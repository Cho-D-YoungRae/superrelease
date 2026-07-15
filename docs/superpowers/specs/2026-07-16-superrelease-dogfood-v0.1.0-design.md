# superrelease v0.1.0 자기 dogfooding — 설계

> 상태: 설계 승인됨 (2026-07-16). 다음 단계: writing-plans.

## 목표

superrelease가 **자기 툴킷으로 자신을 v0.1.0으로 릴리스**한다. init 엔진(scan·render·`validate_config`)과 생성된 **release-pr** 릴리스 흐름 전 과정을 실전에서 한 번 통과시켜, M4a~M4d가 하드닝한 표면이 실제로 동작하는지 검증하고 그 과정의 마찰을 후속 백로그로 남긴다.

## 배경 / 현황

- 버전 소스는 `.claude-plugin/plugin.json`의 `"version"` 필드 — **이미 `0.1.0`**. 태그는 하나도 없음 → **첫 릴리스**.
- `.superrelease/`·`.claude/`가 없음 → init이 이 레포에 한 번도 돌지 않음.
- `main`은 **브랜치 보호 없음**(rulesets 비어 있음)이나, 프로젝트 규율은 PR 기반(GitHub Flow) + **머지 커밋**(squash 아님, `git log --merges`가 "Merge pull request" 확인).
- remote: GitHub SSH(`Cho-D-YoungRae/superrelease`). gh는 이중 계정 — 이 레포 작업은 `Cho-D-YoungRae`, 기본은 `aims-yrcho`.
- `.github/` 없음 → 태그 트리거 CI 없음.
- CHANGELOG.md는 Keep a Changelog 형식, `[Unreleased]`에 0.1.0 산출이 이미 정리돼 있음("v0.1.0 준비 중").

## 스코프

**In (Level 1):** 버전 location을 `.claude-plugin/plugin.json`(json-path)으로 **수동 지정**하고 생성 툴킷으로 v0.1.0을 릴리스. init 엔진(scan·render·validate)과 release-pr 흐름을 검증.

**Out (후속 백로그):**
- scan/init이 `.claude-plugin/plugin.json`을 1급 버전 소스로 **자동 감지**하는 기능(Level 2 마일스톤).
- 아래 §7 마찰 2건의 후속 수정.

의도적으로 **완전한 대화형 init 재현은 하지 않는다** — 운영자(에이전트)가 이미 모든 답을 쥐고 있어, config를 직접 저작하고 `render.py`로 렌더하면 init 산출물과 동일하다. init의 **엔진**(scan은 이미 실행해 갭 확인 완료, render·validate는 아래 절차에서 실행)은 그대로 dogfood된다.

## 자기 config (`.superrelease/config.json`)

`release_pr_app` 골든(검증된 config)에 가장 가깝고, 차이는 **버전 소스·mergePolicy·github**뿐이다. 전문:

```json
{
  "superrelease": {
    "pluginVersion": "0.1.0",
    "configVersion": 1,
    "generatedAt": "2026-07-16T00:00:00+00:00"
  },
  "repo": {
    "kind": "app",
    "defaultBranch": "main",
    "mergePolicy": "merge",
    "releasePath": "release-pr",
    "branching": "trunk",
    "developBranch": null,
    "maintenanceLines": false,
    "releaseCommitFormat": "chore(release): {version}",
    "tagTriggersDeployment": false,
    "monorepoStrategy": null
  },
  "github": {
    "release": true,
    "generateNotes": false,
    "releaseYml": false
  },
  "scopes": [
    {
      "name": "root",
      "path": ".",
      "scheme": {"type": "semver", "pattern": null},
      "versionLocations": [
        {"file": ".claude-plugin/plugin.json", "type": "json-path", "path": "version"}
      ],
      "tag": {"enabled": true, "format": "v{version}", "annotated": true, "signed": false, "movingMajorTag": false},
      "bump": {"mode": "auto-confirm", "sources": ["conventional-commits"], "fallback": "diff", "compatCheck": null},
      "preRelease": {"style": "none", "qualifier": null},
      "devChannel": {"enabled": false, "qualifier": null, "immutableId": []},
      "postRelease": {"bump": "none"},
      "notes": {"destinations": ["changelog", "github-release"], "language": "ko", "audience": "developers", "tone": "neutral", "template": "notes-single.md", "perReleasePath": "docs/releases/"},
      "anchor": {"type": "tag", "value": null},
      "dependents": []
    }
  ],
  "decisions": []
}
```

설계 결정 근거:
- **버전 소스 json-path** — `version.py`의 json-path 핸들러는 파일 일반적(package.json 특수 처리는 package-lock 동기화뿐, 다른 파일엔 무해). `.claude-plugin/plugin.json`의 read/write/verify가 그대로 동작하고, 덤으로 json-path writer를 package.json 아닌 파일에서 검증한다.
- **pre/post `none`** — 플러그인은 SNAPSHOT/dev 버전 관례가 없다. main은 릴리스 버전 그대로 유지(post-release bump 없음). `release_pr_app` 골든과 동일한 pre/post 조합.
- **mergePolicy `merge`** — 이 레포는 머지 커밋을 쓴다. §2 bump 소스의 squash 역참조 분기는 렌더되지 않으며, 첫 릴리스라 bump 분석 자체가 "Initial release"로 대체된다.
- **github `release:true, generateNotes:false, releaseYml:false`** — 공개 플러그인이라 GitHub Releases에 v0.1.0을 게시하되, 우리 CHANGELOG 노트를 직접 본문으로 올린다(generate-notes 하이브리드·release.yml은 첫 릴리스엔 생략, 이후 켤 수 있음). `github.release=true`는 `tag.enabled=true` 불변식을 만족.
- **첫 릴리스** — 태그 0개·`anchor.value` null → release 스킬이 "Initial release"로 처리, 버전은 이미 0.1.0이라 `version.py set 0.1.0`은 no-op, **CHANGELOG 확정이 유일한 실제 변경분**.
- `devChannel.qualifier`는 pre none이라 null로 두되, `validate_config`는 render 시점에 검증한다(실패 시 `release_pr_app`처럼 `"SNAPSHOT"`으로 되돌린다 — devChannel은 enabled=false라 렌더에 나타나지 않는 inert 필드).

## 절차 (2 PR)

### PR1 — adopt (`feat: adopt superrelease self-release toolkit`)

레포가 superrelease 툴킷을 "채택"하는 인프라 커밋. 릴리스가 아니다.

1. `.superrelease/config.json`을 위 전문대로 저작.
2. `render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now <stamp>`로 툴킷 렌더 → `.claude/skills/{release,release-notes}/SKILL.md` + `.superrelease/scripts/{version,next-version}.py` + `.superrelease/templates/{notes-single,changelog-entry,release-pr-body}.md` 생성. (release-pr이라 release-pr-body.md 포함, github.releaseYml=false라 `.github/release.yml` 미생성.)
3. **self-render 정합 테스트**(§드리프트 안전장치) 추가.
4. CLAUDE.md에 "template(`skills/init/assets/skills/…`) vs rendered(`.claude/skills/…`)" 구분 + "asset 수정 후 재렌더" 규율 한 단락.
5. 전체 테스트 green + `claude plugin validate . --strict` PASS 확인 후 PR 생성·머지.

머지 후 `git checkout main && git pull`로 툴킷이 main에 존재하는 상태에서 PR2 진행.

### PR2 — release (생성된 `release` 스킬이 수행, release-pr 경로)

`.claude/skills/release/SKILL.md` 절차를 그대로 따른다:

1. **preflight** — 현재 브랜치 main · clean tree · origin 동기 · `version.py verify` exit 0 · **gh 인증**(release-pr은 릴리스 여부 무관 gh 필요). 첫 릴리스라 중단 상태 감지·열린 릴리스 PR 확인은 해당 없음.
2. **범위** — anchor 없음 → "Initial release"(커밋 전체 나열 금지).
3. **버전** — 첫 릴리스, 버전 0.1.0 확정(`version.py get`=0.1.0, `set 0.1.0`은 no-op).
4. **노트** — CHANGELOG `[Unreleased]` → `## [0.1.0] - 2026-07-16`로 확정하고 새 빈 `[Unreleased]`를 연다. 링크 참조 갱신. 같은 노트를 github-release 본문으로 준비.
5. **dry-run 프리뷰 → release-pr 경로**: `git checkout -b release/0.1.0` → CHANGELOG 커밋(`chore(release): 0.1.0`) → `git push -u origin release/0.1.0` → `gh pr create --base main --head release/0.1.0 --title "chore(release): 0.1.0" --body-file <release-pr-body>` → **여기서 중단**.
6. **PR2 머지**(머지 커밋) 후 **resume**: `git checkout main && git pull` → 머지 후 HEAD에 `git tag -a v0.1.0 -m …`(push 직전 `git ls-remote --tags origin v0.1.0` 비어 있음 재확인) → `git push origin v0.1.0` → `gh release create v0.1.0 --title "0.1.0" --notes-file <notes>`.
7. **post-release** — postRelease.bump none → next-snapshot 복귀 없음. 새 `[Unreleased]`는 4단계에서 이미 열림.

## 드리프트 안전장치 (유일한 코드 산출물)

`tests/test_dogfood_selfrender.py` — 커밋된 툴킷이 asset 템플릿에서 **절대 드리프트하지 않음**을 강제한다. `test_golden.py`의 렌더 메커니즘을 재사용:

1. 커밋된 `ROOT/.superrelease/config.json`을 읽어 `<tmp>/superrelease/`(디렉터리명 고정 → `project.name`="superrelease")로 `render.py` 실행. `env`에 `GIT_CEILING_DIRECTORIES=<tmp>`(감싸는 실제 git 레포 간섭 차단), `--now`는 임의(렌더 산출물에 날짜 미포함). returncode 0 = **config가 유효**(validate 통과)함을 증명.
2. 렌더된 트리(`config.json` 제외)의 각 상대경로에 대해 커밋된 `ROOT/<상대경로>`가 **바이트 동일**한지 assert. 스크립트 verbatim 복제 + 렌더 SKILL·템플릿을 모두 커버.
3. 역방향: 커밋된 툴킷 파일 집합(`ROOT/.claude/skills/**`·`ROOT/.superrelease/scripts/**`·`ROOT/.superrelease/templates/**`)이 렌더 산출 집합과 **정확히 일치**(stale 잔여 파일 없음).

이 테스트가 green이면 asset 수정 → 재렌더 누락 시 즉시 실패한다. 재렌더 절차는 CONTRIBUTING/CLAUDE.md에 규율로 명시(§PR1-4).

## 발견된 dogfooding 마찰 (후속 백로그, v0.1.0 비차단)

1. **scan이 `.claude-plugin/plugin.json`을 버전 소스로 미감지** — Claude Code 플러그인 매니페스트가 scan의 후보에 없음. Level 2 마일스톤(플러그인 매니페스트 1급 버전 소스화: scan 후보 + init 자동감지 + 골든).
2. **release 스킬 §6 비-gitflow release-pr resume 문구가 "squash 머지로 sha가 바뀐다"를 하드코딩** — mergePolicy=merge 레포에선 부정확(머지 후 HEAD에 태그를 만드는 지침 자체는 옳음). 문구를 mergePolicy 반영(`{{#if repo.mergePolicy == "squash"}}squash 머지로{{else}}머지 커밋으로{{/if}}`)으로 고칠 후속. 골든 바이트 영향 확인 필요.

## 실행 모델

spec → writing-plans(운영 런북 + self-render 테스트 1개) → **인라인 실행**. 릴리스는 상태·부작용이 있어 SDD 서브에이전트로 위임하지 않는다 — 부작용 게이트(파일 수정·커밋·PR 생성·머지·태그 push·release 생성)마다 **dry-run → 사용자 확인 → 실행**(플러그인 자체 규율 + 안전 규칙). self-render 테스트만 TDD 사이클로 작성.

gh 계정: PR 생성·머지·release 생성 등 이 레포 대상 gh 작업 직전 `gh auth switch --user Cho-D-YoungRae`, 완료 후 `gh auth switch --user aims-yrcho` 복원(랜딩 패턴 준수).

## 성공 기준 / 검증

- `v0.1.0` 태그가 origin에 push되고 GitHub Release가 게시됨.
- `.claude-plugin/plugin.json` version = `0.1.0` 유지.
- CHANGELOG에 `## [0.1.0] - 2026-07-16` 확정 + 새 `[Unreleased]`.
- 전체 테스트 green(신규 self-render 포함) · `claude plugin validate . --strict` PASS.
- 마찰 2건이 백로그(이 스펙 §7 + 진행 원장)에 기록됨.

## 리스크 / 엣지 케이스

- **버전 no-op(이미 0.1.0)** — release/0.1.0 브랜치의 유일한 변경은 CHANGELOG 확정. 빈 diff PR 아님(내용 있음). 정상.
- **json-path writer가 plugin.json 포맷 보존** — `dump_json_like`가 기존 스타일 유지. dry-run에서 round-trip 확인(무해하지만 첫 사용 파일이라 프리뷰에서 diff 검토).
- **self-render 결정론** — 반드시 `superrelease`명 디렉터리 + `GIT_CEILING_DIRECTORIES`로 렌더(그러지 않으면 `project.name`이 달라져 오탐).
- **커밋된 `.claude/skills/`가 활성 프로젝트 스킬이 됨** — 레포에서 작업 시 `release` 스킬이 뜬다. 의도된 동작(유지보수자가 이걸로 릴리스). CLAUDE.md에 명시.
- **release-pr resume 2단계** — PR2 머지 전까지 태그 없음. 머지 후 별도 재개 필요. 실행 중 중단되면 preflight 6(중단 감지)이 재개 지점을 잡음.
- **gh 계정 오전환** — 복원 누락 시 이후 세션 혼선. 각 gh 작업 블록 후 즉시 복원.

## 후속 (백로그)

- **Level 2**: 플러그인 매니페스트 1급 버전 소스 자동감지(마찰 #1).
- release 스킬 non-gitflow release-pr resume 문구 mergePolicy 반영(마찰 #2).
- (기존 백로그) M4b-2 gitflow hotfix · 문서 소소 정리.
