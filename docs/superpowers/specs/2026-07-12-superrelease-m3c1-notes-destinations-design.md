# superrelease M3c-1 — 노트 목적지 fragment + tag-message 설계

이 문서는 M3c(트레인·backfill·fragment·tag-message)를 서브마일스톤으로 분해한 첫 조각 **M3c-1**의 설계다. 두 개의 신규 `notes.destinations` 값 — **fragment**(노트 소스: `changelog.d/` 조각 취합)와 **tag-message**(노트 sink: annotated 태그 메시지 내장) — 를 추가한다.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md) (§4.3 질문 번들 5, §6.3 절차 5·7, §6.7 노트, §9 notes-and-changelog.md). 베이스 커밋: main `7c61679`.

## M3c 분해 (참고)

M3c는 크기·독립성이 달라 서브마일스톤으로 나눈다:
- **M3c-1 (이 문서)**: 노트 목적지 fragment + tag-message. 가장 작고 트레인과 독립.
- **M3c-2**: CHANGELOG backfill (기존 레포 과거 태그에서 이력 역생성).
- **M3c-3**: release trains (이중 체계 모노레포 — release-train 스킬 + notes-train).

M3c-1은 트레인/backfill에 의존하지 않으며, 노트 시스템을 완성해 후속 조각이 재사용한다.

## 배경

`references/notes-and-changelog.md`가 이미 5종 목적지를 배경 설명하고 있으며 fragment/tag-message는 "M3에서 확정"으로 표시돼 있다. M1은 `changelog | release-file | github-release` 3종을 지원한다. 이 마일스톤이 나머지 2종을 실동작으로 채운다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| fragment 범위 | 소비(취합)만 — 생성은 문서화된 규약 | conventional commits를 소비만 하는 것과 동일 철학, YAGNI |
| 조각 파일 규약 | towncrier식 `{id}.{category}.md` | 확립된 관례, category가 노트 섹션에 자동 매핑 |
| tag-message 가드 | render에서 거부(미annotated/tagless 시) | 기존 independent·tagless·비semver 거부와 일관, config 값 암묵 변경 안 함 |
| fragment 단독 | sink 최소 1개 필요(단독이면 render 거부) | 취합→삭제 후 노트 유실 방지 |

## 렌더 메커니즘 (핵심)

동결 template dialect의 `{{#each}}` + `{{#if this == "lit"}}`를 조합하면 **배열 멤버십**을 dialect만으로 조건 렌더할 수 있다(엔진의 `lookup`이 `this`를 해석, `truthy`가 `this == "lit"` 지원):

```
{{#each scope.notes.destinations}}{{#if this == "fragment"}}<fragment 지시>{{/if}}{{/each}}
```

- 목적지에 `fragment`가 있을 때만 블록을 1회 emit. 없으면 0바이트 → **기존 골든 바이트 불변**.
- render.py 컨텍스트 변경 불필요. 유일한 Python 변경은 `validate_config` 규칙(엔진·산술 무변경).

**단일 vs 모노레포 처리는 M3a 선례를 따른다**: 단일 release 스킬은 조건 블록(byte-invariant), 모노레포 release 스킬은 런타임 프로즈(scope 무인라인, pnpm-monorepo 골든 1파일 재생성).

## A. fragment (노트 소스 — 소비만)

- `notes.destinations`에 `fragment` 값을 유효화.
- **규약**: `changelog.d/{id}.{category}.md` (예: `142.feature.md`, `88.fix.md`, `200.breaking.md`). `id`는 PR/이슈 번호 또는 slug. `category` → 노트 섹션 매핑:
  - `breaking` → Breaking Changes
  - `feature` → 하이라이트/변경 사항
  - `fix` → 변경 사항
  - `misc` (및 미인식 category) → 변경 사항
- **category는 노트 그룹핑 전용** — bump 결정은 기존대로 config `bump.sources`(커밋/PR)에서 이뤄지며 fragment는 bump 소스가 아니다.
- release 시 §5가 `changelog.d/*.md`를 category별로 취합해 노트 초안의 소스로 쓴다. **소비한 조각 파일 삭제(`git rm`)를 릴리스 커밋에 포함**하고 dry-run 프리뷰에 명시한다. 조각 생성은 기여자가 PR을 올릴 때 직접 하는 문서화된 규약이다(superrelease는 생성하지 않는다).
- 취합된 노트는 배열의 다른 **sink** 목적지(changelog/release-file/github-release/tag-message)로 반영된다. **fragment는 최소 1개의 sink 목적지를 함께 요구**한다 — 단독이면 취합·삭제 후 노트가 유실되므로 render가 거부한다(exit 1).

## B. tag-message (노트 sink)

- `notes.destinations`에 `tag-message` 값을 유효화.
- §7(태그 생성)에서 태그 메시지를 한 줄 요약 대신 **5단계 노트 전문**으로 넣는다: `git tag -a <태그> -F <노트 파일>` (signed면 `-s ... -F`).
- **render 거부**: tag-message는 `tag.enabled: true`이고 (`tag.annotated: true` 또는 `tag.signed: true`)일 때만 유효하다. 그 외(plain 태그, tagless)면 exit 1. init도 질문 단계에서 이 조합을 잠근다.

## C. init 번들 5

- fragment/tag-message를 선택지로 해제("M3 표시" 제거). destinations 복수 선택에 두 값을 포함.
- fragment 선택 시: `changelog.d/{id}.{category}.md` 규약과 sink 동반 필요를 안내. tag-message 선택 시: annotated 또는 signed 태그가 필요함을 안내(아니면 잠금).

## D. references

`notes-and-changelog.md`:
- 5종 표에서 fragment/tag-message의 "M3" → "지원"으로 갱신.
- fragment 절(현재 "M3에서 확정할 세부"라고 미룬 부분)에 확정된 규약(`{id}.{category}.md`, category 집합, 소비-only, 소비 후 삭제, sink 동반 필요)을 채운다.
- tag-message 절에 annotated/signed 요건을 명시.

## E. 골든

- 신규 1트리 `fragment-app`: `notes.destinations: ["fragment", "changelog", "tag-message"]` + annotated 태그(기본값). 단일 release 스킬의 fragment·tag-message 조건 블록을 스냅샷으로 고정.
- 기존 9골든 중 8개 단일-scope 골든은 바이트 불변(destinations에 두 값 없음 → 블록 collapse). pnpm-monorepo만 모노레포 런타임 프로즈로 1파일 재생성.

## F. render.py 검증 규칙 (validate_config)

두 규칙 추가:
1. **tag-message 요건**: 어떤 scope의 `notes.destinations`에 `tag-message`가 있는데 그 scope가 `tag.enabled: true` + (`tag.annotated` 또는 `tag.signed`)가 아니면 → 문제(exit 1).
2. **fragment sink**: 어떤 scope의 destinations에 `fragment`가 있는데 sink 목적지(changelog/release-file/github-release/tag-message) 중 하나도 없으면 → 문제(exit 1).

기존 규칙(independent·tagless·비semver·maintenanceLines)과 동일한 append 스타일. render.py는 골든-복사 대상이 아니라 골든 무영향이며, 두 조합 골든이 없어 기존 골든도 불변.

## 제약·검증

- 동결 dialect만(`{{#each}}`+`{{#if this == "lit"}}` 활용), 생성 SKILL.md ≤149줄, init SKILL.md ≤500줄.
- 스크립트 산술·render 엔진 무변경 — 유일한 Python 변경은 `validate_config` 규칙 2건.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어·생성 문서 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인(`git status --porcelain tests/golden`).

## 비범위 (후속)

- fragment 조각 **생성** 도우미(소비만 — 생성은 기여자 몫).
- fragment category를 bump 소스로 쓰는 것(bump는 기존 커밋/PR 유지).
- CHANGELOG backfill(M3c-2), release trains(M3c-3).

## 예상 태스크 (writing-plans에서 확정)

1. render.py tag-message + fragment-sink 검증 규칙 2건 (TDD).
2. 단일 release 스킬 §5/§7 fragment·tag-message 조건 블록(기존 골든 바이트 불변) + 렌더 스모크 테스트.
3. 모노레포 release 스킬 런타임 프로즈(pnpm-monorepo 골든 재생성).
4. init 번들 5 해제 + `notes-and-changelog.md` 정합.
5. 골든 `fragment-app` 신규 + 최종 검증.
