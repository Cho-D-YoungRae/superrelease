# superrelease M3c-2 — CHANGELOG backfill 설계

이 문서는 M3c의 두 번째 조각 **M3c-2**의 설계다. 이미 태그가 쌓여 있는 기존 레포에서, 그동안 기록되지 않았던 과거 릴리스 노트를 태그 구간별로 소급 작성해 CHANGELOG.md를 채우는 **backfill** 기능을 추가한다.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md) (§4.3 질문 번들 7, §6.5 조건부 스킬, §9 edge-cases.md). 베이스 커밋: main `07916b5`.

## M3c 분해 (참고)

- **M3c-1 (완료)**: 노트 목적지 fragment + tag-message.
- **M3c-2 (이 문서)**: CHANGELOG backfill (단일 scope 레포 한정).
- **M3c-3**: release trains (이중 체계 모노레포). 모노레포 backfill도 여기서 함께 다룬다.

## 배경

`references/edge-cases.md`가 이미 backfill 개념을 서술하고 "M3에서 지원"으로 표시하고 있다: 태그가 `v1.0.0`~`v1.5.0`처럼 쌓여 있는데 CHANGELOG가 없으면, `v1.0.0..v1.1.0`·`v1.1.0..v1.2.0`처럼 태그 구간을 순서대로 훑어 각 구간의 커밋으로 그 릴리스의 노트를 하나씩 사후 작성한다. init 번들 7이 "CHANGELOG backfill 제공 여부"를 묻도록 예고돼 있다. 이 마일스톤이 그 기능을 실동작으로 채운다.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 위치 | 조건부 생성 스킬 `backfill/SKILL.md` (manifest `when: "repo.backfill"`) | hotfix 선례, 일회성 작업의 의도적 호출·dry-run 리뷰 통제 |
| 노트 깊이 | 간결한 구간별 항목(changelog-entry 골격) | 이력 재구성에 적절, N구간 × 전체 노트의 토큰 부담 회피, CHANGELOG.md 출력 형식과 일치 |
| 모노레포 | 단일 scope 레포 한정(모노레포 backfill은 M3c-3) | 범위 축소·확실한 출하, 모노레포 태그 네임스페이스 순회는 M3c-3 소관 |

## A. backfill 생성 스킬 (`skills/init/assets/skills/backfill/SKILL.md`)

hotfix처럼 조건부로 생성되는 자립 스킬. description은 3인칭·pushy·한국어 트리거+영어 키워드·**프로젝트명 포함**("백필해줘", "체인지로그 소급", "과거 릴리스 노트 채워줘", "backfill" 등). 절차:

1. **대상 태그 구간 산출**: `git tag --list`에서 scope의 `tag.format`에 맞는 태그만 필터(edge-cases의 anchor 규칙 — 과거 혼재 포맷 태그는 무시)하고 버전 순으로 정렬한다. 연속 쌍 `A..B`가 한 구간이다. 가장 이른 태그는 선행 태그가 없으므로 `<root>..<firstTag>`(첫 릴리스)로 다룬다.
2. **멱등성**: CHANGELOG.md를 읽어 **이미 항목이 있는 버전은 건너뛴다** — 누락된 구간만 채운다. 기존 항목과 Unreleased 섹션은 건드리지 않는다.
3. **구간별 노트 작성**: 채울 각 구간에 대해 `git log <A>..<B> --pretty=format:"%h %s"`(squash 레포면 커밋 제목의 `(#N)`으로 PR을 역참조)로 커밋을 모으고, `.claude/skills/release-notes/SKILL.md` 로직으로 읽어 `.superrelease/templates/changelog-entry.md` 골격(Keep a Changelog: Added/Changed/Fixed)으로 **간결히** 작성한다. 정식 릴리스 노트가 아니라 이력 재구성이므로 Changes 목록 위주로 짧게.
4. **삽입**: CHANGELOG.md에 역시간순(최신이 위)으로 삽입한다. Unreleased 섹션이 있으면 그 아래.
5. **dry-run → 커밋**: 채울 구간 목록과 각 항목 미리보기를 보여주고 확인받은 뒤 CHANGELOG.md만 스테이징해 커밋한다. **태그 생성·버전 bump·push는 하지 않는다** — 순수 이력 문서 작성이다.

**실패 시**: 어디까지 작성했는지 명시. CHANGELOG.md는 되돌리기 쉬우므로(태그 무관) `git checkout CHANGELOG.md`로 안전하게 취소 가능함을 안내한다.

## B. config 스키마 + manifest

- config `repo.backfill: false` 필드 추가(init config 템플릿·각주). backfill 스킬 생성 여부를 게이트한다.
- manifest.json 엔트리: `{ "src": "skills/backfill/SKILL.md", "dest": ".claude/skills/backfill/SKILL.md", "render": true, "when": "repo.backfill" }`.

## C. render.py 검증 규칙 1건

`repo.backfill`이 truthy인데 `repo.monorepoStrategy == "independent"`면 config 오류(exit 1) — 모노레포 backfill은 M3c-3까지 미지원. 기존 `maintenanceLines + independent` 거부 규칙과 동일한 패턴. render.py는 골든-복사 대상이 아니라 골든 무영향이며, 해당 조합 골든이 없어 기존 골든도 불변.

## D. init 번들 7

backfill "M3 예정" 표시 해제. 기존 태그가 있고 CHANGELOG가 없거나 불완전한 단일 스킬 레포에 backfill 스킬 생성을 제안하고 `repo.backfill: true`로 기록한다. independent 모노레포에는 "후속(M3c-3) 지원 예정"으로 표시하고 잠근다(render가 그 조합을 거부한다). 지원 범위 목록도 갱신.

## E. references

`edge-cases.md`의 CHANGELOG backfill 절: "이 기능은 M3에서 지원되며, M1에는 포함되지 않는다." → 실동작(구간 순회·멱등·lean 항목·태그/push 없음·단일 scope 한정) 서술로 교체.

## F. 골든

- 신규 1트리 `backfill-app`: `repo.backfill: true` 단일 scope config. 생성된 backfill 스킬(및 나머지 툴킷)을 스냅샷으로 고정.
- 기존 10골든은 `repo.backfill` 미설정(기본 false) → manifest `when` false → backfill 스킬 미생성 → **바이트 불변**.

## 제약·검증

- 동결 template dialect, 생성 SKILL.md ≤149줄, init SKILL.md ≤500줄.
- render 엔진·산술 무변경 — 유일한 Python 변경은 `validate_config` 규칙 1건.
- 자립성: 생성 backfill 스킬은 `.superrelease/`·`.claude/` 상대 경로만 참조(release-notes 스킬·changelog-entry 템플릿을 프로즈로 참조 — 생성 스킬 간 참조 허용). 플러그인 경로 참조 금지.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어·생성 문서 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인.

## 비범위 (후속)

- 모노레포 backfill(scope별 태그 네임스페이스 순회, `## <scope>@<version>` 헤더) → M3c-3.
- backfill이 릴리스별 파일(release-file)·GitHub Release를 소급 생성하는 것(CHANGELOG.md만 대상).
- 과거 태그 자체 수정·재태깅(edge-cases의 "과거 태그 불변" 원칙 유지).

## 예상 태스크 (writing-plans에서 확정)

1. render.py backfill + independent 거부 규칙 (TDD).
2. backfill 스킬 신규 + manifest 엔트리 + config 스키마 `repo.backfill` 필드 (+ 렌더 스모크 테스트).
3. init 번들 7 해제 + edge-cases.md 정합.
4. 골든 `backfill-app` 신규 + 최종 검증.
