# superrelease M3b (릴리스 경로) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superrelease에 M3b — **릴리스 PR 모드**(protected branch 레포: 버전 bump·노트를 PR로 올리고, 머지 후 태그·Release를 재개하는 2단계 릴리스)와 **hotfix 플로우**(유지보수 라인 `release/X.Y.x`에서의 patch 릴리스, 신규 `hotfix` 생성 스킬) — 를 추가한다. (M3 3분할 중 두 번째: M3a=버전 체계(완료), **M3b=이 계획**, M3c=트레인·backfill·fragment/tag-message.)

**Architecture:** 스크립트는 **하나도 바뀌지 않는다** — M3b는 전부 생성 스킬·템플릿·manifest 계층의 일이다. 릴리스 PR 모드는 기존 `{{#if repo.releasePath == "direct-push"}}` 블록에 `{{else}}` 분기를 더하고(기존 direct-push 렌더는 바이트 불변), PR 본문 골격 `release-pr-body.md` 템플릿을 조건부 manifest 엔트리로 추가한다. 재개는 새 상태 저장 없이 **기존 preflight 중단 상태 감지**(파일 버전 > 마지막 태그, 미태깅)를 재사용한다. hotfix는 신규 자산 SKILL.md 하나 + `when: "repo.maintenanceLines"` manifest 엔트리이며, release 스킬의 해당 단계를 참조해(생성물 간 참조는 자립성 위반이 아님) 얇게 유지한다. 골든은 신규 2트리만 추가되고 기존 6트리는 바이트 불변이다.

**Tech Stack:** 동결 템플릿 dialect(`{{#if}}`/`{{else}}`/`==`·`!=`, 블록 중첩 허용 — 엔진 수정 금지), manifest `when`(if-표현식과 동일 문법), git·gh CLI(+GitHub MCP 폴백 프로즈).

**스펙:** [docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md](../specs/2026-07-09-superrelease-plugin-design.md) §4.3 질문 번들 6 · §5.3 manifest · §6.1 생성물 트리 · §6.3 절차 6(커밋 경로) · §6.5 hotfix · §12 M3. **베이스: main `50311b1`** (M1+M2+M2.1+M3a+M3a.1, 133 테스트). 실행 컨트롤러는 main에서 `feat/superrelease-m3b` 브랜치를 만들어 진행한다.

## Global Constraints

- **스크립트 소스 변경 0건**: `version.py`·`next-version.py`·`changed-packages.py`·`scan.py`·render.py **엔진부(Part 1)** 수정 금지. 유일한 Python 변경은 render.py **파이프라인부의 config 검증 규칙 1건**(Task 3 — render.py는 골든-복사 대상이 아니므로 골든 무영향).
- **골든 재생성 규율:** Task 1·2·3은 골든 변경 **0** — 기존 6 config는 전부 `releasePath: "direct-push"`·`maintenanceLines: false`이므로 else 분기 붕괴·`when` false로 렌더가 바이트 불변이어야 한다. `update_golden.py` 실행 금지, `python3 -m unittest test_golden` GREEN 유지가 증명이다. Task 4만 `tests/golden/{release-pr-app,hotfix-library}/` 신규(`?? ` 2트리)를 만들고, `git status --porcelain tests/golden`에 그 외 항목이 나오면 STOP(원인 수정 후 `git checkout -- tests/golden`).
- 동결 dialect만 사용: `{{path}}`, `{{#if}}`(`{{else}}`, `== "lit"`/`!= "lit"`), `{{#unless}}`, `{{#each}}`. manifest `when`도 같은 문법(AND/OR 없음 — 복합 조건은 config 검증 규칙과 init 잠금으로 대신한다).
- 생성 SKILL.md ≤150줄(마커 1줄 포함 — asset은 149줄 이하로 테스트), init SKILL.md ≤500줄. 모노레포 변형은 **scope 값 인라인 금지**(repo.* 값의 조건 블록·인라인은 허용 — 기존 §7 `releaseCommitFormat` 선례). 코드·스크립트 메시지는 영어, 생성 문서는 한국어.
- 테스트: `cd tests && python3 -m unittest discover -p 'test_*.py'`. 커밋: Conventional Commits + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **계획 단계 확정** (스펙 재량 해석 — 구현 중 재논의 금지, 바꾸려면 컨트롤러와 상의):
  1. **릴리스 브랜치명**: 단일 스킬 `release/<릴리스 버전>`(예: `release/1.3.0`), 모노레포 `release/<첫 scope>@<버전>`(복수 대상이면 `+N` 접미, 예: `release/a@1.2.0+2`). 유지보수 라인 `release/X.Y.x`(리터럴 `x`)와 패턴이 겹치지 않는다. hotfix의 PR head 브랜치는 `hotfix/<패치 버전>`.
  2. **2단계성**: 단계 A = preflight→bump→버전 반영→노트→릴리스 브랜치·커밋·push→PR 생성→**중단**. 단계 B(재개) = 기존 preflight 6(중단 상태 감지)이 잡는다 → PR 머지 확인 → `git checkout <defaultBranch> && git pull` → 태그 단계부터. **태그는 머지 후 pull 받은 defaultBranch HEAD에** 만든다(squash 머지로 sha가 바뀌므로). 스킬은 required checks 대기·자동 머지를 하지 않는다 — 머지는 사람/레포 정책 몫.
  3. **hotfix 전제**: semver scope + 비-independent 레포 한정. 강제 장치 2중 — init이 independent 모노레포·비semver scope에서 질문을 잠그고, render.py 검증 규칙이 `maintenanceLines`+`monorepoStrategy=="independent"` 조합을 exit 1로 거부한다. 유지보수 라인의 post-release는 scope의 `postRelease.bump` 정책을 동일 적용, moving major tag는 "그 major의 최신 릴리스일 때만" 프로즈로 방어.
  4. **release-pr-body.md**: notes 템플릿과 동일한 ko/en `{{#unless scope.notes.language == ...}}` 분기 + `preserve: "template"`(손편집 허용 영역). `{version}` 단일 중괄호는 엔진이 보존하며 PR 생성 시점에 Claude가 채운다.
  5. **post-release 복귀 커밋**: release-pr 레포에서는 next-snapshot 복귀 커밋도 직접 push할 수 없으므로 `chore/next-dev` 브랜치 → 후속 PR 경로를 안내하는 조건부 한 줄을 §8(단일)·§9(모노레포)에 추가한다.

## 파일 구조 (M3b 전체)

```
수정  skills/init/assets/skills/release/SKILL.md            # Task 1: §6 else(릴리스 PR)·§8 복귀커밋 한 줄
생성  skills/init/assets/templates/release-pr-body.md       # Task 1
수정  skills/init/assets/manifest.json                      # Task 1: release-pr-body / Task 3: hotfix 엔트리
수정  tests/test_assets.py                                  # Task 1·2·3: 렌더 스모크 + full-render 케이스
수정  skills/init/assets/skills/release-monorepo/SKILL.md   # Task 2: §7 else·§9 복귀커밋 한 줄
생성  skills/init/assets/skills/hotfix/SKILL.md             # Task 3
수정  skills/init/scripts/render.py                         # Task 3: 검증 규칙 1건 (파이프라인부)
수정  tests/test_render_pipeline.py                         # Task 3: 규칙 테스트
수정  tests/golden_configs.py                               # Task 4: release_pr_app, hotfix_library
생성  tests/golden/{release-pr-app,hotfix-library}/expected/**   # Task 4
수정  skills/init/SKILL.md                                  # Task 5: 번들6 해제·지원 범위·config 각주
수정  skills/init/references/branching-and-release-path.md  # Task 5: "M3 예정" → 실지원 서술
수정  README.md, README_KO.md                               # Task 5: 로드맵 M3a→shipped, M3b→current
```

책임 분리: 경로 분기·재개 절차·hotfix 절차 = 생성 스킬(판단·프로즈), 생성 여부 = manifest `when` + config 검증(결정론), releasePath/maintenanceLines = config(SSOT). 새 스크립트·새 상태 필드 없음(재개는 기존 중단 상태 감지 재사용).

---

### Task 1: 단일 release 스킬 — 릴리스 PR 분기 + release-pr-body.md + manifest

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md` (§6 끝 줄, §8 next-snapshot 문장)
- Create: `skills/init/assets/templates/release-pr-body.md`
- Modify: `skills/init/assets/manifest.json` (templates 그룹에 엔트리 1개)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: config `repo.releasePath`("direct-push"|"release-pr"), `repo.defaultBranch`, `repo.releaseCommitFormat`, `scope.notes.language`, `github.release` — 모두 기존 키(helpers.scope_config 기본값에 이미 존재).
- Produces: 렌더 산출물 `.superrelease/templates/release-pr-body.md`(release-pr일 때만). Task 4의 골든 `release-pr-app`과 Task 5의 init 문서가 이 동작 서술에 의존한다.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py**

`SkillAssetsTest` 클래스의 `test_release_skill_semver_default_has_no_new_blocks` 메서드 뒤에 추가:

```python
    def test_release_skill_release_pr_branch(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("gh pr create", out)
        self.assertIn("릴리스 PR", out)
        self.assertIn("release-pr-body.md", out)
        self.assertIn("chore/next-dev", out)  # §8 복귀 커밋도 PR 경로 안내
        self.assertNotIn("git push origin main`", out)  # direct-push 문장 부재
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_direct_push_has_no_pr_prose(self):
        out = self.render_asset("skills/release/SKILL.md")
        self.assertIn("git push origin main", out)
        self.assertNotIn("릴리스 PR", out)
        self.assertNotIn("gh pr create", out)
        self.assertNotIn("chore/next-dev", out)

    def test_release_pr_body_template_language_blocks(self):
        ko = self.render_asset("templates/release-pr-body.md")
        self.assertIn("릴리스 {version}", ko)
        self.assertNotIn("Release {version}", ko)
        ctx = base_ctx()
        ctx["scope"]["notes"]["language"] = "en"
        en = self.render_asset("templates/release-pr-body.md", ctx)
        self.assertIn("Release {version}", en)
        self.assertNotIn("릴리스 {version}", en)
```

`FullRenderTest` 클래스의 `test_real_assets_render_end_to_end` 메서드 뒤에 추가:

```python
    def test_release_pr_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["releasePath"] = "release-pr"
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(
                (repo / ".superrelease/templates/release-pr-body.md").is_file())
            skill = (repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("gh pr create", skill)
```

그리고 기존 `test_real_assets_render_end_to_end`의 `for rel in (...)` 검증 루프 **아래**(assertIn("generated by...") 줄 앞)에 direct-push 부재 확인 1줄 추가:

```python
            self.assertFalse(
                (repo / ".superrelease/templates/release-pr-body.md").exists())
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets -v 2>&1 | tail -15`
Expected: `test_release_skill_release_pr_branch`·`test_release_pr_body_template_language_blocks`·`test_release_pr_full_render` **FAIL/ERROR** (release-pr 분기·템플릿 부재), `test_release_skill_direct_push_has_no_pr_prose`는 PASS(현재도 PR 프로즈 없음 — 붕괴 회귀 핀).

- [ ] **Step 3: release/SKILL.md §6 마지막 줄 교체**

현재 68행:

```
{{#if repo.releasePath == "direct-push"}}확인 후: 버전 파일 + 노트 파일을 스테이징해 커밋하고 `git push origin {{repo.defaultBranch}}`.{{/if}}
```

아래로 교체 (direct-push 쪽 문자열은 **한 글자도 바꾸지 않는다** — 바이트 불변 조건):

```
{{#if repo.releasePath == "direct-push"}}확인 후: 버전 파일 + 노트 파일을 스테이징해 커밋하고 `git push origin {{repo.defaultBranch}}`.{{else}}확인 후 **릴리스 PR 경로**로 진행한다 (protected branch — 직접 push 금지):

1. `git checkout -b release/<릴리스 버전>` → 버전 파일 + 노트 파일 커밋 → `git push -u origin release/<릴리스 버전>`
2. PR 생성: `gh pr create --base {{repo.defaultBranch}} --head release/<릴리스 버전> --title "<릴리스 커밋 메시지와 동일>" --body-file <본문 파일>` — 본문은 `.superrelease/templates/release-pr-body.md` 골격을 채워 작성하라 (gh 미가용이면 GitHub MCP 폴백)
3. **여기서 중단한다** — 태그·Release는 PR 머지 후다. "PR이 머지되면 다시 릴리스를 요청하세요"라고 안내하라.

머지 후 재개: 1단계 preflight 6(중단 상태 감지)이 이 대기 상태를 잡는다. PR 머지 여부를 확인(`gh pr view <PR번호> --json state`)한 뒤 `git checkout {{repo.defaultBranch}} && git pull`로 머지 커밋을 받아 7단계(태그)부터 이어가라 — 태그는 머지 후 HEAD에 만든다(squash 머지로 sha가 바뀐다). PR이 아직 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}
```

- [ ] **Step 4: release/SKILL.md §8 next-snapshot 분기에 복귀 커밋 경로 한 줄**

현재 84행 앞부분:

```
`python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{else}}
```

아래로 교체 (기존 문장 뒤, `{{else}}` 앞에 조건 한 줄 삽입):

```
`python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.releasePath == "release-pr"}} (release-pr 레포: 이 복귀 커밋도 직접 push할 수 없다 — `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}}{{else}}
```

- [ ] **Step 5: templates/release-pr-body.md 생성**

`skills/init/assets/templates/release-pr-body.md` (전문):

```
{{#unless scope.notes.language == "en"}}<!-- 릴리스 PR 본문 템플릿. {version} 등은 PR 생성 시점에 채운다. -->
## 릴리스 {version}

<!-- 하이라이트 1~3개를 한 문단으로 -->

### 이 PR에 대해

- 버전 파일과 릴리스 노트만 변경한다 (기능 변경 없음).
- 머지되면 {version} 태그{{#if github.release}}와 GitHub Release{{/if}} 생성이 이어진다 — 머지 후 릴리스 재개를 요청하라.
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Release-PR body template. Fill {version} when opening the PR. -->
## Release {version}

### About this PR

- Touches version files and release notes only (no functional change).
- Merging unblocks the {version} tag{{#if github.release}} and GitHub Release{{/if}} — ask to resume the release afterwards.
{{/unless}}
```

- [ ] **Step 6: manifest.json에 엔트리 추가**

`templates/changelog-entry.md` 엔트리 **뒤**에 삽입:

```json
    {
      "src": "templates/release-pr-body.md",
      "dest": ".superrelease/templates/release-pr-body.md",
      "render": true,
      "preserve": "template",
      "when": "repo.releasePath == \"release-pr\""
    },
```

- [ ] **Step 7: 통과 확인 + 골든 바이트 불변 증명**

Run: `cd tests && python3 -m unittest test_assets test_golden -v 2>&1 | tail -8`
Expected: 전부 PASS — 특히 `test_golden`이 **재생성 없이** GREEN(기존 6트리 바이트 불변). `git status --porcelain tests/golden` 출력이 비어 있어야 한다.

- [ ] **Step 8: 전체 스위트 + 커밋**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK 확인 후:

```bash
git add skills/init/assets/skills/release/SKILL.md skills/init/assets/templates/release-pr-body.md skills/init/assets/manifest.json tests/test_assets.py
git commit -m "feat: 단일 release 스킬 릴리스 PR 경로 + release-pr-body 템플릿 (기존 렌더 바이트 불변)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 모노레포 release 스킬 — 릴리스 PR 분기

**Files:**
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (§7 끝 줄, §9)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: Task 1과 동일한 repo.* 키 + `.superrelease/templates/release-pr-body.md`(Task 1 산출물 — 모노레포 config에서도 manifest `when`이 동일하게 적용됨).
- Produces: pnpm-monorepo류 config의 release-pr 렌더 프로즈. **scope 값 인라인 금지 유지** — 이 분기에는 repo.* 값만 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py**

`MonorepoAssetsTest` 클래스의 `test_release_monorepo_omits_github_when_disabled` 뒤에 추가:

```python
    def test_release_monorepo_release_pr_branch(self):
        ctx = mono_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release-monorepo/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("릴리스 PR", out)
        self.assertIn("gh pr create", out)
        self.assertIn("scope당 1커밋", out)
        self.assertNotIn("git push origin main`", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_monorepo_direct_push_has_no_pr_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("git push origin main", out)
        self.assertNotIn("릴리스 PR", out)
        self.assertNotIn("gh pr create", out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest -v 2>&1 | tail -6`
Expected: `test_release_monorepo_release_pr_branch` FAIL, `..._direct_push_has_no_pr_prose` PASS.

- [ ] **Step 3: release-monorepo/SKILL.md §7 마지막 줄 교체**

현재 73행:

```
{{#if repo.releasePath == "direct-push"}}확인 후: scope별로 버전 파일 + 노트 파일을 커밋하고(여러 scope면 scope당 1커밋) `git push origin {{repo.defaultBranch}}`.{{/if}}
```

아래로 교체 (direct-push 쪽 문자열 불변):

```
{{#if repo.releasePath == "direct-push"}}확인 후: scope별로 버전 파일 + 노트 파일을 커밋하고(여러 scope면 scope당 1커밋) `git push origin {{repo.defaultBranch}}`.{{else}}확인 후 **릴리스 PR 경로**: 릴리스 브랜치 하나를 만들어(`release/<첫 scope>@<버전>`, 복수 대상이면 `+N` 접미 — 브랜치명을 프리뷰에 명시) scope당 1커밋으로 쌓고 push → PR 1건 생성(`gh pr create --base {{repo.defaultBranch}}` — 제목에 포함 릴리스를 나열하고, 본문은 `.superrelease/templates/release-pr-body.md` 골격에 scope별 섹션을 채워라; gh 미가용이면 GitHub MCP 폴백) → **중단한다**(태그는 머지 후). 머지 후 재개: 1단계 preflight 6의 중단 상태 감지가 잡는다 — PR 머지 확인 후 `git checkout {{repo.defaultBranch}} && git pull` 하고 scope별로 8단계(태그)부터 이어가라. PR이 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}
```

- [ ] **Step 4: release-monorepo/SKILL.md §9 첫 문장에 복귀 커밋 경로 한 줄**

현재 87행:

```
그 scope의 config `postRelease.bump`가 next-snapshot이면 `python3 .superrelease/scripts/next-version.py --scope <name> --bump patch --qualifier <그 scope의 preRelease.qualifier>` → `version.py set --scope` → 같은 방식으로 프리뷰·확인 후 커밋·push. none이면 파일 버전을 그대로 둔다.
```

아래로 교체 (`커밋·push.` 뒤에 조건 삽입):

```
그 scope의 config `postRelease.bump`가 next-snapshot이면 `python3 .superrelease/scripts/next-version.py --scope <name> --bump patch --qualifier <그 scope의 preRelease.qualifier>` → `version.py set --scope` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.releasePath == "release-pr"}} (release-pr 레포: 복귀 커밋도 `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}} none이면 파일 버전을 그대로 둔다.
```

- [ ] **Step 5: 통과 확인 + pnpm 골든 바이트 불변 증명**

Run: `cd tests && python3 -m unittest test_assets test_golden -v 2>&1 | tail -6`
Expected: 전부 PASS, `git status --porcelain tests/golden` 비어 있음.

- [ ] **Step 6: 전체 스위트 + 커밋**

```bash
git add skills/init/assets/skills/release-monorepo/SKILL.md tests/test_assets.py
git commit -m "feat: 모노레포 release 스킬 릴리스 PR 경로 (pnpm 골든 바이트 불변)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: hotfix 스킬 신규 + manifest + 검증 규칙

**Files:**
- Create: `skills/init/assets/skills/hotfix/SKILL.md`
- Modify: `skills/init/assets/manifest.json` (skills 그룹에 엔트리 1개)
- Modify: `skills/init/scripts/render.py` (validate_config에 규칙 1건 — **엔진부 금지, 검증 함수만**)
- Test: `tests/test_assets.py`, `tests/test_render_pipeline.py`

**Interfaces:**
- Consumes: config `repo.maintenanceLines`(bool), `repo.releasePath`, `repo.defaultBranch`, `repo.tagTriggersDeployment`, `github.release`, `scope.tag.movingMajorTag`, `scope.postRelease.bump`, `scope.preRelease.qualifier` — 모두 기존 키.
- Produces: 렌더 산출물 `.claude/skills/hotfix/SKILL.md`(maintenanceLines=true일 때만). render.py 검증 규칙: `repo.maintenanceLines`가 truthy이면서 `repo.monorepoStrategy == "independent"`이면 config 오류(exit 1). Task 4 골든 `hotfix-library`와 Task 5 문서가 의존.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_assets.py**

`SkillAssetsTest`에 (Task 1에서 추가한 메서드들 뒤) 추가:

```python
    def test_hotfix_skill_renders_clean(self):
        out = self.render_asset("skills/hotfix/SKILL.md")
        self.assertNotIn("{{", out)
        self.assertIn("demo-app", out)
        self.assertIn("체리픽", out)
        self.assertIn("--bump patch", out)
        self.assertIn("release/1.2.x", out)
        self.assertIn("git push origin release/", out)  # direct-push 기본
        self.assertNotIn("gh pr create", out)
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_hotfix_skill_release_pr_path(self):
        ctx = base_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertIn("gh pr create --base release/", out)
        self.assertIn("hotfix/<패치 버전>", out)
```

`FullRenderTest`에 추가:

```python
    def test_maintenance_lines_full_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "demo-app"
            repo.mkdir()
            cfg = scope_config(
                [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
            cfg["repo"]["maintenanceLines"] = True
            write(repo / ".superrelease" / "config.json",
                  json.dumps(cfg, ensure_ascii=False, indent=2))
            write(repo / "gradle.properties", "version=0.1.0\n")
            r = run_script(PLUGIN_SCRIPTS / "render.py",
                           "--config", repo / ".superrelease" / "config.json",
                           "--assets", ASSETS, "--repo", repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            hotfix = (repo / ".claude/skills/hotfix/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("generated by superrelease", hotfix)
            self.assertIn("체리픽", hotfix)
```

그리고 기존 `test_real_assets_render_end_to_end`에 (Task 1에서 추가한 assertFalse 줄 옆) 추가:

```python
            self.assertFalse((repo / ".claude/skills/hotfix/SKILL.md").exists())
```

**tests/test_render_pipeline.py**의 `PipelineTest` 클래스에 추가 (`test_invalid_config_exits_1` 뒤 — 검증은 manifest 처리 전에 실행되므로 합성 트리 픽스처 그대로 쓴다; `monorepo_config`는 이미 import돼 있다):

```python
    def test_maintenance_lines_rejected_for_independent(self):
        cfg = monorepo_config()
        cfg["repo"]["maintenanceLines"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("maintenanceLines", r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets test_render_pipeline -v 2>&1 | tail -10`
Expected: hotfix 렌더 테스트들 ERROR(파일 없음), `test_maintenance_lines_rejected_for_independent` FAIL(현재는 exit 0으로 렌더됨), `test_maintenance_lines_full_render` FAIL(파일 미생성).

- [ ] **Step 3: skills/init/assets/skills/hotfix/SKILL.md 생성 (전문)**

```
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
- 범위 anchor는 이 라인의 마지막 태그: 라인 체크아웃 상태에서 `git describe --tags --abbrev=0`
- 버전 반영: `python3 .superrelease/scripts/version.py set <패치 버전>`
- 노트: `.claude/skills/release-notes/SKILL.md` 절차로 초안을 쓰고, config `scopes[].notes.destinations` 목적지 반영은 release 스킬 5단계와 동일하게 하라.

## 5. dry-run 프리뷰 → 커밋

release 스킬 6단계와 같은 표준 프리뷰(파일 diff·커밋 메시지·태그명·명령 목록{{#if repo.tagTriggersDeployment}}·⚠️ 태그의 CI 배포 트리거 경고{{/if}}·노트 미리보기)를 보여주고 확인받아라.

{{#if repo.releasePath == "direct-push"}}확인 후: 버전 파일 + 노트 파일을 커밋하고 `git push origin release/<라인>`.{{else}}확인 후(릴리스 PR 경로): `git checkout -b hotfix/<패치 버전>` → 커밋 → push → `gh pr create --base release/<라인> --head hotfix/<패치 버전>` — **base는 유지보수 라인이다**. PR 머지 후 재개해 6단계(태그)부터 이어가라.{{/if}}

## 6. 태그{{#if github.release}} + GitHub Release{{/if}}

release 스킬 7단계와 동일하다: `git ls-remote --tags origin <태그>`로 충돌 재확인(결과가 있으면 즉시 중단) → 태그 생성·push{{#if github.release}} → Release 생성{{/if}}.
{{#if scope.tag.movingMajorTag}}- moving major tag는 이 핫픽스가 해당 major의 **최신 릴리스일 때만** 옮겨라 — 더 높은 minor/patch가 이미 릴리스돼 있으면 옮기지 않는다.{{/if}}

## 7. post-release와 {{repo.defaultBranch}} 반영

- {{#if scope.postRelease.bump == "next-snapshot"}}라인에도 동일 정책을 적용한다: `python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 5단계와 같은 경로로 프리뷰·확인 후 커밋.{{else}}post-release bump 없음 — 라인의 파일 버전은 릴리스 버전 그대로 둔다.{{/if}}
- 핫픽스 수정이 `{{repo.defaultBranch}}`에도 필요한지 확인하라. 라인에서 직접 고쳤다면 그 커밋의 체리픽 백을 제안하고, 원래 `{{repo.defaultBranch}}`에서 가져온 수정이면 불필요하다.

## 실패 시

어디까지 진행됐는지(체리픽 / 파일 수정 / 커밋 / push / 태그 / Release)와 되돌리는 방법을 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 버전은 다음 패치로 덮는다.
```

- [ ] **Step 4: manifest.json에 hotfix 엔트리 추가**

`skills/release-notes-monorepo/SKILL.md` 엔트리 **뒤**(scripts 그룹 앞)에 삽입:

```json
    {
      "src": "skills/hotfix/SKILL.md",
      "dest": ".claude/skills/hotfix/SKILL.md",
      "render": true,
      "when": "repo.maintenanceLines"
    },
```

- [ ] **Step 5: render.py validate_config에 규칙 추가**

`validate_config` 함수 안, 기존 `monorepoStrategy` 규칙들(`problems.append('repo.monorepoStrategy is only valid ...')` 부근) 바로 뒤에:

```python
    if repo.get("maintenanceLines") and strategy == "independent":
        problems.append("repo.maintenanceLines (hotfix skill) is not supported "
                        "with the independent monorepo strategy")
```

- [ ] **Step 6: 통과 확인 + 골든 바이트 불변 증명**

Run: `cd tests && python3 -m unittest test_assets test_render_pipeline test_golden -v 2>&1 | tail -8`
Expected: 전부 PASS. `git status --porcelain tests/golden` 비어 있음(기존 6 config는 maintenanceLines=false → hotfix 미생성).

- [ ] **Step 7: 전체 스위트 + 커밋**

```bash
git add skills/init/assets/skills/hotfix/SKILL.md skills/init/assets/manifest.json skills/init/scripts/render.py tests/test_assets.py tests/test_render_pipeline.py
git commit -m "feat: hotfix 생성 스킬(유지보수 라인 patch 릴리스) + maintenanceLines 검증 규칙

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 골든 2종 — release-pr-app · hotfix-library

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/release-pr-app/expected/**`, `tests/golden/hotfix-library/expected/**` (update_golden 산출)

**Interfaces:**
- Consumes: Task 1~3의 자산·manifest (이 태스크는 그 결과를 스냅샷으로 고정할 뿐 자산을 수정하지 않는다).
- Produces: `GOLDEN` dict 8항목 — `test_golden`이 자동 순회한다.

- [ ] **Step 1: golden_configs.py에 config 2개 추가**

`calver_app` 함수 뒤에 추가하고 `GOLDEN` dict를 교체:

```python
def release_pr_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def hotfix_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["repo"]["maintenanceLines"] = True
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library}
```

(release-pr-app은 릴리스 PR 분기 + release-pr-body.md + postRelease none 조합을, hotfix-library는 hotfix 스킬 + SNAPSHOT post-release(§7 스냅샷 분기 렌더) + direct-push와 hotfix의 직교를 고정한다.)

- [ ] **Step 2: 골든 생성 + 범위 검증**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden | sort`
Expected: `?? tests/golden/hotfix-library/`·`?? tests/golden/release-pr-app/` **두 항목만**. ` M `으로 시작하는 기존 트리 변경이 하나라도 있으면 STOP — 원인을 고치고 `git checkout -- tests/golden` 후 재시도.

- [ ] **Step 3: 스냅샷 내용 스팟 확인**

Run:
```bash
grep -l "gh pr create" tests/golden/release-pr-app/expected/.claude/skills/release/SKILL.md
test -f tests/golden/release-pr-app/expected/.superrelease/templates/release-pr-body.md && echo body-ok
test -f tests/golden/hotfix-library/expected/.claude/skills/hotfix/SKILL.md && echo hotfix-ok
grep -c "gh pr create" tests/golden/hotfix-library/expected/.claude/skills/release/SKILL.md || echo direct-push-ok
```
Expected: 첫 grep 파일명 출력, `body-ok`, `hotfix-ok`, 마지막은 `0` 또는 `direct-push-ok`(hotfix-library의 release 스킬은 direct-push).

- [ ] **Step 4: 테스트 통과 확인 + 커밋**

Run: `cd tests && python3 -m unittest test_golden -v 2>&1 | tail -4` → 8 골든 전부 PASS.

```bash
git add tests/golden_configs.py tests/golden/release-pr-app tests/golden/hotfix-library
git commit -m "test: 골든 release-pr-app·hotfix-library 추가 — 릴리스 PR·hotfix 분기 회귀 방어

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: init 번들 6 해제 + 문서 정합

**Files:**
- Modify: `skills/init/SKILL.md` (번들 6, 지원 범위 목록, config 각주)
- Modify: `skills/init/references/branching-and-release-path.md`
- Modify: `README.md`, `README_KO.md` (로드맵)

**Interfaces:**
- Consumes: Task 1~3의 실동작(2단계 진행·hotfix 생성 조건·검증 규칙) — 문서는 구현과 정확히 일치해야 한다.
- Produces: init이 releasePath/maintenanceLines를 실제로 질문·기록하는 지시.

- [ ] **Step 1: skills/init/SKILL.md — 번들 6 교체**

현재:

```
- **번들 6 — 경로·브랜치**: protected branch 감지 시 릴리스 PR 모드가 필요함을 알리되 M1은 direct-push만 지원 — 진행 방법을 사용자와 확인 / 브랜치 전략 확인(신규는 trunk-based 기본 제안) / 유지보수 라인(M3 예정 표시).
```

교체:

```
- **번들 6 — 경로·브랜치**: 커밋 경로 direct-push | release-pr — protected branch(+required checks)가 감지되면 직접 push가 불가능하므로 release-pr를 강제 기본으로 제안하고, 아니면 direct-push 기본. release-pr를 선택하면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행됨을 안내한다 / 브랜치 전략 확인(신규는 trunk-based 기본 제안) / 유지보수 라인 운용 여부(스캔 `branches.releaseBranches`가 근거) — 운용하면 `repo.maintenanceLines: true`로 기록하고 hotfix 스킬이 생성됨을 안내한다. **단 semver 단일 스킬 레포 한정** — independent 모노레포·비semver scope에는 후속 표시하고 잠근다(render가 independent 조합을 거부한다).
```

- [ ] **Step 2: skills/init/SKILL.md — 지원 범위 목록 갱신**

현재 두 줄:

```
- 커밋 경로: direct-push만 — 릴리스 PR 모드는 M3b
```
```
- hotfix 스킬: M3b / CHANGELOG backfill: M3c
```

교체:

```
- 커밋 경로: direct-push | release-pr(보호 브랜치 — PR 생성 후 중단, 머지 후 태그 재개) 지원
```
```
- hotfix 스킬: semver 단일 스킬 레포 지원(independent 모노레포는 후속) / CHANGELOG backfill: M3c
```

- [ ] **Step 3: skills/init/SKILL.md — config 각주 2줄 추가**

config 예시 아래 각주 목록의 『- 모노레포: `repo.monorepoStrategy`를 …』 항목 **뒤**에 추가:

```
- 커밋 경로: `repo.releasePath`가 "release-pr"이면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행되고 `.superrelease/templates/release-pr-body.md`가 함께 생성된다. protected branch 레포는 release-pr가 사실상 유일한 경로다.
- hotfix: `repo.maintenanceLines: true`면 `.claude/skills/hotfix/SKILL.md`가 생성된다 — semver 단일 스킬 레포 한정(independent 모노레포 조합은 render가 거부한다).
```

- [ ] **Step 4: references/branching-and-release-path.md — "M3 예정" 서술 3곳 교체**

(1) 현재:

```
**hotfix 스킬 생성 자체는 M3에서 구현되며, M1에서는 아직 생성되지 않는다.**
```

교체:

```
**hotfix 스킬은 config `repo.maintenanceLines: true`로 설정하면 생성된다** — semver 단일 스킬 레포 한정이며, independent 모노레포와의 조합은 render가 거부한다.
```

(2) 현재:

```
**이 모드는 M3에서 구현되며, M1은 direct push 경로만 지원한다.**

M1 단계에서 protected branch가 감지되면, 릴리스 PR 모드가 아직 없다는 사실과 함께 "후속 버전 지원 예정"이라고 안내한다.
```

교체:

```
**릴리스 PR 모드는 config `repo.releasePath: "release-pr"`로 설정하면 릴리스 스킬이 수행한다.** 진행은 2단계다 — 버전 bump와 노트를 담은 PR을 만들고 일단 중단하며, PR이 머지된 뒤 릴리스를 다시 요청하면 태그와 Release를 만든다(릴리스 스킬의 중단 상태 감지가 이 대기 상태를 인식한다). 스킬은 required checks 대기나 자동 머지를 하지 않는다 — 머지는 사람과 레포 정책의 몫이다.

protected branch가 감지되면 init은 release-pr 모드를 강제 기본으로 제안한다 — direct push로는 대체할 수 없기 때문이다.
```

(3) 결정 트리의 현재:

```
   - 예 → 릴리스 PR 모드로 진행해야 한다 (M3에서 지원 — M1에서는 "후속 버전 지원 예정"으로 안내하고 direct push로 대체할 수 없음을 분명히 한다)
   - 아니오 → direct push로 진행한다 (M1 기본 지원 경로)
```

교체:

```
   - 예 → 릴리스 PR 모드로 진행해야 한다 (`repo.releasePath: "release-pr"` — direct push로 대체할 수 없다)
   - 아니오 → direct push로 진행한다 (기본 경로)
```

- [ ] **Step 5: README.md / README_KO.md 로드맵 갱신 (1:1 유지)**

README.md 현재:

```
- **M3a (current)** — version schemes: CalVer/HeadVer arithmetic, counter
  pre-releases (`-rc.N`), moving major tags
- **M3b** — release paths: release-PR mode for protected branches, hotfix flow
```

교체:

```
- **M3a (shipped)** — version schemes: CalVer/HeadVer arithmetic, counter
  pre-releases (`-rc.N`), moving major tags
- **M3b (current)** — release paths: release-PR mode for protected branches
  (two-phase: PR → merge → tag), hotfix flow on maintenance lines
```

README_KO.md 현재:

```
- **M3a (현재)** — 버전 체계: CalVer/HeadVer 산술, 카운터형 pre-release
  (`-rc.N`), moving major tag
- **M3b** — 릴리스 경로: 보호 브랜치용 릴리스 PR 모드, hotfix 플로우
```

교체:

```
- **M3a (완료)** — 버전 체계: CalVer/HeadVer 산술, 카운터형 pre-release
  (`-rc.N`), moving major tag
- **M3b (현재)** — 릴리스 경로: 보호 브랜치용 릴리스 PR 모드
  (2단계: PR → 머지 → 태그), 유지보수 라인 hotfix 플로우
```

- [ ] **Step 6: 정합 검증 + 커밋**

Run:
```bash
grep -c "M3b" skills/init/SKILL.md            # 기대: 0 (예정 표시 소거; M3c는 남아도 됨)
grep -n "M3 예정\|M1은 direct\|M3에서 구현" skills/init/references/branching-and-release-path.md  # 기대: 출력 없음
wc -l skills/init/SKILL.md                    # 기대: ≤500
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # 기대: OK, 골든 불변
```

```bash
git add skills/init/SKILL.md skills/init/references/branching-and-release-path.md README.md README_KO.md
git commit -m "feat: init 번들6(경로·브랜치) 해제 + 릴리스 경로 문서 정합 (M3b)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 최종 검증 (컨트롤러 직접 수행, 커밋 없음)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 전체 스위트 + strict**

```bash
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK
cd .. && claude plugin validate . --strict                                # 통과
git status --porcelain                                                    # 비어 있음
```

- [ ] **Step 2: 릴리스 PR 모드 e2e (스펙 §12 M3 완료 기준 — protected-branch 샘플 렌더)**

임시 디렉터리에 release-pr config(scope_config + `repo.releasePath="release-pr"`)를 작성하고 render.py를 실행해 확인:
- `.superrelease/templates/release-pr-body.md` 생성됨 + 마커 존재
- release SKILL.md에 `gh pr create`·"여기서 중단"·"머지 후 재개" 프로즈, direct-push push 문장 부재
- `.claude/skills/hotfix/SKILL.md` 부재

- [ ] **Step 3: hotfix 시나리오 e2e (스펙 §12 M3 완료 기준 — 렌더·내용 수준)**

임시 디렉터리에 maintenanceLines=true config로 render.py 실행:
- `.claude/skills/hotfix/SKILL.md` 생성 — "체리픽"·"--bump patch"·"release/1.2.x"·moving tag 방어 문구 확인
- 같은 config에 `monorepoStrategy: "independent"`(+scopes 2개, kind: monorepo)를 넣으면 render exit 1 + stderr에 maintenanceLines

- [ ] **Step 4: 골든 스팟 + 결과 보고**

- `git diff --stat main..HEAD -- tests/golden` 이 신규 2트리만 포함하는지 확인
- 133 → 신규 테스트 수 포함 총 개수, 커밋 목록, 골든 8종 상태를 원장(.superpowers/sdd/progress.md)에 기록

---

## 스펙 커버리지 자체 점검

- §4.3 번들 6(경로·브랜치 질문) → Task 5
- §5.3 manifest `when`(hotfix·조건부 템플릿 예시) → Task 1·3
- §6.1 생성물 트리(hotfix/SKILL.md, release-pr-body.md) → Task 1·3·4
- §6.3 절차 6(direct push 또는 릴리스 PR) → Task 1·2
- §6.5 hotfix(라인 체크아웃→체리픽→patch 릴리스→main 반영 확인) → Task 3
- §12 M3 완료 기준 중 M3b 몫(protected-branch 릴리스 PR e2e, hotfix 시나리오) → Task 6 (렌더·내용 수준 — 실 레포 대화형 릴리스는 플러그인 테스트 범위 밖, M1부터의 준용 관례)
- release-train·notes-train·backfill·fragment/tag-message·`repo.train` → **비범위(M3c)**. hotfix의 independent 모노레포 지원·비semver hotfix → 비범위(후속).
