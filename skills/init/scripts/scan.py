#!/usr/bin/env python3
"""scan.py — read-only project scanner for superrelease init.

Prints a JSON report of build systems, version-string candidates, tag patterns,
Conventional Commits usage, merge-policy evidence, branches, monorepo signals,
changelog artifacts and CI tag-trigger *candidates* (heuristic — the caller must
read the candidate workflow files to confirm).
Exit codes: 0 success (missing git degrades gracefully) / 2 usage error.
"""
import sys

if sys.version_info < (3, 9):
    sys.stderr.write("error: superrelease scripts require Python 3.9+\n")
    sys.exit(2)

import argparse
import json
import re
import subprocess
from pathlib import Path

CC_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]*\))?!?:")
SQUASH_RE = re.compile(r"\(#\d+\)$")
GRADLE_VERSION_PATTERN = "^version\\s*=?\\s*['\\\"]([^'\\\"]+)['\\\"]"
PYPROJECT_VERSION_PATTERN = "^version\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]"
CARGO_VERSION_PATTERN = "^version\\s*=\\s*\\\"([^\\\"]+)\\\""
DOCKER_VERSION_PATTERN = (
    "LABEL\\s+(?:org\\.opencontainers\\.image\\.)?version=\\\"?([^\\\"\\s]+)\\\"?")
CHART_VERSION_PATTERN = "^version:\\s*(\\S+)"
BADGE_VERSION_PATTERN = "badge/version-([0-9][A-Za-z0-9.%-]*)-"
TAG_PATTERNS = {
    "semver-v": r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "semver": r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "short": r"^v?\d+\.\d+$",
}


def git(repo, *args):
    try:
        proc = subprocess.run(["git", "-C", str(repo)] + list(args),
                              capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def scan_build_systems(repo):
    found = []
    gradle_files = ("build.gradle", "build.gradle.kts",
                    "settings.gradle", "settings.gradle.kts")
    if any((repo / n).is_file() for n in gradle_files):
        found.append("gradle")
    if (repo / "pom.xml").is_file():
        found.append("maven")
    if (repo / "package.json").is_file():
        pm = "npm"
        if (repo / "pnpm-lock.yaml").is_file():
            pm = "pnpm"
        elif (repo / "yarn.lock").is_file():
            pm = "yarn"
        found.append("node:" + pm)
    if (repo / "pyproject.toml").is_file():
        found.append("python")
    if (repo / "Cargo.toml").is_file():
        found.append("rust")
    return found


def scan_version_candidates(repo):
    out = []

    def add(file, loc_type, value, **extra):
        entry = {"file": file, "type": loc_type, "value": value}
        entry.update(extra)
        out.append(entry)

    text = read(repo / "gradle.properties")
    if text:
        m = re.search(r"^\s*version\s*=\s*(\S+)\s*$", text, re.M)
        if m:
            add("gradle.properties", "properties-key", m.group(1), key="version")
    for name in ("build.gradle.kts", "build.gradle"):
        text = read(repo / name)
        if text:
            m = re.search(GRADLE_VERSION_PATTERN, text, re.M)
            if m:
                add(name, "regex", m.group(1), pattern=GRADLE_VERSION_PATTERN)
    text = read(repo / "package.json")
    if text:
        try:
            v = json.loads(text).get("version")
            if isinstance(v, str):
                add("package.json", "json-path", v, path="version")
        except json.JSONDecodeError:
            pass
    text = read(repo / "pyproject.toml")
    if text:
        m = re.search(PYPROJECT_VERSION_PATTERN, text, re.M)
        if m:
            add("pyproject.toml", "regex", m.group(1), pattern=PYPROJECT_VERSION_PATTERN)
    text = read(repo / "Cargo.toml")
    if text:
        m = re.search(CARGO_VERSION_PATTERN, text, re.M)
        if m:
            add("Cargo.toml", "regex", m.group(1), pattern=CARGO_VERSION_PATTERN)
    text = read(repo / "Dockerfile")
    if text:
        m = re.search(DOCKER_VERSION_PATTERN, text)
        if m:
            add("Dockerfile", "regex", m.group(1), pattern=DOCKER_VERSION_PATTERN)
    text = read(repo / "Chart.yaml")
    if text:
        m = re.search(CHART_VERSION_PATTERN, text, re.M)
        if m:
            add("Chart.yaml", "regex", m.group(1), pattern=CHART_VERSION_PATTERN)
    text = read(repo / "README.md")
    if text:
        m = re.search(BADGE_VERSION_PATTERN, text)
        if m:
            add("README.md", "regex", m.group(1), pattern=BADGE_VERSION_PATTERN)
    return out


def scan_tags(repo):
    raw = git(repo, "tag", "--list", "--sort=-v:refname")
    if raw is None:
        return {"available": False}
    tags = [t for t in raw.splitlines() if t.strip()]
    by_pattern = {name: [t for t in tags if re.match(p, t)]
                  for name, p in TAG_PATTERNS.items()}
    other = [t for t in tags if not any(re.match(p, t) for p in TAG_PATTERNS.values())]
    latest = tags[0] if tags else None
    annotated = signed = None
    if latest:
        obj_type = (git(repo, "cat-file", "-t", latest) or "").strip()
        annotated = obj_type == "tag"
        if annotated:
            body = git(repo, "cat-file", "tag", latest) or ""
            signed = "-----BEGIN PGP SIGNATURE-----" in body
    groups = [n for n, ts in by_pattern.items() if ts] + (["other"] if other else [])
    return {"available": True, "count": len(tags),
            "byPattern": {n: len(ts) for n, ts in by_pattern.items()},
            "otherCount": len(other), "mixed": len(groups) > 1, "latest": latest,
            "latestAnnotated": annotated, "latestSigned": signed}


def scan_commits(repo):
    raw = git(repo, "log", "-n", "100", "--pretty=%s")
    if raw is None:
        return {"available": False}
    subjects = [s for s in raw.splitlines() if s]
    total = len(subjects)
    cc = sum(1 for s in subjects if CC_RE.match(s))
    squash = sum(1 for s in subjects if SQUASH_RE.search(s))
    merges = sum(1 for s in subjects if s.startswith("Merge pull request"))
    if squash > merges and squash > 0:
        guess = "squash"
    elif merges > 0:
        guess = "merge"
    else:
        guess = "unknown"
    return {"available": True, "sampled": total,
            "conventionalRate": round(cc / total, 2) if total else 0.0,
            "squashSuffixCount": squash, "mergeCommitCount": merges,
            "mergePolicyGuess": guess}


def scan_branches(repo):
    current = (git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "").strip() or None
    head = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    default = head.strip().rsplit("/", 1)[-1] if head else current
    local = [b.strip().lstrip("* ").strip()
             for b in (git(repo, "branch", "--list") or "").splitlines() if b.strip()]
    remote = [b.strip() for b in (git(repo, "branch", "-r") or "").splitlines()
              if b.strip() and "->" not in b]
    names = set(local) | {r.split("/", 1)[-1] for r in remote}
    return {"current": current, "defaultGuess": default,
            "hasDevelop": "develop" in names,
            "releaseBranches": sorted(n for n in names if n.startswith("release/")),
            "hotfixBranches": sorted(n for n in names if n.startswith("hotfix/"))}


def scan_monorepo(repo):
    signals = []
    for name in ("settings.gradle", "settings.gradle.kts"):
        text = read(repo / name)
        if text and re.search(r"^\s*include[ (]", text, re.M):
            signals.append(name + ": multi-module include")
    if (repo / "pnpm-workspace.yaml").is_file():
        signals.append("pnpm-workspace.yaml")
    for d in ("packages", "apps"):
        base = repo / d
        if base.is_dir() and any((c / "package.json").is_file()
                                 for c in base.iterdir() if c.is_dir()):
            signals.append(d + "/: package.json children")
    return {"suspected": bool(signals), "signals": signals}


def scan_changelog(repo):
    return {"changelogMd": (repo / "CHANGELOG.md").is_file(),
            "releasesDir": (repo / "docs" / "releases").is_dir(),
            "fragmentsDir": (repo / "changelog.d").is_dir()}


def scan_ci(repo):
    candidates = []
    workflows = repo / ".github" / "workflows"
    if workflows.is_dir():
        for f in sorted(workflows.iterdir()):
            if f.suffix in (".yml", ".yaml"):
                text = read(f) or ""
                if re.search(r"^\s*tags:", text, re.M) and re.search(r"^\s*push:", text, re.M):
                    candidates.append(f.relative_to(repo).as_posix())
    return {"tagTriggerCandidates": candidates,
            "note": "heuristic only — read each candidate file to confirm "
                    "before treating tag push as a deploy trigger"}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="scan.py",
        description="Read-only project scan for superrelease init (JSON report).")
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--json", action="store_true",
                        help="accepted for symmetry; output is always JSON")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write("error: not a directory: " + str(repo) + "\n")
        sys.exit(2)
    report = {
        "repo": str(repo),
        "git": git(repo, "rev-parse", "--is-inside-work-tree") is not None,
        "buildSystems": scan_build_systems(repo),
        "versionCandidates": scan_version_candidates(repo),
        "tags": scan_tags(repo),
        "commits": scan_commits(repo),
        "branches": scan_branches(repo),
        "monorepo": scan_monorepo(repo),
        "changelog": scan_changelog(repo),
        "ci": scan_ci(repo),
        "python": ".".join(str(v) for v in sys.version_info[:3]),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
