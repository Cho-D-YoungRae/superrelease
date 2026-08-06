import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from golden_configs import GOLDEN
from helpers import ASSETS, PLUGIN_SCRIPTS, normalize_marker_version, write

GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"
NOW = "2026-01-01T00:00:00+00:00"


class GoldenRenderTest(unittest.TestCase):
    def render_case(self, name, build, tmp):
        repo = Path(tmp) / name  # 디렉터리명 고정 → project.name 결정론
        repo.mkdir()
        write(repo / ".superrelease" / "config.json",
              json.dumps(build(), ensure_ascii=False, indent=2) + "\n")
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SCRIPTS / "render.py"),
             "--config", str(repo / ".superrelease" / "config.json"),
             "--assets", str(ASSETS), "--repo", str(repo), "--now", NOW],
            capture_output=True, text=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tmp))})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return repo

    def tree(self, root, skip_config=False):
        out = {}
        for f in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = f.relative_to(root).as_posix()
            if skip_config and rel == ".superrelease/config.json":
                continue
            out[rel] = normalize_marker_version(f.read_text(encoding="utf-8"))
        return out

    def test_golden_snapshots(self):
        for name, build in GOLDEN.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                repo = self.render_case(name, build, tmp)
                actual = self.tree(repo, skip_config=True)
                expected_root = GOLDEN_ROOT / name / "expected"
                self.assertTrue(expected_root.is_dir(),
                                "golden missing — run: python3 tests/update_golden.py")
                expected = self.tree(expected_root)
                self.assertEqual(sorted(actual.keys()), sorted(expected.keys()), name)
                for rel in expected:
                    self.assertEqual(actual[rel], expected[rel], name + "/" + rel)

    def test_project_name_ignores_enclosing_git_repo(self):
        # tmp 루트가 origin 있는 git 레포여도 project.name은 디렉터리명이어야 한다
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", str(tmp)], check=True)
            subprocess.run(["git", "-C", str(tmp), "remote", "add", "origin",
                            "https://example.com/enclosing-name.git"], check=True)
            repo = self.render_case("gradle-app", GOLDEN["gradle-app"], tmp)
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("gradle-app", skill)
            self.assertNotIn("enclosing-name", skill)


class GoldenContentTest(unittest.TestCase):
    """스냅샷 동일성 위에, 신규 골든의 의도(핵심 분기)를 명시적으로 고정한다."""

    def read(self, name, rel):
        return (GOLDEN_ROOT / name / "expected" / rel).read_text(encoding="utf-8")

    def test_gitflow_tagless_hotfix_collapses_tag_section(self):
        skill = self.read("gitflow-tagless-hotfix", ".claude/skills/hotfix/SKILL.md")
        self.assertNotIn("## 6. 태그", skill)

    def test_trunk_monorepo_bundle_renders_round_notes(self):
        skill = self.read("trunk-monorepo-bundle", ".claude/skills/release/SKILL.md")
        self.assertIn("bundle 라운드 노트", skill)
        self.assertIn("--current-among", skill)

    def test_hotfix_release_pr_uses_maintenance_base(self):
        # "release/<라인>" 자체는 branching과 무관하게(direct-push든 release-pr든)
        # 항상 등장해 release-pr 분기를 판별하지 못한다(hotfix-library에도 동일
        # 문자열이 있음). release-pr 분기에서만, 그리고 gitflow 플레이버(base가
        # {{repo.defaultBranch}})와 달리 maintenanceLines 플레이버에서만 등장하는
        # PR 생성 커맨드 전체를 검사한다.
        skill = self.read("hotfix-release-pr", ".claude/skills/hotfix/SKILL.md")
        self.assertIn("gh pr create --base release/<라인>", skill)

    def test_gitflow_fixed_monorepo_renders_single_flavor(self):
        skill = self.read("gitflow-fixed-monorepo", ".claude/skills/release/SKILL.md")
        self.assertIn("## 7. 태그", skill)  # 단일 flavor 섹션 번호 (모노레포는 ## 8)

    def test_mixed_tags_monorepo_notes_per_scope_skip(self):
        skill = self.read("mixed-tags-monorepo", ".claude/skills/release/SKILL.md")
        self.assertIn("태그를 쓰지 않는 scope", skill)


if __name__ == "__main__":
    unittest.main()
