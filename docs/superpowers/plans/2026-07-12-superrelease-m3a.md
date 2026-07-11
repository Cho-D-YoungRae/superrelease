# superrelease M3a (버전 체계 확장) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superrelease에 M3a — CalVer/HeadVer 산술(`next-version.py` 확장), 불변 카운터 pre-release 플로우(`-rc.N` 발행·승격, GitHub Release `--prerelease`), moving major tag(`v<major>` 유동 태그) — 를 추가한다. (M3는 3분할: **M3a=이 계획**, M3b=릴리스 경로(릴리스 PR·hotfix), M3c=트레인·노트. M3c는 M3a의 CalVer에 의존.)

**Architecture:** 산술은 전부 `next-version.py`에 집중(LLM 산술 금지, `--today` 주입으로 결정론 테스트). config 모드에서 scheme/pattern을 config에서 직접 읽어 `next-version.py --scope <name>` 한 줄로 다음 버전이 나온다. 릴리스 스킬은 단일 변형에 **조건부 블록**(scheme 분기·counter·moving tag — 기존 config 렌더는 바이트 불변), 모노레포 변형에 **런타임 프로즈**(scope 무인라인 원칙 유지)로 반영한다. 골든은 의도적 소스 변경분만 재생성하고 diff로 그 범위를 증명한다(M1.1/M2.1 선례).

**Tech Stack:** Python 3.9+ 표준 라이브러리(`datetime.date.isocalendar` 등), 동결 템플릿 dialect(엔진 수정 금지), git·gh CLI.

**스펙:** [docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md](../specs/2026-07-09-superrelease-plugin-design.md) §6.6(next-version)·§7(counter)·§12 M3. **베이스: main `10ac5f1`** (M1+M2+M2.1, 98 테스트). 실행 컨트롤러는 main에서 `feat/superrelease-m3a` 브랜치를 만들어 진행한다.

## Global Constraints

- Python 3.9+ stdlib만. 스크립트 버전 가드·`--help`(영어)·코드/메시지 영어. exit: 0 성공 / 1 검증 실패(잘못된 버전 문자열) / 2 사용법·설정 오류.
- **render.py 엔진부(Part 1)·version.py·changed-packages.py 수정 금지.** 이번에 소스가 바뀌는 골든-복사 스크립트는 `next-version.py` **하나뿐**이다.
- **골든 재생성 규율:** 의도적 소스 변경이 있는 태스크는 그 태스크 안에서 `python3 tests/update_golden.py`를 실행하고, `git status --porcelain tests/golden` 결과가 **정확히 예고된 파일만** 포함하는지 검증 후 함께 커밋한다. 예고 밖 골든 변경이 나오면 STOP(원인을 고치고 `git checkout -- tests/golden`).
  - Task 1(next-version.py 소스): 골든 4트리의 `next-version.py` 사본 4파일만.
  - Task 2(단일 release asset — 조건부 블록): 골든 변경 **0** (기존 config들은 semver·counter아님·movingMajorTag=false라 렌더 불변). update_golden 실행 불필요 — `test_golden`이 그대로 GREEN이어야 한다.
  - Task 3(모노레포 변형 — 무조건 프로즈): `pnpm-monorepo`의 release SKILL 사본 1파일만.
  - Task 4(신규 골든 2종): `tests/golden/{rc-library,calver-app}/` 신규(`??`)만.
- 동결 dialect 유지: `{{path}}`, `{{#if}}`(`{{else}}`, `==`/`!=`), `{{#unless}}`, `{{#each}}`만. 생성 SKILL.md ≤150줄(테스트 ≤149 pre-marker), init SKILL.md ≤500줄. 모노레포 변형은 scope 값 인라인 금지(런타임 프로즈만).
- HeadVer 규칙(스펙·references 확정): `{head}.{yearweek}.{build}` — head는 config `scheme.pattern`(문자열 숫자) 또는 `--head`, yearweek는 **ISO year 2자리 + ISO week 2자리 zero-pad**(1월 초가 전년도 주차일 수 있음), build는 현재 버전 3번째 필드 + 1(주 경계 무관 — 이 프로젝트 규칙, 리셋 없음).
- CalVer 토큰 어휘(동결): `YYYY`·`YY`·`0M`·`MM`·`0D`·`DD`·`MICRO`(최대 1개). MICRO 없는 패턴은 날짜 렌더만 반환(중복 방지는 release preflight의 태그 충돌이 담당).
- counter 시맨틱: `--prerelease QUAL` — 현재가 `X.Y.Z-QUAL.N`이면 `QUAL.(N+1)`, 아니면(`--bump` 조합 포함) 새 base에 `QUAL.1`. `--release`가 승격(수식어 제거, 기존 동작). `--prerelease`는 `--release`·`--qualifier`와 배타, `--bump`와 조합 가능.
- 테스트: `python3 -m unittest discover -s tests -v`. 커밋: Conventional Commits + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 스펙 대비 계획 단계 확정(§9 재량): HeadVer의 head 저장 위치 = `scheme.pattern`(별도 필드 신설 대신 기존 필드 재사용, config 각주로 문서화). `sequential` 체계는 M3a **비범위**(스펙 §12 M3 목록에 없음 — 수요 시 후속). semver에서 `--today`/`--pattern`/`--head` 사용은 exit 2(오사용 방지).

## 파일 구조 (M3a 전체)

```
수정  skills/init/assets/scripts/next-version.py     # Task 1: calver/headver/counter + config scheme 해석 (전체 재작성)
수정  tests/test_next_version.py                     # Task 1: 벡터 테스트 (기존 calver-미지원 테스트 교체)
갱신  tests/golden/*/expected/.superrelease/scripts/next-version.py ×4   # Task 1: 재생성
수정  skills/init/assets/skills/release/SKILL.md     # Task 2: scheme 분기·counter·moving tag 조건 블록
수정  tests/test_assets.py                           # Task 2·3: 렌더 스모크
수정  skills/init/assets/skills/release-monorepo/SKILL.md   # Task 3: 런타임 프로즈 2곳
갱신  tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md  # Task 3: 재생성
수정  tests/golden_configs.py                        # Task 4: rc_library, calver_app
생성  tests/golden/{rc-library,calver-app}/expected/**   # Task 4
수정  skills/init/SKILL.md                           # Task 5: 번들2·4 해제, config 각주, 지원 범위
수정  skills/init/references/version-schemes.md      # Task 5
수정  skills/init/references/prerelease-and-dev-channel.md  # Task 5
수정  README.md, README_KO.md                        # Task 5: 로드맵 3분해, Version schemes 문구
```

책임 분리: 날짜·주차·카운터 산술 = `next-version.py`(결정론), rc 발행/승격/moving tag의 절차·확인 = 릴리스 스킬(판단), pattern/head/style = config(SSOT).

---

### Task 1: next-version.py — CalVer/HeadVer/counter 확장

**Files:**
- Modify: `skills/init/assets/scripts/next-version.py` (전체 교체)
- Test: `tests/test_next_version.py`
- 갱신: `tests/golden/*/expected/.superrelease/scripts/next-version.py` ×4 (update_golden)

**Interfaces:**
- Produces (CLI — 릴리스 스킬·init이 의존):
  - `next-version.py [--current VER | --scope NAME] [--scheme {semver,calver,headver}] [--pattern P] [--head N] [--today YYYY-MM-DD] [--bump L | --release] [--qualifier Q] [--prerelease QUAL]`
  - config 모드(`--current` 없음): `../config.json`에서 scope를 해석(단일이면 생략 가능)해 `scheme.type`을 기본 scheme으로, calver면 `scheme.pattern`을 pattern으로, headver면 `scheme.pattern`을 head로 사용(플래그가 우선). current는 기존대로 version.py 서브프로세스.
  - calver/headver: `--bump/--release/--qualifier/--prerelease` 금지(exit 2), 인자 없이 다음 버전 계산. semver: `--today/--pattern/--head` 금지(exit 2), 기존 규칙 유지 + `--prerelease` 추가.
  - **기존 테스트 1개 교체**: `test_calver_not_supported_yet`(exit 2 + "M3" 기대)는 스펙 변경으로 무효 — calver 실동작 테스트로 대체한다(의도적 교체, 계획 명시).

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_next_version.py 수정**

(1) `test_calver_not_supported_yet` 메서드 전체를 삭제한다.

(2) 파일 끝(`if __name__` 앞)에 추가:

```python
class CalverTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_new_period_resets_micro(self):
        self.check(["--current", "0.1.0", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-07-10"],
                   "2026.7.0")

    def test_same_period_increments_micro(self):
        self.check(["--current", "2026.7.3", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-07-10"],
                   "2026.7.4")

    def test_month_rollover_resets_micro(self):
        self.check(["--current", "2026.7.9", "--scheme", "calver",
                    "--pattern", "YYYY.MM.MICRO", "--today", "2026-08-01"],
                   "2026.8.0")

    def test_zero_padded_tokens(self):
        self.check(["--current", "26.07.1", "--scheme", "calver",
                    "--pattern", "YY.0M.MICRO", "--today", "2026-07-05"],
                   "26.07.2")

    def test_pattern_without_micro_renders_date_only(self):
        self.check(["--current", "2026.06", "--scheme", "calver",
                    "--pattern", "YYYY.0M", "--today", "2026-07-10"],
                   "2026.07")

    def test_pattern_with_no_tokens_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "vvv", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_double_micro_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "MICRO.MICRO", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_calver_missing_pattern_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_calver_rejects_semver_ops(self):
        r = out("--current", "2026.7.0", "--scheme", "calver",
                "--pattern", "YYYY.MM.MICRO", "--bump", "patch")
        self.assertEqual(r.returncode, 2)

    def test_invalid_today_exits_2(self):
        r = out("--current", "1.0", "--scheme", "calver",
                "--pattern", "YYYY.MM.MICRO", "--today", "07/10/2026")
        self.assertEqual(r.returncode, 2)


class HeadverTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_build_increments_yearweek_from_today(self):
        # 2026-07-10 → ISO (2026, week 28) → yearweek "2628"
        self.check(["--current", "1.2627.4", "--scheme", "headver",
                    "--head", "1", "--today", "2026-07-10"],
                   "1.2628.5")

    def test_iso_year_boundary(self):
        # 2027-01-01(금) → ISO year 2026, week 53 → "2653"
        self.check(["--current", "2.2652.9", "--scheme", "headver",
                    "--head", "2", "--today", "2027-01-01"],
                   "2.2653.10")

    def test_unparseable_current_starts_build_zero(self):
        self.check(["--current", "abc", "--scheme", "headver",
                    "--head", "3", "--today", "2026-07-10"],
                   "3.2628.0")

    def test_missing_head_exits_2(self):
        r = out("--current", "1.2628.0", "--scheme", "headver",
                "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)

    def test_non_numeric_head_exits_2(self):
        r = out("--current", "1.2628.0", "--scheme", "headver",
                "--head", "vX", "--today", "2026-07-10")
        self.assertEqual(r.returncode, 2)


class CounterPrereleaseTest(unittest.TestCase):
    def check(self, args, expected):
        r = out(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)

    def test_bump_starts_counter_at_one(self):
        self.check(["--current", "1.3.0", "--bump", "minor", "--prerelease", "rc"],
                   "1.4.0-rc.1")

    def test_same_qualifier_increments(self):
        self.check(["--current", "1.4.0-rc.1", "--prerelease", "rc"], "1.4.0-rc.2")

    def test_other_qualifier_resets_to_one(self):
        self.check(["--current", "1.4.0-SNAPSHOT", "--prerelease", "rc"], "1.4.0-rc.1")

    def test_bare_base_starts_at_one(self):
        self.check(["--current", "1.4.0", "--prerelease", "rc"], "1.4.0-rc.1")

    def test_release_promotes(self):
        self.check(["--current", "1.4.0-rc.2", "--release"], "1.4.0")

    def test_prerelease_release_exclusive(self):
        r = out("--current", "1.4.0-rc.1", "--prerelease", "rc", "--release")
        self.assertEqual(r.returncode, 2)

    def test_prerelease_qualifier_exclusive(self):
        r = out("--current", "1.4.0", "--prerelease", "rc",
                "--qualifier", "SNAPSHOT")
        self.assertEqual(r.returncode, 2)

    def test_invalid_prerelease_qualifier_exits_2(self):
        r = out("--current", "1.4.0", "--prerelease", "-bad-")
        self.assertEqual(r.returncode, 2)

    def test_semver_rejects_today_pattern_head(self):
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--today", "2026-07-10").returncode, 2)
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--pattern", "YYYY").returncode, 2)
        self.assertEqual(out("--current", "1.0.0", "--bump", "patch",
                             "--head", "1").returncode, 2)


class SchemeFromConfigTest(unittest.TestCase):
    def test_calver_scheme_and_pattern_from_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = scope_config(
                [{"file": "package.json", "type": "json-path", "path": "version"}])
            cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
            repo = make_repo(tmp, cfg,
                             {"package.json": '{\n  "name": "x",\n  "version": "2026.7.1"\n}\n'})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--today", "2026-07-10")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "2026.7.2")

    def test_headver_head_from_config_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["scopes"][0]["scheme"] = {"type": "headver", "pattern": "3"}
            repo = make_repo(tmp, cfg, {"gradle.properties": "version=3.2627.7\n"})
            nv = Path(repo) / ".superrelease" / "scripts" / "next-version.py"
            r = run_script(nv, "--today", "2026-07-10")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "3.2628.8")
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: 동작 검증 계열(`check(...)`로 exit 0·값을 기대하는 테스트)은 전부 FAIL — 현 스크립트는 `--today`/`--prerelease`/`--pattern`/`--head`를 모르거나(argparse exit 2) calver를 "M3" 가드로 막기 때문. exit-2를 기대하는 일부 테스트는 같은 이유로 **우연히 즉시 PASS할 수 있다**(정상 — 구현 후에도 의도된 이유로 PASS해야 한다). 기존 나머지 테스트는 PASS. (`test_calver_not_supported_yet` 삭제분은 더 이상 실행되지 않음.)

- [ ] **Step 3: skills/init/assets/scripts/next-version.py 전체 교체**

```python
#!/usr/bin/env python3
"""next-version.py — compute the next version string. Deterministic arithmetic only.

Schemes:
  semver   --bump/--release/--qualifier/--prerelease act on the current version.
  calver   next version from --today and the pattern
           (tokens: YYYY YY 0M MM 0D DD MICRO; MICRO at most once).
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
CALVER_TOKEN_ORDER = ["YYYY", "MICRO", "YY", "0M", "0D", "MM", "DD"]


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


def calver_next(current, pattern, today):
    if not pattern:
        fail("calver requires --pattern or scheme.pattern in config", 2)
    parts = split_calver_pattern(pattern)
    tokens = [val for kind, val in parts if kind == "tok"]
    if not tokens:
        fail("invalid calver pattern (no tokens): " + pattern, 2)
    if tokens.count("MICRO") > 1:
        fail("calver pattern may contain MICRO at most once: " + pattern, 2)
    pieces = []  # rendered date/literal strings; None marks the MICRO slot
    for kind, val in parts:
        if kind == "lit":
            pieces.append(val)
        elif val == "MICRO":
            pieces.append(None)
        else:
            pieces.append(CALVER_RENDER[val](today))
    if None not in pieces:
        return "".join(pieces)
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
    if args.current is None:
        scope = load_scope(args.scope)
        cfg_scheme = scope.get("scheme") or {}
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
        today = parse_today(args.today)
        current = args.current if args.current is not None \
            else current_from_config(args.scope)
        if scheme == "calver":
            print(calver_next(current, pattern, today))
        else:
            print(headver_next(current, head, today))
        return

    # semver
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
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: **`test_golden_snapshots` 1건이 FAIL한다(4개 골든 subTest 전부 사본 불일치)** — next-version.py 소스가 바뀌어 골든 사본과 어긋나기 때문(예상된 상태, Step 5에서 해소). 그 외 전부 PASS(기존 semver 테스트가 하나라도 깨지면 하위호환 위반이므로 스크립트를 수정).

- [ ] **Step 5: 골든 사본 재생성 + 범위 검증**

Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden`
Expected: 정확히 4파일만 ` M ` — `tests/golden/{gradle-app,npm-app,jvm-library,pnpm-monorepo}/expected/.superrelease/scripts/next-version.py`. 다른 파일이 나오면 STOP(`git checkout -- tests/golden` 후 원인 수정).
Run: `python3 -m unittest discover -s tests -v` → **전부 PASS**.
Run: `python3 skills/init/assets/scripts/next-version.py --help` → exit 0.

- [ ] **Step 6: Commit**

```bash
git add skills/init/assets/scripts/next-version.py tests/test_next_version.py tests/golden
git commit -m "feat: next-version.py CalVer/HeadVer 산술·counter pre-release (--today 주입, config scheme 해석)

골든 4트리의 next-version.py 사본 재생성 포함(소스 의도 변경분만).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 단일 release asset — scheme 분기·counter·moving tag 조건 블록

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md` (old→new 3곳)
- Test: `tests/test_assets.py` (스모크 추가)

**Interfaces:**
- Consumes: Task 1의 next-version.py CLI(`--prerelease`, scheme별 인자 규칙)
- Produces: semver·counter·movingMajorTag·비semver 조건 블록. **기존 골든 4종의 config(semver, counter 아님, movingMajorTag=false)에서는 렌더 출력이 바이트 불변** — 조건 블록은 태그가 라인 내용에 밀착 배치되어 거짓이면 아무 문자도 남기지 않는다. 이 태스크에서 `update_golden.py`를 실행하지 않으며 `test_golden`이 그대로 GREEN이어야 한다(불변의 증명). GREEN이 아니면 태그 배치(공백/개행)를 고쳐라 — 골든 재생성 금지.

아래 편집은 정확한 old→new 교체다. old가 현재 파일과 불일치하면 STOP.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py의 `SkillAssetsTest`에 추가**

```python
    def test_release_skill_calver_branch(self):
        ctx = base_ctx()
        ctx["scope"]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("다음 버전 산출", out)
        self.assertNotIn("bump 제안", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_counter_and_moving_tag(self):
        ctx = base_ctx()
        ctx["scope"]["preRelease"] = {"style": "counter", "qualifier": "rc"}
        ctx["scope"]["tag"]["movingMajorTag"] = True
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("--prerelease rc", out)
        self.assertIn("moving major tag", out)
        self.assertIn("git tag -f", out)
        self.assertIn("--prerelease` 플래그", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_semver_default_has_no_new_blocks(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("bump 제안", out)
        self.assertNotIn("moving major tag", out)
        self.assertNotIn("--prerelease", out)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: 신규 3건 중 calver/counter 테스트 FAIL(블록 부재). `test_release_skill_semver_default_has_no_new_blocks`는 즉시 PASS(현재도 없음 — 고정 목적). 기존 전부 PASS.

- [ ] **Step 3: release/SKILL.md 편집 (3곳)**

**(a) §3 섹션 전체 교체.**

old:
```
## 3. bump 제안

- config `scopes[].bump.sources` 순서로 분석하라. 모호하면 fallback(diff)으로 검증하되 토큰 비용에 유의.
- 매핑: feat → minor, fix → patch, BREAKING CHANGE 푸터 또는 타입 뒤 `!` → major.
- **0.x 버전에서는** breaking → minor, feat → patch 관례를 적용하고 그 사실을 함께 표기하라.
- 제시 형식: "**minor 제안** — 근거: feat 커밋 2건(제목 나열)" → 확인 또는 수동 지정.
- 버전 문자열 계산은 스크립트로만:
  - 현재: `python3 .superrelease/scripts/version.py get`
{{#if scope.preRelease.qualifier}}  - 릴리스 버전(수식어 제거): `python3 .superrelease/scripts/next-version.py --release`
{{/if}}  - bump 적용: `python3 .superrelease/scripts/next-version.py --bump <level>`
```

new:
```
## 3. {{#if scope.scheme.type == "semver"}}bump 제안{{else}}다음 버전 산출{{/if}}

{{#if scope.scheme.type == "semver"}}- config `scopes[].bump.sources` 순서로 분석하라. 모호하면 fallback(diff)으로 검증하되 토큰 비용에 유의.
- 매핑: feat → minor, fix → patch, BREAKING CHANGE 푸터 또는 타입 뒤 `!` → major.
- **0.x 버전에서는** breaking → minor, feat → patch 관례를 적용하고 그 사실을 함께 표기하라.
- 제시 형식: "**minor 제안** — 근거: feat 커밋 2건(제목 나열)" → 확인 또는 수동 지정.
- 버전 문자열 계산은 스크립트로만:
  - 현재: `python3 .superrelease/scripts/version.py get`
{{#if scope.preRelease.qualifier}}  - 릴리스 버전(수식어 제거): `python3 .superrelease/scripts/next-version.py --release`
{{/if}}  - bump 적용: `python3 .superrelease/scripts/next-version.py --bump <level>`{{#if scope.preRelease.style == "counter"}}
  - pre-release 발행: 첫 발행은 `python3 .superrelease/scripts/next-version.py --bump <level> --prerelease {{scope.preRelease.qualifier}}`, 반복 발행은 `--prerelease {{scope.preRelease.qualifier}}`만(카운터 자동 증가), 정식 승격은 `--release`{{/if}}{{else}}- {{scope.scheme.type}} 체계에는 bump 수준 개념이 없다 — 다음 버전은 날짜·카운터가 결정한다: `python3 .superrelease/scripts/next-version.py` (config의 scheme·pattern을 자동 사용). 변경 내용은 2단계 수집분으로 노트에만 반영하고 버전 결정에는 쓰지 않는다.{{/if}}
```

**(b) §7 태그 생성 라인에 moving major tag 추가.**

old:
```
- {{#if scope.tag.signed}}signed 태그: `git tag -s <태그> -m "<한 줄 요약>"`{{else}}{{#if scope.tag.annotated}}annotated 태그: `git tag -a <태그> -m "<한 줄 요약>"`{{else}}태그: `git tag <태그>`{{/if}}{{/if}} → `git push origin <태그>`
```

new:
```
- {{#if scope.tag.signed}}signed 태그: `git tag -s <태그> -m "<한 줄 요약>"`{{else}}{{#if scope.tag.annotated}}annotated 태그: `git tag -a <태그> -m "<한 줄 요약>"`{{else}}태그: `git tag <태그>`{{/if}}{{/if}} → `git push origin <태그>`{{#if scope.tag.movingMajorTag}}
- **moving major tag**: 정식 릴리스(수식어 없는 버전)에 한해 `git tag -f v<major>` → `git push -f origin v<major>` — force-push이므로 프리뷰에 별도 경고를 명시하고 개별 확인을 받아라. pre-release에는 옮기지 않는다{{/if}}
```

**(c) §7 gh 라인에 `--prerelease` 플래그 추가.**

old:
```
{{/if}}{{#if github.release}}- gh 경로: {{#if github.generateNotes}}`gh api repos/{owner}/{repo}/releases/generate-notes -f tag_name=<태그>` 뼈대를 참고하되 본문은 5단계 노트로 게시 — {{/if}}`gh release create <태그> --title "<버전>" --notes-file <노트 파일>`
```

new:
```
{{/if}}{{#if github.release}}- gh 경로: {{#if github.generateNotes}}`gh api repos/{owner}/{repo}/releases/generate-notes -f tag_name=<태그>` 뼈대를 참고하되 본문은 5단계 노트로 게시 — {{/if}}`gh release create <태그> --title "<버전>" --notes-file <노트 파일>`{{#if scope.preRelease.style == "counter"}} (pre-release 버전이면 `--prerelease` 플래그를 추가하고, 승격 릴리스에는 붙이지 않는다){{/if}}
```

- [ ] **Step 4: 통과 확인 — 골든 불변이 곧 성공 기준**

Run: `python3 -m unittest discover -s tests -v`
Expected: 전부 PASS. **특히 `test_golden` 4건 GREEN**(기존 config 렌더 바이트 불변). 실패하면 조건 블록의 태그 배치가 공백/개행을 남긴 것 — 블록 열림 태그를 앞 내용에 밀착, 닫힘 태그 뒤 개행 규칙을 (a)~(c)의 new 텍스트 그대로 유지해 고쳐라. `update_golden.py` 실행 금지.
Run: `claude plugin validate . --strict` → 통과.

- [ ] **Step 5: Commit**

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py
git commit -m "feat: release 스킬 scheme 분기·counter 플로우·moving major tag (기존 렌더 바이트 불변)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 모노레포 변형 — 런타임 프로즈 2곳 + 골든 재생성

**Files:**
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (old→new 2곳)
- Test: `tests/test_assets.py` (모노레포 스모크 추가)
- 갱신: `tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md` (update_golden)

**Interfaces:**
- Consumes: Task 1 CLI. **scope 무인라인 원칙**: 모노레포 변형은 scopes[0]만 렌더 컨텍스트에 있으므로 scheme/counter/moving을 조건부 렌더할 수 없다 — 무조건 포함되는 런타임 프로즈로 지시한다(그래서 pnpm-monorepo 골든의 스킬 사본이 바뀌는 것이 **의도된 변경**이다).

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py의 `MonorepoAssetsTest`에 추가**

```python
    def test_release_monorepo_scheme_and_counter_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("calver/headver", out)
        self.assertIn("--prerelease", out)
        self.assertIn("movingMajorTag", out)
        self.assertNotIn("{{scope.", (ASSETS / "skills/release-monorepo/SKILL.md")
                         .read_text(encoding="utf-8"))  # 무인라인 유지
        self.assertLessEqual(len(out.splitlines()), 149)
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m unittest discover -s tests -v` → 신규 1건 FAIL(프로즈 부재). 기존 PASS.

- [ ] **Step 3: release-monorepo/SKILL.md 편집 (2곳)**

**(a) §3 마지막 bullet 뒤에 추가.**

old:
```
- 계산은 스크립트로만: 현재 `python3 .superrelease/scripts/version.py get --scope <name>`, 결과 `python3 .superrelease/scripts/next-version.py --scope <name> --bump <level>` (수식어 제거는 `--release`).
```

new:
```
- 계산은 스크립트로만: 현재 `python3 .superrelease/scripts/version.py get --scope <name>`, 결과 `python3 .superrelease/scripts/next-version.py --scope <name> --bump <level>` (수식어 제거는 `--release`).
- 그 scope의 `scheme.type`이 calver/headver면 bump 수준 없이 `python3 .superrelease/scripts/next-version.py --scope <name>`이 날짜·카운터로 다음 버전을 계산한다. `preRelease.style`이 counter인 scope는 pre-release 발행에 `--prerelease <그 scope의 qualifier>`, 정식 승격에 `--release`를 쓴다.
```

**(b) §8 태그 생성 라인 뒤에 추가.**

old:
```
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
```

new:
```
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
- 그 scope의 `tag.movingMajorTag`가 true면(semver 정식 릴리스에 한해) `git tag -f v<major>` → `git push -f origin v<major>` — force-push 경고를 프리뷰에 명시하고 개별 확인을 받아라. `preRelease.style`이 counter인 scope의 pre-release 버전이면 GitHub Release에 `--prerelease` 플래그를 붙인다.
```

- [ ] **Step 4: 골든 재생성 + 범위 검증 + 통과 확인**

Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden`
Expected: 정확히 1파일만 ` M ` — `tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md`. 다른 파일이 나오면 STOP.
Run: `python3 -m unittest discover -s tests -v` → 전부 PASS. `claude plugin validate . --strict` → 통과.

- [ ] **Step 5: Commit**

```bash
git add skills/init/assets/skills/release-monorepo/SKILL.md tests/test_assets.py tests/golden
git commit -m "feat: 모노레포 릴리스 스킬에 scheme·counter·moving tag 런타임 지시 추가

pnpm-monorepo 골든의 스킬 사본 재생성 포함(의도 변경분만).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 골든 2종 추가 — rc-library·calver-app

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/{rc-library,calver-app}/expected/**` (update_golden 산출 — 검수 후 커밋)

**Interfaces:**
- Consumes: Task 2의 조건 블록(counter·moving·scheme 분기)
- Produces: 새 조건 경로를 바이트 단위로 고정하는 골든 2종. 기존 4종 트리는 이 태스크에서 불변(`git status`에 `??`만).

- [ ] **Step 1: tests/golden_configs.py 수정 — 함수 2개와 GOLDEN 항목 추가**

`pnpm_monorepo()` 함수 아래에 추가하고 GOLDEN dict를 교체:

```python
def rc_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["scopes"][0]["preRelease"] = {"style": "counter", "qualifier": "rc"}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    cfg["scopes"][0]["tag"]["movingMajorTag"] = True
    return cfg


def calver_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app}
```

- [ ] **Step 2: 실패 확인 → 골든 생성 → 검수**

Run: `python3 -m unittest discover -s tests -v` → `rc-library`/`calver-app` subTest가 "golden missing"으로 FAIL, 기존 4 subTest PASS.
Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden` → `?? tests/golden/rc-library/`·`?? tests/golden/calver-app/`만(기존 4종에 ` M ` 없어야 — 있으면 STOP).

**검수(필수, 결과를 리포트에 기록):**
- `rc-library/expected/.claude/skills/release/SKILL.md`: "bump 제안" 헤딩(semver), `--prerelease rc` 라인, "moving major tag"·`git tag -f` 라인, gh 라인의 `--prerelease` 플래그 문구, `{{` 잔존 없음, 마커 frontmatter 직후.
- `calver-app/expected/.claude/skills/release/SKILL.md`: "다음 버전 산출" 헤딩, "bump 수준 개념이 없다" 문구, "bump 제안" 부재, `--prerelease` 부재.
- 두 트리 모두: `notes-single.md` 존재(단일 변형), `changed-packages.py` 부재(모노레포 아님), `.github/release.yml` 존재.

- [ ] **Step 3: 통과 확인 후 커밋**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (골든 6 subTest).

```bash
git add tests/golden_configs.py tests/golden/rc-library tests/golden/calver-app
git commit -m "test: 골든 rc-library·calver-app 추가 — counter/moving tag/calver 분기 회귀 방어

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: init SKILL.md 해제 + references·README 정합

**Files:**
- Modify: `skills/init/SKILL.md`
- Modify: `skills/init/references/version-schemes.md`
- Modify: `skills/init/references/prerelease-and-dev-channel.md`
- Modify: `README.md`, `README_KO.md`

**Interfaces:**
- Consumes: Task 1 CLI(HeadVer head = `scheme.pattern` 저장 규약)
- Produces: init이 CalVer/HeadVer·counter·moving major tag를 실제 선택지로 제시. 문서가 M3a 지원 현황을 정확히 반영. `wc -l skills/init/SKILL.md` ≤500, `--strict` 통과, README EN/KO 1:1 유지.

아래는 정확한 old→new 교체다. old 불일치 시 STOP.

- [ ] **Step 1: skills/init/SKILL.md 편집 (4곳)**

**(a) 번들 2:**

old:
```
- **번들 2 — 체계·SSOT·태그**: 버전 체계(SemVer만 — CalVer/HeadVer는 M3 예정 표시) / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다 / 태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed — independent 모노레포면 scope별 `tag.format` 기본값을 `<scope이름>@{version}` 네임스페이스로 제안한다 / moving major tag(M3 예정 표시).
```
new:
```
- **번들 2 — 체계·SSOT·태그**: 버전 체계 SemVer | CalVer | HeadVer (sequential은 후속 표시) — 라이브러리는 SemVer 사실상 강제, CalVer면 pattern(예: `YYYY.MM.MICRO` — 어휘 YYYY/YY/0M/MM/0D/DD/MICRO)을, HeadVer면 head 번호를 `scheme.pattern`에 기록한다 / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다 / 태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed — independent 모노레포면 scope별 `tag.format` 기본값을 `<scope이름>@{version}` 네임스페이스로 제안한다 / moving major tag — semver+태그 사용 시 `v<major>` 유동 태그 운용 여부(force-push 수반을 경고하고 결정).
```

**(b) 번들 4:**

old:
```
- **번들 4 — pre-release·dev·post**: 수식어 스타일 none | mutable(-SNAPSHOT류) | counter(M3 예정 표시) / (앱·mutable) dev 채널 qualifier 이름과 불변 식별자 immutableId(spring-build-info | docker-sha-tag | npm-dev-suffix) — M1은 config 기록 + 설정 스니펫 안내만, 배포 자동화는 하지 않음 / post-release bump — 라이브러리→next-snapshot 기본, 앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안).
```
new:
```
- **번들 4 — pre-release·dev·post**: 수식어 스타일 none | mutable(-SNAPSHOT류) | counter(-rc.N 등 불변 카운터 — qualifier 이름(rc/alpha/beta)을 확정하고, counter는 postRelease none을 기본 제안) / (앱·mutable) dev 채널 qualifier 이름과 불변 식별자 immutableId(spring-build-info | docker-sha-tag | npm-dev-suffix) — config 기록 + 설정 스니펫 안내만, 배포 자동화는 하지 않음 / post-release bump — 라이브러리→next-snapshot 기본, 앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안).
```

**(c) config 각주 — versionLocations 타입 bullet 바로 아래에 bullet 추가.**

old:
```
- versionLocations 타입: `properties-key`(key= 값) | `json-path`(예: package.json의 "version") | `regex`(캡처 그룹 정확히 1개, MULTILINE로 매칭됨 — scan 리포트의 pattern을 그대로 옮기면 된다).
```
new:
```
- versionLocations 타입: `properties-key`(key= 값) | `json-path`(예: package.json의 "version") | `regex`(캡처 그룹 정확히 1개, MULTILINE로 매칭됨 — scan 리포트의 pattern을 그대로 옮기면 된다).
- scheme: semver면 `pattern: null`. calver면 `pattern`에 CalVer 패턴 문자열(예: "YYYY.MM.MICRO"), headver면 `pattern`에 head 번호 문자열(예: "1")을 기록한다 — 다음 버전은 `next-version.py`가 config의 scheme으로 자동 계산한다.
```

**(d) 지원 범위와 제약 목록:**

old:
```
- 버전 체계: SemVer만 — CalVer/HeadVer/sequential은 M3
- 모노레포 이중 체계(루트 train + 패키지 SemVer)와 release-train 스킬: M3
- 커밋 경로: direct-push만 — 릴리스 PR 모드는 M3
- pre-release: none/mutable만 — 불변 카운터(-rc.N)는 M3
- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3
- hotfix 스킬, moving major tag, CHANGELOG backfill: M3
```
new:
```
- 버전 체계: SemVer/CalVer/HeadVer 지원 — sequential은 후속
- pre-release: none/mutable/counter(-rc.N) 지원 / moving major tag 지원(force-push 경고 수반)
- 모노레포 이중 체계(루트 train + 패키지 SemVer)와 release-train 스킬: M3c
- 커밋 경로: direct-push만 — 릴리스 PR 모드는 M3b
- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3c
- hotfix 스킬: M3b / CHANGELOG backfill: M3c
```

- [ ] **Step 2: references/version-schemes.md 편집 (3곳)**

**(a)** old:
```
**CalVer의 다음 버전 계산은 M3에서 `next-version.py --scheme calver --pattern <PATTERN>` 형태로 지원될 예정이며, M1에는 아직 구현되어 있지 않다.**
```
new:
```
**CalVer의 다음 버전 계산은 `next-version.py --scheme calver --pattern <PATTERN> [--today YYYY-MM-DD]`가 수행한다** — 같은 기간이면 MICRO를 증가시키고, 기간이 바뀌면 0으로 리셋한다(MICRO가 없는 패턴은 날짜 렌더만 반환). config 모드(`--scope`)에서는 scheme.pattern을 자동 사용한다.
```

**(b)** old:
```
**다음 버전 계산(yearweek 산출, build 증가)은 M3에서 `next-version.py`가 `--scheme headver --head <N>` 형태로 지원할 예정이며, M1에는 구현되어 있지 않다.**
```
new:
```
**다음 버전 계산(yearweek 산출, build 증가)은 `next-version.py --scheme headver --head <N> [--today YYYY-MM-DD]`가 수행한다** — yearweek는 ISO 연도 2자리+ISO 주차 2자리(1월 초는 전년도 주차일 수 있음), build는 현재 버전의 3번째 필드+1(리셋 없음)이다. config에는 head 번호를 `scheme.pattern`에 기록하며 config 모드에서 자동 사용된다.
```

**(c)** old:
```
**M1 구현은 SemVer만 지원한다.** CalVer와 HeadVer는 config 스키마에 선택지가 이미 예약되어 있지만 실제 날짜·주차 산술 로직은 아직 없다.

스캔이나 질문 단계에서 이 체계들이 후보로 떠오르면 "후속 버전에서 지원 예정"이라고 안내하고 M1에서는 선택 자체를 막는다.
```
new:
```
**SemVer·CalVer·HeadVer 세 체계 모두 지원된다** — 날짜·주차·카운터 산술은 전부 `next-version.py`가 수행하며(LLM 산술 금지), `--today` 주입으로 결정론적으로 테스트된다.

sequential(단순 증가)은 아직 구현되어 있지 않다 — 질문 단계에서 후보로 떠오르면 "후속 버전에서 지원 예정"으로 안내한다.
```

- [ ] **Step 3: references/prerelease-and-dev-channel.md 편집 (2곳)**

**(a)** old:
```
(superrelease에서 불변 카운터형의 릴리스 플로우 자체는 M3에서 구현되며, config의 선택지 자리는 M1부터 마련되어 있다.)
```
new:
```
(superrelease에서 불변 카운터형 릴리스 플로우는 지원된다 — 발행은 `next-version.py --prerelease <qualifier>`(카운터 자동 증가), 정식 승격은 `--release`가 담당한다.)
```

**(b)** old:
```
이 흐름은 각 rc가 GitHub Release의 prerelease 표시와 자연스럽게 연결되지만, superrelease에서는 **이 릴리스 플로우 자체가 M3 구현 대상**이라 M1에서는 다루지 않는다.
```
new:
```
이 흐름은 각 rc가 GitHub Release의 prerelease 표시와 자연스럽게 연결된다 — superrelease의 release 스킬은 counter 스타일 scope의 pre-release 버전에 `gh release create --prerelease` 플래그를 붙이고, 승격 릴리스에는 붙이지 않는다.
```

- [ ] **Step 4: README.md / README_KO.md 편집 (각 2곳, 1:1 유지)**

**README.md (a) Version schemes 문구:**

old:
```
M1 ships SemVer; CalVer/HeadVer are on the roadmap.
```
new:
```
SemVer, CalVer and HeadVer are all supported; date/week/counter arithmetic
is handled by `next-version.py` (deterministic, `--today`-injectable).
```

**README.md (b) 로드맵:**

old:
```
- **M2 (current)** — monorepo: fixed/independent strategies, changed-package
  detection, `{pkg}@{ver}` tag namespaces, dependency propagation
- **M3** — release trains (CalVer/HeadVer), hotfix flow, release-PR mode for
  protected branches, counter pre-releases (`-rc.N`), CHANGELOG backfill,
  `changelog.d/` fragments
```
new:
```
- **M2 (shipped)** — monorepo: fixed/independent strategies, changed-package
  detection, `{pkg}@{ver}` tag namespaces, dependency propagation
- **M3a (current)** — version schemes: CalVer/HeadVer arithmetic, counter
  pre-releases (`-rc.N`), moving major tags
- **M3b** — release paths: release-PR mode for protected branches, hotfix flow
- **M3c** — release trains (dual-scheme monorepos), CHANGELOG backfill,
  `changelog.d/` fragments, tag-message notes
```

**README_KO.md (a):**

old:
```
M1은 SemVer를 지원합니다; CalVer/HeadVer는 로드맵에 있습니다.
```
new:
```
SemVer, CalVer, HeadVer를 모두 지원합니다; 날짜/주차/카운터 산술은
`next-version.py`가 결정론적으로 수행합니다(`--today` 주입 가능).
```

**README_KO.md (b):**

old:
```
- **M2 (현재)** — 모노레포: fixed/independent 전략, 변경 패키지 감지,
  `{pkg}@{ver}` 태그 네임스페이스, 의존성 전파
- **M3** — 릴리스 트레인(CalVer/HeadVer), hotfix 플로우, 보호 브랜치용
  릴리스 PR 모드, 카운터형 pre-release (`-rc.N`), CHANGELOG backfill,
  `changelog.d/` fragment
```
new:
```
- **M2 (완료)** — 모노레포: fixed/independent 전략, 변경 패키지 감지,
  `{pkg}@{ver}` 태그 네임스페이스, 의존성 전파
- **M3a (현재)** — 버전 체계: CalVer/HeadVer 산술, 카운터형 pre-release
  (`-rc.N`), moving major tag
- **M3b** — 릴리스 경로: 보호 브랜치용 릴리스 PR 모드, hotfix 플로우
- **M3c** — 릴리스 트레인(이중 체계 모노레포), CHANGELOG backfill,
  `changelog.d/` fragment, tag-message 노트
```

- [ ] **Step 5: 검증 후 커밋**

Run: `wc -l skills/init/SKILL.md` → 500 이하.
Run: `claude plugin validate . --strict` → 통과.
Run: `python3 -m unittest discover -s tests -v` → 전부 PASS (문서 변경만 — 골든 불변).
확인: README.md/README_KO.md 헤딩 수·표 행 수 1:1 유지(로드맵 항목 수는 양쪽 동일하게 5개).

```bash
git add skills/init/SKILL.md skills/init/references/version-schemes.md skills/init/references/prerelease-and-dev-channel.md README.md README_KO.md
git commit -m "feat: init 체계·counter·moving tag 질문 해제 + 문서 정합 (M3a)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 최종 검증 — 산술 사이클 e2e + 플러그인 검증

**Files:**
- Create: 없음 (검증 전용)

- [ ] **Step 1: 전체 테스트 + 플러그인 검증 + 골든 상태**

Run: `python3 -m unittest discover -s tests -v` → 전부 PASS.
Run: `claude plugin validate . --strict` → 통과.
Run: `git status --porcelain tests/golden` → 출력 없음(골든 6종 커밋 상태 그대로).
Run: `wc -l skills/init/assets/skills/release/SKILL.md skills/init/assets/skills/release-monorepo/SKILL.md` → 소스 기준 각각 여유 확인(렌더 ≤149는 테스트가 보장).

- [ ] **Step 2: 산술 사이클 e2e (결정론 — --today 고정)**

```bash
NV=skills/init/assets/scripts/next-version.py
set -e
# CalVer 사이클: 첫 릴리스 → 같은 달 재릴리스 → 달 경계
[ "$(python3 $NV --current 0.1.0    --scheme calver --pattern YYYY.MM.MICRO --today 2026-07-10)" = "2026.7.0" ]
[ "$(python3 $NV --current 2026.7.0 --scheme calver --pattern YYYY.MM.MICRO --today 2026-07-10)" = "2026.7.1" ]
[ "$(python3 $NV --current 2026.7.1 --scheme calver --pattern YYYY.MM.MICRO --today 2026-08-01)" = "2026.8.0" ]
# HeadVer: 주차 산출 + ISO 연도 경계 + build 무리셋
[ "$(python3 $NV --current 1.2627.4 --scheme headver --head 1 --today 2026-07-10)" = "1.2628.5" ]
[ "$(python3 $NV --current 2.2652.9 --scheme headver --head 2 --today 2027-01-01)" = "2.2653.10" ]
# counter 사이클: 발행 → 반복 → 승격
[ "$(python3 $NV --current 1.3.0        --bump minor --prerelease rc)" = "1.4.0-rc.1" ]
[ "$(python3 $NV --current 1.4.0-rc.1   --prerelease rc)"              = "1.4.0-rc.2" ]
[ "$(python3 $NV --current 1.4.0-rc.2   --release)"                    = "1.4.0" ]
echo m3a-e2e-ok
```

Expected: `m3a-e2e-ok`. 실패 시 해당 태스크로 돌아가 수정 후 재실행.

- [ ] **Step 3: 렌더 산출물 스팟 확인**

```bash
grep -q "moving major tag" tests/golden/rc-library/expected/.claude/skills/release/SKILL.md && echo rc-golden-ok
grep -q "다음 버전 산출" tests/golden/calver-app/expected/.claude/skills/release/SKILL.md && echo calver-golden-ok
grep -q "calver/headver" tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md && echo mono-prose-ok
```

Expected: 세 줄 모두 출력.

- [ ] **Step 4: 마무리 확인 (수정 사항 있었던 경우만 커밋)**

```bash
git status --porcelain   # 비어 있으면 커밋 불필요
```

---

## 수동 e2e 검증 체크리스트 (구현 완료 후 사용자와 함께)

1. **CalVer 앱 init**: 샘플 npm 앱에서 `claude --plugin-dir <플러그인>` → init → 번들 2에서 CalVer 선택(패턴 `YYYY.MM.MICRO` 질문) → 생성 → "릴리스해줘" → "다음 버전 산출" 흐름으로 `2026.7.0` 형태가 나오는지(오늘 날짜 기준), 같은 달 재릴리스 시 MICRO 증가 확인.
2. **counter 라이브러리**: 샘플 Gradle 라이브러리에서 counter(rc) 선택 → "rc 릴리스해줘" → `X.Y.Z-rc.1` 태그 + GitHub Release `--prerelease` → "rc 하나 더" → rc.2 → "정식 릴리스" → `X.Y.Z` 승격 + (movingMajorTag면) `v<major>` force-push 경고·개별 확인이 뜨는지.
3. **HeadVer 앱**: HeadVer 선택(head 번호 질문 → scheme.pattern 저장) → 릴리스 → `{head}.{yearweek}.{build}` 형태 확인.
4. **재init**: 기존 semver config에서 scheme을 calver로 바꾸고 재init → 질문 없는 재렌더로 "다음 버전 산출" 변형이 나오는지.

## M3a 완료 기준 매핑 (스펙 §12 M3 중 M3a 분)

| 완료 기준 | 검증 위치 |
|---|---|
| CalVer/HeadVer(next-version) 벡터 테스트 | Task 1 + Task 6 Step 2 |
| 불변 카운터 pre-release 릴리스 플로우(+ `--prerelease` 플래그) | Task 1(산술)·Task 2·3(스킬) + 수동 2 |
| moving major tag 실구현 | Task 2·3 + 골든 rc-library + 수동 2 |
| init 질문 해제·문서 정합 | Task 5 + 수동 1~3 |

M3b(릴리스 PR·hotfix)·M3c(트레인·backfill·fragment·tag-message)는 별도 계획으로 이어진다 — M3c는 이 계획의 CalVer 산술에 의존한다.
