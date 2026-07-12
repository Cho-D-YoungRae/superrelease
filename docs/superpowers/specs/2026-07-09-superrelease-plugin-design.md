# superrelease — 버전 관리 Claude Code 플러그인 설계 스펙

- 날짜: 2026-07-09
- 상태: 승인됨 (2026-07-09)
- 저장소: https://github.com/Cho-D-YoungRae/superrelease — **이 레포 루트가 곧 플러그인 루트**
- 원본 요구사항: 사용자 제공 구현 프롬프트(superrelease 구현 프롬프트, 이하 "원 프롬프트"). 원 프롬프트의 확정 사항은 그대로 채택하며, 이 문서는 그 위에 재량 결정·보완 사항을 더해 구현 가능한 수준으로 확정한다.

## 1. 목표와 아키텍처

### 1.1 컴파일러 패턴

superrelease는 하나의 무거운 `init` 스킬만 제공하는 Claude Code 플러그인이다. `init`은 대상 프로젝트를 분석하고 사용자에게 질문하여, 그 프로젝트 전용의 경량 릴리스 스킬·스크립트·설정·템플릿을 프로젝트 레포 안에 생성한다. 이후 일상적인 릴리스는 생성물만으로 수행되고, 플러그인은 (재)init에만 필요하다.

- **init은 fat**: 드물게 실행되므로 도메인 지식을 누락 없이 내장. SKILL.md 본문은 흐름·오케스트레이션만(500줄 이하), 지식은 `references/`로 분할(progressive disclosure).
- **생성물은 lean**: 자주 로드되므로 얇게. 결정론 작업(버전 파싱·수정·산술·변경 패키지 감지)은 스크립트로, 판단(bump 제안, 노트 작성, breaking 판별 보조)은 스킬로, 프로젝트별 값은 config로, 반복 문구는 템플릿으로.
- **렌더링은 결정론**: init은 생성물을 즉석 작성하지 않고, `assets/` 골격을 `render.py`(플러그인 내장 결정론 렌더러)로 config 값에 따라 렌더링한다. 재init의 결정론성과 품질 일관성을 기계적으로 보장한다. (5절)

### 1.2 확정 원칙 (원 프롬프트 채택, 재논의 금지)

1. 생성물 전부 레포에 커밋 → 플러그인 없는 팀원도 릴리스 가능 (팀 자립성)
2. `.superrelease/config.json`이 모든 결정의 SSOT, 생성물은 config에서 항상 재생성 가능
3. 버전의 SSOT는 빌드 파일(`gradle.properties`, `package.json` 등), 태그는 파생물 (사용 여부는 init 질문)
4. 버전 읽기·수정·산술은 스크립트로 (LLM 파싱/산술 금지 — 토큰·속도·정확성)
5. bump는 자동 산출 + 제안·근거·확인이 기본, 수동 지정 가능
6. 웹 앱 dev 서버 배포는 가변 수식어 덮어쓰기 + 불변 식별자(sha) 병기 (7절)
7. post-release는 레포 성격별 best practice를 기본값으로 제안 (7절)
8. 모든 부작용 있는 동작은 dry-run 프리뷰 → 확인 → 실행
9. init은 최초 초기화·기존 레포·재init(정책 변경, 모노레포 패키지 추가) 모두 지원
10. 생성 스킬·스크립트는 플러그인 내부 파일을 절대 참조하지 않음 — 레포 내 상대 경로(`.superrelease/...`)만 참조. 스크립트는 사람이 터미널에서 단독 실행 가능(`--help`, exit code 규약)

## 2. 언어 정책

공개 레포(영문 기본)와 한국어 팀 사용을 모두 만족하도록 계층별로 고정한다.

| 산출물 | 언어 |
|---|---|
| `README.md` | 영어 (기본 진입점, 상단에 `README_KO.md` 링크) |
| `README_KO.md` | 한국어 (동일 내용, 상단에 English 링크) — [revfactory/harness](https://github.com/revfactory/harness) 패턴 |
| `plugin.json` description | 영어 |
| init `SKILL.md` 본문, `references/` 7종 | 한국어 (Claude가 읽는 지시문·지식) |
| 스킬 frontmatter `description` | 한국어 트리거 필수 + 영어 키워드 병기 (원 프롬프트 확정) |
| 생성 스킬 `SKILL.md` 본문 | 한국어 (M1 고정; 생성물 언어 옵션은 로드맵) |
| 스크립트 코드·주석·`--help`·에러 메시지 | 영어 (공개 코드 관례; 한국어 사용법은 README_KO가 담당) |
| 릴리스 노트·템플릿 문구 | `config.scopes[].notes.language` 에 따름 (ko 기본 / en / both) |
| 이 스펙 등 내부 설계 문서 | 한국어 |

## 3. 플러그인 저장소 구조

```
superrelease/                        # 레포 루트 = 플러그인 루트
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json             # 자기 자신을 마켓플레이스로 배포 (source: "./")
├── skills/
│   └── init/
│       ├── SKILL.md                 # 흐름·오케스트레이션 (500줄 이하)
│       ├── references/              # 도메인 지식 (필요할 때만 로드) — 9절
│       │   ├── version-schemes.md
│       │   ├── prerelease-and-dev-channel.md
│       │   ├── monorepo.md
│       │   ├── bump-models.md
│       │   ├── notes-and-changelog.md
│       │   ├── branching-and-release-path.md
│       │   └── edge-cases.md
│       ├── scripts/                 # 플러그인 전용 (init 시에만 실행, 생성물에 미포함)
│       │   ├── scan.py              # Phase 1 결정론 스캔 → JSON 리포트
│       │   └── render.py            # config + assets → 생성물 (컴파일러 백엔드)
│       └── assets/                  # 생성물의 원본 (골격/템플릿/스크립트)
│           ├── manifest.json        # asset → 목적지 매핑 + 조건(when)
│           ├── skills/
│           │   ├── release/SKILL.md
│           │   ├── release-notes/SKILL.md
│           │   ├── hotfix/SKILL.md            # M3
│           │   └── release-train/SKILL.md     # M3
│           ├── scripts/
│           │   ├── version.py
│           │   ├── next-version.py
│           │   └── changed-packages.py        # M2
│           ├── templates/
│           │   ├── notes-single.md
│           │   ├── notes-package.md           # M2
│           │   ├── notes-train.md             # M3
│           │   ├── changelog-entry.md
│           │   └── release-pr-body.md         # M3
│           └── github/
│               └── release.yml
├── tests/                           # 플러그인 개발용 unittest (stdlib만) — 생성물에 미포함
├── docs/superpowers/specs/          # 설계 문서 (이 파일)
├── README.md                        # 영어
└── README_KO.md                     # 한국어
```

규칙: 디렉터리·파일명은 kebab-case. 플러그인 내부 경로 참조는 `${CLAUDE_PLUGIN_ROOT}` 사용. `.claude-plugin/` 안에는 plugin.json·marketplace.json만 둔다(컴포넌트는 플러그인 루트).

### 3.1 plugin.json

```json
{
  "name": "superrelease",
  "version": "0.1.0",
  "description": "Analyzes your project and generates a tailored, self-contained release toolkit (skills, scripts, config, templates) committed into your repo",
  "author": { "name": "Cho-D-Youngrae", "email": "yrc9229@gmail.com" },
  "repository": "https://github.com/Cho-D-YoungRae/superrelease",
  "keywords": ["release", "versioning", "semver", "calver", "headver", "changelog"]
}
```

`version`은 generated 마커·config의 `pluginVersion`과 동기화한다(마이그레이션 감지 기준).

### 3.2 marketplace.json (자기 배포)

```json
{
  "name": "superrelease",
  "owner": { "name": "Cho-D-Youngrae", "email": "yrc9229@gmail.com" },
  "plugins": [
    {
      "name": "superrelease",
      "source": "./",
      "description": "Project-aware release management: one fat init generates a lean per-project release toolkit"
    }
  ]
}
```

설치: `/plugin marketplace add Cho-D-YoungRae/superrelease` → `/plugin install superrelease@superrelease`.

### 3.3 로컬 개발·검증

- 로컬 실행: `claude --plugin-dir .`
- 구조 검증: `claude plugin validate .` (`--strict` 포함)
- 재로드: `/reload-plugins`
- 스킬 호출: 자연어 트리거 또는 `/superrelease:init`

## 4. init 스킬

frontmatter description(3인칭 + pushy 한국어 트리거, 원 프롬프트 예시 채택):

> "프로젝트의 버전·릴리스 관리를 초기화하거나 재구성한다. 사용자가 '릴리스 관리 셋업', '버전 관리 초기화', 'superrelease init', '릴리스 정책 바꾸고 싶어', '모노레포에 패키지 추가했어(버전 관리 대상)' 등을 말하면 반드시 이 스킬을 사용한다."

### 4.1 실행 모드 (`.superrelease/config.json` 존재 여부로 분기)

- **최초 init (기존 레포)**: 스캔 → 질문 → 생성.
- **최초 init (신규/빈 레포)**: 스캔 신호가 없으므로 제안 모드 — 레포 성격을 먼저 묻고 성격별 권장 프리셋 제시.
- **재init**: 4.5절.

### 4.2 Phase 1 — 스캔 (읽기 전용)

**scan.py** (플러그인 내장, `python3 "${CLAUDE_PLUGIN_ROOT}/skills/init/scripts/scan.py" --repo <path> --json`)가 결정론 항목을 JSON으로 출력한다:

- `buildSystems`: gradle(.kts)/maven/package.json(+pnpm/npm/yarn 락파일)/pyproject.toml/Cargo.toml 감지
- `versionCandidates`: 버전 문자열 전수조사 → 버전 위치 후보 매니페스트 (gradle.properties, build.gradle(.kts), package.json, Dockerfile LABEL, Helm Chart.yaml, openapi info.version, README 배지 등 알려진 패턴)
- `tags`: 전체 목록, 포맷 패턴 분류(v prefix·혼재 여부), annotated/signed 여부, 패턴별 마지막 태그
- `conventionalCommits`: 최근 100커밋 샘플링 → 사용률
- `mergePolicy`: squash 추정(제목 `(#N)` 비율) + 근거
- `branches`: 기본 브랜치, develop/release/*/hotfix/* 존재
- `monorepoSignals`: settings.gradle 멀티모듈, pnpm-workspace.yaml, packages/, apps/
- `changelogArtifacts`: CHANGELOG.md / docs/releases/ / changelog.d/
- `ciTagTriggerCandidates`: `.github/workflows/*.yml` 중 태그 트리거로 의심되는 **후보 파일 목록만** (stdlib에 YAML 파서가 없으므로 정규식 휴리스틱). **판단은 Claude가 해당 파일을 직접 읽어 확정**하고, 확정 시 "태그 생성 = 배포 버튼"임을 이후 프리뷰에 명시

**Claude가 GitHub API로 직접 확인** (인증 의존, 저볼륨): protected branch + required checks, 기존 Releases, `.github/release.yml` 존재, 인증 상태·스코프. 접근 계층은 gh CLI 우선 → 미가용 시 GitHub MCP 도구(연결된 경우, 런타임에 발견) → 둘 다 없으면 해당 항목을 사용자에게 질문으로 대체하고 GitHub 연동 기능을 제한 모드로 제안.

부수 효과: init 머신에서 scan.py 실행 자체가 python3 가용성 검증이 된다.

### 4.3 Phase 2 — 질문

**패스트트랙 우선**: 스캔 결과로 전체 추천 구성을 한 화면에 요약 제시(각 항목에 근거 표기)하고 첫 질문으로 "모두 수락 / 항목별 조정"을 묻는다. 수락 시 즉시 Phase 3로. 조정 선택 시에만 아래 번들로 진입한다.

**질문 번들** (AskUserQuestion, 각 호출 ≤4문항, 상류→하류 순서 유지 — 상류 결정이 하류 기본값을 결정):

1. **성격·전략**: 레포 성격(library | app/service | monorepo) / (모노레포) fixed | independent | 이중(루트 train + 패키지 개별) + scope 목록 확정
2. **체계·SSOT·태그**: scope별 버전 체계(SemVer | CalVer | HeadVer | sequential; 기본값 — 라이브러리→SemVer 사실상 강제, 앱→SemVer 또는 CalVer/HeadVer, train 루트→CalVer) / 버전 위치 파일 확정(스캔 후보 확인) / 태그 파생 여부(기본 yes)·prefix·annotated(기본 yes)/signed·(모노레포) 네임스페이스·moving major tag
3. **bump**: auto-confirm(기본) | manual / 소스 우선순위(Conventional Commits ↔ PR 메타데이터, squash면 PR이 1차) / (라이브러리) API 호환성 도구 연동 여부
4. **pre-release·dev·post**: 수식어 없음 | 가변(-SNAPSHOT류) | 불변 카운터(-alpha.N 등) / (앱) dev 채널 수식어·불변 식별자 임베드 방식 / post-release bump (7절 기본값 제안)
5. **노트·GitHub Release**: 목적지 조합("어디에 + 무엇을") / 언어(ko 기본)·독자·어조 / GitHub Release 사용·`--generate-notes` 하이브리드·`.github/release.yml` 생성
6. **경로·브랜치**: protected branch 감지 시 릴리스 PR 모드 강제 제안, 아니면 direct push / 브랜치 전략 확인(신규면 trunk-based 기본) / 유지보수 라인 운용 → hotfix 스킬 생성 여부
7. **첫 릴리스·이력**: 기존 버전 없으면 0.1.0 vs 1.0.0 / 기존 레포면 CHANGELOG backfill 제공 여부(M3) / (모노레포) 내부 의존성 전파 여부

스캔에서 추론된 항목은 확인형으로("태그 패턴상 SemVer + v prefix로 보이는데 맞나요?"). 모든 답은 근거(스캔 신호 or 사용자 답변)와 함께 `config.decisions`에 기록. M1에서 미지원 선택지(CalVer/HeadVer, 모노레포, 릴리스 PR 등)는 "후속 버전 지원 예정"으로 표시하고 선택을 막는다.

### 4.4 Phase 3 — 생성

1. `config.json` 작성 (Claude가 Write; 스키마 6.8절)
2. `render.py --check`로 생성 예정 파일·보존·충돌 목록 프리뷰 → 사용자 확인 (init 자신도 dry-run 원칙 준수)
3. 충돌 처리: **첫 init에도 적용** — 목적지에 마커 없는 기존 파일(예: 자작 `.claude/skills/release/`)이 있으면 경고 + 덮어쓰기 확인 후 `--force`
4. `render.py` 실행 → 생성물 산출
5. 자가 검증: `version.py verify` 통과 + 각 스크립트 `--help` 스모크
6. 요약 출력: 결정 테이블 / 생성 파일 목록 / 첫 릴리스 실행 예시("릴리스해줘"라고 말하면 됨) / CI 태그 트리거 감지 시 경고
7. **커밋까지 마무리**: "생성물은 전부 커밋해야 팀원이 함께 씁니다" 안내와 함께 커밋 여부 확인 → 승인 시 init이 직접 커밋

### 4.5 재init

- 기존 config 요약 제시 → 재스캔 → 레포 현황과 config 불일치(새 패키지, 버전 위치 추가 등) 감지 → **바뀐 부분만 질문** → 생성물 전체 재생성
- 불일치가 없으면 질문 0개로 재렌더만 수행 — **"config를 손으로 고친 뒤 재init"이 공식 커스터마이징 경로**임을 문서화
- generated 마커가 없거나 훼손된 파일은 경고 후 덮어쓰기 확인 (템플릿은 보존 규칙 적용, 5.4절)
- config의 `pluginVersion` < 현재 플러그인 버전이면 마이그레이션 모드: 스키마 변경 사항을 안내하고 재생성

## 5. 렌더링 파이프라인

### 5.1 render.py

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/init/scripts/render.py" \
  --config <repo>/.superrelease/config.json \
  --assets "${CLAUDE_PLUGIN_ROOT}/skills/init/assets" \
  --repo <repo> [--check] [--force]
```

- `--check`: 쓰기 없이 계획 출력 — 생성/갱신/보존(손편집 템플릿)/충돌(마커 없는 기존 파일) 분류
- `--force`: 마커 없는 기존 파일 덮어쓰기 허용 (init이 사용자 확인 후에만 부여)
- exit code: 0 성공 / 1 충돌 존재(`--force` 없이) 또는 config 검증 실패 / 2 사용법 오류
- config 필수 키 검증(경량) 포함. 생성 파일 중 실행 파일은 `chmod +x`. 기존 파일 수정 시 개행 방식(LF/CRLF) 보존.

### 5.2 템플릿 dialect (동결 — 확장 금지)

- `{{path.to.value}}` — config dot-path 치환
- `{{#if path}}…{{else}}…{{/if}}` — truthy 분기
- `{{#if path == "literal"}}` / `{{#if path != "literal"}}` — 문자열 비교
- `{{#unless path}}…{{/unless}}`
- `{{#each path}}…{{this.key}}…{{/each}}` — 배열 순회 (블록 중첩 허용)

렌더 컨텍스트 = config 전체 + 파생 값: `project.name`(origin URL 마지막 세그먼트, 없으면 디렉터리명), `plugin.version`, `generated.at`(ISO 8601 UTC), scope 단위 렌더 시 `scope.*`(해당 scope 객체). asset 파일은 실명 유지(`.tmpl` 접미사 없음 — 렌더 여부는 manifest가 결정).

### 5.3 manifest.json

```json
{
  "entries": [
    { "src": "skills/release/SKILL.md", "dest": ".claude/skills/release/SKILL.md", "render": true },
    { "src": "skills/hotfix/SKILL.md", "dest": ".claude/skills/hotfix/SKILL.md", "render": true,
      "when": "repo.maintenanceLines" },
    { "src": "scripts/version.py", "dest": ".superrelease/scripts/version.py", "render": false, "executable": true },
    { "src": "templates/notes-single.md", "dest": ".superrelease/templates/notes-single.md", "render": true,
      "preserve": "template" },
    { "src": "github/release.yml", "dest": ".github/release.yml", "render": true, "when": "github.releaseYml" }
  ]
}
```

`when`은 if-표현식과 동일 문법(dot-path truthy, `==`/`!=`). `render: false`는 verbatim 복사(스크립트 — placeholder 없음, 런타임에 config를 읽는 config-driven 설계라 재init 시 diff가 없다).

### 5.4 generated 마커와 보존 규칙

- Markdown: `<!-- generated by superrelease v0.1.0 — do not edit; re-run init to regenerate (직접 수정하지 말고 재init 하세요) -->`
- Python·YAML: `# generated by superrelease v0.1.0 — do not edit; re-run init to regenerate`
- config.json: `superrelease.pluginVersion` 필드가 마커 역할 (JSON은 주석 불가)
- 파싱 키: `generated by superrelease v(\d+\.\d+\.\d+)`
- **보존 규칙**: `preserve: "template"` 파일은 마커가 제거되어 있으면 손편집으로 간주하고 보존(스킵 + 리포트). 그 외 파일은 마커가 없으면 충돌로 분류 → 사용자 확인 후 `--force`로만 덮어씀. **템플릿만이 유일한 손편집 허용 영역**이며 나머지 커스터마이징은 config 값 변경 + 재렌더로 유도한다.

## 6. 생성물 명세

### 6.1 생성물 트리 (모두 커밋 대상)

```
{repo}/
├── .claude/skills/
│   ├── release/SKILL.md
│   ├── release-notes/SKILL.md
│   ├── hotfix/SKILL.md            # 조건부: repo.maintenanceLines (M3)
│   └── release-train/SKILL.md     # 조건부: repo.train (M3)
├── .superrelease/
│   ├── config.json
│   ├── scripts/
│   │   ├── version.py
│   │   ├── next-version.py
│   │   └── changed-packages.py    # 조건부: 모노레포 (M2)
│   └── templates/
│       ├── notes-single.md | notes-package.md | notes-train.md   # 해당분만
│       ├── changelog-entry.md
│       └── release-pr-body.md     # 조건부: 릴리스 PR 모드 (M3)
└── .github/release.yml            # 조건부: github.releaseYml
```

### 6.2 생성 스킬 공통 요구

- **자립성**: `.superrelease/` 상대 경로만 참조, 플러그인(`${CLAUDE_PLUGIN_ROOT}`) 참조 금지
- description: 3인칭, pushy, 한국어 트리거 + 영어 키워드, **프로젝트명 포함**(다른 플러그인의 release류 스킬과 트리거 충돌 방지)
- 항상 dry-run 프리뷰 → 사용자 확인 → 실행. 태그 push·GitHub Release 생성·PR 생성은 특히 엄격히
- 본문은 얇게 — **각 SKILL.md 150줄 이하 목표**. 값은 config에서 읽고, 결정론 작업은 scripts 호출
- 확인이 필요한 지점은 AskUserQuestion 사용, 도구가 없는 환경이면 텍스트 질문으로 폴백
- **GitHub 접근 계층**: gh CLI 우선(결정론적·사람도 동일 명령 사용 가능) → 미가용 시 GitHub MCP 도구 폴백(도구 이름을 스킬에 고정하지 않고 런타임에 발견) → 둘 다 없으면 GitHub 단계를 건너뛰는 제한 모드. 어느 경로든 부작용 동작은 동일한 dry-run 확인을 거친다

### 6.3 release 스킬 (오케스트레이터)

description 예 (원 프롬프트 채택 + 프로젝트명 삽입):

> "{project.name} 프로젝트의 릴리스를 수행한다. 사용자가 '릴리스해줘', '버전 올려', 'bump', '태그 따줘', 'release', '릴리스 준비됐는지 봐줘' 등 버전 결정·태그·GitHub Release·릴리스 노트와 관련된 요청을 하면 반드시 이 스킬을 사용한다."

절차:

1. **preflight** — clean working tree / **현재 브랜치 == `repo.defaultBranch`** (hotfix는 예외적으로 release/* 라인) / 원격과 동기화(fetch 후 비교) / `version.py verify` 통과 / (GitHub Release 사용 시) gh auth 스코프 — **gh 미가용 시 GitHub MCP 폴백, 둘 다 없으면 "태그까지만 진행" 제한 모드 제안** / 태그 충돌 없음 / **중단 상태 감지**: 파일 버전 > 마지막 태그인데 미태깅이면 이전 릴리스 중단으로 판단 → resume/rollback 제안
2. **범위 산출** — anchor(마지막 태그 또는 `config.anchor`)..HEAD의 커밋/PR 수집. anchor가 없으면(첫 릴리스) 전체 이력을 나열하지 않고 "Initial release" 정책 적용. 모노레포면 `changed-packages.py`로 대상 필터(M2)
3. **bump 제안** — config의 소스 순서대로 분석, "minor 제안 — 근거: feat 커밋 2건(제목 나열)" 형식 → 확인 또는 수동 지정. SemVer 0.x에서는 breaking→minor, feat→patch 관례를 적용하고 그 사실을 명시. 결과 버전 문자열 계산은 `next-version.py`
4. **버전 반영** — `version.py set`으로 매니페스트 전 위치 동기 수정 (npm 레포는 lockfile 동기화 포함)
5. **노트 생성** — release-notes 스킬 로직 재사용 (템플릿·언어·독자 규칙)
6. **커밋 경로** — `repo.releaseCommitFormat`(기본 `chore(release): {version}`)으로 커밋, 모드에 따라 direct push 또는 릴리스 PR(M3)
7. **태그 + GitHub Release** — annotated 태그(짧은 요약을 태그 메시지에), `gh release create`(`--generate-notes` 뼈대 + LLM 가공 노트). MCP 폴백 경로에서는 `--generate-notes` 뼈대 없이 PR 메타데이터에서 직접 노트 작성(release-notes 로직과 동일). 태그 push가 CI 배포 트리거인 레포면 프리뷰에 "이 태그는 배포를 트리거합니다" 명시
8. **post-release** — 7절 정책 (next-SNAPSHOT bump 등)

**dry-run 프리뷰 표준 형식** (실행 전 반드시 출력):

- 바뀔 파일과 버전 diff (위치별 old → new)
- 생성될 커밋 메시지·태그명
- 실행될 명령 목록 (push, gh release create 등)
- CI 트리거 경고 (해당 시)
- 릴리스 노트 미리보기

**status 모드**: "릴리스 준비 상태 알려줘", "다음 버전 뭐가 될까" 류 요청은 1~3단계만 수행하고 멈춘다. 별도 스킬로 분리하지 않는다(사용 빈도를 보고 후에 판단).

**파라미터**: 모노레포 패키지 지정(M2), bump 수준 강제, dry-run only.

**실패 시**: 어디까지 진행됐는지(파일 수정? 커밋? 태그? push?)와 되돌리는 방법을 명시 출력. 태그 push 이후 실패는 버전 재사용 금지 원칙에 따라 rollback이 아닌 다음 패치로 안내.

### 6.4 release-notes 스킬

부작용 없음. 범위의 PR/커밋을 읽고 템플릿에 맞춰 노트 초안 작성. squash 레포면 PR 제목/본문/라벨/연결 이슈가 1차 소스(커밋 메시지의 `(#N)` 또는 commits API로 역참조), diff는 모호할 때만 확인(토큰 비용 유의). release가 내부 재사용하며 "이번 릴리스 노트만 미리 써줘" 요청에 단독 대응.

### 6.5 hotfix / release-train 스킬 (조건부, M3)

- **hotfix**: 유지보수 라인(release/1.2.x) 체크아웃 → 대상 커밋 체리픽 → patch 릴리스(release 흐름 재사용) → main 반영 여부 확인
- **release-train**: 루트 train 릴리스 — 포함 패키지들의 현재 버전 스냅샷 고정 + 통합 노트(notes-train) + 루트 태그(CalVer). 패키지 개별 릴리스와 별개의 릴리스 타입임을 스킬에 명시

### 6.6 생성 스크립트 명세

**공통 요건 (무의존 절대 조건)**:

- Python 3.9+ 표준 라이브러리만 (uv·pip 패키지 금지, jq 등 외부 도구 가정 금지). 각 스크립트 첫머리에 `sys.version_info >= (3, 9)` 가드 + 명확한 에러 메시지
- 자기 위치 기준으로 `.superrelease/config.json`을 읽는 config-driven 설계 (`Path(__file__).parent.parent / "config.json"`) — CWD 무관, placeholder 불필요
- `--help` 제공, exit code 규약: 0 성공 / 1 검증 실패 / 2 사용법·설정 오류
- 파일 수정 시 개행 방식(LF/CRLF)·들여쓰기 보존
- 모든 파일 조작은 Python stdlib로 직접 수행 — 외부 명령(npm 등)에 의존하지 않는다(단일 도구체인, node 없는 머신에서도 동작). JSON은 포맷 보존 writer(들여쓰기 감지, 키 순서, 마지막 개행 보존)로 수정하고, sed로 JSON을 조작하지 않는다
- **npm lockfile 동기화**: package.json 버전 수정 시 package-lock.json이 있으면 top-level `version`과 `packages[""].version` 두 json-path를 함께 수정 (pnpm-lock.yaml·yarn.lock은 루트 버전을 담지 않으므로 대상 아님)
- 호출 규약은 `python3 <script>` (Windows에서는 `py -3` — README FAQ에 안내)

**version.py** — 버전 SSOT 조작:

```
version.py get    [--scope <name>] [--json]   # 대표 버전(첫 번째 versionLocation) 1줄 출력 (--json: 위치별 전체)
version.py set <version> [--scope <name>]      # 전 위치 동기 수정 + old→new 요약 출력
version.py verify [--scope <name>] [--json]    # 전 위치 일치 검사 (preflight 게이트, 불일치 시 exit 1)
```

versionLocations 타입 3종 지원: `properties-key`(key=value 파일) / `json-path`(package.json 등) / `regex`(캡처 그룹 1개 — Dockerfile LABEL, README 배지 등 범용).

**next-version.py** — 버전 산술 일원화 (LLM 산술 금지):

```
next-version.py --scope <name> --bump <major|minor|patch>     # config 기반 (현재 버전·체계 자동)
next-version.py --scope <name> --release                       # 수식어 제거 (1.3.0-SNAPSHOT → 1.3.0)
next-version.py --scope <name> --bump minor --qualifier SNAPSHOT   # 다음 개발 버전 (→ 1.4.0-SNAPSHOT)
next-version.py --current 1.2.3 --scheme semver --bump minor   # 순수 모드 (config 불필요 — 사람/테스트용)
# M3: --scheme calver --pattern <PATTERN> [--today YYYY-MM-DD] / --scheme headver --head <N> [--today ...]
```

CalVer/HeadVer의 날짜·주차 산술 포함(M3). `--today` 주입으로 테스트 결정론 확보. HeadVer: head=config/수동, yearweek=스크립트 계산(yy+ISO주차), build=마지막 버전의 build+1 자동.

**changed-packages.py** (M2) — `changed-packages.py <ref> [--json]`: anchor..HEAD 변경 파일을 scope path prefix로 매핑, 대상 scope 목록 출력.

### 6.7 템플릿

- 노트 템플릿 3종(단일/패키지/train) 중 해당분만 생성. 섹션: Highlights / Changes / Breaking Changes / 마이그레이션 가이드. 문구는 `notes.language` 기준(ko/en 블록을 dialect 조건부로 보유, both면 양쪽 렌더)
- `changelog-entry.md`: Keep a Changelog 호환 항목 골격. CHANGELOG.md 삽입은 Claude가 수행(헤더 아래 최신 항목으로, Unreleased 섹션 존중) — 결정론 스크립트로 만들지 않는다(과설계 방지, dry-run diff로 검증)
- **템플릿은 유일한 손편집 허용 영역**: 마커를 제거하면 재init이 보존 (5.4절)

### 6.8 config.json 스키마

```json
{
  "superrelease": {
    "pluginVersion": "0.1.0",
    "configVersion": 1,
    "generatedAt": "2026-07-09T00:00:00Z"
  },
  "repo": {
    "kind": "app",
    "defaultBranch": "main",
    "mergePolicy": "squash",
    "releasePath": "direct-push",
    "branching": "trunk",
    "maintenanceLines": false,
    "train": false,
    "releaseCommitFormat": "chore(release): {version}"
  },
  "github": {
    "release": true,
    "generateNotes": true,
    "releaseYml": true
  },
  "scopes": [
    {
      "name": "root",
      "path": ".",
      "scheme": { "type": "semver", "pattern": null },
      "versionLocations": [
        { "file": "gradle.properties", "type": "properties-key", "key": "version" },
        { "file": "package.json", "type": "json-path", "path": "version" },
        { "file": "README.md", "type": "regex", "pattern": "version-([0-9][^-]*)-blue" }
      ],
      "tag": { "enabled": true, "format": "v{version}", "annotated": true, "signed": false, "movingMajorTag": false },
      "bump": {
        "mode": "auto-confirm",
        "sources": ["conventional-commits", "pr-metadata"],
        "fallback": "diff",
        "compatCheck": null
      },
      "preRelease": { "style": "mutable", "qualifier": "SNAPSHOT" },
      "devChannel": {
        "enabled": true,
        "qualifier": "SNAPSHOT",
        "immutableId": ["spring-build-info", "docker-sha-tag"]
      },
      "postRelease": { "bump": "next-snapshot" },
      "notes": {
        "destinations": ["changelog", "github-release"],
        "language": "ko",
        "audience": "developers",
        "tone": "neutral",
        "template": "notes-single.md",
        "perReleasePath": "docs/releases/"
      },
      "anchor": { "type": "tag", "value": null },
      "dependents": []
    }
  ],
  "decisions": [
    {
      "topic": "scheme",
      "scope": "root",
      "answer": "semver",
      "rationale": "기존 태그 12개가 모두 vX.Y.Z 패턴",
      "source": "scan",
      "decidedAt": "2026-07-09"
    }
  ]
}
```

필드 주석 (비자명한 것만):

- `superrelease.configVersion`: config 스키마 버전 — 플러그인 업데이트 시 마이그레이션 감지
- `repo.kind`: `app | library | monorepo` / `repo.train`: 이중 체계(M3)에서 release-train 스킬 생성 조건
- `repo.releaseCommitFormat`: placeholder `{version}`, `{scope}` — chore 타입이라 다음 릴리스 노트에서 자연 제외됨
- `scheme.type`: `semver | calver | headver | sequential` (`pattern`은 calver/headver용)
- `bump.mode`: `auto-confirm | manual` / `bump.compatCheck`: 라이브러리용 API 호환성 도구 식별자(예: `kotlin-bcv`, `japicmp`) 또는 null
- `preRelease.style`: `none | mutable | counter`
- `devChannel.immutableId`: **M1에서는 기록 + 안내만**(Spring `buildInfo()` 스니펫, Docker `sha-{shortSha}` 태그 제안 등). dev 배포 자동화는 CI 몫이므로 하지 않는다
- `notes.destinations`: `changelog | release-file | github-release`(M1) / `fragment | tag-message`(M3). `release-file` 선택 시 `perReleasePath` 사용 (기본 `docs/releases/` — 사람이 읽는 문서 경로에 도구명을 넣지 않는다)
- `anchor`: `tag.enabled=false`일 때 `{ "type": "ref", "value": "<sha>" }` — release 스킬이 릴리스 후 갱신. **config에서 유일하게 상태를 갖는 필드**임을 명시적으로 문서화
- `dependents`: (M2) 이 scope가 bump되면 자동 patch bump할 scope 이름 목록

## 7. 확정 정책: pre-release · dev 채널 · post-release

원 프롬프트 5절 전문을 `references/prerelease-and-dev-channel.md`에 담고 생성 스킬 동작에 반영한다. 요지:

**두 가지 수식어 모델 구분 (혼동 금지)**:

- **불변 카운터형**: `-alpha.1`, `-M1`, `-RC.2` — 한 번 발행되면 불변, 다음은 카운터 증가. SemVer pre-release 시맨틱. (릴리스 플로우 구현은 M3, config 자리는 M1부터)
- **가변 덮어쓰기형**: `-SNAPSHOT`(Maven) 등 — 같은 버전 문자열을 계속 덮어쓰고 소비자가 가변으로 취급. 저장소 시맨틱 자체가 다르다.

**웹 앱의 dev 서버 배포 (핵심 시나리오)**:

- dev 서버에만 배포되는 빌드는 버전을 bump하지 않는다. 파일 버전은 `{다음 목표 버전}-{가변 수식어}`(예: `1.3.0-SNAPSHOT`)로 유지하고 dev 배포는 이 문자열을 계속 덮어쓴다.
- 단, best practice로 **불변 식별자를 반드시 병기**한다 — 가변 문자열만으로는 dev에 어떤 코드가 떠 있는지 추적 불가:
  - Spring: `springBoot { buildInfo() }` + git.properties(커밋 sha) → `/actuator/info`
  - Docker: 가변 채널 태그(`dev`)와 불변 태그(`sha-{shortSha}` 또는 `{version}-{shortSha}`) 함께 push
  - npm 계열: 필요 시 `1.3.0-dev.{sha}` 옵션
- 요약: 사람용 라인 표시는 가변 수식어, 추적은 불변 sha. **정식 릴리스만 bump + 태그.**

**post-release**:

- JVM 라이브러리: 릴리스 직후 다음 개발 버전 `-SNAPSHOT` bump 커밋 (Maven/Spring 관례)
- 앱/서비스: post-release bump 없음이 기본. dev 채널을 SNAPSHOT 방식으로 쓰면 릴리스 직후 `{next}-SNAPSHOT` 복귀가 자연스럽다 (사실상 같은 관례)
- init이 레포 성격에 따라 기본값을 제안하고 확인만 받는다

## 8. 안전장치 (전 스킬 공통)

- dry-run 우선 (6.2·6.3 표준 프리뷰)
- **버전 재사용 금지**: 잘못 나간 버전은 재태깅하지 않는다. 회수는 다음 패치로 덮거나 생태계 절차(npm deprecate, PyPI yank) 안내
- 태그 생성이 동시 릴리스에 대한 자연 락 — push 직전 태그 충돌 재확인, 충돌 시 즉시 중단
- 실패 시 상태 명시: 어디까지 진행됐고 무엇을 되돌려야 하는지 출력. preflight의 중단 상태 감지와 짝
- preflight 브랜치·동기화·verify 게이트 (6.3)

## 9. references/ 지식 문서 명세 (7종, M1에서 전부 작성)

| 파일 | 내용 |
|---|---|
| `version-schemes.md` | SemVer(라이브러리 사실상 강제), CalVer(release train·서비스), HeadVer(`{head}.{yearweek}.{build}`, 앱/서비스용), Sequential. 각 체계의 규칙·적합한 레포 성격·다음 버전 계산법. SemVer 0.x 관례(breaking→minor) 포함. 외부 링크 병기: [semver.org](https://semver.org/), [calver.org](https://calver.org/), [HeadVer](https://github.com/line/headver) + [LY 기술블로그](https://techblog.lycorp.co.jp/ko/headver-new-versioning-system-for-product-teams) |
| `prerelease-and-dev-channel.md` | 7절 전문 |
| `monorepo.md` | fixed / independent / 이중 체계(루트 CalVer train + 패키지 SemVer, Spring Cloud 사례), 내부 의존성 전파 규칙, 태그 네임스페이스(`{pkg}@{ver}`) |
| `bump-models.md` | semantic-release / release-please / changesets 3모델 비교, Conventional Commits 매핑(feat→minor, fix→patch, BREAKING CHANGE·`!`→major), squash 레포에서 PR 메타데이터가 1차 소스인 이유와 역참조(`(#N)`, commits→pulls API), diff는 검증용(토큰 비용), API 호환성 도구 연동(Kotlin binary-compatibility-validator, japicmp) |
| `notes-and-changelog.md` | 목적지 5종과 조합(①CHANGELOG 누적 ②per-release 파일 ③GitHub만 ④fragment/changelog.d ⑤annotated tag 내장), `gh release create --generate-notes` + `.github/release.yml` 하이브리드, 독자·언어·어조 |
| `branching-and-release-path.md` | trunk-based/GitHub flow(신규 기본), git flow는 병렬 유지보수 라인 필요 시만, protected branch → 릴리스 PR 모드(release-please식), `on.push.tags` 감지 → "태그 = 배포 버튼" 인지 |
| `edge-cases.md` | 혼재 태그 포맷(과거 불변·향후 표준만 질문), 태그·파일 버전 불일치 시 신뢰 대상 질문, 첫 릴리스 0.1.0 vs 1.0.0, CHANGELOG backfill, 버전 재사용 금지와 회수 절차, 중단 상태 복구 |

## 10. README 명세

**README.md (영어, 기본)** — 상단에 `[한국어](README_KO.md)` 링크. **README_KO.md (한국어)** — 동일 구성, 상단에 `[English](README.md)` 링크. 두 파일은 항상 동기 유지.

구성:

1. 소개 — 컴파일러 패턴 개념(one fat init → lean per-project toolkit), 왜 생성물을 커밋하는가(팀 자립성)
2. 요구사항 — Claude Code, Python 3.9+(생성 스크립트 실행), gh CLI 또는 GitHub MCP(GitHub Release 사용 시)
3. 설치 — `/plugin marketplace add Cho-D-YoungRae/superrelease` → `/plugin install superrelease@superrelease`, 로컬 개발(`claude --plugin-dir .`)
4. 빠른 시작 — `/superrelease:init` 또는 "릴리스 관리 셋업해줘" → 질문 답변 → 생성물 커밋 → 이후 "릴리스해줘"
5. 생성물 안내 — 트리, 각 파일 역할, **전부 커밋해야 하는 이유**
6. 일상 사용 — 릴리스 / status("릴리스 준비됐어?") / 노트만 미리 쓰기
7. 재init·커스터마이징 — config가 SSOT, config 수정 → 재init(질문 없는 재렌더), 템플릿만 손편집 허용(마커 제거)
8. 버전 체계 소개 — SemVer/CalVer/HeadVer 요약 + 외부 링크
9. 스크립트 단독 사용 — 플러그인 없는 팀원용 (`python3 .superrelease/scripts/version.py verify` 등)
10. FAQ — 플러그인 없는 팀원도 되나(생성 스킬·스크립트는 자립적) / Windows에서 python3(`py -3`) / gh CLI 없이 GitHub MCP만 있어도 되나(폴백 지원) / 제거 방법(`.superrelease/` + `.claude/skills/release*` 삭제) / 배포(publish)는 왜 안 하나(태그 트리거 CI 권장 — 가이드 문단) / 잘못 나간 버전 회수
11. 로드맵 — M1/M2/M3

## 11. 테스트·검증 전략

- **unittest (Python stdlib만, `tests/`)**:
  - render.py: dialect 전 구문, manifest `when`, 마커 삽입, 템플릿 보존 규칙, `--check`/`--force`, 개행 보존
  - version.py: location 타입 3종 get/set/verify, package-lock.json 동기 수정, JSON 포맷 보존 라운드트립(버전 필드 외 바이트 동일)
  - next-version.py: semver 벡터(bump/release/qualifier 조합), M3에서 calver/headver 벡터(`--today` 주입)
  - scan.py: 임시 git 레포 픽스처(태그 패턴, CC 사용률, 모노레포 신호)
- **골든 렌더 테스트**: 대표 config 3종(Gradle 단일 앱 / npm 앱 / 라이브러리) → 생성 트리 전체 스냅샷 비교 — 재init 결정론성의 회귀 방어선
- **플러그인 구조 검증**: `claude plugin validate . --strict`
- **시나리오 e2e (대화형, 마일스톤 완료 기준)**: 샘플 레포에서 init → 릴리스 실제 수행
- **dogfooding (M1 스트레치)**: 이 플러그인 레포 자체에 init 적용 — plugin.json `version`이 json-path 버전 위치의 실전 검증
- skill-creator 스킬이 사용 가능하면 description 트리거 최적화에 활용

## 12. 마일스톤과 완료 기준

### M1 — 단일 레포 해피패스 (이번 구현 범위)

산출물: 플러그인 골격(plugin.json, marketplace.json) / init SKILL.md(패스트트랙 + 번들, 재init 포함) / references 7종 전부 / scan.py, render.py + manifest / assets: release·release-notes SKILL, version.py, next-version.py(semver), notes-single.md, changelog-entry.md, release.yml / README.md + README_KO.md / tests.

지원 범위: Gradle(gradle.properties·build.gradle.kts) + npm/pnpm, SemVer, 가변 SNAPSHOT, CHANGELOG + release-file + GitHub Release, direct push.

완료 기준:

1. `claude plugin validate . --strict` 통과
2. unittest 전부 통과 + 골든 렌더 3종 일치
3. 샘플 Gradle 앱 레포: init → 첫 릴리스 → 두 번째 릴리스(SNAPSHOT 사이클 포함)가 dry-run 프리뷰와 함께 end-to-end 동작
4. 샘플 pnpm 앱 레포: init → 릴리스 1회 e2e
5. (스트레치) superrelease 레포 자체 dogfooding

### M2 — 모노레포

fixed/independent 전략, changed-packages.py, 태그 네임스페이스(`{pkg}@{ver}`), 내부 의존성 전파(dependents patch bump), notes-package.md, init 질문 확장. 완료 기준: pnpm 모노레포 샘플에서 independent 전략으로 두 패키지 개별 릴리스 + 전파 e2e.

### M3 — 조건부 기능

이중 체계 + release-train, hotfix, 릴리스 PR 모드(protected branch) + release-pr-body.md, CalVer/HeadVer(next-version.py 확장), 불변 카운터형 pre-release 릴리스 플로우(+ GitHub Release `--prerelease`), moving major tag 실구현, CHANGELOG backfill, fragment(changelog.d)·tag-message 목적지. 완료 기준: protected-branch 샘플에서 릴리스 PR 모드 e2e, CalVer/HeadVer 벡터 테스트, train/hotfix 시나리오 각 1회.

## 13. 비범위 (Non-goals)

- CI 워크플로 생성 (태그 트리거 감지·경고는 범위, 생성은 프로젝트별 편차가 커서 제외)
- 아티팩트 publish 실행 (npm publish, maven publish 등 — 태그·GitHub Release까지가 범위, 배포는 태그 트리거 CI 권장을 FAQ로 안내)
- towncrier 등 외부 릴리스 도구 설치·통합 (fragment는 자체 규약으로, M3)
- GPG 서명 키 설정 (config `signed` 플래그만 지원)
- 브랜치 보호 규칙 설정 **변경** (init·생성 스킬은 규칙을 대신 만들지 않는다 — 단, release-pr + 미보호 감지 시 ruleset/branch-protection 설정 명령을 **조언**하는 것은 범위)
- dev 채널 배포 자동화 (immutableId는 기록 + 스니펫 안내만)

## 14. 리스크와 완화

| 리스크 | 완화 |
|---|---|
| 템플릿 dialect 복잡화 | dialect 동결(5.2 구문 외 확장 금지) + 골든 테스트 |
| scan 오탐 (버전 위치 census, CI 트리거) | 질문 단계에서 반드시 확인형 재확인, CI 트리거는 Claude가 워크플로 직접 읽어 확정 |
| package.json·lockfile 포맷 훼손 | 보존형 json writer + 라운드트립 테스트 + dry-run에서 diff 표시 |
| 생성 스킬 트리거가 타 플러그인과 충돌 | description에 프로젝트명 포함으로 특정성 강화 |
| 팀원 머신에 python3 부재 | README 요구사항 명시 + 스크립트 자체 버전 가드 + Windows FAQ |
| LLM의 CHANGELOG 삽입 실수 | 템플릿 고정 + dry-run diff 확인 게이트 |

## 15. 이 설계에서 확정한 결정 기록

| 결정 | 선택 | 근거 |
|---|---|---|
| 구현 범위 | M1 먼저 완주, M2·M3 후속 세션 | 검증 깊이·컨텍스트 품질 (사용자 확정) |
| 렌더링 방식 | render.py 결정론 렌더러 | 재init 결정론성이 명시 요구사항, 골든 테스트 가능 (사용자 확정) |
| README | 영어 기본 + README_KO.md 병행 | 공개 레포, harness 레포 패턴 (사용자 확정) |
| 스크립트 언어 | Python 3.9+ stdlib | bash는 JSON·Windows 취약, Node는 비JS 레포 보장 불가 |
| 스크립트 설계 | config-driven verbatim 복사 | 재init 시 스크립트 diff 없음, 로직/정책 분리 |
| 질문 UX | 패스트트랙(추천 일괄 수락) → 번들 7개 | 기존 레포는 스캔 추론이 대부분 정확 |
| init 마무리 | 확인 후 생성물 커밋까지 실행 | 미커밋 시 팀 공유가 깨지는 지점 |
| 스크립트 --help 언어 | 영어 (설계 중 한국어에서 변경) | 공개 코드 관례, 한국어 사용법은 README_KO 담당 |
| release-file 목적지 | M1 포함 (원 프롬프트 M1 범위에서 확장) | 렌더 결과를 파일로 쓰는 것뿐이라 비용 ~0, 원 프롬프트가 기본 경로까지 지정한 관심 항목 |
| fragment·tag-message 목적지 | M3 | 원 프롬프트 M1 범위 준수 |
| counter pre-release·moving major tag | config 자리만 M1, 구현 M3 | moving tag는 태그 force-push라 안전장치 설계 필요 |
| GitHub 접근 | gh CLI 우선 → GitHub MCP 폴백 → 제한 모드 | MCP는 설치마다 도구 구성이 달라 스킬 본문에 고정 불가, 런타임 발견 폴백이 lean 유지 (사용자 제기) |
| package.json 조작 | Python 단일화 — npm 셸아웃 제거 (원 프롬프트 6.7 "네이티브 우선"에서 변경) | 단일 도구체인, node 없는 머신에서도 동작, 테스트 단순화. lockfile은 json-path 직접 수정으로 충분 (사용자 제기) |
| plugin.json author | Cho-D-Youngrae (yrc9229@gmail.com) | git 설정 변경 반영 (사용자 확정) |

구현 계획 단계에서 확정할 세부(스펙 범위 아님): 질문 문구·release.yml 카테고리 구성·템플릿 문안·각 asset의 구체 내용.
