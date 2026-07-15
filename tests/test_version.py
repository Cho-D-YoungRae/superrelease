import json
import tempfile
import unittest
from pathlib import Path

from helpers import make_repo, monorepo_config, run_script, scope_config, write

PKG = '{\n  "name": "demo",\n  "version": "1.2.3",\n  "scripts": {\n    "build": "tsc"\n  }\n}\n'
LOCK = json.dumps({
    "name": "demo", "version": "1.2.3", "lockfileVersion": 3,
    "packages": {"": {"name": "demo", "version": "1.2.3"}},
}, indent=2) + "\n"


def vp(repo):
    return Path(repo) / ".superrelease" / "scripts" / "version.py"


class VersionTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def repo_with(self, locations, files):
        return make_repo(self.tmp.name, scope_config(locations), files)


class PropertiesAndRegexTest(VersionTestBase):
    def test_get_properties_key(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"}],
            {"gradle.properties": "group=com.example\nversion=1.2.3\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1.2.3")

    def test_set_properties_touches_only_value(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"}],
            {"gradle.properties": "group=com.example\nversion=1.2.3\nfoo=bar\n"})
        r = run_script(vp(repo), "set", "1.3.0-SNAPSHOT")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gradle.properties: 1.2.3 -> 1.3.0-SNAPSHOT", r.stdout)
        content = (Path(repo) / "gradle.properties").read_text(encoding="utf-8")
        self.assertEqual(content, "group=com.example\nversion=1.3.0-SNAPSHOT\nfoo=bar\n")

    def test_set_preserves_crlf(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"}],
            {"gradle.properties": "group=com.example\r\nversion=1.2.3\r\n"})
        run_script(vp(repo), "set", "2.0.0")
        raw = (Path(repo) / "gradle.properties").read_bytes()
        self.assertEqual(raw, b"group=com.example\r\nversion=2.0.0\r\n")

    def test_regex_location_badge(self):
        repo = self.repo_with(
            [{"file": "README.md", "type": "regex",
              "pattern": r"version-([0-9][A-Za-z0-9.-]*)-blue"}],
            {"README.md": "# demo\n![v](https://img.shields.io/badge/version-1.2.3-blue)\n"})
        self.assertEqual(run_script(vp(repo), "get").stdout.strip(), "1.2.3")
        run_script(vp(repo), "set", "1.2.4")
        text = (Path(repo) / "README.md").read_text(encoding="utf-8")
        self.assertIn("version-1.2.4-blue", text)

    def test_verify_ok_and_mismatch(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"},
             {"file": "README.md", "type": "regex",
              "pattern": r"version-([0-9][A-Za-z0-9.-]*)-blue"}],
            {"gradle.properties": "version=1.2.3\n",
             "README.md": "badge/version-1.2.3-blue\n"})
        self.assertEqual(run_script(vp(repo), "verify").returncode, 0)
        write(Path(repo) / "README.md", "badge/version-9.9.9-blue\n")
        r = run_script(vp(repo), "verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISMATCH", r.stdout)

    def test_missing_key_exits_1(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"}],
            {"gradle.properties": "group=com.example\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not found", r.stderr)

    def test_unknown_scope_exits_2(self):
        repo = self.repo_with(
            [{"file": "gradle.properties", "type": "properties-key", "key": "version"}],
            {"gradle.properties": "version=1.0.0\n"})
        r = run_script(vp(repo), "get", "--scope", "nope")
        self.assertEqual(r.returncode, 2)

    def test_regex_two_groups_exits_2(self):
        repo = self.repo_with(
            [{"file": "README.md", "type": "regex",
              "pattern": r"(v)(\d+\.\d+\.\d+)"}],
            {"README.md": "v1.2.3\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one capture group", r.stderr)


class JsonPathTest(VersionTestBase):
    def test_get_and_set_package_json(self):
        repo = self.repo_with(
            [{"file": "package.json", "type": "json-path", "path": "version"}],
            {"package.json": PKG})
        self.assertEqual(run_script(vp(repo), "get").stdout.strip(), "1.2.3")
        run_script(vp(repo), "set", "1.3.0")
        obj = json.loads((Path(repo) / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(obj["version"], "1.3.0")

    def test_json_roundtrip_only_version_changes(self):
        repo = self.repo_with(
            [{"file": "package.json", "type": "json-path", "path": "version"}],
            {"package.json": PKG})
        run_script(vp(repo), "set", "1.3.0")
        expected = PKG.replace('"version": "1.2.3"', '"version": "1.3.0"')
        self.assertEqual((Path(repo) / "package.json").read_text(encoding="utf-8"), expected)

    def test_package_lock_synced(self):
        repo = self.repo_with(
            [{"file": "package.json", "type": "json-path", "path": "version"}],
            {"package.json": PKG, "package-lock.json": LOCK})
        r = run_script(vp(repo), "set", "1.3.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        lock = json.loads((Path(repo) / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["version"], "1.3.0")
        self.assertEqual(lock["packages"][""]["version"], "1.3.0")

    def test_get_json_flag(self):
        repo = self.repo_with(
            [{"file": "package.json", "type": "json-path", "path": "version"}],
            {"package.json": PKG})
        r = run_script(vp(repo), "get", "--json")
        data = json.loads(r.stdout)
        self.assertEqual(data["version"], "1.2.3")
        self.assertEqual(data["locations"][0]["file"], "package.json")

    def test_malformed_json_target_exits_1(self):
        repo = self.repo_with(
            [{"file": "package.json", "type": "json-path", "path": "version"}],
            {"package.json": "{bad json"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid JSON", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class MultiScopeTest(VersionTestBase):
    A = '{\n  "name": "a",\n  "version": "1.0.0"\n}\n'
    B = '{\n  "name": "b",\n  "version": "2.0.0"\n}\n'

    def mono_repo(self):
        return make_repo(self.tmp.name, monorepo_config(), {
            "packages/a/package.json": self.A,
            "packages/b/package.json": self.B})

    def test_get_per_scope(self):
        repo = self.mono_repo()
        self.assertEqual(run_script(vp(repo), "get", "--scope", "a").stdout.strip(),
                         "1.0.0")
        self.assertEqual(run_script(vp(repo), "get", "--scope", "b").stdout.strip(),
                         "2.0.0")

    def test_get_without_scope_exits_2(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--scope", r.stderr)

    def test_set_touches_only_target_scope(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "set", "1.1.0", "--scope", "a")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = json.loads((Path(repo) / "packages/a/package.json").read_text(encoding="utf-8"))
        b = json.loads((Path(repo) / "packages/b/package.json").read_text(encoding="utf-8"))
        self.assertEqual(a["version"], "1.1.0")
        self.assertEqual(b["version"], "2.0.0")

    def test_verify_reports_each_scope(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "verify")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scope a", r.stdout)
        self.assertIn("scope b", r.stdout)


class RegexGuardTest(VersionTestBase):
    def test_multi_group_pattern_set_exits_2_without_writing(self):
        content = "A-1.0.0 and B-1.0.0 end\n"
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex",
              "pattern": r"A-(\d+\.\d+\.\d+)|B-(\d+\.\d+\.\d+)"}],
            {"V.md": content})
        r = run_script(vp(repo), "set", "2.0.0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one capture group", r.stderr)
        self.assertEqual((Path(repo) / "V.md").read_text(encoding="utf-8"), content)

    def test_multi_group_pattern_get_exits_2(self):
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex", "pattern": r"(a)-(\d+)"}],
            {"V.md": "a-1\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one capture group", r.stderr)

    def test_invalid_regex_exits_2(self):
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex", "pattern": r"ver-([0-9]+"}],
            {"V.md": "ver-1\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid pattern", r.stderr)

    def test_alternation_single_group_replaces_participating_matches(self):
        # 그룹이 1개면 비참여 alternation 가지는 건너뛰고 참여 매치만 치환한다
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex",
              "pattern": r"version-([0-9][0-9.]*)-blue|version_badge"}],
            {"V.md": "version_badge\nversion-1.2.3-blue\n"})
        r = run_script(vp(repo), "set", "1.2.4")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (Path(repo) / "V.md").read_text(encoding="utf-8")
        self.assertIn("version-1.2.4-blue", text)
        self.assertIn("version_badge\n", text)
        self.assertEqual(run_script(vp(repo), "get").stdout.strip(), "1.2.4")


if __name__ == "__main__":
    unittest.main()
