import json
import tempfile
import unittest
from pathlib import Path

from helpers import make_repo, run_script, scope_config, write

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


if __name__ == "__main__":
    unittest.main()
