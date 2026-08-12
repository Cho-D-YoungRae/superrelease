# M9 설계 — 스캔 확장 에픽 (B-8 + B-6)

2026-08-12 · 근거: [커버리지 검토 §8 P1 백로그](2026-08-06-coverage-review.md) · 로드맵: [M8 스펙 §0](2026-08-12-m8-onboarding-entrance-design.md)

## 0. 배경과 범위

커버리지 검토가 "엔진은 되는데 입구가 없다"고 진단한 갭(전 그룹 C1)을 메운다. B-8(스캔 확장)과 B-6(기존 자동화 감지)을 **한 사이클**로 완주한다(사용자 승인, 2026-08-12). 탐색 범위는 **관례 위치 한정**(접근 A — 사용자 승인): 임의 재귀 탐색 대신 생태계 관례 디렉터리만 보고, 잔여는 M8이 만든 "후보 0건 → 수동 등록" 분기가 받는다.

**공통 원칙**: scan.py는 읽기 전용·Python 3.9+ stdlib 전용 유지. TOML은 tomllib(3.11+) 없이 관례 형태만 regex로 파싱한다. version.py·next-version.py·render 엔진·asset 무변경 — **골든·dogfood 무변경 마일스톤**이다.

## 1. 파일 타입 확장 (scan_version_candidates + scan_build_systems)

| 대상 | 방식 | 규칙 |
|---|---|---|
| `pubspec.yaml` | regex `^version:\s*(\S+)` | 값에 `+`(빌드 번호)가 있으면 **usable:false + advice `pubspec-build-number`** — `version.py set`이 빌드 번호를 소실시킨다(next-version.py는 B-4로 이미 거부). 없으면 일반 후보. buildSystems에 `flutter`(dependencies에 flutter) 또는 `dart` |
| `*.xcconfig` | regex `^MARKETING_VERSION\s*=\s*(\S+)` | 루트와 `ios/`의 1-depth `*.xcconfig`. 파일 여러 개면 각각 후보(다중 등록 → 동기 수정). `CURRENT_PROJECT_VERSION`(빌드 번호)은 감지하지 않는다(M10) |
| `build.gradle(.kts)` `versionName` | regex `versionName\s+['"]([^'"]+)['"]` | 관례 위치 `app/`·`android/app/`(React Native/Flutter). `versionCode`는 감지하지 않는다(M10) |
| `src-tauri/tauri.conf.json` | json-path `version` | v2 최상위 `version`, 없으면 v1 `package.version` 폴백 |
| `Chart.yaml` `appVersion` | **usable:false + advice `chart-app-version`** | 차트 버전(기존 후보)과 앱 버전의 이원 구조 안내용 — 백로그 지시 그대로 |
| `charts/*/Chart.yaml` | 모노레포 신호 + packages | 신호 `charts/: Chart.yaml children`, packages 항목 `{path, name, version, buildSystem: "helm"}` |
| `go.mod` | buildSystems `go` | 버전 후보 아님 — "후보 0건" 분기의 성격 힌트 |
| `*.tf`(루트 글롭) | buildSystems `terraform` | 동상 |

## 2. workspace·모노레포 힌트 (scan_monorepo)

- **uv workspace**: pyproject.toml `[tool.uv.workspace]`의 `members` 글롭(트레일링 `/*`·`/**`는 기존 node 방식과 동일하게 1-depth 확장)을 확장해 멤버별 `{path, name, version, buildSystem: "python"}` 수집(멤버의 pyproject.toml `name`·`version`은 기존 PYPROJECT_VERSION_PATTERN 계열 regex). 내부 의존성은 멤버 pyproject의 `[project]` 테이블 `dependencies` 배열(+ `[project.optional-dependencies]`의 각 배열) 문자열에서 멤버 이름을 매칭해 `internalDependencies`에 합류(node와 같은 이름 기반 방식, PEP 508 문자열은 선두 `[A-Za-z0-9._-]+`만 이름으로 절단).
- **pom `<modules>`**: 기존 ET 파서를 재사용해 `<modules><module>` 목록을 `mavenModuleHints`로 리포트(gradleModuleHints 대응). packages로 승격하지 않는다 — maven 모노레포는 revision 공유가 관례.
- **poetry workspace는 비범위** — 공식 workspace 개념이 없다(§7).

## 3. scoped 태그 (scan_tags)

- `TAG_PATTERNS`에 `scoped` 클래스 추가: `^@?[A-Za-z0-9._/-]+@v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$`. byPattern·mixed 계산에 자연 포함된다.
- `scopedPrefixes` 필드 추가: scoped 태그의 `@` 앞 프리픽스 빈도 상위 목록(최대 10) — init이 independent 모노레포의 scope 이름·`tag.format` 제안에 쓴다.

## 4. B-6 — 기존 릴리스 자동화 감지

새 함수 `scan_release_automation(repo)` → top-level 리포트 키 `releaseAutomation`:

```json
{"tools": [
   {"name": "changesets", "signals": [".changeset/"], "pendingFragments": 3},
   {"name": "semantic-release", "signals": [".releaserc", "package.json:release"]},
   {"name": "release-please", "signals": ["release-please-config.json"]},
   {"name": "towncrier", "signals": ["pyproject.toml:[tool.towncrier]"]}],
 "ciWorkflows": [".github/workflows/release.yml"]}
```

감지 규칙(전부 존재 확인·정규식 수준 — 실행 없음):

- **changesets**: `.changeset/` 디렉터리. `pendingFragments` = `.changeset/*.md` 중 `README.md` 제외 개수.
- **semantic-release**: `.releaserc`(무확장·`.json`·`.yaml`·`.yml`·`.js`·`.cjs`) · `release.config.(js|cjs|mjs)` · package.json의 `release` 키 · dependencies/devDependencies에 `semantic-release`.
- **release-please**: `release-please-config.json` · `.release-please-manifest.json`.
- **towncrier**: `towncrier.toml` · pyproject.toml에 `[tool.towncrier]` 섹션.
- **ciWorkflows**: `.github/workflows/*.yml|yaml`에서 `changesets/action`·`release-please`·`semantic-release`·`towncrier` 문자열을 참조하는 파일 목록 — 이중 자동화 경고의 근거.

**init SKILL.md 안내**(`tools` **또는** `ciWorkflows`가 비어 있지 않으면 — ciWorkflows는 tools의 부분집합이 아니다(설정 파일 없이 CI 액션만 쓰는 레포), Phase 2 번들 질문 전 한 단락 — 실행은 경계):

1. 이중 자동화 경고 — 기존 도구의 CI 파이프라인이 살아 있는 동안 superrelease가 태그·Release를 만들면 같은 태그·버전을 두 시스템이 경합한다. `ciWorkflows` 목록을 보여주고, 전환하려면 해당 워크플로 비활성화가 선행돼야 함을 안내(수정은 사용자 몫).
2. 펜딩 조각 처리 — changesets `pendingFragments` N > 0이면 기존 도구로 소진(마지막 릴리스)하거나 수동 반영 후 전환할 것을 안내.
3. per-package CHANGELOG 화석화 고지 — 기존 도구가 쓰던 패키지별 CHANGELOG는 전환 후 갱신되지 않는다(B-10이 M11 후보).
4. 발행 경로 전환 — 기존 도구가 publish까지 맡고 있었다면, superrelease는 태그·GitHub Release까지만 하므로 태그 트리거 publish 워크플로로의 전환 방향을 한 단락으로 안내(실행 없음).
5. `decisions`에 `{"topic": "existing-automation", "answer": "coexist-warned" | "migrating", "rationale": "<감지 도구·조각 수>", "source": "scan", "decidedAt": "<date>"}` 기록.

## 5. 문서

- **init SKILL.md**: 스캔 감지 목록(Phase 1 절) 갱신 + §4의 안내 단락. ≤500줄 유지(현재 148줄).
- **references/edge-cases.md**: "스캔 밖 수동 등록 레시피" 절 신설 — Info.plist(CFBundleShortVersionString은 키·값이 별도 줄이라 단일행 regex 위치 불가 → xcconfig `MARKETING_VERSION` 전환 권장) · tauri v1/v2 위치 차이 · Android `versionName` 관례 위치.
- **README 양판**: 알려진 한계의 모바일 문구 완화(마케팅 버전 축은 scan이 감지 — 빌드 번호 축 미지원은 유지, M10) + 기존 자동화 문구를 "감지·경고·이주 안내함(파이프라인 전환 실행은 사용자)"으로 갱신. 케이스 커버리지 표의 스캔 감지 목록 갱신. CHANGELOG `[Unreleased]` 기입.

## 6. 검증·테스트

- **test_scan.py**(현 39개)에 추가: 파일 타입별 tmp 픽스처(감지값·usable·advice — pubspec `+N` 분기 포함) · xcconfig 다중 파일 · uv workspace(members 확장·내부 의존성) · mavenModuleHints · scoped 태그(byPattern·scopedPrefixes) · releaseAutomation 도구별·ciWorkflows·pendingFragments.
- **test_render_pipeline.py**: M7의 "scan `*_PATTERN` 상수 전수 → `validate_config` 통과" 테스트가 새 패턴을 포섭하는지 확인하고 개수 어서션 갱신.
- **골든·dogfood 무변경 검증**: `git status --porcelain tests/golden .claude .superrelease`가 빈 출력이어야 한다(이 마일스톤의 핵심 불변식).
- 전체 `python3 -m unittest discover -s tests -q` → `claude plugin validate . --strict`.
- scan_tags의 `latest` 릴리스 패턴 무필터 문제(M8 이월): scoped 클래스 추가로 byPattern 정보가 풍부해지므로, `latest`는 그대로 두되 init 프로즈가 byPattern 기준으로 판단하게 유지(별도 변경 없음 — 스코프 유지).

## 7. 비범위

- 빌드 번호 축 관리(versionCode·CFBundleVersion·pubspec `+N` 산술) — M10 B-7.
- Cargo.lock 동기화(B-9)·watchPaths(B-11)·per-package CHANGELOG 목적지(B-10) — M11.
- poetry workspace — 공식 개념 부재(path dependency 감지는 하지 않음).
- 자동화 이주 실행(CI 수정·조각 소진·기존 도구 제거) — 안내만, 실행은 사용자.
- Info.plist 직접 versionLocation — 다중라인 구조는 엔진(단일행 regex) 한계 — 레시피로 xcconfig 안내.
