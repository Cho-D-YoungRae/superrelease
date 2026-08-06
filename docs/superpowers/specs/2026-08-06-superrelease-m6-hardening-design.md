# M6 — 하드닝: validate 완결성·스크립트 가드 (설계)

- 날짜: 2026-08-06
- 입력: [커버리지 검토 보고서](2026-08-06-coverage-review.md)의 백로그 §8 중 정합성 수비 항목
- 결정 경위: 브레인스토밍에서 B안(v0.4.0 선릴리스 + 풀 하드닝) 채택. M5(구현) → M6(하드닝)의 마일스톤 리듬.

## 1. 목표

커버리지 검토가 **재현까지 확보한 정합성 위험**(P0 3건)과 validate 침묵 지대(B-14~B-17)를 제거하고, 골든 공백(B-18)을 메워 회귀망을 넓힌다. 선행으로 v0.4.0을 릴리스해 [Unreleased] 적체(M5 3건 + `feat!` 스코프 제거 + 로드맵 정리)를 소진한다.

원칙: **엔진은 안정, config 규칙만 자란다** — 산술·렌더 로직은 불변이고, `validate_config` 규칙과 스크립트 *가드*(입력 검증)만 추가한다.

## 2. 비목표

- 커버리지 확장 축(B-5 입구 분기, B-6 기존 도구 공존, B-7 이중 버전, B-8 스캔 에픽, B-9~B-11) — 다음 마일스톤 후보.
- P2 전체(B-21~B-35).
- B-19 프로즈 다발 중 폴리시성 항목(회수 어휘·immutableId 어휘 등) — 정확성 항목 3건만 포함(docstring은 Task 3에 편승, 나머지 2건은 Task 6).
- M6 자체의 릴리스 — 완료 후 별도 결정(validate 강화는 minor감: 침묵 통과하던 조합은 어차피 런타임에 죽던 구성이라 거부는 fix 성격).

## 3. Phase 0 — v0.4.0 선릴리스

M6 코드 작업 전에 자기 툴킷("릴리스해줘" 플로우, release-pr 경로)으로 v0.4.0을 출하한다. `feat!`(train·tag-message 제거)이 있으나 0.x 관례상 breaking→minor. 이 릴리스 자체가 dogfood 실전 e2e 1회로 B-37을 부분 충족한다. 릴리스 후 `git rev-parse HEAD` 원격 정합 확인(운영 체크리스트).

## 4. Task 1 — validate: P0 2건 (B-1·B-2)

`skills/init/scripts/render.py`의 `validate_config`에만 추가. 골든 무영향(config.json은 스냅샷 대상 아님).

- **B-1**: `repo.releasePath ∈ {direct-push, release-pr}` 닫힌 집합. 위반 메시지에 허용값 명시. 근거: 오타 `release_pr`가 침묵 통과해 release-pr flavor 스킬 + 미렌더 `release-pr-body.md` 참조의 망가진 툴킷을 생성(보고서 §5 재현).
- **B-2**: `postRelease.bump == "next-snapshot"` ⇒ `preRelease.style == "mutable"` 그리고 `preRelease.qualifier` 비어있지 않음. 위반 메시지에 이유(생성 스킬이 `--qualifier <값>`을 실행) 명시. 근거: qualifier null이면 릴리스 시점 argparse 사망 또는 bare 복귀로 중단 감지 상시 오탐(보고서 §5 재현).

검증: 보고서의 재현 config 2건을 **역테스트**로 전환 — 이제 exit 1로 거부돼야 통과. 기존 골든 config 전수(next-snapshot 사용 config 포함)는 계속 통과해야 한다.

## 5. Task 2 — validate: 침묵 지대 묶음 (B-14~B-17)

동일하게 `validate_config`만. 규칙별 거부 테스트 + 합법 config 무영향 테스트 쌍.

- **B-14**: `branching == "gitflow"` × `maintenanceLines: true` 거부 — manifest의 hotfix 이중 entry가 같은 목적지에 렌더되어 gitflow flavor만 남고 유지보수 라인 기대가 소리 없이 증발. 메시지: "gitflow의 production hotfix가 대체하며 유지보수 라인 hotfix는 trunk 전용".
- **B-15**: `movingMajorTag: true` ⇒ 해당 scope `scheme.type == "semver"`; 그리고 `monorepoStrategy == "independent"`에서는 거부(비네임스페이스 `v<major>` 유동 태그의 scope 간 충돌 — 네임스페이스 규약 정의 전까지).
- **B-16**: `scheme.type ∈ {calver, headver}` ⇒ `scheme.pattern` 필수(비어있지 않음) — 현재는 릴리스 시점 exit 2로 지연 실패.
- **B-17 묶음**:
  - `monorepoStrategy != "independent"` ⇒ `len(scopes) == 1` (둘째 scope는 렌더에서 유령이 됨).
  - independent: scope `name` 유일성 + tag enabled scope 간 `tag.format` 유일성(anchor 교차 오염 방지).
  - `"release-file" ∈ destinations` ⇒ `notes.perReleasePath` 필수(비어있지 않음) — 명시 null이면 루트에 `{version}.md`가 생기는 사고 방지.
  - `releaseCommitFormat`: `{version}` 포함 필수, `{scope}`는 independent에서만 허용.
  - 닫힌 집합: `notes.language ∈ {ko, en, both}` · `notes.destinations` 비어있지 않음 · `repo.mergePolicy ∈ {merge, squash, rebase, unknown}` (rebase는 머지 커밋 프로즈로 렌더됨을 인지한 허용).

## 6. Task 3 — 스크립트 가드 (B-3·B-4) + docstring, 골든 churn 1회

`skills/init/assets/scripts/{version,next-version}.py`는 골든 21곳에 verbatim 복사된다 — 두 파일을 **한 사이클**로 수정하고 `update_golden.py`를 1회만 돌린다.

- **B-3 (version.py — regex 단일 매치 강제)**: `regex` 타입 location의 get/set/verify 모두, 파일 내 매치 수가 정확히 1이 아니면 exit 1. 메시지에 파일·패턴·매치 수 + 완화 경로("패턴을 행 앵커나 주변 문맥으로 좁혀라") 포함. 근거: 현재 set은 전 매치 치환·get/verify는 첫 매치만 읽는 비대칭이라, Cargo `[dependencies.*]`·pyproject `[tool.*]`·poetry 멀티라인 테이블·k8s 다중 이미지에서 조용한 오염 + 탐지 불가(4개 페르소나군 독립 발견). 스캔이 생성하는 패턴은 전부 단일 매치 전제라 합법 사용 무영향 — 골든 config 전수로 확인.
- **B-4 (next-version.py — build metadata 거부)**: semver 산술 경로 전체(`--bump`/`--release`/`--qualifier`)에서 입력 버전(`--current`든 `--scope` 파일 값이든)에 `+meta`가 있으면 exit 1 + "build metadata는 산술에서 보존되지 않는다 — 마케팅 버전만 캡처하는 패턴을 쓰라". 근거: 현재 `1.2.3+45 --bump patch → 1.2.4`를 stderr 0바이트로 출력(Flutter 워크스루 실측 — 스토어 키 조용한 소실).
- **docstring**(B-19 편승): next-version.py 모듈 docstring "Two input modes" → 3모드(`--current`/`--scope`/`--current-among`) 정정. 같은 churn 사이클에 흡수.

검증: 가드 단위 테스트(다중 매치 fixture·`+meta` 입력) + 재생성 후 `git status --porcelain tests/golden`이 **의도 파일만**(스크립트 verbatim 21곳) 보여야 한다. 산술 결과는 전 케이스 불변(가드는 입력 검증만).

## 7. Task 4 — 골든 공백 채우기 (B-18)

신규 골든 트리 ~9종. 각각 대표 config를 `tests/golden_configs.py`에 추가하고 어서션 1~2개(핵심 분기 존재/부재).

1. trunk × independent × bundle (bundle의 비-gitflow 경로)
2. independent × fragment(+sink)
3. independent × release-file 목적지
4. maintenanceLines × release-pr (단일 레포 hotfix)
5. backfill × gitflow (단일)
6. 단일 gitflow-tagless × hotfix (M5 수동 검증분의 회귀망 편입)
7. fixed × gitflow — 렌더가 정상임을 핀 + **지원 범위 문구에 fixed 명시 여부를 이 기회에 확정**(현행 "단일+independent" 문구와의 정합)
8. Python 라이브러리(pyproject regex) 대표
9. Maven `<revision>` regex 대표

규율: 골든 추가 중 발견되는 프로즈 결함은 S(문구)면 즉수정 + 해당 골든에 어서션, M 이상이면 백로그 기록만.

## 8. Task 5 — 혼합태그 프로즈 게이트 (B-36)

- render `build_context`에 `derived.allTagEnabled` 파생값 추가(기존 `anyTagEnabled` 옆).
- release-monorepo §8: 혼합태그(일부 tagged, 일부 tagless)일 때 per-scope skip 안내 렌더 — all-tagged에서는 0바이트 collapse(개행은 `{{#if}}` 안에)로 기존 골든 바이트 불변을 목표로 하고, 불가피할 때만 pnpm-monorepo 재베이스.
- 프리뷰·"실패 시"의 "태그명" 프로즈(release/release-monorepo/hotfix 3스킬 공유)를 태그 게이트로 한정.

## 9. Task 6 (꼬리) — 프로즈 정확성 3건 (B-19 부분)

- init SKILL.md gitflow 절의 "정식 사이클→태그" vs "태그 선택사항" 상충 → '(태그 사용 시)' 한정 copy-edit (플러그인 소스 — 골든 무관).
- scan.py `BUNDLE_NOTE_RE` 조임: `^\d{4}[.\d]+$`가 순수 8자리(`20260101`)도 매치 → 점 구분 필수(`^\d{4}(\.\d+)+$`) (플러그인 소스 — 골든 무관).
- (Task 3에 편승 완료 항목 확인) next-version.py docstring.

## 10. 완료 기준

1. 보고서 §5의 재현 config 2건(B-1·B-2)이 render에서 거부된다 — 역테스트 통과.
2. 신규 validate 규칙 전부에 거부/무영향 테스트 쌍이 있다.
3. version.py 다중 매치·next-version.py `+meta` 가드가 단위 테스트로 고정되고, 산술 결과는 전 케이스 불변.
4. 골든: 신규 ~9종 추가, Task 3 churn은 1회, 재생성 범위가 `git status --porcelain tests/golden`으로 의도 파일과 일치.
5. 전체 게이트: `python3 -m unittest discover -s tests -q` · `claude plugin validate . --strict` · dogfood self-render 무drift · 재생성 대상 외 기존 골든 바이트 불변.
6. Phase 0: v0.4.0이 출하되고 [Unreleased]가 비어 있다.

## 11. 리스크

- **B-3 오탐**: 합법적 다중 매치 운용이 존재한다면 거부가 기존 사용자를 깨움 — 알려진 케이스 없음(스캔 패턴 전부 단일 매치 전제). 에러 메시지의 완화 경로로 대응. 만에 하나 실사용 보고가 오면 opt-in 완화 플래그를 후속 논의.
- **B-36 골든 재베이스 범위**: 0바이트 collapse가 안 되는 프로즈 형태면 pnpm-monorepo 외 모노레포 골든까지 번질 수 있음 — Task 5를 마지막에 배치해 격리.
- **v0.4.0 선릴리스와 M6 브랜치의 교차**: Phase 0은 main 기준 릴리스 플로우, M6는 그 뒤 분기 — 순서 고정으로 회피.
