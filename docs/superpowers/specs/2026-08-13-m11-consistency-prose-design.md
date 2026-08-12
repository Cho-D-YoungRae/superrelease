# M11 설계 — 정합 잔여 + 프로즈 (B-9 · B-10 · B-11 + B-19 잔여 + 이월 정리)

2026-08-13 · 근거: [커버리지 검토 §8 P1 백로그](2026-08-06-coverage-review.md) · 로드맵: [M8 스펙 §0](2026-08-12-m8-onboarding-entrance-design.md) — **P1 마지막 마일스톤**

## 0. 범위

B-9(Cargo.lock 동기화) + B-10(per-package CHANGELOG 목적지) + B-11(watchPaths) + B-19 잔여(전수 감사 완료, §4) + M8~M10 리뷰 이월 정리를 **한 사이클**로 완주한다(사용자 승인, 2026-08-13). 스크립트 확장 2건은 기존 패턴의 대칭 확장이며 버전 산술은 건드리지 않는다.

## 1. B-9 — Cargo.lock 동기화 (version.py)

`sync_package_lock`(package-lock.json)의 대칭으로 `sync_cargo_lock(toml_path, new_version)` 신설:

- Cargo.toml의 `[package]` 섹션 `name`을 regex로 추출 → 같은 디렉터리 `Cargo.lock`에서 그 이름의 `[[package]]` 블록의 `version`만 교체. cargo 생성 형식(블록 내 `name = "x"` 다음 줄들에 `version = "y"`)이 안정적이라 regex로 안전: `(\[\[package\]\]\s*\nname = "<이름>"\s*\nversion = ")([^"]+)(")` — `<이름>`은 `re.escape` 적용.
- lock 파일 부재·자기 항목 부재 시 조용히 skip(기존 스타일). 교체 시 `Cargo.lock: synced to <v>` 출력. 같은 lock의 다른 패키지 항목(의존성)은 절대 건드리지 않는다.
- 호출 지점: `set_location`에서 `path.name == "Cargo.toml"`일 때 — regex 분기 치환 후 + already-current 경로 모두(package.json의 `sync_package_lock` 호출과 대칭).
- test_version.py 결정론 테스트: 동기화 성공 · lock 부재 skip · 자기 항목 부재 skip · 동명 의존성 미오염(자기 블록만).
- 골든 32종의 version.py가 verbatim 재복사된다 — 예상 blast radius(스크립트 파일만, 렌더 문서 불변).

## 2. B-10 — per-package CHANGELOG 노트 목적지

새 destinations 값 **`package-changelog`** (independent 모노레포 전용):

- validate_config: known_dests에 추가, sink 집합(fragment의 sink 인정)에 포함, **non-independent config에서 거부** — `scopes[i]: notes destination "package-changelog" requires monorepoStrategy "independent" (single-repo scopes: use "changelog")` 취지의 고유 메시지.
- `derived_flags`에 `anyNotesPackageChangelog` 추가 — 테스트는 같은 함수를 호출(M7 교훈).
- release-monorepo SKILL.md §5에 게이트 줄: `package-changelog`가 그 scope의 목적지면 그 scope 경로의 `CHANGELOG.md`(`<scope.path>/CHANGELOG.md`) 최신 항목으로 삽입 — `changelog-entry.md` 골격 재사용하되 헤딩은 `## <version>`(scope 파일 안이므로 scope 접두 불요; 루트 changelog의 `## <scope>@<version>`과 구분). 파일이 없으면 KaC 골격으로 신설.
- **신규 골든 1종 `package-changelog-monorepo`**(33종): independent 모노레포, scope들 destinations `["package-changelog", "github-release"]`.
- init 번들 5 문구에 목적지 추가(independent 한정 표기) + README 노트 목적지 표(양판) 갱신.

## 3. B-11 — changed-packages watchPaths

scope 선택 필드 `watchPaths`(문자열 배열, 기본 `[]`):

- `changed_for`의 파일 필터 확장: scope.path prefix **또는** watchPaths 항목 중 하나의 prefix에 매치하면 그 scope의 변경으로 집계. prefix 정규화는 기존 `path_prefix` 재사용.
- validate_config: `scopes[i].watchPaths must be a list of strings` 취지의 타입 검증(선택 필드 — 부재 허용).
- helpers `scope_config`의 scope에 `"watchPaths": []` 기본 추가(스키마 명문화).
- test_changed_packages.py: 공유 경로(`shared/`) 변경만 있을 때 watchPaths 가진 scope가 hasChanges true · watchPaths 없는 scope는 false · scope.path 변경과의 합집합.
- init 번들 1(independent scope 확정 시)에 한 줄: 전 scope에 영향 주는 공유 경로(공용 라이브러리·codegen 소스 등)가 있으면 해당 scope들의 `watchPaths`에 기록하라. README config 표에 행 추가.
- 골든의 changed-packages.py verbatim 재복사(모노레포 골든들) — 예상 blast radius.

## 4. 프로즈 묶음 — B-19 잔여(감사 확정) + 이월

### 4a. B-19 잔여 (전수 감사 결과 — 2026-08-13)

| 항목 | 대상 파일 | 내용 |
|---|---|---|
| 회수 어휘 확장 | `references/edge-cases.md`(버전 재사용 금지 절) + release asset 실패 절 | cargo yank · Go retract(retract 지시문) · 모바일 스토어(롤백 불가 — 롤포워드) · 데스크톱 업데이터 피드(구버전 재게시) · 컨테이너(태그 재푸시 금지, 새 패치로) 어휘 추가 |
| immutableId SPA 어휘 | `references/prerelease-and-dev-channel.md` | 정적 웹/SPA의 불변 식별자 어휘 한 줄(빌드 해시 파일명·`meta` 태그 주입 등) |
| mergePolicy unknown 지침 | init SKILL.md 번들 6 | 팀 정책이 없으면 `unknown` 기입(README 표와 정합) 한 줄 |
| PEP 440 안내 트리거 보강 | init SKILL.md 번들 4 | 트리거를 "pyproject.toml이 버전 후보"에서 "buildSystems에 python 또는 pyproject 후보"로 확장 |
| KaC 모노레포 헤딩 트레이드오프 | `references/notes-and-changelog.md` | 루트 changelog의 `## <scope>@<version>` 헤딩은 KaC 규약 밖(실소비 파서 희박) — 트레이드오프와 package-changelog 대안(§2) 명문화 |
| fixed의 dependents 무시 | `references/monorepo.md` + init SKILL.md 모노레포 절 | fixed 전략에서 `dependents`는 무의미(단일 scope) — 무시됨을 명시 |
| 번들 4/5 scope별 차등 | init SKILL.md 번들 4·5 | independent 모노레포에서 pre/post·notes는 scope별로 다르게 답할 수 있음을 한 줄 명시 |
| Go /vN 문서 | `references/version-schemes.md` | Go v2+ 메이저는 module path `/vN` 개정 수반 — superrelease 표현 밖(버전 파일·태그만 관리, 경로 개정은 수동) 한 줄 |
| Phase 3 문구 모순 | init SKILL.md | "Phase 3 전 파일 생성 금지" 규칙과 config.json 작성 절(Phase 2 말미)의 배치 모순 확인·정정 — config.json 작성은 Phase 3의 첫 단계로 명시하거나 규칙 문구를 한정 |
| preflight 결번 cosmetic | release asset preflight | 조건부 항목 collapse 시 번호 결번(예: 4→6)이 생길 수 있음 — "번호는 항목 식별용, 결번은 정상" 한 줄 또는 표현 조정 |

**방치 확정(스펙 기록만, 작업 없음)**: `--check` 병기(대상 코드 부재 — 워크스루 시점 이후 소멸) · docstring 3-모드(version.py docstring이 이미 read/write/verify 서술 — 충족) · scan_tags `latest` 무필터(byPattern으로 충분) · 비정형 pubspec 무음 탈락(무효 형식) · `weird@1.2` 2자리 scoped(스펙대로) · monorepo/hotfix 빌드번호 게이트(니치).

### 4b. 이월 코드 minor (scan 다듬기)

- `_python_packages`의 `dependencies` regex를 `[project]` 테이블로 스코프(다른 테이블의 행-시작 dependencies 오탐 방지).
- charts/* helm packages에 node_paths dedup 가드(중복 항목 방지).
- `ANDROID_VERSION_NAME_PATTERN`에 행 앵커(`^\s*versionName…`, re.M — 주석 선매치 완화. 캡처 그룹 1개 유지).
- 번들 4 빌드 번호 질문 트리거에서 bare `dart`(빌드 번호 신호 없는 순수 Dart 라이브러리) 완화 — `flutter` buildSystem·xcconfig·versionName 후보·pubspec `buildNumber` 필드가 있을 때만 질문(프로즈 수정).

### 4c. 이월 프로즈 minor

- 모노레포 preflight 6의 "태그를 쓰지 않는 scope"(config tagless) vs "anchor 태그가 하나도 없는 scope"(태그 0 상태) 인접 문구 구분 명료화(asset — 바이트 변화는 release-pr 모노레포 골든 한정).
- 초기 버전 결정 일원화: 번들 2 후보-0건 시드 규칙과 번들 7(첫 릴리스 0.1.0/1.0.0) 질문의 관계를 상호 참조로 정리 + B-12 "후보 0건 분기와 같은 규칙" superset 표현 정정.
- compatCheck 예시(kotlin-bcv·japicmp)를 JVM 한정으로 표기(+비-JVM 대응 도구 어휘: cargo-semver-checks 등 한 줄).
- README 양판: Known limits의 모바일 불릿(지원 서술 위주)을 케이스 커버리지 표로 이동하고 한계 절에는 잔여 한계만 남긴다.

## 5. 검증

- 스크립트 2건: 결정론 유닛 테스트(test_version·test_changed_packages) + 골든 재생성 — 예상 변경: 전 골든의 version.py·모노레포 골든의 changed-packages.py(verbatim 복사) + 신규 package-changelog-monorepo 트리 + 4c preflight 문구의 release-pr 모노레포 골든. **그 외 렌더 문서 불변**을 `git status`로 확인. dogfood 재렌더(스크립트 2종 + release-monorepo 미렌더(단일 레포) — `.superrelease/scripts/*` 변화 예상).
- validate 신규 규칙 2건(package-changelog 한정·watchPaths 타입) 거부 테스트 — 규칙 고유 문구 핀.
- render 게이트 테스트(test_assets): package-changelog 렌더·미사용 시 collapse.
- 전체 `python3 -m unittest discover -s tests -q` + `claude plugin validate . --strict` + init SKILL.md ≤500줄.
- CHANGELOG `[Unreleased]`·README 갱신은 마지막 태스크.

## 6. 비범위

- P2 전체(B-21~B-35) — 수요 확인 후.
- Cargo workspace 멤버 순회(R13×C6 — B-8 동반 검토 항목이었으나 미수요) · per-package CHANGELOG의 backfill 지원(신규 목적지의 과거 소급은 니치).
- release-train·tag-message 등 명시 제외 목록 유지.
