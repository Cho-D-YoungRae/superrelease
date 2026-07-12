# superrelease M3b.1 — 브랜치 보호 조언 + M3b 리뷰 follow-up 설계

이 문서는 M3b(릴리스 경로) 이후의 하드닝 마일스톤 **M3b.1**의 설계다. 두 부분으로 구성된다: (A) 신규 기능 **브랜치 보호 조언**, (B) M3b 최종 whole-branch 리뷰가 남긴 follow-up 3종.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md) (§4.3 질문 번들 6, §6.8 config.decisions, §13 비범위). 베이스 커밋: main `fea5a92`.

## 배경

init은 스캔 단계에서 `gh api repos/{owner}/{repo}/branches/<기본브랜치>/protection`으로 보호 상태를 **읽어** 릴리스 PR 모드 결정을 구동한다(보호됨 → release-pr 강제). 그러나 릴리스 PR 모드를 선택했는데 기본 브랜치가 **실제로는 보호되지 않은** 경우, 그 PR 흐름은 강제력이 없다(누구나 직접 push 가능). init이 이 갭을 감지하면서도 보호 설정을 **수립하도록 돕지 않는다**는 것이 이 마일스톤이 닫는 갭이다.

플러그인의 일관된 철학은 "감지하고 조언하되 실행하지 않는다"이다 — CI 태그 트리거(감지·경고만), devChannel.immutableId(기록·스니펫 안내만), 아티팩트 publish(태그까지만, 배포는 FAQ). 브랜치 보호도 같은 틀에 넣는다.

## A. 브랜치 보호 조언

### 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 조언 형태 | init 대화 중 일회성 안내 (렌더 아티팩트 없음) | 기존 감지→조언 패턴과 동일, YAGNI |
| 트리거 | `releasePath == "release-pr"` + 기본 브랜치 미보호일 때만 | 가장 정확한 교육 지점, 잔소리 없음 |
| config 발자국 | `config.decisions`에 조언 사실 1항목 기록 | init의 결정 감사 원칙과 일관, 새 스키마 필드 없음 |

### 동작

1. init이 번들 6에서 커밋 경로를 `release-pr`로 확정하고, 스캔이 기본 브랜치를 **미보호**로 읽었을 때만 조언을 띄운다. 이미 보호됨 → 조언 없음. gh 미가용으로 보호 상태를 못 읽었으면 → 기존처럼 질문으로 폴백하고 일반 권고만 언급한다.
2. init은 사용자가 **직접 실행할** 명령을 제시한다. 우선순위:
   - **repository ruleset (현대적, 우선 권장)**: `gh api --method POST repos/{owner}/{repo}/rulesets ...` — 기본 브랜치에 pull request 필수 + status check 필수를 거는 ruleset. (레포 관리자 권한 필요를 명시)
   - **classic branch protection (대안)**: `gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection ...`.
3. init은 이 명령을 **절대 실행하지 않는다** — "레포 보안 설정이라 직접 실행하세요"라고 명시한다. 웹 UI 경로(Settings → Rules → Rulesets)도 병기한다.
4. init은 `config.decisions`에 한 항목을 남긴다: `{ "topic": "branch-protection", "answer": "advised" | "already-protected", "rationale": "<근거>", "source": "scan", "decidedAt": "<date>" }`. 재init 시 여전히 미보호면 다시 안내한다(갭이 살아있으므로 적절).

### 지식 문서

`references/branching-and-release-path.md`의 "protected branch 감지 시: 릴리스 PR 모드" 절에, 미보호+release-pr일 때 init이 보호 설정을 조언한다는 배경과 ruleset/classic 두 경로, "실행은 사용자 몫" 원칙을 보강한다.

### 안전·비범위

레포 보안/접근 설정 변경은 사용자가 직접 해야 한다 — init은 조언만 한다. 스펙 §13 비범위의 "브랜치 보호 규칙 설정 변경"은 그대로 유지하되, **조언(감지 후 명령 제시)은 범위**임을 한 줄로 명확화한다.

### 골든 영향

없음 — init SKILL.md·references·`config.decisions`(init이 런타임에 Write)는 모두 골든-복사 대상이 아니다.

## B. M3b 리뷰 follow-up 3종

M3b 최종 whole-branch 리뷰가 비차단으로 분류한 항목 중 3종을 정리한다.

- **#4 — 비semver hotfix 방어**: `render.py`의 `validate_config`에 규칙 1건 추가 — `repo.maintenanceLines`가 truthy인데 어떤 scope의 `scheme.type`이 semver가 아니면 config 오류(exit 1). hotfix 스킬은 `--bump patch`를 하드코딩하므로 calver/headver scope에는 무의미하다. 기존 `independent`·`tagless` 거부 규칙과 일관한 방어. config는 손편집 SSOT이므로 render 강제가 init 잠금보다 견고하다. (골든 무영향 — 해당 조합 골든 없음)
- **#5 — release-pr + next-snapshot 골든**: release-pr 경로와 postRelease `next-snapshot`이 함께 렌더되는 `chore/next-dev` 복귀 커밋 라인(§8)을 스냅샷으로 고정한다. 현재 unit 테스트(`test_release_skill_release_pr_branch`)만 이 라인을 확인한다. 신규 골든 1트리(예: `release-pr-snapshot` — release-pr + 기본 mutable/next-snapshot)를 추가한다.
- **#2 — hotfix+release-pr 재개 한계 명시**: 생성되는 hotfix 스킬의 release-pr 분기(§5)에 한 줄 추가 — hotfix+release-pr의 머지 후 재개는 자동 감지되지 않으므로(hotfix preflight에 중단 상태 감지 단계가 없음) 머지 후 태그 단계를 수동 진행하라고 명시한다. hotfix-library 골든은 direct-push라 이 분기가 collapse되어 **바이트 불변**.

### 비범위 (M3c 또는 후속)

- hotfix preflight에 실제 중단 상태 감지 단계를 추가하는 full 지원(문서화로 대체).
- 첫 릴리스 release-pr 재개 자동 감지(1회성·human-gated — M3b에서 이미 문서화).
- 중단 감지가 SNAPSHOT/counter에서 릴리스 시작 시 오탐하는 문제(M1부터 기존, M3b 회귀 아님).

## 제약·검증

- 동결 template dialect·생성 스크립트 산술 무변경. 유일한 Python 변경은 `render.py` `validate_config` 규칙 1건(#4).
- 기존 8골든 바이트 불변, #5만 신규 1트리 추가. `git status --porcelain tests/golden`으로 범위 검증.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어·생성 문서 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인.

## 예상 태스크 (writing-plans에서 확정)

1. #4 render 거부 규칙(TDD) + #2 hotfix 스킬 release-pr 재개 한계 한 줄.
2. init 번들 6 브랜치 보호 조언 + `config.decisions` 항목 + `branching-and-release-path.md` 보강 + 스펙 §13 "조언은 범위" 명확화.
3. #5 골든 신규 1트리 + 최종 검증.
