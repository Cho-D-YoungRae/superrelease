# M3c-3b — 모노레포 backfill + backfill 하드닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** M3c-2의 단일 scope CHANGELOG backfill을 `independent` 모노레포로 확장하고(scope별 `<scope>@<version>` 태그 네임스페이스 순회), M3c-2 후속 5건(#2~#6)을 닫는다.

**Architecture:** backfill 스킬 한 파일에 `{{#if repo.monorepoStrategy == "independent"}}` 순회 블록 + `{{#if repo.releasePath == "release-pr"}}` 커밋경로 블록을 추가한다(단일 scope 렌더는 #5 명확화 외 의미 불변). render는 `backfill+independent` 거부를 제거하고 `backfill+전-scope-tagless` 거부를 추가한다. 스크립트·엔진 무변경, 유일한 Python 변경은 `validate_config`.

**Tech Stack:** Python 3.9+ stdlib, 동결 template dialect, unittest, golden 스냅샷.

## Global Constraints

- 동결 template dialect — 확장 금지. 조건 블록의 개행은 `{{#if}}` **안**에 두어 미해당 config에서 0바이트 collapse(기존 골든 바이트 불변).
- 생성 SKILL.md ≤150줄(≤149 assert), init SKILL.md ≤500줄.
- render 엔진·스크립트(version.py·next-version.py·changed-packages.py) 산술·조작 **무변경**. 유일한 Python 변경은 `skills/init/scripts/render.py`의 `validate_config` 규칙 조정(independent 거부 −1, 전-scope-tagless 거부 +1).
- 생성 backfill 스킬 자립성: `.superrelease/`·`.claude/` 상대 경로만. 플러그인 경로 참조 금지. 생성 스킬·템플릿 프로즈 참조 허용.
- 모노레포 backfill 헤더 = `## [<scope>@<version>] - {date}`. 단일 scope 헤더 = `## [<version>] - {date}`(changelog-entry.md 골격).
- backfill은 CHANGELOG.md만 쓴다 — 태그·버전 bump·push 없음(모노레포도 동일).
- 테스트 러너는 unittest(pytest 아님). 전체: `python3 -m unittest discover -s tests -q`. 개별 모듈은 `cd tests && python3 -m unittest <module> -v`(`python3 -m unittest tests.<module>`은 `tests/__init__.py` 부재로 실패).
- exit code 0/1/2. 코드·메시지 영어, 생성 문서·init 프로즈 한국어.
- TDD. 각 태스크 끝 전체 스위트 통과. 최종 `claude plugin validate . --strict` + 골든 범위 확인.

**베이스 스펙:** `docs/superpowers/specs/2026-07-14-superrelease-m3c3b-monorepo-backfill-design.md`. **베이스 커밋:** main `f3c04da`.

---

### Task 1: render.py 규칙 조정 (independent 거부 제거 + 전-scope-tagless 거부)

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`, 현재 line 220-222 backfill 규칙 교체)
- Test: `tests/test_render_pipeline.py` (`test_backfill_rejected_for_independent` 교체)

**Interfaces:**
- Consumes: `validate_config(config)` — 지역변수 `strategy`, `scopes`(config["scopes"]), `repo`.
- Produces: backfill은 이제 independent 모노레포에서 통과하고, 전 scope가 tagless면 거부. Task 2·4가 backfill+independent 유효 config를 렌더한다.

- [ ] **Step 1: 실패/교체 테스트 작성**

`tests/test_render_pipeline.py`에서 기존 `test_backfill_rejected_for_independent`(현재 line 157-163):

```python
    def test_backfill_rejected_for_independent(self):
        cfg = monorepo_config()
        cfg["repo"]["backfill"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("backfill", r.stderr)
```

를 다음 두 메서드로 **교체**한다:

```python
    def test_backfill_ok_for_independent(self):
        cfg = monorepo_config()  # 2 scopes, both tag.enabled=True
        cfg["repo"]["backfill"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_backfill_rejected_when_all_scopes_tagless(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["backfill"] = True
        cfg["scopes"][0]["tag"]["enabled"] = False
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("tagged scope", r.stderr)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v 2>&1 | grep -E "backfill|FAIL|ERROR"; cd ..`
Expected: `test_backfill_ok_for_independent` FAIL(현재 independent+backfill이 거부되어 returncode 1 ≠ 0), `test_backfill_rejected_when_all_scopes_tagless` FAIL(현재 tagless 거부 규칙 없음).

- [ ] **Step 3: render.py 규칙 교체**

`skills/init/scripts/render.py`에서 backfill 규칙(현재 line 220-222):

```python
    if repo.get("backfill") and strategy == "independent":
        problems.append("repo.backfill is not supported with the independent "
                        "monorepo strategy (monorepo backfill is deferred)")
```

를 다음으로 **교체**:

```python
    if repo.get("backfill") and scopes and all(
            not (s.get("tag") or {}).get("enabled", True) for s in scopes):
        problems.append("repo.backfill requires at least one tagged scope; "
                        "backfill walks tag intervals and cannot run when "
                        "every scope is tagless (tag.enabled false)")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v 2>&1 | tail -3; cd ..`
Expected: OK.

- [ ] **Step 5: 전체 스위트**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 169 tests ... OK` (168 − 1 삭제 + 2 신규).

- [ ] **Step 6: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: render — backfill independent 허용, 전 scope tagless면 거부 (M3c-3b)"
```

---

### Task 2: backfill 스킬 확장 (#5·#4·모노레포 분기·tagless skip) + 렌더 스모크

**Files:**
- Modify: `skills/init/assets/skills/backfill/SKILL.md` (전체 교체)
- Test: `tests/test_assets.py` (`test_backfill_skill_renders_clean`(line 198) 뒤에 4 메서드 추가)

**Interfaces:**
- Consumes: render 컨텍스트 `repo.monorepoStrategy`·`repo.releasePath`·`repo.mergePolicy`·`project.name`·`scope`. `mono_ctx()`(independent)·`base_ctx()`(단일) 헬퍼는 test_assets.py에 이미 있다.
- Produces: `.claude/skills/backfill/SKILL.md`(dest, `when: repo.backfill` — manifest 무변경). Task 4 골든이 렌더 결과를 고정한다.

- [ ] **Step 1: backfill 스킬 전체 교체**

`skills/init/assets/skills/backfill/SKILL.md`를 아래 전문으로 교체:

````markdown
---
name: backfill
description: {{project.name}} 프로젝트의 CHANGELOG를 과거 태그 이력에서 소급 작성한다. 사용자가 백필, backfill, 체인지로그 소급, 과거 릴리스 노트 채워줘, CHANGELOG 이력 정리, 예전 태그 노트 만들어줘 등 기존 태그에서 누락된 릴리스 이력을 채우는 요청을 하면 반드시 이 스킬을 사용한다.
---

# backfill — {{project.name}} CHANGELOG 이력 소급 작성

이미 태그가 쌓여 있는데 CHANGELOG에 기록이 없거나 빠진 릴리스가 있을 때, 태그 구간별 커밋으로 과거 릴리스 항목을 사후 작성해 CHANGELOG.md를 채운다. **일회성 정리 작업**이며, 태그·버전 bump·push는 하지 않고 CHANGELOG.md만 쓴다.{{#if repo.monorepoStrategy == "independent"}} 이 레포는 independent 모노레포이므로 scope마다 태그 네임스페이스를 따로 순회한다(아래 "모노레포 순회" 참조).{{/if}}

공통 규칙:

- 부작용 있는 동작은 **dry-run 프리뷰 → 사용자 확인 → 실행**. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
- 이 스킬은 CHANGELOG.md 외 어떤 파일도 바꾸지 않는다 — 태그를 만들거나 옮기지 않고 버전 파일도 건드리지 않는다.

## 1. 대상 태그 구간 산출

- `git tag --list`로 태그를 모으고, config `scopes[0].tag.format`의 {version} 패턴에 맞는 태그만 남긴다(과거 혼재 포맷 태그는 무시 — 표준 포맷 규칙).
- 남은 태그를 버전 순으로 정렬한다. 연속한 두 태그 `A`, `B`가 한 구간 `A..B`이며, **이 구간은 태그 B 버전의 릴리스 항목**이다(그 사이 커밋이 B에서 나갔다). 가장 이른 태그는 선행 태그가 없으므로 그 태그 자체를 "Initial release"로 다룬다(`git log <firstTag>`).

## 2. 멱등 — 이미 있는 버전 건너뛰기

- CHANGELOG.md를 읽어 이미 항목이 있는 버전을 파악한다. 구간 `A..B`의 대상 버전 B가 이미 CHANGELOG에 있으면 **그 구간을 건너뛴다** — 누락된 구간만 채운다. 기존 항목과 Unreleased 섹션은 절대 건드리지 않는다.
- 채울 구간이 하나도 없으면 "CHANGELOG가 이미 최신입니다"라고 보고하고 멈춘다.

## 3. 구간별 항목 작성

- 채울 각 구간에 대해 `git log <A>..<B> --pretty=format:"%h %s"`로 커밋을 모은다.{{#if repo.mergePolicy == "squash"}} squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라.{{/if}}
- `.claude/skills/release-notes/SKILL.md` 절차로 읽되, 정식 릴리스 노트가 아니라 **간결한 이력 항목**을 목표로 한다 — `.superrelease/templates/changelog-entry.md` 골격(Keep a Changelog: Added/Changed/Fixed)에 `## [<버전 B>] - {date}` 헤더로 Changes 목록 위주로 짧게.
- 언어·어조는 config `scopes[0].notes`의 language·tone을 따른다.

## 4. dry-run 프리뷰 → 커밋

- 채울 구간 목록(버전·구간 범위)과 각 구간의 항목 초안을 미리 보여주고 확인받아라.
- 확인 후: CHANGELOG.md에 역시간순(최신이 위)으로 삽입한다. Unreleased 섹션이 있으면 그 아래.{{#if repo.releasePath == "release-pr"}} 이 레포는 보호 브랜치(release-pr)라 기본 브랜치에 직접 push할 수 없다 — CHANGELOG 변경을 `docs/backfill-changelog` 같은 브랜치에 커밋해 push하고 PR로 머지하라(backfill은 태그가 없어 머지 후 재개가 필요 없는 순수 문서 PR다).{{else}} CHANGELOG.md만 스테이징해 커밋한다(예: `docs: backfill CHANGELOG from tags`).{{/if}}
- **태그·버전 bump·push는 하지 않는다.**
{{#if repo.monorepoStrategy == "independent"}}
## 모노레포 순회 (independent)

위 §1~§4를 **각 scope마다** 반복하되 다음을 그 scope 값으로 바꾼다:

- §1 태그 필터: 그 scope의 config `tag.format`(`<scope>@{version}` 네임스페이스)에 맞는 태그만. `tag.enabled`가 false인 scope는 순회할 태그가 없으므로 **"태그 없음 — 건너뜀"으로 skip**한다.
- §3 커밋 수집: `git log <A>..<B> --pretty=format:"%h %s" -- <scope.path>`로 그 scope 경로 아래 커밋만.
- §3 헤더: `## [<scope>@<version B>] - {date}`. 언어·어조는 그 scope의 `notes`를 따른다.
- §2 멱등: CHANGELOG에서 그 `<scope>@<version>` 항목이 이미 있으면 그 구간을 건너뛴다.

전 scope의 채울 구간을 한 번에 dry-run으로 보여주고 확인받은 뒤 §4대로 삽입·커밋한다.
{{/if}}
## 실패 시

어디까지 작성·삽입했는지 명시하라. CHANGELOG.md는 태그와 무관하므로 되돌리기 안전하다 — 잘못됐으면 `git checkout CHANGELOG.md`로 취소하고 다시 시도하면 된다.
````

- [ ] **Step 2: 렌더 스모크 테스트 4건 작성**

`tests/test_assets.py`의 `test_backfill_skill_renders_clean`(현재 line 198-205) 바로 뒤에 삽입:

```python
    def test_backfill_monorepo_branch(self):
        out = self.render_asset("skills/backfill/SKILL.md", mono_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("모노레포 순회", out)
        self.assertIn("<scope>@", out)
        self.assertIn("건너뜀", out)  # tagless skip
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_backfill_single_omits_monorepo_block(self):
        out = self.render_asset("skills/backfill/SKILL.md")  # base_ctx = 단일
        self.assertNotIn("모노레포 순회", out)
        self.assertNotIn("<scope>@", out)

    def test_backfill_release_pr_path(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/backfill/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("docs/backfill-changelog", out)
        self.assertIn("PR로 머지", out)
        self.assertNotIn("CHANGELOG.md만 스테이징", out)  # else 분기 드롭

    def test_backfill_direct_push_commits_directly(self):
        out = self.render_asset("skills/backfill/SKILL.md")  # base_ctx = direct-push
        self.assertIn("CHANGELOG.md만 스테이징", out)
        self.assertNotIn("docs/backfill-changelog", out)
```

- [ ] **Step 3: 스모크 통과 + 줄 수 확인**

Run: `cd tests && python3 -m unittest test_assets -v 2>&1 | grep -E "backfill|FAIL|ERROR"; cd ..`
Expected: backfill 관련 5개(기존 clean + 신규 4) 전부 ok, FAIL/ERROR 없음. (`{{` 잔존이나 collapse 오류가 있으면 조건 블록 개행 위치 수정)

Run: `wc -l skills/init/assets/skills/backfill/SKILL.md`
Expected: ≤149줄.

- [ ] **Step 4: backfill-app 골든 재생성 (스킬과 함께 바뀐다)**

이 스킬 변경으로 기존 `backfill-app` 골든(옛 스킬 스냅샷)이 불일치해진다 — 스킬과 그 골든은 한 태스크에서 함께 갱신한다:

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: **오직** `tests/golden/backfill-app/...`만 변경(`M`). 다른 골든 트리(train-monorepo·pnpm-monorepo·release-pr-app 등)가 바뀌면 조건 블록 collapse가 샌 것 — 멈추고 Step 1 스킬의 `{{#if}}` 개행 위치를 조사(BLOCKED 보고).

Run: `git diff tests/golden/backfill-app -- '*/backfill/SKILL.md' | grep -E "^[-+]" | grep -v "^[-+][-+]" | head -20`
Expected: diff가 **#5 명확화 문장 + 인트로 "단일 scope 레포 전제다" 제거**에 한정(실측: 단일 direct-push 렌더 39줄). 그 외 문장 변경이 있으면 조사.

- [ ] **Step 5: 전체 스위트**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 173 tests ... OK` (169 + 4 스모크; backfill-app 골든을 함께 재생성했으므로 `test_golden`도 통과).

- [ ] **Step 6: 커밋**

```bash
git add skills/init/assets/skills/backfill/SKILL.md tests/test_assets.py tests/golden/backfill-app
git commit -m "feat: backfill 스킬 — 모노레포 순회 분기 + release-pr 경로 + 구간→버전 명확화 (M3c-3b)"
```

---

### Task 3: init 번들7 independent 확장 + #2 경고 + references 정합

**Files:**
- Modify: `skills/init/SKILL.md` (번들7 line 54 / backfill 각주 line 117 / 지원범위 line 143·146)
- Modify: `skills/init/references/monorepo.md` (line 88)
- Modify: `skills/init/references/edge-cases.md` (line 53)

**Interfaces:**
- Consumes: 없음(문서 정합).
- Produces: init이 independent 모노레포에도 backfill 제안 + #2 경고. references가 모노레포 backfill 지원 서술.

- [ ] **Step 1: 번들 7 — independent 확장 + #2 경고 + #3 노트**

`skills/init/SKILL.md` 번들 7(line 54)의 backfill 문구 부분:

```
기존 태그가 있고 CHANGELOG가 없거나 불완전한 **단일 scope 레포**면 CHANGELOG backfill을 제안하고 `repo.backfill: true`로 기록한다(백필 스킬 생성 — 태그 구간별 과거 이력을 CHANGELOG.md에 소급 작성, 태그·push 없음; independent 모노레포는 후속 M3c-3b로 잠그며 render가 그 조합을 거부한다)
```

를 다음으로 교체:

```
기존 태그가 있고 CHANGELOG가 없거나 불완전하면 CHANGELOG backfill을 제안하고 `repo.backfill: true`로 기록한다(백필 스킬 생성 — 태그 구간별 과거 이력을 CHANGELOG.md에 소급 작성, 태그·push 없음; **단일 scope와 independent 모노레포 모두 지원** — 모노레포는 scope별 `<scope>@<version>` 네임스페이스를 순회한다. 대상 scope에 `changelog` 목적지가 없으면 "평상시 릴리스가 CHANGELOG를 갱신하지 않아 소급본이 방치될 수 있음"을 경고하고 확인받아 `decisions`에 기록한다. 전 scope가 tagless면 render가 거부한다)
```

- [ ] **Step 2: backfill 각주 갱신**

`skills/init/SKILL.md` line 117:

```
- backfill: `repo.backfill: true`면 `.claude/skills/backfill/SKILL.md`가 생성된다 — 기존 태그 구간에서 CHANGELOG를 소급 작성하는 일회성 스킬(단일 scope 한정, independent 모노레포는 render가 거부).
```

를 다음으로 교체:

```
- backfill: `repo.backfill: true`면 `.claude/skills/backfill/SKILL.md`가 생성된다 — 기존 태그 구간에서 CHANGELOG를 소급 작성하는 일회성 스킬(단일 scope·independent 모노레포 지원 — 모노레포는 scope별 `<scope>@<version>` 태그 네임스페이스를 순회; 전 scope가 tagless면 render가 거부).
```

- [ ] **Step 3: 지원 범위 — train 줄에서 backfill 후속 제거**

`skills/init/SKILL.md` line 143 끝부분:

```
Spring Cloud식 3파트 CalVer·train 버전 파일(BOM)·모노레포 backfill은 후속(M3c-3b)
```

를 다음으로 교체:

```
Spring Cloud식 3파트 CalVer·train 버전 파일(BOM)은 후속
```

- [ ] **Step 4: 지원 범위 — backfill 줄 갱신**

`skills/init/SKILL.md` line 146:

```
- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: 단일 scope 레포 지원(모노레포는 M3c-3b)
```

를 다음으로 교체:

```
- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: 단일 scope·independent 모노레포 지원(모노레포는 scope별 `<scope>@<version>` 순회, 전 scope tagless면 render 거부)
```

- [ ] **Step 5: monorepo.md 지원 현황 갱신**

`skills/init/references/monorepo.md` line 88:

```
**이중 체계(dual-system)와 release-train은 M3c-3a에서 지원된다** — init이 이중 체계를 물어 `train` 객체를 기록하면 조건부로 `release-train` 스킬이 생성된다. 모노레포 backfill(패키지 태그 네임스페이스 순회)은 후속 M3c-3b로 남는다.
```

를 다음으로 교체:

```
**이중 체계(dual-system)와 release-train은 M3c-3a에서 지원된다** — init이 이중 체계를 물어 `train` 객체를 기록하면 조건부로 `release-train` 스킬이 생성된다. 모노레포 backfill도 M3c-3b에서 지원된다 — backfill 스킬이 scope별 태그 네임스페이스(`<scope>@{version}`)를 순회해 `## [<scope>@<version>]` 항목으로 소급한다(전 scope가 tagless면 render가 거부).
```

- [ ] **Step 6: edge-cases.md backfill 절 갱신**

`skills/init/references/edge-cases.md` line 53 끝 문장:

```
단일 scope 레포 한정이며, 모노레포 backfill은 후속(M3c-3b)이다.
```

를 다음으로 교체:

```
단일 scope와 independent 모노레포를 지원한다 — 모노레포는 scope별 `<scope>@<version>` 태그 네임스페이스를 순회하며 `## [<scope>@<version>]` 항목으로 채우고, 전 scope가 tagless면 render가 거부한다.
```

- [ ] **Step 7: 정합·줄 수·스위트 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -2 && wc -l skills/init/SKILL.md && grep -rn "모노레포 backfill은 후속\|모노레포는 M3c-3b\|render가 거부)" skills/init/ | grep -i backfill`
Expected: `Ran 173 tests ... OK`, init ≤500줄, backfill "후속" 잔재 없음(위 grep이 stale 후속 표시를 반환하지 않아야 함 — 갱신된 "지원" 문구만).

- [ ] **Step 8: 커밋**

```bash
git add skills/init/SKILL.md skills/init/references/monorepo.md skills/init/references/edge-cases.md
git commit -m "feat: init 번들7 backfill independent 확장 + #2 경고 + references 정합 (M3c-3b)"
```

---

### Task 4: 골든 재생성(backfill-app) + 신규(backfill-monorepo·backfill-release-pr) + 최종 검증

**Files:**
- Modify: `tests/golden_configs.py` (빌더 2개 + GOLDEN 엔트리 2개)
- Create: `tests/golden/backfill-monorepo/expected/**`, `tests/golden/backfill-release-pr/expected/**`

**Interfaces:**
- Consumes: `monorepo_config()`·`scope_config()`(helpers), Task 1 render 규칙, Task 2 backfill 스킬(+ Task 2에서 이미 재생성된 backfill-app 골든).
- Produces: 14 골든 트리(12 + 2 신규). backfill-app은 Task 2에서 재생성됐으므로 이 태스크는 신규 2트리만 추가한다.

- [ ] **Step 1: 골든 빌더 2개 + GOLDEN 엔트리 추가**

`tests/golden_configs.py`의 `backfill_app`(현재 line 86-91) 뒤에 추가:

```python
def backfill_monorepo():
    # independent + backfill + merge → 모노레포 순회 분기 + non-squash(#6) 한 트리에
    cfg = monorepo_config()
    cfg["repo"]["backfill"] = True
    cfg["repo"]["mergePolicy"] = "merge"
    return cfg


def backfill_release_pr():
    # backfill + release-pr → #4 release-pr 커밋경로 블록
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["backfill"] = True
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg
```

그리고 GOLDEN 딕셔너리(현재 `train-monorepo`로 끝남)에 두 엔트리 추가:

```python
GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app, "train-monorepo": train_monorepo,
          "backfill-monorepo": backfill_monorepo,
          "backfill-release-pr": backfill_release_pr}
```

- [ ] **Step 2: 골든 재생성**

Run: `python3 tests/update_golden.py`
Expected: 무오류.

- [ ] **Step 3: 골든 범위 확인 — 신규 2트리만 (backfill-app은 Task 2에서 이미 재생성)**

Run: `git status --porcelain tests/golden tests/golden_configs.py`
Expected: `tests/golden_configs.py` 수정 + `tests/golden/backfill-monorepo/...`(신규) + `tests/golden/backfill-release-pr/...`(신규)만. **backfill-app을 포함한 기존 12트리에 변경(`M`)이 있으면 회귀** — backfill-app은 Task 2에서 이미 현행화됐으니 여기서 또 바뀌면 안 되고, train-monorepo 등 다른 트리도 불변이어야 한다. 변경이 있으면 멈추고 조사(BLOCKED 보고).

- [ ] **Step 4: 신규 트리 내용 확인**

Run: `grep -l "모노레포 순회" tests/golden/backfill-monorepo/expected/.claude/skills/backfill/SKILL.md && grep -l "docs/backfill-changelog" tests/golden/backfill-release-pr/expected/.claude/skills/backfill/SKILL.md && grep -rL "{{" tests/golden/backfill-monorepo/expected/ tests/golden/backfill-release-pr/expected/ | head -1`
Expected: backfill-monorepo에 "모노레포 순회" 존재, backfill-release-pr에 "docs/backfill-changelog" 존재, 두 트리에 `{{` 없음.

- [ ] **Step 5: 전체 스위트 + strict**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 173 tests ... OK` (골든 테스트가 14트리 비교).

Run: `claude plugin validate . --strict 2>&1 | tail -2`
Expected: 통과.

- [ ] **Step 6: 커밋**

```bash
git add tests/golden_configs.py tests/golden/backfill-monorepo tests/golden/backfill-release-pr
git commit -m "test: 골든 backfill-monorepo·backfill-release-pr 신규 (M3c-3b)"
```

---

## Self-Review

**1. Spec coverage:**

| 스펙 섹션 | 태스크 |
|---|---|
| A. render(independent 거부 제거 + 전-scope-tagless 거부) | T1 |
| B. backfill 스킬(#5 명확화 · #4 release-pr · 모노레포 분기 · tagless skip) | T2 |
| C. init 번들7 independent 확장 + #2 경고 | T3 |
| D. references(monorepo·edge-cases) | T3 |
| E. 골든 backfill-app 재생성 | T2(스킬과 함께) |
| E. 골든 backfill-monorepo · backfill-release-pr 신규 | T4 |
| #6 non-squash 커버 | T4(backfill-monorepo가 merge) |
| 제약(스크립트 무변경·자립성·줄 수·strict) | 전 태스크 검증 스텝 |

갭 없음.

**2. Placeholder scan:** 모든 코드/문서 스텝에 실제 코드·old/new 문자열·명령·기대 출력. "TBD"·"적절히" 없음. 스킬 전문 수록.

**3. Type consistency:** 새 render 규칙 메시지 키워드 "tagged scope"가 T1 테스트 `assertIn("tagged scope")`와 일치. 스킬 렌더 문자열("모노레포 순회"·"<scope>@"·"건너뜀"·"docs/backfill-changelog"·"CHANGELOG.md만 스테이징")이 T2 스모크 assert 및 T4 골든 확인과 일치. 골든 빌더 2개(backfill_monorepo=independent+merge, backfill_release_pr=단일+release-pr)가 GOLDEN 엔트리와 이름 일치. 헤더 `## [<scope>@<version>]`가 스펙·스킬·references에서 동일.

**4. 테스트 수 회계:** 168(base) → T1: −1(삭제)+2(신규)=169 → T2: +4=173 → T3: 불변 173 → T4: 불변 173(골든 트리 12→14). 각 태스크 검증 스텝 기대치와 일치.
