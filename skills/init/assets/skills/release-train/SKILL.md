---
name: release-train
description: {{project.name}} 모노레포의 루트 release train을 릴리스한다. 사용자가 train 릴리스, 릴리스 트레인, 통합 릴리스, 루트 릴리스, train 태그 따줘, 이번 train에 뭐 들어가, 다음 train 버전, release train 등 패키지 개별이 아닌 루트 train 단위 릴리스를 요청하면 반드시 이 스킬을 사용한다.
---

# release-train — {{project.name}} 루트 release train 릴리스

이 레포는 이중 체계다 — 패키지는 각자 SemVer로 개별 릴리스하고(release 스킬), 루트 **release train**은 그 패키지들의 마지막 릴리스 버전 조합을 하나의 CalVer 버전으로 묶어 스냅샷한다. 이 스킬은 **루트 train 릴리스 전용**이며 패키지 개별 릴리스와 별개의 릴리스 타입이다. 정책 SSOT는 `.superrelease/config.json`의 `train` 객체다.

공통 규칙:

- 버전 산술은 스크립트로만: `python3 .superrelease/scripts/<script>` (Windows는 `py -3`).
- 부작용 있는 동작(파일 수정, 커밋, push, 태그{{#if github.release}}, Release 생성{{/if}})은 **dry-run 프리뷰 → 사용자 확인 → 실행**. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
- train은 **패키지 버전 파일을 수정하지 않는다** — 스냅샷은 읽기 전용이고, 이 스킬이 쓰는 것은 통합 노트 파일과 train 태그뿐이다. 버전 bump·패키지 태그는 release 스킬 소관이다.
{{#if github.release}}- GitHub 접근: gh CLI 우선. 미가용이면 연결된 GitHub MCP 도구를 찾아 쓰고, 둘 다 없으면 "태그까지만" 제한 모드를 제안하라.{{/if}}

status 모드: "이번 train에 뭐 들어가", "다음 train 버전" 류 요청은 2~4단계만 수행해 스냅샷·다음 버전을 보고하고 멈춘다.

## 1. preflight — 모두 통과해야 진행

1. 현재 브랜치: `git branch --show-current` 결과가 `{{repo.defaultBranch}}` 여야 함
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{repo.defaultBranch}} --count` 가 0
{{#if github.release}}4. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
5. 중단된 패키지 릴리스 확인: 어떤 패키지 scope의 파일 버전(수식어 제외)이 마지막 태그보다 높은데 그 버전 태그가 없으면 개별 릴리스가 진행 중인 것 — train은 릴리스된 조합을 묶으므로, 먼저 그 패키지 릴리스를 마치라고 안내하고 멈춰라.

## 2. 현재 train 버전

- `git tag --list`로 태그를 모으고 `{{train.tag.format}}` 포맷({version} 자리에 CalVer)에 맞는 태그만 남긴다.
- 버전 순으로 정렬해 최신 태그에서 접두사를 떼면 현재 train 버전이다. 맞는 태그가 하나도 없으면 **첫 train**이다.

## 3. 다음 train 버전

- 계산은 스크립트로만(LLM 산술 금지): `python3 .superrelease/scripts/next-version.py --current <현재 train 버전> --scheme calver --pattern {{train.scheme.pattern}} --today <오늘 YYYY-MM-DD>`.
- **첫 train**이면 `--current ""`(빈 문자열)로 호출한다. 같은 기간이면 MICRO를 증가시키고, 기간이 바뀌면 0으로 리셋하며, 첫 train은 MICRO 0이다.

## 4. 패키지 버전 스냅샷

- `python3 .superrelease/scripts/changed-packages.py --json`을 실행한다 — 스크립트가 scope마다 자기 마지막 태그(anchor)를 내부적으로 해석한다. anchor는 그 scope `tag.format`의 전체 태그 문자열(예: `pkg-a@1.2.3`)이므로, 네임스페이스(`<scope>@`) 부분을 벗긴 버전이 그 패키지의 **마지막 릴리스 버전**이다.
- anchor가 태그가 아닌 scope(tagless — anchor가 커밋 sha)는 `python3 .superrelease/scripts/version.py get --scope <이름>`으로 파일 버전을 폴백하되, `-SNAPSHOT`·`-dev` 등 개발 수식어가 붙어 있으면 "미릴리스 개발 버전"으로 표시하라.
- 결과를 (패키지 | 버전) 표로 정리한다 — 이 조합이 train이 고정하는 스냅샷이다.

## 5. 통합 노트

- `.claude/skills/release-notes/SKILL.md` 절차로 train 통합 노트 초안을 쓴다. 소스는 각 scope의 `<anchor>..HEAD` 커밋이다: `git log <anchor>..HEAD --pretty=format:"%h %s" -- <scope.path>`{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}.
- `.superrelease/templates/notes-train.md` 골격으로 작성한다: 4단계 스냅샷 표 + 하이라이트 + 주요 변경 + 포함 패키지들의 Breaking Changes rollup.

## 6. dry-run 프리뷰 → 커밋{{#if repo.releasePath == "release-pr"}}/PR{{/if}}

프리뷰에 다음을 보여주고 확인받아라:

- 패키지 버전 스냅샷 표
- 다음 train 버전과 생성될 태그명(`{{train.tag.format}}`의 {version}에 다음 버전 대입)
- 실행될 명령 목록(노트 커밋, {{#if repo.releasePath == "release-pr"}}PR 생성{{else}}push{{/if}}, 태그{{#if github.release}}, Release{{/if}})
- 통합 노트 미리보기

{{#if repo.releasePath == "direct-push"}}확인 후: 통합 노트 파일을 커밋하고 `git push origin {{repo.defaultBranch}}`. 이어서 7단계.{{else}}확인 후 **릴리스 PR 경로**: `release/train-<다음 버전>` 브랜치를 만들어 통합 노트 커밋을 쌓고 push → PR 1건 생성(`gh pr create --base {{repo.defaultBranch}}` — 본문에 스냅샷 표와 통합 노트를 넣어라; gh 미가용이면 GitHub MCP 폴백) → **중단**(태그는 머지 후). 머지 후 재개: PR 머지를 확인하고 `git checkout {{repo.defaultBranch}} && git pull` 한 뒤 7단계부터 이어가라. PR이 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}

## 7. train 태그{{#if github.release}} + GitHub Release{{/if}}

- push 직전 충돌 재확인: `git ls-remote --tags origin <태그>` 가 비어 있어야 함 — 결과가 있으면 **즉시 중단**(동시 릴리스 락, 버전 재사용 금지).
- 태그 생성: {{#if train.tag.signed}}`git tag -s <태그> -F <통합 노트 파일>`{{else}}{{#if train.tag.annotated}}`git tag -a <태그> -F <통합 노트 파일>`{{else}}`git tag <태그>` — lightweight 태그라 노트는 통합 노트 파일에만 남는다{{/if}}{{/if}} → `git push origin <태그>`.
{{#if github.release}}- gh 경로: `gh release create <태그> --title "<태그>" --notes-file <통합 노트 파일>`
- MCP 폴백: 5단계 통합 노트로 Release를 생성하라.
{{/if}}

## 실패 시

어디까지 진행됐는지(노트 커밋 / {{#if repo.releasePath == "release-pr"}}PR / {{/if}}태그{{#if github.release}} / Release{{/if}}) 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 train은 다음 train으로 덮는다.
