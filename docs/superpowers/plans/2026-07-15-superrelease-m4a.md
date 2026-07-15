# superrelease M4a 정확성 픽스 팩 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-07-15 전면 리뷰에서 확정된 실버그 6건(+부수 마감 2건)을 고치고, 버그가 살아남은 원인인 골든/음성 테스트 사각을 함께 닫는다.

**Architecture:** 스펙 [2026-07-15-superrelease-m4a-correctness-design.md](../specs/2026-07-15-superrelease-m4a-correctness-design.md)의 A(자산 스크립트 3종 버그 픽스) / B(생성 스킬 프로즈 수정) / C(validate_config 규칙 추가) / D(골든 4종 신설 + 음성 테스트 + 결정론 하드닝)를 태스크 9개로 구현한다. 결정론 하드닝을 맨 앞에 두어 이후 모든 골든 재생성이 안전하게 하고, validate 규칙(T5) 다음에 골든 신설(T6), 그 뒤 스킬 프로즈 수정(T7~T9)이 신설 골든까지 함께 핀한다.

**Tech Stack:** Python 3.9+ 표준 라이브러리만(스크립트·render), unittest(pytest 금지), 동결 template dialect.

**베이스:** 브랜치 `feat/superrelease-m4a` (스펙 커밋 `ea582c7`, main `2bba1e7`에서 분기).

## Global Constraints

- 전체 테스트: 레포 루트에서 `python3 -m unittest discover -s tests -q`. 단일 모듈: `cd tests && python3 -m unittest <모듈명> -v; cd ..` — **dotted 형식(`python3 -m unittest tests.<mod>`)은 `ModuleNotFoundError: helpers`로 실패하니 금지.** pytest는 설치돼 있지 않다.
- template dialect(`{{path}}`, `{{#if}}`/`{{#if x == "lit"}}`/`{{else}}`, `{{#unless}}`, `{{#each}}`)는 **동결** — 엔진 확장 금지, 스킬은 이 문법만 조합. 단일 중괄호(`v{version}`)는 리터럴 보존.
- **바이트 불변**: 스킬에 조건 블록을 추가할 때 개행을 `{{#if}}` **안**에 두어, 그 기능이 없는 config에서 0바이트로 collapse해야 한다.
- **골든 규율**: 자산(스킬·템플릿·스크립트)을 바꾸면 `python3 tests/update_golden.py`로 재생성하고 `git status --porcelain tests/golden` 출력이 **그 태스크의 "예상 골든 diff"에 명시된 파일만** 보여야 한다. 그 외 파일이 바뀌면 회귀 — 원인을 찾아 고쳐라.
- 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄. 스크립트는 stdlib만, exit `0`(성공)/`1`(검증 실패)/`2`(사용법·config 오류).
- 코드·에러 메시지 영어 / 생성 스킬 프로즈·주석성 문구 한국어.
- 생성물 자립성: `.superrelease/`·`.claude/` 상대 경로만, 플러그인 경로 참조 금지.
- 커밋 메시지는 Conventional Commits 한국어 + `(M4a)` 접미. 각 커밋 뒤 전체 스위트 green 확인.

---

### Task 1: 골든 렌더 결정론 하드닝 (GIT_CEILING_DIRECTORIES)

render.py의 `project_name()`은 `git -C <repo> remote get-url origin`으로 이름을 얻는데, 골든 렌더가 도는 TemporaryDirectory가 우연히 origin 있는 git 레포 **아래**면 project.name이 그 레포 이름으로 오염된다(골든 전체 불일치). 렌더 서브프로세스에 `GIT_CEILING_DIRECTORIES=<tmp>`를 주입해 tmp 위로의 git 탐색을 차단한다.

**Files:**
- Modify: `tests/test_golden.py`
- Modify: `tests/update_golden.py`

**Interfaces:**
- Consumes: `render.py`의 `project_name()` 폴백(원격 조회 실패 시 디렉터리명) — 기존 동작, 무변경.
- Produces: `test_golden.render_case`·`update_golden.render_into`의 서브프로세스 env 규약. 이후 태스크의 모든 `update_golden.py` 실행이 이 결정론 위에서 돈다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_golden.py`의 `GoldenRenderTest` 클래스에 **메서드로** 추가(서브클래스로 만들면 상속된 스냅샷 테스트가 이중 실행되므로 금지), 상단 import에 `os` 추가:

```python
    def test_project_name_ignores_enclosing_git_repo(self):
        # tmp 루트가 origin 있는 git 레포여도 project.name은 디렉터리명이어야 한다
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", str(tmp)], check=True)
            subprocess.run(["git", "-C", str(tmp), "remote", "add", "origin",
                            "https://example.com/enclosing-name.git"], check=True)
            repo = self.render_case("gradle-app", GOLDEN["gradle-app"], tmp)
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("gradle-app", skill)
            self.assertNotIn("enclosing-name", skill)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_golden -v; cd ..`
Expected: `test_project_name_ignores_enclosing_git_repo` FAIL — skill에 `enclosing-name`이 렌더됨.

- [ ] **Step 3: 구현** — `tests/test_golden.py`의 `render_case` 내 `subprocess.run(...)`에 env 추가 (상단에 `import os` 필요):

```python
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SCRIPTS / "render.py"),
             "--config", str(repo / ".superrelease" / "config.json"),
             "--assets", str(ASSETS), "--repo", str(repo), "--now", NOW],
            capture_output=True, text=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tmp))})
```

`tests/update_golden.py`의 `render_into` 내 `subprocess.run(...)`도 동일하게 (상단에 `import os` 추가, `tmp`는 함수 내 TemporaryDirectory 경로):

```python
        proc = subprocess.run(
            [sys.executable, str(PLUGIN_SCRIPTS / "render.py"),
             "--config", str(repo / ".superrelease" / "config.json"),
             "--assets", str(ASSETS), "--repo", str(repo), "--now", NOW],
            capture_output=True, text=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": tmp})
```

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `cd tests && python3 -m unittest test_golden -v; cd ..` → PASS
Run: `python3 -m unittest discover -s tests -q` → OK (173+1)

- [ ] **Step 5: 골든 무변화 확인 후 커밋** — `python3 tests/update_golden.py && git status --porcelain tests/golden` 출력이 **비어 있어야** 한다(결정론 하드닝은 산출물 무변경).

```bash
git add tests/test_golden.py tests/update_golden.py
git commit -m "test: 골든 렌더 결정론 — GIT_CEILING_DIRECTORIES로 TMPDIR git walk-up 차단 (M4a)"
```

---

### Task 2: version.py regex 다중 캡처 그룹 가드

alternation+다중 그룹 패턴에서 `set`이 파일을 조용히 오손한다(뒤 매치가 그룹 2+에 바인딩 → `m.start(1) == -1` 슬라이스 오손, exit 0). 컴파일 시점에 `re.compile(p).groups != 1`이면 exit 2로 막고, read/set 모두 "그룹 1이 참여한 매치"만 다루도록 통일한다.

**Files:**
- Modify: `skills/init/assets/scripts/version.py:124-131` (read_location regex 분기), `:188-199` (set_location regex 분기), `:89` 근처(헬퍼 추가)
- Test: `tests/test_version.py`

**Interfaces:**
- Consumes: 없음 (독립).
- Produces: `location_pattern(path, pattern) -> re.Pattern` (모듈 내부 헬퍼, exit 2 부작용). CLI 계약 변화: 다중 그룹 regex → 항상 exit 2 (기존: get은 대체로 exit 2, set은 가끔 오손+exit 0).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_version.py` 끝(기존 클래스들 뒤)에 추가:

```python
class RegexGuardTest(VersionTestBase):
    def test_multi_group_pattern_set_exits_2_without_writing(self):
        content = "A-1.0.0 and B-1.0.0 end\n"
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex",
              "pattern": r"A-(\d+\.\d+\.\d+)|B-(\d+\.\d+\.\d+)"}],
            {"V.md": content})
        r = run_script(vp(repo), "set", "2.0.0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one capture group", r.stderr)
        self.assertEqual((Path(repo) / "V.md").read_text(encoding="utf-8"), content)

    def test_multi_group_pattern_get_exits_2(self):
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex", "pattern": r"(a)-(\d+)"}],
            {"V.md": "a-1\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("exactly one capture group", r.stderr)

    def test_invalid_regex_exits_2(self):
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex", "pattern": r"ver-([0-9]+"}],
            {"V.md": "ver-1\n"})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid pattern", r.stderr)

    def test_alternation_single_group_replaces_participating_matches(self):
        # 그룹이 1개면 비참여 alternation 가지는 건너뛰고 참여 매치만 치환한다
        repo = self.repo_with(
            [{"file": "V.md", "type": "regex",
              "pattern": r"version-([0-9][0-9.]*)-blue|version_badge"}],
            {"V.md": "version_badge\nversion-1.2.3-blue\n"})
        r = run_script(vp(repo), "set", "1.2.4")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (Path(repo) / "V.md").read_text(encoding="utf-8")
        self.assertIn("version-1.2.4-blue", text)
        self.assertIn("version_badge\n", text)
        self.assertEqual(run_script(vp(repo), "get").stdout.strip(), "1.2.4")
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_version -v; cd ..`
Expected: `test_multi_group_pattern_set_exits_2_without_writing` FAIL(returncode 0, 파일 오손), `test_alternation_single_group_replaces_participating_matches` FAIL(get이 exit 1 — 첫 매치 비참여), `test_invalid_regex_exits_2`는 현재 traceback으로 비-2 종료라면 FAIL.

- [ ] **Step 3: 구현** — `skills/init/assets/scripts/version.py`. `properties_pattern` 함수(:88-89) 아래에 헬퍼 추가:

```python
def location_pattern(path, pattern):
    try:
        pat = re.compile(pattern, re.MULTILINE)
    except re.error as e:
        fail(str(path) + ": invalid pattern '" + pattern + "': " + str(e), 2)
    if pat.groups != 1:
        fail(str(path) + ": pattern '" + pattern
             + "' must have exactly one capture group, found " + str(pat.groups), 2)
    return pat
```

`read_location`의 regex 분기(:124-131) 전체를 교체:

```python
    if t == "regex":
        pat = location_pattern(path, loc["pattern"])
        matches = [m for m in pat.finditer(text) if m.start(1) != -1]
        if not matches:
            fail(str(path) + ": pattern '" + loc["pattern"] + "' not found (needs one capture group)", 1)
        return matches[0].group(1)
```

`set_location`의 regex 분기(:188-199) 전체를 교체:

```python
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
```

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `cd tests && python3 -m unittest test_version -v; cd ..` → 전부 PASS
Run: `python3 -m unittest discover -s tests -q` → **test_golden FAIL이 정상** (골든의 verbatim 스크립트 사본 불일치) — Step 5로.

- [ ] **Step 5: 골든 재생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `tests/golden/*/expected/.superrelease/scripts/version.py` **만** 변경(14개 트리 전부). 다른 파일이 보이면 회귀.
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 6: 커밋**

```bash
git add skills/init/assets/scripts/version.py tests/test_version.py tests/golden
git commit -m "fix: version.py regex 다중 캡처 그룹 오손 → 컴파일 시점 exit 2 가드 (M4a)"
```

---

### Task 3: changed-packages.py 3건 — versionsort·rename·tag.enabled 기본값

① pre-release 태그(`a@1.0.1-rc.1`)가 정식(`a@1.0.1`)보다 anchor로 잡힘 → `versionsort.suffix=-` ② scope 밖으로 `git mv`된 파일의 삭제를 못 잡음 → `--no-renames` ③ `tag.enabled` 키 생략 시 tagless 취급(render.py는 true 취급) → `get("enabled", True)` 통일.

**Files:**
- Modify: `skills/init/assets/scripts/changed-packages.py:58` (latest_tag), `:72` (resolve_anchor), `:83` (changed_for)
- Test: `tests/test_changed_packages.py`

**Interfaces:**
- Consumes: 없음.
- Produces: `--json` 스키마 무변경. anchor 해석 규약 변화: 정식 태그 우선(rc 아래로), rename은 삭제+추가로 계상, `enabled` 생략 = tagged.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_changed_packages.py`의 `ChangedPackagesTest` 클래스에 메서드 3개 추가:

```python
    def test_prerelease_tag_not_preferred_over_final(self):
        # a@1.0.1-rc.1이 a@1.0.1(정식)보다 anchor로 선호되면 안 된다
        g(self.repo, "tag", "-a", "a@1.0.1-rc.1", "-m", "x")
        g(self.repo, "tag", "-a", "a@1.0.1", "-m", "x")
        by = self.scopes_by_name(self.run_cp("--scope", "a", "--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@1.0.1")

    def test_rename_out_of_scope_counts_as_change(self):
        g(self.repo, "tag", "-a", "b@0.1.0", "-m", "x")
        write(self.repo / "packages" / "a" / "util.js", "1\n")
        g(self.repo, "add", "-A")
        g(self.repo, "commit", "-qm", "feat: a util (#2)")
        g(self.repo, "tag", "-a", "a@0.2.0", "-m", "x")
        g(self.repo, "mv", "packages/a/util.js", "packages/b/util.js")
        g(self.repo, "commit", "-qm", "refactor: move util (#3)")
        by = self.scopes_by_name(self.run_cp("--json").stdout)
        self.assertTrue(by["a"]["hasChanges"])   # 원 위치 삭제도 a의 변경이다
        self.assertIn("packages/a/util.js", by["a"]["changed"])
        self.assertTrue(by["b"]["hasChanges"])

    def test_enabled_key_omitted_treated_as_tagged(self):
        cfg = monorepo_config()
        for s in cfg["scopes"]:
            del s["tag"]["enabled"]
        (self.repo / ".superrelease" / "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        g(self.repo, "tag", "-a", "a@0.1.0", "-m", "x")
        by = self.scopes_by_name(self.run_cp("--scope", "a", "--json").stdout)
        self.assertEqual(by["a"]["anchor"], "a@0.1.0")
        self.assertEqual(by["a"]["anchorType"], "tag")
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_changed_packages -v; cd ..`
Expected: 3개 모두 FAIL — anchor가 `a@1.0.1-rc.1` / a의 changed에 원 경로 부재 / anchorType이 `"none"`.

- [ ] **Step 3: 구현** — `skills/init/assets/scripts/changed-packages.py` 세 줄 수정:

`latest_tag`(:58): `git("tag", "--list", glob, "--sort=-v:refname")` →

```python
    lines = [l for l in git("-c", "versionsort.suffix=-", "tag", "--list", glob,
                            "--sort=-v:refname").splitlines()
             if l.strip()]
```

`resolve_anchor`(:72): `if tag_cfg.get("enabled"):` → `if tag_cfg.get("enabled", True):`

`changed_for`(:83): `out = git("diff", "--name-only", anchor + "..HEAD")` → `out = git("diff", "--name-only", "--no-renames", anchor + "..HEAD")`

- [ ] **Step 4: 통과 + 전체 스위트 (골든 불일치 예상)**

Run: `cd tests && python3 -m unittest test_changed_packages -v; cd ..` → PASS
Run: `python3 -m unittest discover -s tests -q` → test_golden FAIL 정상.

- [ ] **Step 5: 골든 재생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `pnpm-monorepo`·`train-monorepo`·`backfill-monorepo` 세 트리의 `expected/.superrelease/scripts/changed-packages.py` **만**.
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 6: 커밋**

```bash
git add skills/init/assets/scripts/changed-packages.py tests/test_changed_packages.py tests/golden
git commit -m "fix: changed-packages versionsort·rename·tag.enabled 기본값 교정 (M4a)"
```

---

### Task 4: next-version.py — MICRO 없는 CalVer 동일 기간 재릴리스 exit 1

`YYYY.0M`처럼 MICRO 없는 패턴은 같은 기간 재계산 시 현재 버전을 그대로 exit 0으로 반환한다(tagless scope는 가드 없이 동일 버전 재릴리스). 결과 == 현재 버전이면 exit 1.

**Files:**
- Modify: `skills/init/assets/scripts/next-version.py:145-146` (calver_next)
- Test: `tests/test_next_version.py`

**Interfaces:**
- Consumes: 없음.
- Produces: CLI 계약 변화 — MICRO 없는 패턴에서 동일 기간이면 exit 1 + stderr에 `MICRO` 언급. MICRO 있는 패턴은 무영향(카운터 증가).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_next_version.py`의 CalVer 관련 클래스가 있으면 그 옆에, 없으면 `PureModeTest`에 추가:

```python
    def test_calver_no_micro_same_period_exits_1(self):
        r = out("--current", "2026.07", "--scheme", "calver",
                "--pattern", "YYYY.0M", "--today", "2026-07-15")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MICRO", r.stderr)

    def test_calver_no_micro_new_period_ok(self):
        r = out("--current", "2026.07", "--scheme", "calver",
                "--pattern", "YYYY.0M", "--today", "2026-08-01")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "2026.08")
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_next_version -v; cd ..`
Expected: `test_calver_no_micro_same_period_exits_1` FAIL(returncode 0, stdout `2026.07`). 두 번째는 이미 PASS일 수 있음(현행도 새 기간은 정상) — 그대로 둔다(회귀 핀).

- [ ] **Step 3: 구현** — `calver_next`의 `if None not in pieces: return "".join(pieces)`(:145-146)를 교체:

```python
    if None not in pieces:
        result = "".join(pieces)
        if result == (current or "").strip():
            fail("calver pattern '" + pattern + "' has no MICRO token and the "
                 "computed version equals the current version (" + result
                 + "); a same-period re-release needs MICRO in the pattern", 1)
        return result
```

- [ ] **Step 4: 통과 + 전체 스위트 (골든 불일치 예상)**

Run: `cd tests && python3 -m unittest test_next_version -v; cd ..` → PASS
Run: `python3 -m unittest discover -s tests -q` → test_golden FAIL 정상.

- [ ] **Step 5: 골든 재생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 14개 트리 전부의 `expected/.superrelease/scripts/next-version.py` **만**.
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 6: 커밋**

```bash
git add skills/init/assets/scripts/next-version.py tests/test_next_version.py tests/golden
git commit -m "fix: next-version MICRO 없는 CalVer 동일 기간 재릴리스 exit 1 (M4a)"
```

---

### Task 5: validate_config 강화 — 규칙 5종 + 필드별 음성 테스트

렌더는 통과하지만 릴리스 시점에 반드시 실패하는 config를 init 시점에 거부한다. render 엔진(토크나이저·파서·파이프라인)은 무변경, `validate_config`에 규칙만 추가.

**Files:**
- Modify: `skills/init/scripts/render.py:177-253` (validate_config — `return problems` 직전에 블록 추가)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Consumes: 없음.
- Produces: 에러 메시지 규약(후속 태스크·문서가 참조) — scheme enum: `scheme.type must be "semver", "calver" or "headver"` / non-semver 조합: `preRelease.style` · `postRelease.bump` 포함 / location: `versionLocations[j].<field>` 프리픽스 / github: `github.release requires ...` 및 `"github-release" requires github.release`. **Task 6의 tagless-app 골든 config는 이 규칙에 맞춰 `github.release: false`여야 한다.**

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_render_pipeline.py`의 `PipelineTest` 클래스에 추가:

```python
    def test_unknown_scheme_type_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["scheme"] = {"type": "sequential", "pattern": None}
        cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
        cfg["scopes"][0]["postRelease"] = {"bump": "none"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("scheme.type", r.stderr)
        self.assertIn("sequential", r.stderr)

    def test_calver_with_mutable_prerelease_and_next_snapshot_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
        # scope_config 기본값이 preRelease mutable + postRelease next-snapshot
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("preRelease.style", r.stderr)
        self.assertIn("postRelease.bump", r.stderr)

    def test_headver_with_next_snapshot_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["scheme"] = {"type": "headver", "pattern": "1"}
        cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
        self.write_config(cfg)  # postRelease는 기본 next-snapshot 유지
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("postRelease.bump", r.stderr)

    def test_location_missing_required_key_exits_1(self):
        cfg = scope_config([{"file": "package.json", "type": "json-path"}])
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("versionLocations[0].path", r.stderr)

    def test_location_unknown_type_exits_1(self):
        cfg = scope_config([{"file": "x.yaml", "type": "yaml-path", "path": "v"}])
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("versionLocations[0].type", r.stderr)

    def test_location_regex_two_groups_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "(a)-(b)"}])
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("exactly one capture group", r.stderr)

    def test_location_regex_invalid_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1"}])
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a valid regex", r.stderr)

    def test_github_release_with_tagless_scope_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["tag"]["enabled"] = False
        cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
        self.write_config(cfg)  # github.release 기본 true
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("github.release", r.stderr)

    def test_github_release_dest_without_github_release_exits_1(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["github"]["release"] = False
        self.write_config(cfg)  # destinations 기본에 github-release 포함
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("github-release", r.stderr)

    def test_required_fields_reported_individually(self):
        # 기존 통짜 빈 config 테스트를 보완 — 규칙별 단독 케이스
        cases = [
            (lambda c: c["scopes"][0].pop("name"), "scopes[0].name"),
            (lambda c: c["scopes"][0].pop("path"), "scopes[0].path"),
            (lambda c: c["scopes"][0].update(scheme={}), "scheme.type is required"),
            (lambda c: c["scopes"][0].update(versionLocations=[]),
             "versionLocations is required"),
            (lambda c: c["repo"].pop("releasePath"), "repo.releasePath"),
            (lambda c: c["superrelease"].pop("configVersion"), "configVersion"),
        ]
        for mutate, expect in cases:
            with self.subTest(expect=expect):
                cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
                mutate(cfg)
                self.write_config(cfg)
                r = self.render()
                self.assertEqual(r.returncode, 1)
                self.assertIn(expect, r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v; cd ..`
Expected: 신규 9개 중 `test_required_fields_reported_individually`만 PASS(기존 규칙), 나머지는 returncode 0으로 FAIL.

- [ ] **Step 3: 구현** — `skills/init/scripts/render.py`의 `validate_config`에서 기존 sinks 루프(`for i, s in enumerate(scopes or []): ... "fragment" ...`) 뒤, `return problems` 직전에 추가:

```python
    for i, s in enumerate(scopes or []):
        scheme_type = (s.get("scheme") or {}).get("type")
        if scheme_type and scheme_type not in ("semver", "calver", "headver"):
            problems.append('scopes[{}].scheme.type must be "semver", "calver" or '
                            '"headver" (got "{}"; sequential is not supported yet)'
                            .format(i, scheme_type))
        if scheme_type in ("calver", "headver"):
            if (s.get("preRelease") or {}).get("style", "none") not in (None, "none"):
                problems.append('scopes[{}]: preRelease.style must be "none" for '
                                "calver/headver schemes (qualifier arithmetic is "
                                "semver-only)".format(i))
            if (s.get("postRelease") or {}).get("bump", "none") not in (None, "none"):
                problems.append('scopes[{}]: postRelease.bump must be "none" for '
                                "calver/headver schemes (next-snapshot is "
                                "semver-only)".format(i))
        for j, loc in enumerate(s.get("versionLocations") or []):
            prefix = "scopes[{}].versionLocations[{}]".format(i, j)
            if not isinstance(loc, dict) or not loc.get("file"):
                problems.append(prefix + ".file is required")
                continue
            ltype = loc.get("type")
            if ltype not in ("properties-key", "json-path", "regex"):
                problems.append(prefix + '.type must be "properties-key", '
                                '"json-path" or "regex" (got "{}")'.format(ltype))
            elif ltype == "properties-key" and not loc.get("key"):
                problems.append(prefix + '.key is required for type "properties-key"')
            elif ltype == "json-path" and not loc.get("path"):
                problems.append(prefix + '.path is required for type "json-path"')
            elif ltype == "regex":
                pattern = loc.get("pattern")
                if not pattern:
                    problems.append(prefix + '.pattern is required for type "regex"')
                else:
                    try:
                        if re.compile(pattern).groups != 1:
                            problems.append(prefix + ".pattern must have exactly "
                                            "one capture group")
                    except re.error as e:
                        problems.append(prefix + ".pattern is not a valid regex: "
                                        + str(e))
    gh_cfg = config.get("github") or {}
    for i, s in enumerate(scopes or []):
        tag_enabled = (s.get("tag") or {}).get("enabled", True)
        dests = (s.get("notes") or {}).get("destinations") or []
        if gh_cfg.get("release") and not tag_enabled:
            problems.append("scopes[{}]: github.release requires tag.enabled "
                            "(GitHub Releases are tag-based) — disable "
                            "github.release or enable tags".format(i))
        if not gh_cfg.get("release") and "github-release" in dests:
            problems.append('scopes[{}]: notes destination "github-release" '
                            "requires github.release: true".format(i))
    return problems
```

- [ ] **Step 4: 통과 + 전체 스위트**

Run: `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` → 전부 PASS
Run: `python3 -m unittest discover -s tests -q` → OK — render.py는 골든 복사 대상이 아니라 골든 무영향. 기존 골든 config 14종이 새 규칙을 전부 통과하는지 이 실행이 함께 증명한다.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: validate_config 강화 — scheme enum·non-semver 조합·location 검증·github.release↔태그 정합 (M4a)"
```

---

### Task 6: 골든 4종 신설 — headver·fixed 모노레포·tagless·모노레포 release-pr

커버리지 0이던 렌더 분기 4종을 스냅샷으로 고정한다. 이후 태스크(T7~T9)의 스킬 수정 diff가 이 트리들에도 함께 핀된다.

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/{headver-app,fixed-monorepo,tagless-app,monorepo-release-pr}/expected/**` (update_golden.py가 생성)

**Interfaces:**
- Consumes: Task 5의 validate 규칙 — headver-app은 preRelease/postRelease none 필수, tagless-app은 github.release false 필수.
- Produces: `GOLDEN` 딕셔너리 4항목 추가(총 18) — 이후 태스크의 "예상 골든 diff"에 이 트리들이 포함된다.

- [ ] **Step 1: config 함수 추가** — `tests/golden_configs.py`의 `train_monorepo()` 뒤에:

```python
def headver_app():
    # headver + pre/post none (validate가 non-semver 조합을 강제)
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["scheme"] = {"type": "headver", "pattern": "1"}
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def fixed_monorepo():
    # fixed = 단일 root scope에 전 패키지 버전 파일 — 흐름은 단일 레포와 동일
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"},
         {"file": "packages/a/package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = "fixed"
    return cfg


def tagless_app():
    # tagless: anchor.value가 범위 기준. GitHub Release는 태그 필수라 비활성
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["scopes"][0]["tag"] = {"enabled": False, "format": "v{version}",
                               "annotated": False, "signed": False,
                               "movingMajorTag": False}
    cfg["scopes"][0]["anchor"] = {"type": "ref", "value": None}
    cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
    cfg["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
    return cfg


def monorepo_release_pr():
    # independent 모노레포 × release-pr — release-monorepo의 PR 분기 고정
    cfg = monorepo_config()
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg
```

`GOLDEN` 딕셔너리에 4항목 추가:

```python
GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app, "train-monorepo": train_monorepo,
          "backfill-monorepo": backfill_monorepo,
          "backfill-release-pr": backfill_release_pr,
          "headver-app": headver_app, "fixed-monorepo": fixed_monorepo,
          "tagless-app": tagless_app, "monorepo-release-pr": monorepo_release_pr}
```

- [ ] **Step 2: 골든 생성 전 실패 확인**

Run: `cd tests && python3 -m unittest test_golden -v; cd ..`
Expected: FAIL — `golden missing — run: python3 tests/update_golden.py` (4개 신규 트리).

- [ ] **Step 3: 골든 생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 신규 4개 디렉터리(`headver-app`, `fixed-monorepo`, `tagless-app`, `monorepo-release-pr`)의 untracked 파일 **만**. 기존 14개 트리는 무변경.

- [ ] **Step 4: 신설 트리 내용 스모크** — 다음을 눈으로 확인(자동 검증은 test_golden이 함):
  - `tagless-app/expected/.claude/skills/release/SKILL.md`에 `gh release create` **없음**, `anchor.value` 갱신 프로즈(§8) 있음, `.github/release.yml` 파일 없음.
  - `headver-app/.../release/SKILL.md`에 `다음 버전 산출` 있음, `bump 제안` 없음.
  - `fixed-monorepo/.../release/SKILL.md`가 단일 변형(제목에 `모노레포` 없음), `changed-packages.py` 파일 없음.
  - `monorepo-release-pr/.../release/SKILL.md`(모노레포 변형)에 `gh pr create`·`release-pr-body.md` 있음.

- [ ] **Step 5: 전체 스위트 + 커밋**

Run: `python3 -m unittest discover -s tests -q` → OK

```bash
git add tests/golden_configs.py tests/golden
git commit -m "test: 골든 4종 신설 — headver·fixed 모노레포·tagless·모노레포 release-pr (M4a)"
```

---

### Task 7: preflight 중단 감지 재정의 + release-pr 중복 PR 가드 (3개 스킬)

preflight의 중단 상태 조건을 "**bare 릴리스 버전인데 그 태그가 없으면**"으로 재정의(mutable 수식어 상태는 정상 명시, tagless는 게이트로 제외), release-pr 레포에는 "열린 `release/*` PR 확인" 항목을 추가하고 재개 확인 명령을 브랜치명 기반으로 바꾼다. github.release 항목의 개행을 `{{#if}}` 안으로 옮기는 개행 위생도 함께(렌더 결과는 true config에서 바이트 동일).

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md:23-24,77`
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md:30-31,75`
- Modify: `skills/init/assets/skills/release-train/SKILL.md:24-25,57`
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: 없음 (프로즈 전용).
- Produces: 렌더 산출물의 preflight 문구 — T8·T9의 골든 diff 검증이 이 문구를 전제.

- [ ] **Step 1: 실패하는 렌더 단위 테스트 작성** — `tests/test_assets.py`의 `SkillAssetsTest`에:

```python
    def test_release_skill_stall_detection_mutable_exception(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 mutable SNAPSHOT
        self.assertIn("중단 상태 감지", out)
        self.assertIn("정상 개발 상태", out)
        self.assertIn("`-SNAPSHOT` 수식어", out)

    def test_release_skill_stall_detection_counter_has_no_mutable_clause(self):
        ctx = base_ctx()
        ctx["scope"]["preRelease"] = {"style": "counter", "qualifier": "rc"}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("중단 상태 감지", out)
        self.assertNotIn("정상 개발 상태", out)

    def test_release_skill_tagless_drops_stall_detection(self):
        ctx = base_ctx()
        ctx["scope"]["tag"]["enabled"] = False
        ctx["scope"]["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("중단 상태 감지", out)

    def test_release_skill_release_pr_open_pr_guard(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out)
        self.assertIn("gh pr list --state open", out)
        self.assertIn("gh pr view release/", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_direct_push_has_no_open_pr_guard(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertNotIn("열린 릴리스 PR", out)
        self.assertNotIn("gh pr list", out)
```

`MonorepoAssetsTest`에:

```python
    def test_release_monorepo_stall_detection_and_open_pr_guard(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("bare 릴리스 버전", out)
        self.assertNotIn("열린 릴리스 PR", out)
        ctx = mono_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out_pr = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out_pr)
        self.assertIn("gh pr view", out_pr)
        self.assertLessEqual(len(out_pr.splitlines()), 149)
```

`ReleaseTrainAssetsTest`에:

```python
    def test_release_train_stall_detection_and_open_pr_guard(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("bare 릴리스 버전", out)
        self.assertNotIn("열린 릴리스 PR", out)
        ctx = train_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out_pr = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("열린 릴리스 PR", out_pr)
        self.assertIn("gh pr view release/train-", out_pr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..`
Expected: 신규 테스트 전부 FAIL(현행 프로즈에 해당 문구 없음). 단 `test_release_skill_direct_push_has_no_open_pr_guard`는 PASS(회귀 핀).

- [ ] **Step 3: release/SKILL.md 수정** — 라인 23-25(**item 5·item 6·뒤따르는 빈 줄**)를 다음으로 교체. 신규 블록 마지막 `{{/if}}` 줄의 개행이 기존 빈 줄 역할을 하므로, 빈 줄을 남겨두면 collapse 시 빈 줄이 두 개가 된다:

기존 (빈 줄 포함 세 줄):

```
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
6. 중단 상태 감지: 파일 버전(수식어 제외)이 마지막 릴리스 태그보다 높은데 그 버전의 태그가 없으면 이전 릴리스가 중단된 것이다 — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.

```

신규 (마지막 줄이 `{{/if}}` — 그 뒤에 바로 `실패 항목이 있으면` 줄이 온다):

```
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인
{{/if}}{{#if scope.tag.enabled}}6. 중단 상태 감지: 마지막 릴리스 태그가 존재하고 파일 버전이 그보다 높은데 **파일 버전 그대로의 태그가 없으면** 이전 릴리스가 중단된 것이다{{#if scope.preRelease.style == "mutable"}} (단, 파일 버전에 `-{{scope.preRelease.qualifier}}` 수식어가 붙어 있으면 정상 개발 상태 — 중단 아님){{/if}} — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.
{{/if}}{{#if repo.releasePath == "release-pr"}}7. 열린 릴리스 PR 확인: `gh pr list --state open --json headRefName,url` 결과에 `release/`로 시작하는 head 브랜치의 PR이 있으면 이전 릴리스가 머지 대기 중이다 — 새 릴리스를 시작하지 말고 그 PR 상태를 보고하고 멈춰라(머지 후 재개는 6번이 잡는다).
{{/if}}
```

교체 후 기본 config 렌더가 기존과 같은 모양(항목 줄들 + 빈 줄 1개 + `실패 항목이...`)인지 확인하라.

라인 77(§6 release-pr 재개 문단)에서 `PR 머지 여부를 확인(\`gh pr view <PR번호> --json state\`)한 뒤` 를 다음으로 교체:

```
PR 머지 여부를 확인(`gh pr view release/<릴리스 버전> --json state,mergedAt` — head 브랜치명으로 조회)한 뒤
```

- [ ] **Step 4: release-monorepo/SKILL.md 수정** — 라인 30-32(**item 5·item 6·뒤따르는 빈 줄**)를 교체 (release와 동일한 빈 줄 소비 규칙 — 신규 마지막 `{{/if}}` 줄이 빈 줄 역할):

기존 (빈 줄 포함 세 줄):

```
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
6. scope별 중단 상태: 대상 scope의 파일 버전(수식어 제외)이 그 scope의 anchor 태그보다 높은데 해당 버전 태그가 없으면 이전 릴리스가 중단된 것 — resume/rollback 중 선택받아라.

```

신규 (마지막 줄이 `{{/if}}` — 그 뒤에 바로 `## 2. scope별 범위 산출` 줄이 온다):

```
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인
{{/if}}6. scope별 중단 상태: 대상 scope의 파일 버전이 개발 수식어(-SNAPSHOT류 mutable qualifier) 없는 **bare 릴리스 버전**이고 anchor 태그보다 높은데 그 버전의 태그가 없으면 이전 릴리스가 중단된 것 — resume/rollback 중 선택받아라. 태그를 쓰지 않는 scope는 이 검사를 건너뛴다.
{{#if repo.releasePath == "release-pr"}}7. 열린 릴리스 PR 확인: `gh pr list --state open --json headRefName,url` 결과에 `release/`로 시작하는 head 브랜치의 PR이 있으면 이전 릴리스가 머지 대기 중이다 — 새 릴리스를 시작하지 말고 그 PR 상태를 보고하고 멈춰라(머지 후 재개는 6번이 잡는다).
{{/if}}
```

라인 75(§7 release-pr 블록)에서 `머지 후 재개: 1단계 preflight 6의 중단 상태 감지가 잡는다 — PR 머지 확인 후` 를 다음으로 교체:

```
머지 후 재개: 1단계 preflight 6의 scope별 중단 상태 감지가 잡는다 — PR 머지 확인(`gh pr view <릴리스 브랜치명> --json state,mergedAt`) 후
```

- [ ] **Step 5: release-train/SKILL.md 수정** — 라인 24-26(**item 4·item 5·뒤따르는 빈 줄**)을 교체 (동일한 빈 줄 소비 규칙):

기존 (빈 줄 포함 세 줄):

```
{{#if github.release}}4. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
5. 중단된 패키지 릴리스 확인: 어떤 패키지 scope의 파일 버전(수식어 제외)이 마지막 태그보다 높은데 그 버전 태그가 없으면 개별 릴리스가 진행 중인 것 — train은 릴리스된 조합을 묶으므로, 먼저 그 패키지 릴리스를 마치라고 안내하고 멈춰라.

```

신규 (마지막 줄이 `{{/if}}` — 그 뒤에 바로 `## 2. 현재 train 버전` 줄이 온다):

```
{{#if github.release}}4. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인
{{/if}}5. 중단된 패키지 릴리스 확인: 어떤 패키지 scope의 파일 버전이 개발 수식어 없는 **bare 릴리스 버전**인데 그 버전의 태그가 없으면 개별 릴리스가 진행 중인 것 — train은 릴리스된 조합을 묶으므로, 먼저 그 패키지 릴리스를 마치라고 안내하고 멈춰라.
{{#if repo.releasePath == "release-pr"}}6. 열린 릴리스 PR 확인: `gh pr list --state open --json headRefName,url` 결과에 `release/`로 시작하는 head 브랜치의 PR이 있으면 이전 릴리스(패키지 또는 train)가 머지 대기 중이다 — 새 train을 시작하지 말고 그 PR 상태를 보고하고 멈춰라.
{{/if}}
```

라인 57(§6 release-pr 블록)에서 `머지 후 재개: PR 머지를 확인하고` 를 다음으로 교체:

```
머지 후 재개: PR 머지를 확인(`gh pr view release/train-<다음 버전> --json state,mergedAt`)하고
```

- [ ] **Step 6: 통과 확인 + 골든 재생성 + 범위 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → 전부 PASS
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: **18개 트리 전부**의 `expected/.claude/skills/release/SKILL.md`(+ `train-monorepo`·`monorepo-release-pr`의 `release-train/SKILL.md`는 train-monorepo만) — 즉 release 계열 SKILL.md만. `git diff tests/golden`에서 diff가 preflight 문구·재개 문구 라인에 한정되는지, release-pr 트리 4종(`release-pr-app`·`release-pr-snapshot`·`backfill-release-pr`·`monorepo-release-pr`)에만 가드 항목이 추가됐는지 확인.
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/skills tests/test_assets.py tests/golden
git commit -m "fix: preflight 중단 감지 재정의(bare 버전 기준) + release-pr 중복 PR 가드 (M4a)"
```

---

### Task 8: anchor 태그 포맷 준수 — versionsort 통일 + describe --match

단일 레포 release §2의 `git describe`(포맷 무시)를 tag.format glob + versionsort 규칙으로 교체하고, 태그 나열이 있는 다른 스킬 프로즈(train §2, backfill §1)에 `-c versionsort.suffix=-`를 병기한다. hotfix §4의 describe는 라인 도달 가능성이 필요하므로 `--match '<glob>'`을 추가한다(스펙 B "anchor 통일"의 자연 확장 — 유지보수 라인에서는 전역 버전 정렬이 오답이라 describe+match가 올바른 형태).

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md:30`
- Modify: `skills/init/assets/skills/hotfix/SKILL.md:37`
- Modify: `skills/init/assets/skills/release-train/SKILL.md:29-30`
- Modify: `skills/init/assets/skills/backfill/SKILL.md:18`
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: T7 이후의 스킬 본문(라인 번호가 T7로 이동했을 수 있음 — 문자열 기준으로 찾아라).
- Produces: 렌더 산출물의 anchor 규칙 문구(`versionsort.suffix=-`).

- [ ] **Step 1: 실패하는 렌더 단위 테스트 작성** — `tests/test_assets.py`:

`SkillAssetsTest`에:

```python
    def test_release_skill_anchor_uses_tag_format_glob(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("versionsort.suffix=-", out)
        self.assertNotIn("git describe", out)
        self.assertIn("v{version}", out)  # glob 파생 기준 포맷 노출

    def test_hotfix_anchor_describe_has_match_filter(self):
        out = self.render_asset("skills/hotfix/SKILL.md")
        self.assertIn("git describe --tags --abbrev=0 --match", out)

    def test_backfill_sort_uses_versionsort(self):
        out = self.render_asset("skills/backfill/SKILL.md")
        self.assertIn("versionsort.suffix=-", out)
```

`ReleaseTrainAssetsTest`에:

```python
    def test_release_train_tag_listing_uses_versionsort(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("versionsort.suffix=-", out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..`
Expected: 신규 4개 FAIL.

- [ ] **Step 3: 구현** — 4개 파일의 해당 라인 교체:

`release/SKILL.md` §2 anchor 라인:

기존:

```
- anchor: {{#if scope.tag.enabled}}마지막 릴리스 태그 — `git describe --tags --abbrev=0`{{else}}config의 `scopes[].anchor.value`{{/if}}
```

신규:

```
- anchor: {{#if scope.tag.enabled}}마지막 릴리스 태그 — `git -c versionsort.suffix=- tag --list '<glob>' --sort=-v:refname | head -n 1` (`<glob>`은 `{{scope.tag.format}}`의 `{version}`을 `*`로 치환 — 이 포맷에 맞는 태그만 보고 다른 포맷 태그는 무시하라){{else}}config의 `scopes[].anchor.value`{{/if}}
```

`hotfix/SKILL.md` §4 anchor 라인:

기존:

```
- 범위 anchor는 이 라인의 마지막 태그: 라인 체크아웃 상태에서 `git describe --tags --abbrev=0`
```

신규:

```
- 범위 anchor는 이 라인의 마지막 태그: 라인 체크아웃 상태에서 `git describe --tags --abbrev=0 --match '<glob>'` (`<glob>`은 config `scopes[].tag.format`의 `{version}`을 `*`로 치환 — 이 라인에서 도달 가능한, 포맷에 맞는 태그만)
```

`release-train/SKILL.md` §2 두 라인:

기존:

```
- `git tag --list`로 태그를 모으고 `{{train.tag.format}}` 포맷({version} 자리에 CalVer)에 맞는 태그만 남긴다.
- 버전 순으로 정렬해 최신 태그에서 접두사를 떼면 현재 train 버전이다. 맞는 태그가 하나도 없으면 **첫 train**이다.
```

신규:

```
- `git -c versionsort.suffix=- tag --list '<glob>' --sort=-v:refname`로 태그를 모은다 — `<glob>`은 `{{train.tag.format}}`의 `{version}`을 `*`로 치환한 것({version} 자리는 CalVer).
- 첫(최신) 태그에서 접두사를 떼면 현재 train 버전이다. 맞는 태그가 하나도 없으면 **첫 train**이다.
```

`backfill/SKILL.md` §1 정렬 라인:

기존:

```
- 남은 태그를 버전 순으로 정렬한다. 연속한 두 태그 `A`, `B`가 한 구간 `A..B`이며, **이 구간은 태그 B 버전의 릴리스 항목**이다(그 사이 커밋이 B에서 나갔다). 가장 이른 태그는 선행 태그가 없으므로 그 태그 자체를 "Initial release"로 다룬다(`git log <firstTag>`).
```

신규:

```
- 남은 태그를 버전 순으로 정렬한다(오름차순: `git -c versionsort.suffix=- tag --list '<glob>' --sort=v:refname` — `<glob>`은 위 tag.format의 `{version}`을 `*`로 치환). 연속한 두 태그 `A`, `B`가 한 구간 `A..B`이며, **이 구간은 태그 B 버전의 릴리스 항목**이다(그 사이 커밋이 B에서 나갔다). 가장 이른 태그는 선행 태그가 없으므로 그 태그 자체를 "Initial release"로 다룬다(`git log <firstTag>`).
```

- [ ] **Step 4: 통과 + 골든 재생성 + 범위 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → PASS
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 변경 파일이 **release/SKILL.md(단일 변형을 받는 트리들)·hotfix-library의 hotfix/SKILL.md·train-monorepo의 release-train/SKILL.md·backfill 3개 트리의 backfill/SKILL.md** 뿐. 모노레포 변형 release/SKILL.md는 anchor를 스크립트로 얻으므로 무변경이어야 한다.
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills tests/test_assets.py tests/golden
git commit -m "fix: anchor 태그 포맷 준수 — versionsort 통일 + hotfix describe --match (M4a)"
```

---

### Task 9: train 배포 경고 + hotfix 백포트 마감 + 최종 검증

release-train 프리뷰에 `tagTriggersDeployment` ⚠️ 경고 블록(다른 3개 스킬과 동일 문구)을 추가하고, hotfix에 ① 백포트 Release의 `--latest=false` ② 라인 CHANGELOG 항목의 main 반영 확인을 추가한다. 마지막으로 M4a 전체 검증.

**Files:**
- Modify: `skills/init/assets/skills/release-train/SKILL.md` (§6 프리뷰 목록)
- Modify: `skills/init/assets/skills/hotfix/SKILL.md` (§6, §7)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: T7·T8 이후의 스킬 본문.
- Produces: 최종 산출물 — 이후 없음.

- [ ] **Step 1: 실패하는 렌더 단위 테스트 작성** — `tests/test_assets.py`:

`ReleaseTrainAssetsTest`에:

```python
    def test_release_train_warns_on_ci_tag_trigger(self):
        ctx = train_ctx()
        ctx["repo"]["tagTriggersDeployment"] = True
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("배포를 트리거", out)
        self.assertNotIn("배포를 트리거",
                         self.render_asset("skills/release-train/SKILL.md", train_ctx()))
```

`SkillAssetsTest`에:

```python
    def test_hotfix_backport_release_marking_and_changelog(self):
        out = self.render_asset("skills/hotfix/SKILL.md")  # github.release=true, changelog 목적지 포함
        self.assertIn("--latest=false", out)
        self.assertIn("CHANGELOG에도 반영", out)
        ctx = base_ctx(github={"release": False, "generateNotes": False,
                               "releaseYml": False})
        ctx["scope"]["notes"]["destinations"] = ["release-file"]
        out2 = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertNotIn("--latest=false", out2)
        self.assertNotIn("CHANGELOG에도 반영", out2)
        self.assertLessEqual(len(out.splitlines()), 149)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..`
Expected: 신규 2개 FAIL.

- [ ] **Step 3: release-train/SKILL.md §6 수정** — 프리뷰 불릿 목록에서 `- 실행될 명령 목록(...)` 라인과 `- 통합 노트 미리보기` 라인 사이에 삽입:

기존:

```
- 실행될 명령 목록(노트 커밋, {{#if repo.releasePath == "release-pr"}}PR 생성{{else}}push{{/if}}, 태그{{#if github.release}}, Release{{/if}})
- 통합 노트 미리보기
```

신규:

```
- 실행될 명령 목록(노트 커밋, {{#if repo.releasePath == "release-pr"}}PR 생성{{else}}push{{/if}}, 태그{{#if github.release}}, Release{{/if}})
{{#if repo.tagTriggersDeployment}}- ⚠️ **이 태그는 CI 배포를 트리거합니다** — 프리뷰에 반드시 명시
{{/if}}- 통합 노트 미리보기
```

- [ ] **Step 4: hotfix/SKILL.md §6·§7 수정** — 두 삽입 모두 **기존 줄 끝에 이어 붙이는 형태**로, 개행을 조건 블록 **안**(내용 앞)에 둔다. 독립된 줄로 삽입하면 비해당 config에서 빈 줄이 남아 바이트 불변이 깨진다.

§6: `release 스킬 7단계와 동일하다: ... → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.` 줄의 **줄 끝**에 이어 붙인다:

기존 줄 끝:

```
... → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.
```

신규 줄 끝 (같은 소스 줄에 계속):

```
... → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.{{#if github.release}}
- 이 패치 버전이 저장소의 최신 릴리스보다 낮으면(구버전 라인 백포트) `gh release create`에 `--latest=false`를 붙여 이 Release가 Latest로 마킹되지 않게 하라.{{/if}}
```

(여는 `{{#if github.release}}` 뒤에서 줄이 바뀌고, 새 불릿 내용 뒤에 `{{/if}}`가 같은 줄에서 닫힌다 — collapse 시 0바이트, 렌더 시 불릿 한 줄 추가.)

§7: `- 핫픽스 수정이 \`{{repo.defaultBranch}}\`에도 필요한지 확인하라. ... 불필요하다.` 줄의 **줄 끝**에 이어 붙인다:

```
...원래 `{{repo.defaultBranch}}`에서 가져온 수정이면 불필요하다.{{#each scope.notes.destinations}}{{#if this == "changelog"}}
- 라인 CHANGELOG에 쓴 이 패치 버전 항목을 `{{repo.defaultBranch}}`의 CHANGELOG에도 반영할지 확인하라 — 빠뜨리면 기본 브랜치 릴리스 이력에 구멍이 남는다.{{/if}}{{/each}}
```

- [ ] **Step 5: 통과 + 골든 재생성 + 범위 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → PASS
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `hotfix-library/expected/.claude/skills/hotfix/SKILL.md` **만** (train 경고는 train-monorepo config가 `tagTriggersDeployment: false`라 0바이트 collapse — 바이트 불변 확인이 곧 검증).
Run: `python3 -m unittest discover -s tests -q` → OK

- [ ] **Step 6: M4a 최종 검증**

```bash
python3 -m unittest discover -s tests -q            # OK (약 200개)
claude plugin validate . --strict                    # PASS
wc -l skills/init/SKILL.md skills/init/assets/skills/*/SKILL.md   # 각각 ≤500 / ≤150
git status --porcelain                               # 커밋 누락 없는지
```

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/skills tests/test_assets.py tests/golden
git commit -m "fix: train 배포 트리거 경고 + hotfix 백포트 마감(--latest=false·CHANGELOG 반영) (M4a)"
```

---

## 완료 기준 (스펙 대비)

| 스펙 항목 | 태스크 |
|---|---|
| A-1 version.py regex 가드 | T2 |
| A-2 changed-packages 3건 | T3 |
| A-3 next-version CalVer 동일 기간 | T4 |
| B preflight 재정의 + release-pr 가드 + tagless 게이트 | T7 |
| B anchor 통일(release·hotfix·train·backfill) | T8 |
| B train 경고 + hotfix 마감 | T9 |
| C validate 규칙 4종(+역방향) | T5 |
| D 골든 4종 신설 | T6 |
| D validate 음성 테스트·필드 개별화 | T5 |
| D 스크립트 단위 테스트 5건 | T2·T3·T4 |
| D 골든 결정론 하드닝 | T1 |

구현 후 랜딩은 운영 패턴대로: push → PR(한국어 본문) → `--merge --delete-branch` → main ff-pull. PR 생성·병합 전 `gh auth switch --user Cho-D-YoungRae`, 완료 후 `gh auth switch --user aims-yrcho` 원복.
