import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from golden_configs import GOLDEN
from helpers import ASSETS, PLUGIN_SCRIPTS, write

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
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return repo

    def tree(self, root, skip_config=False):
        out = {}
        for f in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = f.relative_to(root).as_posix()
            if skip_config and rel == ".superrelease/config.json":
                continue
            out[rel] = f.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
