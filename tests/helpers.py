"""Shared fixtures for superrelease tests. Stdlib only."""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET_SCRIPTS = ROOT / "skills" / "init" / "assets" / "scripts"
PLUGIN_SCRIPTS = ROOT / "skills" / "init" / "scripts"
ASSETS = ROOT / "skills" / "init" / "assets"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_script(script, *args, cwd=None):
    return subprocess.run(
        [sys.executable, str(script)] + [str(a) for a in args],
        capture_output=True, text=True, cwd=cwd,
    )


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def make_repo(tmp, config, files):
    repo = Path(tmp)
    scripts_dir = repo / ".superrelease" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    write(repo / ".superrelease" / "config.json",
          json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    for name in ("version.py", "next-version.py"):
        src = ASSET_SCRIPTS / name
        if src.is_file():
            shutil.copy(src, scripts_dir / name)
    for rel, content in files.items():
        write(repo / rel, content)
    return repo


def scope_config(locations, **repo_overrides):
    scope = {
        "name": "root",
        "path": ".",
        "scheme": {"type": "semver", "pattern": None},
        "versionLocations": locations,
        "tag": {"enabled": True, "format": "v{version}", "annotated": True,
                "signed": False, "movingMajorTag": False},
        "bump": {"mode": "auto-confirm", "sources": ["conventional-commits"],
                 "fallback": "diff", "compatCheck": None},
        "preRelease": {"style": "mutable", "qualifier": "SNAPSHOT"},
        "devChannel": {"enabled": False, "qualifier": "SNAPSHOT", "immutableId": []},
        "postRelease": {"bump": "next-snapshot"},
        "notes": {"destinations": ["changelog", "github-release"], "language": "ko",
                  "audience": "developers", "tone": "neutral",
                  "template": "notes-single.md", "perReleasePath": "docs/releases/"},
        "anchor": {"type": "tag", "value": None},
        "dependents": [],
    }
    repo = {
        "kind": "app", "defaultBranch": "main", "mergePolicy": "squash",
        "releasePath": "direct-push", "branching": "trunk",
        "maintenanceLines": False, "train": False,
        "releaseCommitFormat": "chore(release): {version}",
        "tagTriggersDeployment": False,
    }
    repo.update(repo_overrides)
    return {
        "superrelease": {"pluginVersion": "0.1.0", "configVersion": 1,
                          "generatedAt": "2026-01-01T00:00:00+00:00"},
        "repo": repo,
        "github": {"release": True, "generateNotes": True, "releaseYml": True},
        "scopes": [scope],
        "decisions": [],
    }
