{{#unless scope.notes.language == "en"}}<!-- 릴리스 PR 본문 템플릿. {version} 등은 PR 생성 시점에 채운다. -->
## 릴리스 {version}

<!-- 하이라이트 1~3개를 한 문단으로 -->

### 이 PR에 대해

- 버전 파일과 릴리스 노트만 변경한다 (기능 변경 없음).
- 머지되면 {{#if derived.anyTagEnabled}}{version} 태그{{#if github.release}}와 GitHub Release{{/if}} 생성이 이어진다{{else}}릴리스 후처리(back-merge 등)가 이어진다{{/if}} — 머지 후 릴리스 재개를 요청하라.
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Release-PR body template. Fill {version} when opening the PR. -->
## Release {version}

### About this PR

- Touches version files and release notes only (no functional change).
- Merging {{#if derived.anyTagEnabled}}unblocks the {version} tag{{#if github.release}} and GitHub Release{{/if}}{{else}}unblocks release post-processing (back-merge, etc.){{/if}} — ask to resume the release afterwards.
{{/unless}}
