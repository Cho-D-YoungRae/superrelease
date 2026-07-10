import unittest

from helpers import PLUGIN_SCRIPTS, load_module

render = load_module(PLUGIN_SCRIPTS / "render.py", "render_mod")

CTX = {
    "repo": {"kind": "app", "releasePath": "direct-push", "maintenanceLines": False},
    "github": {"release": True},
    "scope": {"name": "root", "tag": {"enabled": True},
              "notes": {"language": "ko", "destinations": ["changelog", "github-release"]}},
    "project": {"name": "demo-app"},
}


class EngineTest(unittest.TestCase):
    def r(self, text, ctx=None):
        return render.render_template(text, ctx if ctx is not None else CTX)

    def test_var_substitution(self):
        self.assertEqual(self.r("hi {{project.name}}!"), "hi demo-app!")

    def test_unknown_var_raises(self):
        with self.assertRaises(render.TemplateError):
            self.r("{{project.nope}}")

    def test_if_truthy_and_else(self):
        self.assertEqual(self.r("{{#if github.release}}on{{else}}off{{/if}}"), "on")
        self.assertEqual(self.r("{{#if repo.maintenanceLines}}on{{else}}off{{/if}}"), "off")

    def test_if_equality(self):
        self.assertEqual(self.r('{{#if repo.releasePath == "direct-push"}}push{{/if}}'), "push")
        self.assertEqual(self.r('{{#if repo.kind != "library"}}notlib{{/if}}'), "notlib")
        self.assertEqual(self.r('{{#if repo.kind == "library"}}lib{{else}}app{{/if}}'), "app")

    def test_missing_path_in_condition_is_falsy(self):
        self.assertEqual(self.r("{{#if repo.nothing}}x{{else}}y{{/if}}"), "y")
        self.assertEqual(self.r('{{#if repo.nothing != "x"}}t{{/if}}'), "t")

    def test_unless(self):
        self.assertEqual(self.r("{{#unless repo.maintenanceLines}}no-hotfix{{/unless}}"),
                         "no-hotfix")

    def test_each_with_this(self):
        text = "{{#each scope.notes.destinations}}[{{this}}]{{/each}}"
        self.assertEqual(self.r(text), "[changelog][github-release]")

    def test_each_with_dict_items_and_nested_if(self):
        ctx = dict(CTX)
        ctx["items"] = [{"name": "a", "on": True}, {"name": "b", "on": False}]
        text = "{{#each items}}{{#if this.on}}{{this.name}}{{/if}}{{/each}}"
        self.assertEqual(self.r(text, ctx), "a")

    def test_non_string_var_rendered_as_json(self):
        self.assertEqual(self.r("{{github.release}}"), "true")

    def test_mismatched_close_raises(self):
        with self.assertRaises(render.TemplateError):
            self.r("{{#if github.release}}x{{/each}}")

    def test_unclosed_block_raises(self):
        with self.assertRaises(render.TemplateError):
            self.r("{{#if github.release}}x")

    def test_stray_close_raises(self):
        with self.assertRaises(render.TemplateError):
            self.r("x{{/if}}")

    def test_single_braces_pass_through(self):
        self.assertEqual(self.r("format v{version} stays"), "format v{version} stays")

    def test_explicit_null_var_renders_empty(self):
        ctx = dict(CTX)
        ctx["a"] = {"b": None}
        self.assertEqual(self.r("[{{a.b}}]", ctx), "[]")

    def test_missing_var_still_raises(self):
        with self.assertRaises(render.TemplateError):
            self.r("{{a.nope}}")

    def test_each_missing_path_zero_iterations(self):
        self.assertEqual(self.r("{{#each a.nope}}x{{/each}}"), "")


if __name__ == "__main__":
    unittest.main()
