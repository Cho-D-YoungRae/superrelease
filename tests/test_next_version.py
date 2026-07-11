import tempfile
import unittest
from pathlib import Path

from helpers import ASSET_SCRIPTS, make_repo, monorepo_config, run_script, scope_config

NV = ASSET_SCRIPTS / "next-version.py"


def out(*args):
    return run_script(NV, *args)


class PureModeTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_bump_levels(self):
        self.check(["--current", "1.2.3", "--bump", "major"], "2.0.0")
        self.check(["--current", "1.2.3", "--bump", "minor"], "1.3.0")
        self.check(["--current", "1.2.3", "--bump", "patch"], "1.2.4")

    def test_release_strips_qualifier(self):
        self.check(["--current", "1.3.0-SNAPSHOT", "--release"], "1.3.0")
        self.check(["--current", "1.3.0", "--release"], "1.3.0")

    def test_bump_from_snapshot_uses_base(self):
        self.check(["--current", "1.3.0-SNAPSHOT", "--bump", "minor"], "1.4.0")

    def test_qualifier_combinations(self):
        self.check(["--current", "1.3.0", "--bump", "minor", "--qualifier", "SNAPSHOT"],
                   "1.4.0-SNAPSHOT")
        self.check(["--current", "1.3.0", "--qualifier", "SNAPSHOT"], "1.3.0-SNAPSHOT")

    def test_build_metadata_dropped(self):
        self.check(["--current", "1.2.3+build.5", "--bump", "patch"], "1.2.4")

    def test_invalid_version_exits_1(self):
        r = out("--current", "abc", "--release")
        self.assertEqual(r.returncode, 1)

    def test_no_operation_exits_2(self):
        r = out("--current", "1.2.3")
        self.assertEqual(r.returncode, 2)

    def test_bump_and_release_mutually_exclusive(self):
        r = out("--current", "1.2.3", "--bump", "minor", "--release")
        self.assertEqual(r.returncode, 2)

    def test_calver_not_supported_yet(self):
        r = out("--current", "2026.07", "--scheme", "calver", "--bump", "patch")
        self.assertEqual(r.returncode, 2)
        self.assertIn("M3", r.stderr)

    def test_invalid_qualifier_exits_2(self):
        r = out("--current", "1.2.3", "--qualifier", "-bad-")
        self.assertEqual(r.returncode, 2)

    def test_current_and_scope_mutually_exclusive(self):
        r = out("--current", "1.2.3", "--scope", "root", "--release")
        self.assertEqual(r.returncode, 2)


class ConfigModeTest(unittest.TestCase):
    def test_reads_current_via_version_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}]),
                {"gradle.properties": "version=1.2.3-SNAPSHOT\n"})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--release")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "1.2.3")


class MultiScopeConfigModeTest(unittest.TestCase):
    def test_scope_selects_right_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, monorepo_config(), {
                "packages/a/package.json": '{\n  "name": "a",\n  "version": "1.0.0"\n}\n',
                "packages/b/package.json": '{\n  "name": "b",\n  "version": "2.0.0"\n}\n'})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--scope", "b", "--bump", "patch")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "2.0.1")


if __name__ == "__main__":
    unittest.main()
