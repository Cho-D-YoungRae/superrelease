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


class CalverTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_new_period_resets_micro(self):
        self.check(["--current", "0.1.0", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-07-10"],
                   "2026.7.0")

    def test_same_period_increments_micro(self):
        self.check(["--current", "2026.7.3", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-07-10"],
                   "2026.7.4")

    def test_month_rollover_resets_micro(self):
        self.check(["--current", "2026.7.9", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-08-01"],
                   "2026.8.0")

    def test_zero_padded_tokens(self):
        self.check(["--current", "26.07.1", "--scheme", "calver",
                    "--pattern", "YY.0M.MICRO", "--today", "2026-07-05"],
                   "26.07.2")

    def test_pattern_without_micro_renders_date_only(self):
        self.check(["--current", "2026.06", "--scheme", "calver",
                    "--pattern", "YYYY.0M", "--today", "2026-07-10"],
                   "2026.07")

    def test_pattern_with_no_tokens_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "vvv", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_double_micro_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "MICRO.MICRO", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_calver_missing_pattern_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_calver_rejects_semver_ops(self):
        r = out("--current", "2026.7.0", "--scheme", "calver",
                "--pattern", "YYYY.MM.MICRO", "--bump", "patch")
        self.assertEqual(r.returncode, 2)

    def test_invalid_today_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "YYYY.MM.MICRO", "--today", "07/10/2026")
        self.assertEqual(r.returncode, 2)

    def test_unsupported_standard_token_ww_exits_2(self):
        r = out("--current", "2026.27", "--scheme", "calver",
                "--pattern", "YYYY.WW", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)
        self.assertIn("WW", r.stderr)

    def test_unsupported_standard_token_0y_exits_2(self):
        r = out("--current", "6.7.0", "--scheme", "calver",
                "--pattern", "0Y.MM.MICRO", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)
        self.assertIn("0Y", r.stderr)

    def test_plain_literals_still_allowed(self):
        # Only calver.org standard tokens are rejected; ordinary literal
        # separators/prefixes keep rendering as-is.
        self.check(["--current", "release-2026.06", "--scheme", "calver",
                    "--pattern", "release-YYYY.0M", "--today", "2026-07-10"],
                   "release-2026.07")


class HeadverTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_build_increments_yearweek_from_today(self):
        # 2026-07-10 → ISO (2026, week 28) → yearweek "2628"
        self.check(["--current", "1.2627.4", "--scheme", "headver",
                    "--head", "1", "--today", "2026-07-10"],
                   "1.2628.5")

    def test_iso_year_boundary(self):
        # 2027-01-01(금) → ISO year 2026, week 53 → "2653"
        self.check(["--current", "2.2652.9", "--scheme", "headver",
                    "--head", "2", "--today", "2027-01-01"],
                   "2.2653.10")

    def test_unparseable_current_starts_build_zero(self):
        self.check(["--current", "abc", "--scheme", "headver",
                    "--head", "3", "--today", "2026-07-10"],
                   "3.2628.0")

    def test_missing_head_exits_2(self):
        r = out("--current", "1.2628.0", "--scheme", "headver",
                "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_non_numeric_head_exits_2(self):
        r = out("--current", "1.2628.0", "--scheme", "headver",
                "--head", "vX", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)


class CounterPrereleaseTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_bump_starts_counter_at_one(self):
        self.check(["--current", "1.3.0", "--bump", "minor", "--prerelease", "rc"],
                   "1.4.0-rc.1")

    def test_bump_with_same_qualifier_restarts_counter(self):
        # --bump moves the base, so the counter restarts at 1 even when the
        # current pre-release already uses the same qualifier.
        self.check(["--current", "1.4.0-rc.3", "--bump", "minor",
                    "--prerelease", "rc"],
                   "1.5.0-rc.1")

    def test_same_qualifier_increments(self):
        self.check(["--current", "1.4.0-rc.1", "--prerelease", "rc"], "1.4.0-rc.2")

    def test_other_qualifier_resets_to_one(self):
        self.check(["--current", "1.4.0-SNAPSHOT", "--prerelease", "rc"], "1.4.0-rc.1")

    def test_bare_base_starts_at_one(self):
        self.check(["--current", "1.4.0", "--prerelease", "rc"], "1.4.0-rc.1")

    def test_release_promotes(self):
        self.check(["--current", "1.4.0-rc.2", "--release"], "1.4.0")

    def test_prerelease_release_exclusive(self):
        r = out("--current", "1.4.0-rc.1", "--prerelease", "rc", "--release")
        self.assertEqual(r.returncode, 2)

    def test_prerelease_qualifier_exclusive(self):
        r = out("--current", "1.4.0", "--prerelease", "rc",
                "--qualifier", "SNAPSHOT")
        self.assertEqual(r.returncode, 2)

    def test_invalid_prerelease_qualifier_exits_2(self):
        r = out("--current", "1.4.0", "--prerelease", "-bad-")
        self.assertEqual(r.returncode, 2)

    def test_semver_rejects_today_pattern_head(self):
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--today", "2026-07-10").returncode, 2)
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--pattern", "YYYY").returncode, 2)
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--head", "1").returncode, 2)


class SchemeFromConfigTest(unittest.TestCase):
    def test_calver_scheme_and_pattern_from_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = scope_config(
                [{"file": "package.json", "type": "json-path", "path": "version"}])
            cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
            repo = make_repo(tmp, cfg,
                             {"package.json": '{\n  "name": "x",\n  "version": "2026.7.1"\n}\n'})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--today", "2026-07-10")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "2026.7.2")

    def test_headver_head_from_config_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["scopes"][0]["scheme"] = {"type": "headver", "pattern": "3"}
            repo = make_repo(tmp, cfg, {"gradle.properties": "version=3.2627.7\n"})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--today", "2026-07-10")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "3.2628.8")


if __name__ == "__main__":
    unittest.main()
