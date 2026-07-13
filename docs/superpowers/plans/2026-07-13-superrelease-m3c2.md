# superrelease M3c-2 (CHANGELOG backfill) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 태그가 쌓인 단일 scope 레포에서 CHANGELOG.md를 태그 구간별로 소급 작성하는 조건부 생성 스킬 `backfill`을 추가한다 — `repo.backfill: true`로 게이트, hotfix 선례를 따른다.

**Architecture:** 신규 조건부 생성 스킬 `skills/backfill/SKILL.md`(manifest `when: "repo.backfill"`) + config `repo.backfill` 필드 + render.py `validate_config` 거부 규칙 1건(backfill + independent 모노레포) + init 번들 7·edge-cases 정합 + 골든 `backfill-app` 신규 1트리. 스크립트 산술·render 엔진 무변경. 기존 골든은 backfill 미설정(false) → 스킬 미생성 → 바이트 불변.

**Tech Stack:** Python 3.9+ stdlib, 동결 template dialect(엔진 수정 금지), git.

**스펙:** [docs/superpowers/specs/2026-07-13-superrelease-m3c2-changelog-backfill-design.md](../specs/2026-07-13-superrelease-m3c2-changelog-backfill-design.md). 베이스: main `07916b5`(M1~M3c-1, 154 테스트, 골든 10종). 실행 컨트롤러는 main에서 `feat/superrelease-m3c2` 브랜치를 만들어 진행한다.

## Global Constraints

- **스크립트 산술·render 엔진 무변경.** version.py·next-version.py·changed-packages.py·scan.py, render.py 엔진부(render_template/evaluate/parse/tokenize) 수정 금지. 유일한 Python 변경은 render.py **`validate_config` 규칙 1건**(render.py는 골든-복사 대상 아님, 골든 무영향).
- **골든 규율:** Task 1(render 규칙)·Task 2(backfill 스킬 + manifest)는 골든 변경 **0** — 기존 10 config는 `repo.backfill` 미설정(false)이라 manifest `when` false로 backfill 스킬이 생성되지 않는다. `update_golden.py` 금지, `python3 -m unittest test_golden`(from tests/) GREEN + `git status --porcelain tests/golden` 빈 출력이 증명. Task 4(backfill-app)만 신규 1트리. 예고 밖 골든 변경이 나오면 STOP(`git checkout -- tests/golden`).
- **동결 dialect만:** `{{path}}`, `{{#if}}`(`{{else}}`, `== "lit"`/`!= "lit"`), `{{#unless}}`, `{{#each}}`. 생성 SKILL.md ≤149줄, init SKILL.md ≤500줄.
- **자립성:** 생성 backfill 스킬은 `.superrelease/`·`.claude/` 상대 경로만 참조(release-notes 스킬·changelog-entry 템플릿을 프로즈로 참조 — 생성 스킬 간 참조 허용). `${CLAUDE_PLUGIN_ROOT}` 참조 금지.
- backfill은 **CHANGELOG.md만** 쓴다 — 태그 생성·버전 bump·push 없음. 단일 scope 전제(independent 모노레포는 render 거부).
- 코드·스크립트 메시지 영어, 생성 문서·init 프로즈 한국어. Python 3.9+ stdlib, exit 0/1/2.
- 테스트: `cd tests && python3 -m unittest discover -p 'test_*.py'`. 커밋: Conventional Commits + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 파일 구조 (M3c-2 전체)

```
수정  skills/init/scripts/render.py                     # Task 1: validate_config 규칙 1건
수정  tests/test_render_pipeline.py                     # Task 1: 거부 테스트
생성  skills/init/assets/skills/backfill/SKILL.md       # Task 2: backfill 스킬
수정  skills/init/assets/manifest.json                  # Task 2: backfill 엔트리
수정  tests/test_assets.py                              # Task 2: 렌더 스모크 + full-render
수정  skills/init/SKILL.md                              # Task 3: 번들7·config 필드·각주·지원범위
수정  skills/init/references/edge-cases.md              # Task 3: backfill 절 정합
수정  tests/golden_configs.py                           # Task 4: backfill_app 빌더
생성  tests/golden/backfill-app/expected/**             # Task 4: update_golden
```

책임 분리: backfill 절차(구간 순회·멱등·lean 항목·태그/push 없음) = 생성 스킬 프로즈, 생성 여부·거부 = manifest `when` + render 검증, `repo.backfill` = config(SSOT).

---

### Task 1: render.py 검증 규칙 — backfill + independent 거부

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Consumes: config `repo.backfill`(bool), `repo.monorepoStrategy`.
- Produces: 검증 규칙 — `repo.backfill`이 truthy이고 `monorepoStrategy == "independent"`면 exit 1.

- [ ] **Step 1: 실패 테스트 작성 — tests/test_render_pipeline.py**

`PipelineTest` 클래스(이미 `monorepo_config` import, `self.write_config`/`self.render` 헬퍼)에서 기존 `test_maintenance_lines_rejected_for_non_semver_scheme` 메서드 **뒤**에 추가:

```python
    def test_backfill_rejected_for_independent(self):
        cfg = monorepo_config()
        cfg["repo"]["backfill"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("backfill", r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_backfill_rejected_for_independent -v`
Expected: FAIL — 현재는 exit 0으로 렌더된다(미거부).

- [ ] **Step 3: 규칙 구현 — render.py validate_config**

`skills/init/scripts/render.py`의 `validate_config` 함수에서, 기존 `release-pr` + tagless 규칙 블록(`...resume relies on tag detection")`으로 끝남) **뒤**, `sinks = {...}` 줄 **앞**에 삽입:

```python
    if repo.get("backfill") and strategy == "independent":
        problems.append("repo.backfill is not supported with the independent "
                        "monorepo strategy (monorepo backfill is deferred)")
```

엔진부(tokenize/parse/evaluate/render_template)는 건드리지 않는다.

- [ ] **Step 4: 통과 확인 (회귀 포함)**

Run: `cd tests && python3 -m unittest test_render_pipeline -v 2>&1 | tail -6`
Expected: 신규 테스트 PASS. 기존 거부 규칙(independent·tagless·비semver·tag-message·fragment) 테스트도 회귀 없이 PASS.

- [ ] **Step 5: 골든 불변 + 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest test_golden 2>&1 | tail -3` → OK(재생성 없이). `git status --porcelain tests/golden` 빈 출력 확인. 이어서 `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: render 검증 — backfill + independent 모노레포 거부 (M3c-2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: backfill 생성 스킬 + manifest 엔트리

**Files:**
- Create: `skills/init/assets/skills/backfill/SKILL.md`
- Modify: `skills/init/assets/manifest.json` (hotfix 엔트리 뒤)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: config `repo.backfill`(manifest 게이트), `scope.notes`·`repo.mergePolicy`(스킬 프로즈), Task 1 검증(backfill+independent는 애초에 렌더되지 않음).
- Produces: 렌더 산출물 `.claude/skills/backfill/SKILL.md`(backfill=true일 때만). Task 4 골든 `backfill-app`이 스냅샷한다.

- [ ] **Step 1: 실패 테스트 작성 — tests/test_assets.py**

`SkillAssetsTest` 클래스에 (마지막 메서드 뒤) 추가:

```python
    def test_backfill_skill_renders_clean(self):
        out = self.render_asset("skills/backfill/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-app", out)
        self.assertIn("changelog", out.lower())
        self.assertIn("git log", out)
        self.assertIn("태그·버전 bump·push는 하지 않는다", out)
        self.assertLessEqual(len(out.splitlines()), 149)
```

`FullRenderTest` 클래스에 추가:

```python
    def test_backfill_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["backfill"] = True
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            backfill = (repo / ".claude/skills/backfill/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("generated by superrelease", backfill)
            self.assertIn("git log", backfill)
```

그리고 기존 `test_real_assets_render_end_to_end`의 존재 확인 루프 아래(다른 `assertFalse(...exists())` 줄 옆)에 backfill 미생성 확인 1줄 추가:

```python
            self.assertFalse((repo / ".claude/skills/backfill/SKILL.md").exists())
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_backfill_skill_renders_clean test_assets.FullRenderTest.test_backfill_full_render -v`
Expected: 둘 다 ERROR/FAIL(backfill 스킬 파일 없음).

- [ ] **Step 3: skills/init/assets/skills/backfill/SKILL.md 생성 (전문)**

```
---
name: backfill
description: {{project.name}} 프로젝트의 CHANGELOG를 과거 태그 이력에서 소급 작성한다. 사용자가 백필, backfill, 체인지로그 소급, 과거 릴리스 노트 채워줘, CHANGELOG 이력 정리, 예전 태그 노트 만들어줘 등 기존 태그에서 누락된 릴리스 이력을 채우는 요청을 하면 반드시 이 스킬을 사용한다.
---

# backfill — {{project.name}} CHANGELOG 이력 소급 작성

이미 태그가 쌓여 있는데 CHANGELOG에 기록이 없거나 빠진 릴리스가 있을 때, 태그 구간별 커밋으로 과거 릴리스 항목을 사후 작성해 CHANGELOG.md를 채운다. **일회성 정리 작업**이며 단일 scope 레포 전제다. 태그·버전 bump·push는 하지 않고 CHANGELOG.md만 쓴다.

공통 규칙:

- 부작용 있는 동작은 **dry-run 프리뷰 → 사용자 확인 → 실행**. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
- 이 스킬은 CHANGELOG.md 외 어떤 파일도 바꾸지 않는다 — 태그를 만들거나 옮기지 않고 버전 파일도 건드리지 않는다.

## 1. 대상 태그 구간 산출

- `git tag --list`로 태그를 모으고, config `scopes[0].tag.format`의 {version} 패턴에 맞는 태그만 남긴다(과거 혼재 포맷 태그는 무시 — 표준 포맷 규칙).
- 남은 태그를 버전 순으로 정렬한다. 연속한 두 태그 `A`, `B`가 한 구간 `A..B`다. 가장 이른 태그는 선행 태그가 없으므로 그 태그 자체를 "Initial release"로 다룬다(`git log <firstTag>`).

## 2. 멱등 — 이미 있는 버전 건너뛰기

- CHANGELOG.md를 읽어 이미 항목이 있는 버전을 파악한다. **그 버전들은 건너뛰고 누락된 구간만 채운다.** 기존 항목과 Unreleased 섹션은 절대 건드리지 않는다.
- 채울 구간이 하나도 없으면 "CHANGELOG가 이미 최신입니다"라고 보고하고 멈춘다.

## 3. 구간별 항목 작성

- 채울 각 구간에 대해 `git log <A>..<B> --pretty=format:"%h %s"`{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}로 커밋을 모은다.
- `.claude/skills/release-notes/SKILL.md` 절차로 읽되, 정식 릴리스 노트가 아니라 **간결한 이력 항목**을 목표로 한다 — `.superrelease/templates/changelog-entry.md` 골격(Keep a Changelog: Added/Changed/Fixed)으로 Changes 목록 위주로 짧게.
- 언어·어조는 config `scopes[0].notes`의 language·tone을 따른다.

## 4. dry-run 프리뷰 → 커밋

- 채울 구간 목록(버전·구간 범위)과 각 구간의 항목 초안을 미리 보여주고 확인받아라.
- 확인 후: CHANGELOG.md에 역시간순(최신이 위)으로 삽입한다. Unreleased 섹션이 있으면 그 아래. CHANGELOG.md만 스테이징해 커밋한다(예: `docs: backfill CHANGELOG from tags`).
- **태그·버전 bump·push는 하지 않는다.**

## 실패 시

어디까지 작성·삽입했는지 명시하라. CHANGELOG.md는 태그와 무관하므로 되돌리기 안전하다 — 잘못됐으면 `git checkout CHANGELOG.md`로 취소하고 다시 시도하면 된다.
```

- [ ] **Step 4: manifest.json에 backfill 엔트리 추가**

`skills/hotfix/SKILL.md` 엔트리(현재 line 27-32) **뒤**, `scripts/version.py` 엔트리 앞에 삽입:

```json
    {
      "src": "skills/backfill/SKILL.md",
      "dest": ".claude/skills/backfill/SKILL.md",
      "render": true,
      "when": "repo.backfill"
    },
```

- [ ] **Step 5: 통과 확인 + 골든 바이트 불변**

Run: `cd tests && python3 -m unittest test_assets test_golden -v 2>&1 | tail -6`
Expected: 전부 PASS. `git status --porcelain tests/golden` 빈 출력 — 기존 10 config는 `repo.backfill` 미설정(false) → backfill 미생성 → 바이트 불변(재생성 불필요).

- [ ] **Step 6: 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add skills/init/assets/skills/backfill/SKILL.md skills/init/assets/manifest.json tests/test_assets.py
git commit -m "feat: backfill 생성 스킬(태그 구간 CHANGELOG 소급) + manifest 엔트리 (M3c-2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: init 번들 7 해제 + config 필드 + edge-cases 정합

**Files:**
- Modify: `skills/init/SKILL.md` (번들 7, config 템플릿 repo 블록, config 각주, 지원 범위)
- Modify: `skills/init/references/edge-cases.md`

**Interfaces:**
- Consumes: Task 1~2의 실동작(backfill 스킬 생성 조건·거부 규칙).
- Produces: init이 `repo.backfill`을 질문·기록하는 지시. 프로즈 태스크(골든-복사 아님 — 골든·테스트 무영향, 검증은 grep + 줄 수 + strict).

- [ ] **Step 1: init SKILL.md 번들 7 교체**

`skills/init/SKILL.md` 번들 7의 현재 `CHANGELOG backfill(M3 예정 표시)` 부분을 갱신 — 번들 7 전체를 아래로 교체:

```
- **번들 7 — 첫 릴리스·이력·전파**: 기존 버전이 없으면 0.1.0 vs 1.0.0(공개 API 안정성 약속 기준으로 설명) / 기존 태그가 있고 CHANGELOG가 없거나 불완전한 **단일 스킬 레포**면 CHANGELOG backfill을 제안하고 `repo.backfill: true`로 기록한다(백필 스킬 생성 — 태그 구간별 과거 이력을 CHANGELOG.md에 소급 작성, 태그·push 없음; independent 모노레포는 후속 M3c-3으로 잠그며 render가 그 조합을 거부한다) / destinations에 changelog가 있는데 CHANGELOG.md가 없으면 첫 릴리스 때 생성됨을 안내 / (independent 모노레포) 내부 의존성 전파 — 스캔 리포트 `monorepo.internalDependencies`를 근거로 "b가 a에 의존하므로 a 릴리스 시 b를 자동 patch 릴리스" 제안을 scope별 `dependents` 목록으로 확정한다(순환 의존이 생기지 않는지 확인).
```

- [ ] **Step 2: init SKILL.md config 템플릿 repo 블록에 backfill 필드 추가**

config 템플릿 repo 블록의 현재 `"maintenanceLines": false,` 줄 **뒤**에 한 줄 추가:

```
    "maintenanceLines": false,
    "backfill": false,
```

- [ ] **Step 3: init SKILL.md config 각주 추가**

config 각주 목록의 hotfix 각주(현재 `- hotfix: \`repo.maintenanceLines: true\`면 ...(independent 모노레포 조합은 render가 거부한다).`) **뒤**에 추가:

```
- backfill: `repo.backfill: true`면 `.claude/skills/backfill/SKILL.md`가 생성된다 — 기존 태그 구간에서 CHANGELOG를 소급 작성하는 일회성 스킬(단일 scope 한정, independent 모노레포는 render가 거부).
```

- [ ] **Step 4: init SKILL.md 지원 범위 갱신**

지원 범위 목록의 현재 `- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: M3c` 줄을 아래로 교체:

```
- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: 단일 scope 레포 지원(모노레포는 M3c-3)
```

- [ ] **Step 5: edge-cases.md backfill 절 정합**

`skills/init/references/edge-cases.md`의 CHANGELOG backfill 절에서 현재 문장:

```
**이 기능은 M3에서 지원되며, M1에는 포함되지 않는다.**
```

를 아래로 교체:

```
**이 기능은 조건부 생성 스킬 `backfill`로 지원된다** — init이 `repo.backfill: true`로 기록하면 `.claude/skills/backfill/SKILL.md`가 생성된다. 스킬은 표준 포맷 태그 구간을 순서대로 훑어 누락된 버전만(멱등) CHANGELOG.md에 간결한 항목으로 채운다. 태그·버전 bump·push는 하지 않고 CHANGELOG.md만 쓴다. 단일 scope 레포 한정이며, 모노레포 backfill은 후속(M3c-3)이다.
```

- [ ] **Step 6: 정합 검증 + 커밋**

Run:
```bash
grep -c "backfill" skills/init/SKILL.md                          # 기대: ≥3 (번들7·config필드·각주·지원범위)
grep -n "M3 예정\|backfill.*M3c$" skills/init/SKILL.md            # backfill의 "M3 예정" 잔재 없어야 함
grep -c "backfill" skills/init/references/edge-cases.md          # 기대: ≥1
wc -l skills/init/SKILL.md                                       # 기대: ≤500
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK, 골든 clean
cd .. && claude plugin validate . --strict 2>&1 | tail -1        # 통과
```

```bash
git add skills/init/SKILL.md skills/init/references/edge-cases.md
git commit -m "feat: init 번들7 backfill 해제 + config repo.backfill 필드 + edge-cases 정합 (M3c-2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 골든 backfill-app 신규

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/backfill-app/expected/**` (update_golden 산출)

**Interfaces:**
- Consumes: `helpers.scope_config`, Task 2의 backfill 스킬·manifest.
- Produces: `GOLDEN` dict 11항목. `test_golden`이 자동 순회.

- [ ] **Step 1: golden_configs.py에 빌더 추가 + GOLDEN 갱신**

`tests/golden_configs.py`의 `fragment_app` 함수 **뒤**에 추가하고 `GOLDEN` dict를 교체:

```python
def backfill_app():
    # repo.backfill=true → backfill 스킬 생성 (기존 태그 CHANGELOG 소급)
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["backfill"] = True
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app}
```

- [ ] **Step 2: 골든 생성 + 범위 검증**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden | sort`
Expected: `?? tests/golden/backfill-app/` **한 항목만**. ` M `으로 시작하는 기존 트리 변경이 하나라도 있으면 STOP(`git checkout -- tests/golden`).

- [ ] **Step 3: 스냅샷 스팟 확인**

Run:
```bash
test -f tests/golden/backfill-app/expected/.claude/skills/backfill/SKILL.md && echo backfill-ok   # 기대: backfill-ok
grep -c "git log" tests/golden/backfill-app/expected/.claude/skills/backfill/SKILL.md              # 기대: ≥1
grep -rl "backfill" tests/golden/ | grep -v backfill-app || echo "(backfill 스킬은 backfill-app에만)"
```
Expected: `backfill-ok`, `git log` ≥1, backfill 스킬 파일은 backfill-app 트리에만 존재.

- [ ] **Step 4: 테스트 통과 + 커밋**

Run: `cd tests && python3 -m unittest test_golden -v 2>&1 | tail -4` → 11 골든 전부 PASS. 이어서 `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add tests/golden_configs.py tests/golden/backfill-app
git commit -m "test: 골든 backfill-app 추가 — backfill 조건부 스킬 생성 고정 (M3c-2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 최종 검증 (컨트롤러 직접 수행, 커밋 없음)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 전체 스위트 + strict + clean**

```bash
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK (154 + 신규 테스트)
cd .. && claude plugin validate . --strict                                # 통과
git status --porcelain                                                    # 비어 있음
```

- [ ] **Step 2: 골든 범위 확인**

```bash
git diff --name-status main..HEAD -- tests/golden | awk '{print $1}' | sort | uniq -c   # 전부 A
git diff --name-status main..HEAD -- tests/golden | grep -vE 'tests/golden/backfill-app/' || echo "(backfill-app 신규 1트리 외 골든 변경 없음)"
```
Expected: 전부 `A`, backfill-app 외 골든 변경 없음(기존 10트리 바이트 불변).

- [ ] **Step 3: backfill e2e 스팟 (거부 규칙 + 생성)**

```bash
cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_backfill_rejected_for_independent test_assets.FullRenderTest.test_backfill_full_render 2>&1 | tail -3
```
Expected: 2 tests OK (independent 거부 + 단일 backfill 생성).

- [ ] **Step 4: 결과 보고 + 원장 기록**

`git log --oneline main..HEAD`(4커밋), 골든 11종 상태, backfill 스킬 생성 확인을 원장(`.superpowers/sdd/progress.md`)에 기록하고 최종 whole-branch 리뷰로 넘어간다.

---

## 스펙 커버리지 자체 점검

- A. backfill 생성 스킬(구간 순회·멱등·lean 항목·CHANGELOG만·태그/push 없음) → Task 2
- B. config `repo.backfill` 필드 + manifest 엔트리 → Task 2(manifest)·Task 3(config 템플릿)
- C. render.py backfill+independent 거부 → Task 1
- D. init 번들 7 해제 → Task 3
- E. edge-cases.md 정합 → Task 3
- F. 골든 backfill-app + 기존 불변 → Task 4, Task 1·2 바이트 규율
- 비범위(모노레포 backfill=M3c-3 / release-file·GitHub Release 소급 / 과거 태그 수정) → 계획에 없음(의도적)
