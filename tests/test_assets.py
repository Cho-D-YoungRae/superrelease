import unittest

from helpers import ASSETS, PLUGIN_SCRIPTS, load_module, scope_config

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

    def test_release_notes_skill_renders_clean(self):
        out = self.render_asset("skills/release-notes/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("PR 메타데이터가 1차 소스", out)  # mergePolicy=squash 기본
        self.assertLessEqual(len(out.splitlines()), 149)


if __name__ == "__main__":
    unittest.main()
