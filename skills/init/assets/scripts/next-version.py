#!/usr/bin/env python3
"""next-version.py — compute the next version string. Deterministic arithmetic only.

Schemes:
  semver   --bump/--release/--qualifier/--prerelease act on the current version.
  calver   next version from --today and the pattern
           (tokens: YYYY YY 0M MM 0D DD MICRO; MICRO at most once;
           other calver.org standard tokens are rejected).
  headver  {head}.{yearweek}.{build} — head from --head or scheme.pattern,
           yearweek = 2-digit ISO year + 2-digit ISO week (from --today),
           build = current version's third field + 1 (never resets).

Two input modes: --current VER (pure, config-free) or config mode, which reads
the scheme from ../config.json and the current version via the sibling
version.py. All semver operations act on the qualifier-stripped base version.
Exit codes: 0 success / 1 validation failure / 2 usage or config error.
"""
import sys

if sys.version_info < (3, 9):
    sys.stderr.write("error: superrelease scripts require Python 3.9+\n")
    sys.exit(2)

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
SEMVER_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)"
    r"(?:-([0-9A-Za-z][0-9A-Za-z.-]*))?"
    r"(?:\+([0-9A-Za-z][0-9A-Za-z.-]*))?$")
QUALIFIER_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.-]*$")
CALVER_RENDER = {
    "YYYY": lambda d: "{:04d}".format(d.year),
    "YY": lambda d: str(d.year % 100),
    "0M": lambda d: "{:02d}".format(d.month),
    "MM": lambda d: str(d.month),
    "0D": lambda d: "{:02d}".format(d.day),
    "DD": lambda d: str(d.day),
}
# split_calver_pattern scans this list first-match, so YYYY must stay ahead
# of its prefix YY ("YYYY" would otherwise tokenize as YY+YY).
CALVER_TOKEN_ORDER = ["YYYY", "MICRO", "YY", "0M", "0D", "MM", "DD"]
# calver.org tokens this script does not compute — rejected so a pattern like
# "YYYY.WW" cannot silently render "WW" as literal text.
CALVER_UNSUPPORTED_TOKENS = ("WW", "0W", "0Y", "MAJOR", "MINOR", "MODIFIER")


def fail(msg, code):
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(code)


def parse_semver(s):
    m = SEMVER_RE.match(s)
    if not m:
        fail("not a valid SemVer version: " + s, 1)
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def parse_today(value):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail("invalid --today (expected YYYY-MM-DD): " + value, 2)


def load_scope(name):
    if not CONFIG_PATH.is_file():
        fail("config not found: " + str(CONFIG_PATH), 2)
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("invalid config JSON: " + str(e), 2)
    scopes = config.get("scopes") or []
    if not scopes:
        fail("config has no scopes", 2)
    if name:
        matched = [s for s in scopes if s.get("name") == name]
        if not matched:
            fail("unknown scope: " + name, 2)
        return matched[0]
    if len(scopes) == 1:
        return scopes[0]
    fail("multiple scopes defined; use --scope <name>", 2)


def current_from_config(scope):
    script = Path(__file__).resolve().parent / "version.py"
    cmd = [sys.executable, str(script), "get"]
    if scope:
        cmd += ["--scope", scope]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)
    return proc.stdout.strip()


def split_calver_pattern(pattern):
    parts = []
    i = 0
    while i < len(pattern):
        for name in CALVER_TOKEN_ORDER:
            if pattern.startswith(name, i):
                parts.append(("tok", name))
                i += len(name)
                break
        else:
            parts.append(("lit", pattern[i]))
            i += 1
    return parts


def parse_calver_pattern(pattern):
    """Split and validate a calver pattern; returns the parts list.
    Shared by calver_next (next computation) and calver_max (candidate
    selection) so both reject unsupported tokens identically."""
    if not pattern:
        fail("calver requires --pattern or scheme.pattern in config", 2)
    parts = split_calver_pattern(pattern)
    # "\x00" marks consumed tokens so literals on either side of one cannot
    # join into a false token match when scanned below.
    literals = "".join(val if kind == "lit" else "\x00" for kind, val in parts)
    for unsupported in CALVER_UNSUPPORTED_TOKENS:
        if unsupported in literals:
            fail("unsupported calver token in pattern: " + unsupported
                 + " (supported: YYYY YY 0M MM 0D DD MICRO)", 2)
    tokens = [val for kind, val in parts if kind == "tok"]
    if not tokens:
        fail("invalid calver pattern (no tokens): " + pattern, 2)
    if tokens.count("MICRO") > 1:
        fail("calver pattern may contain MICRO at most once: " + pattern, 2)
    return parts


def calver_max(candidates, pattern):
    """Return the highest candidate matching the calver pattern (numeric
    token comparison — lexicographic order breaks on MICRO 10 vs 2).
    Non-matching candidates are ignored; zero matches is an error."""
    parts = parse_calver_pattern(pattern)
    regex = re.compile("^" + "".join(
        re.escape(val) if kind == "lit" else r"(\d+)"
        for kind, val in parts) + "$")
    best = best_key = None
    for cand in candidates:
        m = regex.match(cand.strip())
        if not m:
            continue
        key = tuple(int(g) for g in m.groups())
        if best_key is None or key > best_key:
            best, best_key = cand.strip(), key
    if best is None:
        fail("no candidate matches calver pattern '" + pattern
             + "' (wrong notes path?)", 1)
    return best


def calver_next(current, pattern, today):
    parts = parse_calver_pattern(pattern)
    pieces = []  # rendered date/literal strings; None marks the MICRO slot
    for kind, val in parts:
        if kind == "lit":
            pieces.append(val)
        elif val == "MICRO":
            pieces.append(None)
        else:
            pieces.append(CALVER_RENDER[val](today))
    if None not in pieces:
        result = "".join(pieces)
        if result == (current or "").strip():
            fail("calver pattern '" + pattern + "' has no MICRO token and the "
                 "computed version equals the current version (" + result
                 + "); a same-period re-release needs MICRO in the pattern", 1)
        return result
    same_period = re.compile(
        "^" + "".join(r"(\d+)" if p is None else re.escape(p) for p in pieces) + "$")
    m = same_period.match(current or "")
    micro = int(m.group(1)) + 1 if m else 0
    return "".join(str(micro) if p is None else p for p in pieces)


def headver_next(current, head, today):
    head = "" if head is None else str(head).strip()
    if not head:
        fail("headver requires --head or scheme.pattern with the head number", 2)
    if not re.match(r"^\d+$", head):
        fail("invalid head (must be a number): " + head, 2)
    iso = today.isocalendar()
    yearweek = "{:02d}{:02d}".format(iso[0] % 100, iso[1])
    build = 0
    m = re.match(r"^\d+\.\d+\.(\d+)$", (current or "").strip())
    if m:
        build = int(m.group(1)) + 1
    return "{}.{}.{}".format(head, yearweek, build)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="next-version.py",
        description="Compute the next version string (SemVer, CalVer, HeadVer).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--current", help="current version (omit to read via version.py)")
    mode.add_argument("--scope", help="scope name for config mode")
    mode.add_argument("--current-among", nargs="+", metavar="VER",
                      help="calver only: take the highest pattern-matching "
                           "candidate as the current version")
    parser.add_argument("--scheme", choices=["semver", "calver", "headver"],
                        help="version scheme (config mode default: scheme.type)")
    parser.add_argument("--pattern", help="calver pattern, e.g. YYYY.MM.MICRO")
    parser.add_argument("--head", help="headver head number")
    parser.add_argument("--today",
                        help="date override YYYY-MM-DD (calver/headver only)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--bump", choices=["major", "minor", "patch"])
    group.add_argument("--release", action="store_true",
                       help="strip the pre-release qualifier")
    parser.add_argument("--qualifier", help="append -QUALIFIER to the result")
    parser.add_argument("--prerelease", metavar="QUAL",
                        help="issue or advance an immutable counter pre-release "
                             "(-QUAL.N); combinable with --bump")
    args = parser.parse_args(argv)

    scheme = args.scheme
    pattern = args.pattern
    head = args.head
    # Read the config only for what it can still supply (scheme type,
    # calver pattern, headver head); the current version is fetched via
    # version.py, which parses the config itself.
    if args.current is None and args.current_among is None and (scheme is None
                                 or (scheme == "calver" and pattern is None)
                                 or (scheme == "headver" and head is None)):
        cfg_scheme = load_scope(args.scope).get("scheme") or {}
        scheme = scheme or cfg_scheme.get("type") or "semver"
        if scheme == "calver" and pattern is None:
            pattern = cfg_scheme.get("pattern")
        if scheme == "headver" and head is None:
            head = cfg_scheme.get("pattern")
    else:
        scheme = scheme or "semver"

    has_semver_op = bool(args.bump or args.release or args.qualifier
                         or args.prerelease)

    if scheme in ("calver", "headver"):
        if has_semver_op:
            fail("--bump/--release/--qualifier/--prerelease do not apply to "
                 + scheme, 2)
        if scheme == "calver" and args.head is not None:
            fail("--head does not apply to calver", 2)
        if scheme == "headver" and args.pattern is not None:
            fail("--pattern does not apply to headver (use --head)", 2)
        if args.current_among is not None and scheme != "calver":
            fail("--current-among applies to calver only", 2)
        today = parse_today(args.today)
        if scheme == "calver":
            if args.current_among is not None:
                current = calver_max(args.current_among, pattern)
            elif args.current is not None:
                current = args.current
            else:
                current = current_from_config(args.scope)
            print(calver_next(current, pattern, today))
        else:
            current = args.current if args.current is not None \
                else current_from_config(args.scope)
            print(headver_next(current, head, today))
        return

    # semver
    if args.current_among is not None:
        fail("--current-among applies to calver only", 2)
    if args.today:
        fail("--today only applies to calver/headver", 2)
    if args.pattern or args.head:
        fail("--pattern/--head only apply to calver/headver", 2)
    if args.prerelease and args.release:
        fail("--prerelease cannot be combined with --release", 2)
    if args.prerelease and args.qualifier:
        fail("--prerelease cannot be combined with --qualifier", 2)
    if not has_semver_op:
        fail("nothing to do: pass --bump, --release, --qualifier and/or "
             "--prerelease", 2)
    if args.qualifier and not QUALIFIER_RE.match(args.qualifier):
        fail("invalid qualifier: " + args.qualifier, 2)
    if args.prerelease and not QUALIFIER_RE.match(args.prerelease):
        fail("invalid prerelease qualifier: " + args.prerelease, 2)

    current = args.current if args.current else current_from_config(args.scope)
    major, minor, patch, pre = parse_semver(current)
    if args.bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif args.bump == "minor":
        minor, patch = minor + 1, 0
    elif args.bump == "patch":
        patch += 1
    result = "{}.{}.{}".format(major, minor, patch)
    if args.prerelease:
        counter = 1
        if not args.bump and pre:
            pm = re.match(r"^" + re.escape(args.prerelease) + r"\.(\d+)$", pre)
            if pm:
                counter = int(pm.group(1)) + 1
        result += "-{}.{}".format(args.prerelease, counter)
    elif args.qualifier:
        result += "-" + args.qualifier
    print(result)


if __name__ == "__main__":
    main()
