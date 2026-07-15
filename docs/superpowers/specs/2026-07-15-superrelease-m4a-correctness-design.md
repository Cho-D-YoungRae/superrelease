# superrelease M4a — 정확성 픽스 팩 설계

이 문서는 M4 로드맵의 첫 마일스톤 **M4a**의 설계다. 2026-07-15 플러그인 전면 리뷰(사용성 / 케이스 커버리지 / 엔진·스크립트 3축 병렬 리뷰 + 직접 검증)에서 확정된 실버그 6건과, 그 버그들이 살아남은 원인인 테스트 사각(골든 미커버 분기 4종)을 함께 닫는다.

M4 로드맵: **M4a 정확성(본 문서)** → M4b gitflow 브랜칭 축 → M4c 스캔 커버리지 확장 → M4d 사용성·문서 정리. 각 마일스톤은 독립 스펙 → 플랜 → 구현 사이클을 돈다.

베이스 스펙: [2026-07-09-superrelease-plugin-design.md](2026-07-09-superrelease-plugin-design.md). 베이스 커밋: main `2bba1e7`.

## 배경 — 확정 버그 6건

전부 원본 파일에서 직접 검증했고, 스크립트 버그는 임시 레포에서 실행 재현했다.

1. **version.py regex `set` 오손** — `version.py:189-197`. alternation + 다중 그룹 패턴(`A-(x)|B-(x)`)에서 뒤 매치가 다른 그룹에 바인딩되면 `m.start(1) == -1`로 슬라이스가 깨져 파일 끝에 버전 문자열이 덧붙는데 exit 0. 가드가 `matches[0].lastindex`만 검사하는 게 원인.
2. **preflight 6 "중단 상태 감지" 오탐/미탐** — `release/SKILL.md:24` 등 3개 스킬. "파일 버전(수식어 제외) > 마지막 태그" 조건은 next-snapshot 레포의 정상 상태(`1.2.1-SNAPSHOT`)를 매 릴리스 resume/rollback 프롬프트로 만들고(오탐), release-pr 머지 전 재요청은 잡지 못해 중복 릴리스 PR을 시도한다(미탐). 재개 확인 `gh pr view <PR번호>`의 PR번호 출처도 미지정.
3. **단일 레포 anchor가 태그 포맷 무시** — `release/SKILL.md:30`의 `git describe --tags --abbrev=0`은 배포 태그·구스킴 태그 등 아무 태그나 잡는다. backfill·모노레포·train은 전부 `tag.format` glob 필터인데 single release만 예외.
4. **changed-packages.py 3건** — ① `-v:refname` 정렬이 `a@1.0.1-rc.1`을 `a@1.0.1` 위로 올려 anchor가 pre-release 태그에 고정 ② `git diff --name-only`가 rename을 합쳐 scope 밖으로 이동된 파일의 삭제를 놓침 ③ `tag_cfg.get("enabled")`가 키 생략을 꺼짐으로 해석(render.py는 `get("enabled", True)` — 스크립트 간 기본값 불일치).
5. **validate_config 사각** — scheme×preRelease 교차 검증이 없어 calver/headver + mutable/next-snapshot config가 렌더를 통과하고 릴리스 §8에서 `next-version.py`가 항상 exit 2로 실패하는 툴킷이 생성 가능. versionLocations 항목 내부·scheme.type 어휘도 미검증(hand-edit 후 릴리스 시점 raw traceback).
6. **tagless × github-release 모순 렌더** — tagless scope에서 §7 태그 정의는 `{{#if scope.tag.enabled}}` 안이라 사라지는데 `gh release create <태그>`는 `{{#if github.release}}`로 렌더됨 — gh가 태그를 새로 만들어 tagless 의도와 충돌. 이 조합 골든·테스트 0개.

부수 마감 2건: release-train에만 `tagTriggersDeployment` ⚠️ 경고 부재 / hotfix 백포트 시 `--latest=false` 미처리(구버전 패치 Release가 저장소 Latest로 마킹될 수 있음)와 라인 CHANGELOG 항목의 main 반영 무언급.

## 확정된 설계 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 접근 | 픽스 + 커버리지 고정(B안): 골든 4종 신설·음성 테스트 동반 | 버그가 살아남은 이유(테스트 부재)까지 제거. 골든 스냅샷 규율과 정합 |
| preflight 6 조건 | "마지막 릴리스 태그가 존재하고, 파일 버전이 그보다 높으며, mutable 개발 수식어 상태가 아니고, 파일 버전 그대로의 태그가 없으면 중단 상태" | SNAPSHOT 정상 상태 오탐 제거, counter(rc) 중단 감지 유지, 첫 릴리스(태그 0개)는 §2 anchor-없음 경로로 분리 |
| release-pr 중복 가드 | preflight에 "열린 `release/*` PR 확인" 항목 추가(release-pr 레포 한정), 재개는 `gh pr view release/<버전>` 브랜치명 역참조 | 새 상태 저장 없이(M3b 원칙 유지) 머지 전 재요청을 대기 보고로 처리 |
| anchor 규칙 | `tag.format`의 `{version}`→`*` glob + `git -c versionsort.suffix=- tag --list --sort=-v:refname` | backfill·모노레포·train과 동일 규칙으로 통일. versionsort.suffix로 pre-release가 정식 아래로 정렬 |
| tag.enabled 기본값 | 키 생략 = **true** (render.py 규약, 기존 테스트가 명시) | changed-packages.py를 render 쪽에 맞춘다 — 스키마·helpers도 명시값을 쓰므로 실사용 영향은 hand-edit config뿐 |
| tagless×github-release | validate 거부: `github.release: true`는 전 scope `tag.enabled` 요구 | GitHub Release는 태그 필수 — 모순 조합은 만들 수 없어야 함 |
| calver/headver × pre/post | validate 거부: non-semver scope는 `preRelease.style: "none"` + `postRelease.bump: "none"` 강제 | §8이 항상 실패하는 툴킷 생성 차단. init 번들 4도 이미 그렇게 안내 — render가 이중 차단 |
| hotfix 마감 | 본 팩에 포함(스킬 프로즈 2줄) | 작고 명확한 정확성 이슈 — gitflow 축(M4b)과 독립 |
| 스크립트 수정 범위 | 버그 픽스 한정 — 산술 로직 재설계 없음 | CLAUDE.md "엔진은 안정" 규율은 기능 추가 시 조항. 버그 픽스는 해당 없음을 명시 |

## A. 스크립트 수정 (verbatim 자산 3종)

1. **version.py** — regex 타입 read/set 진입 시 `re.compile(pattern).groups != 1`이면 즉시 exit 2 (메시지: 캡처 그룹 정확히 1개 필요). 매치별 그룹 참여 필터(`m.lastindex`)는 유지 — alternation의 비참여 매치는 계속 건너뛴다. 결과: 다중 그룹 패턴은 "가끔 조용한 오손"에서 "항상 명확한 에러"가 된다.
2. **changed-packages.py** — ① `latest_tag`의 태그 나열에 `-c versionsort.suffix=-` 적용 ② `git diff --name-only --no-renames <anchor>..HEAD`로 rename을 삭제+추가로 분해 ③ `tag_cfg.get("enabled", True)`.
3. **next-version.py** — CalVer에서 계산 결과 == 현재 버전이면 exit 1 (stderr: same-period re-release, pattern에 MICRO 없음 안내). MICRO 있는 패턴은 카운터가 증가하므로 영향 없음.

스크립트는 골든에 verbatim 복사되므로 관련 골든 트리의 스크립트 파일이 재생성된다(의도적).

## B. 생성 스킬 수정 (렌더 자산)

- **preflight 6 재작성** — `release`·`release-monorepo`·`release-train` 3개 스킬. 위 표의 조건으로 교체하되, mutable 수식어 예외 문장은 `{{#if scope.preRelease.style == "mutable"}}` 게이트(none/counter 레포에서 0바이트 collapse). tagless scope에서는 항목 전체를 `{{#if scope.tag.enabled}}`로 게이트(태그 부재 시 중단 감지 자체가 무의미 — anchor.value 기반 판단은 비범위). 모노레포·train의 scope 순회 문맥에 맞춘 문구 변형은 플랜에서 파일별 확정.
- **release-pr 중복 가드** — release-pr을 지원하는 스킬의 preflight에 `{{#if repo.releasePath == "release-pr"}}` 항목 추가: `gh pr list --state open --json headRefName`으로 열린 `release/*` PR이 있으면 새 릴리스를 시작하지 않고 대기 상태를 보고. §6 재개 문단의 `gh pr view <PR번호>`는 `gh pr view release/<릴리스 버전>`(브랜치명 인자)으로 교체.
- **anchor 통일** — `release/SKILL.md` §2의 `git describe`를 glob+versionsort 규칙으로 교체. 태그 나열을 지시하는 다른 스킬 프로즈(backfill·train 등)에도 `-c versionsort.suffix=-`를 병기해 정렬 규칙을 전 스킬 일관화.
- **release-train** — 프리뷰 절에 `{{#if repo.tagTriggersDeployment}}` ⚠️ 경고 블록 추가(다른 3개 스킬과 동일 문구).
- **hotfix** — Release 생성 절에 "태그 버전이 저장소 최신 릴리스보다 낮으면 `gh release create`에 `--latest=false`" 1줄, 백포트 절에 "라인 CHANGELOG에 쓴 항목의 main CHANGELOG 반영 여부 확인" 1줄.

바이트 불변 규율: 신규 조건 블록은 개행을 `{{#if}}` 안에 두어 비해당 config에서 0바이트 collapse. 단 preflight 6 문구와 anchor 문구는 무조건 렌더되는 라인이라 **전 골든 diff가 의도된 결과**다 — `update_golden.py` 후 diff가 해당 문구 라인에 한정되는지 검증한다.

## C. validate_config 강화 (render.py — 규칙만 추가, 엔진 불변)

1. `scheme.type` ∈ {`semver`, `calver`, `headver`} — 그 외 값 거부(메시지에 sequential은 후속임을 언급).
2. calver/headver scope: `preRelease.style`이 `"none"`이 아니거나 `postRelease.bump`이 `"none"`이 아니면 거부.
3. versionLocations 항목 검증: `file` 필수 / `type` ∈ {`properties-key`, `json-path`, `regex`} / type별 필수 키(`key`/`path`/`pattern`) / regex는 컴파일 가능 + `re.compile(p).groups == 1`.
4. `github.release: true`인데 `tag.enabled: false`인 scope가 있으면 거부 (예: `"github.release requires every scope to have tag.enabled: GitHub Releases are tag-based"`). 역방향도 동일 논리로 거부: `notes.destinations`에 `github-release`가 있는 scope가 존재하는데 `github.release`가 false면 §5의 "7단계 Release 본문으로 사용" 참조가 dangling이 된다.

마이그레이션 노트: 기존에 렌더를 통과하던 잘못된 config(calver×mutable, tagless×github-release, 불량 location)는 재init 시 거부된다 — 에러 메시지가 교정 방향을 안내하므로 별도 마이그레이션 없음. 스키마 형태는 불변이라 `configVersion`은 1 유지.

## D. 테스트

- **골든 신설 4종** (기존 14 → 18):
  - `headver-app` — scheme `{type: "headver", pattern: "1"}`, preRelease none, postRelease none (규칙 C-2 준수). release §3의 비-semver 분기 고정.
  - `fixed-monorepo` — kind monorepo + strategy fixed, 단일 root scope에 versionLocations 2개(두 패키지의 package.json). fixed가 단일 레포 흐름과 동일함을 스냅샷으로 고정.
  - `tagless-app` — `tag.enabled: false` + `anchor.type: "ref"` + `github.release: false` + destinations `["changelog"]` + direct-push. preflight 6 게이트·§7 collapse·§8 anchor 갱신 프로즈 고정.
  - `monorepo-release-pr` — monorepo independent + `releasePath: "release-pr"`. release-monorepo의 release-pr 분기 + 신규 중복 가드 블록 고정.
- **validate 음성 테스트**: 신규 규칙 4종 각 1케이스 + 기존 규칙(빈 config 통짜 1개뿐)을 규칙별 케이스로 개별화.
- **스크립트 단위 테스트**: regex 다중 그룹 exit 2 / rc 태그가 anchor로 잡히지 않음 / scope 밖 rename의 삭제 감지 / `enabled` 키 생략 시 tagged 취급 / CalVer 동일 기간 exit 1.
- **골든 결정론 하드닝**: 테스트·update_golden 실행 시 `GIT_CEILING_DIRECTORIES`(또는 동등 수단)로 render `project_name`의 git walk-up이 TMPDIR 위치에 좌우되지 않게 고정.

## 제약·검증

- 동결 template dialect, 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진(토크나이저·파서·파이프라인) 무변경 — Python 변경은 validate_config 규칙 추가와 자산 스크립트 3종의 버그 픽스뿐.
- 자립성: 생성물은 `.superrelease/`·`.claude/` 상대 경로만. 플러그인 경로 참조 금지.
- Python 3.9+ stdlib, exit 0/1/2, 코드·메시지 영어 / 생성 문서·프로즈 한국어.
- TDD. 전체 스위트 + `claude plugin validate . --strict` + 골든 범위 확인(`git status --porcelain tests/golden`이 의도한 트리만).

## 비범위 (후속)

- gitflow·`repo.branching` 죽은 필드 처리 — M4b.
- 스캔 커버리지(Maven pom.xml·Gradle 모노레포·VERSION 등)·PEP 440 문서화 — M4c.
- README 로드맵/생성물 표/Uninstall 드리프트, 업그레이드 스토리, init 요약 개선, 신규 레포 버전 파일 부트스트랩, config 스키마 문서 — M4d.
- changed-packages 루트 공유 파일 "unassigned" 노출 — 동작 변경이라 별도 논의(M4b 또는 후속).
- references 지식을 생성물로 렌더하는 구조 개선 — anchor 건은 B절 프로즈 직접 반영으로 해소, 구조 논의는 후속.
- tagless scope의 anchor.value 기반 중단 감지.

## 예상 태스크 (writing-plans에서 확정)

1. 자산 스크립트 3종 버그 픽스 — TDD(단위 테스트 5건 선행).
2. validate_config 규칙 4종 추가 — TDD(음성 테스트 규칙별).
3. 생성 스킬 수정(preflight 6 재작성 · release-pr 가드 · anchor 통일 · train 경고 · hotfix 마감) + 렌더 스모크.
4. 골든 4종 신설 + 전면 재생성 + diff 범위 검증(문구 라인 한정 확인).
5. 결정론 하드닝(GIT_CEILING_DIRECTORIES) + 전체 스위트 + plugin validate 최종 검증.
