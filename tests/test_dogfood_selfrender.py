"""Dogfooding conformance: the committed toolkit must equal a fresh self-render.

superrelease renders its own release toolkit into this repo (.superrelease/ +
.claude/skills/). This re-renders that toolkit from the committed config and
asserts every committed file is byte-identical — so editing an asset template
without re-rendering (or hand-editing a rendered file) fails here immediately.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ASSETS, PLUGIN_SCRIPTS, ROOT, write

CONFIG = ROOT / ".superrelease" / "config.json"
# self-render로 관리되는 툴킷 서브트리
TOOLKIT_DIRS = (".claude/skills", ".superrelease/scripts", ".superrelease/templates")
NOW = "2026-07-16T00:00:00+00:00"


def _is_source(path):
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


class DogfoodSelfRenderTest(unittest.TestCase):
    def _self_render(self, tmp):
        # 디렉터리명을 superrelease로 고정 → project.name 결정론(git remote 무관)
        repo = Path(tmp) / "superrelease"
        (repo / ".superrelease").mkdir(parents=True)
        write(repo / ".superrelease" / "config.json",
              CONFIG.read_text(encoding="utf-8"))
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SCRIPTS / "render.py"),
             "--config", str(repo / ".superrelease" / "config.json"),
             "--assets", str(ASSETS), "--repo", str(repo), "--now", NOW],
            capture_output=True, text=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tmp))})
        # returncode 0 = 커밋된 config가 validate_config를 통과함을 증명
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = {}
        for f in sorted(p for p in repo.rglob("*") if p.is_file() and _is_source(p)):
            rel = f.relative_to(repo).as_posix()
            if rel == ".superrelease/config.json":
                continue
            out[rel] = f.read_text(encoding="utf-8")
        return out

    def _committed_toolkit(self):
        out = {}
        for d in TOOLKIT_DIRS:
            base = ROOT / d
            for f in sorted(p for p in base.rglob("*") if p.is_file() and _is_source(p)):
                out[f.relative_to(ROOT).as_posix()] = f.read_text(encoding="utf-8")
        return out

    def test_committed_toolkit_matches_self_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            rendered = self._self_render(tmp)
        committed = self._committed_toolkit()
        self.assertEqual(
            sorted(committed.keys()), sorted(rendered.keys()),
            "committed toolkit set != self-render set — re-render:\n"
            "  python3 skills/init/scripts/render.py --config "
            ".superrelease/config.json --assets skills/init/assets --repo .")
        for rel in rendered:
            self.assertEqual(committed[rel], rendered[rel], rel)


if __name__ == "__main__":
    unittest.main()
