#!/usr/bin/env python3
"""Regenerate golden render snapshots under tests/golden/<name>/expected.

Run from the repo root:  python3 tests/update_golden.py
Then review `git diff` — goldens are reviewed, committed artifacts.
NOTE: bumping the plugin version in .claude-plugin/plugin.json changes the
generated markers, so goldens must be regenerated (and reviewed) afterwards.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_configs import GOLDEN  # noqa: E402
from helpers import ASSETS, PLUGIN_SCRIPTS, write  # noqa: E402

GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"
NOW = "2026-01-01T00:00:00+00:00"


def render_into(name, build, dest_root):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / name
        repo.mkdir()
        write(repo / ".superrelease" / "config.json",
              json.dumps(build(), ensure_ascii=False, indent=2) + "\n")
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SCRIPTS / "render.py"),
             "--config", str(repo / ".superrelease" / "config.json"),
             "--assets", str(ASSETS), "--repo", str(repo), "--now", NOW],
            capture_output=True, text=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": tmp})
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            sys.exit(1)
        if dest_root.exists():
            shutil.rmtree(dest_root)
        for f in sorted(p for p in repo.rglob("*") if p.is_file()):
            rel = f.relative_to(repo)
            if rel.as_posix() == ".superrelease/config.json":
                continue
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)


def main():
    for name, build in GOLDEN.items():
        render_into(name, build, GOLDEN_ROOT / name / "expected")
        print("updated golden:", name)


if __name__ == "__main__":
    main()
