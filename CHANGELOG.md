<!-- 한국어 안내: 이 파일은 [Keep a Changelog] 형식을 따른다. 릴리스 전까지 변경은 [Unreleased]에
     쌓고, v0.1.0 태그를 찍을 때 그 내용을 `## [0.1.0] - <날짜>`로 옮긴 뒤 새 [Unreleased]를 연다. -->
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/Cho-D-YoungRae/superrelease/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Cho-D-YoungRae/superrelease/releases/tag/v0.1.0
