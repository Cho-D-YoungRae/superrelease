# superrelease M4b-2 — gitflow production hotfix (설계)

> 상태: 설계 승인됨 (2026-07-16). 다음 단계: writing-plans.

## 목표

M4b에서 이연한 **gitflow production hotfix** 흐름을 추가한다. `references/branching-and-release-path.md`(line 43)가 "후속 지원 예정"으로 명시한 바로 그 기능: main(현 production)에서 `hotfix/*` cut → main 머지·태그 → develop back-merge.

## 배경

- 현 hotfix 스킬은 **trunk 유지보수 라인** 모델(`release/1.2.x` 라인 패치), `repo.maintenanceLines`로 게이트. §7에 gitflow develop 반영 힌트만 존재.
- gitflow의 표준 hotfix는 다르다: 유지보수 라인이 아니라 **현 production(main)** 을 긴급 패치하고 develop로 back-merge. gitflow에 내재된 흐름이라 `maintenanceLines` 없이도 gitflow 레포는 이 기능을 원한다.
- `when`은 OR 미지원. gitflow는 release-pr·단일레포·developBranch 필수. gitflow+maintenanceLines 조합은 validate 허용.

## 스코프

**In:** hotfix 스킬을 gitflow-aware로(production 흐름) · gitflow 레포에도 hotfix 스킬 생성 · 골든/reference/init 반영.
**Out:** gitflow에서 `release/1.2.x` 유지보수 라인 타게팅(gitflow는 production 흐름만 — 후속) · monorepo×gitflow.

## gitflow production hotfix 흐름

1. **대상**: 현 production = `{{repo.defaultBranch}}` HEAD(gitflow에서 릴리스 후 main은 릴리스 버전 유지). 최신 릴리스 태그 확인.
2. **preflight**: `git checkout {{repo.defaultBranch}} && git pull` · clean · `version.py verify` · gh. (유지보수 라인 체크아웃 아님.)
3. **수정**: develop/main의 커밋 체리픽(`-x`) 또는 hotfix 브랜치에서 직접.
4. **patch 버전·노트**: `next-version.py --bump patch`(현재 = main의 릴리스 버전). anchor = main의 최신 릴리스 태그.
5. **release-pr**: `git checkout -b hotfix/<patch>`(main에서) → 커밋 → push → `gh pr create --base {{repo.defaultBranch}}` — **base=main**. 머지 후 재개.
6. **태그 + Release**: 머지 후 main HEAD에 태그(release §7과 동일).
7. **post-release — develop back-merge**: `git checkout {{repo.developBranch}} && git pull` → `git merge {{repo.defaultBranch}}`(충돌 시 버전 파일은 main 릴리스 버전 취함, 직후 복귀가 덮음) → push(거부 시 back-merge PR). 이어서 `postRelease.bump == next-snapshot`이면 develop에서 SNAPSHOT 복귀. (release §8 gitflow와 동형.)

trunk 유지보수 라인 흐름(base=`release/1.2.x`, develop back-merge 없음)과 구분된다.

## 구현

### hotfix 스킬 (`skills/init/assets/skills/hotfix/SKILL.md`) — gitflow 분기
차이 구간을 `{{#if repo.branching == "gitflow"}}…{{else}}…{{/if}}`로 분기(개행을 블록 **안**에 두어 trunk에서 0바이트 collapse → hotfix-library 골든 바이트 불변):
- **§1 대상**: gitflow=main HEAD/최신 태그 · trunk=`release/<라인>`.
- **§2 preflight 체크아웃**: gitflow=`{{repo.defaultBranch}}` · trunk=`release/<라인>`.
- **§4 anchor**: gitflow=main 최신 태그 · trunk=라인 최신 태그.
- **§5 PR base**: gitflow=`{{repo.defaultBranch}}` · trunk=`release/<라인>`.
- **§7 post-release**: gitflow=develop back-merge + SNAPSHOT 복귀 · trunk=라인 post-release + main 체리픽백(현행). 기존 §7의 `{{#if repo.branching == "gitflow"}}` develop 힌트는 이 정식 분기에 흡수.
- **intro(§6줄)**: gitflow면 "production hotfix", trunk면 "유지보수 라인 패치" — 소폭 분기 또는 공통 문구 유지.

### manifest — gitflow 게이트 엔트리 추가
`skills/init/assets/manifest.json`의 hotfix 엔트리(현 `when: repo.maintenanceLines`) **뒤에 두 번째 엔트리**(같은 src·dest, `when: repo.branching == "gitflow"`)를 추가. 이로써 hotfix 스킬은 `maintenanceLines` **또는** `gitflow`일 때 생성된다. 두 조건이 모두 참(gitflow+maintenanceLines)이면 동일 내용을 두 번 렌더(무해 — 같은 바이트로 덮어씀).

### 골든
- **`gitflow-app`** 골든이 이제 hotfix 스킬을 렌더(gitflow 게이트) → 그 트리에 `.claude/skills/hotfix/SKILL.md`(gitflow 흐름)가 **새로 추가**된다. 이것이 gitflow hotfix render 커버리지. **신규 골든 config 불필요.**
- **`hotfix-library`**(trunk+maintenanceLines) hotfix 스킬은 gitflow 블록이 0바이트 collapse → **바이트 불변**.
- `update_golden` 후 `git status tests/golden`: gitflow-app에 hotfix 파일 신규 + (그 외 불변). dual-entry 이중 렌더가 트리에 영향 없음을 gitflow+maintenanceLines 즉석 렌더로 확인(파일 1개).

### reference / init 프로즈
- `references/branching-and-release-path.md` line 43 "후속 지원 예정" 제거 → gitflow production hotfix 흐름 문서화(main cut → 태그 → develop back-merge). line 51/60의 gitflow 관련 문구 정합.
- init `SKILL.md` 번들 6: gitflow 선택 시 hotfix 스킬이 production hotfix 흐름으로 생성됨을 안내(maintenanceLines와 독립).

## 성공 기준

- gitflow 레포(gitflow-app)가 hotfix 스킬을 gitflow production 흐름으로 생성(골든에 반영).
- hotfix-library(trunk) 바이트 불변.
- gitflow+maintenanceLines가 dual-entry로 깨끗이 렌더(에러 없이 hotfix 1파일).
- reference에서 "후속 지원 예정" 제거·흐름 문서화. init 프로즈 반영.
- 전체 스위트 green · `plugin validate . --strict` PASS · `git status tests/golden`은 gitflow-app hotfix 신규만.

## 리스크 / 엣지 케이스

- **바이트 불변** — gitflow 분기 블록의 개행을 블록 안에 두어 trunk collapse. `update_golden` 후 hotfix-library 불변이 수용 기준.
- **dual-entry 이중 렌더** — gitflow+maintenanceLines에서 hotfix 엔트리 2개가 모두 fire → 동일 dest 이중 write(같은 바이트). render.py는 엔트리 독립 처리라 무해. 즉석 렌더로 확인.
- **develop back-merge 충돌** — 버전 파일 충돌은 main 릴리스 버전 취함(직후 SNAPSHOT 복귀가 덮음) — release §8 gitflow와 동일 지침.
- **init prose 자동 테스트 없음** — 골든(gitflow-app)·바이트 불변·사람 검수로 커버.

## 후속 (백로그)

- gitflow에서 `release/1.2.x` 유지보수 라인 타게팅(production + 라인 병행) · monorepo×gitflow · 문서 소소 정리 · libs.versions.toml 등.
