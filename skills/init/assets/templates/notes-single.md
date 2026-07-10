{{#unless scope.notes.language == "en"}}<!-- 릴리스 노트 구조 템플릿. {version}, {date}는 노트 작성 시점에 채운다. 해당 없는 섹션은 생략한다. -->
# {{project.name}} {version} — {date}

## 하이라이트
<!-- 가장 중요한 변경 1~3개를 한 문단으로 -->

## 변경 사항
<!-- - 사용자 관점 요약 (#PR번호) -->

## Breaking Changes
<!-- 없으면 섹션 삭제. 있으면 마이그레이션 가이드 필수 -->

## 마이그레이션 가이드
<!-- 이전 → 이후 코드/설정 예시 -->
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Release-note template. Fill {version} and {date} when drafting; drop empty sections. -->
# {{project.name}} {version} — {date}

## Highlights

## Changes

## Breaking Changes

## Migration Guide
{{/unless}}
