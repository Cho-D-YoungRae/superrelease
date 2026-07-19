{{#unless scope.notes.language == "en"}}<!-- 라운드 묶음 릴리스 노트 템플릿. {round}, {date}는 작성 시점에 채운다. 해당 없는 섹션은 생략한다. -->
# {{project.name}} {round} — {date}

## 포함 버전
<!-- | 패키지 | 버전 | 이번 라운드 | 표 — 릴리스된 scope와 미변경 scope의 현재 버전을 모두 적는다 -->

## 하이라이트
<!-- 라운드 전체에서 가장 중요한 변경 1~3개를 한 문단으로 -->

## 패키지별 변경
<!-- ### <scope> <version> 소제목 아래 사용자 관점 요약 (#PR번호) -->

## Breaking Changes
<!-- 없으면 섹션 삭제. 있으면 scope 명시 + 마이그레이션 가이드 필수 -->
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Bundle round release-note template. Fill {round} and {date} when drafting; drop empty sections. -->
# {{project.name}} {round} — {date}

## Included Versions
<!-- | Package | Version | This round | — released scopes plus unchanged scopes' current versions -->

## Highlights

## Per-package Changes

## Breaking Changes
{{/unless}}
