---
name: init
description: 프로젝트의 버전·릴리스 관리를 초기화하거나 재구성한다. 사용자가 릴리스 관리 셋업, 버전 관리 초기화, superrelease init, 릴리스 정책 바꾸고 싶어, 릴리스 스킬 만들어줘, 모노레포에 패키지 추가했어(버전 관리 대상) 등을 말하면 반드시 이 스킬을 사용한다. release setup, versioning init 같은 영어 표현에도 사용한다.
---

# superrelease init — 프로젝트 전용 릴리스 툴킷 생성

대상 프로젝트를 스캔하고 질문한 뒤, 프로젝트 전용 릴리스 스킬·스크립트·설정·템플릿을 레포 안에 생성한다. 생성 후 일상 릴리스는 생성물만으로 수행된다 — 사용자는 "릴리스해줘"라고 말하면 된다.

절대 규칙:

- Phase 3(생성) 전에는 어떤 파일도 만들거나 수정하지 않는다. 스캔은 읽기 전용.
- 결정론 작업은 스크립트로: 스캔은 scan.py, 생성은 render.py. 스캔 수치를 손으로 재계산하지 않는다.
- 모든 결정을 근거와 함께 `config.decisions`에 기록한다.
- 질문은 AskUserQuestion으로 묶어서(호출당 최대 4문항). 스캔 추론치는 근거를 표기한 추천 옵션을 선두에 둔 확인형으로 묻는다.
- 아래 "지원 범위와 제약" 밖의 선택지는 "지원하지 않음"으로 표시하고 선택하지 못하게 한다(지원 약속을 하지 마라).

## 모드 감지

1. `.superrelease/config.json`이 존재하면 → **재init** (마지막 절로)
2. config가 없고 스캔 신호도 빈약하면(빌드 파일·태그·커밋이 거의 없음) → **신규 레포 제안 모드**: 레포 성격을 먼저 묻고, 성격별 권장 프리셋(라이브러리→SemVer+SNAPSHOT+next-snapshot / 앱→SemVer+dev 채널 선택 / Claude Code 플러그인→번들 1의 플러그인 프리셋 — 매니페스트가 아직 없어도 사용자가 플러그인 성격을 답하면 적용하고 `.claude-plugin/plugin.json` 생성을 Phase 3 렌더에 포함)을 제시한 뒤 아래 흐름을 그대로 진행. **버전 파일이 하나도 없으면**(versionLocations 후보 0건) Phase 3 자가검증(`version.py verify`)이 반드시 실패하므로, 성격에 맞는 버전 파일(예: `package.json`·`gradle.properties`·`VERSION`)과 초기 버전(0.1.0 등)을 Phase 3 렌더에 포함해 사용자 확인 후 함께 생성한다
3. 그 외 → **최초 init**

## Phase 1 — 스캔 (읽기 전용)

1. 실행: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/init/scripts/scan.py" --repo . --json`
   - python3가 없으면 중단하고 안내하라 — 생성물 스크립트도 Python 3.9+를 요구한다.
2. GitHub 확인 — 접근 계층: **gh CLI 우선 → 미가용 시 연결된 GitHub MCP 도구(런타임에 찾기) → 둘 다 없으면 사용자 질문으로 대체**:
   - protected branch + required checks: `gh api "repos/{owner}/{repo}/branches/<기본브랜치>/protection"` (404 = 미보호)
   - 기존 Releases, `.github/release.yml` 존재 여부, `gh auth status` 스코프
3. CI 태그 트리거 확정: 리포트 `ci.tagTriggerCandidates`의 각 워크플로 파일을 직접 읽고 태그 push가 실제 배포를 트리거하는지 판단한다. 참이면 config에 `repo.tagTriggersDeployment: true`로 기록한다.

## Phase 2 — 질문

**패스트트랙 먼저.** 스캔 결과로 아래 모든 결정의 추천값 표(항목 / 추천 / 근거)를 만들어 제시하고, 첫 질문으로 "모두 수락 / 항목별 조정"을 묻는다. 수락이면 바로 config 작성으로. 조정이면 해당 번들만(또는 전부) 순서대로 진행한다 — 상류 결정이 하류 기본값을 정하므로 순서를 지켜라.

깊은 배경이 필요할 때만 해당 reference를 읽어라:

| 번들 | reference |
|---|---|
| 1·2 | references/version-schemes.md, references/monorepo.md |
| 3 | references/bump-models.md |
| 4 | references/prerelease-and-dev-channel.md |
| 5 | references/notes-and-changelog.md |
| 6 | references/branching-and-release-path.md |
| 이상 신호(혼재 태그·버전 불일치·중단 흔적) | references/edge-cases.md |

- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). monorepo면 전략을 묻는다 — fixed(전 패키지 버전 공유) | independent(패키지별 독립). independent면 스캔 리포트 `monorepo.packages`(node·gradle 패키지가 `buildSystem` 필드로 구분되어 함께 온다)를 표로 제시해 scope 목록(이름 = 패키지 이름 또는 디렉터리명, path, 버전 파일)을 확정한다. fixed면 단일 root scope의 versionLocations에 전 패키지 버전 파일을 모은다(릴리스 흐름은 단일 레포와 동일). **(Claude Code 플러그인)** 스캔 `pluginManifest.detected`면 성격을 "Claude Code 플러그인"(app 계열 단일 레포)으로 선두 추천하고 프리셋을 제시한다 — SemVer · 버전 소스 `.claude-plugin/plugin.json`(json-path `version`) · tag `v{version}` · notes changelog+github-release · pre/post none(플러그인은 SNAPSHOT 관례 없음). 경로·브랜치·유지보수 라인은 번들 6을 따른다.
- **번들 2 — 체계·SSOT·태그**: 버전 체계 SemVer | CalVer | HeadVer (sequential 등 그 외 체계는 미지원 표시) — 라이브러리는 SemVer 사실상 강제, CalVer면 pattern(예: `YYYY.MM.MICRO` — 어휘 YYYY/YY/0M/MM/0D/DD/MICRO)을, HeadVer면 head 번호를 `scheme.pattern`에 기록한다 / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다(`usable: false` 후보는 위치로 제안하지 말고 감지 사실과 advice만 안내하라 — `maven-project-version`이면 pom의 project `<version>`은 regex로 parent/dependency와 구분할 수 없으니 versions-maven-plugin 운용 또는 CI-friendly `<revision>` property 전환을 권장) / **플러그인이면**(`pluginManifest.detected`) `.claude-plugin/plugin.json`을 기본 위치로 제안하고, `pluginManifest.marketplaceSelfListed`면 `.claude-plugin/marketplace.json`(`metadata.version`)을 2차 sync 위치로 함께 추천한다(두 매니페스트를 같은 버전으로 유지 — self-listed가 아니면 카탈로그 버전이므로 제안하지 않는다) / 태그 파생 여부(기본 yes; **gitflow면 "태그 없음"도 유효한 선택** — 범위 기준이 기본 브랜치라 태그 없이 성립하며, 단 github.release는 태그가 필요하므로 함께 비활성화됨을 안내)·prefix(v 유무)·annotated(기본 yes)·signed — independent 모노레포면 scope별 `tag.format` 기본값을 `<scope이름>@{version}` 네임스페이스로 제안한다 / moving major tag — semver+태그 사용 시 `v<major>` 유동 태그 운용 여부(force-push 수반을 경고하고 결정).
- **번들 3 — bump**: auto-confirm(기본) | manual / 소스 우선순위 — CC 사용률이 높으면 conventional-commits 우선, squash 레포면 pr-metadata 1차 / (라이브러리) compatCheck 도구(kotlin-bcv, japicmp) 기록 여부.
- **번들 4 — pre-release·dev·post**: 수식어 스타일 none | mutable(-SNAPSHOT류) | counter(-rc.N 등 불변 카운터 — qualifier 이름(rc/alpha/beta)을 확정하고, counter는 postRelease none을 기본 제안) / (앱·mutable) dev 채널 qualifier 이름과 불변 식별자 immutableId(spring-build-info | docker-sha-tag | npm-dev-suffix) — config 기록 + 설정 스니펫 안내만, 배포 자동화는 하지 않음 / post-release bump — 라이브러리→next-snapshot 기본, 앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안) / pyproject.toml이 버전 후보에 있으면 PEP 440 고유 형식(`1.2.0.dev0` 등)은 미지원이며 Python 프로젝트는 none 스타일 권장임을 한 줄 안내하라(references/prerelease-and-dev-channel.md 참고).
- **번들 5 — 노트·GitHub Release**: destinations 복수 선택(changelog | release-file | github-release | fragment) — `fragment`는 노트 소스(`changelog.d/{id}.{category}.md` 조각 취합·소비, category `breaking`/`feature`/`fix`/`misc`)이며 **최소 1개 sink**(changelog/release-file/github-release)와 함께 써야 한다(render가 강제) / release-file이면 perReleasePath(기본 `docs/releases/`) / 언어(ko 기본 | en | both)·독자·어조 / GitHub Release 사용·generateNotes 하이브리드·release.yml 생성 여부 / **(independent 모노레포) bundle 라운드 노트** — 릴리스 라운드마다 CalVer 이름의 묶음 노트 파일(`<notesPath><라운드>.md`)을 만들지 묻는다. 스캔 `changelog.bundleNotesGuess`가 있으면(기존 라운드 노트 운용) 그 디렉터리·관측 패턴을 근거로 선두 추천. pattern 기본 `YYYY.0M.MICRO`, notesPath 기본 `docs/releases/`. 채택 시 top-level `bundle` 객체(`{"enabled": true, "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"}, "notesPath": "docs/releases/"}`)를 기록한다 — 라운드 SSOT는 notesPath의 최신 파일명이며 태그·버전 파일·config 상태를 만들지 않는다.
- **번들 6 — 경로·브랜치**: 커밋 경로 direct-push | release-pr — protected branch(+required checks)가 감지되면 직접 push가 불가능하므로 release-pr를 강제 기본으로 제안하고, 아니면 direct-push 기본. release-pr를 선택하면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행됨을 안내한다. **release-pr로 정했는데 기본 브랜치가 미보호(Phase 1에서 protection 404)면**, PR 흐름이 강제력을 가지려면 보호가 필요함을 알리고 사용자가 **직접 실행할** 설정을 조언한다 — 현대적 방법은 repository ruleset(`gh api --method POST repos/{owner}/{repo}/rulesets` 로 기본 브랜치에 pull_request 필수 + required_status_checks 규칙), 클래식 방법은 `gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection`, 웹 UI는 Settings → Rules → Rulesets. **init은 이 명령을 실행하지 않는다**(레포 보안 설정 — 사용자 몫). 이미 보호됨이면 조언하지 않는다. 어느 경우든 `decisions`에 `{"topic":"branch-protection","answer":"advised"|"already-protected","rationale":"<근거>","source":"scan","decidedAt":"<date>"}`를 기록한다(gh 미가용으로 보호 상태 미확인이면 answer는 `"unknown"`으로 두고 일반 권고만 언급) / 브랜치 전략 — 스캔 `branches.developBranchGuess`가 있으면(develop/development/dev 우선순위 감지) 명시적으로 묻는다: trunk 유지(develop 정리 권장 — 추천) | gitflow(develop에서 릴리스 cut). gitflow 선택 시 `repo.branching: "gitflow"` + `repo.developBranch`(`developBranchGuess` 값, 관례 기본 develop)를 기록하고 **releasePath를 release-pr로 잠근다**(보호 여부 무관 — 사이클이 PR 기반이며 render가 다른 조합을 거부한다). developBranch가 로컬·원격 어디에도 없으면(신규 레포에서 gitflow를 처음 도입) 기본 브랜치에서 생성해 push할 것을 안내하라(`git branch <develop> && git push -u origin <develop>`) — release 스킬 preflight가 통합 브랜치의 존재를 전제한다. 릴리스 사이클(develop에서 cut → PR to 기본 브랜치 → 머지 후 태그 → develop back-merge·SNAPSHOT 복귀)을 안내하라. gitflow면 hotfix 스킬도 production hotfix 흐름(main HEAD cut → 태그 → develop back-merge)으로 함께 생성됨을 안내한다(`maintenanceLines`와 독립). gitflow는 단일 레포와 independent 모노레포를 지원한다(모노레포면 release 스킬이 develop→기본 브랜치 라운드 릴리스를 수행하고, 범위 기준은 태그가 아니라 기본 브랜치다). developBranchGuess가 null이면 trunk 기본 제안(gitflow 선택지는 유지) / 유지보수 라인 운용 여부(스캔 `branches.releaseBranches`가 근거) — 운용하면 `repo.maintenanceLines: true`로 기록하고 hotfix 스킬이 생성됨을 안내한다. **단 semver 단일 스킬 레포 한정** — independent 모노레포·비semver scope에는 미지원 표시하고 잠근다(render가 두 조합을 모두 거부한다).
- **번들 7 — 첫 릴리스·이력·전파**: 기존 버전이 없으면 0.1.0 vs 1.0.0(공개 API 안정성 약속 기준으로 설명) / 기존 태그가 있고 CHANGELOG가 없거나 불완전하면 CHANGELOG backfill을 제안하고 `repo.backfill: true`로 기록한다(백필 스킬 생성 — 태그 구간별 과거 이력을 CHANGELOG.md에 소급 작성, 태그·push 없음; **단일 scope와 independent 모노레포 모두 지원** — 모노레포는 scope별 `<scope>@<version>` 네임스페이스를 순회한다. 대상 scope에 `changelog` 목적지가 없으면 "평상시 릴리스가 CHANGELOG를 갱신하지 않아 소급본이 방치될 수 있음"을 경고하고 확인받아 `decisions`에 기록한다. 전 scope가 tagless면 render가 거부한다) / destinations에 changelog가 있는데 CHANGELOG.md가 없으면 첫 릴리스 때 생성됨을 안내 / (independent 모노레포) 내부 의존성 전파 — 스캔 리포트 `monorepo.internalDependencies`를 근거로 "b가 a에 의존하므로 a 릴리스 시 b를 자동 patch 릴리스" 제안을 scope별 `dependents` 목록으로 확정한다(순환 의존이 생기지 않는지 확인).

모든 답을 decisions에 기록: `{"topic", "scope", "answer", "rationale", "source": "scan"|"user", "decidedAt"}`.

## config.json 작성

`.superrelease/config.json`을 아래 형태로 작성한다 (정본 스키마 — 값은 결정대로):

```json
{
  "superrelease": {
    "pluginVersion": "<plugin.json의 version>",
    "configVersion": 1,
    "generatedAt": "<date -u +%Y-%m-%dT%H:%M:%SZ>"
  },
  "repo": {
    "kind": "app",
    "defaultBranch": "main",
    "mergePolicy": "squash",
    "releasePath": "direct-push",
    "branching": "trunk",
    "developBranch": null,
    "maintenanceLines": false,
    "backfill": false,
    "releaseCommitFormat": "chore(release): {version}",
    "tagTriggersDeployment": false,
    "monorepoStrategy": null
  },
  "github": { "release": true, "generateNotes": true, "releaseYml": true },
  "scopes": [
    {
      "name": "root",
      "path": ".",
      "scheme": { "type": "semver", "pattern": null },
      "versionLocations": [
        { "file": "gradle.properties", "type": "properties-key", "key": "version" }
      ],
      "tag": { "enabled": true, "format": "v{version}", "annotated": true,
               "signed": false, "movingMajorTag": false },
      "bump": { "mode": "auto-confirm",
                "sources": ["conventional-commits", "pr-metadata"],
                "fallback": "diff", "compatCheck": null },
      "preRelease": { "style": "mutable", "qualifier": "SNAPSHOT" },
      "devChannel": { "enabled": true, "qualifier": "SNAPSHOT",
                      "immutableId": ["spring-build-info"] },
      "postRelease": { "bump": "next-snapshot" },
      "notes": { "destinations": ["changelog", "github-release"],
                 "language": "ko", "audience": "developers", "tone": "neutral",
                 "template": "notes-single.md", "perReleasePath": "docs/releases/" },
      "anchor": { "type": "tag", "value": null },
      "dependents": []
    }
  ],
  "decisions": []
}
```

- versionLocations 타입: `properties-key`(key= 값) | `json-path`(예: package.json의 "version") | `regex`(캡처 그룹 정확히 1개, MULTILINE로 매칭됨 — scan 리포트의 pattern을 그대로 옮기면 된다).
- scheme: semver면 `pattern: null`. calver면 `pattern`에 CalVer 패턴 문자열(예: "YYYY.MM.MICRO"), headver면 `pattern`에 head 번호 문자열(예: "1")을 기록한다 — 다음 버전은 `next-version.py`가 config의 scheme으로 자동 계산한다.
- 태그 미사용이면 `"tag": {"enabled": false, ...}` + `"anchor": {"type": "ref", "value": null}` — 첫 릴리스 후 release 스킬이 anchor.value를 갱신한다(config에서 유일하게 상태를 갖는 필드).
- devChannel.immutableId를 기록했으면 요약 단계에서 해당 설정 스니펫(Spring `springBoot { buildInfo() }`, Docker `-t app:dev -t app:sha-<shortSha>` 병행 push, npm `1.3.0-dev.<sha>`)을 안내하라.
- 모노레포: `repo.monorepoStrategy`를 "fixed" 또는 "independent"로 기록한다. independent면 `scopes`가 패키지 수만큼 늘어나고, scope마다 `path`(패키지 경로), 상대 경로 기준의 `versionLocations`, `tag.format`(`<scope>@{version}` 네임스페이스), `notes.template: "notes-package.md"`, `dependents`(이 scope 릴리스 시 patch 릴리스로 따라갈 scope 이름 목록)를 설정하고, `releaseCommitFormat`은 `chore(release): {scope}@{version}` 을 기본으로 제안하라. fixed면 scope는 root 하나이고 versionLocations에 전 패키지 버전 파일이 들어간다.
- 커밋 경로: `repo.releasePath`가 "release-pr"이면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행되고 `.superrelease/templates/release-pr-body.md`가 함께 생성된다. protected branch 레포는 release-pr가 사실상 유일한 경로다.
- hotfix: `repo.maintenanceLines: true`면 `.claude/skills/hotfix/SKILL.md`가 생성된다 — semver 단일 스킬 레포 한정(independent 모노레포 조합은 render가 거부한다).
- backfill: `repo.backfill: true`면 `.claude/skills/backfill/SKILL.md`가 생성된다 — 기존 태그 구간에서 CHANGELOG를 소급 작성하는 일회성 스킬(단일 scope·independent 모노레포 지원 — 모노레포는 scope별 `<scope>@<version>` 태그 네임스페이스를 순회; 전 scope가 tagless면 render가 거부).

## Phase 3 — 생성

1. 프리뷰: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/init/scripts/render.py" --config .superrelease/config.json --assets "${CLAUDE_PLUGIN_ROOT}/skills/init/assets" --repo . --check`
2. 분류 결과(create / update / unchanged / preserve / skipped / conflict)를 보여주고 확인받는다. **conflict가 있으면**(마커 없는 기존 파일 — 예: 자작 `.claude/skills/release/`) 해당 파일 내용을 보여주고 덮어쓸지 개별 확인받아라. 이 규칙은 최초 init에도 적용된다.
3. 실행: 같은 명령에서 `--check`를 빼고 실행(동의받은 경우에만 `--force` 추가).
4. 자가 검증: `python3 .superrelease/scripts/version.py verify` → exit 0 / `python3 .superrelease/scripts/next-version.py --help` → exit 0 / (모노레포) `python3 .superrelease/scripts/changed-packages.py --help` → exit 0. 실패하면 원인(대부분 versionLocations 오기)을 고치고 재렌더.
5. 요약 출력: 결정 테이블 / 생성 파일 목록 / **생성된 스킬별 첫 사용 예시** — release는 "릴리스해줘"·"릴리스 준비됐는지 봐줘", 생성됐다면 hotfix는 "핫픽스"/"1.2.x에 패치", backfill은 "백필해줘"/"CHANGELOG 소급"도 함께 나열(생성한 스킬의 실행 문구를 빠뜨리지 마라) / `tagTriggersDeployment`면 "태그 push = 배포 트리거" 경고 / immutableId 스니펫 안내.
6. 커밋 마무리: "생성물은 전부 커밋하세요 — 커밋해야 팀원이 함께 씁니다"와 함께 커밋 여부를 확인받고, 승인 시 생성물 전부(`.superrelease/`, `.claude/skills/`, 존재 시 `.github/release.yml`)를 `chore: superrelease 릴리스 툴킷 초기화` 메시지로 커밋한다.

## 재init (config가 이미 있을 때)

1. 기존 config를 결정 테이블로 요약해 보여준다.
2. Phase 1을 다시 수행하고 config와의 불일치(새 버전 위치 후보, 태그 패턴 변화, protected 변화, 새 워크플로 등)를 나열한다.
3. **바뀐 부분만** 질문한다. 불일치·변경 요청이 없으면 질문 0개로 Phase 3로 — "config를 손으로 고친 뒤 재init"이 공식 커스터마이징 경로다(필드·허용값·validate 규칙 요약은 README의 config.json 편집 절(영문판 "Editing config.json") 참고).
4. `superrelease.pluginVersion`이 현재 플러그인 version보다 낮으면 마이그레이션: 바뀐 스키마 항목을 안내하고 pluginVersion을 갱신한다.
5. Phase 3를 수행한다. preserve(마커가 제거된 템플릿 = 손편집)는 보존했음을 보고한다.

## 지원 범위와 제약 (범위 밖 선택지에 "지원하지 않음" 표시)

지원: 단일 레포(app/library) + 모노레포 fixed/independent — scope별 태그 네임스페이스, changed-packages 변경 감지, dependents 전파 포함.

- 스캔 감지: gradle.properties / build.gradle(.kts) / package.json / pyproject.toml / Cargo.toml / Dockerfile LABEL / Chart.yaml / README 배지 / VERSION / openapi·swagger(json·yaml) / pom.xml(`<revision>` property는 후보, project `<version>`은 감지·안내 전용) / .claude-plugin/plugin.json(Claude Code 플러그인 매니페스트 — json-path `version`) + node·gradle 모노레포 패키지 — libs.versions.toml(의존성 카탈로그)·gradle 내부 의존성·pom 직접 쓰기(xml-path)는 지원하지 않는다
- 브랜칭: trunk / gitflow(release-pr 전용 — develop cut → 기본 브랜치 태그 → back-merge 정식 사이클, production hotfix 포함; 단일 레포·independent 모노레포 지원, gitflow에서는 태그가 선택사항) 지원 — direct-push gitflow는 지원하지 않는다
- 버전 체계: SemVer/CalVer/HeadVer 지원 — sequential 등 그 외 체계는 지원하지 않는다
- pre-release: none/mutable/counter(-rc.N) 지원 / moving major tag 지원(force-push 경고 수반)
- 모노레포 이중 체계(루트 CalVer train + 패키지 SemVer)·release-train: 지원하지 않는다 — config에 `train` 객체가 있으면 render가 거부한다. independent로 패키지를 개별 릴리스하고, 검증된 조합 공표가 필요하면 릴리스 노트·문서에 조합 표를 남기는 운용을 안내하라
- 커밋 경로: direct-push | release-pr(보호 브랜치 — PR 생성 후 중단, 머지 후 태그 재개) 지원 — trunk×release-pr는 태그 필수(tagless는 direct-push 또는 gitflow에서만)
- 노트 목적지: changelog/release-file/github-release/fragment 지원 — fragment는 sink 동반 필수(render가 검증) / tag-message(annotated 태그 메시지에 노트 전문)는 지원하지 않는다 — 태그 메시지에는 한 줄 요약만 남는다 / bundle 라운드 노트(independent 모노레포 — CalVer 파일명 라벨, top-level bundle 객체): 지원
- hotfix 스킬: semver 지원 — 단일 스킬 레포 + gitflow independent 모노레포(scope 지정 patch); 비-gitflow independent 모노레포의 maintenanceLines 유지보수 라인은 지원하지 않는다 / CHANGELOG backfill: 단일 scope·independent 모노레포 지원(모노레포는 scope별 `<scope>@<version>` 순회, 전 scope tagless면 render 거부)
