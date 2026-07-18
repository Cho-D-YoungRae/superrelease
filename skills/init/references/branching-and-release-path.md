# 브랜칭 전략과 릴리스 경로

이 문서는 init이 브랜칭 전략과 릴리스 커밋 경로(direct push vs 릴리스 PR)를 제안할 때 참고하는 배경 지식이다.

| | trunk-based / GitHub flow | git flow |
|---|---|---|
| 상시 브랜치 | main 하나 | main + develop |
| 릴리스 방식 | main에서 바로 | release/* 브랜치를 거쳐 |
| 병렬 유지보수 | 기본적으로 없음 | release/1.x 등으로 지원 |
| 적합한 대상 | 대부분의 신규 프로젝트 | 여러 버전을 동시 지원해야 하는 제품 |

## 신규 프로젝트 기본값: trunk-based / GitHub flow

새로 시작하는 프로젝트에는 trunk-based 개발(또는 GitHub flow)을 기본으로 제안한다.

둘 다 브랜치 하나(main)를 항상 배포 가능한 상태로 유지한다는 원칙을 공유한다.

- 기능 작업은 짧게 사는 브랜치에서 한다.
- PR로 리뷰·CI를 거쳐 곧바로 main에 합쳐진다.
- 릴리스도 그 main에서 바로 만든다.

develop이나 release 브랜치를 별도로 유지하며 서로 동기화할 필요가 없으므로, 브랜치 사이에서 커밋이 누락되거나 꼬이는 실수도 원천적으로 줄어들고 릴리스 마찰이 가장 적다.

참고: [trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/)

엄밀히는 두 용어가 완전히 같지는 않다. trunk-based 개발은 브랜치 수명을 짧게 유지한다는 광범위한 개발 원칙을 가리키고, GitHub flow는 그 원칙을 GitHub의 PR 기반 워크플로로 구체화한 실무 절차에 가깝다. 이 문서와 init에서는 두 용어를 "main 하나에서 릴리스하는 단순한 흐름"이라는 공통점을 기준으로 함께 다룬다.

## git flow 지원 — 릴리스 사이클

git flow는 2010년 Vincent Driessen이 제안한 브랜칭 모델로, `develop`을 상시 통합 브랜치로 두고 `release/*`, `hotfix/*` 브랜치를 통해 릴리스와 긴급 수정을 별도로 관리한다.

참고: [nvie.com의 원문 글](https://nvie.com/posts/a-successful-git-branching-model/)

**superrelease는 gitflow 정식 릴리스 사이클을 지원한다** — config `repo.branching: "gitflow"` + `repo.developBranch`(통합 브랜치명). release-pr 전용이며(render가 다른 조합을 거부), **단일 레포와 independent 모노레포 모두 지원한다**(모노레포는 release-monorepo 스킬이 라운드 단위로 수행 — 여러 scope를 한 develop→main 사이클에 묶어 릴리스한다). 범위·변경 감지·중단 감지의 앵커는 태그가 아니라 **기본 브랜치**(`origin/<defaultBranch>`)로 통일되어 있다 — develop이 기본 브랜치보다 앞선 커밋 구간이 곧 "이번 라운드에 나갈 변경"이며, 태그 유무와 무관하게 성립한다. 사이클은 다음과 같다.

1. preflight가 통합 브랜치(develop)를 기준으로 검사하고, 릴리스 브랜치(`release/<버전>`, 모노레포 라운드는 `release/<라운드>`)를 develop에서 cut해 버전 bump·노트를 커밋한다.
2. PR base는 기본 브랜치(main)다 — PR이 열려 있는 동안 release 브랜치에 안정화 커밋을 쌓는 gitflow 관례가 그대로 성립한다. 머지는 사람과 레포 정책의 몫이다.
3. 머지 후 재개 시 기본 브랜치의 머지 커밋에 태그를 만든다 — **단, gitflow에서는 태그가 선택 사항이다**(`tag.enabled: false`도 허용된다); tagless scope는 이 단계를 건너뛴다.
4. **back-merge**: (태그를 쓰는 scope는 태그 push 후, tagless면 머지 확인 후) `main → develop`을 merge해 동기화한다(충돌은 사용자와 해결, develop이 보호돼 있으면 back-merge PR). postRelease가 next-snapshot이면 복귀 커밋은 back-merge 후 develop에서만 수행한다 — main은 릴리스 버전을 유지한다(Maven gitflow 관례).

중단 상태 감지도 gitflow 전용 패턴으로 동작한다 — 머지된 최신 release PR의 후처리가 남아 있으면: ① 태그를 쓰는 scope 중 그 라운드 태그가 없으면 태그부터 재개(**tagless scope는 건너뛴다**) ② 기본 브랜치가 develop에서 도달 불가(`git merge-base --is-ancestor origin/<defaultBranch> HEAD` 실패 — back-merge 누락, 복구) ③ develop의 mutable scope 파일 버전이 bare(수식어 없음)면 SNAPSHOT 복귀부터. 파일 버전 기반 감지는 develop에서 미탐이라 쓰지 않는다.

gitflow의 **hotfix 흐름**(main HEAD에서 `hotfix/*` cut → patch bump → main 머지·태그 → develop back-merge + SNAPSHOT 복귀)은 hotfix 스킬이 수행한다 — gitflow 레포면 `maintenanceLines` 없이도 hotfix 스킬이 생성된다(production hotfix는 gitflow에 내재된 흐름이다). 아래 병렬 유지보수 라인은 별개 개념이다(과거 메이저 라인 패치).

## 병렬 유지보수 라인이 필요한 경우

여러 released 버전을 동시에 유지보수해야 하는 제품 — 예를 들어 `release/1.x`를 계속 패치하면서 동시에 `release/2.x`나 main도 따로 진행하는 경우다.

이렇게 병렬 유지보수 라인을 운영하는지 여부(config `repo.maintenanceLines`)가 **trunk 레포에서** hotfix 스킬을 생성할지 말지를 가르는 조건이다(gitflow 레포는 위 production hotfix로 항상 생성된다) — trunk에서 유지보수 라인이 없다면 hotfix 스킬 자체가 필요 없다.

**hotfix 스킬은 `repo.maintenanceLines: true` 또는 `repo.branching: gitflow`면 생성된다** — 두 경로 모두 semver scope 한정이다(calver/headver는 patch-bump가 부적합해 render가 거부). independent 모노레포와의 조합은 `maintenanceLines`(trunk 유지보수 라인) 경로에서만 거부되며, **gitflow 경로는 independent 모노레포에서도 지원된다**(scope별 production hotfix, `bundle.enabled`면 그 hotfix도 라운드로 취급되어 라운드 노트를 만든다). gitflow면 production hotfix 흐름(main cut → develop back-merge)으로, trunk+maintenanceLines면 유지보수 라인 흐름(`release/1.2.x` 패치)으로 렌더된다(gitflow+maintenanceLines면 gitflow 흐름).

반대로 과거 메이저 버전에 대한 보안 패치를 계속 내야 하는 라이브러리나 엔터프라이즈 제품이라면, trunk-based만으로는 "이미 릴리스된 옛 버전에 패치를 얹는" 시나리오를 감당하기 어렵다.

유지보수 라인을 운용하는 레포에서 hotfix 스킬이 생성되면, 그 스킬은 대략 다음 흐름을 따르게 된다.

1. 문제가 된 released 버전에 대응하는 유지보수 브랜치(예: `release/1.2.x`)를 체크아웃한다.
2. 고쳐야 할 커밋을 그 브랜치로 체리픽한다.
3. patch 릴리스를 만든다 (release 흐름 재사용).
4. 그 수정을 main에도 반영할지 확인한다 — gitflow 레포면 develop 반영도 함께 확인한다.

## protected branch 감지 시: 릴리스 PR 모드

기본 브랜치가 protected branch로 설정되어 있고 required status checks까지 걸려 있으면, main에 직접 push하는 release 흐름이 애초에 불가능하다.

이 경우에는 버전 bump와 노트를 커밋 대신 PR로 올리고, 그 PR이 머지되는 시점에 태그가 트리거되는 **릴리스 PR 모드**로 전환해야 한다 — release-please가 쓰는 방식과 같다.

**릴리스 PR 모드는 config `repo.releasePath: "release-pr"`로 설정하면 릴리스 스킬이 수행한다.** 진행은 2단계다 — 버전 bump와 노트를 담은 PR을 만들고 일단 중단하며, PR이 머지된 뒤 릴리스를 다시 요청하면 태그와 Release를 만든다(릴리스 스킬의 중단 상태 감지가 이 대기 상태를 인식한다). 스킬은 required checks 대기나 자동 머지를 하지 않는다 — 머지는 사람과 레포 정책의 몫이다.

릴리스 PR 재개는 **기존 릴리스 태그가 있다는 전제**에 기댄다 — 중단 상태 감지가 "파일 버전 > 마지막 태그"로 판정하기 때문이다. 그래서 태그를 만들지 않는 scope(`tag.enabled: false`)는 릴리스 PR 모드와 함께 쓸 수 없고 init·render가 이 조합을 거부한다. 또한 첫 릴리스(아직 태그가 하나도 없는 상태)는 병합 후 자동 재개가 감지되지 않으므로, 첫 태그까지는 수동으로 태그 단계를 진행한다.

릴리스 PR 모드를 선택했는데 기본 브랜치가 실제로는 **보호되지 않았다면** 그 PR 흐름은 강제력이 없다 — 누구나 main에 직접 push할 수 있기 때문이다. 그래서 init은 이 조합(release-pr + 미보호)을 감지하면 보호 설정을 **조언**한다. 현대적 방법은 repository ruleset(`gh api --method POST repos/{owner}/{repo}/rulesets` — 기본 브랜치에 `pull_request` 필수와, CI가 있으면 `required_status_checks`를 거는 규칙)이고, 클래식 방법은 branch protection(`gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection`)이며, 웹 UI로는 Settings → Rules → Rulesets에서 만든다.

이 설정은 레포의 보안·접근 규칙이므로 **사용자가 직접 실행한다** — init·생성 스킬은 명령을 제시할 뿐 대신 실행하지 않는다(감지·조언은 범위, 설정 변경은 비범위). 이는 CI 태그 트리거를 감지·경고만 하고 워크플로를 생성하지 않는 것, dev 채널 immutableId를 기록·안내만 하는 것과 같은 원칙이다.

protected branch가 감지되면 init은 release-pr 모드를 강제 기본으로 제안한다 — direct push로는 대체할 수 없기 때문이다.

## "태그 생성 = 배포 버튼" 인지

`.github/workflows/*.yml` 중 `on.push.tags`로 트리거되는 워크플로가 있으면, 그 레포에서는 태그를 만드는 행위 자체가 곧 배포를 일으키는 버튼이나 다름없다.

예를 들어 워크플로에 다음과 같은 트리거가 있으면 태그 push가 곧 배포다.

```yaml
on:
  push:
    tags:
      - 'v*'
```

scan.py는 표준 라이브러리만으로 동작하기 때문에 YAML을 제대로 파싱하지 않고 정규식 휴리스틱으로 `on.push.tags`처럼 보이는 후보 워크플로 파일 목록만 뽑아낸다.

정규식 휴리스틱은 오탐이 있을 수 있다 — 예를 들어 주석 처리된 트리거나 다른 목적의 `tags:` 키를 잘못 후보로 집어낼 수 있다. 그래서 scan.py의 출력은 어디까지나 "후보 파일 목록"이고, 최종 판단은 Claude가 그 파일들을 직접 읽어 확정한다.

확정되면 이 사실을 config `repo.tagTriggersDeployment`에 기록해두고, 릴리스 스킬의 dry-run 프리뷰에 반드시 경고로 노출한다 — 사용자가 "그냥 태그만 만든다"고 가볍게 생각하고 승인했다가 의도치 않게 배포까지 실행되는 상황을 막기 위함이다.

## 릴리스 커밋 경로 결정 트리

1. 기본 브랜치가 protected + required checks인가?
   - 예 → 릴리스 PR 모드로 진행해야 한다 (`repo.releasePath: "release-pr"` — direct push로 대체할 수 없다)
   - 아니오 → direct push로 진행한다 (기본 경로)

이 결정은 스캔 단계에서 GitHub API로 확인한 protected branch·required checks 정보를 바탕으로 하며, 판단 결과는 질문 단계에서 사용자에게 확인형으로 다시 보여준다.

릴리스 스킬의 preflight 단계도 이 결정을 그대로 이어받는다. direct push 경로인 레포에서는 현재 브랜치가 기본 브랜치와 일치하는지를 검사하고, 일치하지 않으면 릴리스를 진행하지 않는다.
