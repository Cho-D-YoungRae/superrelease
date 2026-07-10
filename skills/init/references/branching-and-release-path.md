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

## git flow가 필요한 경우

git flow는 2010년 Vincent Driessen이 제안한 브랜칭 모델로, `develop`을 상시 통합 브랜치로 두고 `release/*`, `hotfix/*` 브랜치를 통해 릴리스와 긴급 수정을 별도로 관리한다.

참고: [nvie.com의 원문 글](https://nvie.com/posts/a-successful-git-branching-model/)

이런 구분은 여러 released 버전을 동시에 유지보수해야 하는 제품에만 필요하다. 예를 들어 `release/1.x`를 계속 패치하면서 동시에 `release/2.x`나 main도 따로 진행하는 경우다.

이렇게 병렬 유지보수 라인을 운영하는지 여부(config `repo.maintenanceLines`)가 곧 hotfix 스킬을 생성할지 말지를 가르는 조건이다 — 유지보수 라인이 없다면 hotfix 스킬 자체가 필요 없다.

**hotfix 스킬 생성 자체는 M3에서 구현되며, M1에서는 아직 생성되지 않는다.**

반대로 과거 메이저 버전에 대한 보안 패치를 계속 내야 하는 라이브러리나 엔터프라이즈 제품이라면, trunk-based만으로는 "이미 릴리스된 옛 버전에 패치를 얹는" 시나리오를 감당하기 어렵다.

유지보수 라인을 운용하는 레포에서 hotfix 스킬이 생성되면, 그 스킬은 대략 다음 흐름을 따르게 된다.

1. 문제가 된 released 버전에 대응하는 유지보수 브랜치(예: `release/1.2.x`)를 체크아웃한다.
2. 고쳐야 할 커밋을 그 브랜치로 체리픽한다.
3. patch 릴리스를 만든다 (release 흐름 재사용).
4. 그 수정을 main에도 반영할지 확인한다.

## protected branch 감지 시: 릴리스 PR 모드

기본 브랜치가 protected branch로 설정되어 있고 required status checks까지 걸려 있으면, main에 직접 push하는 release 흐름이 애초에 불가능하다.

이 경우에는 버전 bump와 노트를 커밋 대신 PR로 올리고, 그 PR이 머지되는 시점에 태그가 트리거되는 **릴리스 PR 모드**로 전환해야 한다 — release-please가 쓰는 방식과 같다.

**이 모드는 M3에서 구현되며, M1은 direct push 경로만 지원한다.**

M1 단계에서 protected branch가 감지되면, 릴리스 PR 모드가 아직 없다는 사실과 함께 "후속 버전 지원 예정"이라고 안내한다.

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
   - 예 → 릴리스 PR 모드로 진행해야 한다 (M3에서 지원 — M1에서는 "후속 버전 지원 예정"으로 안내하고 direct push로 대체할 수 없음을 분명히 한다)
   - 아니오 → direct push로 진행한다 (M1 기본 지원 경로)

이 결정은 스캔 단계에서 GitHub API로 확인한 protected branch·required checks 정보를 바탕으로 하며, 판단 결과는 질문 단계에서 사용자에게 확인형으로 다시 보여준다.

릴리스 스킬의 preflight 단계도 이 결정을 그대로 이어받는다. direct push 경로인 레포에서는 현재 브랜치가 기본 브랜치와 일치하는지를 검사하고, 일치하지 않으면 릴리스를 진행하지 않는다.
