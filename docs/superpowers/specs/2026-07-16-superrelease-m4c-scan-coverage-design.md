# superrelease M4c — 스캔 커버리지 확장 설계

이 문서는 M4 로드맵의 세 번째 마일스톤 **M4c**의 설계다. 2026-07-15 전면 리뷰가 지적한 스캔 사각(Maven 비대칭, Gradle 모노레포 빈손, VERSION 미감지, openapi 스펙-코드 드리프트)과 M4b 최종 리뷰 이관분(hasDevelop 리터럴), 그리고 PEP 440 한계의 침묵을 닫는다. **scan.py·init·references만 변경 — 골든 diff 0인 마일스톤이다** (scan.py는 골든 미복사, 생성 스킬·템플릿·자산 스크립트 무변경).

M4 로드맵: M4a 정확성(PR #12) → M4b gitflow(PR #13) → **M4c 스캔 커버리지(본 문서)** → M4d 사용성·문서.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md) §4.2(openapi info.version 약속 — 본 마일스톤이 이행). 베이스 커밋: main `e171ace`.

## 배경

- **Maven 비대칭**: scan.py가 pom.xml을 buildSystems로 감지하면서 버전 후보는 뽑지 않는다. 단, Maven의 project 직계 `<version>`은 parent/dependency `<version>`과 **regex로 구분할 수 없고**, `version.py set`은 참여 매치를 전부 치환하므로 순진한 regex 후보는 pom 오손 위험이 있다(사용자 결정: xml-path 타입 신설 대신 "감지+안전 후보만").
- **Gradle 모노레포 빈손**: `monorepo.packages`의 경로·버전 수집이 package.json 계열 전용이라, JVM 모노레포에서 init 번들 1의 핵심 흐름(패키지 표 확정)이 데이터 없이 진행된다.
- **VERSION 플레인 파일 미감지**, **openapi info.version**은 원 설계 스펙 §4.2가 약속했으나 미구현(스펙-코드 드리프트).
- **hasDevelop**이 리터럴 `"develop"`만 매칭해 `dev`/`development` 통합 브랜치 레포에서 M4b의 번들 6 브랜칭 질문이 발화하지 않는다.
- **PEP 440 침묵**: `1.2.0.dev0` 등 Python 고유 문법은 next-version.py의 SemVer 파서가 거부하는데(qualifier 하이픈 문법), pyproject.toml을 1급으로 스캔하면서 이 한계가 어디에도 명시돼 있지 않다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 스코프 | 6건 전부(pom·gradle 모노레포·VERSION·openapi·hasDevelop·PEP 440 문서화) | 사용자 결정 |
| 구현 형태 | scan.py 인라인 확장(기존 함수에 추가, 약 340→430줄) | 읽기 전용 단일 스크립트 원칙 유지. 모듈 분리는 이 규모에 과함 |
| pom.xml 깊이 | **감지 + 안전 후보만** — `<revision>` property는 정상 후보, 일반 project `<version>`은 감지·안내 전용 | 사용자 결정. regex 오손 리스크 0. xml-path 타입 신설은 후속 |
| 후보 구분 | versionCandidates 엔트리에 선택 필드 `usable: false` + `advice` | "쓰기 가능한 후보"와 "감지·안내 전용"의 구조적 구분 — init이 오해 없이 표를 만든다 |
| libs.versions.toml | **제외** | 의존성 버전 카탈로그이지 프로젝트 자기 버전을 두는 관례가 아님 — 후보로 잡으면 오탐이 기본값 |
| gradle 내부 의존성 | 제외(후속) | `project(":x")` regex 파싱은 신뢰도가 낮음 — packages 수집(path·name·version)까지만 |
| YAML openapi | regex 휴리스틱 + 값이 버전 형태일 때만 후보 | stdlib에 YAML 파서 없음. 스캔은 후보일 뿐이고 init이 표로 확인하는 기존 계약(ci.tagTriggerCandidates 선례) |
| hasDevelop | `develop > development > dev` 우선순위 + 신규 `developBranchGuess` 필드 | `dev`는 용도가 다양해 우선순위 최하위. M4b 번들 6 프로즈("감지된 통합 브랜치명")가 이미 이 값을 기다림 |

## A. scan_version_candidates 확장 (scan.py)

versionCandidates 엔트리 스키마에 선택 필드 2개를 추가한다: `usable: false`(이 엔트리는 versionLocation으로 쓸 수 없음 — 기본은 필드 부재 = 사용 가능)와 `advice`(사용자에게 안내할 문구의 근거 데이터).

1. **pom.xml** — `xml.etree.ElementTree`로 파싱(POM 네임스페이스 유무 모두 대응 — 태그 localname 매칭). 파싱 실패 시 조용히 건너뜀(기존 JSONDecodeError 선례).
   - project 직계 `properties/revision`이 있으면: `{"file": "pom.xml", "type": "regex", "value": <값>, "pattern": "<revision>([^<]+)</revision>"}` — 정상 후보. revision은 pom에서 이 형태로 유일하다(CI-friendly versions 관례).
   - 아니고 project 직계 `version`이 있으면: `{"file": "pom.xml", "type": "regex", "value": <값>, "usable": false, "advice": "maven-project-version"}` — pattern 없음. init이 이 advice 코드를 보고 "pom의 project <version>은 regex로 parent/dependency와 구분할 수 없어 위치로 쓸 수 없다 — versions-maven-plugin 운용 또는 CI-friendly `<revision>` property 전환을 권장"을 안내한다.
   - 둘 다 없으면(순수 aggregator pom 등) 엔트리 없음.
2. **VERSION 플레인 파일** — 루트 `VERSION` 파일의 내용이 공백 제거 후 **단일 라인 버전 형태**(`^v?\d[\w.\-+]*$`)일 때만: `{"file": "VERSION", "type": "regex", "value": <값>, "pattern": "^(\\S+)\\s*$"}`. 버전 형태가 아니면 엔트리 없음(다른 용도의 VERSION 파일 오탐 방지).
3. **openapi** — 루트에서 `openapi.json`·`openapi.yaml`·`openapi.yml`·`swagger.json`·`swagger.yaml`·`swagger.yml`을 이 순서로 확인, **첫 매치 1건만** 후보화:
   - JSON: `json.loads` → `info.version`이 문자열이면 `{"file": <이름>, "type": "json-path", "value": <값>, "path": "info.version"}` — version.py의 dotted json-path가 이미 read/write를 지원하는 완전한 후보.
   - YAML: regex 휴리스틱 `^[ \t]+version:\s*["']?([0-9][^"'\s#]*)` (MULTILINE, **들여쓴 version 키만** — 최상위 `openapi:`/`version:` 문서 키와 구분. `[ \t]+`인 이유: `\s+`는 MULTILINE에서 개행을 삼켜 비들여쓰기 줄까지 매칭될 수 있다) 첫 매치. 값이 버전 형태일 때만 후보로 넣고, 같은 pattern을 기록한다. 오탐 가능성은 init의 후보 확인 표가 흡수한다(스캔=후보 계약).
4. **libs.versions.toml은 넣지 않는다** — 위 결정 표의 근거를 이 스펙이 기록으로 남긴다.

기존 후보(gradle.properties·build.gradle(.kts)·package.json·pyproject.toml·Cargo.toml·Dockerfile·Chart.yaml·README 배지)는 무변경.

## B. scan_monorepo Gradle 확장 (scan.py)

- `_gradle_packages(repo)` 신설: settings.gradle(.kts)의 `include` 라인에서 모듈 경로를 해석한다 — `include(":a")` / `include ':a', ':b'` / `include(":a:b")` → 콜론 구분을 디렉터리 경로로(`a`, `a/b`). 기존 `_module_hints`의 추출 regex를 재사용하되 경로 변환을 더한다.
- 각 모듈 디렉터리에서 버전을 수집: 모듈의 `gradle.properties`(`version=` 키) 우선, 없으면 `build.gradle(.kts)`의 기존 `GRADLE_VERSION_PATTERN`. 없으면 `version: null`.
- 산출 스키마는 node 패키지와 동일 + 구분 필드: `{"path": "a/b", "name": <마지막 세그먼트>, "version": <값|null>, "buildSystem": "gradle"}`. **node 패키지 엔트리에도 `"buildSystem": "node"`를 부여**해 대칭을 맞춘다(additive 필드 — 기존 소비자는 영향 없음).
- `internalDependencies`는 node 전용 유지(gradle은 결정 표대로 후속). `gradleModuleHints` 필드는 하위호환으로 유지한다.
- `suspected` 판정에 gradle packages도 반영: `len(packages) > 1`이 gradle 포함 총수로 계산되도록.

## C. scan_branches 확장 (scan.py)

- `DEVELOP_BRANCH_NAMES = ("develop", "development", "dev")` — names와의 교집합을 이 우선순위로 검사해 첫 매치를 `developBranchGuess`(문자열|null)로 보고하고, `hasDevelop`은 `developBranchGuess is not None`으로 정의한다(기존 필드 의미 확장 — 하위호환: develop 존재 시 기존과 동일하게 true).

## D. PEP 440 한계 문서화 (references — 코드 무변경)

- `references/version-schemes.md`: SemVer 절에 "superrelease의 버전 산술은 SemVer 문법 전용 — PEP 440 고유 형식(`1.2.0.dev0`, `.post0`, epoch, 로컬 버전)은 next-version.py가 거부한다(exit 1)" 명시.
- `references/prerelease-and-dev-channel.md`: mutable dev 채널(-SNAPSHOT류)과 next-snapshot이 Python 관례와 비호환임을 명시하고, Python 프로젝트 권장 운용을 기술 — `preRelease.style: none` + 릴리스 시점 bump(파일 버전 = 마지막 릴리스), pre-release가 필요하면 SemVer 문법(`-rc.N`)을 쓰되 PyPI 업로드 시 PEP 440 정규화(`1.2.0rc1`)와 표기가 달라짐을 주의.

## E. init SKILL.md 정합

- **번들 2** (버전 위치 확정): 후보 표 프로즈에 1줄 — "`usable: false` 후보는 위치로 제안하지 말고 감지 사실과 advice(예: maven-project-version → versions-maven-plugin/revision 전환 권장)만 안내하라".
- **번들 1** (모노레포 scope 확정): `monorepo.packages`가 이제 gradle 모듈을 포함함을 반영(별도 프로즈 변경은 최소 — 표 제시 로직은 동일, `buildSystem` 열 언급 1구절).
- **번들 4** (pre-release): pyproject.toml이 versionCandidates에 있으면 "PEP 440 고유 형식은 미지원 — Python 프로젝트는 none 스타일 권장(references 참고)" 1줄 안내.
- **번들 6**: `hasDevelop` 언급을 `developBranchGuess`(감지된 이름) 사용으로 갱신 — M4b 프로즈가 이미 "감지된 통합 브랜치명"이라 자연 연결.
- **지원 범위와 제약** 절: 스캔 감지 대상 목록을 한 줄로 명시(감지 파일 열거 + "libs.versions.toml·gradle 내부 의존성·xml-path는 비감지/후속").

## F. 테스트 (tests/test_scan.py — fixture 기반 단위)

- pom.xml: ① revision property → 정상 regex 후보 ② project version만 → `usable: false` + advice ③ parent version만 있고 project version 없음 → 엔트리 없음 ④ 네임스페이스 있는 pom 파싱.
- VERSION: ① 버전 형태 → 후보 ② 산문 내용 → 엔트리 없음.
- openapi: ① openapi.json → json-path 후보 ② openapi.yaml → regex 후보(들여쓴 info.version) ③ 최상위 `version:` 문서 키 오탐 없음.
- gradle 모노레포: settings include 3형태 해석 + 모듈 gradle.properties/build.gradle 버전 + buildSystem 필드(node 대칭) + suspected 판정.
- branches: develop/development/dev 각각 + 우선순위(develop과 dev 공존 시 develop) + 부재 시 null.
- **골든 무영향 게이트**: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력(전 태스크 공통).

## 제약·검증

- scan.py는 Python 3.9+ 표준 라이브러리만(ElementTree 포함), 읽기 전용, exit 0/2. 기존 리포트 필드는 전부 하위호환(추가만, 제거·의미 축소 없음 — `hasDevelop`은 확장이나 기존 true 조건 포함).
- render 엔진·자산 스크립트·생성 스킬·템플릿 **무변경** — 골든 diff 0.
- init SKILL.md ≤500줄(현재 148). 코드·에러 영어 / 프로즈 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict`.

## 비범위 (후속)

- xml-path location 타입 신설(pom 직접 쓰기) — Maven 수요 확인 후.
- gradle `internalDependencies`(`project(":x")` 파싱), maven multi-module(`<modules>`) 수집.
- libs.versions.toml 감지(오탐 기본값 — 결정 표 근거).
- YAML 정식 파싱, 루트 외 경로의 openapi 문서 탐색(api/ 등).
- 노트 언어 신호(전면 리뷰 A13 — 우선순위 낮음), README·CLAUDE.md 갱신(M4d).

## 예상 태스크 (writing-plans에서 확정)

1. scan_version_candidates 확장(pom·VERSION·openapi + usable/advice) — fixture TDD.
2. scan_monorepo gradle 확장(_gradle_packages + buildSystem 대칭) — fixture TDD.
3. scan_branches developBranchGuess — TDD.
4. references PEP 440 2건 + init SKILL.md 정합(번들 1·2·4·6·지원범위).
5. 최종 검증(전체 스위트 · plugin validate · 골든 diff 0 · 라인 예산).
