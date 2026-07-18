# superrelease

> English: [README.md](README.md)

**무거운 `init` 하나, 프로젝트 전용의 가벼운 릴리스 툴킷.**

superrelease는 저장소를 분석하고 몇 가지 질문을 거쳐, 프로젝트 전용 릴리스
툴킷(프로젝트 스킬, 무의존 스크립트, 설정, 노트 템플릿)을 레포 안에 생성하는
Claude Code 플러그인입니다. init 이후의 일상 릴리스는 생성물만으로
동작하며("릴리스해줘"), 플러그인은 (재)init에만 필요합니다.

```
┌─ superrelease plugin ─────────────┐      ┌─ your repo ──────────────────────┐
│ init skill (fat)                  │      │ .claude/skills/release/          │
│  scan.py → questions → render.py ─┼─────▶│ .claude/skills/release-notes/    │
│  references/ (domain knowledge)   │      │ .superrelease/{config,scripts,   │
│  assets/ (skeletons)              │      │               templates}         │
└───────────────────────────────────┘      │ .github/release.yml (optional)   │
                                           └──────────────────────────────────┘
```

설계 원칙:

- `.superrelease/config.json`이 모든 정책 결정의 단일 진실 공급원(SSOT)입니다;
  생성된 파일은 언제든 이 파일로부터 다시 렌더링할 수 있습니다.
- 버전의 진실 공급원은 여러분의 빌드 파일입니다(`gradle.properties`,
  `package.json`, …); 태그는 여기서 파생됩니다.
- 결정적인 작업(버전 파싱, 파일 수정, 산술)은 스크립트가 수행하며 LLM이 직접
  하지 않습니다. 판단이 필요한 일(bump 제안, 릴리스 노트)은 Claude의 몫입니다.
- 부작용이 있는 모든 단계는 dry-run 프리뷰를 보여주고 실행 전에 확인을 받습니다.

## 요구사항

- 플러그인을 지원하는 Claude Code
- Python 3.9+ (표준 라이브러리만 사용 — 생성된 스크립트는 의존성이 전혀 없습니다)
- `gh` CLI(인증됨) 또는 연결된 GitHub MCP 서버 — GitHub Releases 또는 릴리스 PR 경로를 사용할 때만 필요합니다

## 설치

```
/plugin marketplace add Cho-D-YoungRae/superrelease
/plugin install superrelease@superrelease
```

로컬 개발: `claude --plugin-dir .` · 검증은
`claude plugin validate . --strict` · 리로드는 `/reload-plugins`.

## 빠른 시작

1. 프로젝트에서 `/superrelease:init`을 실행하세요 (또는 "릴리스 관리 셋업해줘" / "set up release management"라고 말해도 됩니다).
2. 스캔 기반 추천 표를 검토하세요 — 전체를 그대로 받아들이거나, 번들 단위로
   (스킴, 버전 위치, 태그, bump 소스, pre-release, 노트, GitHub Releases 등)
   조정할 수 있습니다.
3. 렌더 프리뷰를 확인하세요. init이 툴킷을 생성하고, 승인하면 커밋까지
   합니다.
4. 그 이후에는:
   - "릴리스해줘" / "release it" — preflight → 근거를 포함한 bump 제안 →
     버전 파일 갱신 → 노트 작성 → 커밋 & push → 태그 + GitHub Release →
     post-release (예: `-SNAPSHOT`으로 복귀)
   - "릴리스 준비됐는지 봐줘" — 상태 확인만 수행(bump 제안 이후 중단)
   - "이번 릴리스 노트만 미리 써줘" — 노트만 초안 작성, 부작용 없음

## 유즈케이스

**init이 정보를 모으는 방식.** init은 조용히 추측하지 않습니다. `scan.py`가
빌드 파일, 버전 문자열 후보, 태그, 최근 커밋(Conventional Commits 사용률,
squash 흔적), 브랜치(develop 브랜치 추정 포함), 모노레포 신호를 전부 읽기
전용으로 수집하고, 브랜치 보호는 `gh`로 확인합니다. 추론 가능한 것은 근거를
표기한 추천 표("전체 수락 / 항목별 조정")로 제시하고, 추론할 수 없는 것만
질문이 됩니다. 신호가 없는 신규 레포에서는 제안 모드로 전환합니다: 레포
성격을 먼저 묻고 프리셋(라이브러리 / 앱 / Claude Code 플러그인)을 제시하며,
없는 버전 파일 생성까지 렌더에 포함합니다. 재init은 지난 실행 이후 바뀐
것만 묻습니다.

### 스킬 역할

| 스킬 | 생성 조건 | 이렇게 말하면 | 역할 |
|---|---|---|---|
| release | 항상 | "릴리스해줘" / "release it" / "릴리스 준비됐는지 봐줘" | 오케스트레이터: preflight 게이트 → 변경 범위 → 근거 있는 bump 제안 → 버전 파일 → 노트 → 커밋 또는 릴리스 PR → 태그 + GitHub Release → post-release. 상태 확인성 요청은 bump 제안에서 멈춥니다. |
| release-notes | 항상 | "release notes만 미리 써줘" / "changelog 정리" | 노트 초안만 — 파일 수정·push 없음. release 스킬이 노트 단계에서 재사용합니다. |
| hotfix | `maintenanceLines` 또는 gitflow | "핫픽스" / "1.2.x에 패치" | 유지보수 라인(`release/1.2.x`) 패치 릴리스, 또는 gitflow production hotfix 사이클. |
| backfill | `backfill` | "백필해줘" / "CHANGELOG 소급" | 일회성: 기존 태그 이력에서 누락된 CHANGELOG 항목을 소급 작성. 멱등이며 CHANGELOG.md만 수정. |

각 스킬의 frontmatter description에는 프로젝트명과 한국어·영어 트리거
문구가 함께 들어가므로, 슬래시 명령 없이 자연어 요청만으로 Claude가 알맞은
스킬을 찾아 씁니다. 툴킷을 커밋해야 나만이 아니라 팀원 모두의 Claude가
같은 스킬을 쓰게 됩니다.

### gitflow에서 브랜치별로 스킬이 하는 일

| 브랜치 | 무슨 일이 일어나는가 |
|---|---|
| `feature/*` | 일반 개발 — 릴리스 스킬 개입 없음. 여기서 쓴 Conventional Commits가 나중에 bump의 근거가 됩니다(설정했다면 `changelog.d/` 조각도). |
| `develop` | 릴리스가 시작되는 곳. "릴리스해줘" → release 스킬이 `develop` 위인지 확인하고, `anchor..HEAD`에서 bump를 제안하고, `-SNAPSHOT`을 떼고, 노트를 쓰고, `release/<버전>` 브랜치를 만들어 기본 브랜치로 PR을 연 뒤 — 거기서 멈춥니다. |
| `release/<버전>` | 스킬이 만든 단명 PR 브랜치. 사람은 리뷰하고 **머지 커밋으로 병합**만 하면 됩니다(squash는 다음 릴리스의 범위 계산을 깨뜨립니다). 장수 안정화 브랜치가 아니며, 그런 운용은 이 사이클에 없습니다. |
| `main` | 머지 후 다시 "릴리스해줘": preflight가 머지됐지만 태그가 없는 상태를 감지해 재개합니다 — 머지 커밋에 태그(+ GitHub Release), 이어서 `develop`으로 back-merge하고 다음 `-SNAPSHOT`으로 복귀. |
| hotfix | "핫픽스" → hotfix 스킬이 기본 브랜치 HEAD에서 `hotfix/<패치>`를 만들어 PR → 머지 후 태그 → `develop` back-merge. |

### 워크스루 1 — 신규 백엔드 서비스 (단일 레포 · Gradle 멀티모듈 · gitflow)

새로 시작하는 Spring 스타일 백엔드: 레포 하나, Gradle 모듈 여럿, 배포물 하나.

- 아직 신호가 없으므로 제안 모드. 성격: **앱**. 배포물이 하나인 멀티모듈
  빌드는 **단일 버전**(root scope 하나)입니다 — 모노레포가 아니며, init은
  `settings.gradle`만 보고 단정하지 않고 물어봅니다.
- init이 `gradle.properties`에 `version=0.1.0-SNAPSHOT` 생성을 제안하고,
  SemVer, 가변 `-SNAPSHOT` + next-snapshot, 태그 `v{version}`,
  changelog + GitHub Releases를 추천합니다.
- gitflow를 선택하면 릴리스 경로가 release-pr로 잠기고 `developBranch`가
  기록되며 — 브랜치가 아직 없으므로 `develop` 생성·push를 안내하고, 브랜치
  보호 설정을 조언합니다(실행은 하지 않음). hotfix 스킬은 gitflow
  flavor로 생성됩니다.
- 일상 릴리스는 위 브랜치 표대로 흘러갑니다.

### 워크스루 2 — 기존 모노레포 (프론트엔드 + 멀티모듈 백엔드 · 앱별 SemVer)

프론트엔드 패키지 하나와, 부팅 가능한 모듈(api / batch / worker)이 각자
버전을 갖는 백엔드가 함께 있는 모노레포.

- scan이 워크스페이스/모듈 패키지를 버전·내부 의존성과 함께 나열하고,
  **independent** 전략과 scope 목록을 확인받습니다. scope마다
  `pkg@{version}` 태그 네임스페이스를 갖고, `changed-packages.py`가 scope별
  마지막 태그 이후 변경을 감지하며, `dependents`가 내부 의존성을 따라
  patch 릴리스를 전파합니다.
- 버전 위치는 유연합니다: `properties-key`는 **공유 파일**의 서로 다른
  키를 겨냥할 수 있습니다(예: 백엔드 `gradle.properties` 하나에
  `apiVersion` / `batchVersion` / `workerVersion`). 커스텀 키 이름은 scan이
  자동 감지하지 못하므로 버전 위치 질문에서 직접 추가하세요.
- 태그는 쌓여 있는데 CHANGELOG가 빈약하면 init이 **backfill**을 제안합니다.
- 정직한 한계: gitflow와 bundle 라운드 노트는 이제 independent 모노레포에서
  모두 지원합니다 — 아래 *config.json 수정*의 Branching 표와 `bundle` 행을
  참고하세요. 남은 한계 하나: 태그가 필수인 것은 trunk 브랜칭의 release-pr
  경로뿐입니다(`tag.enabled: false` 거부). 태그는 direct-push(원래부터)와
  gitflow(M5부터 — 기본 브랜치가 범위 앵커)에서 선택입니다.

### 워크스루 3 — 신규 Claude Code 플러그인

- `.claude-plugin/plugin.json`이 있으면 scan이 감지하고 init이 플러그인
  프리셋을 선두로 제안합니다: SemVer, `plugin.json`이 버전 소스, 태그
  `v{version}`, changelog + GitHub Releases, SNAPSHOT 관례 없음. 매니페스트가
  아직 없는 신규 레포라면 제안 모드에서 "Claude Code 플러그인"이라고
  답하면 `plugin.json` 생성이 렌더에 포함됩니다.
- 마켓플레이스를 자기 자신으로 나열(`marketplace.json`의 source `"./"`)하면
  `metadata.version`이 2차 위치로 동기화됩니다.
- 보호된 `main` → release-pr 경로. superrelease 자신이 정확히 이 툴킷으로
  릴리스합니다(dogfooding).

## 생성물 안내 (전부 커밋하세요)

| 경로 | 역할 |
|---|---|
| `.claude/skills/release/SKILL.md` | 이 프로젝트의 릴리스 오케스트레이터 스킬 |
| `.claude/skills/release-notes/SKILL.md` | 노트 초안 작성 스킬 (부작용 없음) |
| `.superrelease/config.json` | 모든 결정의 단일 진실 공급원(SSOT) |
| `.superrelease/scripts/version.py` | 설정된 모든 위치에서 버전을 읽기/쓰기/검증 |
| `.superrelease/scripts/next-version.py` | 버전 산술 (bump/release/qualifier) |
| `.superrelease/scripts/changed-packages.py` | scope별 변경 패키지 감지 (independent 모노레포 전용) |
| `.superrelease/templates/*.md` | 노트·체인지로그 골격 (직접 수정 가능) |
| `.github/release.yml` | 라벨 기반 릴리스 노트 카테고리 (선택) |
| `.claude/skills/hotfix/SKILL.md` | 유지보수 라인용 hotfix 스킬 (조건부: `maintenanceLines`) |
| `.claude/skills/backfill/SKILL.md` | 태그 이력에서 1회성 CHANGELOG backfill (조건부: `backfill`) |
| `.superrelease/templates/release-pr-body.md` | 릴리스 PR 본문 골격 (조건부: `release-pr`) |
| `.superrelease/templates/notes-package.md` | 패키지별 노트 골격 (조건부: independent 모노레포) |

툴킷을 커밋하는 것이 팀 도구로 만드는 핵심입니다: 플러그인이 없는
팀원도 릴리스할 수 있습니다 — 생성된 파일은 오직 `.superrelease/…` 경로만
참조하며, 플러그인은 전혀 참조하지 않습니다.

## 재init과 커스터마이징

- 정책 변경: `.superrelease/config.json`을 수정한 뒤 init을 다시 실행하세요 —
  바뀌지 않은 답변은 다시 묻지 않으며 파일은 결정적으로 재렌더링됩니다.
- `.superrelease/templates/` 아래의 템플릿은 유일한 직접 수정 영역입니다:
  `generated by superrelease` 마커 줄을 제거하면 재init에서도 사용자가 수정한
  버전이 보존됩니다.
- 그 외 모든 파일은 재init 시 재생성됩니다; 마커 줄은 수동 수정을 하지
  말라는 경고입니다.

## 브랜칭

| 전략 | 적합 | 릴리스 경로 |
|---|---|---|
| trunk / GitHub flow | 대부분의 신규 프로젝트 | `main`에서 릴리스 |
| gitflow | `develop` 통합 브랜치에서 릴리스하는 팀 | 단일 레포·independent 모노레포 모두, release-pr 전용 (develop에서 cut → main에 머지 → 태그(선택) → back-merge) |

gitflow 지원은 release-pr 경로로 한정됩니다(단일 레포·independent 모노레포
모두); direct-push gitflow는 지원하지 않습니다. gitflow에서는 태그가 선택
사항입니다 — 태그 유무와 무관하게 기본 브랜치가 변경 감지·중단/재개의 범위
앵커입니다.

## 감지 항목

`init`은 버전 문자열 위치와 레포 시그널을 읽기 전용으로 스캔합니다:
`gradle.properties`, `build.gradle(.kts)`, `package.json`, `pyproject.toml`,
`Cargo.toml`, `Dockerfile` LABEL, `Chart.yaml`, README 배지, `VERSION`,
`openapi`/`swagger`(json·yaml), `pom.xml`(`<revision>` 프로퍼티는 사용 가능한
위치이고, 일반 project `<version>`은 감지는 되지만 사용 불가로 표시됩니다),
node·Gradle 모노레포 패키지도 포함됩니다. 감지하지 않는 것:
`libs.versions.toml`(의존성 카탈로그), Gradle 내부 의존성.

## 업그레이드

플러그인은 (재)init에만 필요합니다. 새 플러그인 버전이 나오면 이미 init된
레포에서 `/superrelease:init`을 다시 실행하세요: 바뀌지 않은 답변은 다시
묻지 않으며 파일은 결정적으로 재렌더링됩니다. 생성된 각 파일의
`generated by superrelease vX.Y.Z` 마커 줄이 렌더링된 버전을 기록합니다.
`.superrelease/config.json`을 직접 수정한 뒤 init을 다시 실행하는 것이
공식 커스터마이징 경로입니다.

## config.json 수정

`.superrelease/config.json`이 단일 진실 공급원(SSOT)입니다. 주요 필드:

| 필드 | 값 | 비고 |
|---|---|---|
| `repo.branching` | `trunk` \| `gitflow` | gitflow는 `releasePath: release-pr` + `developBranch` 필요 |
| `repo.releasePath` | `direct-push` \| `release-pr` | release-pr은 2단계(PR → 머지 → 태그) |
| `scopes[].scheme.type` | `semver` \| `calver` \| `headver` | calver/headver는 `preRelease.style: none` + `postRelease.bump: none` 필요 |
| `scopes[].preRelease.style` | `none` \| `mutable` \| `counter` | mutable = `-SNAPSHOT`; counter = `-rc.N` |
| `scopes[].tag.enabled` | 명시적 boolean | 필수; `github.release: true`면 true여야 함 |
| `scopes[].notes.destinations` | `changelog` \| `release-file` \| `github-release` \| `fragment` | `fragment`는 다른 목적지 1개 이상을 sink로 필요 |
| `bundle` | `{enabled, scheme: calver+pattern, notesPath}` | independent 모노레포: 릴리스 라운드마다 CalVer 이름의 묶음 노트 |

잘못된 조합은 렌더 시점에 수정 방법을 알려주는 메시지와 함께 거부됩니다 —
수정 후 init을 다시 실행하세요.

## 버전 체계

| 체계 | 적합한 대상 | 링크 |
|---|---|---|
| SemVer | 라이브러리(사실상 필수), 일반 앱 | [semver.org](https://semver.org/) |
| CalVer | 릴리스 트레인, 주기적으로 배포되는 서비스 | [calver.org](https://calver.org/) |
| HeadVer | 앱/서비스 (`{head}.{yearweek}.{build}`) | [line/headver](https://github.com/line/headver) |

SemVer, CalVer, HeadVer를 모두 지원합니다; 날짜/주차/카운터 산술은
`next-version.py`가 결정론적으로 수행합니다(`--today` 주입 가능).

## 스크립트 단독 사용 (플러그인·Claude 없이)

```bash
python3 .superrelease/scripts/version.py get            # print current version
python3 .superrelease/scripts/version.py verify         # check all locations agree
python3 .superrelease/scripts/version.py set 1.3.0      # write everywhere (+ lockfile)
python3 .superrelease/scripts/next-version.py --release            # 1.3.0-SNAPSHOT → 1.3.0
python3 .superrelease/scripts/next-version.py --bump minor --qualifier SNAPSHOT
python3 .superrelease/scripts/changed-packages.py --json   # 모노레포: 패키지별 마지막 태그 이후 변경
```

종료 코드: `0` 성공 · `1` 검증 실패 · `2` 사용법/설정 오류.
Windows에서는 `python3` 대신 `py -3`을 사용하세요.

## FAQ

- **팀원도 플러그인이 필요한가요?** 아니요. 생성된 스킬과 스크립트는
  자립적입니다; 플러그인은 (재)init에만 필요합니다.
- **`gh` CLI가 없다면?** 연결된 GitHub MCP 서버로 폴백하거나, 태그까지만
  진행하는 제한 모드를 제공합니다.
- **왜 아티팩트를 publish하지 않나요?** publish는 CI의 몫입니다. 권장하는
  경계는 다음과 같습니다: superrelease가 태그(와 GitHub Release)를 생성하고,
  여러분의 CI가 태그 push를 트리거로 삼아 publish합니다.
- **잘못된 버전이 나갔다면?** 절대 태그를 재사용하지 마세요. 그 위에 다음
  patch를 올려 배포하고 생태계의 회수 절차(`npm deprecate`, PyPI yank)를
  사용하세요 — 스킬이 안내합니다.
- **개발 서버 빌드는요?** `-SNAPSHOT`을 유지하고(bump 없음) 불변 식별자
  (Spring build-info를 통한 커밋 SHA, Docker `sha-…` 태그)를 함께 사용하세요.
- **제거하려면?** `.superrelease/`와
  `.claude/skills/{release*,hotfix,backfill}`를 삭제하세요
  (사용하지 않는다면 `.github/release.yml`도 함께).

## 로드맵

- **M1 (완료)** — 단일 레포: SemVer, 가변 `-SNAPSHOT`, CHANGELOG /
  릴리스별 파일 / GitHub Releases, direct push
- **M2 (완료)** — 모노레포: fixed/independent 전략, 변경 패키지 감지,
  `{pkg}@{ver}` 태그 네임스페이스, 의존성 전파
- **M3a (완료)** — 버전 체계: CalVer/HeadVer 산술, 카운터형 pre-release
  (`-rc.N`), moving major tag
- **M3b (완료)** — 릴리스 경로: 보호 브랜치용 릴리스 PR 모드
  (2단계: PR → 머지 → 태그), 유지보수 라인 hotfix 플로우
- **M3c (완료)** — 릴리스 트레인(이중 체계 모노레포), CHANGELOG backfill,
  `changelog.d/` fragment, tag-message 노트
- **M4 (완료)** — 하드닝: gitflow 브랜칭(단일 스킬 레포·release-pr 전용),
  스캔 커버리지(Maven/Gradle 모노레포/openapi/VERSION), 정확성 수정
- **범위 정리 (미릴리스)** — 릴리스 트레인(이중 체계 모노레포)과 `tag-message`
  노트 목적지를 제거했습니다; 둘 다 렌더 시점에 지원되는 대안을 안내하며
  거부됩니다
- **M5 (미릴리스)** — gitflow 모노레포(develop발 라운드 릴리스), 태그 선택
  gitflow, CalVer bundle 라운드 노트(imstargg 스타일)

지원 계획 없음(범위 밖): sequential 버저닝, direct-push gitflow, 릴리스
트레인(루트 태그 — 제거된 이중 체계 트레인이며, 위 bundle 라운드 노트
라벨과는 다릅니다), `tag-message` 노트, `pom.xml` project `<version>` 직접
쓰기, `libs.versions.toml`, 아티팩트 publish, CI 워크플로 생성.
