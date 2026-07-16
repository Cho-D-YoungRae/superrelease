# superrelease M4d — 사용성·문서 정리 설계

이 문서는 M4 로드맵의 마지막 마일스톤 **M4d**의 설계다. M4a~M4c가 각각 스펙에 "이연"으로 명시한 누적 문서 부채와, 2026-07-15 전면 리뷰가 남긴 사용성 지적, M4a/M4b 최종 리뷰가 M4d로 이관한 생성 스킬 프로즈 잔여물을 한 번에 정리한다.

M4 로드맵: M4a 정확성(PR #12) → M4b gitflow(PR #13) → M4c 스캔 커버리지(PR #14) → **M4d 사용성·문서(본 문서)**.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md). 베이스 커밋: main `7eaecf0`.

## 배경 — 누적 문서 부채

- **README 로드맵 드리프트**: `M3b (current)`·`M3c (미래)`로 정지 — M3c·M4a·M4b·M4c 전부 출하됨. README_KO도 동일 드리프트(`M3b (현재)`).
- **README 생성물 표·Uninstall 불완전**: 조건부 생성물(hotfix/backfill/release-train SKILL.md, release-pr-body.md, notes-package/train 템플릿) 누락. Uninstall glob `.claude/skills/release*`가 hotfix/backfill/release-train 미포함.
- **지원 매트릭스 미반영**: gitflow 브랜칭 축(M4b)·스캔 커버리지 확장(M4c)이 README·CLAUDE.md에 없음.
- **업그레이드 스토리 부재**: 이미 init한 레포 사용자가 재init 계기를 알 채널이 README에 없음(전면 리뷰 A7).
- **config 스키마 참조 부재**: "손편집 후 재init"이 공식 커스터마이징 경로인데 필드·허용값 참조가 없어 render 에러 기반 시행착오가 됨(전면 리뷰 A12).
- **init 요약이 조건부 스킬 트리거 문구 미노출**: backfill 등을 생성하고도 실행 문구를 안 알려줌(전면 리뷰 A8).
- **신규 레포 버전 파일 부트스트랩 부재**: 버전 파일 없는 신생 레포는 Phase 3 자가검증이 반드시 실패(케이스 리뷰 #7).
- **생성 스킬 프로즈 잔여물**(M4a/M4b 이관): tagless §7 빈 섹션·§5 github-release 범례 dangling·release-pr×no-github gh 인증 preflight 부재·개행 위생.
- **CHANGELOG**: v0.1.0 준비 중인데 M4a~M4c 산출이 Unreleased에 미반영.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 스코프 | Tier 1(외부 문서) + Tier 2(init·references 프로즈) + Tier 3(생성 스킬 프로즈) + CHANGELOG 전부 | 사용자 결정. 이연 항목 일괄 청산 |
| 구현 형태 | 4파트 분할(외부 문서 / init·references / 생성 스킬 / 테스트) | 골든 무영향(Tier 1+2)과 골든 변경(Tier 3)을 태스크 경계로 분리 |
| §7 빈 섹션 게이트 | `{{#if scope.tag.enabled}}` 단일 조건으로 §7 전체 게이트 | validate 규칙상 `github.release=true ⟹ tag.enabled=true`라 §7 내용은 tag.enabled=true일 때만 존재 — 단일 조건으로 충분 |
| §5 범례 게이트 | `github-release` 불릿만 목적지 존재로 게이트(changelog·release-file는 유지) | github-release 불릿만 "7단계 Release 본문"으로 collapsible 섹션을 참조 → §7 게이트 시 dangling 방지. release-file은 파일 경로 참조라 dangle 없음(대규모 churn 회피) |
| config 스키마 문서 | README 섹션(필드·허용값·validate 요약)으로 — 새 렌더 asset 아님 | README는 GitHub 공개 문서라 손편집 사용자가 접근 가능. `.superrelease/`로 렌더(=기능)는 비범위 |
| 로드맵 형식 | M1~M3c shipped 갱신 + M4 하드닝 한 줄 | 제품 능력 기준(내부 작업 마일스톤명 M4a-d는 노출 안 함) |

## 파트 1 — 외부 문서 (Tier 1, 골든 무영향)

**README.md ↔ README_KO.md (1:1 동기 — 모든 변경을 양쪽에 미러)**:

1. **로드맵**: `M3b (current)`/`M3c` 항목을 전부 shipped로 갱신. 최종 형태 — M1~M3c 각 `(shipped)` + 신규 줄 `M4 (shipped) — gitflow 브랜칭, 스캔 커버리지 확장, 정확성 하드닝`.
2. **생성물 표**: 조건부 행 추가 — `.claude/skills/hotfix/SKILL.md`(maintenanceLines), `.claude/skills/backfill/SKILL.md`(backfill), `.claude/skills/release-train/SKILL.md`(train), `.superrelease/templates/release-pr-body.md`(release-pr), notes-package/notes-train 템플릿. 각 행 Role에 "(조건부: <조건>)" 표기.
3. **Uninstall FAQ**: `.claude/skills/release*` → `.claude/skills/{release*,hotfix,backfill,release-train}`.
4. **지원 매트릭스**: 새 항목 "Branching: trunk / gitflow (single-skill repos, release-pr only)". 새 짧은 섹션 "What superrelease detects" — 스캔 감지 파일 목록(M4c 지원범위 절과 정합).
5. **Upgrading 섹션 신설**: 플러그인 업데이트 → 재init(불일치 없으면 질문 0개, 파일 결정론적 재렌더, 마커 버전이 SSOT). 재init이 손편집 커스터마이징의 공식 경로임을 명시.
6. **config.json reference 섹션 신설**: 주요 필드·허용값·핵심 validate 규칙(gitflow→release-pr, calver/headver→pre/post none, github.release↔tag.enabled 등) 요약 표 + "손편집 후 재init".

**CLAUDE.md**: "지원 현황" 줄에 "브랜칭(trunk/gitflow)" 추가.

**CHANGELOG.md**: Unreleased에 M4a~M4c 산출 추가 — gitflow 브랜칭 축, 스캔 커버리지 확장(pom·VERSION·openapi·gradle 모노레포·developBranchGuess), 정확성 하드닝(version.py regex 가드·changed-packages·CalVer·validate 규칙). v0.1.0 미태그라 Unreleased 누적.

## 파트 2 — init/references 프로즈 (Tier 2, 골든 무영향)

1. **init Phase 3 요약** (SKILL.md §5 "요약 출력"): "첫 사용 예시(\"릴리스해줘\", \"릴리스 준비됐는지 봐줘\")"를 "생성된 스킬별 사용 예시 나열"로 일반화 — 조건부 스킬이 생성됐으면 그 트리거 문구도 나열(hotfix "핫픽스", backfill "백필해줘", release-train "train 릴리스").
2. **init 신규 레포 모드** (모드 감지 #2): 버전 파일 부트스트랩 단계 추가 — versionLocations 대상 파일이 없는 신생 레포는 Phase 3 자가검증(`version.py verify`) 전에 그 파일(예: `package.json`·`VERSION`·`gradle.properties`) 생성을 확인한다(프로즈 안내, init이 대화 중 초기 버전으로 생성). 절대 규칙("Phase 3 전 파일 생성 금지")과의 관계 명확화 — 버전 파일 부트스트랩은 Phase 3 렌더의 일부로 사용자 확인 후 수행.
3. **config 스키마 상호 참조**: 재init 절의 "config를 손으로 고친 뒤 재init" 언급에 README config 섹션 포인터를 정합(양방향).

## 파트 3 — 생성 스킬 프로즈 (Tier 3, 골든 변경)

1. **§7 빈 섹션 게이트** (`release/SKILL.md`): `## 7. 태그...` 헤더부터 §7 끝까지 전체를 `{{#if scope.tag.enabled}}...{{/if}}`로 감싼다. tag.enabled=true(정상 config 전부)는 렌더 바이트 동일, tagless-app(tag.enabled=false)은 §7 전체 collapse. 기존 내부 `{{#if scope.tag.enabled}}`/`{{#if github.release}}` 블록은 바깥 게이트 안으로 재구성.
2. **§5 github-release 범례 게이트** (`release/SKILL.md`, `release-monorepo/SKILL.md`): `- github-release: ...` 불릿을 `{{#each scope.notes.destinations}}{{#if this == "github-release"}}...{{/if}}{{/each}}`로 게이트(fragment·tag-message 선례와 동일). §7 게이트 후 dangling "7단계" 참조 방지. 골든 영향: github-release 목적지 없는 config만(fragment-app·tagless-app; monorepo 골든은 전부 github-release 보유 → 무변경).
3. **release-pr gh-auth preflight** (`release/SKILL.md`, `release-monorepo/SKILL.md`, `release-train/SKILL.md`): gh 인증 preflight item을 `github.release` 단독 게이트에서 "github.release **또는** releasePath release-pr"로 확장(동결 dialect에 OR 없음 → 중첩 `{{#if}}`). release-pr은 github.release 무관하게 gh(pr create/list)를 쓰므로. 골든 영향: 기존 release-pr 골든은 전부 github.release=true라 item이 이미 렌더 → 무변경. 신규 골든 `release-pr-nogh`(release-pr + github.release=false)로 이 경로를 핀.
4. **공통 규칙 개행 위생** (`release/SKILL.md`): `{{#if github.release}}- GitHub 접근...{{/if}}` collapse 시 남는 이중 공백을 개행을 블록 안으로 옮겨 정리. 골든 영향: github.release=false config(tagless-app)만.

## 파트 4 — 테스트·골든

- **Tier 1+2 골든 무영향 검증**: 외부 문서·init·references는 골든 미복사 → `python3 tests/update_golden.py && git status --porcelain tests/golden` 빈 출력.
- **Tier 3 골든**: 영향 골든 재생성 — `tagless-app`(§7 collapse·§5 github-release 제거·개행 위생), `fragment-app`(§5 github-release 제거). 신규 골든 `release-pr-nogh`(release-pr + github.release=false, destinations changelog만 — gh preflight 핀). 그 외 골든 바이트 불변.
- **렌더 단위 테스트**(test_assets): §7 tag.enabled=false collapse / §5 github-release 목적지 게이트(있음·없음) / release-pr gh preflight(github.release=false여도 렌더) / trunk 정상 config 바이트 불변 핀.
- 골든 총수 19 → 20(release-pr-nogh 신설).

## 제약·검증

- 동결 template dialect(OR 없음 — 중첩 `{{#if}}`). 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진·자산 스크립트 무변경 — Tier 3는 생성 스킬 프로즈만, Python 변경 없음.
- **바이트 불변**: Tier 3 게이트는 정상 config(tag.enabled=true, github.release=true 등)에서 렌더 바이트 동일 — 영향 골든만 재생성되고 나머지는 diff 0.
- README EN/KO 1:1(운영 규율). 자립성·코드 영어·프로즈 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인.

## 비범위 (후속)

- superrelease 자기 dogfooding(자기 툴킷으로 v0.1.0 릴리스) — 별도 작업.
- config 스키마를 `.superrelease/`로 렌더(새 asset=기능).
- §5 changelog·release-file 범례 게이트(dangle 없음 — 대규모 golden churn 회피).
- release-monorepo §8 per-scope 태그의 tagless 게이트(tagless 모노레포 골든 부재·release-pr×tagless는 validate 거부).
- M4b-2 gitflow hotfix / 이연 minor 중 코드 정상 확인된 테스트 커버리지 갭.

## 예상 태스크 (writing-plans에서 확정)

1. 외부 문서 — README.md·README_KO.md 로드맵·표·Uninstall·매트릭스·Upgrading·config 섹션(1:1), CLAUDE.md, CHANGELOG. 골든 diff 0 검증.
2. init/references 프로즈 — Phase 3 요약·신규 레포 부트스트랩·config 상호참조. 골든 diff 0 검증.
3. 생성 스킬 Tier 3 — §7 게이트·§5 github-release 게이트·gh preflight OR·개행 위생 + 렌더 단위 테스트 + 영향 골든 재생성(tagless-app·fragment-app) + 나머지 바이트 불변.
4. 신규 골든 `release-pr-nogh` + gh preflight 핀.
5. 최종 검증(전체 스위트·plugin validate·라인 예산·골든 범위).
