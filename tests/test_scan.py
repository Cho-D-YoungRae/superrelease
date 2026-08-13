import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import PLUGIN_SCRIPTS, load_module, make_git_repo, run_script, write

SCAN = PLUGIN_SCRIPTS / "scan.py"

DEPLOY_YML = "on:\n  push:\n    tags:\n      - 'v*'\njobs: {}\n"

POM_WITH_REVISION = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <groupId>com.example</groupId>\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>${revision}</version>\n"
    "  <properties>\n"
    "    <revision>1.2.0-SNAPSHOT</revision>\n"
    "  </properties>\n"
    "</project>\n")

POM_PLAIN_VERSION = (
    "<project>\n"
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <parent>\n"
    "    <groupId>g</groupId>\n"
    "    <artifactId>p</artifactId>\n"
    "    <version>9.9.9</version>\n"
    "  </parent>\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>1.2.0</version>\n"
    "</project>\n")

POM_PARENT_ONLY = (
    "<project>\n"
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <parent>\n"
    "    <groupId>g</groupId>\n"
    "    <artifactId>p</artifactId>\n"
    "    <version>9.9.9</version>\n"
    "  </parent>\n"
    "  <artifactId>demo</artifactId>\n"
    "</project>\n")

OPENAPI_YAML = (
    "openapi: 3.0.3\n"
    "info:\n"
    "  title: Demo API\n"
    "  version: 2.4.0\n"
    "paths: {}\n")

POM_COMMENTED_REVISION = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <!-- <revision>0.9.0</revision> legacy -->\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>${revision}</version>\n"
    "  <properties>\n"
    "    <revision>1.2.0</revision>\n"
    "  </properties>\n"
    "</project>\n")

POM_PROFILE_REVISION = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>${revision}</version>\n"
    "  <properties>\n"
    "    <revision>1.2.0</revision>\n"
    "  </properties>\n"
    "  <profiles>\n"
    "    <profile>\n"
    "      <properties>\n"
    "        <revision>1.2.0-SNAPSHOT</revision>\n"
    "      </properties>\n"
    "    </profile>\n"
    "  </profiles>\n"
    "</project>\n")

OPENAPI_YAML_TWO_VERSIONS = (
    "openapi: 3.0.3\n"
    "info:\n"
    "  title: Demo API\n"
    "  version: 2.4.0\n"
    "components:\n"
    "  schemas:\n"
    "    Widget:\n"
    "      properties:\n"
    "        version: 1.0.0\n")


class ScanTest(unittest.TestCase):
    def test_gradle_app_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"gradle.properties": "version=1.2.0\n",
                       "build.gradle.kts": "plugins { }\n",
                       "CHANGELOG.md": "# Changelog\n",
                       ".github/workflows/deploy.yml": DEPLOY_YML},
                commits=["feat: one (#1)", "fix: two (#2)", "docs: three (#3)",
                         "plain message"],
                tags=("v1.1.0", "v1.2.0"))
            r = run_script(SCAN, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertTrue(data["git"])
            self.assertIn("gradle", data["buildSystems"])
            files = [c["file"] for c in data["versionCandidates"]]
            self.assertIn("gradle.properties", files)
            self.assertEqual(data["tags"]["byPattern"]["semver-v"], 2)
            self.assertFalse(data["tags"]["mixed"])
            self.assertEqual(data["tags"]["latest"], "v1.2.0")
            self.assertTrue(data["tags"]["latestAnnotated"])
            self.assertEqual(data["commits"]["conventionalRate"], 0.75)
            self.assertEqual(data["commits"]["mergePolicyGuess"], "squash")
            self.assertEqual(data["branches"]["current"], "main")
            self.assertTrue(data["changelog"]["changelogMd"])
            self.assertEqual(data["ci"]["tagTriggerCandidates"],
                             [".github/workflows/deploy.yml"])
            self.assertFalse(data["monorepo"]["suspected"])

    def test_node_repo_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"package.json": '{"name": "x", "version": "0.1.0"}\n',
                       "pnpm-lock.yaml": "lockfileVersion: 9\n"},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertIn("node:pnpm", data["buildSystems"])
            cand = data["versionCandidates"][0]
            self.assertEqual(cand["file"], "package.json")
            self.assertEqual(cand["type"], "json-path")
            self.assertEqual(cand["path"], "version")
            self.assertEqual(cand["value"], "0.1.0")

    def test_non_git_dir_still_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "package.json", '{"name": "x", "version": "0.1.0"}\n')
            r = run_script(SCAN, "--repo", tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertFalse(data["git"])
            self.assertFalse(data["tags"]["available"])

    def test_monorepo_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": "packages:\n  - packages/*\n",
                       "packages/a/package.json": '{"name": "a", "version": "0.1.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertTrue(data["monorepo"]["suspected"])

    def test_missing_dir_exits_2(self):
        r = run_script(SCAN, "--repo", "/nonexistent-superrelease-test")
        self.assertEqual(r.returncode, 2)

    def test_monorepo_packages_and_internal_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/a/package.json":
                           '{"name": "a", "version": "0.1.0"}\n',
                       "packages/b/package.json":
                           '{"name": "b", "version": "0.2.0", '
                           '"dependencies": {"a": "workspace:^"}}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            mono = data["monorepo"]
            self.assertTrue(mono["suspected"])
            paths = {p["path"]: p for p in mono["packages"]}
            self.assertEqual(sorted(paths), ["packages/a", "packages/b"])
            self.assertEqual(paths["packages/a"]["version"], "0.1.0")
            deps = mono["internalDependencies"]
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0]["fromName"], "b")
            self.assertEqual(deps[0]["toName"], "a")
            self.assertEqual(deps[0]["toPath"], "packages/a")

    def test_root_workspaces_field_enumerates_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"package.json":
                           '{"name": "root", "workspaces": ["libs/*"]}\n',
                       "libs/x/package.json":
                           '{"name": "x", "version": "1.0.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["libs/x"])

    def test_double_star_glob_enumerates_immediate_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"package.json":
                           '{"name": "root", "workspaces": ["libs/**"]}\n',
                       "libs/x/package.json":
                           '{"name": "x", "version": "1.0.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["libs/x"])

    def test_literal_path_workspace_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"package.json":
                           '{"name": "root", "workspaces": ["tools/cli"]}\n',
                       "tools/cli/package.json":
                           '{"name": "cli", "version": "2.0.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["tools/cli"])

    def test_non_object_package_json_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/a/package.json": "[]\n",
                       "packages/b/package.json":
                           '{"name": "b", "version": "0.1.0"}\n'},
                commits=["chore: init"])
            r = run_script(SCAN, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            names = [p.get("name") for p in data["monorepo"]["packages"]]
            self.assertIn("b", names)     # valid package still enumerated
            self.assertNotIn(None, names) # the "[]" package was skipped, not crashed on

    def _candidates_by_file(self, repo):
        data = json.loads(run_script(SCAN, "--repo", repo).stdout)
        return {c["file"]: c for c in data["versionCandidates"]}

    def test_pom_revision_property_is_usable_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_WITH_REVISION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "1.2.0-SNAPSHOT")
            self.assertEqual(cand["pattern"], "<revision>([^<]+)</revision>")
            self.assertNotIn("usable", cand)

    def test_pom_plain_version_detected_but_not_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_PLAIN_VERSION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertEqual(cand["value"], "1.2.0")  # parent의 9.9.9가 아니라 project 직계
            self.assertIs(cand["usable"], False)
            self.assertEqual(cand["advice"], "maven-project-version")
            self.assertNotIn("pattern", cand)

    def test_pom_parent_only_yields_no_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_PARENT_ONLY},
                                 commits=["chore: init"])
            self.assertNotIn("pom.xml", self._candidates_by_file(repo))

    def test_pom_commented_revision_downgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_COMMENTED_REVISION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertEqual(cand["value"], "1.2.0")   # ET reads the canonical one
            self.assertIs(cand["usable"], False)         # but the regex is ambiguous
            self.assertNotIn("pattern", cand)

    def test_pom_profile_revision_downgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_PROFILE_REVISION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertIs(cand["usable"], False)
            self.assertNotIn("pattern", cand)

    def test_version_file_versionish_content_is_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.4.2\n"},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["VERSION"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "1.4.2")
            self.assertEqual(cand["pattern"], "^(\\S+)\\s*$")

    def test_version_file_prose_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"VERSION": "see docs for versioning policy\n"},
                commits=["chore: init"])
            self.assertNotIn("VERSION", self._candidates_by_file(repo))

    def test_openapi_json_info_version_is_json_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"openapi.json":
                       '{"openapi": "3.0.3", "info": {"title": "x", "version": "2.4.0"}}\n'},
                commits=["chore: init"])
            cand = self._candidates_by_file(repo)["openapi.json"]
            self.assertEqual(cand["type"], "json-path")
            self.assertEqual(cand["path"], "info.version")
            self.assertEqual(cand["value"], "2.4.0")

    def test_openapi_yaml_indented_info_version_is_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"swagger.yaml": OPENAPI_YAML},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["swagger.yaml"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "2.4.0")

    def test_openapi_yaml_toplevel_version_key_not_matched(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"openapi.yaml": "version: 9.9.9\npaths: {}\n"},
                commits=["chore: init"])
            self.assertNotIn("openapi.yaml", self._candidates_by_file(repo))

    def test_openapi_yaml_multiple_version_keys_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp,
                                 files={"openapi.yaml": OPENAPI_YAML_TWO_VERSIONS},
                                 commits=["chore: init"])
            self.assertNotIn("openapi.yaml", self._candidates_by_file(repo))

    def test_openapi_json_non_versionish_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"openapi.json":
                       '{"info": {"title": "x", "version": "N/A"}}\n'},
                commits=["chore: init"])
            self.assertNotIn("openapi.json", self._candidates_by_file(repo))

    def test_claude_plugin_manifest_is_json_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={".claude-plugin/plugin.json":
                       '{"name": "demo", "version": "1.3.0"}\n'},
                commits=["chore: init"])
            cand = self._candidates_by_file(repo)[".claude-plugin/plugin.json"]
            self.assertEqual(cand["type"], "json-path")
            self.assertEqual(cand["path"], "version")
            self.assertEqual(cand["value"], "1.3.0")
            self.assertNotIn("usable", cand)  # usable 후보는 키 생략(package.json·openapi와 동일)

    def test_plugin_manifest_detected_plugin_json_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertEqual(pm["detected"], True)
            self.assertEqual(pm["version"], "1.3.0")
            self.assertNotIn("marketplaceVersion", pm)

    def test_plugin_manifest_marketplace_self_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={
                    ".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n',
                    ".claude-plugin/marketplace.json":
                        '{"name": "demo", "metadata": {"version": "1.3.0"},'
                        ' "plugins": [{"name": "demo", "source": "./"}]}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertEqual(pm["marketplaceVersion"], "1.3.0")
            self.assertIs(pm["marketplaceSelfListed"], True)

    def test_plugin_manifest_marketplace_multi_not_self_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={
                    ".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n',
                    ".claude-plugin/marketplace.json":
                        '{"metadata": {"version": "9.9.9"},'
                        ' "plugins": [{"name": "demo", "source": "./"},'
                        ' {"name": "other", "source": "./other"}]}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertIs(pm["marketplaceSelfListed"], False)

    def test_plugin_manifest_single_plugin_name_mismatch_not_self_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={
                    ".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n',
                    ".claude-plugin/marketplace.json":
                        '{"metadata": {"version": "1.3.0"},'
                        ' "plugins": [{"name": "different", "source": "./"}]}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertIs(pm["marketplaceSelfListed"], False)   # name 불일치 → 게이트 차단
            self.assertEqual(pm["marketplaceVersion"], "1.3.0")  # 감지는 유지

    def test_plugin_manifest_absent_for_non_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"package.json": '{"name": "x", "version": "1.0.0"}\n'},
                commits=["chore: init"])
            self.assertIsNone(json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"])

    def test_gradle_multimodule_packages_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"settings.gradle":
                           'rootProject.name = "demo"\n'
                           'include(":app")\n'
                           "include ':lib-a', ':lib-b'\n"
                           'include(":nested:core")\n',
                       "app/build.gradle": 'version = "1.0.0"\n',
                       "lib-a/gradle.properties": "version=2.0.0\n",
                       "lib-b/build.gradle.kts": 'version = "3.0.0"\n',
                       "nested/core/build.gradle": "// no version\n"},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            mono = data["monorepo"]
            self.assertTrue(mono["suspected"])
            by_path = {p["path"]: p for p in mono["packages"]}
            self.assertEqual(sorted(by_path),
                             ["app", "lib-a", "lib-b", "nested/core"])
            self.assertEqual(by_path["app"]["version"], "1.0.0")
            self.assertEqual(by_path["lib-a"]["version"], "2.0.0")   # properties 우선
            self.assertEqual(by_path["lib-b"]["version"], "3.0.0")
            self.assertIsNone(by_path["nested/core"]["version"])
            self.assertEqual(by_path["nested/core"]["name"], "core")
            self.assertTrue(all(p["buildSystem"] == "gradle"
                                for p in mono["packages"]))

    def test_node_packages_carry_build_system_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/a/package.json":
                           '{"name": "a", "version": "0.1.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual(data["monorepo"]["packages"][0]["buildSystem"],
                             "node")

    def test_gradle_module_missing_dir_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"settings.gradle": 'include(":ghost")\ninclude(":real")\n',
                       "real/build.gradle": 'version = "1.0.0"\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["real"])

    def test_mixed_node_and_gradle_dedup_node_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/shared/package.json":
                           '{"name": "shared", "version": "1.0.0"}\n',
                       "packages/shared/build.gradle": 'version = "2.0.0"\n',
                       "settings.gradle":
                           'include(":packages:shared")\ninclude(":gradle-only")\n',
                       "gradle-only/build.gradle": 'version = "3.0.0"\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            by_path = {p["path"]: p for p in data["monorepo"]["packages"]}
            # packages/shared is in both node workspace and gradle include —
            # node wins (single entry, node buildSystem, node version), the
            # gradle duplicate is deduped out.
            self.assertEqual(sorted(by_path),
                             ["gradle-only", "packages/shared"])
            self.assertEqual(by_path["packages/shared"]["buildSystem"], "node")
            self.assertEqual(by_path["packages/shared"]["version"], "1.0.0")
            self.assertEqual(by_path["gradle-only"]["buildSystem"], "gradle")
            self.assertEqual(by_path["gradle-only"]["version"], "3.0.0")

    def test_gradle_commented_include_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"settings.gradle":
                           'include(":app") // include(":legacy")\n',
                       "app/build.gradle": 'version = "1.0.0"\n',
                       "legacy/build.gradle": 'version = "9.9.9"\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            paths = [p["path"] for p in data["monorepo"]["packages"]]
            self.assertIn("app", paths)
            self.assertNotIn("legacy", paths)

    def _branch(self, repo, name):
        subprocess.run(["git", "-C", str(repo), "branch", name],
                       check=True, capture_output=True)

    def test_develop_branch_guess_variants(self):
        for branch, expect in (("develop", "develop"),
                               ("development", "development"),
                               ("dev", "dev")):
            with self.subTest(branch=branch), \
                    tempfile.TemporaryDirectory() as tmp:
                repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                     commits=["chore: init"])
                self._branch(repo, branch)
                data = json.loads(run_script(SCAN, "--repo", repo).stdout)
                self.assertTrue(data["branches"]["hasDevelop"])
                self.assertEqual(data["branches"]["developBranchGuess"], expect)

    def test_develop_wins_over_dev(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                 commits=["chore: init"])
            self._branch(repo, "dev")
            self._branch(repo, "develop")
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual(data["branches"]["developBranchGuess"], "develop")

    def test_no_develop_branch_guess_is_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                 commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertFalse(data["branches"]["hasDevelop"])
            self.assertIsNone(data["branches"]["developBranchGuess"])

    def test_bundle_notes_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "docs" / "release" / "2026.05.0.md", "x\n")
            write(repo / "docs" / "release" / "2026.05.1.md", "x\n")
            write(repo / "docs" / "release" / "README.md", "x\n")
            r = run_script(SCAN, "--repo", repo)
            data = json.loads(r.stdout)
            guess = data["changelog"]["bundleNotesGuess"]
            self.assertEqual(guess["dir"], "docs/release/")
            self.assertEqual(guess["notes"], ["2026.05.0", "2026.05.1"])

    def test_bundle_notes_guess_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_script(SCAN, "--repo", tmp)
            data = json.loads(r.stdout)
            self.assertIsNone(data["changelog"]["bundleNotesGuess"])

    def test_bundle_note_re_requires_dot_separated_groups(self):
        # ^\d{4}[.\d]+$ 는 순수 8자리(20260101)도 매치했다 — 점 구분 필수로 조인다
        scan = load_module(PLUGIN_SCRIPTS / "scan.py", "scan_module")
        self.assertIsNotNone(scan.BUNDLE_NOTE_RE.match("2026.07.1"))
        self.assertIsNotNone(scan.BUNDLE_NOTE_RE.match("2026.07"))
        self.assertIsNone(scan.BUNDLE_NOTE_RE.match("20260101"))
        self.assertIsNone(scan.BUNDLE_NOTE_RE.match("2026"))


def scan_tmp(testcase, files):
    with tempfile.TemporaryDirectory() as tmp:
        for rel, content in files.items():
            write(Path(tmp) / rel, content)
        r = run_script(SCAN, "--repo", tmp)
        testcase.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class MobileScanTest(unittest.TestCase):
    def test_pubspec_clean_version_is_usable_candidate(self):
        report = scan_tmp(self, {"pubspec.yaml":
                                 "name: demo\nversion: 1.2.3\n\ndependencies:\n  flutter:\n    sdk: flutter\n"})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "pubspec.yaml"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "1.2.3")
        self.assertEqual(cands[0]["type"], "regex")
        self.assertNotIn("usable", cands[0])
        self.assertIn("flutter", report["buildSystems"])

    def test_pubspec_build_number_becomes_marketing_only_candidate(self):
        # M10: `+N`이 있으면 마케팅 부분만 캡처하는 usable 후보로 승격 —
        # set()이 캡처 그룹만 치환하므로 +N은 보존된다. advice-only는 폐지.
        report = scan_tmp(self, {"pubspec.yaml": "name: demo\nversion: 1.2.3+45\n"})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "pubspec.yaml"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "1.2.3")
        self.assertEqual(cands[0]["buildNumber"], "45")
        self.assertNotIn("usable", cands[0])
        self.assertEqual(cands[0]["pattern"], "^version:\\s*(\\d[^+\\s]*)")
        self.assertIn("dart", report["buildSystems"])

    def test_xcconfig_build_setting_reference_is_skipped(self):
        # M10(M9 이월): $(inherited) 같은 빌드 세팅 참조는 후보가 아니다.
        report = scan_tmp(self, {
            "Base.xcconfig": "MARKETING_VERSION = $(inherited)\n",
            "App.xcconfig": "MARKETING_VERSION = 2.0.1\n"})
        files = [c["file"] for c in report["versionCandidates"]
                 if c["file"].endswith(".xcconfig")]
        self.assertEqual(files, ["App.xcconfig"])

    def test_flutter_classification_top_level_section(self):
        # M10(M9 이월): ^[ \t]*flutter: — 최상위 flutter: 섹션도 Flutter 신호,
        # 개행 관통 메커니즘에는 의존하지 않는다.
        top = scan_tmp(self, {"pubspec.yaml":
                              "name: demo\nversion: 1.2.3\n\nflutter:\n  uses-material-design: true\n"})
        self.assertIn("flutter", top["buildSystems"])
        plain = scan_tmp(self, {"pubspec.yaml": "name: demo\nversion: 1.2.3\n"})
        self.assertIn("dart", plain["buildSystems"])

    def test_xcconfig_marketing_version_root_and_ios(self):
        report = scan_tmp(self, {
            "Config.xcconfig": "MARKETING_VERSION = 2.0.1\nCURRENT_PROJECT_VERSION = 77\n",
            "ios/App.xcconfig": "MARKETING_VERSION = 2.0.1\n"})
        files = sorted(c["file"] for c in report["versionCandidates"]
                       if c["file"].endswith(".xcconfig"))
        self.assertEqual(files, ["Config.xcconfig", "ios/App.xcconfig"])
        for c in report["versionCandidates"]:
            if c["file"].endswith(".xcconfig"):
                self.assertEqual(c["value"], "2.0.1")
        # CURRENT_PROJECT_VERSION(빌드 번호)은 감지하지 않는다
        joined = json.dumps(report["versionCandidates"])
        self.assertNotIn("CURRENT_PROJECT_VERSION", joined)

    def test_android_version_name_conventional_paths(self):
        report = scan_tmp(self, {
            "android/app/build.gradle":
                'android {\n  defaultConfig {\n    versionCode 45\n    versionName "3.1.0"\n  }\n}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "android/app/build.gradle"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "3.1.0")
        # versionCode(빌드 번호)는 감지하지 않는다
        self.assertNotIn("45", json.dumps(report["versionCandidates"]))

    def test_android_version_name_kotlin_dsl(self):
        report = scan_tmp(self, {
            "app/build.gradle.kts":
                'android {\n  defaultConfig {\n    versionCode = 45\n'
                '    versionName = "4.2.0"\n    versionNameSuffix = "-dev"\n  }\n}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "app/build.gradle.kts"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "4.2.0")


class TauriHelmInfraScanTest(unittest.TestCase):
    def test_tauri_v2_top_level_version(self):
        report = scan_tmp(self, {"src-tauri/tauri.conf.json":
                                 '{"productName": "demo", "version": "0.5.0"}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "src-tauri/tauri.conf.json"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "0.5.0")
        self.assertEqual(cands[0]["path"], "version")

    def test_tauri_v1_package_version_fallback(self):
        report = scan_tmp(self, {"src-tauri/tauri.conf.json":
                                 '{"package": {"productName": "demo", "version": "0.4.2"}}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "src-tauri/tauri.conf.json"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "0.4.2")
        self.assertEqual(cands[0]["path"], "package.version")

    def test_chart_app_version_is_advice_only(self):
        report = scan_tmp(self, {"Chart.yaml":
                                 "apiVersion: v2\nname: demo\nversion: 1.4.0\nappVersion: \"2.9.1\"\n"})
        chart = [c for c in report["versionCandidates"] if c["file"] == "Chart.yaml"]
        self.assertEqual(len(chart), 2)  # version(기존) + appVersion(신규)
        app = [c for c in chart if c.get("advice") == "chart-app-version"]
        self.assertEqual(len(app), 1)
        self.assertFalse(app[0]["usable"])

    def test_charts_children_become_helm_packages(self):
        report = scan_tmp(self, {
            "charts/api/Chart.yaml": "apiVersion: v2\nname: api\nversion: 0.3.0\n",
            "charts/web/Chart.yaml": "apiVersion: v2\nname: web\nversion: 0.8.0\n"})
        self.assertIn("charts/: Chart.yaml children", report["monorepo"]["signals"])
        helm = [p for p in report["monorepo"]["packages"]
                if p["buildSystem"] == "helm"]
        self.assertEqual([(p["path"], p["version"]) for p in helm],
                         [("charts/api", "0.3.0"), ("charts/web", "0.8.0")])
        self.assertTrue(report["monorepo"]["suspected"])

    def test_go_and_terraform_build_systems(self):
        report = scan_tmp(self, {"go.mod": "module example.com/demo\n\ngo 1.22\n",
                                 "main.tf": 'resource "null_resource" "x" {}\n'})
        self.assertIn("go", report["buildSystems"])
        self.assertIn("terraform", report["buildSystems"])
        self.assertEqual(report["versionCandidates"], [])  # 버전 후보 아님


class WorkspaceScanTest(unittest.TestCase):
    def test_uv_workspace_members_and_internal_deps(self):
        report = scan_tmp(self, {
            "pyproject.toml":
                '[project]\nname = "root"\nversion = "0.0.0"\n\n'
                '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
            "packages/core/pyproject.toml":
                '[project]\nname = "demo-core"\nversion = "1.1.0"\ndependencies = []\n',
            "packages/api/pyproject.toml":
                '[project]\nname = "demo-api"\nversion = "2.0.0"\n'
                'dependencies = ["demo-core>=1.0", "fastapi>=0.100"]\n'})
        self.assertIn("pyproject.toml: [tool.uv.workspace]",
                      report["monorepo"]["signals"])
        py = [p for p in report["monorepo"]["packages"]
              if p["buildSystem"] == "python"]
        self.assertEqual([(p["path"], p["name"], p["version"]) for p in py],
                         [("packages/api", "demo-api", "2.0.0"),
                          ("packages/core", "demo-core", "1.1.0")])
        internal = report["monorepo"]["internalDependencies"]
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal[0]["fromName"], "demo-api")
        self.assertEqual(internal[0]["toName"], "demo-core")

    def test_maven_modules_become_hints_not_packages(self):
        report = scan_tmp(self, {
            "pom.xml":
                "<project>\n  <modelVersion>4.0.0</modelVersion>\n"
                "  <artifactId>parent</artifactId>\n  <version>${revision}</version>\n"
                "  <properties>\n    <revision>1.0.0</revision>\n  </properties>\n"
                "  <modules>\n    <module>core</module>\n    <module>api</module>\n"
                "  </modules>\n</project>\n"})
        self.assertEqual(report["monorepo"]["mavenModuleHints"], ["api", "core"])
        self.assertIn("pom.xml: <modules>", report["monorepo"]["signals"])
        self.assertEqual([p for p in report["monorepo"]["packages"]
                          if p["buildSystem"] == "maven"], [])


class ScopedTagScanTest(unittest.TestCase):
    def test_scoped_tags_classified_and_prefixes_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_git_repo(tmp, {"f.txt": "x\n"}, ["chore: seed"],
                          tags=["core@1.0.0", "core@1.1.0", "api@0.2.0",
                                "@acme/core@2.0.0", "@acme/core@2.1.0",
                                "@acme/core@2.2.0", "v9.9.9"])
            r = run_script(SCAN, "--repo", tmp)
            report = json.loads(r.stdout)
        tags = report["tags"]
        self.assertEqual(tags["byPattern"]["scoped"], 6)
        self.assertEqual(tags["byPattern"]["semver-v"], 1)
        self.assertEqual(tags["otherCount"], 0)
        self.assertTrue(tags["mixed"])  # scoped + semver-v 두 그룹
        self.assertEqual(tags["scopedPrefixes"], ["@acme/core", "core", "api"])  # 빈도순

    def test_no_scoped_tags_gives_empty_prefixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_git_repo(tmp, {"f.txt": "x\n"}, ["chore: seed"], tags=["v1.0.0"])
            r = run_script(SCAN, "--repo", tmp)
            report = json.loads(r.stdout)
        self.assertEqual(report["tags"]["scopedPrefixes"], [])


class ReleaseAutomationScanTest(unittest.TestCase):
    def test_changesets_with_pending_count(self):
        report = scan_tmp(self, {
            ".changeset/README.md": "readme\n",
            ".changeset/config.json": "{}\n",
            ".changeset/wild-cats-jump.md": "---\n'demo': patch\n---\nfix\n",
            ".changeset/tame-dogs-sit.md": "---\n'demo': minor\n---\nfeat\n"})
        tools = {t["name"]: t for t in report["releaseAutomation"]["tools"]}
        self.assertIn("changesets", tools)
        self.assertEqual(tools["changesets"]["pendingFragments"], 2)  # README 제외

    def test_semantic_release_via_releaserc_and_package_json(self):
        report = scan_tmp(self, {
            ".releaserc.json": "{}\n",
            "package.json": '{"name": "d", "version": "1.0.0", '
                            '"devDependencies": {"semantic-release": "^24.0.0"}}\n'})
        tools = {t["name"]: t for t in report["releaseAutomation"]["tools"]}
        self.assertIn("semantic-release", tools)
        self.assertIn(".releaserc.json", tools["semantic-release"]["signals"])
        self.assertIn("package.json:devDependencies",
                      tools["semantic-release"]["signals"])

    def test_release_please_and_towncrier(self):
        report = scan_tmp(self, {
            "release-please-config.json": "{}\n",
            "pyproject.toml": '[tool.towncrier]\ndirectory = "changelog.d"\n'})
        names = [t["name"] for t in report["releaseAutomation"]["tools"]]
        self.assertIn("release-please", names)
        self.assertIn("towncrier", names)

    def test_ci_workflow_referencing_tool_is_listed(self):
        report = scan_tmp(self, {
            ".changeset/config.json": "{}\n",
            ".github/workflows/release.yml":
                "on: push\njobs:\n  r:\n    steps:\n"
                "      - uses: changesets/action@v1\n"})
        self.assertEqual(report["releaseAutomation"]["ciWorkflows"],
                         [".github/workflows/release.yml"])

    def test_clean_repo_reports_empty(self):
        report = scan_tmp(self, {"README.md": "# demo\n"})
        self.assertEqual(report["releaseAutomation"],
                         {"tools": [], "ciWorkflows": []})


class ScanRefinementTest(unittest.TestCase):
    def test_python_deps_scoped_to_project_table(self):
        # [tool.x] 테이블의 행-시작 dependencies 배열을 오탐하지 않는다.
        report = scan_tmp(self, {
            "pyproject.toml":
                '[project]\nname = "root"\nversion = "0.0.0"\n\n'
                '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
            "packages/api/pyproject.toml":
                '[project]\nname = "demo-api"\nversion = "1.0.0"\n\n'
                '[tool.custom]\ndependencies = ["demo-core"]\n',
            "packages/core/pyproject.toml":
                '[project]\nname = "demo-core"\nversion = "1.0.0"\n'})
        self.assertEqual(report["monorepo"]["internalDependencies"], [])

    def test_charts_child_that_is_node_package_not_duplicated(self):
        report = scan_tmp(self, {
            "pnpm-workspace.yaml": 'packages:\n  - "charts/*"\n',
            "charts/web/package.json": '{"name": "web", "version": "1.0.0"}\n',
            "charts/web/Chart.yaml": "apiVersion: v2\nname: web\nversion: 0.1.0\n"})
        paths = [p["path"] for p in report["monorepo"]["packages"]]
        self.assertEqual(paths.count("charts/web"), 1)

    def test_commented_version_name_not_matched(self):
        report = scan_tmp(self, {
            "app/build.gradle":
                'android {\n  defaultConfig {\n'
                '    // versionName "9.9.9"\n'
                '    versionName "3.1.0"\n  }\n}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "app/build.gradle"]
        self.assertEqual(cands[0]["value"], "3.1.0")


if __name__ == "__main__":
    unittest.main()
