import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ASSET_SCRIPTS, make_git_repo, make_repo, monorepo_config, run_script, write

PKG_A = '{\n  "name": "a",\n  "version": "0.1.0"\n}\n'
PKG_B = '{\n  "name": "b",\n  "version": "0.1.0"\n}\n'


def g(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@test",
                    "-c", "user.name=tester", "-c", "commit.gpgsign=false",
                    "-c", "tag.gpgsign=false", *args],
                   check=True, capture_output=True, text=True)


class ChangedPackagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_git_repo(self.tmp.name, files={
            "pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
            "packages/a/package.json": PKG_A,
            "packages/b/package.json": PKG_B,
        }, commits=["feat: init (#1)"])
        make_repo(self.repo, monorepo_config(), {})
        self.cp = self.repo / ".superrelease" / "scripts" / "changed-packages.py"

    def run_cp(self, *args):
        return run_script(self.cp, *args)

    def scopes_by_name(self, stdout):
        return {s["name"]: s for s in json.loads(stdout)["scopes"]}

    def test_first_release_no_anchor_everything_changed(self):
        r = self.run_cp("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        by = self.scopes_by_name(r.stdout)
        self.assertIsNone(by["a"]["anchor"])
        self.assertEqual(by["a"]["anchorType"], "none")
        self.assertTrue(by["a"]["hasChanges"])
        self.assertTrue(by["b"]["hasChanges"])

    def test_tag_anchor_and_path_filter(self):
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "a@0.1.0")
        g(self.repo, "tag", "-a", "b@0.1.0", "-m", "b@0.1.0")
        write(self.repo / "packages" / "b" / "index.js", "console.log(1)\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: b change (#2)")
        by = self.scopes_by_name(self.run_cp("--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@0.1.0")
        self.assertEqual(by["a"]["anchorType"], "tag")
        self.assertFalse(by["a"]["hasChanges"])
        self.assertEqual(by["b"]["anchor"], "b@0.1.0")
        self.assertTrue(by["b"]["hasChanges"])
        self.assertIn("packages/b/index.js", by["b"]["changed"])

    def test_latest_tag_wins(self):
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "x")
        write(self.repo / "packages" / "a" / "index.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: a (#2)")
        g(self.repo, "tag", "-a", "a@0.2.0", "-m", "x")
        by = self.scopes_by_name(self.run_cp("--scope", "a", "--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@0.2.0")
        self.assertFalse(by["a"]["hasChanges"])

    def test_scope_filter_and_unknown_scope(self):
        r = self.run_cp("--scope", "b", "--json")
        self.assertEqual([s["name"] for s in json.loads(r.stdout)["scopes"]], ["b"])
        self.assertEqual(self.run_cp("--scope", "nope").returncode, 2)

    def test_ref_override(self):
        write(self.repo / "packages" / "b" / "index.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: b (#2)")
        by = self.scopes_by_name(self.run_cp("--ref", "HEAD~1", "--json").stdout)
        self.assertEqual(by["a"]["anchorType"], "ref")
        self.assertFalse(by["a"]["hasChanges"])
        self.assertTrue(by["b"]["hasChanges"])

    def test_human_output(self):
        r = self.run_cp()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("packages/a", r.stdout)

    def test_tag_disabled_uses_anchor_value(self):
        # tag.enabled=false + anchor.value 설정 시 그 ref를 anchor로 사용
        cfg = monorepo_config()
        for s in cfg["scopes"]:
            s["tag"]["enabled"] = False
            s["anchor"] = {"type": "ref", "value": "HEAD"}
        (self.repo / ".superrelease" / "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        by = self.scopes_by_name(self.run_cp("--json").stdout)
        self.assertEqual(by["a"]["anchor"], "HEAD")
        self.assertEqual(by["a"]["anchorType"], "ref")

    def test_sibling_prefix_not_confused(self):
        # packages/a 필터가 packages/ab 하위 파일을 오매칭하지 않는다
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "x")
        g(self.repo, "tag", "-a", "b@0.1.0", "-m", "x")
        write(self.repo / "packages" / "ab" / "index.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: ab (#9)")
        by = self.scopes_by_name(self.run_cp("--json").stdout)
        self.assertFalse(by["a"]["hasChanges"])   # packages/ab 변경은 scope a에 안 잡힘

    def test_git_command_failure_exits_2(self):
        # git 저장소가 아닌 디렉터리에서 실행하면 git 실패 → exit 2
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sd = base / ".superrelease" / "scripts"
            sd.mkdir(parents=True)
            (base / ".superrelease" / "config.json").write_text(
                json.dumps(monorepo_config(), ensure_ascii=False), encoding="utf-8")
            shutil.copy(ASSET_SCRIPTS / "changed-packages.py", sd / "changed-packages.py")
            (base / "packages" / "a").mkdir(parents=True)
            (base / "packages" / "a" / "package.json").write_text(
                '{"name":"a","version":"0.1.0"}', encoding="utf-8")
            r = run_script(sd / "changed-packages.py", "--json")
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
