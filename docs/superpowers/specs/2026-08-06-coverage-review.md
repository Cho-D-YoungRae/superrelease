# superrelease 커버리지 검토 — 갭 분석 보고서 + 백로그

- 날짜: 2026-08-06
- 상태: 검토 완료 (개선 실행은 별도 작업 — 이 문서의 백로그는 **약속이 아닌 후보 목록**이다)
- 방법: 페르소나 18행 × 지원 차원 11열 매트릭스 데스크 리뷰(레인 5개 병렬) + 합성 레포 3종 인-세션 init 워크스루 + config 조합 완결성·dogfood 마찰·정형 파일 적합성 별도 절. P0 주장 2건은 스크래치 재현으로 확정.
- 검토 태도: **확장 지향(이번 검토 한정)** — 발견 갭은 기본 "지원 후보"로 취급하되, 기존 "지원 약속 금지" 정책은 유지한다. artifact publishing·CI workflow 생성은 하드 경계(백로그 금지, "태그·GitHub Release까지가 superrelease 몫"). 파일·버전모델류 Not-planned(libs.versions.toml, 이중 버전 모델 등)는 재평가 허용.

## 1. 판정 기준 (3층 레이어)

| 판정 | 정의 |
|---|---|
| ✅ 지원 | init이 스캔·질문·안내로 다루고(I✓) 엔진이 수행 |
| 🟡 부분 | 엔진·수동 config로 가능하나 init 미안내, 또는 관행의 일부만 커버 |
| ❌ 미지원 | 엔진 표현 불가(validate 거부 포함) 또는 산술 부재 |
| N/A | 해당 페르소나에 본질적으로 무관(사유 명기) |

레이어 표기: **S**(scan 자동 감지) / **E**(엔진 가능) / **I**(init 안내). 부분·미지원 칸마다 백로그 항목 또는 처분 사유를 붙였다(§3).

열 정의: C1 스캔·인식 / C2 버전 소스 표현력 / C3 버전 모델·scheme / C4 pre-release·dev 채널 / C5 브랜칭·릴리스 경로 / C6 모노레포 / C7 태그·앵커 / C8 노트·체인지로그 / C9 hotfix·유지보수 / C10 backfill·온보딩 / C11 post-release·회수.

## 2. 매트릭스 총괄 (18행 × 11열 = 198칸)

**판정 분포: ✅ 90 · 🟡 84 · ❌ 9 · N/A 15**

| 행 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 | C11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 npm 라이브러리 | ✅ | ✅ | ✅ | 🟡 | ✅ | N/A | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| R2 Python 라이브러리 | ✅ | 🟡 | ✅ | ❌ | ✅ | N/A | ✅ | ✅ | ✅ | 🟡 | 🟡 |
| R3 JVM 라이브러리 | ✅ | ✅ | 🟡 | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R4 Rust crate | ✅ | 🟡 | ✅ | ✅ | ✅ | N/A | ✅ | ✅ | ✅ | ✅ | 🟡 |
| R5 npm workspaces 모노레포 | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 | ✅ | 🟡 | 🟡 | 🟡 | 🟡 |
| R6 백엔드 서비스(Gradle) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| R7 프론트엔드 SPA | 🟡 | ✅ | ✅ | 🟡 | 🟡 | N/A | ✅ | ✅ | N/A | 🟡 | 🟡 |
| R8 풀스택 모노레포 | 🟡 | ✅ | ✅ | 🟡 | ✅ | 🟡 | ✅ | 🟡 | 🟡 | ✅ | 🟡 |
| R9 Flutter 앱 | ❌ | 🟡 | 🟡 | 🟡 | ✅ | 🟡 | ✅ | 🟡 | 🟡 | ✅ | 🟡 |
| R10 iOS 네이티브 | ❌ | 🟡 | 🟡 | 🟡 | ✅ | N/A | ✅ | 🟡 | 🟡 | ✅ | 🟡 |
| R11 Android 네이티브 | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 | 🟡 | ✅ | 🟡 |
| R12 React Native | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | N/A | ✅ | 🟡 | 🟡 | ✅ | 🟡 |
| R13 데스크톱(Electron/Tauri) | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 | ✅ | ✅ | 🟡 |
| R14 Helm 차트 | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 | 🟡 | 🟡 | ✅ | 🟡 | ✅ |
| R15 GitOps/k8s manifest | ❌ | ❌ | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ❌ | N/A |
| R16 태그-only(Go CLI·Terraform) | ❌ | ❌ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡* | 🟡 |
| R17 Python uv/poetry workspace | 🟡 | 🟡 | ✅ | 🟡 | ✅ | 🟡 | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| R18 Maven 멀티모듈 | 🟡 | 🟡 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |

\* R16×C10은 데스크 리뷰 ❌를 워크스루가 🟡로 정정 — backfill 자체는 완주 가능하며, 문제는 "버전 파일을 전혀 쓰지 않는 기능이 versionLocations 관문 뒤에 있다"는 구조(§4.2).

**헤드라인 독해:**
- **라이브러리·웹앱·JVM(R1~R8)은 견고하다.** 특히 R3(JVM)·R6(백엔드)은 설계 원형답게 거의 전 칸 ✅. R1·R5의 npm 계열도 엔진 레벨은 강하고, 갭은 "기존 도구(changesets) 공존"과 노트 관행에 몰려 있다.
- **모바일 4행(R9~R12)은 "엔진은 절반, 안내는 0"이다.** 마케팅 버전 축은 regex 우회로 전부 성립하지만(E✓), 스캔 감지 0건·init 안내 0건에 빌드번호(이중 버전) 축이 엔진에 아예 없다.
- **❌ 9칸의 뿌리는 셋뿐이다**: ① versionLocations 필수 규칙(태그-only 표현 불가 — R15·R16), ② 이중 버전 모델 부재의 극단 케이스(R9~R10 스캔·인식 0), ③ pom 직접 쓰기 미지원(R18 independent — 이건 명문화된 의도적 제외).
- N/A 15칸 중 8칸이 R15(GitOps) — "버전 소스가 아닌 전파 대상 레포"라는 진단 자체가 정확하며, 필요한 것은 기능이 아니라 우아한 거절 문구다.

## 3. 그룹별 상세 — 🟡/❌/N/A 칸의 근거와 처분

✅ 칸은 생략한다(판정 근거는 §2 총괄표와 레인 판정 기준으로 갈음). 각 칸: 근거 → **처분**(백로그 번호 또는 제외 사유). 백로그 상세는 §8.

### 3.1 오픈소스 라이브러리 (R1~R5)

- **R1×C4** 🟡 (E✓ counter / dist-tag 없음): `-rc.N` counter와 GH Release `--prerelease`는 지원하나 npm dist-tag 채널(latest/next/beta)은 publish 시점 레지스트리 조작이라 어디에도 없음 → **B-21** (기록+스니펫 안내만) / 실행은 **아키텍처 경계**.
- **R1×C10** 🟡: semantic-release/release-please 등 기존 자동화 설정을 스캔이 무감지 — 이중 자동화 경고 없이 init 통과 → **B-6**.
- **R1×C11** 🟡: npm deprecate는 안내 문구만(실행은 경계 — 올바름). init 라이브러리 프리셋이 SNAPSHOT+next-snapshot을 무조건 선제안하는 JVM 편향 → **B-20**.
- **R2×C2** 🟡: 정적 pyproject는 지원. `__init__.py __version__` 이중 기록은 E✓·I✗, `dynamic = ["version"]`(setuptools-scm)은 버전 파일이 없어 표현 불가 → **B-23**(태그-SSOT 모드, L). regex 전 매치 치환의 `[tool.*] version =` 오염 위험 → **B-3**.
- **R2×C4** ❌: PEP 440(`rc1`·`.dev0`·`.post1`)은 SEMVER_RE 불일치로 exit 1. init이 "미지원·none 권장" 한 줄 안내 + `-rc.N` 우회를 문서화하고 있어 관리되는 갭 → **B-22**(P2).
- **R2×C10** 🟡: towncrier 운용 레포와 조각 소비 주체 충돌 무감지 → **B-6**.
- **R2×C11** 🟡: PyPI yank 안내만(경계 — 올바름). 처분: 경계 유지.
- **R3×C3** 🟡: japicmp/kotlin-bcv는 config 기록+안내까지만 — 생성된 release 스킬이 compatCheck 필드를 한 번도 참조하지 않는 dead 필드 → **B-24**.
- **R3×C6** 🟡: gradle 내부 의존성 자동 감지 없음(internalDependencies는 node 전용), libs.versions.toml 미지원 — SKILL.md에 명문화된 제외. 처분: **문서화된 범위 제외 유지**(dependents 수동 선언으로 E✓).
- **R4×C2** 🟡: **version.py set이 Cargo.lock을 갱신하지 않음**(sync는 package-lock.json 전용) — 릴리스 커밋·태그에 구버전 lockfile 박제 → **B-9**. `[dependencies.foo]`의 `version =` 라인 오염 위험 → **B-3**.
- **R4×C11** 🟡: 회수 안내 예시에 cargo yank 미명명 → **B-19**(문구 묶음).
- **R5×C4** 🟡: R1×C4와 동일 → **B-21**.
- **R5×C6** 🟡: dependents 전파 시 내부 의존 범위 문자열(`"^1.2.0"`) 미갱신 — workspace:* 레포는 무영향 → **B-25**(P2).
- **R5×C8** 🟡: **패키지 디렉터리별 CHANGELOG.md 누적**(changesets 관행·npm tarball 동봉)이 4목적지에 없음 — 루트 changelog뿐 → **B-10**.
- **R5×C9** 🟡: trunk independent의 유지보수 라인은 validate 거부(gitflow hotfix는 지원). 처분: **의도적 제외 유지**(다중 메이저 동시 유지 npm 모노레포는 니치) — 수요 증거 시 재검토(B-26).
- **R5×C10** 🟡: **changesets 공존·이주 무안내** — 워크스루로 실증(§4.3) → **B-6**(최우선 대상).
- **R5×C11** 🟡: 경계 유지.

### 3.2 웹앱 (R6~R8)

- **R6×C9** 🟡: gitflow hotfix는 머지 후 태그 중단 자동 감지가 없고 release preflight 검색이 `head:release/` 한정 → **B-27**(P2).
- **R6×C11** 🟡: 회수 안내 어휘가 npm/PyPI뿐 — 서비스형(컨테이너·배포 롤백) 예시 부재 → **B-19**.
- **R7×C1** 🟡: 연속 배포 신호(vercel.json·netlify.toml) 미감지·미안내 → **B-28**(P2). 플랫폼 대시보드 설정은 원리적 감지 불가(부분 경계).
- **R7×C4** 🟡: immutableId 어휘가 백엔드·패키지 중심(spring/docker/npm-dev) — SPA 관행(Sentry release류) 부재 → **B-19**.
- **R7×C5** 🟡: **trunk×release-pr 첫 릴리스(태그 0개)는 머지 후 재개 미감지** — "첫 태그까지 수동"이 reference에 명문. 보호 main+무태그 신규 도입 레포에 정통 타격 → **B-13**. trunk×release-pr×tagless 거부는 처분: 의도적 제약 유지(대안 2개 존재).
- **R7×C10** 🟡: **0.0.0 placeholder 버전을 "기존 버전 있음"으로 취급** — 시작 버전 리셋 질문(0.1.0 vs 1.0.0)이 "기존 버전 없음"에만 발화 → **B-12**.
- **R7×C11** 🟡: 정적 배포 롤백 어휘 → **B-19**.
- **R8×C1** 🟡: 공유 gradle.properties 커스텀 키(apiVersion 등) 자동 감지 불가 — walkthrough 2가 한계 명문(질문으로 보완됨) → **B-29**(P2, `*Version` 패턴 후보 나열).
- **R8×C4** 🟡: config·스킬·골든은 scope별 pre-release 차등을 완전 지원 — init 번들 4 문구에만 scope별 차등 질문 규정 부재 → **B-19**.
- **R8×C6** 🟡: **changed-packages가 scope path 밖 변경(루트 빌드 설정·buildSrc·공유 코드)을 어느 scope에도 귀속 못 함** — 전 모듈 영향 변경의 릴리스 후보 미탐 → **B-11**(watchPaths).
- **R8×C8** 🟡: 노트 설정(언어·독자·어조)이 전 scope 공통 1회 — FE/BE 차등은 config 손편집으로만(M2 범위 결정으로 문서화, 동작은 함) → **B-19**(선택 질문 문구).
- **R8×C9** 🟡: R5×C9와 동일 — 의도적 제외 유지.
- **R8×C11** 🟡: **B-19**.

### 3.3 모바일/데스크톱 (R9~R13)

이 그룹의 코어 긴장 두 개가 4행에 공통으로 걸린다:
- **G1 이중 버전 모델**: versionCode/CFBundleVersion/pubspec `+N`은 scope당 단일 버전값 전제(verify가 전 위치 동일 강제)에 막혀 등재 불가, 단조증가 정수 산술도 없음 → **B-7** (C2/C3/C9 전반의 처분).
- **G2 스캔 사각지대**: pubspec.yaml·Info.plist·xcconfig·build.gradle versionName·tauri.conf.json 전부 미감지(스캔은 레포 루트만, 하위 디렉터리 미탐) → **B-8** (C1 전반의 처분).

행별 추가 사항만 적는다:

- **R9(Flutter)×C3** 🟡: full-string 캡처 시 **next-version.py가 `1.2.3+45 → 1.2.4`로 build metadata를 무경고 드롭**(stderr 0바이트, exit 0 — 워크스루 실측) → **B-4**. 마케팅만 캡처 시 +45는 보존되나 영구 동결.
- **R9~R12×C4** 🟡: 스토어 베타 관행(TestFlight/Play 트랙)은 빌드번호+트랙 기반이라 버전 qualifier 모델 밖. iOS 마케팅 버전 필드는 qualifier 표기 자체가 거부됨 — "모바일은 none 권장" 안내조차 없음(PEP 440 안내와 같은 패턴이 필요) → **B-30**(P2).
- **R9~R12×C8** 🟡: 스토어 what's new(fastlane `metadata/<locale>/changelogs/<versionCode>.txt`)는 경로 규약·플레인텍스트·versionCode 파일명이 release-file(`{path}{version}.md`)과 전부 불일치 → **B-31**(P2, 파일 규약 일반화 — 업로드 실행은 경계). §7.2 참조.
- **R9~R13×C11** 🟡: 스토어(롤백 불가·단계 출시 중단)·업데이터 피드 회수 어휘 부재 → **B-19**.
- **R10(iOS)×C2** 🟡: xcconfig `MARKETING_VERSION = 1.2.3`은 properties-key와 정확 호환(즉시 사용 가능). Info.plist는 다중라인 regex로 표현 가능하나 레시피 부재, `$(MARKETING_VERSION)` 변수 참조 프로젝트는 xcconfig가 SSOT → **B-8** 레시피에 포함.
- **R11(Android)×C1** 🟡: gradle 빌드시스템은 감지되나 `^version =` 패턴이 android 블록 `versionName`에 불일치 — 후보 0건 → **B-8**.
- **R12(RN)×C2** 🟡: 마케팅 버전 3중 동기화(package.json+iOS+Android)는 versionLocations 다중 파일 sync의 강점이 정확히 적용됨(E✓) — 빌드번호 2종만 공백 → **B-7**·**B-8**.
- **R13(데스크톱)×C1/C2** 🟡: tauri.conf.json은 순수 JSON이라 json-path로 즉시 표현 가능 — 스캔·안내만 부재 → **B-8**. Cargo.lock 동기화 → **B-9**.
- **R13×C6** 🟡: Cargo workspace 멤버 순회 없음 → **B-8**(동반 검토).
- **R13×C8** 🟡: latest.yml·appcast.xml은 서명·크기 메타를 요구하는 **배포 피드 아티팩트**(전용 도구 생성물) — 처분: **아키텍처 경계**(GH Release 본문은 이미 피드 노트로 활용 가능).

### 3.4 인프라/정형 파일 (R14~R16)

- **R14(Helm)×C1** 🟡: Chart.yaml `version`(차트)만 감지 — `appVersion`은 미감지이며 **별개 버전 스트림**(같은 scope에 넣으면 verify 영구 MISMATCH). "버전 소스 vs 전파 대상" 구분 안내 필요 → **B-8**(usable:false/advice 선례 재사용).
- **R14×C2** 🟡: 관행 구조에선 안전하나 `^version:` 다중 매치 시 전 매치 치환 위험 → **B-3**.
- **R14×C6** 🟡: charts/* 다중 차트 스캔 부재 → **B-8**.
- **R14×C7** 🟡: chart-releaser 관행 태그 `<chart>-{version}`은 tag.format으로 표현 가능 — init이 관행을 몰라 기본 제안이 어긋남 → **B-32**(P2).
- **R14×C8** 🟡: **Artifact Hub `artifacthub.io/changes`(Chart.yaml YAML annotation)** — 노트의 기계 소비자인데 현 엔진(md 목적지·regex 단일 캡처)으로 표현 불가 → **B-33**(P2, L — 니치·수요 확인 전 보류). §7.2 참조.
- **R14×C10** 🟡: cr 태그 포맷을 config에 넣지 않으면 backfill·앵커가 기존 태그를 놓침 → **B-32**에 흡수.
- **R15(GitOps)×C1/C2/C10** ❌: 버전 소스가 아닌 **전파 대상** 레포 — newTag/image.tag를 versionLocations에 넣으면 전 매치 치환 오염 + 환경별 오버레이(의도적으로 서로 다른 버전)와 verify 전제가 정면 충돌. **지원이 아니라 진단·거절이 정답** → **B-34**(P2: "이 레포는 버전 소스가 아님 — 앱 레포에 설치하라" 문구), 오염 가드는 **B-3**. 나머지 7칸 N/A(버전 소스 아님).
- **R16(태그-only)×C2** ❌: versionLocations 필수 → 버전 파일 없는 레포는 config 표현 불가(재현 확정: `scopes[0].versionLocations is required`). VERSION 파일 항복은 **이중 SSOT**(Go proxy·goreleaser·ldflags 전원 태그만 소비 — VERSION은 superrelease 전용 사본, 드리프트를 잡아줄 소비자 없음) → **B-23**(태그-SSOT 모드, L — 수요 확인 후).
- **R16×C1** ❌: go.mod·*.tf 인식 전무 → **B-8**(단독으로는 반쪽 — B-5·B-23과 묶어야 유효).
- **R16×C3** 🟡: Go v2+ 메이저 승급의 module path `/vN` 개정은 표현·안내 불가 → **B-19**(문서 한 줄).
- **R16×C4~C9** 🟡: 축 자체는 완비(counter·trunk·moving major·maintenanceLines 전부 관행 정합)인데 C2 게이트로 도달 불가 — B-23 해소 시 대부분 ✅ 승격 예상.
- **R16×C10** 🟡(워크스루 정정): "기존 레포+버전 후보 0건" 분기가 SKILL.md에 미정의(버전 파일 생성 절차는 신규 레포 제안 모드 문단 내부에만) — 하드 블록이 아니라 **진행자별 비결정성**(0.1.0 시드로 태그 이력과 역행하는 사고 포함) → **B-5**. backfill 자체는 항복 후 완주 확인.
- **R16×C11** 🟡: Go `retract` 지시어(태그-only 생태계의 공식 회수 수단) 부재 → **B-19**.

### 3.5 추가 모노레포 (R17~R18)

- **R17(uv/poetry workspace)×C1/C6** 🟡: `[tool.uv.workspace]` members·내부 의존성(workspace = true) 감지 전무 — independent 온보딩의 두 축(scope 표·dependents 제안)이 모두 빈손. node·gradle과의 감지 비대칭이 가장 큰 그룹 → **B-8**.
- **R17×C2** 🟡: 멤버 pyproject regex는 엔진 완전 지원. poetry 멀티라인 의존성 테이블(`version = "^1.2"`) 오염 위험 → **B-3**.
- **R17×C4** 🟡: PEP 440 축(R2와 동일) + 번들 4 안내 트리거("pyproject가 버전 후보에 있으면")가 workspace-only 루트에선 미발동 위험 → **B-22**·**B-19**.
- **R17×C9** 🟡: trunk independent maintenanceLines 거부 — 의도적 제외 유지.
- **R17×C11** 🟡: next-snapshot이 PEP 440 invalid — 권장 경로(none)는 완전 동작. 처분: 문서화된 우회 유지.
- **R18(Maven 멀티모듈)×C1** 🟡: pom `<modules>` 미파싱(gradle include와 비대칭) — fixed+`<revision>` 관행이면 루트 후보는 잡혀 실해 완충 → **B-8**(힌트 수준).
- **R18×C2** 🟡: 루트 `<revision>` flatten(fixed)은 완전 지원. 모듈별 pom `<version>` 독립 구조는 regex로 parent/dependency와 구분 불가 + xml-path 미지원 **명문 제외** — usable:false advice(versions-maven-plugin/revision 전환 권장) 흐름 존재. 처분: **정책 종결**.
- **R18×C6** ❌: independent는 C2 선행 차단으로 불성립(fixed는 단일 흐름이라 모노레포 기능 불요). 처분: xml-path 배제 정책에 종속 — **종결**.
- 참고(확신도 낮음): fixed×gitflow 조합은 validate 통과·렌더 정상으로 판정했으나 지원 범위 문구("단일+independent")에 fixed 명시가 없고 골든도 없다 → **B-18**(골든 묶음)에서 함께 처리.

## 4. init 워크스루 시뮬레이션 요약 (3종)

합성 레포는 스크래치패드에 격리, 플러그인 레포 무수정, 발견 버그는 백로그 기록만.

### 4.1 Flutter 앱 (R9)

- 시나리오: pubspec `version: 1.2.3+45`, 태그 v1.2.2·v1.2.3, conventional 커밋, CHANGELOG 없음, 1인 개발·trunk·direct-push.
- 결과: **스캔 버전 후보 0건 → 패스트트랙 표 구성 불가** → 번들 2 "스캔 후보를 표로 제시" 절차가 빈 표에서 공전. 성격 추천·pubspec regex 작성·이중 버전 갈림길 설명 전부 실행 주체의 임기응변(SKILL.md 지시 밖). regex 우회 자체는 완전 동작: 마케팅만 캡처 시 get/set/verify 라운드트립 정상, +45 보존(단 영구 동결). 풀스트링 캡처 시 `--bump patch`가 `1.2.4` 출력(stderr 0바이트) — **+45 무경고 소실 실측**. 렌더 6파일·자가검증 exit 0·리허설(anchor→범위→minor 제안 1.3.0) 정상.
- 판정 검증: scan 0건 확인 / regex 우회 성립 확인(단, 잘못된 캡처 선택도 동일하게 "성립"해 보이는 함정) / G3(+메타 드롭) 확인 / G1(빌드번호 미커버 — 렌더 툴킷 전체 grep 0건) 확인.
- 파생 발견: 태그마저 없는 Flutter 레포였다면 신규 레포 제안 모드가 pubspec이 이미 있는데 VERSION 생성을 제안하는 어긋난 경로(→ B-5 문구에 "파일은 있는데 감지 못한 케이스" 포함). cosmetic: preflight 번호 결번(4→6), --check 동일 경로 create+skipped 병기, mergePolicy unknown 기입 지침 부재, "Phase 3 전 파일 생성 금지" 규칙과 config.json 작성 절의 위치 모순(→ B-19).

### 4.2 태그-only Go CLI (R16)

- 시나리오: go.mod + `var version = "dev"`(ldflags 관례) + goreleaser + 태그 v1.4.0·v1.5.0 + 태그 push=배포 CI, CHANGELOG 없음.
- 결과: 모드 감지는 "태그·커밋 풍부"라 **최초 init**으로 낙착 — 버전 파일 생성 절차는 신규 레포 제안 모드 문단 내부에만 있어 **미정의 분기 실재 확인**(하드 블록 아닌 표류: 시드 버전 지침이 "0.1.0 등"뿐이라 v1.5.0 이력과 역행 위험 — "최신 태그에서 시드"는 이번 워크스루의 창작). 1차 희망("태그가 유일한 진실")은 선택지에도 미지원 열거에도 없음(침묵). (a) 빈 versionLocations → 즉시 거부(원문 확보). (b) `var version = "dev"` regex 등록 → **--check·verify 전부 통과 후 첫 릴리스 3단계에서 `not a valid SemVer version: dev`로 폭발** — verify는 위치 간 일치만 검사, 스킴 유효성 미검사. preflight 중단 감지도 "dev" 비교 불능으로 무력. (c) VERSION=1.5.0 항복 → 렌더 8파일·자가검증 정상, **backfill은 태그 구간 산출·멱등·커밋까지 흠 없이 완주**.
- 판정 검증: versionLocations 필수 차단 확인 / C10 미정의 분기 확인(성격 정정: 차단→표류) / 이중 SSOT 긴장 확인(이 생태계 소비자 전원이 태그만 읽음) / "backfill 진입 불가"는 **부분 반박** — 정확한 진술은 "버전 파일을 전혀 쓰지 않는 기능이 버전 파일 도입을 강제하는 관문 뒤에 있다".

### 4.3 changesets 운용 pnpm 모노레포 (R5)

- 시나리오: @acme/core 1.1.0·@acme/ui 0.4.0(workspace:^ 의존), 펜딩 changeset 1개, changesets action CI(push:main 트리거), per-package CHANGELOG 2개, changesets 관례 태그.
- 결과: 기계 파이프라인은 무결점(스캔 패키지·내부 의존성 정확, 렌더·verify·changed-packages 전부 정상). **기존 태그 `@acme/core@1.1.0`이 재태깅 없이 그대로 anchor로 해석됨 — 바이트 호환 실측 확인**(이주 친화의 백미). 반면: `.changeset/`은 스캔 리포트에 0비트(scan_changelog는 changelog.d만), **펜딩 조각의 운명 무언급**(사람의 bump 의도 선언이 조용히 증발), **changesets action 이중 자동화 무경고**(push:main 트리거라 tagTriggerCandidates 시야 밖 — superrelease 릴리스 커밋이 main에 닿으면 action이 중복 bump PR 생성, 머지 시 같은 태그 네임스페이스에서 두 시스템이 경합), per-package CHANGELOG 1지망 표현 불가(차선: 루트 changelog+github-release, 기존 파일 화석화 고지도 임기응변), scoped 태그가 byPattern 전부 0·other로 뭉개져 태그 관례 추천 근거 공백, backfill 오발동(이력이 per-package에 완비인데 루트 기준 "없음"으로 제안).
- 신규 발견(데스크 리뷰에 없던 것): **npm publish 공백** — changesets는 버전 관리기이자 배포기였는데, action 제거 시 발행 경로가 사라지는 것에 대해 init이 묻지도 안내하지도 않음("태그 push 트리거 publish로 전환하라" 한 단락 필요 — 실행은 경계 유지).

## 5. config 조합 완결성 (기준선 ii)

골든 22트리가 커버하는 조합 외 validate 침묵 지대를 점검했다. **P0 2건은 스크래치 재현으로 확정.**

| 조합 | 분류 | 근거·재현 | 처분 |
|---|---|---|---|
| **releasePath 오타(닫힌 집합 아님)** | 침묵-위험 **P0 재현 확정** | `"release_pr"` → validate 통과(exit 0), 생성 release 스킬은 release-pr flavor(`{{else}}` 분기)로 렌더되며 `.superrelease/templates/release-pr-body.md`를 참조하는데 **그 템플릿은 manifest 게이트(`== "release-pr"`) 불일치로 미렌더** — 망가진 툴킷 침묵 생성. branching은 닫힌 집합인데 비대칭 | **B-1** |
| **postRelease next-snapshot × qualifier null** | 침묵-위험 **P0 재현 확정** | validate 통과 → 생성 스킬에 `--qualifier ` (값 없음) 명령 박제 → 실행 시 argparse `expected one argument`(exit 2). 빈 문자열 우회 시 bare 버전 복귀 → preflight 중단 감지 상시 오탐 | **B-2** |
| movingMajorTag × independent | 침묵-위험 | release-monorepo가 `git tag -f v<major>` 비네임스페이스 — 두 scope가 같은 major면 충돌·교차 force-push. 골든 전무 | **B-15** |
| movingMajorTag × calver/headver | 침묵-무의미 | 단일 레포 스킬은 스킴 무관 렌더(`v2026` 유동 태그 force-push 가능). 모노레포판만 자체 가드 보유 | **B-15** |
| gitflow × maintenanceLines | 침묵-위험 | 둘 다 validate 통과 — manifest의 hotfix 이중 entry가 같은 목적지에 렌더, gitflow flavor만 남고 구버전 라인 패치 기대가 소리 없이 증발 | **B-14** |
| calver/headver scope × pattern null | 침묵-지연실패 | pattern 필수 규칙이 bundle에만 — scope는 통과 후 릴리스 시점 exit 2 | **B-16** |
| 비-independent × scopes ≥2 / scope name·tag.format 중복 | 침묵-위험 | ctx.scope=scopes[0]이라 둘째 scope는 유령 / 유일성 비검증 — anchor 교차 오염 | **B-17** |
| release-file × perReleasePath null | 침묵-위험(경미) | 명시 null이면 빈 문자열 → 루트에 `{version}.md` 생성 | **B-17**(묶음) |
| releaseCommitFormat placeholder | 침묵-위험(경미) | `{scope}` × 단일 레포 = 리터럴 잔존 / independent × `{scope}` 없음 = 커밋 구분 불가 | **B-17**(묶음) |
| language·destinations·mergePolicy 비검증 | 침묵-안전(경미) | 임의 문자열이 조용히 특정 분기로 렌더 | **B-17**(묶음) |
| github.release × 혼합 tagless 모노레포 | 과잉 거부 | tagless scope 하나라도 있으면 전면 거부 — tagged scope만 GH Release 원하는 혼합 구성 불가 | **B-35**(P2, 수요 확인 전 보류) |
| devChannel × style none / anchor.type ref × backfill / fragment × bundle / fixed × dependents | 침묵-무의미·안전 | devChannel·anchor.type은 생성물이 미소비(장식 필드) — 설계 의도 문서화됨 | 처분 없음(fixed의 dependents 무시는 init 프로즈 한 줄 — B-19) |
| 골든 공백 | — | trunk×bundle, independent×fragment/release-file, maintenanceLines×release-pr hotfix, backfill×gitflow, 단일 gitflow-tagless hotfix, fixed×gitflow | **B-18** |

## 6. dogfood/실사용 마찰 (기준선 iii)

해결 완료(백로그 아님): plugin.json 미감지(v0.2.0 출하) · resume squash 하드코딩(mergePolicy 분기) · json-path 재포맷(surgical write) · 마커 버전 churn(M4b-2 근본픽스, v0.3.0에서 0바이트 churn 실증).

미해결 → 백로그:
- **M5 최종 리뷰 Low 6건 적체**: 혼합태그 per-scope skip 안내 부재·tagless 미게이트 프로즈(3스킬 공유) → **B-36**; docstring 3-모드·bundleNotesGuess 8자리 오탐·골든 churn 주의 → **B-19**.
- **init gitflow 태그 프로즈 상충** 잔존("정식 사이클→태그" vs "태그 선택사항") → **B-19**.
- **실전 검증 조합의 협소함**: end-to-end 실적은 단일 조합(trunk×release-pr×semver×changelog+github-release) 3회뿐 — gitflow·모노레포·hotfix·backfill·bundle·calver/headver·fragment·tagless·direct-push·counter는 골든(렌더 스냅샷)만, 실 릴리스 0회. v0.1.0 마찰 3건 전부 실사용에서만 발견된 전례 → **B-37**(v0.4.0 릴리스로 [Unreleased] 소진 + 비-dogfood 조합 실전 1회).
- gh 이중 계정 전환: 환경 특이 운영 절차로 문서화됨 — 백로그 제외.

## 7. 정형 파일(YAML) 적합성 종합 — 인터뷰 검토 항목 5

### 7.1 (5a) 버전 위치로서의 정형 파일 — 결론: **엔진은 이미 되고, 스캔·안내가 없다**

flat YAML(pubspec `version:`, Chart.yaml `version:`)·xcconfig·tauri.conf.json(JSON)·versionName은 전부 기존 3타입(regex/properties-key/json-path)으로 표현 가능함을 워크스루·데스크 리뷰로 확인했다. 진짜 갭은 포맷이 아니라 3가지다:
1. **스캔 사각지대**(B-8) — 후보 0건으로 시작하는 온보딩.
2. **regex 전 매치 치환의 오염 위험**(B-3) — YAML·TOML의 동일 키 다중 출현(의존성 테이블, 다중 이미지) 시 무증상 오염. get/verify는 첫 매치만 읽어 탐지 불가(비대칭). scan의 openapi 단일 매치 가드 철학을 엔진에도.
3. **구조적 YAML 경로(json-path의 YAML판)는 미지원** — 단 위 1·2가 해소되면 실수요는 얇다(flat 키가 관행의 대부분). 별도 백로그 없이 B-3·B-8의 결과를 보고 재평가.

이중 버전(빌드번호)은 파일 포맷 문제가 아니라 **버전 모델 문제**로 분리 확정(B-7).

### 7.2 (5b) 노트 포맷으로서의 정형 파일 — 결론: **md-only로 충분하되, 좁은 재정의 2건**

판정 기준(기계 소비자 존재)으로 전수 평가한 결과:

| 기계 소비자 | 판정 |
|---|---|
| GitHub Release body API 소비(Renovate 등) | **현 목적지로 충분** — 이 생태계에선 md가 곧 기계 포맷 |
| keep-a-changelog 파서 | 단일 레포: 충분(현 템플릿이 KaC 준수) / 모노레포 `## scope@ver` 헤딩은 KaC 규약 밖(실소비자 희박) → 트레이드오프 명문화만(B-19) |
| GitLab식 YAML 조각 | fragment는 towncrier식 md 조각 — 외부 정형 계약 없음, 해당 없음 |
| Sparkle appcast / electron-updater latest.yml | **아키텍처 경계** — 노트가 아니라 서명·크기 메타를 담는 배포 피드(전용 도구 생성물) |
| fastlane/F-Droid 스토어 changelog | **부분 갭** — 경로 규약·플레인텍스트·versionCode 파일명이 release-file과 불일치 → B-31(파일 규약 일반화로 좁게, 수요 확인 후) |
| Artifact Hub `artifacthub.io/changes` | **정형 산출물 갭(니치)** — Chart.yaml에 YAML 리스트 주입 필요, 현 엔진 불가 → B-33(보류) |

**종합**: "범용 YAML/JSON 노트 포맷 추가"는 정답이 아니다 — 필요한 곳은 각자의 경로·필드 규약이 본체라 범용 포맷으로 해결되지 않고, 나머지는 md를 그대로 소비한다. 갭은 release-file의 **파일 규약 일반화**(파일명 패턴·확장자·포맷)로 좁게 재정의하고 페르소나 수요 확인 후에만 연다.

## 8. 백로그 (P0 → P2, 약속 아닌 후보 목록)

규모: **S** = config 분기·validate 규칙·스킬 문구 / **M** = 스크립트·렌더·scan 변경 / **L** = 신규 스킬 asset·새 실행 모델.

### P0 — 정합성 위험 (재현 확정 2 + 오염 클래스 1)

| # | 항목 | 규모 | 근거 |
|---|---|---|---|
| B-1 | validate: `releasePath` 닫힌 집합(direct-push/release-pr) 검증 | S | 오타 → 망가진 툴킷 침묵 렌더(§5 재현). branching과 비대칭 |
| B-2 | validate: `postRelease: next-snapshot` ⇒ `preRelease.style: mutable` + qualifier 필수 | S | 릴리스 시점 argparse 사망 또는 중단 감지 상시 오탐(§5 재현) |
| B-3 | version.py **regex 다중 매치 가드** — set 전 매치 치환·get/verify 첫 매치의 비대칭을 단일 매치 강제(또는 다중 시 fail)로 | M | 4개 페르소나군에서 독립 발견(Cargo deps·pyproject tool 섹션·poetry 테이블·k8s 다중 이미지) — 조용한 파일 오염 + 탐지 불가 |

### P1 — 흔한 관행 마찰 (온보딩·정합 축)

| # | 항목 | 규모 | 근거 칸 |
|---|---|---|---|
| B-4 | next-version.py build metadata(`+N`) 무경고 드롭 → 경고 또는 거부 | S | R9×C3 실측(스토어 키 조용한 소실) |
| B-5 | init "기존 레포 + 버전 후보 0건" 분기 정의 — 버전 파일 도입 확인 절차를 신규 모드 밖으로 일반화 + 시드 버전은 최신 태그 기준(0.1.0 역행 방지) + "파일은 있는데 감지 못한" 케이스 문구 | S | R16×C10·R9 워크스루 양쪽 강타 — 모바일·Go·인프라 전체의 입구 |
| B-6 | **기존 릴리스 자동화 감지 + 공존·이주 안내** — `.changeset/`(+펜딩 조각 수)·semantic-release·release-please·towncrier 감지, 이중 자동화(CI action) 경고, 펜딩 조각 처리·per-package CHANGELOG 화석화 고지, "발행 경로 전환(태그 트리거 publish)" 안내 한 단락(실행은 경계) | M | R5 워크스루 — 태그 경합은 페르소나 한정 치명 |
| B-7 | **모바일 이중 버전 모델**(마케팅+빌드번호) 1급 지원 검토 — scope 보조 buildNumber location + 단조증가 산술(기존 MICRO 산술 재사용 가능성) | M~L | R9~R12×C2/C3/C9 공통 코어. 파일·버전모델류 재평가 허용 대상 |
| B-8 | **스캔 확장 에픽**(분할 가능): pubspec.yaml·xcconfig·build.gradle versionName·tauri.conf.json·Chart.yaml appVersion(usable:false+advice)·charts/*·uv/poetry workspace(members+내부 의존성)·pom `<modules>` 힌트·go.mod/tf 인식·하위 디렉터리 후보·scoped 태그 byPattern 클래스 + references 레시피(Info.plist 다중라인 regex 등) | M | 전 그룹 C1 — "엔진은 되는데 입구가 없다"의 입구 |
| B-9 | Cargo.lock 동기화(sync_package_lock의 Cargo.lock판) | M | R4·R13×C2 — 릴리스 커밋에 구버전 lockfile 박제 |
| B-10 | per-package CHANGELOG.md 노트 목적지 | S~M | R5×C8 — changesets 관행·npm tarball 동봉 |
| B-11 | changed-packages scope별 watchPaths(공유 경로 감시) | M | R8×C6 — 전 모듈 영향 변경 릴리스 누락 축 |
| B-12 | placeholder(0.0.0) 감지 시 시작 버전 리셋 질문 | S | R7×C10 |
| B-13 | trunk×release-pr 첫 릴리스(태그 0) 머지 후 재개 감지 — gitflow가 이미 쓰는 머지된 release/* PR 검색 재사용 | S | R7×C5 |
| B-14 | validate: gitflow × maintenanceLines 거부(hotfix 이중 entry shadowing 해소) | S | §5 |
| B-15 | movingMajorTag 가드: semver 전용 + independent 거부(네임스페이스 규약 정의 전까지) | S | §5 |
| B-16 | validate: calver/headver scope ⇒ scheme.pattern 필수 | S | §5 |
| B-17 | validate 묶음: 비-independent scopes=1 강제 · scope name/tag.format 유일성 · release-file⇒perReleasePath 필수 · releaseCommitFormat placeholder · language/destinations/mergePolicy 닫힌 집합 | S | §5 |
| B-18 | 골든 공백 채우기: trunk×bundle · independent×fragment/release-file · maintenanceLines×release-pr hotfix · backfill×gitflow · 단일 gitflow-tagless hotfix · fixed×gitflow(+지원 범위 문구에 fixed 명시) · python regex·maven revision 대표 케이스 | S | §5·R17/R18 |
| B-19 | 프로즈·문서 묶음(S 다발): 회수 어휘 확장(cargo yank·Go retract·스토어 롤포워드·업데이터 피드·컨테이너) · gitflow 태그 프로즈 상충 정리 · KaC 모노레포 헤딩 트레이드오프 · fixed의 dependents 무시 명시 · 번들4/5 scope별 차등 문구 · immutableId SPA 어휘 · Go /vN 문서 · mergePolicy unknown 지침 · Phase 3 문구 모순 · preflight 결번·--check 병기 cosmetic · docstring 3-모드 · bundleNotesGuess 오탐 · PEP 440 안내 트리거 보강 | S | 전 그룹 |
| B-20 | init 라이브러리 프리셋의 SNAPSHOT+next-snapshot 기본을 JVM 한정 분기(npm·Rust·Python은 none 기본) | S | R1×C11 |
| B-36 | 혼합태그 모노레포 프로즈 게이트(derived.allTagEnabled + per-scope skip 안내 + tagless 미게이트 "태그명" 프로즈 3스킬) | M | M5 리뷰 Low ①④ |
| B-37 | dogfood 확장: v0.4.0 릴리스로 [Unreleased] 소진 + 비-dogfood 조합(gitflow 모노레포 등) 실전 end-to-end 1회 | 검증 활동 | §6 — 골든만으로는 절차 결함이 안 잡힌 전례 |

### P2 — 니치·수요 확인 후

| # | 항목 | 규모 |
|---|---|---|
| B-21 | npm dist-tag 채널 config 기록+스니펫 안내(실행 없음) | S |
| B-22 | PEP 440 pre-release 산술(rc1·.dev0·.post1) | M~L |
| B-23 | 태그-SSOT(버전 파일 없는) 레포 실행 모델 — versionLocations 선택화+태그 읽기 | L |
| B-24 | compatCheck dead 필드 → release 스킬에서 실행 권고·bump 근거 반영 | S |
| B-25 | dependents 전파 시 내부 의존 범위 문자열 갱신 옵션 | M |
| B-26 | independent scope별 유지보수 라인 hotfix | L |
| B-27 | hotfix 머지 후 태그 중단 감지(preflight 검색 확장) | S |
| B-28 | 연속 배포 신호(vercel.json 등) 감지+태그 의미 안내 | M |
| B-29 | 공유 properties `*Version` 패턴 키 후보 나열 | M |
| B-30 | 모바일 dev 채널 안내: "iOS는 qualifier 불가 → none 권장" 한 줄 + immutableId 모바일 어휘 | S |
| B-31 | release-file 파일 규약 일반화(파일명 패턴·확장자·플레인텍스트) — fastlane/F-Droid 대응, 모바일 수요 확인 시 P1 승격 | M |
| B-32 | Chart.yaml 감지 시 chart-releaser 태그 포맷 선두 제안(+backfill 헤딩 표기) | S |
| B-33 | Artifact Hub `artifacthub.io/changes` annotation 목적지 | L |
| B-34 | GitOps/전파-대상 레포 진단·우아한 거절 문구 + 앱 레포 릴리스 요약에 전파 안내 스니펫(자동화 없음) | S |
| B-35 | github.release × 혼합 tagless 과잉 거부 완화 | M |

## 9. 명시적 제외 (처분 종결)

| 항목 | 사유 |
|---|---|
| artifact publishing 일체(npm/PyPI/crates publish, Sonatype 스테이징, 스토어 업로드, 이미지 push, helm push) | **아키텍처 경계** — "superrelease는 태그·GitHub Release까지, publishing은 CI 몫". 안내 문구는 스킬에 유지 |
| CI workflow 생성·수정, GitOps 리포 커밋 자동화, 배포 피드(appcast/latest.yml) 생성 | 동일 경계 — 배포 비개입 |
| 레지스트리 회수 실행(deprecate/yank/retract), 스토어 콘솔 조작(단계 출시 중단) | 동일 경계 — 어휘 안내만 확장(B-19) |
| pom project `<version>` 직접 쓰기(xml-path) | 명문화된 제외 유지 — usable:false+advice 흐름 존재(R18×C2) |
| gradle 내부 의존성 자동 감지·libs.versions.toml | 명문화된 제외 유지 — 표준 라이브러리 파싱 한계, 질문으로 보완 |
| trunk independent maintenanceLines / trunk×release-pr×tagless / direct-push gitflow / release-train / tag-message / sequential | validate 명시 거부 + 대안 존재 — 유지 |
| GitOps 레포를 버전 소스로 지원 | 진단이 정답(전파 대상) — B-34의 거절 문구로 종결 |

## 10. 완료 기준 자가 점검

- [x] 매트릭스 전 칸(198) 판정 + 레이어 표기 — §2·§3 (부분·미지원 93칸 전부에 백로그 번호 또는 제외 사유)
- [x] 시뮬레이션 요약 섹션 — §4 (3종, 데스크 판정 확인·정정 명시)
- [x] P0~P2 백로그 + S/M/L 규모 — §8 (37항목, 약속 아님 명시)
- [x] 정형 파일 적합성 5a/5b 결론 — §7
- [x] config 조합 완결성·dogfood 마찰 — §5·§6
- 확신도 낮은 판정은 각 레인 로그에 별도 표기돼 있으며, 실행 전 재검증 권장 항목: B-7 축소 설계(MICRO 산술 재사용) 타당성, B-31 모바일 수요, poetry 멀티라인 테이블 실전 빈도(B-3의 P0 산정 민감도).

---
*방법론 각주: 데스크 리뷰 5레인 + 조합·dogfood·5b 레인 병렬, 판정 기준·경계는 2026-08-06 인터뷰 확정 스펙. 합성 레포 3종과 P0 재현 스크래치는 세션 스크래치패드에 격리(레포 미포함). 경쟁 도구 기능 비교는 기준선에서 제외(생태계 관행 지식·수요 프록시 인용만 허용).*
