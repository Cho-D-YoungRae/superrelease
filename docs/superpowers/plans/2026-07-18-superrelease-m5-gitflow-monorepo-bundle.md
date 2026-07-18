# superrelease M5 — gitflow 모노레포 · tagless gitflow · bundle 라운드 노트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** imstargg-v2 형태(independent 모노레포 × gitflow × tagless × CalVer 라운드 묶음 노트)를 superrelease가 생성하는 툴킷으로 지원한다.

**Architecture:** 스펙 [2026-07-18-superrelease-m5-gitflow-monorepo-bundle-design.md](../specs/2026-07-18-superrelease-m5-gitflow-monorepo-bundle-design.md)의 접근 A — 새 스킬 asset 없이 기존 release-monorepo·release·hotfix 스킬에 조건 분기를 추가하고, bundle은 config 최상위 객체 + `notes-bundle.md` 템플릿으로 릴리스 흐름에 통합한다. gitflow의 앵커는 태그가 아니라 `origin/<defaultBranch>`다.

**Tech Stack:** Python 3.9+ stdlib only · 동결 template dialect · unittest (pytest 없음)

## Global Constraints

- **동결 dialect**: `{{path}}`, `{{#if x}}`/`{{#if x == "lit"}}`/`{{else}}`, `{{#unless}}`(비교식 허용), `{{#each}}`만. 확장 금지. 단일 중괄호(`{round}`)는 리터럴 보존.
- **바이트 불변**: 조건 블록 추가 시 그 기능이 없는 config에서 0바이트 collapse. 개행은 `{{#if}}` **안**에. 검증: `git status --porcelain tests/golden`에 의도한 트리만.
- **기존 골든 영향 허용 범위**: `gitflow-app`(앵커 통일로 의도 변경)과 신규 `gitflow-monorepo-bundle`뿐. 모노레포 3종(pnpm-monorepo·backfill-monorepo·monorepo-release-pr)·나머지는 전부 바이트 불변이어야 한다.
- **생성 SKILL.md 렌더 결과 ≤150줄** (test_assets가 `assertLessEqual(len(out.splitlines()), 149)`로 게이트).
- **스크립트**: stdlib only, exit 0/1/2 규약, `--today` 주입 결정론. 이번 마일스톤의 스크립트 변경은 `next-version.py` 하나뿐(스펙 5절).
- **테스트 러너 함정**: 전체는 `python3 -m unittest discover -s tests -q`, 단일 모듈은 `cd tests && python3 -m unittest <module> -v; cd ..` (dotted 형식은 ModuleNotFoundError).
- 코드·에러 메시지 영어 / 생성 문서·init 프로즈 한국어.
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: next-version.py `--current-among` (+ 패턴 검증 헬퍼 추출)

**Files:**
- Modify: `skills/init/assets/scripts/next-version.py`
- Test: `tests/test_next_version.py`

**Interfaces:**
- Produces: CLI `next-version.py --scheme calver --pattern <P> --today <D> --current-among <v1> [<v2>…]` → 후보 중 패턴 매칭 최댓값을 current로 삼아 다음 CalVer 출력. 매칭 0개면 exit 1, calver 외 scheme이면 exit 2, `--current`/`--scope`와 상호 배타(argparse exit 2). Task 4·6·7의 스킬 프로즈가 이 호출 형태를 그대로 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_next_version.py` 파일 끝(`if __name__` 위)에 추가:

```python
class CurrentAmongTest(unittest.TestCase):
    def test_picks_numeric_max_not_lexicographic(self):
        # 사전순 최대는 2026.05.2지만 수치 최대는 2026.05.10 — 다음은 .11
        r = out("--scheme", "calver", "--pattern", "YYYY.0M.MICRO",
                "--today", "2026-05-20",
                "--current-among", "2026.05.2", "2026.05.10", "2026.04.3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "2026.05.11")

    def test_ignores_non_matching_candidates(self):
        r = out("--scheme", "calver", "--pattern", "YYYY.0M.MICRO",
                "--today", "2026-06-01",
                "--current-among", "README", "2026.05.1", "notes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "2026.06.0")  # 기간 변경 → MICRO 0

    def test_all_non_matching_exits_1(self):
        r = out("--scheme", "calver", "--pattern", "YYYY.0M.MICRO",
                "--today", "2026-06-01", "--current-among", "README", "notes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no candidate matches", r.stderr)

    def test_semver_rejects_current_among(self):
        r = out("--scheme", "semver", "--current-among", "1.2.3")
        self.assertEqual(r.returncode, 2)
        self.assertIn("calver only", r.stderr)

    def test_headver_rejects_current_among(self):
        r = out("--scheme", "headver", "--head", "1", "--today", "2026-06-01",
                "--current-among", "1.2624.0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("calver only", r.stderr)

    def test_mutually_exclusive_with_current(self):
        r = out("--scheme", "calver", "--pattern", "YYYY.0M.MICRO",
                "--current", "2026.05.0", "--current-among", "2026.05.1")
        self.assertEqual(r.returncode, 2)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_next_version.CurrentAmongTest -v; cd ..`
Expected: FAIL/ERROR (unrecognized arguments: --current-among)

- [ ] **Step 3: 구현** — `skills/init/assets/scripts/next-version.py`:

(a) `calver_next` 앞에 검증 헬퍼를 추출하고 `calver_next`의 인라인 검증을 교체:

```python
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
```

`calver_next`의 첫 검증 블록(`if not pattern:` 부터 `fail("calver pattern may contain MICRO at most once: " + pattern, 2)` 까지)을 삭제하고 첫 줄을 `parts = parse_calver_pattern(pattern)`으로 교체한다 (기존 `parts = split_calver_pattern(pattern)` 줄과 literals 검사 4줄, tokens 검사 5줄이 모두 헬퍼로 이동).

(b) argparse `mode` 그룹에 추가 (`mode.add_argument("--scope", ...)` 다음 줄):

```python
    mode.add_argument("--current-among", nargs="+", metavar="VER",
                      help="calver only: take the highest pattern-matching "
                           "candidate as the current version")
```

(c) config 로드 조건에 current_among 제외 추가 — 기존:

```python
    if args.current is None and (scheme is None
```

→

```python
    if args.current is None and args.current_among is None and (scheme is None
```

(d) calver/headver 분기에 가드 + current 산출 교체 — 기존 분기 내부:

```python
        today = parse_today(args.today)
        current = args.current if args.current is not None \
            else current_from_config(args.scope)
        if scheme == "calver":
            print(calver_next(current, pattern, today))
        else:
            print(headver_next(current, head, today))
        return
```

→

```python
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
```

(e) semver 섹션 최상단(`if args.today:` 검사 앞)에 가드:

```python
    if args.current_among is not None:
        fail("--current-among applies to calver only", 2)
```

- [ ] **Step 4: 통과 확인 + 기존 벡터 회귀 확인**

Run: `cd tests && python3 -m unittest test_next_version -v; cd ..`
Expected: 전부 PASS (기존 46개 + 신규 6개)

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/scripts/next-version.py tests/test_next_version.py
git commit -m "feat(scripts): next-version --current-among — calver 후보 중 최댓값 기반 다음 라운드 계산

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: validate_config — gitflow 모노레포 허용 · gitflow tagless 허용 · bundle 규칙

**Files:**
- Modify: `skills/init/scripts/render.py` (validate_config)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Produces: config 최상위 `bundle` 객체(`{"enabled": bool, "scheme": {"type": "calver", "pattern": str}, "notesPath": str}`)가 유효 스키마가 된다. gitflow×monorepo, gitflow×tagless×release-pr 조합이 validate를 통과한다. Task 6·8의 config들이 이를 전제한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_render_pipeline.py`의 `PipelineTest` 클래스 안, 기존 `test_gitflow_rejected_for_monorepo`를 **교체**하고 그 아래 신규 테스트 추가:

```python
    def test_gitflow_monorepo_allowed(self):
        cfg = monorepo_config()
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["developBranch"] = "develop"
        cfg["repo"]["releasePath"] = "release-pr"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_gitflow_tagless_release_pr_allowed(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["developBranch"] = "develop"
        cfg["repo"]["releasePath"] = "release-pr"
        cfg["scopes"][0]["tag"]["enabled"] = False
        cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
        cfg["github"] = {"release": False, "generateNotes": False,
                        "releaseYml": False}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bundle_requires_independent(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["bundle"] = {"enabled": True,
                         "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                         "notesPath": "docs/releases/"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("independent", r.stderr)

    def test_bundle_requires_calver_and_pattern(self):
        cfg = monorepo_config()
        cfg["bundle"] = {"enabled": True,
                         "scheme": {"type": "semver", "pattern": ""},
                         "notesPath": "docs/releases/"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("calver", r.stderr)
        self.assertIn("bundle.scheme.pattern", r.stderr)

    def test_bundle_requires_notes_path(self):
        cfg = monorepo_config()
        cfg["bundle"] = {"enabled": True,
                         "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bundle.notesPath", r.stderr)

    def test_bundle_ok_for_trunk_monorepo(self):
        # bundle은 branching 무관 — trunk 모노레포 라운드에도 허용 (회귀 핀)
        cfg = monorepo_config()
        cfg["bundle"] = {"enabled": True,
                         "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                         "notesPath": "docs/releases/"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)
```

기존 `test_release_pr_rejected_for_tagless_scope`는 그대로 둔다(trunk 기본값 — "trunk×release-pr×tagless 여전히 거부" 회귀 핀이 된다).

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_gitflow_monorepo_allowed test_render_pipeline.PipelineTest.test_bundle_requires_independent -v; cd ..`
Expected: FAIL (monorepo 거부 메시지 / bundle 규칙 부재로 returncode 0)

- [ ] **Step 3: 구현** — `skills/init/scripts/render.py` validate_config:

(a) release-pr×tagless 규칙에 gitflow 예외 — 기존:

```python
    if repo.get("releasePath") == "release-pr" and scopes and any(
            not (s.get("tag") or {}).get("enabled", True) for s in scopes):
        problems.append('repo.releasePath "release-pr" is not supported with '
                        "tagless scopes (tag.enabled false): merge-then-tag "
                        "resume relies on tag detection")
```

→

```python
    if (repo.get("releasePath") == "release-pr"
            and repo.get("branching") != "gitflow" and scopes and any(
                not (s.get("tag") or {}).get("enabled", True) for s in scopes)):
        problems.append('repo.releasePath "release-pr" is not supported with '
                        "tagless scopes (tag.enabled false) outside gitflow: "
                        "merge-then-tag resume relies on tag detection "
                        "(gitflow resumes from branch state instead)")
```

(b) gitflow 블록에서 모노레포 거부 삭제 — 다음 4줄을 제거:

```python
        if repo.get("kind") == "monorepo" or strategy:
            problems.append('repo.branching "gitflow" is not supported for '
                            "monorepos yet (single-skill repos only)")
```

(c) train 거부 블록 바로 뒤에 bundle 규칙 추가:

```python
    bundle = config.get("bundle") or {}
    if bundle.get("enabled"):
        if strategy != "independent":
            problems.append("bundle (round notes) requires the independent "
                            "monorepo strategy")
        if (bundle.get("scheme") or {}).get("type") != "calver":
            problems.append('bundle.scheme.type must be "calver" '
                            "(round labels are CalVer)")
        if not (bundle.get("scheme") or {}).get("pattern"):
            problems.append("bundle.scheme.pattern is required "
                            "(a CalVer pattern, e.g. YYYY.0M.MICRO)")
        if not bundle.get("notesPath"):
            problems.append("bundle.notesPath is required "
                            '(round notes directory, e.g. "docs/releases/")')
```

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v; cd ..`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat(render): validate — gitflow 모노레포·gitflow tagless 허용 + bundle 규칙

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: build_context에 derived.anyTagEnabled + 테스트 ctx 헬퍼 갱신

**Files:**
- Modify: `skills/init/scripts/render.py` (build_context)
- Modify: `tests/test_assets.py` (base_ctx·mono_ctx·gitflow_ctx)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Produces: 렌더 컨텍스트에 `derived.anyTagEnabled`(bool — 한 scope라도 `tag.enabled` true) 추가. Task 6의 release-monorepo §8 게이트(`{{#if derived.anyTagEnabled}}`)가 소비한다. dialect는 배열 술어를 표현할 수 없어 파생 값이 필요하다(스펙 6절 "전 scope tagless면 §8 collapse"의 구현 수단 — 엔진 문법이 아니라 컨텍스트 값 추가).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_render_pipeline.py`의 `PipelineTest`에 추가 (fake asset이 derived를 쓰도록 ASSET_FILES의 `skills/release/SKILL.md` 값을 교체):

```python
ASSET_FILES = {
    "skills/release/SKILL.md":
        "---\nname: release\ndescription: {{project.name}} 릴리스\n---\n\n"
        "# {{project.name}} release\n"
        "{{#if derived.anyTagEnabled}}TAGGED\n{{/if}}",
    "scripts/tool.py": "#!/usr/bin/env python3\nprint('hi')\n",
    "templates/notes.md": "# Notes {{scope.name}}\n",
    "github/release.yml": "changelog:\n  categories: []\n",
}
```

그리고 테스트 2개:

```python
    def test_derived_any_tag_enabled_true(self):
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)
        skill = (self.repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("TAGGED", skill)

    def test_derived_any_tag_enabled_false_when_all_tagless(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["tag"]["enabled"] = False
        cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
        cfg["github"] = {"release": False, "generateNotes": False,
                        "releaseYml": False}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)
        skill = (self.repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("TAGGED", skill)
```

주의: `test_create_renders_and_inserts_marker_after_frontmatter`의 `lines[4]` 마커 위치 단정은 frontmatter 뒤라 영향 없음. `test_rerender_same_config_is_unchanged` 등은 내용 무관.

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_derived_any_tag_enabled_true -v; cd ..`
Expected: FAIL (unknown placeholder 아님 — `{{#if}}` truthy는 missing을 False 취급하므로 TAGGED 미출력으로 FAIL)

- [ ] **Step 3: 구현** — `render.py` build_context:

```python
def build_context(config, repo_dir, plugin_version, now):
    ctx = dict(config)
    ctx["project"] = {"name": project_name(repo_dir)}
    ctx["plugin"] = {"version": plugin_version}
    ctx["generated"] = {"at": now}
    ctx["scope"] = (config.get("scopes") or [{}])[0]
    # Array predicates are inexpressible in the frozen dialect; precompute
    # the few the templates need.
    ctx["derived"] = {"anyTagEnabled": any(
        (s.get("tag") or {}).get("enabled")
        for s in config.get("scopes") or [])}
    return ctx
```

그리고 `tests/test_assets.py`의 `base_ctx`·`mono_ctx`·`gitflow_ctx` 각각에서 `ctx["scope"] = cfg["scopes"][0]` 줄 다음에 동일 파생값을 추가:

```python
    ctx["derived"] = {"anyTagEnabled": any(
        s["tag"]["enabled"] for s in cfg["scopes"])}
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m unittest discover -s tests -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py tests/test_assets.py
git commit -m "feat(render): 렌더 컨텍스트에 derived.anyTagEnabled 추가 — 배열 술어 파생값

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: notes-bundle.md 템플릿 + manifest 엔트리

**Files:**
- Create: `skills/init/assets/templates/notes-bundle.md`
- Modify: `skills/init/assets/manifest.json`
- Test: `tests/test_assets.py`

**Interfaces:**
- Produces: `.superrelease/templates/notes-bundle.md` (when: `bundle.enabled`, preserve: template). Task 6·7의 스킬 프로즈가 이 경로를 참조한다. `{round}`·`{date}`는 단일 중괄호 리터럴.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_assets.py`의 `MonorepoAssetsTest`에 추가 (gitflow_mono_ctx는 Task 6에서 추가되므로 여기서는 mono_ctx에 bundle만 얹는다):

```python
    def test_notes_bundle_renders_clean_ko(self):
        ctx = mono_ctx()
        ctx["bundle"] = {"enabled": True,
                         "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                         "notesPath": "docs/releases/"}
        out = self.render_asset("templates/notes-bundle.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("포함 버전", out)
        self.assertIn("demo-mono {round} — {date}", out)  # 단일 중괄호 보존
        self.assertNotIn("Included Versions", out)        # en 블록은 ko에서 드롭
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest.test_notes_bundle_renders_clean_ko -v; cd ..`
Expected: ERROR (FileNotFoundError: templates/notes-bundle.md)

- [ ] **Step 3: 템플릿 작성** — `skills/init/assets/templates/notes-bundle.md` (파일 전체):

```markdown
{{#unless scope.notes.language == "en"}}<!-- 라운드 묶음 릴리스 노트 템플릿. {round}, {date}는 작성 시점에 채운다. 해당 없는 섹션은 생략한다. -->
# {{project.name}} {round} — {date}

## 포함 버전
<!-- | 패키지 | 버전 | 이번 라운드 | 표 — 릴리스된 scope와 미변경 scope의 현재 버전을 모두 적는다 -->

## 하이라이트
<!-- 라운드 전체에서 가장 중요한 변경 1~3개를 한 문단으로 -->

## 패키지별 변경
<!-- ### <scope> <version> 소제목 아래 사용자 관점 요약 (#PR번호) -->

## Breaking Changes
<!-- 없으면 섹션 삭제. 있으면 scope 명시 + 마이그레이션 가이드 필수 -->
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Bundle round release-note template. Fill {round} and {date} when drafting; drop empty sections. -->
# {{project.name}} {round} — {date}

## Included Versions
<!-- | Package | Version | This round | — released scopes plus unchanged scopes' current versions -->

## Highlights

## Per-package Changes

## Breaking Changes
{{/unless}}
```

manifest.json — `templates/changelog-entry.md` 엔트리 **앞**에 추가:

```json
    {
      "src": "templates/notes-bundle.md",
      "dest": ".superrelease/templates/notes-bundle.md",
      "render": true,
      "preserve": "template",
      "when": "bundle.enabled"
    },
```

- [ ] **Step 4: 통과 확인 + 골든 무영향 확인**

Run: `python3 -m unittest discover -s tests -q && python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 테스트 전부 PASS, `git status` 출력 **없음** (기존 골든 어디에도 bundle.enabled가 없어 skipped)

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/templates/notes-bundle.md skills/init/assets/manifest.json tests/test_assets.py
git commit -m "feat(assets): notes-bundle.md 라운드 묶음 노트 템플릿 (when: bundle.enabled)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: release(단일) 스킬 — gitflow 앵커 통일 + tagless gitflow

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md`
- Test: `tests/test_assets.py`
- Regen: `tests/golden/gitflow-app/expected/**` (의도 변경 — 이 트리만)

**Interfaces:**
- Consumes: 없음 (템플릿 텍스트만)
- Produces: gitflow 렌더에서 §1.6이 브랜치 상태 기반 감지, §2가 `origin/<main>..HEAD` 범위. trunk 렌더는 바이트 불변.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_assets.py` `SkillAssetsTest`에 추가:

```python
    def test_release_skill_gitflow_anchor_is_main(self):
        out = self.render_asset("skills/release/SKILL.md", gitflow_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("origin/main..HEAD", out)
        self.assertIn("merge-base --is-ancestor origin/main", out)
        self.assertNotIn("--merged origin/main", out)   # 옛 태그 도달성 감지 제거
        self.assertNotIn("anchor가 없으면", out)          # 첫 릴리스 특례 드롭

    def test_release_skill_gitflow_tagless(self):
        ctx = gitflow_ctx()
        ctx["scope"]["tag"]["enabled"] = False
        ctx["scope"]["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False,
                        "releaseYml": False}
        ctx["derived"] = {"anyTagEnabled": False}
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("중단 상태 감지", out)              # tagless여도 감지 존재
        self.assertNotIn("7단계(태그)부터", out)          # 태그 재개 항목은 드롭
        self.assertIn("merge-base --is-ancestor", out)
        self.assertNotIn("anchor.value", out)            # anchor 갱신 문구 없음
        self.assertNotIn("## 7. 태그", out)
        self.assertLessEqual(len(out.splitlines()), 149)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_release_skill_gitflow_anchor_is_main -v; cd ..`
Expected: FAIL

- [ ] **Step 3: 템플릿 수정** — `skills/init/assets/skills/release/SKILL.md` 4개 지점 (trunk 렌더 바이트 불변이 절대 조건 — else 가지에 기존 텍스트를 **그대로** 보존):

(a) §1 preflight 6 — 기존의 `{{#if scope.tag.enabled}}{{#if repo.branching == "gitflow"}}6. 중단 상태 감지 (gitflow): ① … ② … {{else}}6. 중단 상태 감지: …{{/if}}` 구조를 다음으로 교체 (바깥 게이트를 gitflow 우선으로 재배치):

```
{{#if repo.branching == "gitflow"}}6. 중단 상태 감지 (gitflow): {{#if scope.tag.enabled}}① 머지된 릴리스 PR(`gh pr list --state merged --search "head:release/" --json headRefName,mergedAt`)의 `release/<버전>` head 중 그 버전의 태그가 아직 없으면 이전 릴리스가 태그 전에 중단된 것 — 6단계의 "머지 후 재개"대로 7단계(태그)부터 이어가라. ② {{/if}}back-merge 누락: `git merge-base --is-ancestor origin/{{repo.defaultBranch}} HEAD` 가 실패하면 직전 릴리스(또는 hotfix)의 back-merge가 누락된 것 — 8단계의 back-merge부터 복구하라{{#if scope.preRelease.style == "mutable"}}. 파일 버전이 `-{{scope.preRelease.qualifier}}` 수식어 없는 bare 버전이면 8단계의 다음 개발 버전 복귀부터 이어가라{{/if}}.{{else}}{{#if scope.tag.enabled}}6. 중단 상태 감지: 마지막 릴리스 태그가 존재하고 파일 버전이 그보다 높은데 **파일 버전 그대로의 태그가 없으면** 이전 릴리스가 중단된 것이다{{#if scope.preRelease.style == "mutable"}} (단, 파일 버전에 `-{{scope.preRelease.qualifier}}` 수식어가 붙어 있으면 정상 개발 상태 — 중단 아님){{/if}} — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.{{/if}}{{/if}}
```

주의: 기존 비-gitflow 텍스트("마지막 릴리스 태그가 존재하고 …")는 한 글자도 바꾸지 않는다. 기존 gitflow ②의 versionsort `--merged` 감지 문장은 삭제된다(gitflow-app 골든 의도 변경). 개행 배치는 기존 줄 구조를 유지한다.

(b) §2 anchor — 기존:

```
- anchor: {{#if scope.tag.enabled}}마지막 릴리스 태그 — `git -c versionsort.suffix=- tag --list '<glob>' --sort=-v:refname | head -n 1` (`<glob>`은 `{{scope.tag.format}}`의 `{version}`을 `*`로 치환 — 이 포맷에 맞는 태그만 보고 다른 포맷 태그는 무시하라){{else}}config의 `scopes[].anchor.value`{{/if}}
- anchor가 없으면 **첫 릴리스**: 커밋 전체를 나열하지 말고 "Initial release"로 다뤄라.
- 수집: `git log <anchor>..HEAD --pretty=format:"%h %s"`
```

→

```
- anchor: {{#if repo.branching == "gitflow"}}`origin/{{repo.defaultBranch}}` — gitflow의 범위 기준은 태그가 아니라 기본 브랜치다(릴리스 머지로만 전진하며, config의 anchor 필드는 사용되지 않는다){{else}}{{#if scope.tag.enabled}}마지막 릴리스 태그 — `git -c versionsort.suffix=- tag --list '<glob>' --sort=-v:refname | head -n 1` (`<glob>`은 `{{scope.tag.format}}`의 `{version}`을 `*`로 치환 — 이 포맷에 맞는 태그만 보고 다른 포맷 태그는 무시하라){{else}}config의 `scopes[].anchor.value`{{/if}}{{/if}}
{{#unless repo.branching == "gitflow"}}- anchor가 없으면 **첫 릴리스**: 커밋 전체를 나열하지 말고 "Initial release"로 다뤄라.
{{/unless}}- 수집: `git log {{#if repo.branching == "gitflow"}}origin/{{repo.defaultBranch}}{{else}}<anchor>{{/if}}..HEAD --pretty=format:"%h %s"`
```

(수집 줄의 squash 접미 `{{#if repo.mergePolicy == "squash"}}…{{/if}}`는 그대로 유지.)

(c) §7 — 변경 없음 (`{{#if scope.tag.enabled}}` 게이트가 tagless gitflow에서 이미 collapse).

(d) §8 anchor 갱신 unless 블록 — 기존:

```
{{#unless scope.tag.enabled}}
태그를 쓰지 않는 설정이다 — 릴리스 후 `.superrelease/config.json`의 `scopes[].anchor.value`를 릴리스 커밋 sha로 갱신해 함께 커밋하라 (다음 릴리스의 범위 기준점이며, config에서 유일하게 상태를 갖는 필드다).
{{/unless}}
```

→ (gitflow에서는 anchor 미사용)

```
{{#unless scope.tag.enabled}}{{#unless repo.branching == "gitflow"}}
태그를 쓰지 않는 설정이다 — 릴리스 후 `.superrelease/config.json`의 `scopes[].anchor.value`를 릴리스 커밋 sha로 갱신해 함께 커밋하라 (다음 릴리스의 범위 기준점이며, config에서 유일하게 상태를 갖는 필드다).
{{/unless}}{{/unless}}
```

- [ ] **Step 4: 테스트 + 골든 재생성 + 범위 확인**

Run: `python3 -m unittest discover -s tests -q` → 전부 PASS 후
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `tests/golden/gitflow-app/expected/.claude/skills/release/SKILL.md` **한 파일만** M. 다른 트리가 보이면 trunk 바이트 불변이 깨진 것 — else 가지 텍스트를 원본과 대조해 고칠 것.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py tests/golden
git commit -m "feat(assets): release 스킬 gitflow 앵커를 main 브랜치로 통일 — tagless gitflow 지원

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: release-monorepo 스킬 — gitflow 분기 + bundle 라운드 노트

**Files:**
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (전체 교체)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: Task 1의 `--current-among` 호출 형태, Task 3의 `derived.anyTagEnabled`, Task 4의 `notes-bundle.md`.
- Produces: gitflow 모노레포 라운드 릴리스 흐름. trunk 렌더는 바이트 불변.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_assets.py`: 파일 상단 헬퍼들 뒤에 추가:

```python
def gitflow_mono_ctx(**overrides):
    cfg = monorepo_config()
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["bundle"] = {"enabled": True,
                     "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                     "notesPath": "docs/releases/"}
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-mono"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    ctx["derived"] = {"anyTagEnabled": any(
        s["tag"]["enabled"] for s in cfg["scopes"])}
    return ctx
```

`MonorepoAssetsTest`에 추가:

```python
    def test_release_monorepo_gitflow_branch(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md",
                                gitflow_mono_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("--ref origin/main", out)
        self.assertIn("`develop`", out)
        self.assertIn("origin/main..HEAD", out)
        self.assertIn("merge-base --is-ancestor origin/main", out)
        self.assertIn("back-merge", out)
        self.assertIn("gh pr merge --merge", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_bundle_round_note(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md",
                                gitflow_mono_ctx())
        self.assertIn("--current-among", out)
        self.assertIn("notes-bundle.md", out)
        self.assertIn("docs/releases/", out)
        self.assertIn("release/<라운드>", out)

    def test_release_monorepo_all_tagless_collapses_tag_section(self):
        ctx = gitflow_mono_ctx()
        for s in ctx["scopes"]:
            s["tag"]["enabled"] = False
            s["notes"]["destinations"] = ["changelog"]
        ctx["github"] = {"release": False, "generateNotes": False,
                        "releaseYml": False}
        ctx["derived"] = {"anyTagEnabled": False}
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertNotIn("## 8. 태그", out)
        self.assertNotIn("anchor.value", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_trunk_has_no_gitflow_or_bundle(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertNotIn("--ref origin", out)
        self.assertNotIn("--current-among", out)
        self.assertNotIn("back-merge", out)
        self.assertNotIn("merge-base", out)
        self.assertIn("## 8. 태그", out)   # trunk(태그 기본)는 §8 유지
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest.test_release_monorepo_gitflow_branch -v; cd ..`
Expected: FAIL

- [ ] **Step 3: 스킬 전체 교체** — `skills/init/assets/skills/release-monorepo/SKILL.md`를 아래 내용으로 Write (기존 96줄에서 gitflow·bundle 조건 삽입 — trunk 렌더가 현재와 바이트 동일해야 하므로, 조건 밖 텍스트는 기존 파일과 글자 단위로 같다):

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

- `python3 .superrelease/scripts/changed-packages.py{{#if repo.branching == "gitflow"}} --ref origin/{{repo.defaultBranch}}{{/if}} --json` 실행{{#if repo.branching == "gitflow"}}(먼저 `git fetch origin`) — gitflow의 범위 기준은 태그가 아니라 `origin/{{repo.defaultBranch}}`다(기본 브랜치는 릴리스 머지로만 전진하며, config의 anchor 필드는 사용되지 않는다). scope별 변경 파일을 확보한다.{{else}} — scope별 anchor(마지막 태그)와 변경 파일을 확보한다.{{/if}}
- 사용자가 패키지를 지정했으면 그 scope(복수 가능). 지정하지 않았으면 hasChanges=true인 scope 목록을 보여주고 선택받아라.
- 선택된 scope의 config `dependents`를 확인해 전파 대상(6단계)이 생기는지 미리 안내하라.

## 1. preflight — 모두 통과해야 진행

1. 현재 브랜치: `git branch --show-current` 결과가 `{{#if repo.branching == "gitflow"}}{{repo.developBranch}}{{else}}{{repo.defaultBranch}}{{/if}}` 여야 함{{#if repo.branching == "gitflow"}} (gitflow — 릴리스는 통합 브랜치에서 시작한다){{/if}}
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{#if repo.branching == "gitflow"}}{{repo.developBranch}}{{else}}{{repo.defaultBranch}}{{/if}} --count` 가 0
4. 전 scope 버전 일치: `python3 .superrelease/scripts/version.py verify` → exit 0
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인
{{else}}{{#if repo.releasePath == "release-pr"}}5. gh 인증: `gh auth status` — release-pr 경로는 PR 생성·조회에 gh가 필요하다(실패 시 GitHub MCP 폴백)
{{/if}}{{/if}}{{#if repo.branching == "gitflow"}}6. 중단 상태 감지 (gitflow): 머지된 최신 릴리스 PR(`gh pr list --state merged --search "head:release/" --json headRefName,mergedAt`)의 후처리가 남아 있으면 이어서 진행하라 — {{#if derived.anyTagEnabled}}① `tag.enabled`인 scope 중 그 라운드 버전의 태그가 없으면 8단계(태그)부터 ② {{/if}}back-merge 누락(`git merge-base --is-ancestor origin/{{repo.defaultBranch}} HEAD` 실패)이면 9단계의 back-merge부터, mutable scope의 파일 버전이 수식어 없는 bare면 9단계의 SNAPSHOT 복귀부터.{{else}}6. scope별 중단 상태: 대상 scope의 파일 버전이 개발 수식어(-SNAPSHOT류 mutable qualifier) 없는 **bare 릴리스 버전**이고 anchor 태그보다 높은데 그 버전의 태그가 없으면 이전 릴리스가 중단된 것 — resume/rollback 중 선택받아라. 태그를 쓰지 않는 scope는 이 검사를 건너뛴다.{{/if}}
{{#if repo.releasePath == "release-pr"}}7. 열린 릴리스 PR 확인: `gh pr list --state open --json headRefName,url` 결과에 `release/`로 시작하는 head 브랜치의 PR이 있으면 이전 릴리스가 머지 대기 중이다 — 새 릴리스를 시작하지 말고 그 PR 상태를 보고하고 멈춰라(머지 후 재개는 6번이 잡는다).
{{/if}}
## 2. scope별 범위 산출

{{#if repo.branching == "gitflow"}}- 범위 기준은 `origin/{{repo.defaultBranch}}`다 — scope별 anchor 태그를 쓰지 않는다.
- 수집: `git log origin/{{repo.defaultBranch}}..HEAD --pretty=format:"%h %s" -- <scope.path>`{{else}}- anchor는 changed-packages 출력의 값(그 scope 태그 포맷의 최신 태그). anchor가 없으면 **첫 릴리스** — 커밋을 나열하지 말고 "Initial release"로 다뤄라.
- 수집: `git log <anchor>..HEAD --pretty=format:"%h %s" -- <scope.path>`{{/if}}{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}

## 3. scope별 bump 제안

- 그 scope의 config `bump.sources` 순서로 분석. 매핑: feat → minor, fix → patch, BREAKING CHANGE 푸터 또는 `!` → major. **0.x는** breaking → minor, feat → patch 관례를 적용하고 명시하라.
- 제시 형식: "**a: minor 제안** — 근거: feat 커밋 2건(제목 나열)" → 확인 또는 수동 지정.
- 계산은 스크립트로만: 현재 `python3 .superrelease/scripts/version.py get --scope <name>`, 결과 `python3 .superrelease/scripts/next-version.py --scope <name> --bump <level>` (수식어 제거는 `--release`).
- 그 scope의 `scheme.type`이 calver/headver면 bump 수준 없이 `python3 .superrelease/scripts/next-version.py --scope <name>`이 날짜·카운터로 다음 버전을 계산한다. `scheme.type`이 semver인 scope 중 `preRelease.style`이 counter인 scope는 pre-release 발행에 `--prerelease <그 scope의 qualifier>`, 정식 승격에 `--release`를 쓴다.

## 4. 버전 반영

`python3 .superrelease/scripts/version.py set <버전> --scope <name>` — 그 scope의 전 위치 동기 수정. 7단계 프리뷰에 포함하라.

## 5. 릴리스 노트 (scope별)

`.claude/skills/release-notes/SKILL.md` 절차로 scope별 초안을 쓰고, 그 scope의 config `notes.destinations`별로 반영하라:

- `changelog`: 루트 CHANGELOG.md 최신 항목으로 `## <scope>@<version>` 삽입 (Unreleased 섹션이 있으면 그 아래)
- `release-file`: `<notes.perReleasePath><scope>@<version>.md` 파일 생성 (notes.template 사용)
- `github-release`: 8단계 Release 본문으로 사용
- `fragment`가 그 scope의 목적지면: 그 scope 경로의 `changelog.d/*.md` 조각을 category별(`breaking`→Breaking Changes, `feature`→하이라이트·변경, `fix`·`misc`(및 미인식)→변경)로 취합해 노트 소스로 쓰고, 소비한 조각을 릴리스 커밋에서 `git rm`으로 삭제하라(7단계 프리뷰에 명시). fragment는 최소 1개 sink 목적지와 함께 쓰며, bump 결정에는 쓰지 않는다(bump는 커밋·PR 소스 그대로).
{{#if bundle.enabled}}- **bundle 라운드 노트**: `{{bundle.notesPath}}`의 `*.md` 파일명(확장자 제거)을 모아 `python3 .superrelease/scripts/next-version.py --scheme calver --pattern {{bundle.scheme.pattern}} --today <오늘 YYYY-MM-DD> --current-among <파일명들…>`로 다음 라운드 번호를 계산하라(파일이 하나도 없으면 `--current ""` — 첫 라운드). `.superrelease/templates/notes-bundle.md` 골격으로 `{{bundle.notesPath}}<라운드>.md`를 작성한다 — 이번 라운드에 릴리스되는 scope×버전 표(미변경 scope는 현재 버전 병기)·하이라이트·scope별 변경·Breaking rollup. 릴리스 커밋에 포함하라.
{{/if}}
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

{{#if repo.releasePath == "direct-push"}}확인 후: scope별로 버전 파일 + 노트 파일을 커밋하고(여러 scope면 scope당 1커밋) `git push origin {{repo.defaultBranch}}`.{{else}}확인 후 **릴리스 PR 경로**: 릴리스 브랜치 하나를 만들어({{#if bundle.enabled}}`release/<라운드>` — 5단계의 라운드 번호{{else}}`release/<첫 scope>@<버전>`, 복수 대상이면 `+N` 접미{{/if}} — 브랜치명을 프리뷰에 명시) scope당 1커밋으로 쌓고 push → PR 1건 생성(`gh pr create --base {{repo.defaultBranch}}` — 제목에 포함 릴리스를 나열하고, 본문은 `.superrelease/templates/release-pr-body.md` 골격에 scope별 섹션을 채워라; gh 미가용이면 GitHub MCP 폴백) → **중단한다**(태그는 머지 후).{{#if repo.branching == "gitflow"}} 릴리스 PR은 **머지 커밋**(`gh pr merge --merge`, --no-ff)으로 머지하라 — squash로 머지하면 `origin/{{repo.defaultBranch}}..{{repo.developBranch}}` 범위 계산과 back-merge가 어그러진다.{{/if}} 머지 후 재개: 1단계 preflight 6의 {{#if repo.branching == "gitflow"}}중단 상태 감지가 잡는다 — PR 머지 확인(`gh pr view <릴리스 브랜치명> --json state,mergedAt`) 후 `git checkout {{repo.defaultBranch}} && git pull` 하고 {{#if derived.anyTagEnabled}}scope별로 8단계(태그)부터{{else}}9단계(back-merge)부터{{/if}} 이어가라{{else}}scope별 중단 상태 감지가 잡는다 — PR 머지 확인(`gh pr view <릴리스 브랜치명> --json state,mergedAt`) 후 `git checkout {{repo.defaultBranch}} && git pull` 하고 scope별로 8단계(태그)부터 이어가라{{/if}}. PR이 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}

{{#if derived.anyTagEnabled}}## 8. 태그{{#if github.release}} + GitHub Release{{/if}} (scope별)

- 태그명: 그 scope의 config `tag.format`에서 {version}에 릴리스 버전 대입. `tag.enabled`가 false인 scope는 이 단계를 건너뛴다.
- push 직전 충돌 재확인: `git ls-remote --tags origin <태그>` 가 비어 있어야 함 — 결과가 있으면 **즉시 중단** (동시 릴리스 락, 버전 재사용 금지).
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
- 그 scope의 `tag.movingMajorTag`가 true면(semver 정식 릴리스에 한해) `git tag -f v<major>` → `git push -f origin v<major>` — force-push 경고를 프리뷰에 명시하고 개별 확인을 받아라. `preRelease.style`이 counter인 scope의 pre-release 버전이면 GitHub Release에 `--prerelease` 플래그를 붙인다.
{{#if github.release}}- gh 경로: {{#if github.generateNotes}}`gh api repos/{owner}/{repo}/releases/generate-notes -f tag_name=<태그>` 뼈대를 참고하되 본문은 5단계 노트로 게시 — {{/if}}`gh release create <태그> --title "<scope>@<version>" --notes-file <노트 파일>`
- MCP 폴백 경로: generate-notes 뼈대 없이 5단계 노트로 Release를 생성하라.
{{/if}}
{{/if}}## 9. post-release (scope별)

{{#if repo.branching == "gitflow"}}{{#if derived.anyTagEnabled}}태그 push 후{{else}}머지 확인 후{{/if}} **back-merge**로 `{{repo.developBranch}}` 브랜치를 동기화한다: `git checkout {{repo.developBranch}} && git pull` → `git merge {{repo.defaultBranch}}` (버전 파일 충돌은 `{{repo.defaultBranch}}` 쪽 릴리스 버전을 취하라 — 직후 복귀가 덮는다) → 프리뷰·확인 후 `git push origin {{repo.developBranch}}`. push가 거부되면(`{{repo.developBranch}}` 보호) back-merge PR을 만들어 머지하라.

{{/if}}그 scope의 config `postRelease.bump`가 next-snapshot이면 `python3 .superrelease/scripts/next-version.py --scope <name> --bump patch --qualifier <그 scope의 preRelease.qualifier>` → `version.py set --scope` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.releasePath == "release-pr"}}{{#if repo.branching == "gitflow"}} (gitflow: 이 복귀 커밋은 back-merge 후 `{{repo.developBranch}}`에서 scope별로 수행한다 — push가 거부되면 PR로.){{else}} (release-pr 레포: 복귀 커밋도 `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}}{{/if}} none이면 파일 버전을 그대로 둔다.
{{#unless repo.branching == "gitflow"}}
태그를 쓰지 않는 scope는 릴리스 후 config의 그 scope `anchor.value`를 릴리스 커밋 sha로 갱신해 함께 커밋하라.
{{/unless}}
## 실패 시

scope 단위로 어디까지 진행됐는지(파일 수정 / 커밋 / push / 태그 / Release)와 되돌리는 방법을 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 버전은 다음 패치로 덮고, 배포물 회수는 생태계 절차(npm deprecate, PyPI yank 등)를 안내하라.
````

주의(전체 교체 시 검증 포인트): trunk 렌더 바이트 불변이 깨지는 3대 원인 — ① 조건 밖 텍스트 오탈자 ② 개행을 `{{#if}}` 밖에 둠 ③ §8 게이트·§9 unless로 인한 빈 줄 수 변화. Step 4의 golden 확인이 잡는다. 기존 §8은 무조건 렌더였고 §9 앞뒤 빈 줄 구조를 그대로 유지해야 한다: `{{#if derived.anyTagEnabled}}## 8. …{{/if}}## 9.` 사이 개행이 태그 있음 config에서 기존과 동일한지 diff로 대조하라.

- [ ] **Step 4: 테스트 + 골든 무변경 확인**

Run: `python3 -m unittest discover -s tests -q` → PASS 후
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 출력 **없음** — trunk 모노레포 골든 3종(pnpm/backfill/monorepo-release-pr) 전부 바이트 불변. 바뀐 파일이 보이면 위 검증 포인트를 diff로 확인.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/release-monorepo/SKILL.md tests/test_assets.py
git commit -m "feat(assets): release-monorepo gitflow 라운드 릴리스 + bundle 노트 단계

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: hotfix 스킬 — gitflow 모노레포 분기

**Files:**
- Modify: `skills/init/assets/skills/hotfix/SKILL.md`
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: Task 4의 notes-bundle, Task 1의 `--current-among`.
- Produces: gitflow×independent에서 scope 지정 patch 릴리스. 단일 gitflow·유지보수 라인 렌더는 바이트 불변.

- [ ] **Step 1: 실패하는 테스트 작성** — `MonorepoAssetsTest`에 추가:

```python
    def test_hotfix_gitflow_monorepo_branch(self):
        ctx = gitflow_mono_ctx()
        out = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("--scope", out)
        self.assertIn("hotfix/<첫 scope>@<패치 버전>", out)
        self.assertIn("--current-among", out)      # bundle 라운드 노트
        self.assertLessEqual(len(out.splitlines()), 149)
```

그리고 `SkillAssetsTest`에 단일 gitflow 불변 핀:

```python
    def test_hotfix_gitflow_single_has_no_monorepo_prose(self):
        out = self.render_asset("skills/hotfix/SKILL.md", gitflow_ctx())
        self.assertNotIn("--scope", out)
        self.assertNotIn("hotfix/<첫 scope>@", out)
        self.assertNotIn("--current-among", out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest.test_hotfix_gitflow_monorepo_branch -v; cd ..`
Expected: ERROR 또는 FAIL (MonorepoAssetsTest에 render_asset이 ctx 필수 — 기존 시그니처 확인: `def render_asset(self, rel, ctx=None)` 형태면 그대로, 아니면 ctx 전달)

- [ ] **Step 3: 템플릿 수정** — `skills/init/assets/skills/hotfix/SKILL.md`의 gitflow 가지들 안에 `{{#if repo.monorepoStrategy == "independent"}}` 분기 삽입 (단일 렌더 바이트 불변 — else 가지에 기존 텍스트 보존). 수정 지점 4곳:

(a) §1 대상 결정의 gitflow 가지 — 기존 두 번째 불릿(`- 수정이 이미 …`) **앞**에 삽입:

```
{{#if repo.monorepoStrategy == "independent"}}- 수정이 영향을 주는 **scope**를 확정하라 — 사용자가 지정하지 않았으면 수정 파일 경로를 각 scope의 `path`와 대조해 판별하고 확인받아라(복수 가능).
{{/if}}
```

(b) §4 patch 버전 — 기존 첫 불릿의 명령을 조건 분기:

```
- 다음 버전은 **patch 고정**: `python3 .superrelease/scripts/next-version.py{{#if repo.monorepoStrategy == "independent"}} --scope <name>{{/if}} --bump patch` (현재 버전은 {{#if repo.branching == "gitflow"}}`{{repo.defaultBranch}}`의{{else}}라인의{{/if}} 파일에서 자동으로 읽힌다){{#if repo.monorepoStrategy == "independent"}} — 영향 scope마다 반복한다{{/if}}
```

버전 반영 불릿도 동일하게: `` `python3 .superrelease/scripts/version.py set <패치 버전>{{#if repo.monorepoStrategy == "independent"}} --scope <name>{{/if}}` ``

그리고 §4 끝에 bundle 블록 추가:

```
{{#if bundle.enabled}}- **bundle 라운드 노트**: hotfix도 라운드다 — `{{bundle.notesPath}}`의 파일명들로 `python3 .superrelease/scripts/next-version.py --scheme calver --pattern {{bundle.scheme.pattern}} --today <오늘 YYYY-MM-DD> --current-among <파일명들…>` 라운드 번호를 계산하고(파일이 없으면 `--current ""`), `.superrelease/templates/notes-bundle.md` 골격으로 `{{bundle.notesPath}}<라운드>.md`를 작성해 hotfix 커밋에 포함하라(수정된 scope만 표에 "이번 라운드"로 표시).
{{/if}}
```

(c) §5 릴리스 PR 가지의 브랜치명 — 기존 `git checkout -b hotfix/<패치 버전>`을:

```
`git checkout -b {{#if repo.monorepoStrategy == "independent"}}hotfix/<첫 scope>@<패치 버전>{{else}}hotfix/<패치 버전>{{/if}}`
```

(d) §6 태그: 기존 "release 스킬 7단계와 동일하다" 문장을:

```
release 스킬 {{#if repo.monorepoStrategy == "independent"}}8단계와 동일하다(`tag.enabled`인 scope만, scope별 `tag.format`){{else}}7단계와 동일하다{{/if}}: `git ls-remote --tags origin <태그>`로 충돌 재확인(결과가 있으면 즉시 중단) → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.
```

§7의 SNAPSHOT 복귀 명령에도 `{{#if repo.monorepoStrategy == "independent"}} --scope <name>{{/if}}`을 같은 방식으로 삽입한다 (`next-version.py --bump patch --qualifier …`와 `version.py set` 둘 다, "mutable scope마다 반복" 문구 포함).

- [ ] **Step 4: 테스트 + 골든 확인**

Run: `python3 -m unittest discover -s tests -q && python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: 테스트 PASS, `git status` 출력 없음 (gitflow-app·hotfix-library의 hotfix 렌더 불변 — 모노레포 분기가 단일 config에서 0바이트 collapse)

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/hotfix/SKILL.md tests/test_assets.py
git commit -m "feat(assets): hotfix gitflow 모노레포 분기 — scope 지정 patch + bundle 라운드

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 골든 `gitflow-monorepo-bundle` (imstargg 모양)

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/gitflow-monorepo-bundle/expected/**` (update_golden 산출)

**Interfaces:**
- Consumes: Task 2의 validate 허용 조합, Task 4~7의 렌더 결과.

- [ ] **Step 1: config 추가** — `tests/golden_configs.py`의 `gitflow_app` 뒤에:

```python
def gitflow_monorepo_bundle():
    # imstargg 모양: 공유 gradle.properties 키 3개 + frontend json-path,
    # 전 scope tagless, gitflow(develop), bundle 라운드 노트, GitHub Release 없음
    def app(name, path, locations):
        return {"name": name, "path": path,
                "scheme": {"type": "semver", "pattern": None},
                "versionLocations": locations,
                "tag": {"enabled": False, "format": name + "@{version}",
                        "annotated": False, "signed": False,
                        "movingMajorTag": False},
                "bump": {"mode": "auto-confirm",
                         "sources": ["conventional-commits"],
                         "fallback": "diff", "compatCheck": None},
                "preRelease": {"style": "mutable", "qualifier": "SNAPSHOT"},
                "devChannel": {"enabled": False, "qualifier": None,
                               "immutableId": []},
                "postRelease": {"bump": "next-snapshot"},
                "notes": {"destinations": ["changelog"], "language": "ko",
                          "audience": "developers", "tone": "neutral",
                          "template": "notes-package.md",
                          "perReleasePath": "docs/releases/"},
                "anchor": {"type": "ref", "value": None},
                "dependents": []}

    def prop(key):
        return [{"file": "../../gradle.properties",
                 "type": "properties-key", "key": key}]

    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = "independent"
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["repo"]["releaseCommitFormat"] = "chore(release): {scope}@{version}"
    cfg["github"] = {"release": False, "generateNotes": False,
                     "releaseYml": False}
    cfg["bundle"] = {"enabled": True,
                     "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                     "notesPath": "docs/releases/"}
    cfg["scopes"] = [
        app("core-api", "backend/apps/api", prop("apiVersion")),
        app("core-batch", "backend/apps/batch", prop("batchVersion")),
        app("core-worker", "backend/apps/worker", prop("workerVersion")),
        app("frontend", "frontend",
            [{"file": "package.json", "type": "json-path", "path": "version"}]),
    ]
    return cfg
```

`GOLDEN` 딕셔너리의 `"gitflow-app": gitflow_app,` 뒤에 `"gitflow-monorepo-bundle": gitflow_monorepo_bundle,` 추가.

- [ ] **Step 2: 골든 생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `?? tests/golden/gitflow-monorepo-bundle/` (신규 트리)만. 생성 트리에 `.claude/skills/release/SKILL.md`(monorepo 변형)·`release-notes`·`hotfix`·`changed-packages.py`·`notes-package.md`·`notes-bundle.md`·`release-pr-body.md`가 있고 `.github/release.yml`은 **없어야** 한다.

- [ ] **Step 3: 스냅샷 내용 스팟 검사**

Run: `grep -c "current-among" "tests/golden/gitflow-monorepo-bundle/expected/.claude/skills/release/SKILL.md"` → 1 이상
Run: `grep -c "## 8. 태그" "tests/golden/gitflow-monorepo-bundle/expected/.claude/skills/release/SKILL.md"` → 0 (전 scope tagless collapse)

- [ ] **Step 4: 전체 테스트**

Run: `python3 -m unittest discover -s tests -q`
Expected: PASS (test_golden이 신규 케이스 포함 통과)

- [ ] **Step 5: 커밋**

```bash
git add tests/golden_configs.py tests/golden/gitflow-monorepo-bundle
git commit -m "test: gitflow-monorepo-bundle 골든 — imstargg 모양 대표 스냅샷

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: scan.py — bundleNotesGuess

**Files:**
- Modify: `skills/init/scripts/scan.py` (scan_changelog)
- Test: `tests/test_scan.py`

**Interfaces:**
- Produces: 리포트 `changelog.bundleNotesGuess` = `{"dir": "docs/release/", "notes": ["2026.05.0", …]}` 또는 `null`. Task 10의 init 프로즈가 추천 근거로 소비.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_scan.py`에 (기존 클래스 스타일에 맞춰 scan 실행 후 JSON 파싱하는 테스트가 있는 클래스에) 추가:

```python
    def test_bundle_notes_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "docs" / "release" / "2026.05.0.md", "x\n")
            write(repo / "docs" / "release" / "2026.05.1.md", "x\n")
            write(repo / "docs" / "release" / "README.md", "x\n")
            r = run_script(SCAN, "--repo", repo)
            data = json.loads(r.stdout)
            guess = data["changelog"]["bundleNotesGuess"]
            self.assertEqual(guess["dir"], "docs/release/")
            self.assertEqual(guess["notes"], ["2026.05.0", "2026.05.1"])

    def test_bundle_notes_guess_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_script(SCAN, "--repo", tmp)
            data = json.loads(r.stdout)
            self.assertIsNone(data["changelog"]["bundleNotesGuess"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v 2>&1 | tail -5; cd ..`
Expected: KeyError/FAIL

- [ ] **Step 3: 구현** — scan.py 상단 상수에 추가:

```python
BUNDLE_NOTE_RE = re.compile(r"^\d{4}[.\d]+$")
BUNDLE_NOTE_DIRS = ("docs/releases", "docs/release")
```

`scan_changelog` 교체:

```python
def scan_changelog(repo):
    bundle_guess = None
    for d in BUNDLE_NOTE_DIRS:
        base = repo / d
        if not base.is_dir():
            continue
        notes = sorted(p.stem for p in base.glob("*.md")
                       if BUNDLE_NOTE_RE.match(p.stem))
        if notes:
            bundle_guess = {"dir": d + "/", "notes": notes}
            break
    return {"changelogMd": (repo / "CHANGELOG.md").is_file(),
            "releasesDir": (repo / "docs" / "releases").is_dir(),
            "fragmentsDir": (repo / "changelog.d").is_dir(),
            "bundleNotesGuess": bundle_guess}
```

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_scan -v 2>&1 | tail -3; cd ..`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat(scan): bundleNotesGuess — 기존 CalVer 라운드 노트 디렉터리 감지

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: init SKILL.md — 질문·지원 범위 갱신

**Files:**
- Modify: `skills/init/SKILL.md`

**Interfaces:**
- Consumes: Task 9의 `bundleNotesGuess`, Task 2의 validate 규칙.

- [ ] **Step 1: 편집 4곳** (Edit 도구, old→new 정확 치환):

(a) 번들 2의 태그 문장 — `태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed` 를 다음으로 교체:

```
태그 파생 여부(기본 yes; **gitflow면 "태그 없음"도 유효한 선택** — 범위 기준이 기본 브랜치라 태그 없이 성립하며, 단 github.release는 태그가 필요하므로 함께 비활성화됨을 안내)·prefix(v 유무)·annotated(기본 yes)·signed
```

(b) 번들 5 끝에 추가 (`/ GitHub Release 사용·generateNotes 하이브리드·release.yml 생성 여부` 뒤):

```
 / **(independent 모노레포) bundle 라운드 노트** — 릴리스 라운드마다 CalVer 이름의 묶음 노트 파일(`<notesPath><라운드>.md`)을 만들지 묻는다. 스캔 `changelog.bundleNotesGuess`가 있으면(기존 라운드 노트 운용) 그 디렉터리·관측 패턴을 근거로 선두 추천. pattern 기본 `YYYY.0M.MICRO`, notesPath 기본 `docs/releases/`. 채택 시 top-level `bundle` 객체(`{"enabled": true, "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"}, "notesPath": "docs/releases/"}`)를 기록한다 — 라운드 SSOT는 notesPath의 최신 파일명이며 태그·버전 파일·config 상태를 만들지 않는다
```

(c) 번들 6 — `gitflow는 단일 스킬 레포 한정(모노레포 조합은 render 거부 — 미지원 표시).` 를 다음으로 교체:

```
gitflow는 단일 레포와 independent 모노레포를 지원한다(모노레포면 release 스킬이 develop→기본 브랜치 라운드 릴리스를 수행하고, 범위 기준은 태그가 아니라 기본 브랜치다).
```

(d) 지원 범위와 제약 절 — 브랜칭·노트 두 줄을 교체하고 bundle 줄을 추가:

브랜칭 줄:
```
- 브랜칭: trunk / gitflow(release-pr 전용 — develop cut → 기본 브랜치 태그 → back-merge 정식 사이클, production hotfix 포함; 단일 레포·independent 모노레포 지원, gitflow에서는 태그가 선택사항) 지원 — direct-push gitflow는 지원하지 않는다
```

노트 목적지 줄 끝에 추가:
```
 / bundle 라운드 노트(independent 모노레포 — CalVer 파일명 라벨, top-level bundle 객체): 지원
```

tagless 관련: 커밋 경로 줄을 다음으로 교체:
```
- 커밋 경로: direct-push | release-pr(보호 브랜치 — PR 생성 후 중단, 머지 후 태그 재개) 지원 — trunk×release-pr는 태그 필수(tagless는 direct-push 또는 gitflow에서만)
```

- [ ] **Step 2: 검증**

Run: `wc -l skills/init/SKILL.md` → ≤500 확인
Run: `grep -c "bundle" skills/init/SKILL.md` → 2 이상

- [ ] **Step 3: 커밋**

```bash
git add skills/init/SKILL.md
git commit -m "feat(init): bundle 질문·gitflow 모노레포/tagless 안내·지원 범위 갱신

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: 문서 — README×2 · CLAUDE.md · CHANGELOG · references

**Files:**
- Modify: `README.md`, `README_KO.md`, `CLAUDE.md`, `CHANGELOG.md`, `skills/init/references/branching-and-release-path.md`, `skills/init/references/monorepo.md`

- [ ] **Step 1: README.md** —
  - Not planned 목록에서 `monorepo × gitflow,` 삭제, `release trains,` → `release trains (root tags),`.
  - Branching 표의 gitflow 행 "Fits/Release path"를 갱신: `single-repo and independent-monorepo projects, release-pr only (cut from develop → merge to main → tag (optional) → back-merge)` / 그 아래 한계 문단을 `direct-push gitflow is not supported; on gitflow, tags are optional (the default branch is the range anchor).`로 교체.
  - Editing config.json 표에 행 추가: `| bundle | {enabled, scheme: calver+pattern, notesPath} | independent monorepos: CalVer-named round note bundling each release round |`
  - 유즈케이스 워크스루 2의 "Honest limits" 불릿을 교체: gitflow 모노레포·bundle 지원 문구 + trunk×release-pr×tagless만 남는 한계.
  - Roadmap에 추가: `- **M5 (unreleased)** — gitflow monorepos (round release from develop), tag-optional gitflow, CalVer bundle round notes (imstargg-style)`.
- [ ] **Step 2: README_KO.md** — 위와 동일 내용 한국어 미러 (기존 병기 문장 톤 유지).
- [ ] **Step 3: CLAUDE.md** — 지원 현황 줄을 갱신: `브랜칭(trunk/gitflow — gitflow는 단일+independent 모노레포·태그 선택)` / `노트 목적지 4종(…) + bundle 라운드 노트` 추가.
- [ ] **Step 4: CHANGELOG.md** — `## [Unreleased]`에 `### Added` 섹션(기존 Removed 위) 추가:

```markdown
### Added

- **gitflow 모노레포** — independent 모노레포가 gitflow(develop→기본 브랜치 라운드 릴리스)를
  지원한다. 범위·변경 감지·중단 감지의 앵커는 태그가 아니라 기본 브랜치다
  (`changed-packages.py --ref origin/<main>`), 단일 레포 gitflow도 같은 앵커로 통일했다.
- **tagless gitflow** — gitflow에서는 태그가 선택사항이다(브랜치 상태로 재개 감지).
  trunk×release-pr는 종전대로 태그 필수.
- **bundle 라운드 노트** — independent 모노레포의 릴리스 라운드마다 CalVer 이름의 묶음
  노트 파일(`docs/releases/2026.07.1.md` 류)을 만든다. top-level `bundle` 객체,
  `notes-bundle.md` 템플릿, `next-version.py --current-among`(후보 중 최댓값 기반 다음
  라운드 계산) 추가. hotfix도 라운드로 취급한다.
```

- [ ] **Step 5: references** —
  - `branching-and-release-path.md`: gitflow 절이 "단일 레포 한정"을 언급하면 모노레포 지원·태그 선택·main 앵커로 갱신(해당 문구를 grep으로 찾아 교체).
  - `monorepo.md`: "지원 현황" 절 끝에 한 문단 추가: `gitflow 모노레포와 bundle 라운드 노트(CalVer 파일명 라벨 — 이중 체계 train과 달리 태그·별도 스킬 없이 릴리스 흐름에 통합)는 M5부터 지원된다.` 그리고 이중 체계 문단 끝에 `조합 공표가 목적이라면 bundle 라운드 노트가 지원되는 대안이다.` 추가.
- [ ] **Step 6: 전체 검증 + 커밋**

```bash
python3 -m unittest discover -s tests -q && claude plugin validate . --strict
git add README.md README_KO.md CLAUDE.md CHANGELOG.md skills/init/references
git commit -m "docs: M5 문서 반영 — gitflow 모노레포·tagless gitflow·bundle 라운드 노트

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: 최종 검증 게이트

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트** — `python3 -m unittest discover -s tests -q` → OK
- [ ] **Step 2: 플러그인 검증** — `claude plugin validate . --strict` → passed
- [ ] **Step 3: 골든 범위 최종 확인** — `git status --porcelain tests/golden` → 깨끗(전부 커밋됨), `git log --oneline main..HEAD -- tests/golden | head` 로 골든 변경이 gitflow-app(M) + gitflow-monorepo-bundle(A)뿐인지 확인
- [ ] **Step 4: dogfood 확인** — self-render 테스트가 스위트에 포함되어 통과함을 확인(이 레포는 trunk 단일 config라 재렌더 불필요 — 실패 시 `python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo .` 재렌더 후 커밋)
- [ ] **Step 5: 스펙 완료 기준 대조** — 스펙 15절 5개 항목을 하나씩 확인하고 미충족 항목이 있으면 해당 Task로 돌아간다

## Self-Review 결과

- 스펙 커버리지: 3절→T4·T6, 4절→T5·T6, 5절→T1, 6절→T6, 7절→T5, 8절→T7, 9절→T2, 10절→T9·T10, 11절→T11, 12절→T2·T5~T8, 15절→T12. 누락 없음.
- 타입 일관성: `--current-among` 호출 형태(T1 정의 ↔ T6·T7 프로즈), `derived.anyTagEnabled`(T3 정의 ↔ T5·T6 소비), `bundle` 스키마(T2 ↔ T4 when ↔ T6·T7·T8·T10) 일치 확인.
- 주의: T6은 전체 파일 교체라 트렁크 바이트 불변 리스크가 가장 크다 — Step 4의 골든 무변경 확인이 필수 게이트다.
