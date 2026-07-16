import json
import tempfile
import unittest
from pathlib import Path

from helpers import (ASSETS, PLUGIN_SCRIPTS, load_module, monorepo_config,
                     run_script, scope_config, write)

render = load_module(PLUGIN_SCRIPTS / "render.py", "render_for_assets")


def base_ctx(**overrides):
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-app"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx


def mono_ctx(**overrides):
    cfg = monorepo_config()
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-mono"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx


def train_ctx(**overrides):
    cfg = monorepo_config()
    cfg["train"] = {"enabled": True,
                    "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                    "tag": {"format": "train-{version}", "annotated": True,
                            "signed": False}}
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-mono"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx


def gitflow_ctx(**overrides):
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-app"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx


class SkillAssetsTest(unittest.TestCase):
    def render_asset(self, rel, ctx=None):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        return render.render_template(text, ctx or base_ctx())

    def test_release_skill_renders_clean(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-app", out)
        self.assertIn("version.py verify", out)
        self.assertTrue(out.startswith("---\n"))
        self.assertIn("v{version}", out)  # tag.format의 단일 중괄호는 보존된다
        self.assertLessEqual(len(out.splitlines()), 149)  # 마커 1줄 삽입 후 150줄 이하

    def test_release_skill_direct_push_tag_and_github_sections(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("git push origin main", out)
        self.assertIn("git tag -a", out)
        self.assertIn("gh release create", out)
        self.assertIn("chore(release): {version}", out)

    def test_release_skill_omits_github_when_disabled(self):
        ctx = base_ctx(github={"release": False, "generateNotes": False,
                               "releaseYml": False})
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("gh release create", out)
        self.assertNotIn("gh auth status", out)

    def test_release_skill_post_release_none(self):
        ctx = base_ctx()
        ctx["scope"]["postRelease"]["bump"] = "none"
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("post-release bump 없음", out)
        self.assertNotIn("--qualifier SNAPSHOT", out)

    def test_release_skill_warns_on_ci_tag_trigger(self):
        ctx = base_ctx()
        ctx["repo"]["tagTriggersDeployment"] = True
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("배포를 트리거", out)

    def test_release_skill_signed_tag(self):
        ctx = base_ctx()
        ctx["scope"]["tag"]["signed"] = True
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("git tag -s", out)
        self.assertNotIn("git tag -a", out)
        # signed=false (default) still uses annotated -a:
        self.assertIn("git tag -a", self.render_asset("skills/release/SKILL.md"))

    def test_release_skill_calver_branch(self):
        ctx = base_ctx()
        ctx["scope"]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("다음 버전 산출", out)
        self.assertNotIn("bump 제안", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_counter_and_moving_tag(self):
        ctx = base_ctx()
        ctx["scope"]["preRelease"] = {"style": "counter", "qualifier": "rc"}
        ctx["scope"]["tag"]["movingMajorTag"] = True
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("--prerelease rc", out)
        self.assertIn("moving major tag", out)
        self.assertIn("git tag -f", out)
        self.assertIn("--prerelease` 플래그", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_semver_default_has_no_new_blocks(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("bump 제안", out)
        self.assertNotIn("moving major tag", out)
        self.assertNotIn("--prerelease", out)

    def test_release_skill_fragment_and_tag_message(self):
        ctx = base_ctx()
        ctx["scope"]["notes"]["destinations"] = ["fragment", "changelog", "tag-message"]
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("changelog.d", out)          # fragment 프리앰블
        self.assertIn("git rm", out)               # 소비 조각 삭제
        self.assertIn("-F <노트 파일>", out)        # tag-message 메커니즘
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_default_has_no_fragment_or_tag_message(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 destinations = changelog+github-release
        self.assertNotIn("changelog.d", out)
        self.assertNotIn("-F <노트 파일>", out)

    def test_release_skill_release_pr_branch(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("gh pr create", out)
        self.assertIn("릴리스 PR", out)
        self.assertIn("release-pr-body.md", out)
        self.assertIn("chore/next-dev", out)  # §8 복귀 커밋도 PR 경로 안내
        self.assertNotIn("git push origin main`", out)  # direct-push 문장 부재
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_direct_push_has_no_pr_prose(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("git push origin main", out)
        self.assertNotIn("릴리스 PR", out)
        self.assertNotIn("gh pr create", out)
        self.assertNotIn("chore/next-dev", out)

    def test_release_skill_stall_detection_mutable_exception(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 mutable SNAPSHOT
        self.assertIn("중단 상태 감지", out)
        self.assertIn("정상 개발 상태", out)
        self.assertIn("`-SNAPSHOT` 수식어", out)

    def test_release_skill_stall_detection_counter_has_no_mutable_clause(self):
        ctx = base_ctx()
        ctx["scope"]["preRelease"] = {"style": "counter", "qualifier": "rc"}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("중단 상태 감지", out)
        self.assertNotIn("정상 개발 상태", out)

    def test_release_skill_tagless_drops_stall_detection(self):
        ctx = base_ctx()
        ctx["scope"]["tag"]["enabled"] = False
        ctx["scope"]["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("중단 상태 감지", out)

    def test_release_skill_release_pr_open_pr_guard(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out)
        self.assertIn("gh pr list --state open", out)
        self.assertIn("gh pr view release/", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_direct_push_has_no_open_pr_guard(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertNotIn("열린 릴리스 PR", out)
        self.assertNotIn("gh pr list", out)

    def test_release_skill_anchor_uses_tag_format_glob(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("versionsort.suffix=-", out)
        self.assertNotIn("git describe", out)
        self.assertIn("v{version}", out)  # glob 파생 기준 포맷 노출

    def test_release_pr_body_template_language_blocks(self):
        ko = self.render_asset("templates/release-pr-body.md")
        self.assertIn("릴리스 {version}", ko)
        self.assertNotIn("Release {version}", ko)
        ctx = base_ctx()
        ctx["scope"]["notes"]["language"] = "en"
        en = self.render_asset("templates/release-pr-body.md", ctx)
        self.assertIn("Release {version}", en)
        self.assertNotIn("릴리스 {version}", en)

    def test_release_notes_skill_renders_clean(self):
        out = self.render_asset("skills/release-notes/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("PR 메타데이터가 1차 소스", out)  # mergePolicy=squash 기본
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_hotfix_skill_renders_clean(self):
        out = self.render_asset("skills/hotfix/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-app", out)
        self.assertIn("체리픽", out)
        self.assertIn("--bump patch", out)
        self.assertIn("release/1.2.x", out)
        self.assertIn("git push origin release/", out)  # direct-push 기본
        self.assertNotIn("gh pr create", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_hotfix_skill_release_pr_path(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertIn("gh pr create --base release/", out)
        self.assertIn("hotfix/<패치 버전>", out)
        self.assertNotIn("{{", out)
        self.assertIn("수동으로", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_hotfix_anchor_describe_has_match_filter(self):
        out = self.render_asset("skills/hotfix/SKILL.md")
        self.assertIn("git describe --tags --abbrev=0 --match", out)

    def test_hotfix_backport_release_marking_and_changelog(self):
        out = self.render_asset("skills/hotfix/SKILL.md")  # github.release=true, changelog 목적지 포함
        self.assertIn("--latest=false", out)
        self.assertIn("CHANGELOG에도 반영", out)
        ctx = base_ctx(github={"release": False, "generateNotes": False,
                               "releaseYml": False})
        ctx["scope"]["notes"]["destinations"] = ["release-file"]
        out2 = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertNotIn("--latest=false", out2)
        self.assertNotIn("CHANGELOG에도 반영", out2)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_hotfix_gitflow_mentions_develop_backport(self):
        ctx = gitflow_ctx()
        ctx["repo"]["maintenanceLines"] = True
        out = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("`develop` 반영도 함께", out)
        out_trunk = self.render_asset("skills/hotfix/SKILL.md")
        self.assertNotIn("반영도 함께", out_trunk)

    def test_backfill_skill_renders_clean(self):
        out = self.render_asset("skills/backfill/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-app", out)
        self.assertIn("changelog", out.lower())
        self.assertIn("git log", out)
        self.assertIn("태그·버전 bump·push는 하지 않는다", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_backfill_monorepo_branch(self):
        out = self.render_asset("skills/backfill/SKILL.md", mono_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("모노레포 순회", out)
        self.assertIn("<scope>@", out)
        self.assertIn("건너뜀", out)  # tagless skip
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_backfill_single_omits_monorepo_block(self):
        out = self.render_asset("skills/backfill/SKILL.md")  # base_ctx = 단일
        self.assertNotIn("모노레포 순회", out)
        self.assertNotIn("<scope>@", out)

    def test_backfill_release_pr_path(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/backfill/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("docs/backfill-changelog", out)
        self.assertIn("PR로 머지", out)
        self.assertNotIn("CHANGELOG.md만 스테이징", out)  # else 분기 드롭

    def test_backfill_direct_push_commits_directly(self):
        out = self.render_asset("skills/backfill/SKILL.md")  # base_ctx = direct-push
        self.assertIn("CHANGELOG.md만 스테이징", out)
        self.assertNotIn("docs/backfill-changelog", out)

    def test_backfill_sort_uses_versionsort(self):
        out = self.render_asset("skills/backfill/SKILL.md")
        self.assertIn("versionsort.suffix=-", out)

    def test_release_skill_gitflow_branch_and_detection(self):
        out = self.render_asset("skills/release/SKILL.md", gitflow_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("결과가 `develop`", out)          # preflight 1 기준 브랜치
        self.assertIn("origin/develop", out)             # preflight 3 원격 동기화
        self.assertIn("중단 상태 감지 (gitflow)", out)
        self.assertIn("gh pr list --state merged", out)  # 감지 (a)
        self.assertIn("merge-base --is-ancestor", out)   # 감지 (b)
        self.assertIn("back-merge", out)                  # §8
        self.assertIn("git merge main", out)
        self.assertNotIn("chore/next-dev", out)  # gitflow 복귀는 develop 직접
        self.assertIn("머지 커밋", out)                       # Critical #1 merge-commit 요구
        self.assertIn('--search "head:release/"', out)        # Important #3
        self.assertIn("--merged origin/main", out)            # Important #2
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_trunk_has_no_gitflow_prose(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 trunk·direct-push
        self.assertIn("결과가 `main`", out)
        self.assertNotIn("gitflow", out)
        self.assertNotIn("back-merge", out)
        self.assertNotIn("gh pr list --state merged", out)
        self.assertNotIn("merge-base --is-ancestor", out)
        self.assertNotIn("**머지 커밋**", out)

        # §6 "머지 후 재개" 문단(및 squash resume 핀)은 release-pr 경로에만 존재 —
        # trunk·release-pr로 별도 렌더링해 확인한다. bare "머지 커밋"은 이 문단의
        # 기존 문구("...머지 커밋을 받아...")와 우연히 겹치므로(Critical #1과 무관)
        # Edit B가 추가한 굵게 표시된 문구로 특정해 오탐을 피한다.
        pr_ctx = base_ctx()
        pr_ctx["repo"]["releasePath"] = "release-pr"
        pr_out = self.render_asset("skills/release/SKILL.md", pr_ctx)  # trunk·release-pr
        self.assertNotIn("**머지 커밋**", pr_out)              # gitflow 전용 머지-커밋 요구 프로즈 미노출
        self.assertIn("squash 머지로 sha가 바뀐다", pr_out)    # trunk resume 문구 불변 핀

    def test_release_skill_tagless_collapses_section_7(self):
        ctx = base_ctx()
        ctx["scope"]["tag"] = {"enabled": False, "format": "v{version}",
                               "annotated": False, "signed": False,
                               "movingMajorTag": False}
        ctx["scope"]["anchor"] = {"type": "ref", "value": None}
        ctx["scope"]["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertNotIn("## 7. 태그", out)      # 빈 §7 섹션 collapse
        self.assertNotIn("github-release", out)   # §5 범례 게이트

    def test_release_skill_github_release_legend_gated(self):
        ctx = base_ctx()
        ctx["scope"]["notes"]["destinations"] = ["changelog"]  # no github-release dest
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("- `github-release`: 7단계", out)

    def test_release_skill_normal_config_keeps_section_7_and_legend(self):
        out = self.render_asset("skills/release/SKILL.md")  # tag.enabled·github.release 기본 true
        self.assertIn("## 7. 태그", out)
        self.assertIn("- `github-release`: 7단계", out)

    def test_release_skill_release_pr_no_github_has_gh_preflight(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        ctx["scope"]["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("gh 인증", out)               # release-pr은 gh 필요
        self.assertIn("PR 생성·조회에 gh", out)
        self.assertNotIn("제한 모드(태그까지만)", out)  # github.release=false라 릴리스 제한모드 문구 아님

    def test_release_skill_direct_push_no_github_has_no_gh_preflight(self):
        ctx = base_ctx()
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("gh 인증", out)  # direct-push + no github → gh preflight 없음


class FullRenderTest(unittest.TestCase):
    def test_real_assets_render_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            for rel in (".claude/skills/release/SKILL.md",
                        ".claude/skills/release-notes/SKILL.md",
                        ".superrelease/scripts/version.py",
                        ".superrelease/scripts/next-version.py",
                        ".superrelease/templates/notes-single.md",
                        ".superrelease/templates/changelog-entry.md",
                        ".github/release.yml"):
                self.assertTrue((repo / rel).is_file(), rel + " missing")
            self.assertFalse(
                (repo / ".superrelease/templates/release-pr-body.md").exists())
            self.assertFalse((repo / ".claude/skills/hotfix/SKILL.md").exists())
            self.assertFalse((repo / ".claude/skills/backfill/SKILL.md").exists())
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("generated by superrelease v0.1.0", skill)
            verify = run_script(repo / ".superrelease" / "scripts" / "version.py", "verify")
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_release_pr_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["releasePath"] = "release-pr"
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(
                (repo / ".superrelease/templates/release-pr-body.md").is_file())
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("gh pr create", skill)

    def test_maintenance_lines_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["maintenanceLines"] = True
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            hotfix = (repo / ".claude/skills/hotfix/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("generated by superrelease", hotfix)
            self.assertIn("체리픽", hotfix)

    def test_backfill_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["backfill"] = True
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            backfill = (repo / ".claude/skills/backfill/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("generated by superrelease", backfill)
            self.assertIn("git log", backfill)


class MonorepoAssetsTest(unittest.TestCase):
    def render_asset(self, rel, ctx=None):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        return render.render_template(text, ctx or mono_ctx())

    def test_release_monorepo_renders_clean(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-mono", out)
        self.assertIn("changed-packages.py", out)
        self.assertIn("--scope", out)
        self.assertIn("dependents", out)
        self.assertIn("네임스페이스", out)
        self.assertTrue(out.startswith("---\n"))
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_no_scope_inlining(self):
        # scope별 값(태그 포맷, 수식어 등)은 인라인 금지 — a@ 같은 특정 scope 값이 없어야 한다
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertNotIn("a@{version}", out)
        self.assertIn("chore(release): {scope}@{version}", out)  # repo 수준 값은 인라인

    def test_release_monorepo_scheme_and_counter_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("calver/headver", out)
        self.assertIn("--prerelease", out)
        self.assertIn("movingMajorTag", out)
        self.assertNotIn("{{scope.", (ASSETS / "skills/release-monorepo/SKILL.md")
                         .read_text(encoding="utf-8"))  # 무인라인 유지
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_fragment_and_tag_message_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("changelog.d", out)     # fragment 취합 프로즈
        self.assertIn("tag-message", out)     # tag-message 프로즈
        self.assertIn("-F", out)              # -F 노트 파일
        # scope 무인라인 유지 — asset에 {{scope. 리터럴 없음
        self.assertNotIn("{{scope.", (ASSETS / "skills/release-monorepo/SKILL.md")
                         .read_text(encoding="utf-8"))
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_omits_github_when_disabled(self):
        ctx = mono_ctx(github={"release": False, "generateNotes": False,
                               "releaseYml": False})
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("gh release create", out)
        self.assertNotIn("gh auth status", out)

    def test_release_monorepo_release_pr_branch(self):
        ctx = mono_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("릴리스 PR", out)
        self.assertIn("gh pr create", out)
        self.assertIn("scope당 1커밋", out)
        self.assertNotIn("git push origin main`", out)
        self.assertIn("chore/next-dev", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_direct_push_has_no_pr_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("git push origin main", out)
        self.assertNotIn("릴리스 PR", out)
        self.assertNotIn("gh pr create", out)
        self.assertNotIn("chore/next-dev", out)

    def test_release_monorepo_stall_detection_and_open_pr_guard(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("bare 릴리스 버전", out)
        self.assertNotIn("열린 릴리스 PR", out)
        ctx = mono_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out_pr = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out_pr)
        self.assertIn("gh pr view", out_pr)
        self.assertLessEqual(len(out_pr.splitlines()), 149)

    def test_release_notes_monorepo_renders_clean(self):
        out = self.render_asset("skills/release-notes-monorepo/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("changed-packages.py", out)
        self.assertIn("notes-package.md", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_notes_package_language_blocks(self):
        ko = self.render_asset("templates/notes-package.md")
        self.assertIn("하이라이트", ko)
        self.assertNotIn("Highlights", ko)
        ctx = mono_ctx()
        ctx["scope"]["notes"]["language"] = "en"
        en = self.render_asset("templates/notes-package.md", ctx)
        self.assertIn("Highlights", en)
        self.assertNotIn("하이라이트", en)
        ctx["scope"]["notes"]["language"] = "both"
        both = self.render_asset("templates/notes-package.md", ctx)
        self.assertIn("하이라이트", both)
        self.assertIn("Highlights", both)

    def test_release_monorepo_release_pr_no_github_has_gh_preflight(self):
        ctx = mono_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        for s in ctx["scopes"]:
            s["notes"]["destinations"] = ["changelog"]
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("gh 인증", out)
        self.assertIn("PR 생성·조회에 gh", out)


class FullRenderMonorepoTest(unittest.TestCase):
    def test_monorepo_render_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-mono"
            repo.mkdir()
            write(repo / ".superrelease" / "config.json",
                  json.dumps(monorepo_config(), ensure_ascii=False, indent=2))
            write(repo / "packages" / "a" / "package.json",
                  '{\n  "name": "a",\n  "version": "0.1.0"\n}\n')
            write(repo / "packages" / "b" / "package.json",
                  '{\n  "name": "b",\n  "version": "0.1.0"\n}\n')
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("모노레포", skill)
            self.assertIn("changed-packages.py", skill)
            notes_skill = (repo / ".claude/skills/release-notes/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("changed-packages.py", notes_skill)
            self.assertTrue((repo / ".superrelease/scripts/changed-packages.py").is_file())
            self.assertTrue((repo / ".superrelease/templates/notes-package.md").is_file())
            self.assertFalse((repo / ".superrelease/templates/notes-single.md").exists())
            verify = run_script(repo / ".superrelease" / "scripts" / "version.py", "verify")
            self.assertEqual(verify.returncode, 0, verify.stderr)


class ReleaseTrainAssetsTest(unittest.TestCase):
    def render_asset(self, rel, ctx):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        return render.render_template(text, ctx)

    def test_release_train_renders_clean(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("demo-mono", out)
        self.assertIn("changed-packages.py --json", out)
        self.assertIn("--pattern YYYY.MICRO", out)
        self.assertIn("train-{version}", out)  # tag.format 단일 중괄호 보존

    def test_release_train_tag_listing_uses_versionsort(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("versionsort.suffix=-", out)

    def test_release_train_direct_push_path(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("git push origin main", out)
        self.assertIn("git tag -a", out)
        self.assertNotIn("release/train-", out)

    def test_release_train_release_pr_path(self):
        ctx = train_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("release/train-", out)
        self.assertIn("gh pr create", out)
        self.assertNotIn("통합 노트 파일을 커밋하고 `git push origin main`", out)

    def test_release_train_signed_tag(self):
        ctx = train_ctx()
        ctx["train"]["tag"]["signed"] = True
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("git tag -s", out)
        self.assertNotIn("git tag -a", out)

    def test_release_train_omits_github_when_disabled(self):
        ctx = train_ctx()
        ctx["github"]["release"] = False
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertNotIn("gh release create", out)
        self.assertNotIn("gh auth status", out)

    def test_release_train_stall_detection_and_open_pr_guard(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("bare 릴리스 버전", out)
        self.assertNotIn("열린 릴리스 PR", out)
        ctx = train_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out_pr = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out_pr)
        self.assertIn("gh pr view release/train-", out_pr)

    def test_release_train_warns_on_ci_tag_trigger(self):
        ctx = train_ctx()
        ctx["repo"]["tagTriggersDeployment"] = True
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("배포를 트리거", out)
        self.assertNotIn("배포를 트리거",
                         self.render_asset("skills/release-train/SKILL.md", train_ctx()))

    def test_notes_train_renders_clean_ko(self):
        out = self.render_asset("templates/notes-train.md", train_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("포함 버전 스냅샷", out)
        self.assertIn("demo-mono train {version}", out)  # 헤딩 단일 중괄호 보존
        self.assertNotIn("Version Snapshot", out)  # en 블록은 ko에서 드롭

    def test_release_train_release_pr_no_github_has_gh_preflight(self):
        ctx = train_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("gh 인증", out)
        self.assertIn("PR 생성·조회에 gh", out)


if __name__ == "__main__":
    unittest.main()
