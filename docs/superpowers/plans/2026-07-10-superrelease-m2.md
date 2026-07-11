# superrelease M2 (모노레포) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superrelease에 모노레포 지원(M2)을 추가한다 — fixed/independent 전략, scope별 변경 감지(`changed-packages.py`), 태그 네임스페이스(`{scope}@{version}`), 내부 의존성 전파(`dependents`), 패키지 노트 템플릿, init 질문 확장.

**Architecture:** M1 인프라를 그대로 확장한다. `version.py`/`next-version.py`는 이미 멀티 스코프를 지원하므로 **수정하지 않고 회귀 테스트로 고정**한다. 모노레포(independent) 전용 release/release-notes 스킬은 **별도 asset 파일**로 작성하고 manifest의 동일-dest `when` 스위칭(기존 메커니즘)으로 선택한다 — 기존 M1 asset은 한 글자도 수정하지 않으므로 M1 골든 3종은 바이트 불변이다. fixed 전략은 "전 패키지 버전 파일을 가진 단일 scope"로 모델링해 릴리스 흐름이 M1과 동일하다(independent만 새 흐름).

**Tech Stack:** Python 3.9+ 표준 라이브러리(스크립트·unittest), 동결 템플릿 dialect(엔진 수정 금지), git·gh CLI.

**스펙:** [docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md](../specs/2026-07-09-superrelease-plugin-design.md) §12 M2. **베이스: main `6824c62`** (M1 + M1.1 병합 완료, 66 테스트). 실행 컨트롤러는 main에서 `feat/superrelease-m2` 브랜치를 만들어 진행한다.

## Global Constraints

- Python 3.9+ stdlib만 — 외부 패키지·jq 금지. 새 스크립트도 첫머리 버전 가드(미달 시 exit 2), argparse `--help`(영어), 코드·메시지 영어.
- exit code 규약: 0 성공 / 1 검증 실패 / 2 사용법·설정·환경 오류. `changed-packages.py`는 검증 개념이 없어 **0/2만** 사용(문서화).
- **render.py 엔진부(Part 1) 수정 금지** — 동결 dialect. 파이프라인부(`validate_config`)만 수정 허용.
- **`version.py`·`next-version.py` 수정 금지** — 골든에 verbatim 복사되는 파일이므로, 수정하면 골든이 깨진다. M2는 회귀 테스트만 추가한다.
- **M1 골든 3종(gradle-app/npm-app/jvm-library)은 전 과정에서 바이트 불변** — `tests/update_golden.py`는 Task 5에서 pnpm-monorepo 추가 시 한 번만 실행하며, 실행 후 `git status --porcelain tests/golden`에 기존 3종 트리가 나타나면 그 변경은 버그다(골든을 고치지 말고 원인을 고쳐라).
- generated 마커·kebab-case·`${CLAUDE_PLUGIN_ROOT}`·생성물의 플러그인 참조 금지·생성 SKILL.md ≤150줄(테스트는 ≤149 pre-marker)·init SKILL.md ≤500줄 — M1 규약 전부 승계.
- 테스트 실행: `python3 -m unittest discover -s tests -v` — 각 태스크 마지막에 전체 통과 확인 후 커밋. `claude plugin validate . --strict`는 SKILL/manifest를 만지는 태스크에서 확인.
- 커밋: Conventional Commits(제목 영어 타입 + 한국어 허용), 말미 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 스펙 대비 계획 단계 확정(§9 재량 범위):
  - config에 `repo.monorepoStrategy: null | "fixed" | "independent"` 추가 — 번들 1의 전략 답을 manifest `when`과 생성 스킬이 소비하는 통로 (M1의 `tagTriggersDeployment`와 같은 성격의 스키마 추가).
  - **fixed = 단일 scope 모델링**: 전 패키지의 버전 파일을 root scope `versionLocations`에 모은다. 릴리스 흐름·생성물은 M1과 동일(모노레포 변형 스킬은 independent 전용).
  - `changed-packages.py` CLI는 스펙 6.5 스케치의 `<ref>` 위치 인자 대신 `--ref` 옵션 — independent에선 scope별 anchor(각자의 마지막 태그)가 달라 **자동 해석이 기본**이고 `--ref`는 전 scope 공통 override다.
  - M2에서 notes 설정(언어·독자·어조·목적지)은 전 scope 공통으로 1회 질문(스코프별 개별 설정은 후속).
  - 비범위: 내부 의존성 버전 범위 재작성(pnpm `workspace:` 프로토콜은 publish 시 해석 — publish는 CI 몫, 스펙 non-goal), npm workspaces 루트 lockfile의 per-package 항목 동기화(완료 기준은 pnpm이며 pnpm-lock.yaml은 루트 버전을 담지 않음), 이중 체계·release-train(M3).

## 파일 구조 (M2 전체)

```
수정  tests/helpers.py                                  # Task 1: monorepoStrategy 기본값, 복사 목록, monorepo_config()
수정  tests/test_version.py                             # Task 1: MultiScopeTest (회귀 고정)
수정  tests/test_next_version.py                        # Task 1: 멀티 스코프 config 모드
생성  skills/init/assets/scripts/changed-packages.py    # Task 2
생성  tests/test_changed_packages.py                    # Task 2
수정  skills/init/assets/manifest.json                  # Task 2(+1항목) / Task 4(when 스위칭+2스킬+1템플릿 → 총 11항목)
수정  skills/init/scripts/render.py                     # Task 3: validate_config만
수정  tests/test_render_pipeline.py                     # Task 3: 검증·스위칭 테스트
생성  skills/init/assets/skills/release-monorepo/SKILL.md        # Task 4
생성  skills/init/assets/skills/release-notes-monorepo/SKILL.md  # Task 4
생성  skills/init/assets/templates/notes-package.md              # Task 4
수정  tests/test_assets.py                              # Task 4: mono_ctx + 모노레포 스모크/통합
수정  tests/golden_configs.py                           # Task 5: pnpm_monorepo
생성  tests/golden/pnpm-monorepo/expected/**            # Task 5: update_golden 산출(검수 후 커밋)
수정  skills/init/scripts/scan.py                       # Task 6: scan_monorepo 확장
수정  tests/test_scan.py                                # Task 6
수정  skills/init/SKILL.md                              # Task 7: 번들 1·2·7, config 예시, 지원 범위
수정  skills/init/references/monorepo.md                # Task 7: "M1 범위" → 지원 현황
수정  README.md, README_KO.md                           # Task 7: 로드맵·생성물 표·스크립트 예시 (1:1 유지)
```

책임 분리: 변경 감지+anchor 해석은 `changed-packages.py`(결정론), scope 선택·전파 오케스트레이션은 모노레포 release 스킬(판단), 전략·scope 목록·dependents는 config(SSOT). 모노레포 변형 스킬은 **scope별 값을 인라인하지 않고**(scopes[0]만 렌더 컨텍스트에 있으므로) 런타임에 config의 해당 scope 항목을 읽도록 지시한다 — repo 수준 값(`defaultBranch`, `releaseCommitFormat`, `mergePolicy` 분기 등)만 인라인.

---

### Task 1: helpers 확장 + 멀티 스코프 회귀 고정

**Files:**
- Modify: `tests/helpers.py`
- Test: `tests/test_version.py`, `tests/test_next_version.py` (추가)

**Interfaces:**
- Produces: `helpers.monorepo_config(strategy="independent") -> dict` — pnpm 스타일 2-scope config(scope `a`: path `packages/a`, tag.format `a@{version}`, dependents `["b"]` / scope `b`: path `packages/b`, tag.format `b@{version}`, dependents `[]`; 둘 다 json-path package.json, preRelease none, postRelease none, notes.template `notes-package.md`; repo.kind `monorepo`, repo.monorepoStrategy=strategy, releaseCommitFormat `chore(release): {scope}@{version}`). **이후 모든 태스크의 테스트·골든이 이 형태에 의존한다.**
- Produces: `scope_config()`의 repo에 `"monorepoStrategy": None` 기본 필드 추가. `make_repo`가 `changed-packages.py`도 복사(파일 존재 시 — Task 2 전에는 자동 skip).
- **주의:** 이 태스크의 테스트는 프로덕션 코드 무변경으로 **즉시 GREEN이어야 정상**이다(이미 구현된 멀티 스코프 동작을 회귀 고정). RED가 나오면 멀티 스코프 버그 발견이므로 STOP하고 BLOCKED로 보고하라 — 임의로 프로덕션을 고치지 말 것.

- [ ] **Step 1: tests/helpers.py 수정**

(1) `scope_config`의 repo dict에서 아래를:

```python
        "releaseCommitFormat": "chore(release): {version}",
        "tagTriggersDeployment": False,
```

다음으로 교체:

```python
        "releaseCommitFormat": "chore(release): {version}",
        "tagTriggersDeployment": False,
        "monorepoStrategy": None,
```

(2) `make_repo`의 복사 튜플을:

```python
    for name in ("version.py", "next-version.py"):
```

다음으로 교체:

```python
    for name in ("version.py", "next-version.py", "changed-packages.py"):
```

(3) 파일 끝에 추가:

```python
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
```

- [ ] **Step 2: tests/test_version.py에 MultiScopeTest 추가**

상단 import를 `from helpers import make_repo, monorepo_config, run_script, scope_config, write` 로 확장하고, 파일 끝(`if __name__` 앞)에 추가:

```python
class MultiScopeTest(VersionTestBase):
    A = '{\n  "name": "a",\n  "version": "1.0.0"\n}\n'
    B = '{\n  "name": "b",\n  "version": "2.0.0"\n}\n'

    def mono_repo(self):
        return make_repo(self.tmp.name, monorepo_config(), {
            "packages/a/package.json": self.A,
            "packages/b/package.json": self.B})

    def test_get_per_scope(self):
        repo = self.mono_repo()
        self.assertEqual(run_script(vp(repo), "get", "--scope", "a").stdout.strip(),
                         "1.0.0")
        self.assertEqual(run_script(vp(repo), "get", "--scope", "b").stdout.strip(),
                         "2.0.0")

    def test_get_without_scope_exits_2(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--scope", r.stderr)

    def test_set_touches_only_target_scope(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "set", "1.1.0", "--scope", "a")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = json.loads((Path(repo) / "packages/a/package.json").read_text(encoding="utf-8"))
        b = json.loads((Path(repo) / "packages/b/package.json").read_text(encoding="utf-8"))
        self.assertEqual(a["version"], "1.1.0")
        self.assertEqual(b["version"], "2.0.0")

    def test_verify_reports_each_scope(self):
        repo = self.mono_repo()
        r = run_script(vp(repo), "verify")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("scope a", r.stdout)
        self.assertIn("scope b", r.stdout)
```

- [ ] **Step 3: tests/test_next_version.py에 멀티 스코프 config 모드 테스트 추가**

상단 import를 `from helpers import ASSET_SCRIPTS, make_repo, monorepo_config, run_script, scope_config` 로 확장하고 파일 끝에 추가:

```python
class MultiScopeConfigModeTest(unittest.TestCase):
    def test_scope_selects_right_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, monorepo_config(), {
                "packages/a/package.json": '{\n  "name": "a",\n  "version": "1.0.0"\n}\n',
                "packages/b/package.json": '{\n  "name": "b",\n  "version": "2.0.0"\n}\n'})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--scope", "b", "--bump", "patch")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "2.0.1")
```

- [ ] **Step 4: 즉시 GREEN 확인 (회귀 고정 성격)**

Run: `python3 -m unittest discover -s tests -v`
Expected: 전부 PASS (기존 66 + 신규 5 = 71). **신규 테스트가 FAIL하면 STOP — 프로덕션을 고치지 말고 BLOCKED 보고.** 골든 3종도 그대로 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/helpers.py tests/test_version.py tests/test_next_version.py
git commit -m "test: 멀티 스코프 회귀 고정 + monorepo_config 헬퍼

version.py/next-version.py는 무수정 — 이미 지원하는 멀티 스코프 동작을 테스트로 고정.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: changed-packages.py — scope별 anchor 해석·경로 기반 변경 감지

**Files:**
- Create: `skills/init/assets/scripts/changed-packages.py`
- Modify: `skills/init/assets/manifest.json` (1항목 추가)
- Test: `tests/test_changed_packages.py`

**Interfaces:**
- Consumes: `helpers.monorepo_config`, `make_git_repo`, `make_repo` (Task 1)
- Produces (CLI — 모노레포 release 스킬·init이 의존):
  - `changed-packages.py [--scope NAME] [--ref REF] [--json]`
  - scope별 anchor 자동 해석: `tag.enabled`면 `tag.format`의 `{version}`→`*` glob으로 최신 태그(`git tag --list <glob> --sort=-v:refname` 첫 줄), 태그 미사용이면 `anchor.value`, 없으면 None(첫 릴리스). `--ref`는 전 scope 공통 override.
  - 변경 파일: anchor 있으면 `git diff --name-only <anchor>..HEAD`, 없으면 `git ls-files -- <path>`. scope.path 접두사(`.`→전체)로 필터.
  - `--json` 출력: `{"scopes": [{"name","path","anchor","anchorType"("tag"|"ref"|"none"),"hasChanges","changedCount","changed":[...]}]}`. 기본은 사람용 표(변경 scope에 `*` 마크).
  - exit: 0 성공 / 2 사용법·설정·git 오류(알 수 없는 scope, git 실패). config는 `Path(__file__).resolve().parent.parent / "config.json"`.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_changed_packages.py**

```python
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import make_git_repo, make_repo, monorepo_config, run_script, write

PKG_A = '{\n  "name": "a",\n  "version": "0.1.0"\n}\n'
PKG_B = '{\n  "name": "b",\n  "version": "0.1.0"\n}\n'


def g(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@test",
                    "-c", "user.name=tester", "-c", "commit.gpgsign=false",
                    "-c", "tag.gpgsign=false", *args],
                   check=True, capture_output=True, text=True)


class ChangedPackagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_git_repo(self.tmp.name, files={
            "pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
            "packages/a/package.json": PKG_A,
            "packages/b/package.json": PKG_B,
        }, commits=["feat: init (#1)"])
        make_repo(self.repo, monorepo_config(), {})
        self.cp = self.repo / ".superrelease" / "scripts" / "changed-packages.py"

    def run_cp(self, *args):
        return run_script(self.cp, *args)

    def scopes_by_name(self, stdout):
        return {s["name"]: s for s in json.loads(stdout)["scopes"]}

    def test_first_release_no_anchor_everything_changed(self):
        r = self.run_cp("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        by = self.scopes_by_name(r.stdout)
        self.assertIsNone(by["a"]["anchor"])
        self.assertEqual(by["a"]["anchorType"], "none")
        self.assertTrue(by["a"]["hasChanges"])
        self.assertTrue(by["b"]["hasChanges"])

    def test_tag_anchor_and_path_filter(self):
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "a@0.1.0")
        g(self.repo, "tag", "-a", "b@0.1.0", "-m", "b@0.1.0")
        write(self.repo / "packages" / "b" / "index.js", "console.log(1)\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: b change (#2)")
        by = self.scopes_by_name(self.run_cp("--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@0.1.0")
        self.assertEqual(by["a"]["anchorType"], "tag")
        self.assertFalse(by["a"]["hasChanges"])
        self.assertEqual(by["b"]["anchor"], "b@0.1.0")
        self.assertTrue(by["b"]["hasChanges"])
        self.assertIn("packages/b/index.js", by["b"]["changed"])

    def test_latest_tag_wins(self):
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "x")
        write(self.repo / "packages" / "a" / "index.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: a (#2)")
        g(self.repo, "tag", "-a", "a@0.2.0", "-m", "x")
        by = self.scopes_by_name(self.run_cp("--scope", "a", "--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@0.2.0")
        self.assertFalse(by["a"]["hasChanges"])

    def test_scope_filter_and_unknown_scope(self):
        r = self.run_cp("--scope", "b", "--json")
        self.assertEqual([s["name"] for s in json.loads(r.stdout)["scopes"]], ["b"])
        self.assertEqual(self.run_cp("--scope", "nope").returncode, 2)

    def test_ref_override(self):
        write(self.repo / "packages" / "b" / "index.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: b (#2)")
        by = self.scopes_by_name(self.run_cp("--ref", "HEAD~1", "--json").stdout)
        self.assertEqual(by["a"]["anchorType"], "ref")
        self.assertFalse(by["a"]["hasChanges"])
        self.assertTrue(by["b"]["hasChanges"])

    def test_human_output(self):
        r = self.run_cp()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("packages/a", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: test_changed_packages 전부 FAIL(스크립트 부재 — make_repo의 존재 가드로 복사가 skip되어 실행 실패). 기존 71개 PASS 유지.

- [ ] **Step 3: skills/init/assets/scripts/changed-packages.py 구현 (전체)**

```python
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
```

- [ ] **Step 4: manifest.json에 항목 추가**

`next-version.py` 항목(닫는 `}`) 뒤, `templates/notes-single.md` 항목 앞에 추가:

```json
    {
      "src": "scripts/changed-packages.py",
      "dest": ".superrelease/scripts/changed-packages.py",
      "render": false,
      "executable": true,
      "when": "repo.kind == \"monorepo\""
    },
```

- [ ] **Step 5: 통과 확인 + 스모크 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (FullRenderTest는 app config라 skipped — 여전히 7파일 ✓, 골든 3종 불변 ✓).
Run: `python3 skills/init/assets/scripts/changed-packages.py --help` → usage, exit 0.

```bash
git add skills/init/assets/scripts/changed-packages.py skills/init/assets/manifest.json tests/test_changed_packages.py
git commit -m "feat: changed-packages.py — scope별 anchor 해석·경로 기반 변경 감지

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: render.py 모노레포 config 검증 + 동일-dest when 스위칭 테스트

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`만 — 엔진부 수정 금지)
- Test: `tests/test_render_pipeline.py` (2개 테스트 클래스 추가)

**Interfaces:**
- Consumes: Task 1의 `monorepo_config`
- Produces: `validate_config` 추가 규칙 — `repo.kind == "monorepo"`인데 `repo.monorepoStrategy`가 `"fixed"`/`"independent"`가 아니면 문제(exit 1 경로), `"independent"`인데 scope가 2개 미만이면 문제. 그리고 "같은 dest를 가진 두 manifest 항목을 배타적 `when`으로 스위칭"하는 패턴이 동작함을 고정하는 테스트(Task 4의 manifest가 의존하는 성질).

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_render_pipeline.py에 추가**

상단 import 줄을 다음으로 교체:

```python
from helpers import (PLUGIN_SCRIPTS, make_plugin_tree, monorepo_config, run_script,
                     scope_config, write)
```

파일 끝(`if __name__` 앞)에 추가:

```python
SWITCH_MANIFEST = {
    "entries": [
        {"src": "skills/single.md", "dest": ".claude/skills/release/SKILL.md",
         "render": True, "when": 'repo.monorepoStrategy != "independent"'},
        {"src": "skills/mono.md", "dest": ".claude/skills/release/SKILL.md",
         "render": True, "when": 'repo.monorepoStrategy == "independent"'},
    ]
}
SWITCH_FILES = {
    "skills/single.md": "SINGLE {{project.name}}\n",
    "skills/mono.md": "MONO {{project.name}}\n",
}


class SameDestSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.assets = make_plugin_tree(base / "plugin", SWITCH_MANIFEST, SWITCH_FILES)
        self.repo = base / "target-repo"
        self.repo.mkdir()
        self.config_path = self.repo / ".superrelease" / "config.json"

    def render_with(self, cfg):
        write(self.config_path, json.dumps(cfg, ensure_ascii=False, indent=2))
        return run_script(PLUGIN_SCRIPTS / "render.py", "--config", self.config_path,
                          "--assets", self.assets, "--repo", self.repo)

    def dest_text(self):
        return (self.repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")

    def test_single_variant_for_non_monorepo(self):
        r = self.render_with(scope_config(
            [{"file": "x", "type": "regex", "pattern": "v(1)"}]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SINGLE", self.dest_text())
        self.assertIn("skipped", r.stdout)

    def test_mono_variant_for_independent(self):
        r = self.render_with(monorepo_config())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("MONO", self.dest_text())
        self.assertNotIn("SINGLE", self.dest_text())


class MonorepoValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.assets = make_plugin_tree(base / "plugin", SWITCH_MANIFEST, SWITCH_FILES)
        self.repo = base / "target-repo"
        self.repo.mkdir()
        self.config_path = self.repo / ".superrelease" / "config.json"

    def render_with(self, cfg):
        write(self.config_path, json.dumps(cfg, ensure_ascii=False, indent=2))
        return run_script(PLUGIN_SCRIPTS / "render.py", "--config", self.config_path,
                          "--assets", self.assets, "--repo", self.repo)

    def test_monorepo_without_strategy_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["kind"] = "monorepo"  # monorepoStrategy는 None 그대로
        r = self.render_with(cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("monorepoStrategy", r.stderr)

    def test_independent_with_single_scope_exits_1(self):
        cfg = monorepo_config()
        cfg["scopes"] = cfg["scopes"][:1]
        r = self.render_with(cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("at least two scopes", r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: `MonorepoValidateTest` 2건 FAIL(검증 규칙 부재 → exit 0으로 렌더 성공해버림). `SameDestSwitchTest`는 기존 파이프라인 성질이라 **즉시 PASS일 수 있다** — PASS면 그대로 두고(고정 목적), FAIL이면 파이프라인 버그이므로 STOP·보고. 기존 테스트 PASS 유지.

- [ ] **Step 3: validate_config에 규칙 추가**

`skills/init/scripts/render.py`의 `validate_config`에서 `return problems` 직전(scopes 검사 for 루프 블록 뒤)에 추가:

```python
    strategy = repo.get("monorepoStrategy")
    if repo.get("kind") == "monorepo" and strategy not in ("fixed", "independent"):
        problems.append('repo.monorepoStrategy must be "fixed" or "independent" '
                        'when repo.kind is "monorepo"')
    if strategy == "independent" and scopes and len(scopes) < 2:
        problems.append("independent strategy requires at least two scopes")
```

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS. 골든 3종 불변(`test_golden` PASS — validate 추가는 렌더 출력에 무영향, M1 config는 kind app/library라 새 규칙 미적용).

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: 모노레포 config 검증 + 동일-dest when 스위칭 고정 테스트

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 모노레포 변형 스킬·notes-package 템플릿 + manifest when 스위칭

**Files:**
- Create: `skills/init/assets/skills/release-monorepo/SKILL.md`
- Create: `skills/init/assets/skills/release-notes-monorepo/SKILL.md`
- Create: `skills/init/assets/templates/notes-package.md`
- Modify: `skills/init/assets/manifest.json` (전체 교체 — 최종 11항목)
- Test: `tests/test_assets.py` (mono_ctx + MonorepoAssetsTest + FullRenderMonorepoTest)

**Interfaces:**
- Consumes: Task 2 `changed-packages.py` CLI, Task 3 검증·스위칭 성질, 동결 dialect
- Produces: independent 모노레포에서 `.claude/skills/release/SKILL.md`·`.claude/skills/release-notes/SKILL.md` dest에 렌더되는 **scope-generic 변형** 2종(M1 단일 변형과 같은 dest, 배타 `when`). scope별 값은 인라인하지 않고 런타임에 config를 읽도록 지시 — repo 수준 값만 인라인. **기존 단일 변형 asset 3종(release, release-notes, notes-single)은 한 글자도 수정하지 않는다**(골든 불변 보장의 핵심).
- 설계 노트(리뷰어 참고): 두 변형 SKILL.md는 공통 규칙·preflight 일부 문구를 공유한다. in-file 조건 분기 대신 별도 파일을 택한 이유 — (1) M1 asset 무수정으로 골든 바이트 불변을 구조적으로 보장, (2) 블록 태그 삽입 시 공백/개행 회귀 위험 제거, (3) 두 흐름은 실제로 절차가 다르다(scope 선택·전파·scope별 태그). 문구 중복은 의도된 트레이드오프다.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py에 추가**

상단 import 줄을 다음으로 교체:

```python
from helpers import (ASSETS, PLUGIN_SCRIPTS, load_module, monorepo_config,
                     run_script, scope_config, write)
```

`base_ctx` 함수 아래에 추가:

```python
def mono_ctx(**overrides):
    cfg = monorepo_config()
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-mono"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx
```

파일 끝(`if __name__` 앞)에 추가:

```python
class MonorepoAssetsTest(unittest.TestCase):
    def render_asset(self, rel, ctx=None):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        return render.render_template(text, ctx or mono_ctx())

    def test_release_monorepo_renders_clean(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-mono", out)
        self.assertIn("changed-packages.py", out)
        self.assertIn("--scope", out)
        self.assertIn("dependents", out)
        self.assertIn("네임스페이스", out)
        self.assertTrue(out.startswith("---\n"))
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_no_scope_inlining(self):
        # scope별 값(태그 포맷, 수식어 등)은 인라인 금지 — a@ 같은 특정 scope 값이 없어야 한다
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertNotIn("a@{version}", out)
        self.assertIn("chore(release): {scope}@{version}", out)  # repo 수준 값은 인라인

    def test_release_monorepo_omits_github_when_disabled(self):
        ctx = mono_ctx(github={"release": False, "generateNotes": False,
                               "releaseYml": False})
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("gh release create", out)
        self.assertNotIn("gh auth status", out)

    def test_release_notes_monorepo_renders_clean(self):
        out = self.render_asset("skills/release-notes-monorepo/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("changed-packages.py", out)
        self.assertIn("notes-package.md", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_notes_package_language_blocks(self):
        ko = self.render_asset("templates/notes-package.md")
        self.assertIn("하이라이트", ko)
        self.assertNotIn("Highlights", ko)
        ctx = mono_ctx()
        ctx["scope"]["notes"]["language"] = "en"
        en = self.render_asset("templates/notes-package.md", ctx)
        self.assertIn("Highlights", en)
        self.assertNotIn("하이라이트", en)
        ctx["scope"]["notes"]["language"] = "both"
        both = self.render_asset("templates/notes-package.md", ctx)
        self.assertIn("하이라이트", both)
        self.assertIn("Highlights", both)


class FullRenderMonorepoTest(unittest.TestCase):
    def test_monorepo_render_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-mono"
            repo.mkdir()
            write(repo / ".superrelease" / "config.json",
                  json.dumps(monorepo_config(), ensure_ascii=False, indent=2))
            write(repo / "packages" / "a" / "package.json",
                  '{\n  "name": "a",\n  "version": "0.1.0"\n}\n')
            write(repo / "packages" / "b" / "package.json",
                  '{\n  "name": "b",\n  "version": "0.1.0"\n}\n')
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("모노레포", skill)
            self.assertIn("changed-packages.py", skill)
            notes_skill = (repo / ".claude/skills/release-notes/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("changed-packages.py", notes_skill)
            self.assertTrue((repo / ".superrelease/scripts/changed-packages.py").is_file())
            self.assertTrue((repo / ".superrelease/templates/notes-package.md").is_file())
            self.assertFalse((repo / ".superrelease/templates/notes-single.md").exists())
            verify = run_script(repo / ".superrelease" / "scripts" / "version.py", "verify")
            self.assertEqual(verify.returncode, 0, verify.stderr)


```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: MonorepoAssetsTest는 FileNotFoundError로 ERROR(asset 부재), FullRenderMonorepoTest는 단일 변형이 렌더돼 "모노레포" 미포함으로 FAIL. 기존 PASS 유지.

- [ ] **Step 3: skills/init/assets/skills/release-monorepo/SKILL.md 작성 (전체)**

````markdown
---
name: release
description: {{project.name}} 모노레포의 패키지 릴리스를 수행한다. 사용자가 릴리스해줘, 특정 패키지 릴리스, 버전 올려, bump, 태그 따줘, release, 어떤 패키지 바뀌었어, 릴리스 준비됐는지 봐줘 등 버전 결정·태그{{#if github.release}}·GitHub Release{{/if}}·릴리스 노트와 관련된 요청을 하면 반드시 이 스킬을 사용한다.
---

# release — {{project.name}} 모노레포 릴리스 오케스트레이터 (independent)

이 레포는 패키지(scope)별로 버전·태그를 독립 관리한다. 정책의 SSOT는 `.superrelease/config.json`이며, **scope별 값(버전 체계, 태그 포맷, 수식어, post-release, 노트 설정, dependents)은 반드시 config의 해당 scope 항목에서 읽어라** — 이 문서에 인라인된 scope 값은 없다.

공통 규칙:

- 버전 파싱·산술·파일 수정·변경 감지는 스크립트로만: `python3 .superrelease/scripts/<script>` (Windows는 `py -3`).
- 부작용 있는 모든 동작(파일 수정, 커밋, push, 태그, Release 생성)은 **dry-run 프리뷰 → 사용자 확인 → 실행**. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
{{#if github.release}}- GitHub 접근: gh CLI 우선. gh 미가용이면 연결된 GitHub MCP 도구를 찾아 쓰고, 둘 다 없으면 "태그까지만 진행"하는 제한 모드를 제안하라.{{/if}}

status 모드: "릴리스 준비됐는지", "어떤 패키지 바뀌었어" 류 요청은 0~3단계만 수행하고 보고 후 멈춘다.

## 0. 대상 패키지 결정

- `python3 .superrelease/scripts/changed-packages.py --json` 실행 — scope별 anchor(마지막 태그)와 변경 파일을 확보한다.
- 사용자가 패키지를 지정했으면 그 scope(복수 가능). 지정하지 않았으면 hasChanges=true인 scope 목록을 보여주고 선택받아라.
- 선택된 scope의 config `dependents`를 확인해 전파 대상(6단계)이 생기는지 미리 안내하라.

## 1. preflight — 모두 통과해야 진행

1. 현재 브랜치: `git branch --show-current` 결과가 `{{repo.defaultBranch}}` 여야 함
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{repo.defaultBranch}} --count` 가 0
4. 전 scope 버전 일치: `python3 .superrelease/scripts/version.py verify` → exit 0
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
6. scope별 중단 상태: 대상 scope의 파일 버전(수식어 제외)이 그 scope의 anchor 태그보다 높은데 해당 버전 태그가 없으면 이전 릴리스가 중단된 것 — resume/rollback 중 선택받아라.

## 2. scope별 범위 산출

- anchor는 changed-packages 출력의 값(그 scope 태그 포맷의 최신 태그). anchor가 없으면 **첫 릴리스** — 커밋을 나열하지 말고 "Initial release"로 다뤄라.
- 수집: `git log <anchor>..HEAD --pretty=format:"%h %s" -- <scope.path>`{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}

## 3. scope별 bump 제안

- 그 scope의 config `bump.sources` 순서로 분석. 매핑: feat → minor, fix → patch, BREAKING CHANGE 푸터 또는 `!` → major. **0.x는** breaking → minor, feat → patch 관례를 적용하고 명시하라.
- 제시 형식: "**a: minor 제안** — 근거: feat 커밋 2건(제목 나열)" → 확인 또는 수동 지정.
- 계산은 스크립트로만: 현재 `python3 .superrelease/scripts/version.py get --scope <name>`, 결과 `python3 .superrelease/scripts/next-version.py --scope <name> --bump <level>` (수식어 제거는 `--release`).

## 4. 버전 반영

`python3 .superrelease/scripts/version.py set <버전> --scope <name>` — 그 scope의 전 위치 동기 수정. 7단계 프리뷰에 포함하라.

## 5. 릴리스 노트 (scope별)

`.claude/skills/release-notes/SKILL.md` 절차로 scope별 초안을 쓰고, 그 scope의 config `notes.destinations`별로 반영하라:

- `changelog`: 루트 CHANGELOG.md 최신 항목으로 `## <scope>@<version>` 삽입 (Unreleased 섹션이 있으면 그 아래)
- `release-file`: `<notes.perReleasePath><scope>@<version>.md` 파일 생성 (notes.template 사용)
- `github-release`: 8단계 Release 본문으로 사용

## 6. 의존성 전파

- 릴리스한 scope의 config `dependents`에 있는 각 scope를 **patch 릴리스 대상으로 추가**하라. 전이적으로 반복하되 이미 처리한 scope를 다시 만나면(순환) 중단하고 사용자에게 알려라.
- 전파로 추가된 scope도 3~9단계를 동일하게 수행하며, 노트에는 "의존성 <scope> <version> 반영"을 명시하라.
- 전파 체인 전체(누가 누구를 유발했는지)를 7단계 프리뷰에 표로 명시하고 확인받아라.

## 7. dry-run 프리뷰 → 커밋

scope별 표준 프리뷰를 보여주고 확인받아라:

- 바뀔 파일과 버전 diff (위치별 old → new)
- 생성될 커밋 메시지(`{{repo.releaseCommitFormat}}` 의 {scope}·{version} 치환)와 태그명(그 scope의 config `tag.format` — 네임스페이스는 포맷에 포함, 예: `my-pkg@1.2.0`)
- 실행될 명령 목록 (push, Release 생성 등)
{{#if repo.tagTriggersDeployment}}- ⚠️ **이 태그는 CI 배포를 트리거합니다** — 프리뷰에 반드시 명시
{{/if}}- 릴리스 노트 미리보기 + 의존성 전파 체인

{{#if repo.releasePath == "direct-push"}}확인 후: scope별로 버전 파일 + 노트 파일을 커밋하고(여러 scope면 scope당 1커밋) `git push origin {{repo.defaultBranch}}`.{{/if}}

## 8. 태그{{#if github.release}} + GitHub Release{{/if}} (scope별)

- 태그명: 그 scope의 config `tag.format`에서 {version}에 릴리스 버전 대입.
- push 직전 충돌 재확인: `git ls-remote --tags origin <태그>` 가 비어 있어야 함 — 결과가 있으면 **즉시 중단** (동시 릴리스 락, 버전 재사용 금지).
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
{{#if github.release}}- gh 경로: {{#if github.generateNotes}}`gh api repos/{owner}/{repo}/releases/generate-notes -f tag_name=<태그>` 뼈대를 참고하되 본문은 5단계 노트로 게시 — {{/if}}`gh release create <태그> --title "<scope>@<version>" --notes-file <노트 파일>`
- MCP 폴백 경로: generate-notes 뼈대 없이 5단계 노트로 Release를 생성하라.
{{/if}}

## 9. post-release (scope별)

그 scope의 config `postRelease.bump`가 next-snapshot이면 `python3 .superrelease/scripts/next-version.py --scope <name> --bump patch --qualifier <그 scope의 preRelease.qualifier>` → `version.py set --scope` → 같은 방식으로 프리뷰·확인 후 커밋·push. none이면 파일 버전을 그대로 둔다.

태그를 쓰지 않는 scope는 릴리스 후 config의 그 scope `anchor.value`를 릴리스 커밋 sha로 갱신해 함께 커밋하라.

## 실패 시

scope 단위로 어디까지 진행됐는지(파일 수정 / 커밋 / push / 태그 / Release)와 되돌리는 방법을 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 버전은 다음 패치로 덮고, 배포물 회수는 생태계 절차(npm deprecate, PyPI yank 등)를 안내하라.
````

- [ ] **Step 4: skills/init/assets/skills/release-notes-monorepo/SKILL.md 작성 (전체)**

````markdown
---
name: release-notes
description: {{project.name}} 모노레포의 패키지별 릴리스 노트 초안을 작성한다. 사용자가 릴리스 노트 써줘, 특정 패키지 릴리스 정리해줘, 체인지로그 정리, changelog, release notes 등 변경 요약·노트 작성 관련 요청을 하면 반드시 이 스킬을 사용한다. release 스킬이 5단계에서 재사용한다.
---

# release-notes — 패키지별 노트 초안 (부작용 없음)

이 스킬은 파일을 수정하거나 커밋·push하지 않는다. 초안 작성과 피드백 반영까지만 한다.

## 절차

1. 대상 scope 확정: 사용자가 지정하지 않았으면 `python3 .superrelease/scripts/changed-packages.py --json`으로 변경 있는 scope를 보여주고 선택받아라.
2. 범위 산출: 그 scope의 anchor(changed-packages 출력)..HEAD에서 `-- <scope.path>` 커밋만.
3. 소스 수집:
   - {{#if repo.mergePolicy == "squash"}}squash 레포: **PR 메타데이터가 1차 소스** — 커밋 제목의 `(#N)`으로 PR 번호를 얻고 `gh pr view <N> --json title,body,labels,closingIssuesReferences`로 읽어라. 커밋 메시지는 보조.{{else}}커밋 메시지(Conventional Commits)가 1차 소스, PR 메타데이터는 보조.{{/if}}
   - diff는 변경 의도가 모호할 때만 확인하라 (토큰 비용 유의).
4. 분류: Breaking(라벨, 타입 뒤 `!`, BREAKING CHANGE 푸터) / 기능 / 수정 / 기타. chore·릴리스 커밋 자체는 제외. 의존성 전파로 만들어진 릴리스라면 "의존성 <scope> <version> 반영"이 본문의 핵심이다.
5. 작성: `.superrelease/templates/` 아래 그 scope의 config `notes.template`(기본 notes-package.md) 구조를 따르고, 언어·독자·어조도 그 scope의 `notes.*` 값을 따르라. {package}에는 scope 이름, {version}·{date}는 작성 시점 값을 채운다.
6. 초안을 보여주고 피드백을 반영하라. 저장·게시는 release 스킬의 몫이다.
````

- [ ] **Step 5: skills/init/assets/templates/notes-package.md 작성 (전체)**

````markdown
{{#unless scope.notes.language == "en"}}<!-- 패키지 릴리스 노트 템플릿. {package}, {version}, {date}는 노트 작성 시점에 채운다. 해당 없는 섹션은 생략한다. -->
# {package} {version} — {date}

## 하이라이트
<!-- 이 패키지에서 가장 중요한 변경 1~3개를 한 문단으로 -->

## 변경 사항
<!-- - 사용자 관점 요약 (#PR번호) -->

## Breaking Changes
<!-- 없으면 섹션 삭제. 있으면 마이그레이션 가이드 필수 -->

## 마이그레이션 가이드
<!-- 이전 → 이후 코드/설정 예시 -->

## 의존성
<!-- 내부 의존성 반영(예: "a 1.2.0 반영")이 있으면 명시 -->
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Package release-note template. Fill {package}, {version}, {date} when drafting; drop empty sections. -->
# {package} {version} — {date}

## Highlights

## Changes

## Breaking Changes

## Migration Guide

## Dependencies
{{/unless}}
````

- [ ] **Step 6: manifest.json 전체 교체 (최종 11항목)**

```json
{
  "entries": [
    {
      "src": "skills/release/SKILL.md",
      "dest": ".claude/skills/release/SKILL.md",
      "render": true,
      "when": "repo.monorepoStrategy != \"independent\""
    },
    {
      "src": "skills/release-monorepo/SKILL.md",
      "dest": ".claude/skills/release/SKILL.md",
      "render": true,
      "when": "repo.monorepoStrategy == \"independent\""
    },
    {
      "src": "skills/release-notes/SKILL.md",
      "dest": ".claude/skills/release-notes/SKILL.md",
      "render": true,
      "when": "repo.monorepoStrategy != \"independent\""
    },
    {
      "src": "skills/release-notes-monorepo/SKILL.md",
      "dest": ".claude/skills/release-notes/SKILL.md",
      "render": true,
      "when": "repo.monorepoStrategy == \"independent\""
    },
    {
      "src": "scripts/version.py",
      "dest": ".superrelease/scripts/version.py",
      "render": false,
      "executable": true
    },
    {
      "src": "scripts/next-version.py",
      "dest": ".superrelease/scripts/next-version.py",
      "render": false,
      "executable": true
    },
    {
      "src": "scripts/changed-packages.py",
      "dest": ".superrelease/scripts/changed-packages.py",
      "render": false,
      "executable": true,
      "when": "repo.kind == \"monorepo\""
    },
    {
      "src": "templates/notes-single.md",
      "dest": ".superrelease/templates/notes-single.md",
      "render": true,
      "preserve": "template",
      "when": "repo.monorepoStrategy != \"independent\""
    },
    {
      "src": "templates/notes-package.md",
      "dest": ".superrelease/templates/notes-package.md",
      "render": true,
      "preserve": "template",
      "when": "repo.monorepoStrategy == \"independent\""
    },
    {
      "src": "templates/changelog-entry.md",
      "dest": ".superrelease/templates/changelog-entry.md",
      "render": true,
      "preserve": "template"
    },
    {
      "src": "github/release.yml",
      "dest": ".github/release.yml",
      "render": false,
      "when": "github.releaseYml"
    }
  ]
}
```

(M1 config는 `monorepoStrategy`가 null/부재 → `!=` 조건이 참 → 기존과 동일하게 렌더된다. 골든 불변의 근거.)

- [ ] **Step 7: 통과 확인 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS. **특히 `test_golden`이 골든 무변경으로 PASS해야 한다** — 실패하면 기존 asset을 건드렸다는 뜻이므로 되돌려라.
Run: `claude plugin validate . --strict` → 통과.

```bash
git add skills/init/assets tests/test_assets.py
git commit -m "feat: 모노레포 변형 스킬·notes-package 템플릿 — manifest 동일-dest when 스위칭

기존 단일 변형 asset은 무수정(M1 골든 바이트 불변). independent만 변형 스킬 사용.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 골든 pnpm-monorepo 추가 (M1 3종 불변 확인 포함)

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/pnpm-monorepo/expected/**` (update_golden.py 산출 — 검수 후 커밋)

**Interfaces:**
- Consumes: Task 1 `monorepo_config`, Task 4 manifest·변형 assets, 기존 `tests/update_golden.py`·`tests/test_golden.py`(수정 불필요 — GOLDEN dict를 순회)
- Produces: 4번째 골든 케이스 `pnpm-monorepo` — 모노레포 변형 렌더 결과의 회귀 방어선.

- [ ] **Step 1: tests/golden_configs.py 수정 (전체 교체)**

```python
"""Representative configs for golden-render snapshots."""
from helpers import monorepo_config, scope_config


def gradle_app():
    return scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])


def npm_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    cfg["scopes"][0]["notes"]["destinations"] = ["release-file", "github-release"]
    cfg["repo"]["tagTriggersDeployment"] = True
    return cfg


def jvm_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["github"]["releaseYml"] = False
    cfg["scopes"][0]["notes"]["language"] = "both"
    return cfg


def pnpm_monorepo():
    return monorepo_config()


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo}
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest tests.test_golden -v`
Expected: `pnpm-monorepo` subTest가 "golden missing — run: python3 tests/update_golden.py"로 FAIL. 기존 3 subTest는 PASS.

- [ ] **Step 3: 골든 생성 → 검수 → 불변 확인**

Run: `python3 tests/update_golden.py` → `updated golden: ...` 4줄.

**M1 불변 확인(필수):** `git status --porcelain tests/golden` 출력에 `tests/golden/pnpm-monorepo/` 신규 항목(`??`)만 있어야 한다. 기존 3종 트리에 ` M `이 하나라도 있으면 STOP — 원인(기존 asset/스크립트 수정)을 고치고 골든을 되돌려라(`git checkout -- tests/golden`).

**pnpm-monorepo 트리 검수(필수):**
- `.claude/skills/release/SKILL.md` — "모노레포 릴리스 오케스트레이터" 포함, `{{` 잔존 없음, 마커가 frontmatter 직후, `chore(release): {scope}@{version}` 인라인 확인
- `.claude/skills/release-notes/SKILL.md` — "changed-packages.py" 포함
- `.superrelease/scripts/changed-packages.py` — 존재, 셔뱅 다음 줄 마커, 실행 모드(100755)
- `.superrelease/templates/notes-package.md` — ko 블록만(하이라이트 있음, Highlights 없음 — monorepo_config의 language가 ko이므로)
- `.superrelease/templates/notes-single.md` — **부재**
- `.github/release.yml` — 존재(github.releaseYml true)

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (골든 4 subTest 포함).

```bash
git add tests/golden_configs.py tests/golden/pnpm-monorepo
git commit -m "test: 골든 pnpm-monorepo 추가 — 모노레포 변형 렌더 회귀 방어 (M1 3종 불변)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: scan.py — 모노레포 패키지·내부 의존성 열거

**Files:**
- Modify: `skills/init/scripts/scan.py` (`scan_monorepo` 교체 + 헬퍼 2개 추가)
- Test: `tests/test_scan.py` (2개 테스트 추가)

**Interfaces:**
- Consumes: 기존 `read()` 헬퍼, 기존 `scan_monorepo` 시그널 로직(유지)
- Produces (init 번들 1·7이 소비하는 리포트 확장 — 기존 키에 **추가만**):
  - `monorepo.packages: [{path, name, version}]` — node 워크스페이스 패키지 열거(pnpm-workspace.yaml의 `- "dir/*"` 항목, 루트 package.json `workspaces` 필드, 기본 `packages/*`·`apps/*`). 트레일링 `/*`(또는 `/**`) glob만 지원하는 휴리스틱(문서화).
  - `monorepo.internalDependencies: [{fromPath, fromName, toPath, toName}]` — 패키지의 dependencies/devDependencies/peerDependencies 중 워크스페이스 내 다른 패키지 이름을 가리키는 것.
  - `monorepo.gradleModuleHints: [names]` — settings.gradle include의 모듈 이름 힌트(열거만).
  - `suspected`는 기존 시그널 OR 패키지 2개 이상.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_scan.py에 추가**

아래 두 메서드를 **`ScanTest` 클래스 내부**, 마지막 메서드(`test_missing_dir_exits_2`) 뒤에 추가한다 (들여쓰기 유지 — 모듈 레벨 아님):

```python
    def test_monorepo_packages_and_internal_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/a/package.json":
                           '{"name": "a", "version": "0.1.0"}\n',
                       "packages/b/package.json":
                           '{"name": "b", "version": "0.2.0", '
                           '"dependencies": {"a": "workspace:^"}}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            mono = data["monorepo"]
            self.assertTrue(mono["suspected"])
            paths = {p["path"]: p for p in mono["packages"]}
            self.assertEqual(sorted(paths), ["packages/a", "packages/b"])
            self.assertEqual(paths["packages/a"]["version"], "0.1.0")
            deps = mono["internalDependencies"]
            self.assertEqual(len(deps), 1)
            self.assertEqual(deps[0]["fromName"], "b")
            self.assertEqual(deps[0]["toName"], "a")
            self.assertEqual(deps[0]["toPath"], "packages/a")

    def test_root_workspaces_field_enumerates_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"package.json":
                           '{"name": "root", "workspaces": ["libs/*"]}\n',
                       "libs/x/package.json":
                           '{"name": "x", "version": "1.0.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["libs/x"])
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest tests.test_scan -v`
Expected: 신규 2건이 KeyError(`packages` 키 부재)로 FAIL/ERROR. 기존 scan 테스트 PASS.

- [ ] **Step 3: scan.py 수정 — scan_monorepo 교체**

기존 `scan_monorepo` 함수 전체를 아래 3개 함수로 교체한다 (`scan_changelog` 앞 위치 유지):

```python
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
            ws = json.loads(root_pkg).get("workspaces")
        except json.JSONDecodeError:
            ws = None
        if isinstance(ws, list):
            globs += [g for g in ws if isinstance(g, str)]
        elif isinstance(ws, dict) and isinstance(ws.get("packages"), list):
            globs += [g for g in ws["packages"] if isinstance(g, str)]
    seen, packages = set(), []
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
            deps = set()
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                block = data.get(key)
                if isinstance(block, dict):
                    deps.update(block)
            packages.append({"path": rel, "name": data.get("name"),
                             "version": data.get("version"),
                             "_deps": sorted(deps)})
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
    return {"suspected": bool(signals) or len(packages) > 1,
            "signals": signals, "packages": packages,
            "internalDependencies": internal,
            "gradleModuleHints": _module_hints(repo)}
```

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (기존 gradle 스캔 테스트는 packages/internalDependencies/gradleModuleHints가 빈 값으로 추가되어도 영향 없음 — additive).
Run: `python3 skills/init/scripts/scan.py --repo . | python3 -m json.tool > /dev/null && echo self-scan-ok` → self-scan-ok.

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat: scan.py 모노레포 패키지·내부 의존성 열거 (워크스페이스 glob 휴리스틱)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: init SKILL.md 모노레포 확장 + 문서 정합 (references·README)

**Files:**
- Modify: `skills/init/SKILL.md`
- Modify: `skills/init/references/monorepo.md`
- Modify: `README.md`, `README_KO.md`

**Interfaces:**
- Consumes: Task 6 스캔 리포트 키(`monorepo.packages`, `monorepo.internalDependencies`), Task 2 `changed-packages.py`, Task 4 config 필드(`repo.monorepoStrategy`, scope별 `tag.format` 네임스페이스, `notes-package.md`)
- Produces: init이 모노레포에서 전략을 묻고 scope·dependents를 확정하는 질문 흐름. 완료 후에도 `wc -l skills/init/SKILL.md` ≤ 500, `claude plugin validate . --strict` 통과, README EN/KO 1:1 유지.

아래 편집은 전부 **정확한 old → new 텍스트 교체**다. old 텍스트는 현재 파일과 일치한다(불일치하면 STOP — 파일이 바뀐 것이므로 보고).

- [ ] **Step 1: skills/init/SKILL.md 편집 (6곳)**

**(a) 절대 규칙 마지막 항목:**

old:
```
- 아래 "M1 제약" 밖의 선택지는 "후속 버전 지원 예정"으로 표시하고 선택하지 못하게 한다.
```
new:
```
- 아래 "지원 범위와 제약" 밖의 선택지는 "후속 버전 지원 예정"으로 표시하고 선택하지 못하게 한다.
```

**(b) 번들 1:**

old:
```
- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). 모노레포 신호가 있으면 알리되 M1은 단일 스코프만 지원 — 루트 스코프로 진행할지 확인.
```
new:
```
- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). monorepo면 전략을 묻는다 — fixed(전 패키지 버전 공유) | independent(패키지별 독립) | 이중 체계(M3 예정 표시). independent면 스캔 리포트 `monorepo.packages`를 표로 제시해 scope 목록(이름 = 패키지 이름 또는 디렉터리명, path, 버전 파일)을 확정한다. fixed면 단일 root scope의 versionLocations에 전 패키지 버전 파일을 모은다(릴리스 흐름은 단일 레포와 동일).
```

**(c) 번들 2:**

old:
```
- **번들 2 — 체계·SSOT·태그**: 버전 체계(M1: SemVer만) / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다 / 태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed / moving major tag(M3 예정 표시).
```
new:
```
- **번들 2 — 체계·SSOT·태그**: 버전 체계(SemVer만 — CalVer/HeadVer는 M3 예정 표시) / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다 / 태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed — independent 모노레포면 scope별 `tag.format` 기본값을 `<scope이름>@{version}` 네임스페이스로 제안한다 / moving major tag(M3 예정 표시).
```

**(d) 번들 7:**

old:
```
- **번들 7 — 첫 릴리스·이력**: 기존 버전이 없으면 0.1.0 vs 1.0.0(공개 API 안정성 약속 기준으로 설명) / CHANGELOG backfill(M3 예정 표시) / destinations에 changelog가 있는데 CHANGELOG.md가 없으면 첫 릴리스 때 생성됨을 안내.
```
new:
```
- **번들 7 — 첫 릴리스·이력·전파**: 기존 버전이 없으면 0.1.0 vs 1.0.0(공개 API 안정성 약속 기준으로 설명) / CHANGELOG backfill(M3 예정 표시) / destinations에 changelog가 있는데 CHANGELOG.md가 없으면 첫 릴리스 때 생성됨을 안내 / (independent 모노레포) 내부 의존성 전파 — 스캔 리포트 `monorepo.internalDependencies`를 근거로 "b가 a에 의존하므로 a 릴리스 시 b를 자동 patch 릴리스" 제안을 scope별 `dependents` 목록으로 확정한다(순환 의존이 생기지 않는지 확인).
```

**(e) config 예시의 repo 블록:**

old:
```
    "releaseCommitFormat": "chore(release): {version}",
    "tagTriggersDeployment": false
```
new:
```
    "releaseCommitFormat": "chore(release): {version}",
    "tagTriggersDeployment": false,
    "monorepoStrategy": null
```

**(f) config 각주(3개 bullet의 마지막, `devChannel.immutableId...` 항목) 뒤에 bullet 추가:**

old:
```
- devChannel.immutableId를 기록했으면 요약 단계에서 해당 설정 스니펫(Spring `springBoot { buildInfo() }`, Docker `-t app:dev -t app:sha-<shortSha>` 병행 push, npm `1.3.0-dev.<sha>`)을 안내하라.
```
new:
```
- devChannel.immutableId를 기록했으면 요약 단계에서 해당 설정 스니펫(Spring `springBoot { buildInfo() }`, Docker `-t app:dev -t app:sha-<shortSha>` 병행 push, npm `1.3.0-dev.<sha>`)을 안내하라.
- 모노레포: `repo.monorepoStrategy`를 "fixed" 또는 "independent"로 기록한다. independent면 `scopes`가 패키지 수만큼 늘어나고, scope마다 `path`(패키지 경로), 상대 경로 기준의 `versionLocations`, `tag.format`(`<scope>@{version}` 네임스페이스), `notes.template: "notes-package.md"`, `dependents`(이 scope 릴리스 시 patch 릴리스로 따라갈 scope 이름 목록)를 설정하고, `releaseCommitFormat`은 `chore(release): {scope}@{version}` 을 기본으로 제안하라. fixed면 scope는 root 하나이고 versionLocations에 전 패키지 버전 파일이 들어간다.
```

**(g) Phase 3 자가 검증(4단계):**

old:
```
4. 자가 검증: `python3 .superrelease/scripts/version.py verify` → exit 0 / `python3 .superrelease/scripts/next-version.py --help` → exit 0. 실패하면 원인(대부분 versionLocations 오기)을 고치고 재렌더.
```
new:
```
4. 자가 검증: `python3 .superrelease/scripts/version.py verify` → exit 0 / `python3 .superrelease/scripts/next-version.py --help` → exit 0 / (모노레포) `python3 .superrelease/scripts/changed-packages.py --help` → exit 0. 실패하면 원인(대부분 versionLocations 오기)을 고치고 재렌더.
```

**(h) "M1 제약" 섹션 전체 교체:**

old:
```
## M1 제약 (해당 선택지에 "후속 버전 지원 예정" 표시)

- 버전 체계: SemVer만 — CalVer/HeadVer/sequential은 M3
- 단일 스코프만 — 모노레포 fixed/independent/이중 체계는 M2/M3
- 커밋 경로: direct-push만 — 릴리스 PR 모드는 M3
- pre-release: none/mutable만 — 불변 카운터(-rc.N)는 M3
- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3
- hotfix·release-train 스킬, moving major tag, CHANGELOG backfill: M3
```
new:
```
## 지원 범위와 제약 (해당 선택지에 "후속 버전 지원 예정" 표시)

지원: 단일 레포(app/library) + 모노레포 fixed/independent — scope별 태그 네임스페이스, changed-packages 변경 감지, dependents 전파 포함.

- 버전 체계: SemVer만 — CalVer/HeadVer/sequential은 M3
- 모노레포 이중 체계(루트 train + 패키지 SemVer)와 release-train 스킬: M3
- 커밋 경로: direct-push만 — 릴리스 PR 모드는 M3
- pre-release: none/mutable만 — 불변 카운터(-rc.N)는 M3
- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3
- hotfix 스킬, moving major tag, CHANGELOG backfill: M3
```

- [ ] **Step 2: skills/init/references/monorepo.md — "## M1 범위" 섹션 전체 교체**

"## M1 범위" 헤딩부터 파일 끝까지(마지막 줄 "config의 `scopes` 배열은 M1 동안 항상 항목이 하나인 상태로 유지된다." 포함)를 다음으로 교체:

```
## 지원 현황

fixed / independent 전략, `dependents` 전파, `changed-packages.py` 변경 감지는 **M2부터 지원된다**. init이 모노레포를 감지하면 전략을 묻고, independent를 선택하면 scope를 패키지 수만큼 확장한다.

fixed는 단일 scope로 모델링된다 — 모든 패키지의 버전 파일을 root scope의 `versionLocations`에 모아 함께 bump하며, 릴리스 흐름은 단일 레포와 동일하다. independent는 scope별 태그 네임스페이스(`<scope>@{version}`)와 scope 단위 릴리스 흐름(변경 감지 → scope별 bump → scope별 태그 → dependents 전파)을 쓴다.

**이중 체계(dual-system)와 release-train은 M3**(조건부 기능)로 미뤄진다 — M2에서도 이중 체계 질문은 아직 등장하지 않는다.
```

- [ ] **Step 3: README.md / README_KO.md 편집 (1:1 유지)**

**README.md:**

(1) Roadmap:

old:
```
- **M1 (current)** — single repo: SemVer, mutable `-SNAPSHOT`, CHANGELOG /
  per-release files / GitHub Releases, direct push
- **M2** — monorepo: fixed/independent strategies, changed-package detection,
  `{pkg}@{ver}` tag namespaces, dependency propagation
```
new:
```
- **M1 (shipped)** — single repo: SemVer, mutable `-SNAPSHOT`, CHANGELOG /
  per-release files / GitHub Releases, direct push
- **M2 (current)** — monorepo: fixed/independent strategies, changed-package
  detection, `{pkg}@{ver}` tag namespaces, dependency propagation
```

(2) "What gets generated" 표에서 `next-version.py` 행 바로 아래에 행 추가:

```
| `.superrelease/scripts/changed-packages.py` | Detect changed packages per scope (monorepo only) |
```

(3) "Using the scripts directly" 코드 블록에서 마지막 줄(`python3 .superrelease/scripts/next-version.py --bump minor --qualifier SNAPSHOT`) 아래에 추가:

```
python3 .superrelease/scripts/changed-packages.py --json   # monorepo: changes since each package's last tag
```

**README_KO.md — 같은 3곳을 1:1로:**

(1) 로드맵:

old:
```
- **M1 (현재)** — 단일 레포: SemVer, 가변 `-SNAPSHOT`, CHANGELOG /
  릴리스별 파일 / GitHub Releases, direct push
- **M2** — 모노레포: fixed/independent 전략, 변경 패키지 감지,
  `{pkg}@{ver}` 태그 네임스페이스, 의존성 전파
```
new:
```
- **M1 (완료)** — 단일 레포: SemVer, 가변 `-SNAPSHOT`, CHANGELOG /
  릴리스별 파일 / GitHub Releases, direct push
- **M2 (현재)** — 모노레포: fixed/independent 전략, 변경 패키지 감지,
  `{pkg}@{ver}` 태그 네임스페이스, 의존성 전파
```

(2) 생성물 표 `next-version.py` 행 아래:

```
| `.superrelease/scripts/changed-packages.py` | scope별 변경 패키지 감지 (모노레포 전용) |
```

(3) 스크립트 사용 코드 블록 마지막에 (명령·플래그는 EN과 바이트 동일, 주석만 한국어):

```
python3 .superrelease/scripts/changed-packages.py --json   # 모노레포: 패키지별 마지막 태그 이후 변경
```

주의: EN/KO에서 (3)의 **주석 텍스트는 언어별로 다르다** — 이 코드 블록 줄은 기존 EN/KO 대응 관행(명령 동일·주석 번역)을 따른 것이며, 섹션 수·표 행 수 1:1은 유지된다.

- [ ] **Step 4: 검증 후 커밋**

Run: `wc -l skills/init/SKILL.md` → 500 이하.
Run: `claude plugin validate . --strict` → 통과.
Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (문서 변경만).
확인: README.md와 README_KO.md의 헤딩 수·표 행 수가 여전히 1:1.

```bash
git add skills/init/SKILL.md skills/init/references/monorepo.md README.md README_KO.md
git commit -m "feat: init 모노레포 질문 확장(전략·scope·dependents) + 문서 정합

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 최종 검증 — pnpm 모노레포 결정론 파이프라인 e2e

**Files:**
- Create: 없음 (스크래치 샘플 레포 — 커밋 대상 아님)

**Interfaces:**
- Consumes: 전부 — M2 완료 기준의 자동화 가능한 부분을 통짜로 태운다.

- [ ] **Step 1: 전체 테스트 + 플러그인 검증**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS.
Run: `claude plugin validate . --strict` → 통과.
Run: `git status --porcelain tests/golden` → 출력 없음(골든 4종 커밋 상태 그대로).

- [ ] **Step 2: pnpm 모노레포 샘플에서 결정론 파이프라인 e2e**

```bash
PLUGIN=$(pwd)   # superrelease 플러그인 레포 루트에서 시작
S="$(mktemp -d)/pnpm-mono"
mkdir -p "$S/packages/a" "$S/packages/b" && cd "$S"
git init -q -b main
printf 'packages:\n  - "packages/*"\n' > pnpm-workspace.yaml
printf '{\n  "name": "a",\n  "version": "0.1.0"\n}\n' > packages/a/package.json
printf '{\n  "name": "b",\n  "version": "0.1.0",\n  "dependencies": {\n    "a": "workspace:^"\n  }\n}\n' > packages/b/package.json
git -c user.email=t@test -c user.name=tester add -A
git -c user.email=t@test -c user.name=tester commit -qm "feat: 초기 패키지 (#1)"

# 1) 스캔: 패키지 2개 + 내부 의존 b→a
python3 "$PLUGIN/skills/init/scripts/scan.py" --repo . | python3 -c "
import json, sys
m = json.load(sys.stdin)['monorepo']
assert len(m['packages']) == 2, m['packages']
assert m['internalDependencies'][0]['toName'] == 'a', m['internalDependencies']
print('scan-mono-ok')"

# 2) config 작성 (init이 만들 independent 정본형)
mkdir -p .superrelease
cat > .superrelease/config.json <<'CFG'
{
  "superrelease": { "pluginVersion": "0.1.0", "configVersion": 1,
                    "generatedAt": "2026-01-01T00:00:00+00:00" },
  "repo": { "kind": "monorepo", "defaultBranch": "main", "mergePolicy": "squash",
            "releasePath": "direct-push", "branching": "trunk",
            "maintenanceLines": false, "train": false,
            "releaseCommitFormat": "chore(release): {scope}@{version}",
            "tagTriggersDeployment": false, "monorepoStrategy": "independent" },
  "github": { "release": true, "generateNotes": true, "releaseYml": true },
  "scopes": [
    { "name": "a", "path": "packages/a",
      "scheme": { "type": "semver", "pattern": null },
      "versionLocations": [ { "file": "package.json", "type": "json-path", "path": "version" } ],
      "tag": { "enabled": true, "format": "a@{version}", "annotated": true,
               "signed": false, "movingMajorTag": false },
      "bump": { "mode": "auto-confirm", "sources": ["conventional-commits"],
                "fallback": "diff", "compatCheck": null },
      "preRelease": { "style": "none", "qualifier": null },
      "devChannel": { "enabled": false, "qualifier": null, "immutableId": [] },
      "postRelease": { "bump": "none" },
      "notes": { "destinations": ["changelog", "github-release"], "language": "ko",
                 "audience": "developers", "tone": "neutral",
                 "template": "notes-package.md", "perReleasePath": "docs/releases/" },
      "anchor": { "type": "tag", "value": null }, "dependents": ["b"] },
    { "name": "b", "path": "packages/b",
      "scheme": { "type": "semver", "pattern": null },
      "versionLocations": [ { "file": "package.json", "type": "json-path", "path": "version" } ],
      "tag": { "enabled": true, "format": "b@{version}", "annotated": true,
               "signed": false, "movingMajorTag": false },
      "bump": { "mode": "auto-confirm", "sources": ["conventional-commits"],
                "fallback": "diff", "compatCheck": null },
      "preRelease": { "style": "none", "qualifier": null },
      "devChannel": { "enabled": false, "qualifier": null, "immutableId": [] },
      "postRelease": { "bump": "none" },
      "notes": { "destinations": ["changelog", "github-release"], "language": "ko",
                 "audience": "developers", "tone": "neutral",
                 "template": "notes-package.md", "perReleasePath": "docs/releases/" },
      "anchor": { "type": "tag", "value": null }, "dependents": [] }
  ],
  "decisions": []
}
CFG

# 3) 렌더 (--check → 실제) — 모노레포 변형 확인
python3 "$PLUGIN/skills/init/scripts/render.py" --config .superrelease/config.json \
  --assets "$PLUGIN/skills/init/assets" --repo . --check
python3 "$PLUGIN/skills/init/scripts/render.py" --config .superrelease/config.json \
  --assets "$PLUGIN/skills/init/assets" --repo .
grep -q "모노레포 릴리스 오케스트레이터" .claude/skills/release/SKILL.md && echo variant-ok
test -x .superrelease/scripts/changed-packages.py && echo cp-deployed
test -f .superrelease/templates/notes-package.md && test ! -f .superrelease/templates/notes-single.md && echo templates-ok

# 4) 첫 릴리스 판정: 둘 다 변경(anchor 없음)
python3 .superrelease/scripts/changed-packages.py --json | python3 -c "
import json, sys
by = {s['name']: s for s in json.load(sys.stdin)['scopes']}
assert by['a']['hasChanges'] and by['b']['hasChanges']
assert by['a']['anchorType'] == 'none'
print('first-release-ok')"

# 5) a 릴리스 시뮬레이션 (minor: 0.1.0 → 0.2.0) + 태그
python3 .superrelease/scripts/next-version.py --scope a --bump minor    # → 0.2.0
python3 .superrelease/scripts/version.py set 0.2.0 --scope a
python3 .superrelease/scripts/version.py verify
python3 -c "import json; assert json.load(open('packages/b/package.json'))['version'] == '0.1.0'; print('b-untouched-ok')"
git -c user.email=t@test -c user.name=tester add -A
git -c user.email=t@test -c user.name=tester commit -qm "chore(release): a@0.2.0"
git -c user.email=t@test -c user.name=tester tag -a a@0.2.0 -m a@0.2.0
git -c user.email=t@test -c user.name=tester tag -a b@0.1.0 -m b@0.1.0   # b 현재 상태도 릴리스로 간주

# 6) 태그 후: 변경 없음 → 둘 다 false
python3 .superrelease/scripts/changed-packages.py --json | python3 -c "
import json, sys
by = {s['name']: s for s in json.load(sys.stdin)['scopes']}
assert by['a']['anchor'] == 'a@0.2.0' and not by['a']['hasChanges']
assert by['b']['anchor'] == 'b@0.1.0' and not by['b']['hasChanges']
print('clean-after-tags-ok')"

# 7) b만 변경 → b만 감지
printf 'console.log(1)\n' > packages/b/index.js
git -c user.email=t@test -c user.name=tester add -A
git -c user.email=t@test -c user.name=tester commit -qm "feat: b 기능 (#2)"
python3 .superrelease/scripts/changed-packages.py --json | python3 -c "
import json, sys
by = {s['name']: s for s in json.load(sys.stdin)['scopes']}
assert not by['a']['hasChanges'] and by['b']['hasChanges']
assert 'packages/b/index.js' in by['b']['changed']
print('detect-b-only-ok')"

# 8) 전파 시뮬레이션 (a 릴리스가 dependents=[b]로 b patch 릴리스 유발 가정)
python3 .superrelease/scripts/next-version.py --scope b --bump patch    # → 0.1.1
python3 .superrelease/scripts/version.py set 0.1.1 --scope b
python3 .superrelease/scripts/version.py verify && echo mono-e2e-ok
```

Expected: `scan-mono-ok`, `--check`에 conflict 없음, 렌더가 `rendered 8 file(s)`(스킬 2 + 스크립트 3 + notes-package + changelog-entry + release.yml), `variant-ok`/`cp-deployed`/`templates-ok`, `first-release-ok`, next-version 출력 `0.2.0`, `b-untouched-ok`, `clean-after-tags-ok`, `detect-b-only-ok`, `0.1.1`, 마지막 `mono-e2e-ok`. 실패 시 해당 태스크로 돌아가 수정 후 재실행.

- [ ] **Step 3: 마무리 확인 (수정 사항이 있었던 경우만 커밋)**

```bash
cd "$PLUGIN" && git status --porcelain   # 비어 있으면 커밋 불필요
```

---

## 수동 e2e 검증 체크리스트 (구현 완료 후 사용자와 함께)

init·릴리스는 대화형이므로 아래를 실제 세션에서 수행한다. M2 완료 기준의 나머지 절반이다.

1. **모노레포 init**: pnpm 모노레포 샘플에서 `claude --plugin-dir <플러그인 경로>` 세션 → `/superrelease:init` → 모노레포 감지 + 전략 질문(fixed | independent, 이중은 M3 표시) → independent 선택 → 스캔 packages 표로 scope 확정 → internalDependencies 기반 dependents 제안(a.dependents=[b]) → 렌더 프리뷰(모노레포 변형) → 커밋 확인까지.
2. **패키지 개별 릴리스 ①**: "a 릴리스해줘" → changed-packages로 대상 확인 → a minor 릴리스(a@0.2.0 태그) → **전파: b가 patch 릴리스 대상으로 추가·프리뷰에 체인 명시 → b@0.1.1** — 두 패키지 개별 릴리스 + 전파가 한 흐름에서 동작.
3. **패키지 개별 릴리스 ②**: b만 커밋 추가 → "릴리스해줘"(패키지 미지정) → changed-packages가 b만 제안 → b patch 릴리스(전파 없음 — b.dependents 비어 있음).
4. **status 모드**: "어떤 패키지 바뀌었어?" → 0~3단계에서 멈추는지.
5. **fixed 전략 확인**: 별도 샘플에서 fixed 선택 → 단일 scope + M1 변형 스킬이 렌더되는지(notes-single, changed-packages는 배포되되 스킬은 단일 흐름).
6. **재init**: config에서 b.dependents를 바꾼 뒤 init → 질문 없이 재렌더 / notes-package.md 마커 제거 손편집 → 보존 확인.

## M2 완료 기준 매핑 (스펙 §12)

| 완료 기준 | 검증 위치 |
|---|---|
| fixed/independent 전략 | Task 4(변형 스위칭)·Task 7(질문) + 수동 1·5 |
| changed-packages.py | Task 2 + Task 8 Step 2(4·6·7) |
| 태그 네임스페이스 `{pkg}@{ver}` | Task 1(config 형태)·Task 8(a@0.2.0 anchor 해석) + 수동 2 |
| 내부 의존성 전파 | Task 4(스킬 6단계)·Task 7(번들 7 질문) + Task 8 Step 2(8) + 수동 2 |
| notes-package.md | Task 4·Task 5(골든) |
| init 질문 확장 | Task 7 + 수동 1 |
| **pnpm 모노레포 샘플에서 independent로 두 패키지 개별 릴리스 + 전파 e2e** | Task 8(결정론 부분) + 수동 체크리스트 1~3 |

M3(이중 체계·release-train·hotfix·릴리스 PR·CalVer/HeadVer·counter pre-release·backfill·fragment)는 이 계획의 범위 밖이며 후속 계획으로 진행한다.
