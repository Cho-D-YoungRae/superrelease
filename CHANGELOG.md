<!-- 한국어 안내: 이 파일은 [Keep a Changelog] 형식을 따른다. 릴리스 전까지 변경은 [Unreleased]에
     쌓고, v0.1.0 태그를 찍을 때 그 내용을 `## [0.1.0] - <날짜>`로 옮긴 뒤 새 [Unreleased]를 연다. -->
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **init이 버전 후보 0건 레포의 입구를 안내한다** — 버전 파일이 없는 기존
  레포(Go CLI·모바일·인프라)에서 init이 절차 없이 표류하는 대신, "파일이
  없는지, 있는데 스캔이 못 찾았는지"를 구분해 수동 versionLocation 등록
  또는 버전 파일 생성을 제안한다. 초기 버전은 최신 릴리스 태그를 시드로
  써서 0.1.0 역행을 막는다.
- **init이 placeholder 버전(0.0.0)을 감지하면 시작 버전 리셋을 묻는다** —
  한 번도 릴리스된 적 없는 `package.json`류의 `0.0.0`을 그대로 첫 릴리스
  버전의 기준으로 삼지 않는다.
- **trunk×release-pr의 첫 릴리스도 머지 후 재개를 감지한다** — 중단 상태
  감지가 "마지막 릴리스 태그 존재"를 전제해 태그가 하나도 없는 첫 릴리스는
  PR 머지 후 태그 단계 재개를 잡지 못했다. gitflow가 이미 쓰는 머지된
  릴리스 PR 검색을 단일·모노레포 release 스킬의 trunk 분기에도 적용했다.

### Changed

- **모노레포 릴리스 스킬이 쓰지 않는 노트 목적지를 더 이상 나열하지 않는다** —
  independent 모노레포용 release 스킬은 노트 목적지 4종(changelog·release-file·
  github-release·fragment)을 설정과 무관하게 항상 프로즈로 나열해, 자기 설정에
  없는 목적지 지시까지 읽어야 했다(단일 레포 flavor는 원래 조건 분기가 있었다).
  이제 **어느 scope도 쓰지 않는 목적지 줄은 렌더되지 않는다**. scope마다 목적지가
  다를 수 있으므로 게이트는 합집합 기준이며, 어느 scope가 어느 목적지를 쓰는지는
  종전대로 릴리스 시점에 config를 읽어 판단한다.
- **라이브러리 프리셋의 SNAPSHOT 기본을 JVM으로 한정** — init이 모든
  라이브러리에 `-SNAPSHOT`+next-snapshot을 기본 제안해 npm·Rust·Python
  생태계 관례와 어긋났다. 이제 gradle·maven 감지 시에만 기본이며, 그 외
  라이브러리는 pre/post `none`이 기본이다.

### Fixed

- **모순되는 검증 메시지 제거 — calver/headver × next-snapshot** — calver·headver
  scope에 `postRelease.bump: next-snapshot`을 적으면 두 규칙이 동시에 발화해
  서로를 무효화했다: 하나는 "bump를 none으로", 다른 하나는 "preRelease를
  mutable로"라고 안내하는데, 후자를 따르면 "calver는 preRelease.style이 none이어야
  한다"가 새로 발화해 빠져나갈 수 없는 수정 루프가 됐다. 이제 non-semver 스킴에는
  스킴 규칙 하나만 발화한다.
- **검증 메시지가 어느 scope인지 지목한다** — scope 이름·`tag.format` 중복 거부
  메시지가 다른 규칙과 달리 `scopes[i]:` 인덱스를 붙이지 않아, scope가 3개
  이상인 모노레포에서 어느 쪽을 고쳐야 하는지 알 수 없었다. 이제 충돌한 scope와
  먼저 그 값을 쓴 scope를 함께 지목한다.
- **누락된 필수 필드를 오타로 보고하지 않는다** — `repo.mergePolicy`와
  `scopes[].notes.language`는 사실상 필수인데, 필드를 아예 빼거나 null로 두면
  `got "None"`이라는 오타 문구로 거부돼 사용자가 잘못 적은 값을 찾아 헤맸다.
  이제 부재·null은 `is required`로 구분해 보고한다.

## [0.4.1] - 2026-08-11

### Fixed

- **잘못된 releasePath·post-release 조합을 render가 거부** — `repo.releasePath`에
  `direct-push`/`release-pr` 외의 값(오타 포함)을 적으면 이제 render가 즉시
  거부한다(종전엔 조용히 통과해 미렌더 `release-pr-body.md`를 참조하는 스킬이
  만들어졌다). `postRelease.bump: next-snapshot`은 `preRelease.style: mutable`과
  qualifier를 요구한다 — 종전엔 생성된 release 스킬이 릴리스 시점에 `--qualifier`
  인자 없이 실행되다 실패했다.
- **gitflow·movingMajorTag·calver/headver 조합 오류를 render가 거부** —
  `repo.maintenanceLines`를 gitflow 브랜칭과 함께 켜면 hotfix 스킬이 같은 목적지에
  이중으로 렌더돼 유지보수 라인 기대가 조용히 사라졌다 — 이제 이 조합을 거부한다.
  `tag.movingMajorTag`는 semver 스킴에 한정하고(calver/headver엔 무의미)
  independent 모노레포에서도 거부한다(scope 네임스페이스가 없어 major 태그가
  충돌한다). calver/headver scope에 `scheme.pattern`이 없으면 종전엔 render를
  통과하고 릴리스 시점에 `next-version.py`가 실패했다.
- **scope·notes·릴리스 커밋 포맷의 구조적 오류를 render가 거부** — 복수 scope인데
  `monorepoStrategy: independent`가 아니거나(단일 레포용 스킬은 `scopes[0]`만
  본다), scope 이름·`tag.format`이 중복되거나, `notes.destinations`가 비었거나
  `release-file`인데 `notes.perReleasePath`가 없으면 이제 거부한다.
  `releaseCommitFormat`은 `{version}`을 반드시 포함해야 하고 `{scope}`는
  independent 전용이며, `notes.language`·`notes.destinations`·`repo.mergePolicy`도
  닫힌 집합으로 검증한다. 종전엔 이런 config도 render는 통과했지만 생성된 스킬이
  릴리스 실행 중에야 깨졌다.
- **스크립트가 모호하거나 손실되는 입력을 조용히 넘기지 않는다** — `version.py`의
  regex 위치가 파일에서 2회 이상 매치하면 `get`/`set`/`verify` 모두 이제
  거부한다(종전엔 `set`이 전 매치를 치환하고 `get`/`verify`는 첫 매치만 읽는
  비대칭이 있어, 의존성 핀 등의 의도치 않은 두 번째 매치가 조용히 오염되거나
  검증을 통과했다). `next-version.py`도 `1.2.3+45`처럼 build metadata가 섞인
  semver 입력을 이제 명시적으로 거부한다 — 종전엔 `+45`가 경고 없이 드롭돼 모바일
  빌드 번호 같은 값이 릴리스마다 소실될 수 있었다.
- **`bundleNotesGuess`가 순수 8자리 날짜를 라운드 노트로 오탐하지 않는다** —
  스캔이 기존 bundle 라운드 노트 파일명을 추정할 때 `20260101`처럼 점 구분이
  없는 8자리 숫자도 매치해, 실제로는 없는 라운드 노트 관행을 있다고 잘못 인식할
  수 있었다. 이제 점으로 구분된 그룹(`2026.07.1` 류)만 매치한다.

### Changed

- **존재하지 않는 태그 안내 제거 — 태그 섹션은 skip 문구가 아니라 통째로
  사라진다** — independent 모노레포에서 일부 scope만 태그를 쓰거나
  (release-monorepo·hotfix), 단일 scope 자체가 tagless면(release —
  `monorepoStrategy != independent` 전용 단일-scope 스킬이라 "혼합"이 아니라
  그 하나의 scope로만 갈린다) 프리뷰·"실패 시" 절의 태그 언급이 이제 태그를
  쓰는 대상에만 렌더된다. 일부만 tagless인 혼합 모노레포는 태그 섹션 헤딩이
  남아 그 안에 "이 단계 전체를 건너뛴다"는 안내가 붙지만, 전부(또는 단일
  scope) tagless면 태그 섹션 헤딩 자체가 렌더되지 않아 번호가 모노레포는
  7→9로, 단일 레포는 6→8로 건너뛴다 — 안내 문구조차 남지 않는다.
- **init의 gitflow 사이클 안내가 "태그는 선택"임을 반영** — gitflow에서는 태그가
  선택사항인데, init이 릴리스 사이클을 설명하는 문구는 마치 항상 태그를 찍는
  것처럼 읽혔다. gitflow 사이클 설명에서 태그가 선택사항임을 반영해 관련
  문구 두 곳(번들 6 안내·지원 범위 절)을 정리했다.

## [0.4.0] - 2026-08-06

### Added

- **gitflow 모노레포** — independent 모노레포가 gitflow(develop→기본 브랜치 라운드 릴리스)를
  지원한다. 범위·변경 감지·중단 감지의 앵커는 태그가 아니라 기본 브랜치다
  (`changed-packages.py --ref origin/<main>`), 단일 레포 gitflow도 같은 앵커로 통일했다.
- **tagless gitflow** — gitflow에서는 태그가 선택사항이다(브랜치 상태로 재개 감지).
  trunk×release-pr는 종전대로 태그 필수.
- **bundle 라운드 노트** — independent 모노레포의 릴리스 라운드마다 CalVer 이름의 묶음
  노트 파일(`docs/releases/2026.07.1.md` 류)을 만든다. top-level `bundle` 객체,
  `notes-bundle.md` 템플릿, `next-version.py --current-among`(후보 중 최댓값 기반 다음
  라운드 계산) 추가. hotfix도 라운드로 취급한다.

### Removed

- **release-train(이중 체계 모노레포) 제거** — 루트 CalVer train + 패키지 SemVer 이중 체계,
  `release-train` 스킬, `notes-train` 템플릿을 정리했다(니치 운용 대비 유지비 — 범위 축소).
  config에 `train` 객체가 있으면 render가 대안 안내와 함께 거부한다: independent로 패키지를
  개별 릴리스하고, 검증된 조합 공표가 필요하면 릴리스 노트·문서에 조합 표를 남긴다.
- **`tag-message` 노트 목적지 제거** — annotated 태그 메시지에 노트 전문을 넣는 목적지를
  정리했다. annotated/signed 태그 메시지에는 한 줄 요약만 남고, 노트 전문은 나머지 목적지
  (changelog/release-file/github-release/fragment)로 보낸다. `notes.destinations`의
  `tag-message`는 render가 거부하며, 목적지 값 자체가 닫힌 집합으로 검증된다(오타도 거부).

### Changed

- **로드맵 정리** — init·references·README의 "후속 버전 지원 예정" 표기를 "지원하지 않음"으로
  정리했다(sequential, direct-push gitflow, `libs.versions.toml`,
  pom 직접 쓰기 등 — 지원 계획 없음). 0.3.0에서 이미 출하된 gitflow production hotfix가
  init 지원 범위 절에 "후속"으로 남아 있던 낡은 문구도 바로잡았다.

## [0.3.0] - 2026-07-17

### Added

- **gitflow production hotfix** — `repo.branching: gitflow` 레포에서 `hotfix` 스킬이 표준
  production hotfix 사이클로 분기한다: 기본 브랜치 HEAD에서 hotfix 브랜치 → PR(base=기본
  브랜치) → 태그 → develop back-merge + SNAPSHOT 복귀. gitflow 게이트는 semver scope에만
  적용된다(calver/headver는 patch-bump가 부적합하여 `validate_config`에서 거부).

### Fixed

- **생성 마커 결정론** — 렌더 엔진이 생성 마커(`generated by superrelease vX`)의 버전을 라이브
  `.claude-plugin/plugin.json`이 아니라 `config.superrelease.pluginVersion`에서 읽는다.
  superrelease가 자기 자신을 릴리스할 때 골든·self-render 스냅샷이 더는 churn되지 않으며,
  비교 시 마커 버전 정규화를 방어적으로 유지한다.

## [0.2.0] - 2026-07-16

### Added

- **Claude Code 플러그인 지원** — scan이 `.claude-plugin/plugin.json`을 버전 소스로 감지하고, init이 "Claude Code 플러그인" 성격을 인식해 프리셋(SemVer · `plugin.json` json-path · tag `v{version}` · changelog+github-release · pre/post none)을 선두 추천한다. marketplace가 이 플러그인 하나만 나열(self-listed)하면 `.claude-plugin/marketplace.json`의 `metadata.version`을 2차 sync 위치로 함께 제안한다.

### Fixed

- **version.py json-path `set`을 surgical write로** — 버전 값만 치환해 inline JSON 배열/객체(`author`·`keywords` 등)를 보존하고, 동일 버전 재지정(no-op)은 파일을 바꾸지 않는다(기존엔 전체 재직렬화로 재포맷). 다중 위치도 각각 최소 diff로 동기화.
- **release 스킬 재개 안내가 mergePolicy를 반영** — 비-gitflow release-PR 재개 문구가 merge 정책이면 "머지 커밋으로"로 정확히 안내한다(기존 "squash 머지로" 하드코딩).

## [0.1.0] - 2026-07-16

### Added

- **`init` 스킬 (컴파일러 패턴)** — 레포를 스캔하고 번들 질문을 한 뒤, 프로젝트 전용 릴리스
  툴킷(스킬·무의존 스크립트·`config.json`·템플릿)을 레포 안에 렌더한다. 이후 일상 릴리스는
  생성물만으로 동작하며 플러그인은 (재)init에만 필요하다.
- **생성 스킬** — `release` / `release-notes`(단일·모노레포 변형), 조건부 `hotfix`(유지보수
  라인) · `backfill`(태그 이력에서 CHANGELOG 소급, 단일 + independent 모노레포) ·
  `release-train`(이중 체계 루트 CalVer train).
- **무의존 스크립트** — `version.py`(전 위치 read/write/verify) · `next-version.py`(버전 산술) ·
  `changed-packages.py`(모노레포 변경 감지). Python 3.9+ 표준 라이브러리만, exit 0/1/2,
  `--today` 주입으로 결정론적 날짜 산술.
- **버전 체계** — SemVer · CalVer · HeadVer.
- **모노레포 전략** — fixed · independent(scope별 태그 네임스페이스·dependents 전파) · 이중
  체계(루트 CalVer train + 패키지 SemVer, file-less train 객체).
- **릴리스 경로** — direct-push · release-PR(보호 브랜치, PR 생성 → 머지 후 태그 재개) +
  브랜치 보호 조언.
- **노트 목적지** — changelog · release-file · github-release · fragment(`changelog.d`) ·
  tag-message.
- **기타** — pre-release 스타일(none/mutable/counter) · moving major tag · GitHub Release
  (`--generate-notes` 하이브리드 · `release.yml`) · CHANGELOG backfill.
- **gitflow 브랜칭 축** — `repo.branching: gitflow`(단일 스킬 레포·release-pr 전용) —
  develop cut → 기본 브랜치 태그 → develop back-merge + SNAPSHOT 복귀 정식 사이클,
  gitflow 전용 중단 감지 2종(머지-미태깅 PR·back-merge 누락).
- **스캔 커버리지 확장** — pom.xml(`<revision>` 후보/project 감지·안내) · VERSION 플레인
  파일 · openapi·swagger `info.version`(json·yaml) · Gradle 멀티모듈 패키지 수집 ·
  `developBranchGuess`(develop/development/dev). versionCandidates `usable`/`advice` 구분.
- **정확성 하드닝** — version.py regex 다중 캡처그룹 가드 · changed-packages
  versionsort·rename·tag.enabled 기본값 · CalVer 동일 기간 exit 1 · validate_config
  강화(scheme enum·non-semver 조합·location·github↔태그·branching gitflow 전제).

[Unreleased]: https://github.com/Cho-D-YoungRae/superrelease/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.4.1
[0.4.0]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.4.0
[0.3.0]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.3.0
[0.2.0]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.2.0
[0.1.0]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.1.0
