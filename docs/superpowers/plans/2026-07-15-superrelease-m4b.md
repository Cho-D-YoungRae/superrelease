# superrelease M4b gitflow 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 죽은 `repo.branching` 필드를 실소비 enum으로 확정하고, develop 통합 브랜치에서 릴리스하는 gitflow 정식 사이클(develop cut → main 머지·태그 → develop back-merge + SNAPSHOT 복귀)을 release-pr 전용으로 지원한다.

**Architecture:** 스펙 [2026-07-15-superrelease-m4b-gitflow-design.md](../specs/2026-07-15-superrelease-m4b-gitflow-design.md)의 접근 A — 기존 release 스킬에 `{{#if repo.branching == "gitflow"}}` 조건 블록. 실분기는 세 곳뿐(preflight 기준 브랜치 인라인 / gitflow 전용 중단 감지 2종 / §8 back-merge·develop 복귀)이고 §6 cut·§7 태그·열린 PR 가드는 구조 동형이라 무변경. validate 규칙 5종이 gitflow의 전제(release-pr·단일 레포·developBranch)를 강제한다.

**Tech Stack:** Python 3.9+ 표준 라이브러리(render.py validate만), 동결 template dialect, unittest.

**베이스:** 브랜치 `feat/superrelease-m4b` (스펙 커밋 `dd7e643`, main `267dd3a`에서 분기).

## Global Constraints

- 전체 테스트: 레포 루트에서 `python3 -m unittest discover -s tests -q`. 단일 모듈: `cd tests && python3 -m unittest <모듈명> -v; cd ..` — dotted 형식 금지(ModuleNotFoundError). pytest 미설치.
- 동결 template dialect — **AND 없음**: 복합 조건은 중첩 `{{#if}}`로. 단일 중괄호 리터럴 보존.
- **바이트 불변**: 기존 골든 18종은 전부 branching `"trunk"` — gitflow 블록은 0바이트 collapse해야 하고, preflight 1·3 인라인 분기의 else 경로는 기존 텍스트와 바이트 동일해야 한다. T2의 `update_golden.py` 후 diff 0이 그 증명.
- 골든 규율: `python3 tests/update_golden.py` 후 `git status --porcelain tests/golden`이 각 태스크의 "예상 골든 diff"와 정확히 일치해야 한다.
- 생성 SKILL.md ≤150줄(release 현재 102줄), init SKILL.md ≤500줄(현재 146줄).
- render 엔진 무변경 — Python 변경은 `validate_config` 규칙 추가뿐. 스크립트 3종(version/next-version/changed-packages) 무변경.
- 코드·에러 메시지 영어 / 생성 스킬 프로즈·init 프로즈 한국어. 자립성: 생성물은 `.superrelease/`·`.claude/` 상대 경로만.
- 커밋 메시지 Conventional Commits 한국어 + `(M4b)` 접미, 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 별도 줄. 각 커밋 뒤 전체 스위트 green.

---

### Task 1: validate_config gitflow 규칙 5종 + helpers developBranch

**Files:**
- Modify: `skills/init/scripts/render.py` (validate_config — 라인 297의 versionLocations 루프 끝과 라인 298 `gh_cfg = ...` 사이에 블록 삽입)
- Modify: `tests/helpers.py:70-77` (scope_config의 repo dict)
- Test: `tests/test_render_pipeline.py` (PipelineTest 클래스)

**Interfaces:**
- Consumes: 없음.
- Produces: config 필드 규약 — `repo.branching` ∈ {"trunk","gitflow"}(미기록 허용 — missing은 템플릿에서도 trunk와 동일 렌더), gitflow면 `repo.releasePath=="release-pr"` + 비모노레포 + `repo.developBranch`(defaultBranch와 상이) 필수. 에러 메시지 키워드(후속 태스크 테스트가 참조): `repo.branching` / `release-pr` / `monorepo` / `developBranch` / `must differ`. helpers의 `scope_config()` repo에 `"developBranch": None` 추가 — T2의 gitflow_ctx·T3의 골든 config가 이 위에 얹는다.

- [ ] **Step 1: 실패하는 음성 테스트 5종 작성** — `tests/test_render_pipeline.py`의 `PipelineTest` 클래스에 추가:

```python
    def test_branching_enum_rejected(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "git-flow"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("repo.branching", r.stderr)

    def test_gitflow_requires_release_pr(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["developBranch"] = "develop"  # releasePath는 기본 direct-push
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("release-pr", r.stderr)

    def test_gitflow_rejected_for_monorepo(self):
        cfg = monorepo_config()
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["developBranch"] = "develop"
        cfg["repo"]["releasePath"] = "release-pr"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("monorepo", r.stderr)

    def test_gitflow_requires_develop_branch(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["releasePath"] = "release-pr"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("developBranch", r.stderr)

    def test_gitflow_develop_must_differ_from_default(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["releasePath"] = "release-pr"
        cfg["repo"]["developBranch"] = "main"  # defaultBranch와 동일
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("must differ", r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v; cd ..`
Expected: 신규 5개 전부 FAIL (returncode 0 — 규칙 부재).

- [ ] **Step 3: validate 규칙 구현** — `skills/init/scripts/render.py`의 validate_config에서 versionLocations 루프가 끝나는 지점(라인 297 `+ str(e))` 다음)과 `gh_cfg = config.get("github") or {}`(라인 298) 사이에 삽입 (`strategy` 변수는 라인 198에서 이미 정의됨):

```python
    branching = repo.get("branching")
    if branching and branching not in ("trunk", "gitflow"):
        problems.append('repo.branching must be "trunk" or "gitflow" '
                        '(got "{}")'.format(branching))
    if branching == "gitflow":
        if repo.get("releasePath") != "release-pr":
            problems.append('repo.branching "gitflow" requires releasePath '
                            '"release-pr": the release cycle is PR-based '
                            "(cut from the develop branch, merge to the "
                            "default branch)")
        if repo.get("kind") == "monorepo" or strategy:
            problems.append('repo.branching "gitflow" is not supported for '
                            "monorepos yet (single-skill repos only)")
        dev = repo.get("developBranch")
        if not dev:
            problems.append('repo.branching "gitflow" requires '
                            "repo.developBranch (the integration branch, "
                            'e.g. "develop")')
        elif dev == repo.get("defaultBranch"):
            problems.append("repo.developBranch must differ from "
                            "repo.defaultBranch (identical branches mean "
                            'trunk-based — use branching "trunk")')
```

- [ ] **Step 4: helpers에 developBranch 필드 추가** — `tests/helpers.py`의 `scope_config` 내 repo dict(라인 70-77)를 다음으로 교체:

```python
    repo = {
        "kind": "app", "defaultBranch": "main", "mergePolicy": "squash",
        "releasePath": "direct-push", "branching": "trunk",
        "developBranch": None,
        "maintenanceLines": False,
        "releaseCommitFormat": "chore(release): {version}",
        "tagTriggersDeployment": False,
        "monorepoStrategy": None,
    }
```

- [ ] **Step 5: 통과 + 전체 스위트 + 골든 무영향 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` → 전부 PASS
Run: `python3 -m unittest discover -s tests -q` → OK — render.py는 골든 미복사, config.json은 골든 스냅샷 스킵 대상이라 골든 무영향. 기존 config 전부 branching "trunk" → 규칙 1만 적용·통과(마이그레이션 무필요 증명).
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력.

- [ ] **Step 6: 커밋**

```bash
git add skills/init/scripts/render.py tests/helpers.py tests/test_render_pipeline.py
git commit -m "feat: validate — repo.branching enum + gitflow 전제(release-pr·단일 레포·developBranch) 규칙 5종 (M4b)"
```

---

### Task 2: release 스킬 gitflow 분기 (기존 골든 18종 바이트 불변)

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md:19,21,24,76,91-95`
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: T1의 helpers repo dict(developBranch 포함).
- Produces: `gitflow_ctx(**overrides)` 헬퍼(test_assets 모듈 레벨 — T4의 hotfix 테스트가 재사용). 렌더 문구 마커(골든·테스트가 참조): `중단 상태 감지 (gitflow)` / `gh pr list --state merged` / `merge-base --is-ancestor` / `back-merge`.

- [ ] **Step 1: 실패하는 렌더 단위 테스트 작성** — `tests/test_assets.py`. 먼저 모듈 레벨(기존 `train_ctx` 함수 뒤)에 ctx 헬퍼 추가:

```python
def gitflow_ctx(**overrides):
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-app"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx
```

`SkillAssetsTest` 클래스에 테스트 2개 추가:

```python
    def test_release_skill_gitflow_branch_and_detection(self):
        out = self.render_asset("skills/release/SKILL.md", gitflow_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("결과가 `develop`", out)          # preflight 1 기준 브랜치
        self.assertIn("origin/develop", out)             # preflight 3 원격 동기화
        self.assertIn("중단 상태 감지 (gitflow)", out)
        self.assertIn("gh pr list --state merged", out)  # 감지 (a)
        self.assertIn("merge-base --is-ancestor", out)   # 감지 (b)
        self.assertIn("back-merge", out)                  # §8
        self.assertIn("git merge main", out)
        self.assertNotIn("chore/next-dev", out)  # gitflow 복귀는 develop 직접
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_trunk_has_no_gitflow_prose(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 trunk·direct-push
        self.assertIn("결과가 `main`", out)
        self.assertNotIn("gitflow", out)
        self.assertNotIn("back-merge", out)
        self.assertNotIn("gh pr list --state merged", out)
        self.assertNotIn("merge-base --is-ancestor", out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..`
Expected: `test_release_skill_gitflow_branch_and_detection` FAIL(gitflow 문구 부재). trunk 음성 테스트는 PASS(회귀 핀).

- [ ] **Step 3: preflight 1·3 기준 브랜치 인라인** — `skills/init/assets/skills/release/SKILL.md`:

라인 19 교체 — 기존:

```
1. 현재 브랜치: `git branch --show-current` 결과가 `{{repo.defaultBranch}}` 여야 함
```

신규:

```
1. 현재 브랜치: `git branch --show-current` 결과가 `{{#if repo.branching == "gitflow"}}{{repo.developBranch}}{{else}}{{repo.defaultBranch}}{{/if}}` 여야 함{{#if repo.branching == "gitflow"}} (gitflow — 릴리스는 통합 브랜치에서 시작한다){{/if}}
```

라인 21 교체 — 기존:

```
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{repo.defaultBranch}} --count` 가 0
```

신규:

```
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{#if repo.branching == "gitflow"}}{{repo.developBranch}}{{else}}{{repo.defaultBranch}}{{/if}} --count` 가 0
```

- [ ] **Step 4: preflight 6 gitflow/trunk 중첩 분기** — 라인 24(한 소스 줄) 교체. 기존:

```
{{#if scope.tag.enabled}}6. 중단 상태 감지: 마지막 릴리스 태그가 존재하고 파일 버전이 그보다 높은데 **파일 버전 그대로의 태그가 없으면** 이전 릴리스가 중단된 것이다{{#if scope.preRelease.style == "mutable"}} (단, 파일 버전에 `-{{scope.preRelease.qualifier}}` 수식어가 붙어 있으면 정상 개발 상태 — 중단 아님){{/if}} — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.
```

신규 (여전히 한 소스 줄 — 바깥 `{{#if scope.tag.enabled}}` 게이트와 줄 구조는 그대로, 내부만 gitflow/trunk 분기):

```
{{#if scope.tag.enabled}}{{#if repo.branching == "gitflow"}}6. 중단 상태 감지 (gitflow): ① `gh pr list --state merged --json headRefName,mergedAt` 결과의 `release/<버전>` head 중 그 버전의 태그가 아직 없으면 이전 릴리스가 태그 전에 중단된 것 — 6단계의 "머지 후 재개"대로 7단계(태그)부터 이어가라. ② 최신 릴리스 태그(2단계 glob 규칙)가 현재 브랜치에서 도달 불가하면(`git merge-base --is-ancestor <태그> HEAD` 실패) 직전 릴리스의 back-merge가 누락된 것 — 8단계의 back-merge부터 복구하라.{{else}}6. 중단 상태 감지: 마지막 릴리스 태그가 존재하고 파일 버전이 그보다 높은데 **파일 버전 그대로의 태그가 없으면** 이전 릴리스가 중단된 것이다{{#if scope.preRelease.style == "mutable"}} (단, 파일 버전에 `-{{scope.preRelease.qualifier}}` 수식어가 붙어 있으면 정상 개발 상태 — 중단 아님){{/if}} — 이어서 진행(resume)/되돌리기(rollback) 중 사용자 선택을 받아라.{{/if}}
```

(`{{else}}`는 가장 안쪽 열린 `{{#if repo.branching == "gitflow"}}`에 바인딩되고, else 분기 안의 mutable 중첩 if는 자체 `{{/if}}`로 닫힌다 — trunk 렌더는 M4a 텍스트와 바이트 동일.)

- [ ] **Step 5: §6 중단 안내 1줄 (append seam)** — 라인 76 끝에 이어 붙인다. 기존 줄 끝:

```
3. **여기서 중단한다** — 태그·Release는 PR 머지 후다. "PR이 머지되면 다시 릴리스를 요청하세요"라고 안내하라.
```

신규 줄 끝 (같은 소스 줄에 계속):

```
3. **여기서 중단한다** — 태그·Release는 PR 머지 후다. "PR이 머지되면 다시 릴리스를 요청하세요"라고 안내하라.{{#if repo.branching == "gitflow"}} 머지 후에는 태그(7단계)와 develop back-merge(8단계)가 남아 있음을 함께 알려라.{{/if}}
```

- [ ] **Step 6: §8 back-merge + develop 복귀 분기** — 라인 91-95 영역 교체. 기존:

```
## 8. post-release

{{#if scope.postRelease.bump == "next-snapshot"}}릴리스 직후 다음 개발 버전으로 복귀한다 (기본 patch 증가, 다음 계획이 minor면 조정 확인):

`python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.releasePath == "release-pr"}} (release-pr 레포: 이 복귀 커밋도 직접 push할 수 없다 — `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}}{{else}}post-release bump 없음 — 파일 버전은 릴리스 버전 그대로 둔다.{{/if}}
```

신규 (back-merge 블록은 개행·빈 줄을 블록 **안**에 두어 trunk에서 0바이트 collapse; next-snapshot 괄호는 gitflow/trunk 분기로 chore/next-dev를 gitflow에서 제외):

```
## 8. post-release

{{#if repo.branching == "gitflow"}}태그 push 후 **back-merge**로 `{{repo.developBranch}}`를 동기화한다: `git checkout {{repo.developBranch}} && git pull` → `git merge {{repo.defaultBranch}}` (충돌이 나면 해결안을 사용자와 확인하며 진행) → 프리뷰·확인 후 `git push origin {{repo.developBranch}}`. push가 거부되면(`{{repo.developBranch}}` 보호) back-merge PR을 만들어 머지하라.

{{/if}}{{#if scope.postRelease.bump == "next-snapshot"}}릴리스 직후 다음 개발 버전으로 복귀한다 (기본 patch 증가, 다음 계획이 minor면 조정 확인):

`python3 .superrelease/scripts/next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}}` → `version.py set` → 같은 방식으로 프리뷰·확인 후 커밋·push.{{#if repo.branching == "gitflow"}} (gitflow: 이 복귀 커밋은 back-merge 후 `{{repo.developBranch}}`에서 수행한다 — `{{repo.defaultBranch}}`는 릴리스 버전을 유지한다){{else}}{{#if repo.releasePath == "release-pr"}} (release-pr 레포: 이 복귀 커밋도 직접 push할 수 없다 — `chore/next-dev` 브랜치로 후속 PR을 만들어 머지하라){{/if}}{{/if}}{{else}}post-release bump 없음 — 파일 버전은 릴리스 버전 그대로 둔다.{{/if}}
```

- [ ] **Step 7: 통과 확인 + 골든 바이트 불변 검증 (이 태스크의 핵심 게이트)**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → 전부 PASS
Run: `python3 -m unittest discover -s tests -q` → OK (기존 골든과 바이트 동일해야 하므로 test_golden도 재생성 없이 통과해야 한다)
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → **빈 출력** (18종 전부 trunk — gitflow 블록 0바이트 collapse + 인라인 else 경로 바이트 동일의 증명). 출력이 있으면 개행/시임 오류 — 고치기 전에는 진행 금지.
Run: `wc -l skills/init/assets/skills/release/SKILL.md` → ≤150 (예상 ~105).

- [ ] **Step 8: 커밋**

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py
git commit -m "feat: release 스킬 gitflow 분기 — develop 기준 preflight·감지 2종·back-merge (M4b)"
```

---

### Task 3: gitflow-app 골든 신설

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/gitflow-app/expected/**` (update_golden.py가 생성)

**Interfaces:**
- Consumes: T1 validate 규칙(이 config가 통과해야 렌더 가능), T2의 gitflow 프로즈.
- Produces: `GOLDEN` 19번째 항목 `gitflow-app`.

- [ ] **Step 1: config 함수 + GOLDEN 등록** — `tests/golden_configs.py`의 `monorepo_release_pr()` 뒤에 추가:

```python
def gitflow_app():
    # gitflow: develop cut → main 머지·태그 → back-merge. release-pr 전용(validate 강제)
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg
```

`GOLDEN` 딕셔너리 마지막에 `"gitflow-app": gitflow_app` 추가 (기존 항목 순서 유지):

```python
GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app, "train-monorepo": train_monorepo,
          "backfill-monorepo": backfill_monorepo,
          "backfill-release-pr": backfill_release_pr,
          "headver-app": headver_app, "fixed-monorepo": fixed_monorepo,
          "tagless-app": tagless_app, "monorepo-release-pr": monorepo_release_pr,
          "gitflow-app": gitflow_app}
```

- [ ] **Step 2: 생성 전 실패 확인**

Run: `cd tests && python3 -m unittest test_golden -v; cd ..`
Expected: FAIL — `golden missing — run: python3 tests/update_golden.py` (gitflow-app).

- [ ] **Step 3: 골든 생성 + 범위 확인**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: `tests/golden/gitflow-app/` 아래 untracked 파일 **만**. 기존 18개 트리 무변경.

- [ ] **Step 4: 내용 스모크** — `tests/golden/gitflow-app/expected/.claude/skills/release/SKILL.md`에서 확인: preflight 1이 `develop` 기준 / `중단 상태 감지 (gitflow)` / 열린 PR 가드(7번) 존재 / §8 back-merge 문단 + develop 복귀 괄호 / `chore/next-dev` 부재 / `release-pr-body.md` 템플릿 파일 존재.

- [ ] **Step 5: 전체 스위트 + 커밋**

Run: `python3 -m unittest discover -s tests -q` → OK

```bash
git add tests/golden_configs.py tests/golden
git commit -m "test: gitflow-app 골든 신설 (M4b)"
```

---

### Task 4: init 번들 6·스키마·지원 범위 + references + hotfix §7

**Files:**
- Modify: `skills/init/SKILL.md:53,74,141-146`
- Modify: `skills/init/references/branching-and-release-path.md:28-47`
- Modify: `skills/init/assets/skills/hotfix/SKILL.md:56`
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: T2의 `gitflow_ctx`.
- Produces: 최종 문서 정합 — 이후 없음.

- [ ] **Step 1: 실패하는 hotfix 렌더 테스트 작성** — `tests/test_assets.py`의 `SkillAssetsTest`에:

```python
    def test_hotfix_gitflow_mentions_develop_backport(self):
        ctx = gitflow_ctx()
        ctx["repo"]["maintenanceLines"] = True
        out = self.render_asset("skills/hotfix/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("`develop` 반영도 함께", out)
        out_trunk = self.render_asset("skills/hotfix/SKILL.md")
        self.assertNotIn("반영도 함께", out_trunk)
```

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → 신규 1개 FAIL.

- [ ] **Step 2: hotfix §7 gitflow 1줄 (append seam)** — `skills/init/assets/skills/hotfix/SKILL.md` 라인 56에서 `불필요하다.` 와 `{{#each scope.notes.destinations}}` 사이에 이어 붙인다. 기존 줄 시작부:

```
- 핫픽스 수정이 `{{repo.defaultBranch}}`에도 필요한지 확인하라. 라인에서 직접 고쳤다면 그 커밋의 체리픽 백을 제안하고, 원래 `{{repo.defaultBranch}}`에서 가져온 수정이면 불필요하다.{{#each scope.notes.destinations}}{{#if this == "changelog"}}
```

신규:

```
- 핫픽스 수정이 `{{repo.defaultBranch}}`에도 필요한지 확인하라. 라인에서 직접 고쳤다면 그 커밋의 체리픽 백을 제안하고, 원래 `{{repo.defaultBranch}}`에서 가져온 수정이면 불필요하다.{{#if repo.branching == "gitflow"}} gitflow 레포다 — `{{repo.defaultBranch}}` 반영을 확인할 때 `{{repo.developBranch}}` 반영도 함께 확인하라.{{/if}}{{#each scope.notes.destinations}}{{#if this == "changelog"}}
```

- [ ] **Step 3: init SKILL.md 번들 6 확장** — 라인 53의 번들 6 항목에서 `브랜치 전략 확인(신규는 trunk-based 기본 제안)` 구절을 다음으로 교체:

```
브랜치 전략 — 스캔 `branches.hasDevelop`이 true면 명시적으로 묻는다: trunk 유지(develop 정리 권장 — 추천) | gitflow(develop에서 릴리스 cut). gitflow 선택 시 `repo.branching: "gitflow"` + `repo.developBranch`(감지된 통합 브랜치명, 관례 기본 develop)를 기록하고 **releasePath를 release-pr로 잠근다**(보호 여부 무관 — 사이클이 PR 기반이며 render가 다른 조합을 거부한다). 릴리스 사이클(develop에서 cut → PR to 기본 브랜치 → 머지 후 태그 → develop back-merge·SNAPSHOT 복귀)을 안내하라. gitflow는 단일 스킬 레포 한정(모노레포 조합은 render 거부 — 후속 표시). hasDevelop이 false면 trunk 기본 제안(gitflow 선택지는 유지)
```

- [ ] **Step 4: init 스키마 예시에 developBranch** — 라인 74의 `"branching": "trunk",` 다음 줄에 `"developBranch": null,` 추가:

```json
    "branching": "trunk",
    "developBranch": null,
```

- [ ] **Step 5: 지원 범위 절에 브랜칭 축 추가** — 라인 141(`- 버전 체계: ...`) 앞에 항목 추가:

```
- 브랜칭: trunk / gitflow(단일 스킬 레포 · release-pr 전용 — develop cut → 기본 브랜치 태그 → back-merge 정식 사이클) 지원 — gitflow hotfix 흐름(main에서 hotfix/* cut)·모노레포×gitflow·direct-push gitflow는 후속
```

- [ ] **Step 6: references 재작성** — `skills/init/references/branching-and-release-path.md`의 "## git flow가 필요한 경우" 절(라인 28-47)을 다음으로 교체 (hotfix 관련 기존 문단·hotfix 흐름 4단계는 유지하고, 지원 선언과 사이클 규율을 추가):

```markdown
## git flow 지원 — 릴리스 사이클

git flow는 2010년 Vincent Driessen이 제안한 브랜칭 모델로, `develop`을 상시 통합 브랜치로 두고 `release/*`, `hotfix/*` 브랜치를 통해 릴리스와 긴급 수정을 별도로 관리한다.

참고: [nvie.com의 원문 글](https://nvie.com/posts/a-successful-git-branching-model/)

**superrelease는 gitflow 정식 릴리스 사이클을 지원한다** — config `repo.branching: "gitflow"` + `repo.developBranch`(통합 브랜치명). 단일 스킬 레포 · release-pr 전용이며(render가 다른 조합을 거부), 사이클은 다음과 같다.

1. preflight가 통합 브랜치(develop)를 기준으로 검사하고, 릴리스 브랜치(`release/<버전>`)를 develop에서 cut해 버전 bump·노트를 커밋한다.
2. PR base는 기본 브랜치(main)다 — PR이 열려 있는 동안 release 브랜치에 안정화 커밋을 쌓는 gitflow 관례가 그대로 성립한다. 머지는 사람과 레포 정책의 몫이다.
3. 머지 후 재개 시 기본 브랜치의 머지 커밋에 태그를 만든다.
4. **back-merge**: 태그 push 후 `main → develop`을 merge해 동기화한다(충돌은 사용자와 해결, develop이 보호돼 있으면 back-merge PR). postRelease가 next-snapshot이면 복귀 커밋은 back-merge 후 develop에서만 수행한다 — main은 릴리스 버전을 유지한다(Maven gitflow 관례).

중단 상태 감지도 gitflow 전용 2종으로 동작한다: ① 머지됐는데 미태깅인 release PR(태그 재개) ② 최신 릴리스 태그가 develop에서 도달 불가(back-merge 누락 — 복구). 파일 버전 기반 감지는 develop에서 미탐이라 쓰지 않는다.

gitflow의 **hotfix 흐름**(main에서 `hotfix/*` cut → main 머지·태그 → develop back-merge)은 후속 지원 예정이다. 그때까지 main 긴급 패치는 병렬 유지보수 라인(아래) 또는 수동 절차로 다룬다.

## 병렬 유지보수 라인이 필요한 경우

여러 released 버전을 동시에 유지보수해야 하는 제품 — 예를 들어 `release/1.x`를 계속 패치하면서 동시에 `release/2.x`나 main도 따로 진행하는 경우다.

이렇게 병렬 유지보수 라인을 운영하는지 여부(config `repo.maintenanceLines`)가 곧 hotfix 스킬을 생성할지 말지를 가르는 조건이다 — 유지보수 라인이 없다면 hotfix 스킬 자체가 필요 없다.

**hotfix 스킬은 config `repo.maintenanceLines: true`로 설정하면 생성된다** — semver 단일 스킬 레포 한정이며, independent 모노레포·비semver scope와의 조합은 render가 모두 거부한다. gitflow 레포와의 조합은 허용된다(병렬 라인 패치는 gitflow에도 존재한다).

반대로 과거 메이저 버전에 대한 보안 패치를 계속 내야 하는 라이브러리나 엔터프라이즈 제품이라면, trunk-based만으로는 "이미 릴리스된 옛 버전에 패치를 얹는" 시나리오를 감당하기 어렵다.

유지보수 라인을 운용하는 레포에서 hotfix 스킬이 생성되면, 그 스킬은 대략 다음 흐름을 따르게 된다.

1. 문제가 된 released 버전에 대응하는 유지보수 브랜치(예: `release/1.2.x`)를 체크아웃한다.
2. 고쳐야 할 커밋을 그 브랜치로 체리픽한다.
3. patch 릴리스를 만든다 (release 흐름 재사용).
4. 그 수정을 main에도 반영할지 확인한다 — gitflow 레포면 develop 반영도 함께 확인한다.
```

문서 상단(라인 5-10)의 비교 표에서 git flow 열의 "적합한 대상"은 그대로 두되, 표 아래에 지원 상태가 명시됐으므로 다른 수정은 하지 않는다.

- [ ] **Step 7: 통과 + 골든 확인 + 전체 스위트**

Run: `cd tests && python3 -m unittest test_assets -v; cd ..` → PASS
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden`
Expected: **빈 출력** — hotfix §7의 gitflow 게이트는 hotfix-library(trunk)에서 0바이트 collapse하고, gitflow-app은 maintenanceLines false라 hotfix 스킬이 없다. init SKILL.md·references는 골든 미복사.
Run: `python3 -m unittest discover -s tests -q` → OK
Run: `wc -l skills/init/SKILL.md` → ≤500 (예상 ~150).

- [ ] **Step 8: 커밋**

```bash
git add skills/init/SKILL.md skills/init/references/branching-and-release-path.md skills/init/assets/skills/hotfix/SKILL.md tests/test_assets.py
git commit -m "feat: init 번들6 브랜칭 질문 + gitflow 지원범위·references 정합 + hotfix develop 병기 (M4b)"
```

---

### Task 5: 최종 검증

**Files:** 없음 (검증 전용 — 문제 발견 시에만 수정 커밋)

**Interfaces:**
- Consumes: T1~T4 전부.
- Produces: M4b 완료 판정.

- [ ] **Step 1: 전체 검증 실행 및 기록**

```bash
python3 -m unittest discover -s tests -q            # OK (T1 +5, T2 +2, T4 +1 → 214개 예상)
claude plugin validate . --strict                    # PASS
wc -l skills/init/SKILL.md skills/init/assets/skills/*/SKILL.md   # init ≤500, 생성 스킬 각 ≤150
git status --porcelain                               # clean
git log --oneline dd7e643..HEAD                     # T1~T4 커밋 4개
```

- [ ] **Step 2: 스펙 대비 완료 기준 확인** — 아래 표의 각 행이 실제 커밋에 존재하는지 대조:

| 스펙 항목 | 태스크 |
|---|---|
| A validate 규칙 5종 + 마이그레이션(기존 config 통과) | T1 |
| B init 번들 6·지원 범위 | T4 |
| C preflight 1·3 인라인 / 감지 (a)(b) / §6 1줄 / §8 back-merge·develop 복귀 | T2 |
| D gitflow-app 골든(18→19) / 음성 5종 / 렌더 단위 / 기존 골든 바이트 불변 | T3 / T1 / T2·T4 / T2 |
| E references 재작성 / hotfix §7 1줄 / README는 M4d 이연 | T4 |

문제가 없으면 커밋 없이 종료. 발견 시 수정 후 `fix: ... (M4b)` 커밋.
