#!/usr/bin/env python3
# generated-by note: this file is copied verbatim into <repo>/.superrelease/scripts/ by superrelease init.
"""version.py — read, write and verify the project version across all configured locations.

Reads policy from ../config.json (this file must live in .superrelease/scripts/).
Location types: properties-key | json-path | regex (exactly one capture group).
Exit codes: 0 success / 1 validation failure / 2 usage or config error.
"""
import sys

if sys.version_info < (3, 9):
    sys.stderr.write("error: superrelease scripts require Python 3.9+\n")
    sys.exit(2)

import argparse
import json
import re
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


def select_scopes(config, name):
    scopes = config.get("scopes") or []
    if not scopes:
        fail("config has no scopes", 2)
    if name is None:
        return scopes
    matched = [s for s in scopes if s.get("name") == name]
    if not matched:
        fail("unknown scope: " + name, 2)
    return matched


def single_scope(config, name):
    scopes = config.get("scopes") or []
    if name is not None:
        return select_scopes(config, name)[0]
    if len(scopes) == 1:
        return scopes[0]
    fail("multiple scopes defined; use --scope <name>", 2)


def read_text_preserving(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    return (raw.replace("\r\n", "\n") if crlf else raw), crlf


def write_text_preserving(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def detect_json_indent(text):
    m = re.search(r'^([ \t]+)"', text, re.MULTILINE)
    return m.group(1) if m else "  "


def dump_json_like(text, obj):
    out = json.dumps(obj, indent=detect_json_indent(text), ensure_ascii=False)
    if text.endswith("\n"):
        out += "\n"
    return out


def properties_pattern(key):
    return re.compile(r"^(\s*" + re.escape(key) + r"\s*=\s*)(.*?)(\s*)$", re.MULTILINE)


def location_pattern(path, pattern):
    try:
        pat = re.compile(pattern, re.MULTILINE)
    except re.error as e:
        fail(str(path) + ": invalid pattern '" + pattern + "': " + str(e), 2)
    if pat.groups != 1:
        fail(str(path) + ": pattern '" + pattern
             + "' must have exactly one capture group, found " + str(pat.groups), 2)
    return pat


def loc_path(scope, loc):
    return (repo_root() / scope.get("path", ".") / loc["file"]).resolve()


def json_path_get(obj, dotted, path):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            fail(str(path) + ": json path '" + dotted + "' not found", 1)
        cur = cur[part]
    if not isinstance(cur, str):
        fail(str(path) + ": json path '" + dotted + "' is not a string", 1)
    return cur


def read_location(scope, loc):
    path = loc_path(scope, loc)
    if not path.is_file():
        fail(str(path) + ": file not found", 1)
    text, _ = read_text_preserving(path)
    t = loc.get("type")
    if t == "properties-key":
        m = properties_pattern(loc["key"]).search(text)
        if not m:
            fail(str(path) + ": key '" + loc["key"] + "' not found", 1)
        return m.group(2)
    if t == "json-path":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            fail(str(path) + ": invalid JSON: " + str(e), 1)
        return json_path_get(obj, loc["path"], path)
    if t == "regex":
        pat = location_pattern(path, loc["pattern"])
        matches = [m for m in pat.finditer(text) if m.start(1) != -1]
        if not matches:
            fail(str(path) + ": pattern '" + loc["pattern"] + "' not found (needs one capture group)", 1)
        return matches[0].group(1)
    fail("unknown location type: " + str(t), 2)


def sync_package_lock(pkg_path, new_version):
    lock = pkg_path.parent / "package-lock.json"
    if not lock.is_file():
        return
    text, crlf = read_text_preserving(lock)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        fail(str(lock) + ": invalid JSON: " + str(e), 1)
    changed = False
    if isinstance(obj.get("version"), str):
        obj["version"] = new_version
        changed = True
    packages = obj.get("packages")
    if isinstance(packages, dict) and isinstance(packages.get(""), dict) \
            and "version" in packages[""]:
        packages[""]["version"] = new_version
        changed = True
    if changed:
        write_text_preserving(lock, dump_json_like(text, obj), crlf)
        print("package-lock.json: synced to " + new_version)


def set_location(scope, loc, new_version):
    path = loc_path(scope, loc)
    if not path.is_file():
        fail(str(path) + ": file not found", 1)
    text, crlf = read_text_preserving(path)
    t = loc.get("type")
    if t == "properties-key":
        pat = properties_pattern(loc["key"])
        m = pat.search(text)
        if not m:
            fail(str(path) + ": key '" + loc["key"] + "' not found", 1)
        old = m.group(2)
        text = pat.sub(lambda mm: mm.group(1) + new_version + mm.group(3), text, count=1)
        write_text_preserving(path, text, crlf)
        return old
    if t == "json-path":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            fail(str(path) + ": invalid JSON: " + str(e), 1)
        old = json_path_get(obj, loc["path"], path)
        if old == new_version:
            # already current: don't rewrite the JSON (preserve formatting),
            # but still reconcile package-lock as the pre-surgical path did
            if path.name == "package.json":
                sync_package_lock(path, new_version)
            return old
        key = loc["path"].split(".")[-1]
        vpat = re.compile('("' + re.escape(key) + r'"\s*:\s*")' + re.escape(old) + '(")')
        if len(vpat.findall(text)) == 1:
            # surgical: replace only the target value, preserving all other formatting
            text = vpat.sub(lambda m: m.group(1) + new_version + m.group(2), text, count=1)
            write_text_preserving(path, text, crlf)
        else:
            # ambiguous (key/value not unique) — fall back to a full re-dump
            cur = obj
            parts = loc["path"].split(".")
            for part in parts[:-1]:
                cur = cur[part]
            cur[parts[-1]] = new_version
            write_text_preserving(path, dump_json_like(text, obj), crlf)
        if path.name == "package.json":
            sync_package_lock(path, new_version)
        return old
    if t == "regex":
        pat = location_pattern(path, loc["pattern"])
        matches = [m for m in pat.finditer(text) if m.start(1) != -1]
        if not matches:
            fail(str(path) + ": pattern '" + loc["pattern"] + "' not found (needs one capture group)", 1)
        old = matches[0].group(1)
        for m in reversed(matches):
            text = text[:m.start(1)] + new_version + text[m.end(1):]
        write_text_preserving(path, text, crlf)
        return old
    fail("unknown location type: " + str(t), 2)


def locations_of(scope):
    locs = scope.get("versionLocations") or []
    if not locs:
        fail("scope '" + scope.get("name", "?") + "' has no versionLocations", 2)
    return locs


def cmd_get(args):
    config = load_config()
    scope = single_scope(config, args.scope)
    locs = locations_of(scope)
    if args.json:
        entries = [{"file": l["file"], "version": read_location(scope, l)} for l in locs]
        print(json.dumps({"scope": scope["name"], "version": entries[0]["version"],
                          "locations": entries}, ensure_ascii=False, indent=2))
    else:
        print(read_location(scope, locs[0]))


def cmd_set(args):
    config = load_config()
    scope = single_scope(config, args.scope)
    for loc in locations_of(scope):
        old = set_location(scope, loc, args.version)
        print(loc["file"] + ": " + old + " -> " + args.version)


def cmd_verify(args):
    config = load_config()
    report, ok = [], True
    for scope in select_scopes(config, args.scope):
        values = [{"file": l["file"], "version": read_location(scope, l)}
                  for l in locations_of(scope)]
        scope_ok = len({v["version"] for v in values}) == 1
        ok = ok and scope_ok
        report.append({"scope": scope["name"], "ok": scope_ok, "locations": values})
    if args.json:
        print(json.dumps({"ok": ok, "scopes": report}, ensure_ascii=False, indent=2))
    else:
        for r in report:
            print("[" + ("OK" if r["ok"] else "MISMATCH") + "] scope " + r["scope"])
            for l in r["locations"]:
                print("  " + l["file"] + ": " + l["version"])
    sys.exit(0 if ok else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="version.py",
        description="Read, write and verify the project version across all "
                    "locations configured in .superrelease/config.json.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_get = sub.add_parser("get", help="print the current version (first location)")
    p_get.add_argument("--scope", help="scope name (required only for multi-scope configs)")
    p_get.add_argument("--json", action="store_true", help="print all locations as JSON")
    p_get.set_defaults(func=cmd_get)
    p_set = sub.add_parser("set", help="write VERSION to every configured location")
    p_set.add_argument("version")
    p_set.add_argument("--scope")
    p_set.set_defaults(func=cmd_set)
    p_verify = sub.add_parser("verify", help="check that all locations agree (exit 1 on mismatch)")
    p_verify.add_argument("--scope")
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
