---
name: release-notes
description: {{project.name}} 모노레포의 패키지별 릴리스 노트 초안을 작성한다. 사용자가 릴리스 노트 써줘, 특정 패키지 릴리스 정리해줘, 체인지로그 정리, changelog, release notes 등 변경 요약·노트 작성 관련 요청을 하면 반드시 이 스킬을 사용한다. release 스킬이 5단계에서 재사용한다.
---

# release-notes — 패키지별 노트 초안 (부작용 없음)

이 스킬은 파일을 수정하거나 커밋·push하지 않는다. 초안 작성과 피드백 반영까지만 한다.

## 절차

1. 대상 scope 확정: 사용자가 지정하지 않았으면 `python3 .superrelease/scripts/changed-packages.py --json`으로 변경 있는 scope를 보여주고 선택받아라.
2. 범위 산출: 그 scope의 anchor(changed-packages 출력)..HEAD에서 `-- <scope.path>` 커밋만.
3. 소스 수집:
   - {{#if repo.mergePolicy == "squash"}}squash 레포: **PR 메타데이터가 1차 소스** — 커밋 제목의 `(#N)`으로 PR 번호를 얻고 `gh pr view <N> --json title,body,labels,closingIssuesReferences`로 읽어라. 커밋 메시지는 보조.{{else}}커밋 메시지(Conventional Commits)가 1차 소스, PR 메타데이터는 보조.{{/if}}
   - diff는 변경 의도가 모호할 때만 확인하라 (토큰 비용 유의).
4. 분류: Breaking(라벨, 타입 뒤 `!`, BREAKING CHANGE 푸터) / 기능 / 수정 / 기타. chore·릴리스 커밋 자체는 제외. 의존성 전파로 만들어진 릴리스라면 "의존성 <scope> <version> 반영"이 본문의 핵심이다.
5. 작성: `.superrelease/templates/` 아래 그 scope의 config `notes.template`(기본 notes-package.md) 구조를 따르고, 언어·독자·어조도 그 scope의 `notes.*` 값을 따르라. {package}에는 scope 이름, {version}·{date}는 작성 시점 값을 채운다.
6. 초안을 보여주고 피드백을 반영하라. 저장·게시는 release 스킬의 몫이다.
