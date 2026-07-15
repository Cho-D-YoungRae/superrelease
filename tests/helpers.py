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
    for name in ("version.py", "next-version.py", "changed-packages.py"):
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
        "developBranch": None,
        "maintenanceLines": False,
        "releaseCommitFormat": "chore(release): {version}",
        "tagTriggersDeployment": False,
        "monorepoStrategy": None,
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


def make_plugin_tree(base, manifest, asset_files, version="0.1.0"):
    base = Path(base)
    assets = base / "skills" / "init" / "assets"
    write(base / ".claude-plugin" / "plugin.json",
          json.dumps({"name": "superrelease", "version": version}) + "\n")
    write(assets / "manifest.json",
          json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for rel, content in asset_files.items():
        write(assets / rel, content)
    return assets


def make_git_repo(tmp, files, commits, tags=()):
    repo = Path(tmp)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)],
                   check=True, capture_output=True)

    def g(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@test",
                        "-c", "user.name=tester", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgsign=false", *args],
                       check=True, capture_output=True, text=True)

    for rel, content in files.items():
        write(repo / rel, content)
    g("add", "-A")
    first = True
    for msg in commits:
        if first:
            g("commit", "-q", "-m", msg)
            first = False
        else:
            g("commit", "-q", "--allow-empty", "-m", msg)
    for t in tags:
        g("tag", "-a", t, "-m", t)
    return repo


def monorepo_config(strategy="independent"):
    """pnpm-style two-scope monorepo config: a (depended on by nothing,
    but declared upstream of b via dependents=["b"]) and b."""

    def pkg_scope(name, dependents):
        return {
            "name": name,
            "path": "packages/" + name,
            "scheme": {"type": "semver", "pattern": None},
            "versionLocations": [
                {"file": "package.json", "type": "json-path", "path": "version"}],
            "tag": {"enabled": True, "format": name + "@{version}",
                    "annotated": True, "signed": False, "movingMajorTag": False},
            "bump": {"mode": "auto-confirm", "sources": ["conventional-commits"],
                     "fallback": "diff", "compatCheck": None},
            "preRelease": {"style": "none", "qualifier": None},
            "devChannel": {"enabled": False, "qualifier": None, "immutableId": []},
            "postRelease": {"bump": "none"},
            "notes": {"destinations": ["changelog", "github-release"],
                      "language": "ko", "audience": "developers", "tone": "neutral",
                      "template": "notes-package.md",
                      "perReleasePath": "docs/releases/"},
            "anchor": {"type": "tag", "value": None},
            "dependents": dependents,
        }

    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = strategy
    cfg["repo"]["releaseCommitFormat"] = "chore(release): {scope}@{version}"
    cfg["scopes"] = [pkg_scope("a", ["b"]), pkg_scope("b", [])]
    return cfg
