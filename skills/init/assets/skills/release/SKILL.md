---
name: release
description: {{project.name}} 프로젝트의 릴리스를 수행한다. 사용자가 릴리스해줘, 버전 올려, bump, 태그 따줘, release, 릴리스 준비됐는지 봐줘, 다음 버전 뭐가 될까 등 버전 결정·태그{{#if github.release}}·GitHub Release{{/if}}·릴리스 노트와 관련된 요청을 하면 반드시 이 스킬을 사용한다.
---

# release — {{project.name}} 릴리스 오케스트레이터

공통 규칙:

- 정책의 SSOT는 `.superrelease/config.json`이다. 이 문서에 없는 세부 값은 config에서 읽어라.
- 버전 문자열의 파싱·산술·파일 수정은 직접 하지 말고 반드시 `.superrelease/scripts/`를 호출하라 (`python3`, Windows는 `py -3`).
- 부작용 있는 모든 동작(파일 수정, 커밋, push, 태그, Release 생성)은 **dry-run 프리뷰 → 사용자 확인 → 실행** 순서를 지켜라. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
{{#if github.release}}- GitHub 접근: gh CLI 우선. gh 미가용이면 연결된 GitHub MCP 도구를 찾아 쓰고, 둘 다 없으면 "태그까지만 진행"하는 제한 모드를 제안하라.{{/if}}

status 모드: "릴리스 준비됐는지", "다음 버전 뭐가 될까" 류 요청은 1~3단계만 수행하고 보고 후 멈춘다.

## 1. preflight — 모두 통과해야 진행

1. 현재 브랜치: `git branch --show-current` 결과가 `{{repo.defaultBranch}}` 여야 함
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{repo.defaultBranch}} --count` 가 0
4. 버전 위치 일치: `python3 .superrelease/scripts/version.py verify` → exit 0
{{#if github.release}}5. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인
{{/if}}{{#if scope.tag.enabled}}6. 중단 상태 감지: 마지막 릴리스 태그가 존재하고 파일 버전이 그보다 높은데 **파일 버전 그대로의 태그가 없으면** 이전 릴리스가 중단된 것이다{{#if scope.preRelease.style == "mutable"}} (단, 파일 버전에 `-{{scope.preRelease.qualifier}}` 수식어가 붙어 있으면 정상 개발 상태 — 중단 아님){{/if}} — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.
{{/if}}{{#if repo.releasePath == "release-pr"}}7. 열린 릴리스 PR 확인: `gh pr list --state open --json headRefName,url` 결과에 `release/`로 시작하는 head 브랜치의 PR이 있으면 이전 릴리스가 머지 대기 중이다 — 새 릴리스를 시작하지 말고 그 PR 상태를 보고하고 멈춰라(머지 후 재개는 6번이 잡는다).
{{/if}}
실패 항목이 있으면 이유와 해결 방법을 보여주고 중단하라.

## 2. 범위 산출

- anchor: {{#if scope.tag.enabled}}마지막 릴리스 태그 — `git describe --tags --abbrev=0`{{else}}config의 `scopes[].anchor.value`{{/if}}
- anchor가 없으면 **첫 릴리스**: 커밋 전체를 나열하지 말고 "Initial release"로 다뤄라.
- 수집: `git log <anchor>..HEAD --pretty=format:"%h %s"`{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}

## 3. {{#if scope.scheme.type == "semver"}}bump 제안{{else}}다음 버전 산출{{/if}}

{{#if scope.scheme.type == "semver"}}- config `scopes[].bump.sources` 순서로 분석하라. 모호하면 fallback(diff)으로 검증하되 토큰 비용에 유의.
- 매핑: feat → minor, fix → patch, BREAKING CHANGE 푸터 또는 타입 뒤 `!` → major.
- **0.x 버전에서는** breaking → minor, feat → patch 관례를 적용하고 그 사실을 함께 표기하라.
- 제시 형식: "**minor 제안** — 근거: feat 커밋 2건(제목 나열)" → 확인 또는 수동 지정.
- 버전 문자열 계산은 스크립트로만:
  - 현재: `python3 .superrelease/scripts/version.py get`
{{#if scope.preRelease.qualifier}}  - 릴리스 버전(수식어 제거): `python3 .superrelease/scripts/next-version.py --release`
{{/if}}  - bump 적용: `python3 .superrelease/scripts/next-version.py --bump <level>`{{#if scope.preRelease.style == "counter"}}
  - pre-release 발행: 첫 발행은 `python3 .superrelease/scripts/next-version.py --bump <level> --prerelease {{scope.preRelease.qualifier}}`, 반복 발행은 `--prerelease {{scope.preRelease.qualifier}}`만(카운터 자동 증가), 정식 승격은 `--release`{{/if}}{{else}}- {{scope.scheme.type}} 체계에는 bump 수준 개념이 없다 — 다음 버전은 날짜·카운터가 결정한다: `python3 .superrelease/scripts/next-version.py` (config의 scheme·pattern을 자동 사용). 변경 내용은 2단계 수집분으로 노트에만 반영하고 버전 결정에는 쓰지 않는다.{{/if}}

## 4. 버전 반영

`python3 .superrelease/scripts/version.py set <릴리스 버전>` — 전 위치 동기 수정. 실행 전 6단계 프리뷰에 포함하라.

## 5. 릴리스 노트

`.claude/skills/release-notes/SKILL.md` 절차로 초안을 작성하고, config `scopes[].notes.destinations`의 목적지별로 반영하라:

{{#each scope.notes.destinations}}{{#if this == "fragment"}}노트 소스로 `changelog.d/*.md` 조각을 category별로 취합하라 — 파일명 `{id}.{category}.md`의 category가 `breaking`이면 Breaking Changes, `feature`면 하이라이트·변경 사항, `fix`·`misc`(및 미인식)이면 변경 사항에 넣는다. 취합한 조각 파일은 릴리스 커밋에서 `git rm`으로 삭제하고 6단계 프리뷰에 명시하라(bump 결정에는 쓰지 않는다 — bump는 커밋·PR 소스 그대로).

{{/if}}{{/each}}- `changelog`: `.superrelease/templates/changelog-entry.md` 골격으로 CHANGELOG.md 최신 항목으로 삽입 (Unreleased 섹션이 있으면 그 아래)
- `release-file`: `{{scope.notes.perReleasePath}}{version}.md` 파일 생성 (`{{scope.notes.template}}` 사용)
- `github-release`: 7단계 Release 본문으로 사용{{#each scope.notes.destinations}}{{#if this == "tag-message"}}
- `tag-message`: 7단계 태그 메시지에 노트 전문을 넣는다(아래 참조){{/if}}{{/each}}

## 6. dry-run 프리뷰 → 커밋

표준 프리뷰를 보여주고 확인받아라:

- 바뀔 파일과 버전 diff (위치별 old → new)
- 생성될 커밋 메시지(`{{repo.releaseCommitFormat}}` 의 {version} 치환)와 태그명
- 실행될 명령 목록 (push, Release 생성 등)
{{#if repo.tagTriggersDeployment}}- ⚠️ **이 태그는 CI 배포를 트리거합니다** — 프리뷰에 반드시 명시
{{/if}}- 릴리스 노트 미리보기

{{#if repo.releasePath == "direct-push"}}확인 후: 버전 파일 + 노트 파일을 스테이징해 커밋하고 `git push origin {{repo.defaultBranch}}`.{{else}}확인 후 **릴리스 PR 경로**로 진행한다 (protected branch — 직접 push 금지):

1. `git checkout -b release/<릴리스 버전>` → 버전 파일 + 노트 파일 커밋 → `git push -u origin release/<릴리스 버전>`
2. PR 생성: `gh pr create --base {{repo.defaultBranch}} --head release/<릴리스 버전> --title "<릴리스 커밋 메시지와 동일>" --body-file <본문 파일>` — 본문은 `.superrelease/templates/release-pr-body.md` 골격을 채워 작성하라 (gh 미가용이면 GitHub MCP 폴백)
3. **여기서 중단한다** — 태그·Release는 PR 머지 후다. "PR이 머지되면 다시 릴리스를 요청하세요"라고 안내하라.

머지 후 재개: 1단계 preflight 6(중단 상태 감지)이 이 대기 상태를 잡는다. PR 머지 여부를 확인(`gh pr view release/<릴리스 버전> --json state,mergedAt` — head 브랜치명으로 조회)한 뒤 `git checkout {{repo.defaultBranch}} && git pull`로 머지 커밋을 받아 7단계(태그)부터 이어가라 — 태그는 머지 후 HEAD에 만든다(squash 머지로 sha가 바뀐다). PR이 아직 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}

## 7. 태그{{#if github.release}} + GitHub Release{{/if}}

{{#if scope.tag.enabled}}- 태그명: `{{scope.tag.format}}` 의 {version}에 릴리스 버전 대입
- push 직전 충돌 재확인: `git ls-remote --tags origin <태그>` 가 비어 있어야 함 — 결과가 있으면 **즉시 중단** (동시 릴리스 락, 버전 재사용 금지)
- {{#if scope.tag.signed}}signed 태그: `git tag -s <태그> -m "<한 줄 요약>"`{{else}}{{#if scope.tag.annotated}}annotated 태그: `git tag -a <태그> -m "<한 줄 요약>"`{{else}}태그: `git tag <태그>`{{/if}}{{/if}} → `git push origin <태그>`{{#each scope.notes.destinations}}{{#if this == "tag-message"}}
- **tag-message**: 위 태그 명령의 `-m "<한 줄 요약>"`를 `-F <노트 파일>`로 바꿔 5단계 노트 전문을 태그 메시지에 넣어라 (annotated/signed 태그에만 유효){{/if}}{{/each}}{{#if scope.tag.movingMajorTag}}
- **moving major tag**: 정식 릴리스(수식어 없는 버전)에 한해 `git tag -f v<major>` → `git push -f origin v<major>` — force-push이므로 프리뷰에 별도 경고를 명시하고 개별 확인을 받아라. pre-release에는 옮기지 않는다{{/if}}
{{/if}}{{#if github.release}}- gh 경로: {{#if github.generateNotes}}`gh api repos/{owner}/{repo}/releases/generate-notes -f tag_name=<태그>` 뼈대를 참고하되 본문은 5단계 노트로 게시 — {{/if}}`gh release create <태그> --title "<버전>" --notes-file <노트 파일>`{{#if scope.preRelease.style == "counter"}} (pre-release 버전이면 `--prerelease` 플래그를 추가하고, 승격 릴리스에는 붙이지 않는다){{/if}}
- MCP 폴백 경로: generate-notes 뼈대 없이 5단계 노트로 Release를 생성하라.
{{/if}}

## 8. post-release

{{#if scope.postRelease.bump == "next-snapshot"}}릴리스 직후 다음 개발 버전으로 복귀한다 (기본 patch 증가, 다음 계획이 minor면 조정 확인):

`python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.releasePath == "release-pr"}} (release-pr 레포: 이 복귀 커밋도 직접 push할 수 없다 — `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}}{{else}}post-release bump 없음 — 파일 버전은 릴리스 버전 그대로 둔다.{{/if}}
{{#unless scope.tag.enabled}}
태그를 쓰지 않는 설정이다 — 릴리스 후 `.superrelease/config.json`의 `scopes[].anchor.value`를 릴리스 커밋 sha로 갱신해 함께 커밋하라 (다음 릴리스의 범위 기준점이며, config에서 유일하게 상태를 갖는 필드다).
{{/unless}}

## 실패 시

어디까지 진행됐는지(파일 수정 / 커밋 / push / 태그 / Release)와 각 단계를 되돌리는 방법을 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 버전은 다음 패치로 덮고, 배포물 회수는 생태계 절차(npm deprecate, PyPI yank 등)를 안내하라.
