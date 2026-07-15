# superrelease M4b — gitflow 브랜칭 축 지원 설계

이 문서는 M4 로드맵의 두 번째 마일스톤 **M4b**의 설계다. 2026-07-15 전면 리뷰에서 5축 중 최약("침묵 미지원")으로 판정된 gitflow 브랜칭 축을 닫는다 — 죽은 `repo.branching` 필드를 실소비 enum으로 확정하고, develop 통합 브랜치에서 릴리스하는 **gitflow 정식 릴리스 사이클**(develop에서 cut → main 머지·태그 → develop back-merge + SNAPSHOT 복귀)을 지원한다.

M4 로드맵: M4a 정확성(랜딩 완료, PR #12) → **M4b gitflow(본 문서)** → M4c 스캔 커버리지 → M4d 사용성·문서.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md), [2026-07-15-superrelease-m4a-correctness-design.md](2026-07-15-superrelease-m4a-correctness-design.md). 베이스 커밋: main `267dd3a`.

## 배경

전면 리뷰의 (c) git flow 축 판정: `repo.branching`은 config에 기록만 되고 assets·스크립트 어디서도 소비되지 않는 **죽은 필드**이고, scan.py가 수집하는 `branches.hasDevelop`을 init이 소비하지 않으며, "지원 범위와 제약" 절에 브랜칭 축 자체가 없어 gitflow 미지원이 **침묵**이다. 결과: defaultBranch=main인데 develop에서 릴리스하는 팀은 preflight 1에서 무조건 차단되고, defaultBranch=develop으로 우회하면 태그·릴리스 커밋이 develop에만 남고 main 반영은 아무도 하지 않는다.

구조적 발견: superrelease의 기존 **release-pr 2단계**(bump 커밋 → PR → 머지 → 태그 재개)는 gitflow 릴리스 사이클과 동형이다 — 차이는 ① 릴리스 브랜치를 main이 아닌 develop에서 cut ② 머지 후 develop back-merge + SNAPSHOT 복귀 단계뿐. preflight가 develop을 기준 브랜치로 요구하면 §6의 `git checkout -b release/<버전>`은 자동으로 develop에서 일어나고 PR base는 이미 main이므로, 지원 비용이 구조 변경이 아니라 **조건 블록 추가** 수준이다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 스코프 | gitflow 정식 릴리스 사이클 지원, **단일 스킬 레포 한정** | 사용자 결정. 모노레포×gitflow는 조합 폭발 — validate 거부 + 후속 표시(hotfix×independent 선례와 동형) |
| 구현 형태 | 기존 release 스킬에 `{{#if repo.branching == "gitflow"}}` 조건 블록(접근 A) | 흐름이 release-pr과 구조 동형(파라미터만 상이). 별도 스킬 변형(접근 B)은 프로즈 절반 이상이 3중 중복 |
| 릴리스 경로 | **release-pr 전용** — gitflow면 validate가 releasePath를 강제 | 사용자 결정. "머지는 사람과 레포 정책의 몫" 원칙 유지, PR이 열린 동안 release 브랜치에 안정화 커밋을 쌓는 gitflow 관례가 자연 지원됨 |
| 중단 상태 감지 | gitflow 전용 2종으로 교체: (a) **머지됐는데 미태깅**인 release PR → 태그 재개 (b) **최신 릴리스 태그가 develop에서 도달 불가** → back-merge 재개 | 기존 파일버전-기반 감지는 develop에서 미탐(머지 직후 develop은 여전히 `-SNAPSHOT`). gitflow=release-pr 전용=gh 전제라 gh 기반 감지가 성립 |
| back-merge | 태그 push 후 `main → develop` 로컬 merge + push. 충돌은 사용자와 해결, push 거부(develop 보호) 시 back-merge PR 안내 | 표준 관례(태그 커밋 포함). 완전한 develop 보호 대응은 비범위 — 안내로 한정 |
| SNAPSHOT 복귀 위치 | postRelease next-snapshot 복귀 커밋은 back-merge 후 **develop에서만** — main은 릴리스 버전 유지 | Maven gitflow 관례. main·develop의 버전 파일이 다른 것이 정상 상태 |
| developBranch | `repo.developBranch` 필드 신설 — gitflow면 필수(스캔 감지값, 관례 기본 `"develop"`), trunk면 null | 통합 브랜치명은 가변(dev, development 등) |
| hotfix | 정식 gitflow-hotfix 흐름(main에서 hotfix/* cut)은 **M4b-2로 분리**. 이번엔 기존 hotfix 스킬 §7 반영 확인에 gitflow 시 develop 병기 1줄만 | 사용자 결정. 기존 maintenanceLines 모델은 gitflow 레포의 병렬 라인 패치로 계속 유효 — 조합 허용 유지 |

## A. config 스키마 + validate_config (규칙만 추가, 엔진 불변)

스키마: `repo.branching`은 기존 필드(지금까지 `"trunk"` 고정 기록), `repo.developBranch`를 신설한다(trunk면 `null`). init SKILL.md의 정본 스키마 예시에 `"developBranch": null`을 추가한다.

validate 규칙 5종:

1. `repo.branching` ∈ {`"trunk"`, `"gitflow"`} — 그 외 값 거부. 기존 config는 전부 `"trunk"`라 통과.
2. gitflow → `repo.releasePath`가 `"release-pr"`이 아니면 거부 (예: `"branching gitflow requires releasePath release-pr: the release cycle is PR-based (cut from develop, merge to the default branch)"`).
3. gitflow → `repo.kind`가 `"monorepo"`(또는 `monorepoStrategy` 설정)면 거부 — 단일 스킬 레포 한정, 메시지에 후속 지원 예정 언급.
4. gitflow → `repo.developBranch`가 비어 있으면 거부.
5. gitflow → `repo.developBranch == repo.defaultBranch`면 거부 (통합 브랜치와 릴리스 대상 브랜치가 같으면 gitflow가 아니다 — trunk를 쓰라는 메시지).

마이그레이션: 기존 config는 branching `"trunk"` + developBranch 부재 → 규칙 1만 적용되고 통과. `configVersion` 1 유지(필드 추가·제약 추가뿐).

## B. init — 번들 6 확장 + 지원 범위

- **브랜칭 질문 신설**: 스캔 `branches.hasDevelop`이 true면(현재 수집만 되고 미소비) 번들 6에서 브랜칭 전략을 명시적으로 묻는다 — "develop 통합 브랜치가 감지됐다: ① trunk 유지(develop 정리 권장 — 추천) ② gitflow(develop에서 릴리스 cut)". hasDevelop이 false여도 선택지에 gitflow는 존재한다(추천은 trunk).
- gitflow 선택 시: `releasePath`를 `"release-pr"`로 잠그고(protected 여부와 무관 — 사이클이 PR 기반이므로), `developBranch`를 감지된 이름으로 확정하고, 릴리스 사이클(develop cut → PR to main → 머지 후 태그 → back-merge + SNAPSHOT 복귀)을 안내한다. 기존 보호-조언 로직(미보호 main에 release-pr)은 그대로 적용된다. 결정을 `decisions`에 기록.
- **지원 범위와 제약** 절에 브랜칭 축 추가: "브랜칭: trunk / gitflow(단일 스킬 레포 · release-pr 전용 — develop cut → main 태그 → back-merge 정식 사이클) 지원. gitflow hotfix 흐름(main에서 hotfix/* cut)·모노레포×gitflow·direct-push gitflow는 후속".

## C. release 스킬 gitflow 분기 (조건 블록 — 트렁크 config는 0바이트 collapse)

- **preflight 1·3 기준 브랜치 인라인**: `{{repo.defaultBranch}}` 두 곳을 `{{#if repo.branching == "gitflow"}}{{repo.developBranch}}{{else}}{{repo.defaultBranch}}{{/if}}`로 — trunk 렌더는 기존과 바이트 동일.
- **preflight 6 감지 분기**: 기존 `{{#if scope.tag.enabled}}` 게이트 안에서 gitflow/trunk를 중첩 분기한다(gitflow는 release-pr 전용이고 release-pr×tagless는 기거부라 태그 전제 성립).
  - (a) 미태깅 머지 PR: `gh pr list --state merged --json headRefName,mergedAt`의 `release/<버전>` head 중 그 버전의 태그가 없으면 이전 릴리스가 태그 전에 중단된 것 — §7(태그)부터 재개하라(태그는 `{{repo.defaultBranch}}` 머지 커밋에).
  - (b) back-merge 누락: 최신 릴리스 태그(M4a의 glob+versionsort 규칙)가 현재 브랜치에서 도달 불가하면(`git merge-base --is-ancestor <태그> HEAD` 실패) 직전 릴리스의 back-merge가 누락된 것 — §8의 back-merge부터 복구하라. 이 검사가 §2 범위 산출(anchor가 develop에서 도달 가능해야 함)의 전제를 preflight에서 확립한다.
  - trunk 분기는 M4a 문구 그대로(바이트 불변).
- **preflight 7(열린 PR 가드)·§2·§6·§7**: 무변경 — 열린 `release/*` PR 가드, anchor 규칙, cut(§6 — preflight 1 덕에 develop에서 자동), PR base main, 머지 후 재개(checkout main → 태그)가 전부 gitflow에서 그대로 유효하다. §6에 gitflow 안내 프로즈가 필요하면 1줄 이내(플랜에서 확정).
- **§8 post-release 확장**: gitflow 게이트 블록 — 태그 push 후 ① `git checkout {{repo.developBranch}} && git pull` → `git merge {{repo.defaultBranch}}`(충돌 시 사용자와 해결·확인) → push. push 거부(develop 보호) 시 back-merge PR을 만들라고 안내. ② postRelease가 next-snapshot이면 복귀 커밋(`next-version.py --bump patch --qualifier ...` → `version.py set`)을 back-merge 후 develop에서 수행 — main은 릴리스 버전 유지. 기존 trunk 프로즈의 release-pr `chore/next-dev` 후속 PR 규칙은 gitflow에 부적용(develop 직접 push 기본)이므로 분기로 정리한다. 전 단계 dry-run 프리뷰 → 확인 규율 동일 적용.
- 라인 예산: 현재 102줄 + 추정 12~18줄 ≤150 (플랜에서 실측).

## D. 테스트·골든

- **골든 신설 1종** (18 → 19): `gitflow-app` — gradle.properties + branching `"gitflow"` + developBranch `"develop"` + releasePath `"release-pr"` + mutable SNAPSHOT + postRelease next-snapshot (대표적 JVM gitflow 조합). 감지 (a)(b)·back-merge·develop 복귀 프로즈를 스냅샷으로 고정.
- **validate 음성 테스트 5종**: 규칙 1~5 각 1케이스.
- **test_assets 렌더 단위**: gitflow ctx — preflight 기준 브랜치가 develop, 감지 (a)(b) 렌더, back-merge 블록 렌더, `chore/next-dev` 부재. trunk 기본 ctx — gitflow 마커 문구 전부 부재(기존과 동일 렌더).
- **기존 골든 18종 바이트 불변**: 전부 branching `"trunk"`이므로 gitflow 블록이 0바이트 collapse — `update_golden.py` 후 diff가 `gitflow-app` 신설뿐이어야 한다.

## E. references·주변 정합

- `references/branching-and-release-path.md`: gitflow 절을 "지원 선언 + 사이클 규율"로 재작성 — release-pr 전용, (a)(b) 재개 모델, back-merge·SNAPSHOT 복귀 규율, develop 보호 시 PR 폴백, hotfix 흐름은 후속임을 명시.
- `hotfix/SKILL.md` §7: 반영 확인 프로즈에 gitflow 게이트 1줄 — 체리픽 백·CHANGELOG 반영 확인 대상에 `{{repo.developBranch}}`도 병기(gitflow×maintenanceLines 조합은 계속 허용).
- README 지원 매트릭스·로드맵 갱신은 **M4d에서 일괄**(이연을 스펙에 명시 — M4d 백로그에 이미 등재).

## 제약·검증

- 동결 template dialect(AND 없음 — 필요한 곳은 중첩 `{{#if}}`), 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진 무변경 — Python 변경은 validate_config 규칙 추가뿐. 스크립트 3종 무변경.
- 바이트 불변: gitflow 블록은 개행을 블록 안에 두어 trunk config에서 0바이트 collapse. 인라인 분기(preflight 1·3)의 else 경로는 기존 텍스트와 동일해야 한다.
- 자립성: 생성물은 `.superrelease/`·`.claude/` 상대 경로만.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인(`git status --porcelain tests/golden`이 gitflow-app 신설뿐).

## 비범위 (후속)

- gitflow hotfix 정식 흐름(main에서 hotfix/* cut → main 머지·태그 → develop back-merge) — **M4b-2**.
- direct-push gitflow(스킬이 로컬에서 release/x.y → main 머지 수행).
- 모노레포(fixed·independent)·train × gitflow — validate 거부 + 후속 표시.
- develop 보호 브랜치 완전 대응 — back-merge PR 안내까지만.
- git-flow CLI 연동, README 갱신(M4d).
- **최종 리뷰 반영**: gitflow 릴리스 PR은 머지 커밋(--no-ff) 전제 — squash 머지는 태그 조상에서 develop 이력을 끊어 §2 범위를 오염시키므로 스킬이 머지 커밋을 요구한다(§2 anchor 규칙 자체는 무변경이나 머지 방식 전제가 붙는다).

## 예상 태스크 (writing-plans에서 확정)

1. validate 규칙 5종 + 음성 테스트 5종 — TDD.
2. release 스킬 gitflow 분기(preflight 1·3 인라인 + 감지 (a)(b) 중첩 분기 + §8 back-merge/develop 복귀) + 렌더 단위 테스트 + 기존 골든 바이트 불변 검증.
3. `gitflow-app` 골든 신설.
4. init 번들 6 브랜칭 질문 + 스키마 예시(developBranch) + 지원 범위 절 + references 재작성 + hotfix §7 1줄.
5. 최종 검증(전체 스위트 · plugin validate · 라인 예산 · 골든 범위).
