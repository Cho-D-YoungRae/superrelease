# M8 온보딩 입구 정비 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** init·release 스킬의 온보딩 입구 4개 갭(B-5 버전 후보 0건 분기, B-12 placeholder 리셋, B-13 trunk×release-pr 첫 릴리스 재개, B-20 SNAPSHOT 기본 JVM 한정)을 프로즈 수정만으로 메운다.

**Architecture:** 스펙은 [2026-08-12-m8-onboarding-entrance-design.md](../specs/2026-08-12-m8-onboarding-entrance-design.md). render 엔진·스크립트 무변경 — `skills/init/SKILL.md`(플러그인 스킬, 골든 무관)와 `skills/init/assets/skills/{release,release-monorepo}/SKILL.md`(렌더 asset — 골든·dogfood 재생성 필요)만 수정한다.

**Tech Stack:** Python 3.9+ stdlib · unittest(pytest 없음) · 동결 template dialect(`{{#if x == "lit"}}` 인라인 게이트)

**실행 모델:** 구현 서브에이전트는 **opus 모델**로 dispatch한다(사용자 지시).

## Global Constraints

- 테스트 러너: 전체는 `python3 -m unittest discover -s tests -q`. 단일 모듈은 `cd tests && python3 -m unittest test_assets -v; cd ..` — **dotted 형식(`python3 -m unittest tests.test_assets`)은 ModuleNotFoundError로 실패한다. 쓰지 마라.**
- **바이트 불변**: asset에 조건 블록을 추가할 때 그 기능이 없는 config에서 0바이트로 collapse해야 한다 — 공백·개행을 `{{#if}}` **안**에 두어라.
- **골든 규율**: asset 수정 후 `python3 tests/update_golden.py` → `git status --porcelain tests/golden`이 의도한 파일만 보여야 한다. 그 외 파일이 바뀌면 회귀 — 중단하고 보고하라.
- **dogfood**: asset 수정 후 재렌더 필수 — `tests/test_dogfood_selfrender.py`가 드리프트 시 실패한다.
- 동결 dialect: `{{path}}`, `{{#if x}}`/`{{#if x == "lit"}}`/`{{else}}`, `{{#unless}}`, `{{#each}}`만. 확장 금지.
- 어서션은 **규칙 고유 문구**를 핀하라("첫 릴리스가 머지 후 태그 전에 중단"). 범용 단어("resume", "PR")는 오탐한다.
- 프로즈는 한국어, 코드·커밋 메시지 제목은 Conventional Commits. init SKILL.md ≤500줄(현재 148줄).
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 작업 브랜치: `feat/m8-onboarding-entrance` (이미 체크아웃됨). push·PR은 계획 범위 밖 — 하지 마라.

---

### Task 1: B-13 단일 release asset — trunk×release-pr 첫 릴리스 재개 감지

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md` (preflight 6, 라인 26)
- Test: `tests/test_assets.py` (`SkillAssetsTest` 클래스)

**Interfaces:**
- Produces: 렌더 프로즈 고유 문구 `"첫 릴리스가 머지 후 태그 전에 중단"` — Task 2·3의 어서션·골든이 이 문구에 의존한다.

**배경:** gitflow 분기(라인 25)는 `gh pr list --state merged --search "head:release/"`로 태그 전 중단을 잡지만, trunk 분기(라인 26)는 "마지막 릴리스 태그가 존재하고" 전제라 첫 릴리스(태그 0개)의 머지 후 재개를 못 잡는다. trunk×**direct-push**에는 이 문제가 없으므로(릴리스 PR 자체가 없다) `{{#if repo.releasePath == "release-pr"}}` 인라인 게이트로만 추가한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_assets.py`의 `SkillAssetsTest` 클래스(라인 71~) 안에 추가:

```python
    def test_release_skill_first_release_resume_gated_by_release_pr(self):
        # B-13: trunk×release-pr에서만 "태그 0개 + 머지된 release/* PR" 첫 릴리스
        # 재개 문구가 렌더된다 — trunk×direct-push에서는 0바이트로 collapse.
        pr_ctx = base_ctx()
        pr_ctx["repo"]["releasePath"] = "release-pr"
        pr_out = self.render_asset("skills/release/SKILL.md", pr_ctx)
        self.assertIn("첫 릴리스가 머지 후 태그 전에 중단", pr_out)
        self.assertIn('gh pr list --state merged --search "head:release/"', pr_out)

        dp_out = self.render_asset("skills/release/SKILL.md")  # trunk·direct-push
        self.assertNotIn("첫 릴리스가 머지 후 태그 전에 중단", dp_out)
        self.assertNotIn("--state merged", dp_out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_release_skill_first_release_resume_gated_by_release_pr -v; cd ..`
Expected: FAIL — `'첫 릴리스가 머지 후 태그 전에 중단' not found in ...`

- [ ] **Step 3: asset 수정**

`skills/init/assets/skills/release/SKILL.md` 라인 26의 문장 끝 `사용자 선택을 받아라.` 바로 뒤(같은 줄, 개행 앞)에 다음을 삽입한다. **선행 공백이 게이트 안에 있어야 한다**:

```
{{#if repo.releasePath == "release-pr"}} 릴리스 태그가 **하나도 없으면** 파일 버전 기반 감지가 불가능하다 — 머지된 릴리스 PR을 검색해(`gh pr list --state merged --search "head:release/" --json headRefName,mergedAt`) `release/<버전>` head가 있는데 그 버전의 태그가 없으면 첫 릴리스가 머지 후 태그 전에 중단된 것이니 6단계의 "머지 후 재개"대로 7단계(태그)부터 이어가라.{{/if}}
```

삽입 후 라인 26은 다음으로 끝난다: `…사용자 선택을 받아라.{{#if repo.releasePath == "release-pr"}} 릴리스 태그가 …이어가라.{{/if}}` (뒤 개행은 기존 그대로).

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest -v; cd ..`
Expected: 전부 PASS — 특히 기존 `test_release_skill_gitflow_*` 계열이 그대로 통과해야 한다(gitflow 분기는 건드리지 않았다).

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py
git commit -m "feat(assets): trunk×release-pr 첫 릴리스(태그 0) 머지 후 재개 감지 — 단일 release

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: B-13 release-monorepo asset — scope별 첫 릴리스 재개 감지

**Files:**
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (preflight 6, 라인 32)
- Test: `tests/test_assets.py` (`MonorepoAssetsTest` 클래스, 라인 576~)

**Interfaces:**
- Consumes: Task 1의 고유 문구 `"첫 릴리스가 머지 후 태그 전에 중단"` — 두 asset이 같은 문구를 쓴다(골든 어서션 일관성).

**배경:** 단일판과 같은 갭. 모노레포 trunk 분기(라인 32 `{{else}}` 이후)는 "anchor 태그보다 높은데" 전제라 anchor 없는 scope(첫 릴리스)를 못 잡는다. 태그 단계는 모노레포에서 **8단계**다(단일은 7단계 — 번호가 다르니 주의).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_assets.py`의 `MonorepoAssetsTest` 클래스 안에 추가:

```python
    def test_release_monorepo_first_release_resume_gated_by_release_pr(self):
        # B-13 모노레포판: anchor 없는 scope의 머지 후 재개는 release-pr에서만 안내.
        pr_ctx = mono_ctx()
        pr_ctx["repo"]["releasePath"] = "release-pr"
        pr_out = self.render_asset("skills/release-monorepo/SKILL.md", pr_ctx)
        self.assertIn("첫 릴리스가 머지 후 태그 전에 중단", pr_out)
        self.assertIn('gh pr list --state merged --search "head:release/"', pr_out)

        dp_out = self.render_asset("skills/release-monorepo/SKILL.md")  # direct-push
        self.assertNotIn("첫 릴리스가 머지 후 태그 전에 중단", dp_out)
        self.assertNotIn("--state merged", dp_out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest.test_release_monorepo_first_release_resume_gated_by_release_pr -v; cd ..`
Expected: FAIL — `'첫 릴리스가 머지 후 태그 전에 중단' not found in ...`

- [ ] **Step 3: asset 수정**

`skills/init/assets/skills/release-monorepo/SKILL.md` 라인 32의 trunk 분기 문장 끝 `태그를 쓰지 않는 scope는 이 검사를 건너뛴다.` 바로 뒤(`{{/if}}` 앞)에 삽입한다. **선행 공백이 게이트 안에 있어야 한다**:

```
{{#if repo.releasePath == "release-pr"}} anchor 태그가 **하나도 없는** scope는 파일 버전 기반 감지가 불가능하다 — 머지된 릴리스 PR을 검색해(`gh pr list --state merged --search "head:release/" --json headRefName,mergedAt`) 그 PR에 포함된 scope 중 그 버전의 태그가 없는 scope는 첫 릴리스가 머지 후 태그 전에 중단된 것이니 8단계(태그)부터 이어가라.{{/if}}
```

삽입 후 라인 32의 trunk 분기는 `…건너뛴다.{{#if repo.releasePath == "release-pr"}} anchor 태그가 …이어가라.{{/if}}{{/if}}`로 끝난다(마지막 `{{/if}}`는 기존 gitflow/trunk 분기 닫힘).

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest -v; cd ..`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/release-monorepo/SKILL.md tests/test_assets.py
git commit -m "feat(assets): trunk×release-pr 첫 릴리스 재개 감지 — release-monorepo scope별

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 골든 재생성 + dogfood 재렌더 + 전체 테스트

**Files:**
- Modify: `tests/golden/*/expected/**` (update_golden.py가 재생성)
- Modify: `.claude/skills/release/SKILL.md` (dogfood 재렌더 — superrelease 자신이 trunk×release-pr)

**Interfaces:**
- Consumes: Task 1·2의 asset 변경. 이 태스크 전에는 `test_dogfood_selfrender`·골든 비교가 **실패하는 것이 정상**이다.

- [ ] **Step 1: 골든 재생성**

```bash
python3 tests/update_golden.py
git status --porcelain tests/golden
```

Expected 변경 범위: **trunk×release-pr 조합** 골든의 `release/SKILL.md` 또는 `release-monorepo/SKILL.md`만 — 후보: `release-pr-app`, `release-pr-merge`, `release-pr-nogh`, `release-pr-snapshot`, `monorepo-release-pr`, `hotfix-release-pr`, `backfill-release-pr`(이 중 실제로 해당 스킬을 렌더하는 것만). **gitflow-* 골든과 direct-push 골든(gradle-app, npm-app 등)이 하나라도 바뀌면 바이트 불변 위반 — 즉시 중단하고 보고하라.**

- [ ] **Step 2: dogfood 재렌더**

```bash
NOW=$(python3 -c "import json; print(json.load(open('.superrelease/config.json'))['superrelease']['generatedAt'])")
python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now "$NOW"
git status --porcelain .claude .superrelease
```

Expected: `.claude/skills/release/SKILL.md`만 변경(superrelease는 단일 레포 — release-monorepo는 렌더되지 않는다).

- [ ] **Step 3: 전체 테스트 + 플러그인 검증**

```bash
python3 -m unittest discover -s tests -q
claude plugin validate . --strict
```

Expected: 전부 OK / validation passed.

- [ ] **Step 4: 커밋**

```bash
git add tests/golden .claude/skills/release/SKILL.md
git commit -m "test(golden): B-13 첫 릴리스 재개 문구 재baseline + dogfood 재렌더

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: B-5 — init "버전 후보 0건" 분기 일반화

**Files:**
- Modify: `skills/init/SKILL.md` 라인 21(신규 모드)·라인 49(번들 2)

**Interfaces:**
- Produces: 번들 2의 새 분기 명칭 "**후보 0건이면**" — Task 5의 B-12 문구가 "후보 0건 분기와 같은 규칙"으로 이를 참조한다.

init SKILL.md는 렌더 asset이 아니다 — 골든·dogfood 무관, 자동 테스트 없음. 검증은 줄 수와 문서 정합뿐이므로 아래 문구를 그대로 적용하라.

- [ ] **Step 1: 번들 2(라인 49)에 후보 0건 분기 삽입**

라인 49에서 `CI-friendly \`<revision>\` property 전환을 권장)` 뒤의 ` / ` **다음**에 아래 텍스트 + ` / `를 삽입한다(즉 "버전 위치 확정" 항목과 "플러그인이면" 항목 사이에 새 항목이 들어간다):

```
**후보 0건이면**(신규·기존 레포 공통): 먼저 버전 파일이 실제로 없는지, 있는데 스캔이 못 찾았는지 물어라 — 있다면 파일 경로·형식을 받아 수동 versionLocation(json-path 또는 regex)으로 등록한다(일치 여부는 Phase 3 자가검증 `version.py verify`가 확인). 없다면 성격에 맞는 버전 파일(예: `VERSION`·`package.json`·`gradle.properties`)과 초기 버전을 Phase 3 렌더에 포함해 사용자 확인 후 함께 생성한다. 초기 버전은 스캔 `tags`의 최신 릴리스 태그가 있으면 그 버전을 시드로 하고(태그 있는 기존 레포에 0.1.0 역행 금지), 태그도 없으면 0.1.0을 제안한다
```

- [ ] **Step 2: 신규 모드(라인 21)의 중복 문구 축약**

라인 21의 다음 텍스트를:

```
**버전 파일이 하나도 없으면**(versionLocations 후보 0건) Phase 3 자가검증(`version.py verify`)이 반드시 실패하므로, 성격에 맞는 버전 파일(예: `package.json`·`gradle.properties`·`VERSION`)과 초기 버전(0.1.0 등)을 Phase 3 렌더에 포함해 사용자 확인 후 함께 생성한다
```

다음으로 교체한다:

```
**버전 파일이 하나도 없으면** 번들 2의 후보 0건 분기를 따른다(버전 파일 생성이 Phase 3 렌더에 포함된다)
```

- [ ] **Step 3: 검증**

```bash
wc -l skills/init/SKILL.md
grep -c "후보 0건" skills/init/SKILL.md
```

Expected: 500줄 이하(현재 148줄 기준 ±2줄) / "후보 0건" 2회(번들 2 정의 1 + 신규 모드 참조 1).

- [ ] **Step 4: 커밋**

```bash
git add skills/init/SKILL.md
git commit -m "feat(init): 버전 후보 0건 분기 일반화 — 수동 등록·파일 도입·태그 시드 (B-5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: B-12 placeholder 리셋 + B-20 SNAPSHOT 기본 JVM 한정

**Files:**
- Modify: `skills/init/SKILL.md` 라인 21(프리셋)·라인 49(번들 2)·라인 51(번들 4)

**Interfaces:**
- Consumes: Task 4가 만든 "후보 0건이면" 분기(B-12 문구가 참조).

- [ ] **Step 1: B-12 — 번들 2(라인 49)에 placeholder 리셋 삽입**

Task 4에서 삽입한 후보 0건 분기 텍스트 끝 `태그도 없으면 0.1.0을 제안한다` 뒤의 ` / ` **다음**에 아래 텍스트 + ` / `를 삽입한다:

```
감지된 현재 값이 `0.0.0`이면 placeholder일 가능성을 알리고 실제 시작 버전으로 리셋할지 물어라 — 제안값은 후보 0건 분기와 같은 규칙(최신 릴리스 태그 우선, 없으면 0.1.0(초기 개발)/1.0.0(이미 안정) 중 선택)이며, 거절하면 그대로 둔다
```

- [ ] **Step 2: B-20 — 신규 모드 프리셋(라인 21) 분기**

라인 21의 `성격별 권장 프리셋(라이브러리→SemVer+SNAPSHOT+next-snapshot / 앱→` 를 다음으로 교체한다:

```
성격별 권장 프리셋(JVM 라이브러리(gradle·maven)→SemVer+SNAPSHOT+next-snapshot / 그 외 라이브러리(npm·Rust·Python 등)→SemVer+pre/post none(SNAPSHOT은 JVM 생태계 관례 — references/prerelease-and-dev-channel.md) / 앱→
```

- [ ] **Step 3: B-20 — 번들 4(라인 51) post-release 기본 분기**

라인 51의 `post-release bump — 라이브러리→next-snapshot 기본, 앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안)` 을 다음으로 교체한다:

```
post-release bump — JVM 라이브러리(스캔 `buildSystems`의 gradle·maven)→next-snapshot 기본, 그 외 라이브러리·앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안)
```

- [ ] **Step 4: 검증**

```bash
wc -l skills/init/SKILL.md
grep -c "JVM 라이브러리" skills/init/SKILL.md
grep -n "라이브러리→next-snapshot" skills/init/SKILL.md
```

Expected: ≤500줄 / "JVM 라이브러리" 2회(라인 21·51) / 세 번째 grep은 **0건**(무한정 문구가 남아 있으면 B-20 미완).

- [ ] **Step 5: 커밋**

```bash
git add skills/init/SKILL.md
git commit -m "feat(init): placeholder(0.0.0) 리셋 질문 + SNAPSHOT 기본 JVM 한정 (B-12·B-20)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: CHANGELOG + README 정합 + 최종 검증

**Files:**
- Modify: `CHANGELOG.md` ([Unreleased])
- Modify: `README.md`·`README_KO.md` (알려진 한계 절 한 줄)

**Interfaces:**
- Consumes: Task 1~5의 변경 전부(문서화 대상).

- [ ] **Step 1: CHANGELOG [Unreleased]에 M8 항목 추가**

`## [Unreleased]` 아래, 기존 `### Changed` **앞**에 `### Added` 섹션을 신설한다:

```markdown
### Added

- **init이 버전 후보 0건 레포의 입구를 안내한다** — 버전 파일이 없는 기존
  레포(Go CLI·모바일·인프라)에서 init이 절차 없이 표류하는 대신, "파일이
  없는지, 있는데 스캔이 못 찾았는지"를 구분해 수동 versionLocation 등록
  또는 버전 파일 생성을 제안한다. 초기 버전은 최신 릴리스 태그를 시드로
  써서 0.1.0 역행을 막는다.
- **init이 placeholder 버전(0.0.0)을 감지하면 시작 버전 리셋을 묻는다** —
  한 번도 릴리스된 적 없는 `package.json`류의 `0.0.0`을 그대로 첫 릴리스
  버전의 기준으로 삼지 않는다.
- **trunk×release-pr의 첫 릴리스도 머지 후 재개를 감지한다** — 중단 상태
  감지가 "마지막 릴리스 태그 존재"를 전제해 태그가 하나도 없는 첫 릴리스는
  PR 머지 후 태그 단계 재개를 잡지 못했다. gitflow가 이미 쓰는 머지된
  릴리스 PR 검색을 단일·모노레포 release 스킬의 trunk 분기에도 적용했다.
```

그리고 기존 `### Changed` 목록 끝에 추가:

```markdown
- **라이브러리 프리셋의 SNAPSHOT 기본을 JVM으로 한정** — init이 모든
  라이브러리에 `-SNAPSHOT`+next-snapshot을 기본 제안해 npm·Rust·Python
  생태계 관례와 어긋났다. 이제 gradle·maven 감지 시에만 기본이며, 그 외
  라이브러리는 pre/post `none`이 기본이다.
```

- [ ] **Step 2: README 한계 절 정합(양판)**

`README.md`의:

```
- **Tag-only repos** (no version file — Go CLIs, Terraform modules) and
  **GitOps/manifest repos** (propagation targets, not version sources) are
  out of scope: `versionLocations` is required per scope.
```

을 다음으로 교체한다:

```
- **Tag-only repos** (no version file — Go CLIs, Terraform modules) and
  **GitOps/manifest repos** (propagation targets, not version sources) are
  out of scope: `versionLocations` is required per scope. For tag-only
  repos, init offers to introduce a version file seeded from the latest tag.
```

`README_KO.md`의:

```
- **태그 전용 레포**(버전 파일 없음 — Go CLI, Terraform 모듈)와
  **GitOps/manifest 레포**(버전 소스가 아니라 전파 대상)는 범위 밖입니다:
  scope마다 `versionLocations`가 필수입니다.
```

을 다음으로 교체한다:

```
- **태그 전용 레포**(버전 파일 없음 — Go CLI, Terraform 모듈)와
  **GitOps/manifest 레포**(버전 소스가 아니라 전파 대상)는 범위 밖입니다:
  scope마다 `versionLocations`가 필수입니다. 태그 전용 레포에는 init이
  최신 태그를 시드로 버전 파일 도입을 안내합니다.
```

- [ ] **Step 3: 최종 검증**

```bash
python3 -m unittest discover -s tests -q
claude plugin validate . --strict
git status --porcelain
```

Expected: 테스트 전부 OK / validation passed / 커밋 안 된 변경은 CHANGELOG·README 2판뿐.

- [ ] **Step 4: 커밋**

```bash
git add CHANGELOG.md README.md README_KO.md
git commit -m "docs: CHANGELOG [Unreleased] M8 기입 + README 태그-only 한계 문구 보강

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
