import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import PLUGIN_SCRIPTS, make_git_repo, run_script, write

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


if __name__ == "__main__":
    unittest.main()
