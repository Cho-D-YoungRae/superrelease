#!/usr/bin/env python3
"""changed-packages.py — list scopes changed since their last release anchor.

For each scope in .superrelease/config.json (this file must live in
.superrelease/scripts/), resolve the anchor — the latest tag matching the
scope's tag format, the configured anchor ref, or none (first release) —
then diff anchor..HEAD and keep files under the scope's path prefix.
Pass --ref to override the anchor for every scope.
Exit codes: 0 success / 2 usage, config or git error.
"""
import sys

if sys.version_info < (3, 9):
    sys.stderr.write("error: superrelease scripts require Python 3.9+\n")
    sys.exit(2)

import argparse
import json
import subprocess
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def fail(msg, code):
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(code)


def load_config():
    if not CONFIG_PATH.is_file():
        fail("config not found: " + str(CONFIG_PATH), 2)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("invalid config JSON: " + str(e), 2)


def repo_root():
    return Path(__file__).resolve().parent.parent.parent


def git(*args):
    try:
        proc = subprocess.run(["git", "-C", str(repo_root())] + list(args),
                              capture_output=True, text=True)
    except FileNotFoundError:
        fail("git is not available on PATH", 2)
    if proc.returncode != 0:
        fail("git " + " ".join(args) + " failed: " + proc.stderr.strip(), 2)
    return proc.stdout


def latest_tag(tag_format):
    if "{version}" not in (tag_format or ""):
        return None
    glob = tag_format.replace("{version}", "*")
    lines = [l for l in git("tag", "--list", glob, "--sort=-v:refname").splitlines()
             if l.strip()]
    return lines[0] if lines else None


def path_prefix(scope_path):
    p = (scope_path or ".").strip("/")
    return "" if p in ("", ".") else p + "/"


def resolve_anchor(scope, ref):
    if ref:
        return ref, "ref"
    tag_cfg = scope.get("tag") or {}
    if tag_cfg.get("enabled"):
        tag = latest_tag(tag_cfg.get("format") or "")
        return (tag, "tag") if tag else (None, "none")
    value = (scope.get("anchor") or {}).get("value")
    return (value, "ref") if value else (None, "none")


def changed_for(scope, ref):
    anchor, kind = resolve_anchor(scope, ref)
    prefix = path_prefix(scope.get("path"))
    if anchor:
        out = git("diff", "--name-only", anchor + "..HEAD")
    else:
        out = git("ls-files", "--", scope.get("path") or ".")
    files = [f for f in out.splitlines() if f.strip()]
    if prefix:
        files = [f for f in files if f.startswith(prefix)]
    return {"name": scope.get("name"), "path": scope.get("path"),
            "anchor": anchor, "anchorType": kind,
            "hasChanges": bool(files), "changedCount": len(files),
            "changed": files}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="changed-packages.py",
        description="List scopes changed since their last release anchor "
                    "(per-scope latest tag, configured anchor ref, or --ref).")
    parser.add_argument("--scope", help="limit to one scope")
    parser.add_argument("--ref",
                        help="use REF as the anchor for every scope "
                             "instead of auto-resolving")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output")
    args = parser.parse_args(argv)

    config = load_config()
    scopes = config.get("scopes") or []
    if not scopes:
        fail("config has no scopes", 2)
    if args.scope:
        scopes = [s for s in scopes if s.get("name") == args.scope]
        if not scopes:
            fail("unknown scope: " + args.scope, 2)

    report = [changed_for(s, args.ref) for s in scopes]
    if args.json:
        print(json.dumps({"scopes": report}, ensure_ascii=False, indent=2))
    else:
        for r in report:
            mark = "*" if r["hasChanges"] else " "
            print("{} {:<16} {:<24} anchor={}  changed={}".format(
                mark, r["name"], r["path"], r["anchor"] or "(none)",
                r["changedCount"]))


if __name__ == "__main__":
    main()
