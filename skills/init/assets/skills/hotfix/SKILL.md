---
name: hotfix
description: {{project.name}} 프로젝트의 이미 릴리스된 버전에 핫픽스 패치 릴리스를 수행한다. 사용자가 핫픽스, hotfix, 긴급 패치, 구버전 패치, 유지보수 라인 릴리스, 1.2.x에 패치 등 과거 릴리스 수정과 관련된 요청을 하면 반드시 이 스킬을 사용한다.
---

# hotfix — {{project.name}} 유지보수 라인 패치 릴리스

이미 릴리스된 버전(예: 1.2.3)의 문제를 유지보수 라인(`release/1.2.x`)에서 고쳐 patch 릴리스(1.2.4)로 내보낸다. `{{repo.defaultBranch}}`의 최신 개발분은 포함하지 않는다. 이 스킬은 semver scope 전제다(patch bump).

공통 규칙은 release 스킬(`.claude/skills/release/SKILL.md`)과 동일하다:

- 버전 파싱·산술·파일 수정은 `.superrelease/scripts/`로만 (`python3`, Windows는 `py -3`).
- 부작용 있는 모든 동작은 **dry-run 프리뷰 → 사용자 확인 → 실행**.
{{#if github.release}}- GitHub 접근: gh CLI 우선, 미가용이면 GitHub MCP 폴백, 둘 다 없으면 태그까지만 진행하는 제한 모드.{{/if}}

## 1. 대상 결정

- 고칠 릴리스 버전을 확인한다(예: 1.2.3). 그 버전의 태그가 존재해야 한다 — 태그명은 config `scopes[].tag.format`의 {version} 대입.
- 유지보수 라인은 `release/<major>.<minor>.x`(예: `release/1.2.x`)다. `git branch -a --list "release/*"`로 존재를 확인하고, 없으면 태그에서 생성을 제안하라: `git branch release/1.2.x <태그>` → `git push -u origin release/1.2.x`.
- 수정이 이미 `{{repo.defaultBranch}}`에 커밋돼 있는지(체리픽 대상 sha), 라인에서 직접 고칠지 확인한다.

## 2. preflight

1. `git fetch origin` → `git checkout release/<라인>` → `git pull`
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 버전 위치 일치: `python3 .superrelease/scripts/version.py verify` → exit 0
{{#if github.release}}4. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}

## 3. 수정 반영

- `{{repo.defaultBranch}}`의 커밋을 가져오는 경우: `git cherry-pick -x <sha>` — 충돌이 나면 해결안을 사용자와 확인하며 진행하라.
- 라인에서 직접 고치는 경우: 일반 커밋으로 반영한다.

## 4. patch 버전·노트

- 다음 버전은 **patch 고정**: `python3 .superrelease/scripts/next-version.py --bump patch` (현재 버전은 라인의 파일에서 자동으로 읽힌다)
- 범위 anchor는 이 라인의 마지막 태그: 라인 체크아웃 상태에서 `git describe --tags --abbrev=0 --match '<glob>'` (`<glob>`은 config `scopes[].tag.format`의 `{version}`을 `*`로 치환 — 이 라인에서 도달 가능한, 포맷에 맞는 태그만)
- 버전 반영: `python3 .superrelease/scripts/version.py set <패치 버전>`
- 노트: `.claude/skills/release-notes/SKILL.md` 절차로 초안을 쓰고, config `scopes[].notes.destinations` 목적지 반영은 release 스킬 5단계와 동일하게 하라.

## 5. dry-run 프리뷰 → 커밋

release 스킬 6단계와 같은 표준 프리뷰(파일 diff·커밋 메시지·태그명·명령 목록{{#if repo.tagTriggersDeployment}}·⚠️ 태그의 CI 배포 트리거 경고{{/if}}·노트 미리보기)를 보여주고 확인받아라.

{{#if repo.releasePath == "direct-push"}}확인 후: 버전 파일 + 노트 파일을 커밋하고 `git push origin release/<라인>`.{{else}}확인 후(릴리스 PR 경로): `git checkout -b hotfix/<패치 버전>` → 커밋 → push → `gh pr create --base release/<라인> --head hotfix/<패치 버전>` — **base는 유지보수 라인이다**. PR 머지 후 재개해 6단계(태그)부터 이어가라. hotfix는 release 스킬과 달리 중단 상태를 자동 감지하지 않으니 — 머지 후 태그 단계를 **수동으로** 진행하고 체리픽·버전 반영을 반복하지 마라.{{/if}}

## 6. 태그{{#if github.release}} + GitHub Release{{/if}}

release 스킬 7단계와 동일하다: `git ls-remote --tags origin <태그>`로 충돌 재확인(결과가 있으면 즉시 중단) → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.{{#if github.release}}
- 이 패치 버전이 저장소의 최신 릴리스보다 낮으면(구버전 라인 백포트) `gh release create`에 `--latest=false`를 붙여 이 Release가 Latest로 마킹되지 않게 하라.{{/if}}
{{#if scope.tag.movingMajorTag}}- moving major tag는 이 핫픽스가 해당 major의 **최신 릴리스일 때만** 옮겨라 — 더 높은 minor/patch가 이미 릴리스돼 있으면 옮기지 않는다.{{/if}}

## 7. post-release와 {{repo.defaultBranch}} 반영

- {{#if scope.postRelease.bump == "next-snapshot"}}라인에도 동일 정책을 적용한다: `python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 5단계와 같은 경로로 프리뷰·확인 후 커밋.{{else}}post-release bump 없음 — 라인의 파일 버전은 릴리스 버전 그대로 둔다.{{/if}}
- 핫픽스 수정이 `{{repo.defaultBranch}}`에도 필요한지 확인하라. 라인에서 직접 고쳤다면 그 커밋의 체리픽 백을 제안하고, 원래 `{{repo.defaultBranch}}`에서 가져온 수정이면 불필요하다.{{#each scope.notes.destinations}}{{#if this == "changelog"}}
- 라인 CHANGELOG에 쓴 이 패치 버전 항목을 `{{repo.defaultBranch}}`의 CHANGELOG에도 반영할지 확인하라 — 빠뜨리면 기본 브랜치 릴리스 이력에 구멍이 남는다.{{/if}}{{/each}}

## 실패 시

어디까지 진행됐는지(체리픽 / 파일 수정 / 커밋 / push / 태그 / Release)와 되돌리는 방법을 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 버전은 다음 패치로 덮는다.
