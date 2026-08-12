# M8 설계 — 온보딩 입구 정비 (B-5 · B-12 · B-13 · B-20)

2026-08-12 · 근거: [커버리지 검토 §8 P1 백로그](2026-08-06-coverage-review.md)

## 0. 배경과 로드맵

커버리지 검토의 P1 백로그 11건을 마일스톤 4개로 분해해 순차 완주한다(사용자 승인, 2026-08-12):

| 순서 | 마일스톤 | 항목 |
|---|---|---|
| **M8 (이 문서)** | 온보딩 입구 정비 | B-5 · B-12 · B-13 · B-20 |
| M9 | 스캔 확장 에픽 | B-8 · B-6 (스펙 시 분할 가능) |
| M10 | 모바일 이중 버전 | B-7 (검토 게이트 포함) |
| M11 | 정합 잔여 + 프로즈 | B-9 · B-10 · B-11 · B-19 잔여 |

P2(B-21~B-35)는 범위 정책("니치·수요 확인 후")대로 보류한다. 구현은 opus 서브에이전트가 수행하고 스펙·계획은 메인 세션이 작성한다(사용자 지시).

**공통 원칙**: render 엔진·스크립트(version/next-version/changed-packages.py) 무변경. init SKILL.md 프로즈 + release·release-monorepo asset 프로즈만 수정한다. asset 변경분은 골든 재생성 + dogfood 재렌더가 따라온다.

## 1. B-5 — "기존 레포 + 버전 후보 0건" 분기 (init SKILL.md)

**현황**: 버전 파일 도입 절차가 신규 레포 제안 모드(SKILL.md 모드 판정 2절) 안에만 있다. 태그·커밋 히스토리가 풍부한 기존 레포(Go CLI·모바일·인프라)는 신규 모드에 진입하지 않으므로, versionLocations 후보가 0건이면 절차 없이 표류한다 — 커버리지 검토 R16×C10·R9 워크스루에서 실측된 갭.

**변경**: 번들 2(버전 위치 확정)에 후보 0건 분기를 일반화한다.

1. 후보가 0건이면 먼저 묻는다: "버전 파일이 실제로 없는가, 있는데 스캔이 못 찾았는가."
2. **있다고 하면**: 파일 경로·형식을 받아 수동 versionLocation(json-path 또는 regex)으로 등록한다 — 일치 여부는 Phase 3 자가검증(`version.py verify`)이 확인한다. 스캔 확장(M9) 전까지 미지원 파일 형식의 다리 역할.
3. **없으면**: 성격에 맞는 버전 파일(예: `VERSION`·`package.json`·`gradle.properties`)과 초기 버전을 Phase 3 렌더에 포함해 사용자 확인 후 생성한다 — 신규 모드가 이미 하는 것과 같은 절차.
4. **시드 버전**: 스캔 `tags`에 최신 릴리스 태그가 있으면 그 버전을 시드로 한다(v2.3.1 태그가 있는 레포에 0.1.0 역행 방지). 태그도 없으면 0.1.0을 제안한다.
5. 신규 모드(모드 판정 2절)의 기존 "버전 파일이 하나도 없으면" 문구는 이 일반 절차를 참조하도록 축약해 중복을 없앤다.

## 2. B-12 — placeholder(0.0.0) 리셋 질문 (init SKILL.md 번들 2)

scan은 이미 후보의 현재 값(`value`)을 리포트한다. 번들 2에서 감지 값이 `0.0.0`이면 placeholder일 가능성을 알리고 실제 시작 버전으로 리셋할지 묻는다. 제안값은 §1과 같은 규칙(최신 릴리스 태그 > 없으면 0.1.0/1.0.0 선택). 거절하면 그대로 둔다. 근거: R7×C10(웹앱 package.json의 `0.0.0` 관행).

## 3. B-13 — trunk×release-pr 첫 릴리스 재개 감지 (release + release-monorepo asset)

**현황**: gitflow 분기는 "머지된 release/* PR 검색"(`gh pr list --state merged --search "head:release/"`)으로 태그 전 중단을 잡지만, trunk 분기의 중단 감지는 "마지막 릴리스 태그가 존재하고" 전제라 **첫 릴리스(태그 0개)** 는 PR 머지 후 재개를 못 잡는다. 단일(release/SKILL.md preflight 6 else 분기)·모노레포(release-monorepo/SKILL.md preflight 6 else 분기) 동일한 갭. 근거: R7×C5.

**변경**: 두 asset의 trunk 중단 감지에 `{{#if repo.releasePath == "release-pr"}}` 인라인 게이트로 한 문장을 추가한다 — 릴리스 태그가 하나도 없으면 gitflow와 같은 머지된 릴리스 PR 검색으로 "머지됐지만 태그 없는 첫 릴리스"를 감지해 태그 단계부터 재개하라. 모노레포판은 scope별(anchor 없는 scope)로 동일 판정.

**바이트 불변**: direct-push config에서 0바이트로 collapse해 기존 골든 바이트 불변. release-pr 계열 골든만 변한다. superrelease 자신이 trunk×release-pr이므로 dogfood 재렌더도 발생한다.

## 4. B-20 — SNAPSHOT+next-snapshot 기본을 JVM 한정 (init SKILL.md 2곳)

`references/prerelease-and-dev-channel.md`는 이미 SNAPSHOT 관례를 "JVM 라이브러리"로 한정한다 — SKILL.md만 어긋난 상태다. 근거: R1×C11(npm 라이브러리에 SNAPSHOT 기본은 생태계 관례 위반).

- **신규 모드 프리셋**(모드 판정 2절): "라이브러리→SemVer+SNAPSHOT+next-snapshot" → **JVM 라이브러리(gradle/maven 감지) 한정**. 그 외 라이브러리(npm·Rust·Python)는 SemVer + preRelease `none` + postRelease `none` 기본.
- **번들 4**: "post-release bump — 라이브러리→next-snapshot 기본" → 같은 분기. 판정 근거는 스캔 `buildSystems`.

## 5. 검증·테스트

- **새 테스트**(tests/test_assets.py): B-13 렌더 분기 어서션 — trunk×release-pr 렌더에 규칙 고유 문구(머지된 릴리스 PR 검색) 존재, trunk×direct-push 렌더에 부재. M6 교훈대로 범용 단어가 아닌 규칙 고유 문구를 핀한다.
- 골든 재생성(`python3 tests/update_golden.py`) → `git status --porcelain tests/golden`이 release-pr 계열만 보이는지 확인.
- dogfood 재렌더(`python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now <ISO>`) — `tests/test_dogfood_selfrender.py`가 드리프트를 강제한다.
- 전체 테스트 `python3 -m unittest discover -s tests -q` → `claude plugin validate . --strict` → init SKILL.md ≤500줄 확인(현재 148줄).

## 6. 비범위

- 스캔 확장(새 파일 형식 감지)은 M9(B-8). B-5의 수동 등록은 그 전까지의 다리다.
- 기존 자동화 감지(B-6)·모바일 이중 버전(B-7)은 각각 M9·M10.
- 엔진·스크립트·validate_config 변경 없음 — M8은 전부 프로즈 규모다.
