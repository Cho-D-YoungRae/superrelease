# 모노레포 버전 전략

모노레포는 여러 패키지가 한 레포에 같이 있다는 사실만으로 버전 전략이 저절로 결정되지 않는다.

아래 세 갈래 중 어느 쪽을 택하는지가 태그 네임스페이스, 내부 의존성 전파, scope 설정 전반에 영향을 준다.

## 전략 2종

**fixed(고정)**: 레포 안의 모든 패키지가 항상 같은 버전 번호를 공유한다. 패키지 하나만 바뀌어도 전체가 같이 bump된다.

- 대표 사례: Angular(`@angular/core`, `@angular/common`, `@angular/router` 등). 패키지 하나만 콕 집어 올린다는 개념이 없고, 항상 "Angular 17" 전체가 한 세트로 움직인다.
- 채택 이유: 각 패키지가 항상 세트로 맞물려 동작해야 한다. `@angular/core`와 `@angular/router`가 서로 다른 메이저 버전이면 호환성을 보장하기 어렵다.
- 장점: "지금 몇 버전을 쓰고 있는지" 팀 전체가 헷갈릴 일이 없다.
- 대가: 아무것도 안 바뀐 패키지까지 버전 번호만 계속 올라간다.

**independent(독립)**: 패키지마다 자기 변경 이력에 따라 따로 버전이 오른다.

- 대표 사례: Babel(`@babel/core`, `@babel/preset-env` 등). 각 패키지가 서로 다른 속도로 버전이 올라간다.
- 채택 이유: Babel의 각 플러그인은 필요에 따라 골라 쓰는 독립적인 도구에 가까워, 서로 버전이 달라도 함께 동작하는 데 지장이 없다.
- 장점: 버전 번호가 "이 패키지가 실제로 얼마나 바뀌었는지"를 정직하게 반영한다.
- 대가: 어떤 패키지가 어떤 버전과 호환되는지를 더 꼼꼼히 관리해야 한다.

**이중 체계(참고 — 지원하지 않음)**: 루트에는 CalVer 기반 release train 버전을 두고, 그 안의 개별 패키지는 자기 SemVer를 유지하는 방식이다. 대표 사례는 Spring Cloud — 루트 train은 `2020.0.x`처럼 CalVer 스타일 이름을 쓰고, `spring-cloud-config` 같은 모듈들은 각자의 SemVer를 유지하며, "이번 train에 어떤 조합이 함께 검증됐는가"를 train 버전 하나로 표현한다. superrelease는 이 방식을 지원하지 않는다 — config에 `train` 객체가 있으면 render가 거부한다. independent로 패키지를 개별 릴리스하고, 검증된 조합 공표가 필요하면 릴리스 노트나 문서에 조합 표를 남기는 운용을 권한다. 조합 공표가 목적이라면 bundle 라운드 노트가 지원되는 대안이다.

## 내부 의존성 전파

한 패키지(주로 공유 라이브러리)가 bump되면, 그 패키지에 의존하는 다른 내부 패키지도 자동으로 patch bump되어야 하는 경우가 있다.

이 관계는 config의 `dependents` 목록으로 표현한다 — 어떤 scope가 bump되면 어느 scope들을 따라서 patch bump할지를 미리 선언해두는 방식이다.

다만 전파는 연쇄로 번질 위험이 있다.

- A가 bump되어 B가 patch bump되면, B에 의존하는 C도 다시 patch bump되어야 하는지가 이어질 수 있다.
- 이 연쇄를 자동으로 끝까지 따라가 버리면 의도치 않은 범위까지 릴리스가 번질 수 있다.
- 그래서 전파를 실행하기 전에는 반드시 영향받는 패키지 전체 목록을 먼저 보여주고 확인을 받아야 하며, 각 단계에서 사람이 범위를 확인하는 편이 자동 연쇄보다 안전하다.

전파 규칙을 선언할 때는 순환 의존도 함께 확인해야 한다. A의 `dependents`에 B가 있고 B의 `dependents`에 다시 A가 있는 경우, 순환이 생겨 전파가 끝나지 않고 서로를 무한히 bump하려 든다.

## 태그 네임스페이스

모노레포에서는 태그 하나로 여러 패키지 중 무엇을 가리키는지 알 수 없으므로 패키지별로 네임스페이스를 나눈다.

changesets 관례를 따라 `{pkg}@{ver}` 포맷(예: `my-pkg@1.2.3`)을 쓰는 것이 일반적이다.

패키지 하나에 속하지 않는 루트 태그(과거에 쓰던 통합 태그, 인프라 마킹 등)가 이미 있다면 패키지 네임스페이스와 겹치지 않는지 확인해야 한다. 네임스페이스가 섞이면 anchor 계산이나 changed-packages 판별이 꼬이기 때문이다.

## scope와 변경 패키지 감지

config의 `scopes[]` 배열이 "이 레포 안에 버전 관리 대상이 몇 개 있고 각각 어디에 있는지"를 표현한다.

scope 하나는 대체로 다음 정보를 가진다.

- `name` — scope 이름
- `path` — 레포 안 경로
- `scheme` — 버전 체계
- `versionLocations` — 버전이 적힌 위치 목록
- `tag` — 태그 설정
- `bump` — bump 소스와 방식
- `notes` — 노트 목적지
- `anchor` — 마지막 릴리스 지점

모노레포에서는 이 구조체가 패키지 수만큼 배열로 늘어나고, 단일 레포에서는 배열에 항목이 하나뿐이다.

릴리스 시 "이번에 어떤 scope가 실제로 바뀌었는가"는 anchor 이후 변경된 파일 경로를 각 scope의 `path` 접두사와 대조해서 판별한다 — 이 경로 기반 감지 로직을 담당하는 것이 `changed-packages.py`다.

worked example:

- anchor 이후 `packages/foo/src/index.ts`와 `packages/bar/README.md`가 바뀌었다면 foo, bar 두 scope가 모두 변경 대상으로 판별된다.
- 반대로 루트의 `docs/`나 `.github/`만 바뀌었다면 어떤 scope의 `path` 접두사와도 일치하지 않으므로 이번 릴리스 대상에서 제외된다.

커밋 메시지나 PR 제목을 해석해서 대상 패키지를 추측하지 않고, 실제로 어느 경로 아래 파일이 바뀌었는지만 보고 기계적으로 판별한다는 점이 핵심이다.

## 노트 설정의 범위

M2에서 릴리스 노트 설정(언어·독자·어조·목적지)은 **전 scope 공통**으로 다룬다 — init은 이를 한 번만 묻고 모든 scope에 같은 값을 적용한다. 배포되는 `notes-package.md` 템플릿은 렌더 시점에 대표 scope의 `notes.language`로 ko/en 블록이 고정되므로, scope마다 다른 언어를 섞는 구성은 M2 범위 밖이다. 릴리스 노트를 실제로 쓸 때는 생성된 release-notes 스킬이 그 scope의 config `notes.*` 값을 다시 확인하도록 지시하므로, 손으로 config를 편집해 scope별 언어를 달리한 경우에도 노트 문체 자체는 그 scope 설정을 따른다(다만 템플릿 스캐폴드의 헤딩 언어는 대표 scope 기준이다).

## 지원 현황

fixed / independent 전략, `dependents` 전파, `changed-packages.py` 변경 감지가 지원된다. init이 모노레포를 감지하면 전략을 묻고, independent를 선택하면 scope를 패키지 수만큼 확장한다.

fixed는 단일 scope로 모델링된다 — 모든 패키지의 버전 파일을 root scope의 `versionLocations`에 모아 함께 bump하며, 릴리스 흐름은 단일 레포와 동일하다. independent는 scope별 태그 네임스페이스(`<scope>@{version}`)와 scope 단위 릴리스 흐름(변경 감지 → scope별 bump → scope별 태그 → dependents 전파)을 쓴다.

이중 체계(dual-system)·release-train은 지원하지 않는다(위 "전략 2종" 참고). 모노레포 backfill은 지원된다 — backfill 스킬이 scope별 태그 네임스페이스(`<scope>@{version}`)를 순회해 `## <scope>@<version>` 항목으로 소급한다(전 scope가 tagless면 render가 거부한다).

gitflow 모노레포와 bundle 라운드 노트(CalVer 파일명 라벨 — 이중 체계 train과 달리 태그·별도 스킬 없이 릴리스 흐름에 통합)는 M5부터 지원된다. gitflow는 independent 모노레포에서 develop→기본 브랜치 라운드 릴리스로 동작하며(release-monorepo 스킬이 여러 scope를 한 사이클로 묶는다), bundle은 `repo.monorepoStrategy: independent`에서만 켤 수 있다(top-level `bundle.enabled` + `scheme.type: calver` + `notesPath` — 릴리스 라운드마다 `<notesPath><라운드>.md` 노트를 만들며, 라운드 번호의 SSOT는 그 디렉터리 안 최신 CalVer 파일명이다).
