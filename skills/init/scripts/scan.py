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
import xml.etree.ElementTree as ET
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
POM_REVISION_PATTERN = "<revision>([^<]+)</revision>"
VERSION_FILE_PATTERN = "^(\\S+)\\s*$"
OPENAPI_YAML_PATTERN = "^[ \\t]+version:\\s*[\"']?([0-9][^\"'\\s#]*)"
VERSIONISH_RE = re.compile(r"^v?\d[\w.+-]*$")
OPENAPI_FILES = ("openapi.json", "openapi.yaml", "openapi.yml",
                 "swagger.json", "swagger.yaml", "swagger.yml")
TAG_PATTERNS = {
    "semver-v": r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "semver": r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "short": r"^v?\d+\.\d+$",
}
DEVELOP_BRANCH_NAMES = ("develop", "development", "dev")


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


def _pom_project_fields(text):
    """Return (project version, revision property) from a POM, matching tags
    by localname so namespaced and plain POMs both parse. (None, None) on
    parse failure or non-project root."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, None

    def local(el):
        return el.tag.rsplit("}", 1)[-1]

    if local(root) != "project":
        return None, None
    version = revision = None
    for child in root:
        name = local(child)
        if name == "version" and (child.text or "").strip():
            version = child.text.strip()
        elif name == "properties":
            for prop in child:
                if local(prop) == "revision" and (prop.text or "").strip():
                    revision = prop.text.strip()
    return version, revision


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
    text = read(repo / "pom.xml")
    if text:
        version, revision = _pom_project_fields(text)
        if revision is not None:
            add("pom.xml", "regex", revision, pattern=POM_REVISION_PATTERN)
        elif version is not None:
            add("pom.xml", "regex", version,
                usable=False, advice="maven-project-version")
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
    text = read(repo / "VERSION")
    if text:
        stripped = text.strip()
        if stripped and "\n" not in stripped and VERSIONISH_RE.match(stripped):
            add("VERSION", "regex", stripped, pattern=VERSION_FILE_PATTERN)
    for name in OPENAPI_FILES:
        text = read(repo / name)
        if not text:
            continue
        if name.endswith(".json"):
            try:
                info = json.loads(text).get("info")
            except (json.JSONDecodeError, AttributeError):
                continue
            v = info.get("version") if isinstance(info, dict) else None
            if isinstance(v, str) and v.strip():
                add(name, "json-path", v.strip(), path="info.version")
                break
        else:
            m = re.search(OPENAPI_YAML_PATTERN, text, re.M)
            if m and VERSIONISH_RE.match(m.group(1)):
                add(name, "regex", m.group(1), pattern=OPENAPI_YAML_PATTERN)
                break
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
    guess = next((n for n in DEVELOP_BRANCH_NAMES if n in names), None)
    return {"current": current, "defaultGuess": default,
            "hasDevelop": guess is not None,
            "developBranchGuess": guess,
            "releaseBranches": sorted(n for n in names if n.startswith("release/")),
            "hotfixBranches": sorted(n for n in names if n.startswith("hotfix/"))}


def _module_hints(repo):
    hints = []
    for name in ("settings.gradle", "settings.gradle.kts"):
        text = read(repo / name)
        if not text:
            continue
        for line in text.splitlines():
            if re.match(r"^\s*include[ (]", line):
                hints += re.findall(r"['\"]:?([A-Za-z0-9._:-]+)['\"]", line)
    return sorted(set(hints))


def _node_packages(repo):
    globs = ["packages/*", "apps/*"]
    text = read(repo / "pnpm-workspace.yaml")
    if text:
        globs += re.findall(r"^\s*-\s*['\"]?([^'\"#\s]+)", text, re.M)
    root_pkg = read(repo / "package.json")
    if root_pkg:
        try:
            root_data = json.loads(root_pkg)
        except json.JSONDecodeError:
            root_data = None
        ws = root_data.get("workspaces") if isinstance(root_data, dict) else None
        if isinstance(ws, list):
            globs += [g for g in ws if isinstance(g, str)]
        elif isinstance(ws, dict) and isinstance(ws.get("packages"), list):
            globs += [g for g in ws["packages"] if isinstance(g, str)]
    seen, packages = set(), []
    # Only trailing "/*" and "/**" globs are supported (both expand to the
    # base dir's immediate children — "**" is NOT treated as recursive);
    # any other value is treated as a literal package directory path.
    for g in globs:
        if g.endswith("/**"):
            base = g[:-3]
        elif g.endswith("/*"):
            base = g[:-2]
        else:
            base = g
        base_dir = repo / base
        if not base_dir.is_dir():
            continue
        if g == base:
            candidates = [base_dir]
        else:
            candidates = sorted(d for d in base_dir.iterdir() if d.is_dir())
        for d in candidates:
            pj = d / "package.json"
            text = read(pj) if pj.is_file() else None
            if not text:
                continue
            rel = d.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            deps = set()
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                block = data.get(key)
                if isinstance(block, dict):
                    deps.update(block)
            packages.append({"path": rel, "name": data.get("name"),
                             "version": data.get("version"),
                             "buildSystem": "node",
                             "_deps": sorted(deps)})
    return packages


def _gradle_packages(repo):
    """Resolve settings.gradle(.kts) include paths (":a:b" -> "a/b") and
    collect each existing module's version (gradle.properties key first,
    then build.gradle(.kts) assignment)."""
    seen, packages = set(), []
    for name in ("settings.gradle", "settings.gradle.kts"):
        text = read(repo / name)
        if not text:
            continue
        for line in text.splitlines():
            if not re.match(r"^\s*include[ (]", line):
                continue
            for mod in re.findall(r"['\"]:?([A-Za-z0-9._:-]+)['\"]", line):
                rel = mod.replace(":", "/")
                if rel in seen:
                    continue
                seen.add(rel)
                d = repo / rel
                if not d.is_dir():
                    continue
                version = None
                props = read(d / "gradle.properties")
                if props:
                    m = re.search(r"^\s*version\s*=\s*(\S+)\s*$", props, re.M)
                    if m:
                        version = m.group(1)
                if version is None:
                    for bname in ("build.gradle.kts", "build.gradle"):
                        btext = read(d / bname)
                        if btext:
                            m = re.search(GRADLE_VERSION_PATTERN, btext, re.M)
                            if m:
                                version = m.group(1)
                                break
                packages.append({"path": rel,
                                 "name": rel.rsplit("/", 1)[-1],
                                 "version": version,
                                 "buildSystem": "gradle"})
    return packages


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
    packages = _node_packages(repo)
    names = {p["name"]: p["path"] for p in packages if p.get("name")}
    internal = []
    for p in packages:
        for dep in p.pop("_deps", []):
            if dep in names and names[dep] != p["path"]:
                internal.append({"fromPath": p["path"], "fromName": p.get("name"),
                                 "toPath": names[dep], "toName": dep})
    node_paths = {p["path"] for p in packages}
    packages += [g for g in _gradle_packages(repo)
                 if g["path"] not in node_paths]
    return {"suspected": bool(signals) or len(packages) > 1,
            "signals": signals, "packages": packages,
            "internalDependencies": internal,
            "gradleModuleHints": _module_hints(repo)}


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
