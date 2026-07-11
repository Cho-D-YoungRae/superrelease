import json
import tempfile
import unittest
from pathlib import Path

from helpers import PLUGIN_SCRIPTS, make_git_repo, run_script, write

SCAN = PLUGIN_SCRIPTS / "scan.py"

DEPLOY_YML = "on:\n  push:\n    tags:\n      - 'v*'\njobs: {}\n"


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


if __name__ == "__main__":
    unittest.main()
