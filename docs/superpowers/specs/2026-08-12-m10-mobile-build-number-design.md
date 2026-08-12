# M10 설계 — 모바일 이중 버전 축소 지원 (B-7 축소판 + B-30)

2026-08-12 · 근거: [커버리지 검토 §3.3·§8](2026-08-06-coverage-review.md) · 로드맵: [M8 스펙 §0](2026-08-12-m8-onboarding-entrance-design.md)

## 0. 검토 결론 (B-7 처분 — 사용자 승인)

B-7 원안(1급 지원: buildNumber 위치 + 단조증가 산술 + verify 완화)은 **채택하지 않는다**. 근거:

1. 빌드 번호는 릴리스 사이클과 독립이다 — 베타 빌드마다 증가(TestFlight/Play 트랙)하며 릴리스당 1회 bump가 아니라서 release 스킬의 실행 모델과 맞지 않는다.
2. 업계 표준은 CI 자동 증가(`github.run_number`·fastlane `increment_build_number`·`flutter build --build-number`)다. 릴리스 도구가 파일의 빌드 번호를 관리하면 CI와 경합한다 — superrelease의 경계("publishing은 CI 몫")와도 일치.
3. 1급 지원은 엔진·스크립트 3종을 모두 건드리는 L 규모로 "엔진은 안정" 원칙과 정면 긴장.

대신 **축소 지원**: 실행 없이 감지·질문·기록·안내를 1급화한다. 남는 실질 케이스(Flutter pubspec `+N` — 마케팅 버전과 같은 필드에 박제)는 마케팅-only 캡처 패턴으로 해소한다 — `version.py set`은 캡처 그룹 범위만 치환하므로(`text[:m.start(1)] + new + text[m.end(1):]`) `+45`가 보존된다(커버리지 리뷰 R9×C3 실측과 일치).

사용자 승인으로 **B-30(P2)을 한 줄 승격**해 포함한다(모바일 preRelease none 권장 안내 — 모바일 묶음과 응집).

## 1. config 필드 + validate

- `repo.buildNumber`: `"ci"` | `"manual"` | `null`(기본 — 비모바일 레포).
- `validate_config`에 닫힌 집합 규칙 추가: null/부재는 허용, 그 외 값은 `repo.buildNumber must be "ci", "manual" or null (got "<x>")` — 엔진·스크립트 무변경, 검증 규칙만 자란다.

## 2. scan — pubspec 마케팅-only 승격 + M9 이월 2건

- **pubspec `+N` 처리 개선**(M9의 advice-only를 대체): 값에 `+`가 있으면 마케팅 부분만 캡처하는 `PUBSPEC_MARKETING_PATTERN = "^version:\\s*(\\d[^+\\s]*)"`으로 **usable 후보**를 만들고, extra 필드 `buildNumber: "<+ 뒤 문자열 그대로>"`(예: `"45"`, 비숫자 메타데이터도 그대로)를 붙여 빌드 번호 존재를 리포트한다(init 질문 트리거). `+`가 없으면 기존 `PUBSPEC_VERSION_PATTERN` 전체-캡처 후보 그대로. M9 테스트 `test_pubspec_build_number_is_advice_only`는 새 계약을 핀하도록 대체한다.
- **xcconfig 게이트**(M9 이월): 캡처 값이 `VERSIONISH_RE`에 맞을 때만 후보로 — `MARKETING_VERSION = $(inherited)` 같은 빌드 세팅 참조 제외.
- **flutter 분류**(M9 이월): `^\s+flutter:` → `^[ \t]*flutter:`(개행 관통 방지 + 0 들여쓰기 포함 — 최상위 `flutter:` 섹션(uses-material-design 등)도 진짜 Flutter 신호라는 M9 리뷰 확인을 반영).

## 3. init — 빌드 번호 질문·기록·안내 (+B-30)

모바일 신호(buildSystems의 `flutter`/`dart`, xcconfig 후보, pubspec 후보의 `buildNumber` 필드, `app/`·`android/app/` versionName 후보) 중 하나라도 있으면 번들 4에서 묻는다:

- **질문**: 빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)을 어떻게 관리하는가 — **CI 자동 증가(권장)** | 수동. 답을 `repo.buildNumber`에 기록하고 `decisions`에 `{"topic": "build-number", "answer": "ci"|"manual", "rationale": "<감지 신호>", "source": "scan", "decidedAt": "<date>"}` 기록.
- **안내**(실행 없음): CI 증가 스니펫 방향 한 줄 — `github.run_number`·`flutter build --build-number`·fastlane `increment_build_number`·agvtool. superrelease는 빌드 번호를 절대 수정하지 않음을 명시.
- **B-30 한 줄**: 같은 자리에서 "모바일 앱은 preRelease `none` 권장 — 스토어 베타(TestFlight/Play 트랙)는 빌드번호+트랙 기반이라 버전 qualifier 모델 밖"(PEP 440 안내와 같은 패턴, references/prerelease-and-dev-channel.md 참조 유지).
- 비모바일 레포에서는 이 질문을 하지 않고 `repo.buildNumber`를 null로 둔다.

## 4. release asset 안내 게이트 + 신규 골든

- `skills/init/assets/skills/release/SKILL.md` 4단계(버전 반영)에 인라인 게이트 추가(개행·공백은 게이트 안 — 바이트 불변):
  - `{{#if repo.buildNumber == "ci"}}` 빌드 번호(versionCode·CFBundleVersion·pubspec `+N`)는 건드리지 마라 — CI가 올린다(버전 파일의 빌드 번호 부분은 항상 보존). `{{/if}}`
  - `{{#if repo.buildNumber == "manual"}}` 빌드 번호는 이 커밋에서 올리지 않는다 — 스토어 업로드 전 수동 증가를 릴리스 요약에 리마인드로 포함하라. `{{/if}}`
- release-monorepo에는 넣지 않는다 — 모바일 모노레포 이중 버전은 니치(수요 확인 후).
- **신규 골든 `flutter-app`** 1종: pubspec 마케팅-only regex 위치 + `repo.buildNumber: "ci"` + trunk×direct-push + changelog+github-release — 게이트 렌더를 골든으로 핀. `golden_configs.py`에 config 추가, README "프로젝트 유형(골든 핀)"에 Flutter 추가(32종).
- null config에서 0바이트 collapse → 기존 골든·dogfood 바이트 불변(superrelease 자신은 buildNumber 부재).

## 5. 문서

- README 양판: 모바일 한계 불릿을 "빌드 번호 축은 CI-관리 모델로 지원 — init이 감지·질문하고 config에 기록, release가 보존을 보장(파일 증가 실행은 하지 않음)"으로 갱신 + 골든 핀 목록에 Flutter.
- `references/edge-cases.md`: Flutter 레시피를 마케팅-only 패턴 기준으로 갱신(빌드 번호 보존 동작 명시). config 표(README)에 `repo.buildNumber` 행 추가.
- CHANGELOG `[Unreleased]`: Added(모바일 빌드 번호 CI-관리 모델 + flutter-app 골든) + Changed(pubspec `+N` 감지가 advice-only에서 마케팅-only usable 후보로).

## 6. 검증·테스트

- test_scan: pubspec `+N` → 마케팅-only usable 후보 + `buildNumber` extra(기존 advice 테스트 대체) · `+` 없음 → 전체 캡처 불변 · xcconfig `$(inherited)` 제외 · flutter `[ \t]` 분류.
- test_render_pipeline: `repo.buildNumber` 닫힌 집합 거부(`"cd"` 같은 오타 → 규칙 고유 문구 핀) · null/부재 허용.
- test_assets: buildNumber ci/manual 게이트 렌더 존재 + null 0바이트 collapse(규칙 고유 문구 핀).
- 골든: `update_golden.py` 후 신규 flutter-app 트리만 추가되고 기존 골든 불변 · dogfood 재렌더 바이트 불변 확인.
- `PUBSPEC_MARKETING_PATTERN`은 `*_PATTERN` str 상수 — 캡처 그룹 1개, 패턴 전수 테스트 하한 13→14.
- 전체 스위트 + `claude plugin validate . --strict` + init SKILL.md ≤500줄.

## 7. 비범위

- 빌드 번호 파일 증가 실행(1급 지원) — 검토 결과 기각(§0). 수요가 확인되면 재평가.
- iOS Info.plist 직접 위치·CURRENT_PROJECT_VERSION 감지 — M9 레시피(xcconfig 전환) 유지.
- 모바일 모노레포의 scope별 buildNumber — 니치.
- 스토어 what's new(fastlane metadata) 노트 목적지 — B-31(P2) 유지.
