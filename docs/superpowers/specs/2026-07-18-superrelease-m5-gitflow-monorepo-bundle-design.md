# superrelease M5 — gitflow 모노레포 · tagless gitflow · bundle 라운드 노트 설계 스펙

- 날짜: 2026-07-18
- 상태: 승인됨 (2026-07-18, 브레인스토밍 대화에서 섹션별 승인)
- 선행: [2026-07-16 범위 축소](2026-07-16-superrelease-m4d-docs-usability-design.md) 이후 v0.4(미릴리스) 브랜치 위에서 진행
- 참고 레포: `no-commit-today/imstargg-v2` (비공개 — 2026-07-17 조사 결과를 본 문서에 요약)

## 1. 배경과 목표

README 유즈케이스 정리 과정에서 유즈케이스 2(기존 모노레포 · 프론트엔드 + 멀티모듈 백엔드 · 앱별 SemVer · gitflow)가 세 가지 이유로 지원 불가임이 확인됐다: ① 모노레포 × gitflow 거부, ② tagless × release-pr 거부(gitflow는 release-pr 강제), ③ 루트 CalVer 묶음 개념 부재. 사용자는 이 형태(imstargg 포함)를 **모두 지원**하기로 결정했다 — 직전 범위 정리에서 "지원 계획 없음"으로 내렸던 모노레포×gitflow를 명시적으로 뒤집는 결정이다(루트 CalVer는 제거했던 tag 기반 release-train이 아니라 아래 3절의 **노트 라벨** 형태로 지원한다).

**imstargg-v2 실태 (2026-07-17 조사):**

- independent 모노레포: `imstargg-backend/gradle.properties` **한 파일**에 `coreApiVersion`/`coreBatchVersion`/`coreWorkerVersion` 키로 앱별 버전 + `imstargg-frontend/package.json`. core-admin·admin-frontend는 버전 관리 제외.
- gitflow, release 브랜치 없음: `main`(운영, finalized) · `develop`(통합, SNAPSHOT). feature → develop → (배포 준비 시) develop→main PR 1건.
- **git 태그 없음.** 릴리스 표식은 main 머지 + 묶음 노트 파일.
- 루트 CalVer는 develop→main 라운드마다 만드는 **묶음 노트 파일명**(`docs/release/2026.07.1.md`)에만 쓰인다 — 코드·태그 어디에도 붙지 않는 릴리스 라운드 라벨.
- 자체 제작 `release-management` 스킬로 위 흐름을 자동화 중(superrelease로 대체 가능해지는 것이 장기 목표, 이번 범위 아님).

## 2. 브레인스토밍 결정 기록

| 질문 | 결정 | 근거 |
|---|---|---|
| 루트 CalVer 형태 | **묶음 노트 라벨** (루트 태그·루트 버전 파일 없음) | 루트를 "버전"으로 관리하는 관행은 드묾; imstargg 실형태가 노트 파일명 라벨; tagless 호환 |
| 모노레포 gitflow hotfix | **이번 범위 포함** | imstargg 실사용에 존재(`hotfix/*` 브랜치); gitflow 지원의 완성 조건 |
| tagless 허용 범위 | **gitflow에서만 확장** (단일·모노레포) | gitflow는 main 브랜치가 앵커를 대체; trunk×release-pr는 태그 필수 유지 |
| 완료 기준 | **골든 + 시나리오 테스트** | imstargg-v2 실적용·자체 스킬 대체는 별도 후속 세션 |
| 접근 방식 | **A: 기존 스킬에 흡수** (release-monorepo gitflow 분기 + bundle 통합) | 스킬 asset 수 불변(범위 정책), 스크립트 변경 최소, "라운드 = 릴리스와 동시에 노트" 형태 일치 |

## 3. bundle — 라운드 묶음 노트

### 3.1 config 스키마 (top-level)

```json
"bundle": {
  "enabled": true,
  "scheme": { "type": "calver", "pattern": "YYYY.0M.MICRO" },
  "notesPath": "docs/releases/"
}
```

- **independent 모노레포 전용** (validate가 강제).
- 라운드 번호의 SSOT는 **`notesPath` 안의 최신 CalVer 파일명**이다. 태그도 버전 파일도 config 상태도 만들지 않는다 — tagless 레포와 호환되고 config는 무상태를 유지한다(gitflow에서는 anchor도 쓰지 않으므로, gitflow+bundle 조합의 config는 완전 무상태).
- 템플릿은 `notes-bundle.md` 고정 — config 필드로 두지 않는다(scope 노트만 `notes.template`이 갈린다).
- branching 무관: trunk 모노레포의 direct-push/release-pr 라운드에도 쓸 수 있다(라운드 = 릴리스 1회 실행/PR 1건).

### 3.2 notes-bundle.md 템플릿 (신규 asset)

`skills/init/assets/templates/notes-bundle.md` → `.superrelease/templates/notes-bundle.md` (manifest `when: bundle.enabled`, `preserve: template`, `render: true`). 구성: 라운드 번호·날짜 헤더 / 이번 라운드 scope×버전 표(릴리스된 scope) + 미변경 scope 현재 버전 병기 / 하이라이트 / scope별 주요 변경 rollup / Breaking Changes rollup. 언어 블록은 대표 scope(`scope.notes.language`) 기준 ko/en 조건부(기존 템플릿과 동일 방식).

### 3.3 라운드 번호 산출

1. 스킬이 `notesPath`의 `*.md` 파일명(확장자 제거)을 수집한다.
2. `next-version.py --scheme calver --pattern <bundle pattern> --today <오늘> --current-among <값들…>` → 다음 라운드 번호. 파일이 0개면 `--current ""`로 첫 라운드(같은 기간 MICRO 0).
3. hotfix도 bundle.enabled면 라운드다 — MICRO가 증가한 bundle 노트를 만든다("main에 반영되는 모든 배포 = 라운드", imstargg의 잦은 MICRO 증가 패턴과 일치).

## 4. gitflow 앵커 통일 — main 브랜치가 앵커

gitflow에서 릴리스 범위·변경 감지·중단 감지의 기준을 태그에서 **`origin/<defaultBranch>`**로 통일한다. main은 릴리스 머지(+hotfix 머지)로만 전진하므로 `origin/<main>..HEAD`(develop 위)가 정확히 "이번 라운드에 나갈 변경"이고, 태그 유무와 무관하게 성립한다.

- **단일 레포 gitflow도 동일하게 통일한다** — 현행 태그 앵커(§2)와 유지보수 라인 태그를 `--merged`로 제외하던 복잡한 감지(§1.6-②)가 함께 단순해진다. `gitflow-app` 골든이 **의도적으로 변경**된다.
- gitflow에서 `scopes[].anchor` 필드는 **사용되지 않는다**. tagless여도 anchor.value 갱신 커밋이 필요 없다.
- 중단 감지(gitflow 공통 패턴): ① 열린 `release/*` PR → 대기 보고 ② 머지된 최신 `release/*` PR의 후처리 미완 → (a) `tag.enabled` scope 중 그 라운드 태그 누락 → 태그부터 (b) back-merge 누락(`git merge-base --is-ancestor origin/<main> HEAD` 실패) → back-merge부터 (c) develop의 mutable scope 파일 버전이 bare(수식어 없음) → SNAPSHOT 복귀부터. **tagless scope는 (a)를 스킵**한다(단일 레포 gitflow의 태그 검사도 `tag.enabled` 조건부로 렌더).

## 5. 스크립트 — 변경은 정확히 하나

| 스크립트 | 변경 |
|---|---|
| `changed-packages.py` | **없음** — gitflow 모노레포는 기존 `--ref origin/<main>` 플래그를 그대로 쓴다 |
| `version.py` | **없음** — 공유 파일 다중 키는 기존 properties-key로 이미 표현 가능 |
| `next-version.py` | `--current-among <v1> [<v2>…]` 추가 (아래) |

**`--current-among`**: 후보들 중 pattern에 맞는 것만 파싱해 최댓값을 `--current`로 삼아 다음 CalVer를 계산한다. CalVer는 사전순 정렬이 깨지므로(`2026.05.10` < `2026.05.2`) 최댓값 선택은 LLM 산술 금지 원칙상 스크립트 몫이다.

- calver 전용 — 다른 scheme과 조합하면 exit 2 (usage error).
- `--current`·`--scope`와 상호 배타 (exit 2).
- `nargs="+"` (1개 이상). 후보를 넘겼는데 **pattern 매칭이 0개면 exit 1** — "no candidate matches pattern (wrong notesPath?)" (잘못된 notesPath로 라운드가 조용히 0으로 리셋되는 사고 방지). README.md 같은 비버전 파일이 섞여 있는 것은 정상이며 무시된다(매칭이 1개 이상이면 성공).
- "엔진은 안정" 규율과의 긴장을 인지한 결정이다: 결정론(LLM 산술 금지) 원칙이 우선하며, 순수 함수 하나의 추가로 한정한다.

## 6. release-monorepo 스킬 — gitflow 분기

기존 단계 구조를 유지하고 `{{#if repo.branching == "gitflow"}}` 분기와 bundle 단계만 추가한다(단일 release 스킬이 이미 쓰는 조건 패턴과 동일).

| 단계 | gitflow에서 달라지는 것 |
|---|---|
| §0 대상 | `changed-packages.py --ref origin/<main> --json` (fetch 후). 변경 scope 표 → 선택 → dependents 안내 동일 |
| §1 preflight | 브랜치==`developBranch` / clean / develop 원격 동기화 / verify / gh 인증(release-pr 고정) / **중단 감지 = 4절 패턴** |
| §2 범위 | scope별 `git log origin/<main>..HEAD -- <scope.path>` — anchor 태그 미사용. "첫 릴리스" 특례 소멸(main..develop이 자연히 전체 미출시분) |
| §3–4 | 동일 (scope별 bump 제안·`--release`로 SNAPSHOT 제거·`version.py set --scope`) |
| §5 노트 | scope별 노트 동일 + **bundle 단계**(bundle.enabled): 3.3절로 라운드 번호 산출 → `notes-bundle.md` 골격으로 `<notesPath><라운드>.md` 작성 → 릴리스 커밋에 포함 |
| §6 전파 | 동일 |
| §7 PR | 릴리스 브랜치명 = bundle이면 `release/<라운드>`, 아니면 기존 `release/<첫 scope>@<버전>(+N)`. base=`<main>`, **머지 커밋 강제**(squash는 main..develop 이력과 back-merge를 어그러뜨린다). 생성 후 중단 |
| §8 태그 | 머지 후 `tag.enabled` scope만 수행. 전 scope tagless면 단계 전체가 0바이트 collapse. bundle은 태그를 만들지 않는다 |
| §9 post-release | back-merge(`<main>`→develop, 버전 파일 충돌은 main 쪽 선택) → mutable scope들 SNAPSHOT 복귀(develop에서, 보호 시 PR) → **anchor 갱신 없음** |

imstargg 자체 스킬과의 모델 차이(의도된 단순화): imstargg는 feature 머지마다 SNAPSHOT을 계속 올리는 "bump 모드"가 있으나, superrelease는 **릴리스 시점에 bump를 확정**한다(postRelease next-snapshot이 기본 patch를 미리 올려두고 릴리스 때 minor/major 조정 확인). 결과 버전은 동일하고 개발 중 개입이 없다.

## 7. release(단일) 스킬 — gitflow 앵커 통일 + tagless

- §2 범위: gitflow면 `origin/<main>..HEAD` (비-gitflow는 현행 태그/anchor 유지).
- §1.6 중단 감지: 4절 패턴으로 교체 — 태그 검사는 `tag.enabled`일 때만 렌더, tagless면 머지된 `release/*` PR + develop 상태(back-merge 누락·bare 버전)로 감지.
- §7 태그: `{{#if scope.tag.enabled}}` 게이트 기존 그대로 — gitflow+tagless면 §7이 collapse되고 §8(back-merge·복귀)만 남는다.
- §8: gitflow tagless에서 anchor.value 갱신 문구가 나오지 않도록 — 기존 `{{#unless scope.tag.enabled}}` anchor 갱신 블록을 `{{#unless}}` + 비-gitflow 조건으로 한정.

## 8. hotfix 스킬 — gitflow 모노레포 분기

- §1 대상: 수정이 영향을 주는 **scope들**을 확정(사용자 지정 또는 수정 파일 경로 ↔ scope.path 대조). main HEAD에서 `hotfix/<첫 scope>@<패치 버전>`(복수 scope면 `+N` 접미 — 릴리스 브랜치 관례와 대칭) cut.
- §4 버전·노트: 영향 scope만 `next-version.py --scope <name> --bump patch` → `version.py set --scope`. 노트는 그 scope의 destinations. **bundle.enabled면 라운드 노트 생성**(MICRO 증가).
- §5–6: PR base=`<main>` → 머지 후 `tag.enabled` scope만 태그 → back-merge(develop) → mutable scope SNAPSHOT 복귀.
- 단일 gitflow hotfix 흐름은 변경 없음(모노레포 분기가 단일 config에서 0바이트 collapse).

## 9. validate_config 변경 (엔진 불변, 규칙만)

**완화 2건:**

1. `gitflow × 모노레포 거부` 삭제 — independent는 release-monorepo gitflow 분기, fixed는 단일 흐름 그대로(fixed는 원래 release 단일 스킬을 받으므로 추가 작업 없이 성립).
2. `release-pr × tagless 거부`를 `repo.branching != "gitflow"`일 때만 적용.

**추가 4건:**

1. `bundle.enabled`는 `monorepoStrategy == "independent"` 필수.
2. `bundle.scheme.type == "calver"` + `bundle.scheme.pattern` 필수.
3. `bundle.notesPath` 필수(문자열, init이 기본 `docs/releases/`를 채움).
4. (회귀 핀) `bundle`은 branching 제약 없음 — 규칙을 추가하지 않는 것 자체를 테스트로 핀.

**유지(변경 없음):** gitflow 전 scope semver 필수 · `github.release`는 태그 필요(tagless면 false 강제) · `maintenanceLines × independent` 거부 · gitflow의 release-pr 잠금 · `tag.enabled` 명시 boolean.

## 10. init · scan 변경

- **scan 소확장 1건**: `scan_changelog`에 `bundleNotesGuess` 추가 — `docs/releases/`·`docs/release/` 안의 CalVer풍 파일명(`^\d{4}[.\d]+\.md$` 휴리스틱) 목록. 기존 라운드 노트 운용 감지 → bundle 추천 근거.
- **번들 2(태그)**: gitflow면 "태그 없음"이 유효 선택지임을 안내(github.release 동반 비활성 안내 포함).
- **번들 5(노트)**: independent 모노레포면 bundle 여부 질문 — pattern(기본 `YYYY.0M.MICRO`)·notesPath(기본 `docs/releases/`, `bundleNotesGuess`가 있으면 그 디렉터리 추천).
- **번들 6(브랜치)**: "gitflow는 단일 스킬 레포 한정" 제약 문구 삭제, 모노레포 gitflow 안내(release-monorepo가 라운드 릴리스 수행).
- **지원 범위와 제약 절** 갱신: 모노레포×gitflow 지원 / gitflow tagless 지원 / bundle 지원 / trunk×release-pr×tagless는 계속 미지원.

## 11. 문서 갱신

- README.md·README_KO.md: Not planned에서 "monorepo × gitflow" 제거, "release trains" 항목을 "release trains (root **tags**)"로 명확화(노트 라벨 bundle과 혼동 방지), 유즈케이스 워크스루 2의 한계 문구를 bundle·gitflow 지원으로 교체, config 표에 `bundle` 행 추가, Roadmap에 M5 항목.
- CLAUDE.md 지원 현황: 모노레포×gitflow·tagless gitflow·bundle 추가. "제거된 기능" 절의 release-train은 유지하되 "노트 라벨 bundle로 대체" 한 줄 병기.
- 메모리(`superrelease-scope-policy`): 모노레포×gitflow "지원 계획 없음" 반전을 반영해 갱신(구현 세션에서).

## 12. 테스트 전략 (완료 기준: 골든 + 시나리오)

- **골든 신규 1종** `gitflow-monorepo-bundle` — imstargg 모양 그대로: 공유 `backend/gradle.properties`의 properties-key 3개(api/batch/worker) + frontend json-path, **전 scope tagless**, `github.release=false`, gitflow(develop), bundle(`YYYY.0M.MICRO`, `docs/releases/`). 골든 선형 증가 억제 방침에 따라 대표 1개만.
- **test_assets**: release-monorepo gitflow 분기·bundle 단계·`--current-among` 호출 문구·hotfix 모노레포 분기·release 단일 gitflow 앵커 문구 단정 + **trunk 모노레포 config에서 gitflow·bundle 블록 0바이트 collapse**(기존 모노레포 골든 3종 바이트 불변) 단정.
- **test_render_pipeline**: 신규 validate 규칙 각각 + 회귀 핀("trunk×release-pr×tagless 여전히 거부", "bundle×trunk 허용", "gitflow×fixed 허용").
- **test_next_version**: `--current-among` 벡터 — 최댓값 선택(`2026.05.2` vs `2026.05.10` 함정), pattern 불일치 무시, 전원 불일치 exit 1, calver 외 scheme exit 2, `--current` 동시 지정 exit 2.
- **기존 골든 영향(의도)**: `gitflow-app`만 변경(앵커 통일). 모노레포 3종(pnpm/backfill/release-pr)·나머지는 바이트 불변이어야 하며, `git status --porcelain tests/golden`으로 검증.

## 13. Non-goals

- trunk × release-pr × tagless — 계속 거부 (앵커 대안이 gh 의존적, 수요 없음)
- bundle의 태그·GitHub Release — 노트 파일만 (라운드에 태그가 필요해지면 후속 결정)
- 개발 중 연속 SNAPSHOT bump 자동화(imstargg bump 모드) — postRelease next-snapshot으로 갈음
- imstargg-v2 실적용·자체 release-management 스킬 대체 — 후속 세션
- 모노레포 유지보수 라인(maintenanceLines × independent) — 계속 미지원

## 14. 리스크와 완화

| 리스크 | 완화 |
|---|---|
| release-monorepo 렌더 결과 150줄 한도 초과 (현 96줄 + gitflow·bundle 분기) | 구현 계획 단계에서 최악 config(gitflow+bundle+release-pr) 렌더 줄 수를 먼저 실측; 초과 시 프리앰블·§9 프로즈 압축. test_assets의 `assertLessEqual(149)` 단정이 게이트 |
| 새 조건 블록이 기존 골든을 오염 | 바이트 불변 규율(개행을 `{{#if}}` 안에) + `git status tests/golden` 범위 검증 + collapse 단정 테스트 |
| gitflow-app 골든 변경(앵커 통일)이 의도인지 리뷰 어려움 | 스펙에 의도 명시(4절) + PR 본문에 diff 요약 |
| `--current-among`이 "스크립트 산술 불변" 규율과 긴장 | 순수 함수 1개 한정, 벡터 테스트로 커버, 스펙 5절에 결정 근거 기록 |
| hotfix 3-flavor(유지보수 라인/단일 gitflow/모노레포 gitflow) 조건 밀도 | 모노레포 분기를 단일 gitflow 프로즈와 최대 공유; 64→80줄 내 목표 |

## 15. 마일스톤 완료 기준

1. `python3 -m unittest discover -s tests -q` 전부 통과 (신규 벡터·단정 포함)
2. `claude plugin validate . --strict` 통과
3. 골든 `gitflow-monorepo-bundle` 스냅샷 존재 + 기존 골든 영향이 `gitflow-app`뿐임을 `git status`로 확인
4. README·README_KO·CLAUDE.md·init 지원 범위 갱신 완료
5. imstargg 모양 config(3.1·12절)가 validate를 통과하고 렌더 결과가 (a) develop 기준 라운드 릴리스 (b) tagless 태그 단계 collapse (c) bundle 노트 단계 포함을 모두 담고 있음
