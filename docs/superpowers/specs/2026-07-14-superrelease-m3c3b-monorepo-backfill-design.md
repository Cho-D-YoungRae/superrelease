# superrelease M3c-3b — 모노레포 backfill + backfill 하드닝 설계

이 문서는 M3c-3의 두 번째(마지막) 조각 **M3c-3b**의 설계다. M3c-2에서 단일 scope 레포로 한정했던 CHANGELOG backfill을 `independent` 모노레포로 확장하고, M3c-2 최종 리뷰가 남긴 후속 5건(#2~#6)을 함께 닫는다. 이것으로 M3(조건부 기능) 전체가 완료된다.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md), [2026-07-13-superrelease-m3c2-changelog-backfill-design.md](2026-07-13-superrelease-m3c2-changelog-backfill-design.md). 베이스 커밋: main `68f4471`.

## 배경

M3c-2가 backfill 스킬(태그 구간별 CHANGELOG 소급)을 단일 scope 레포로 출하하면서, `independent` 모노레포 조합을 render가 거부하도록 잠갔다(모노레포는 scope별 태그 네임스페이스 순회가 필요하기 때문). M3c-2 최종 whole-branch 리뷰는 비차단 후속 5건을 남겼다:

- **#2** backfill + no-changelog-destination 미검증
- **#3** backfill + tagless scope render 미거부
- **#4** backfill + release-pr 커밋 경로 미명시
- **#5** 멱등 구간→버전 매핑 암묵
- **#6** squash=false 브랜치 골든 미핀

이 마일스톤이 모노레포 확장과 이 5건을 함께 닫는다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 스킬 구조 | 기존 backfill 스킬 한 개에 `{{#if monorepoStrategy == "independent"}}` 내부 분기 | manifest `when`은 단일 표현식이라 "backfill AND independent" 복합 게이트 불가 |
| #2 changelog 목적지 없음 | init 경고(soft) + 허용, render 거부 안 함 | backfill은 일회성 이력 문서 — legitimate 이력-보존 케이스를 막지 않는다 |
| #3 tagless | 전 scope tagless면 render 거부; 모노레포는 scope별 skip | 원차 불가한 dead 스킬 방지, `release-pr + tagless` 거부 선례와 동형. 혼합 모노레포는 tagged scope만 처리 |
| 모노레포 헤더 | `## <scope>@<version>` (bare) | 상시 release-monorepo 헤더와 동일 — 소급 항목이 상시 릴리스 항목과 같은 스타일로 섞이도록 |

## A. render 검증 규칙 조정

`validate_config`에서:

1. **제거**: `repo.backfill` truthy + `monorepoStrategy == "independent"` 거부 규칙(M3c-2). independent 모노레포 backfill 잠금 해제.
2. **추가 (#3)**: `repo.backfill` truthy인데 **태그를 쓰는 scope가 하나도 없으면**(모든 scope의 `tag.enabled`가 false) 거부(exit 1). 단일 scope 레포는 `scopes[0]`가 tagless면 해당. backfill이 순회할 태그 구간이 원차 불가한 config를 막는다.
3. **#2는 render 무변경** — init 경고로 처리(soft).

기존 테스트 `test_backfill_rejected_for_independent`는 제거하고, "independent + backfill 통과" 및 "전 scope tagless + backfill 거부" 테스트로 교체한다. render.py는 골든-복사 대상이 아니라 골든 무영향.

## B. backfill 스킬 확장 (`skills/init/assets/skills/backfill/SKILL.md`, `when: repo.backfill`)

한 파일에 조건 블록을 추가한다. 자립성(`.superrelease/`·`.claude/` 상대 경로만) 유지, ≤150줄.

- **#5 (구간→버전 명확화)**: §1·§2 프로즈에 "구간 `A..B`는 **태그 B 버전**의 릴리스 항목이다 — 그 사이 커밋이 B에서 나갔다"를 명시하고, 멱등을 "B의 버전이 CHANGELOG에 이미 있으면 그 구간을 건너뛴다"로 구체화한다. 단일 scope 프로즈가 바뀌므로 backfill-app 골든이 재생성된다(의도적, diff는 명확화 문장으로 한정).
- **#4 (release-pr 경로)**: §4에 `{{#if repo.releasePath == "release-pr"}}` 블록 — 보호 브랜치면 직접 push가 불가하므로 CHANGELOG 커밋을 브랜치(예: `docs/backfill-changelog`)에 올려 PR로 머지하라고 안내(backfill은 태그가 없어 머지 후 재개 불필요 — 순수 문서 PR). 개행을 `{{#if}}` 안에 두어 direct-push 렌더는 바이트 불변.
- **모노레포 분기**: `{{#if repo.monorepoStrategy == "independent"}}` 블록 — 각 scope를 순회하며 (a) 그 scope의 `tag.format`(`<scope>@{version}` 네임스페이스)에 맞는 태그만 필터, (b) `git log <A>..<B> --pretty=format:"%h %s" -- <scope.path>`로 경로 한정 수집, (c) `.superrelease/templates/changelog-entry.md` 골격에 `## <scope>@<version>` (bare, `<version>`=태그 B) 헤더로 삽입, (d) `tag.enabled`가 false인 scope는 **"태그 없음 — 건너뜀"으로 skip**(#3). 단일 scope 브랜치(부재 시 렌더)는 현행 `scopes[0]` 프로즈 그대로.
- squash 조건(`{{#if repo.mergePolicy == "squash"}}`)은 단일·모노레포 공유 프로즈로 유지한다.

절차 골자(태그 구간 산출 → 멱등 skip → 구간별 간결 항목 → dry-run → CHANGELOG.md만 커밋, 태그·bump·push 없음)와 실패 안내는 M3c-2 그대로.

## C. init 번들 7

- backfill 잠금 해제를 **independent 모노레포까지 확장**. "independent 모노레포는 후속 M3c-3b로 잠그며 render가 그 조합을 거부한다" 문구 제거 → independent에도 backfill을 제안하고(scope별 `<scope>@<version>` 순회로 소급), `repo.backfill: true`로 기록.
- **#2 경고**: backfill 제안 시 대상 scope에 `changelog` 목적지가 없으면 "평상시 릴리스가 CHANGELOG를 갱신하지 않아 소급본이 이후 방치될 수 있음"을 경고하고 확인받아 `decisions`에 기록한다(render는 거부하지 않는다).
- 지원 범위 목록에서 backfill을 "단일 scope + independent 모노레포 지원"으로 갱신.

## D. references 정합

- `monorepo.md`: 지원 현황의 "모노레포 backfill(패키지 태그 네임스페이스 순회)은 후속 M3c-3b로 남는다" → 실동작(scope별 태그 네임스페이스 순회·`## <scope>@<version>` 헤더·tagless scope skip) 서술로 교체.
- `edge-cases.md`: backfill 절의 "단일 scope 레포 한정이며, 모노레포 backfill은 후속(M3c-3b)이다" → independent 모노레포 지원 서술로 교체.

## E. 골든

- `backfill-app`(기존): #5 프로즈 변경으로 **재생성**(단일 scope 의미 불변 — diff가 명확화 문장에 한정되는지 검증).
- `backfill-monorepo`(신규): `independent` + `repo.backfill: true` + `mergePolicy: "merge"` — 모노레포 분기와 **#6 non-squash 브랜치**를 한 트리로 고정.
- `backfill-release-pr`(신규): 단일 scope + `repo.backfill: true` + `releasePath: "release-pr"` — **#4 release-pr 블록**을 고정.
- 그 외 골든은 backfill·monorepoStrategy·releasePath·mergePolicy 조합이 달라 backfill 조건 블록이 이전과 동일하게 렌더/collapse → 바이트 불변(단, #5로 backfill 스킬이 생성되는 트리만 영향 — 현재 backfill-app 하나뿐).

## 제약·검증

- 동결 template dialect, 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진·스크립트(version.py·next-version.py·changed-packages.py) 산술·조작 **무변경** — 유일한 Python 변경은 `validate_config` 규칙 조정(independent 거부 −1, 전-scope-tagless 거부 +1).
- 자립성: backfill 스킬은 `.superrelease/`·`.claude/` 상대 경로만 참조. 생성 스킬·템플릿을 프로즈로 참조(허용). 플러그인 경로 참조 금지.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어·생성 문서·init 프로즈 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인(`git status --porcelain tests/golden`이 의도한 트리만).

## 비범위 (후속)

- train 이력 backfill(`train-*` 구간 소급) — CHANGELOG는 패키지·train 축이 달라 별도 설계 필요.
- backfill이 release-file·GitHub Release를 소급 생성하는 것 — CHANGELOG.md만 대상(M3c-2 원칙 유지).
- 과거 태그 수정·재태깅(edge-cases의 "과거 태그 불변" 원칙 유지).
- `fixed` 모노레포는 이미 단일 root scope로 모델링되어 단일 scope backfill과 동일하게 동작(별도 작업 없음).

## 예상 태스크 (writing-plans에서 확정)

1. render.py 규칙 조정(independent 거부 제거 + 전-scope-tagless 거부) — TDD, 테스트 교체.
2. backfill 스킬 확장(#5 명확화 + #4 release-pr 블록 + 모노레포 분기 + tagless skip) + 렌더 스모크(단일·모노레포·release-pr·merge 분기).
3. init 번들7 independent 확장 + #2 경고 + monorepo.md·edge-cases.md 정합.
4. 골든 재생성(backfill-app) + 신규(backfill-monorepo·backfill-release-pr) + 최종 검증.
