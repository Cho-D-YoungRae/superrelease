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
- 아래 "지원 범위와 제약" 밖의 선택지는 "후속 버전 지원 예정"으로 표시하고 선택하지 못하게 한다.

## 모드 감지

1. `.superrelease/config.json`이 존재하면 → **재init** (마지막 절로)
2. config가 없고 스캔 신호도 빈약하면(빌드 파일·태그·커밋이 거의 없음) → **신규 레포 제안 모드**: 레포 성격을 먼저 묻고, 성격별 권장 프리셋(라이브러리→SemVer+SNAPSHOT+next-snapshot / 앱→SemVer+dev 채널 선택)을 제시한 뒤 아래 흐름을 그대로 진행
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

- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). monorepo면 전략을 묻는다 — fixed(전 패키지 버전 공유) | independent(패키지별 독립) | 이중 체계(M3 예정 표시). independent면 스캔 리포트 `monorepo.packages`를 표로 제시해 scope 목록(이름 = 패키지 이름 또는 디렉터리명, path, 버전 파일)을 확정한다. fixed면 단일 root scope의 versionLocations에 전 패키지 버전 파일을 모은다(릴리스 흐름은 단일 레포와 동일).
- **번들 2 — 체계·SSOT·태그**: 버전 체계 SemVer | CalVer | HeadVer (sequential은 후속 표시) — 라이브러리는 SemVer 사실상 강제, CalVer면 pattern(예: `YYYY.MM.MICRO` — 어휘 YYYY/YY/0M/MM/0D/DD/MICRO)을, HeadVer면 head 번호를 `scheme.pattern`에 기록한다 / 버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다 / 태그 파생 여부(기본 yes)·prefix(v 유무)·annotated(기본 yes)·signed — independent 모노레포면 scope별 `tag.format` 기본값을 `<scope이름>@{version}` 네임스페이스로 제안한다 / moving major tag — semver+태그 사용 시 `v<major>` 유동 태그 운용 여부(force-push 수반을 경고하고 결정).
- **번들 3 — bump**: auto-confirm(기본) | manual / 소스 우선순위 — CC 사용률이 높으면 conventional-commits 우선, squash 레포면 pr-metadata 1차 / (라이브러리) compatCheck 도구(kotlin-bcv, japicmp) 기록 여부.
- **번들 4 — pre-release·dev·post**: 수식어 스타일 none | mutable(-SNAPSHOT류) | counter(-rc.N 등 불변 카운터 — qualifier 이름(rc/alpha/beta)을 확정하고, counter는 postRelease none을 기본 제안) / (앱·mutable) dev 채널 qualifier 이름과 불변 식별자 immutableId(spring-build-info | docker-sha-tag | npm-dev-suffix) — config 기록 + 설정 스니펫 안내만, 배포 자동화는 하지 않음 / post-release bump — 라이브러리→next-snapshot 기본, 앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안).
- **번들 5 — 노트·GitHub Release**: destinations 복수 선택(M1: changelog | release-file | github-release; fragment·tag-message는 M3 표시) / release-file이면 perReleasePath(기본 `docs/releases/`) / 언어(ko 기본 | en | both)·독자·어조 / GitHub Release 사용·generateNotes 하이브리드·release.yml 생성 여부.
- **번들 6 — 경로·브랜치**: 커밋 경로 direct-push | release-pr — protected branch(+required checks)가 감지되면 직접 push가 불가능하므로 release-pr를 강제 기본으로 제안하고, 아니면 direct-push 기본. release-pr를 선택하면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행됨을 안내한다. **release-pr로 정했는데 기본 브랜치가 미보호(Phase 1에서 protection 404)면**, PR 흐름이 강제력을 가지려면 보호가 필요함을 알리고 사용자가 **직접 실행할** 설정을 조언한다 — 현대적 방법은 repository ruleset(`gh api --method POST repos/{owner}/{repo}/rulesets` 로 기본 브랜치에 pull_request 필수 + required_status_checks 규칙), 클래식 방법은 `gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection`, 웹 UI는 Settings → Rules → Rulesets. **init은 이 명령을 실행하지 않는다**(레포 보안 설정 — 사용자 몫). 이미 보호됨이면 조언하지 않는다. 어느 경우든 `decisions`에 `{"topic":"branch-protection","answer":"advised"|"already-protected","rationale":"<근거>","source":"scan","decidedAt":"<date>"}`를 기록한다(gh 미가용으로 보호 상태 미확인이면 answer는 `"unknown"`으로 두고 일반 권고만 언급) / 브랜치 전략 확인(신규는 trunk-based 기본 제안) / 유지보수 라인 운용 여부(스캔 `branches.releaseBranches`가 근거) — 운용하면 `repo.maintenanceLines: true`로 기록하고 hotfix 스킬이 생성됨을 안내한다. **단 semver 단일 스킬 레포 한정** — independent 모노레포·비semver scope에는 후속 표시하고 잠근다(render가 두 조합을 모두 거부한다).
- **번들 7 — 첫 릴리스·이력·전파**: 기존 버전이 없으면 0.1.0 vs 1.0.0(공개 API 안정성 약속 기준으로 설명) / CHANGELOG backfill(M3 예정 표시) / destinations에 changelog가 있는데 CHANGELOG.md가 없으면 첫 릴리스 때 생성됨을 안내 / (independent 모노레포) 내부 의존성 전파 — 스캔 리포트 `monorepo.internalDependencies`를 근거로 "b가 a에 의존하므로 a 릴리스 시 b를 자동 patch 릴리스" 제안을 scope별 `dependents` 목록으로 확정한다(순환 의존이 생기지 않는지 확인).

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
    "maintenanceLines": false,
    "train": false,
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

## Phase 3 — 생성

1. 프리뷰: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/init/scripts/render.py" --config .superrelease/config.json --assets "${CLAUDE_PLUGIN_ROOT}/skills/init/assets" --repo . --check`
2. 분류 결과(create / update / unchanged / preserve / skipped / conflict)를 보여주고 확인받는다. **conflict가 있으면**(마커 없는 기존 파일 — 예: 자작 `.claude/skills/release/`) 해당 파일 내용을 보여주고 덮어쓸지 개별 확인받아라. 이 규칙은 최초 init에도 적용된다.
3. 실행: 같은 명령에서 `--check`를 빼고 실행(동의받은 경우에만 `--force` 추가).
4. 자가 검증: `python3 .superrelease/scripts/version.py verify` → exit 0 / `python3 .superrelease/scripts/next-version.py --help` → exit 0 / (모노레포) `python3 .superrelease/scripts/changed-packages.py --help` → exit 0. 실패하면 원인(대부분 versionLocations 오기)을 고치고 재렌더.
5. 요약 출력: 결정 테이블 / 생성 파일 목록 / 첫 사용 예시("릴리스해줘", "릴리스 준비됐는지 봐줘") / `tagTriggersDeployment`면 "태그 push = 배포 트리거" 경고 / immutableId 스니펫 안내.
6. 커밋 마무리: "생성물은 전부 커밋하세요 — 커밋해야 팀원이 함께 씁니다"와 함께 커밋 여부를 확인받고, 승인 시 생성물 전부(`.superrelease/`, `.claude/skills/`, 존재 시 `.github/release.yml`)를 `chore: superrelease 릴리스 툴킷 초기화` 메시지로 커밋한다.

## 재init (config가 이미 있을 때)

1. 기존 config를 결정 테이블로 요약해 보여준다.
2. Phase 1을 다시 수행하고 config와의 불일치(새 버전 위치 후보, 태그 패턴 변화, protected 변화, 새 워크플로 등)를 나열한다.
3. **바뀐 부분만** 질문한다. 불일치·변경 요청이 없으면 질문 0개로 Phase 3로 — "config를 손으로 고친 뒤 재init"이 공식 커스터마이징 경로다.
4. `superrelease.pluginVersion`이 현재 플러그인 version보다 낮으면 마이그레이션: 바뀐 스키마 항목을 안내하고 pluginVersion을 갱신한다.
5. Phase 3를 수행한다. preserve(마커가 제거된 템플릿 = 손편집)는 보존했음을 보고한다.

## 지원 범위와 제약 (해당 선택지에 "후속 버전 지원 예정" 표시)

지원: 단일 레포(app/library) + 모노레포 fixed/independent — scope별 태그 네임스페이스, changed-packages 변경 감지, dependents 전파 포함.

- 버전 체계: SemVer/CalVer/HeadVer 지원 — sequential은 후속
- pre-release: none/mutable/counter(-rc.N) 지원 / moving major tag 지원(force-push 경고 수반)
- 모노레포 이중 체계(루트 train + 패키지 SemVer)와 release-train 스킬: M3c
- 커밋 경로: direct-push | release-pr(보호 브랜치 — PR 생성 후 중단, 머지 후 태그 재개) 지원
- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3c
- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: M3c
