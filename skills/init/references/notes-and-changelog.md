# 릴리스 노트와 CHANGELOG

릴리스 노트를 어디에 남길지는 프로젝트마다 다르고, 여러 목적지를 동시에 쓰는 경우도 흔하다.

## 목적지 5종

**① 루트 CHANGELOG.md 누적**: Keep a Changelog 형식을 따라 `Added` / `Changed` / `Fixed` / `Removed` 같은 하위 섹션으로 항목을 쌓는다.

Keep a Changelog 관례는 최신 릴리스를 파일 맨 위에, 과거 릴리스일수록 아래로 내려가도록 배치한다. 아직 릴리스되지 않은 변경 사항을 모아두는 `Unreleased` 섹션을 맨 위에 별도로 둔다. 릴리스마다 이 `Unreleased` 아래(또는 없다면 파일 맨 위)에 새 항목을 추가하는 방식이다.

**② per-release 파일**: `docs/releases/{version}.md`처럼 릴리스마다 독립된 파일을 만든다.

과거 릴리스 노트를 하나의 거대한 파일에 누적하지 않고 릴리스 단위로 쪼개 관리한다.

**③ GitHub Release만**: 레포 안에 파일을 남기지 않고 GitHub Release 페이지에만 노트를 게시한다.

**④ fragment(조각) 방식**: `changelog.d/` 같은 디렉터리에 변경 하나당 작은 조각 파일을 커밋해두고, 릴리스 시점에 이를 모아 하나의 노트로 취합한다.

towncrier, changesets 계열 도구가 쓰는 방식이다. towncrier 계열은 조각 파일 이름에 이슈·PR 번호와 카테고리를 담는 관례(`142.feature.md`, `456.bugfix.md`)를 쓴다.

superrelease는 towncrier식 규약을 쓴다: `changelog.d/{id}.{category}.md`(예: `142.feature.md`). `id`는 PR·이슈 번호나 slug, `category`는 노트 섹션에 매핑된다 — `breaking`→Breaking Changes, `feature`→하이라이트·변경 사항, `fix`·`misc`(및 미인식)→변경 사항. 릴리스 시 release 스킬이 조각을 취합해 노트 소스로 쓰고 **소비한 조각을 릴리스 커밋에서 삭제**한다. superrelease는 조각을 **취합만** 하며 생성하지 않는다(조각은 기여자가 PR에서 직접 추가하는 규약). category는 노트 그룹핑 전용이고 bump 결정에는 쓰지 않는다. fragment는 노트 소스이므로 **최소 1개 sink 목적지**(changelog/release-file/github-release/tag-message)와 함께 써야 한다 — 단독이면 취합·삭제 후 노트가 유실되어 render가 거부한다.

이 방식의 장점은 두 가지다.

- 여러 PR이 CHANGELOG.md라는 파일 하나를 동시에 고치면서 생기는 병합 충돌을 없앤다.
- 각 변경의 작성자가 그 변경을 가장 잘 아는 시점(PR을 올릴 때)에 직접 노트를 남기게 해 노트 품질도 함께 끌어올린다.

**⑤ annotated tag 메시지 내장**: 별도 파일 없이 git 태그의 annotated 메시지 자체에 노트를 담는다.

다섯 목적지를 한눈에 정리하면 다음과 같다.

| 목적지 | 어디에 남는가 | 지원 |
|---|---|---|
| changelog | 루트 CHANGELOG.md | 지원 |
| release-file | `docs/releases/{version}.md` | 지원 |
| github-release | GitHub Release 페이지 | 지원 |
| fragment | `changelog.d/` 조각 → 취합 | 지원 |
| tag-message | annotated 태그 메시지 | 지원 |

## 조합

여러 목적지를 함께 쓰는 조합이 오히려 일반적이다. config의 `notes.destinations`는 배열이라 여러 목적지를 동시에 선택할 수 있다.

자주 쓰이는 조합 예시:

- `changelog + github-release`: 레포에 이력을 남기면서 동시에 GitHub 알림도 원하는 팀.
- `release-file + github-release`: 릴리스별로 상세 문서 페이지를 남기고 싶은 팀.
- `fragment + changelog + github-release`: 여러 기여자가 각자 조각으로 노트를 쓰고, 이를 모아 누적 CHANGELOG와 GitHub Release 두 곳에 동시에 반영하는 팀.

## 하이브리드: generate-notes + release.yml

`gh release create --generate-notes`는 GitHub이 PR 라벨을 기준으로 카테고리별 뼈대 노트를 자동 생성해주는 기능이다.

어떤 라벨이 어떤 카테고리(예: Breaking Changes, New Features, Bug Fixes)로 묶일지는 `.github/release.yml`에서 라벨 기반으로 정의한다.

superrelease는 이 뼈대를 받아온 뒤 그 위에 LLM이 사람이 읽기 좋은 문장으로 가공하는 하이브리드 방식을 취한다 — 완전히 백지에서 쓰지도, GitHub이 만든 뼈대를 그대로 게시하지도 않는다.

`.github/release.yml`은 대략 다음과 같은 형태로 라벨과 카테고리를 매핑한다.

```yaml
changelog:
  categories:
    - title: Breaking Changes
      labels: [breaking-change]
    - title: New Features
      labels: [feature]
    - title: Bug Fixes
      labels: [bug]
```

이렇게 정의해두면 `--generate-notes`가 PR에 붙은 라벨을 보고 각 항목을 알맞은 카테고리 아래로 자동 분류해준다.

## 독자·언어·어조

같은 변경이라도 노트를 누가 읽는지에 따라 쓰는 방식이 달라진다.

- **독자**: 개발자 대상이면 API 시그니처, 설정 키, 마이그레이션 절차처럼 기술적인 세부가 중요해진다. 최종 사용자 대상이면 "무엇이 더 좋아졌는지"를 중심으로 쓰고 내부 구현 용어는 피한다.
- **언어**: `ko` / `en` / `both` 중 config `notes.language`에 따라 결정된다. `both`면 두 언어 블록을 모두 렌더링한다.
- **어조**: 담백한 사실 전달(neutral)부터 격식체, 캐주얼한 톤까지 config로 조정한다.

worked example — 로그인 방식이 변경됐다는 같은 사실도 독자에 따라 이렇게 달라진다.

- 개발자 대상: "`POST /auth/login` 요청 바디의 `username` 필드가 `email`로 이름이 바뀌었습니다(#128)"
- 최종 사용자 대상: "이제 이메일로 더 간편하게 로그인할 수 있습니다"

세 축은 서로 독립적으로 조합되므로, 같은 변경이라도 독자·언어·어조 설정에 따라 문장이 완전히 달라질 수 있다.

## 지원 범위

**다섯 목적지 모두 지원된다** — `changelog` / `release-file` / `github-release` / `fragment` / `tag-message`.

`tag-message`는 노트 전문을 annotated 태그 메시지에 `git tag -a <태그> -F <노트 파일>`(signed면 `-s ... -F`)로 넣는다. plain 태그나 태그를 안 쓰는 scope에는 적용할 수 없어 init·render가 그 조합을 막는다.

release-file이 M1에 포함된 이유는 렌더링 비용이 낮기 때문이다 — 이미 갖고 있는 노트를 파일로 한 번 더 쓰는 것뿐이라 추가 구현 부담이 거의 없다. 반면 fragment는 조각 파일 규약과 취합 로직을, tag-message는 별도의 릴리스 플로우 연동을 새로 설계해야 해서 M3로 미뤄졌다가 이후 M3c에서 구현됐다.

Keep a Changelog 형식 참고: [keepachangelog.com](https://keepachangelog.com/)
