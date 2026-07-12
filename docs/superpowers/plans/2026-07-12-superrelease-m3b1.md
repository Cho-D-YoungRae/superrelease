# superrelease M3b.1 (브랜치 보호 조언 + 리뷰 follow-up) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superrelease에 (A) **브랜치 보호 조언** — init이 릴리스 PR 모드를 확정하는데 기본 브랜치가 미보호면 ruleset/branch-protection 설정 명령을 조언(실행은 사용자 몫)하고 `config.decisions`에 기록 — 과 (B) M3b 최종 리뷰 follow-up 3종(#4 비semver hotfix render 거부, #5 release-pr+next-snapshot 골든, #2 hotfix+release-pr 재개 한계 문서화)을 추가한다.

**Architecture:** 브랜치 보호 조언은 **fat init 스킬**의 일(번들 6 프로즈 + `references/branching-and-release-path.md` 지식 + 런타임 `config.decisions` 기록) — 생성 툴킷·골든과 무관하다. follow-up 중 #4는 `render.py`의 `validate_config` 규칙 1건(엔진부·산술 무변경), #2는 생성 hotfix 스킬의 release-pr 분기 한 줄(direct-push 골든 바이트 불변), #5는 신규 골든 1트리다. 기존 8골든은 바이트 불변, #5만 신규 추가한다.

**Tech Stack:** Python 3.9+ stdlib, 동결 template dialect(엔진 수정 금지), gh CLI(조언 대상 명령 — init은 실행하지 않음).

**스펙:** [docs/superpowers/specs/2026-07-12-superrelease-branch-protection-advice-design.md](../specs/2026-07-12-superrelease-branch-protection-advice-design.md). 베이스: main `fea5a92`(M1~M3b, 144 테스트, 골든 8종). 실행 컨트롤러는 main에서 `feat/superrelease-m3b1` 브랜치를 만들어 진행한다.

## Global Constraints

- **스크립트 산술·엔진 무변경.** version.py·next-version.py·changed-packages.py·scan.py·render.py **엔진부**(render_template/evaluate/parse/tokenize) 수정 금지. 유일한 Python 변경은 render.py **`validate_config` 규칙 1건**(#4 — render.py는 골든-복사 대상 아님, 골든 무영향).
- **골든 규율:** Task 1(#4 render 규칙 + #2 hotfix release-pr 분기 한 줄)은 골든 변경 **0** — #4 조합(maintenanceLines+비semver) 골든이 없고, #2는 hotfix-library가 direct-push라 release-pr 분기가 collapse되어 렌더 바이트 불변. `update_golden.py` 실행 금지, `python3 -m unittest test_golden`(from tests/) GREEN 유지 + `git status --porcelain tests/golden` 빈 출력이 증명. Task 3(#5)만 신규 1트리(`release-pr-snapshot/`)를 만들고, 그 외 기존 8트리가 하나라도 ` M `로 나오면 STOP(`git checkout -- tests/golden`).
- **동결 dialect만:** `{{path}}`, `{{#if}}`(`{{else}}`, `== "lit"`/`!= "lit"`), `{{#unless}}`, `{{#each}}`. 생성 SKILL.md ≤149줄, init SKILL.md ≤500줄. 코드·스크립트 메시지 영어, 생성 문서·init 프로즈 한국어.
- **브랜치 보호 조언은 조언만** — init은 레포 보안 설정을 **실행하지 않는다**(금지 사항). ruleset/classic 명령·웹 UI 경로를 제시하고 "직접 실행하세요"를 명시한다.
- 테스트: `cd tests && python3 -m unittest discover -p 'test_*.py'`. 커밋: Conventional Commits + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 파일 구조 (M3b.1 전체)

```
수정  skills/init/scripts/render.py                          # Task 1: validate_config 규칙 1건(#4)
수정  tests/test_render_pipeline.py                          # Task 1: #4 거부 테스트
수정  skills/init/assets/skills/hotfix/SKILL.md              # Task 1: §5 release-pr 재개 한계 한 줄(#2)
수정  tests/test_assets.py                                   # Task 1: hotfix 재개 한계 어서션(#2)
수정  skills/init/SKILL.md                                   # Task 2: 번들6 브랜치 보호 조언 + decisions 항목
수정  skills/init/references/branching-and-release-path.md   # Task 2: 조언 배경·명령·"실행은 사용자 몫"
수정  docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md  # Task 2: §13 "조언은 범위" 명확화
수정  tests/golden_configs.py                                # Task 3: release_pr_snapshot 빌더
생성  tests/golden/release-pr-snapshot/expected/**           # Task 3: update_golden
```

책임 분리: 조언 판단·프로즈 = fat init 스킬(런타임), 생성 여부·거부 = render 검증(결정론), hotfix 재개 한계 = 생성 스킬 프로즈, #5 상호작용 고정 = 골든.

---

### Task 1: #4 비semver hotfix render 거부 + #2 hotfix release-pr 재개 한계

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`)
- Test: `tests/test_render_pipeline.py`
- Modify: `skills/init/assets/skills/hotfix/SKILL.md` (§5 release-pr 분기)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: config `repo.maintenanceLines`(bool), scope `scheme.type`, `repo.releasePath`.
- Produces: render 검증 규칙 — `maintenanceLines` truthy이고 어떤 scope의 `scheme.type != "semver"`면 exit 1. hotfix 스킬 release-pr 분기의 재개 한계 프로즈.

- [ ] **Step 1: #4 실패 테스트 작성 — tests/test_render_pipeline.py**

`PipelineTest` 클래스(이미 `scope_config` import, `self.write_config`/`self.render` 헬퍼 보유)에서, 기존 `test_release_pr_rejected_for_tagless_scope` 메서드 **뒤**에 추가:

```python
    def test_maintenance_lines_rejected_for_non_semver_scheme(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["maintenanceLines"] = True
        cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("semver", r.stderr)
```

- [ ] **Step 2: #4 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_maintenance_lines_rejected_for_non_semver_scheme -v`
Expected: FAIL — 현재는 exit 0으로 렌더된다(해당 조합 미거부).

- [ ] **Step 3: #4 규칙 구현 — render.py validate_config**

`skills/init/scripts/render.py`의 `validate_config` 함수에서, 기존 `maintenanceLines`+`independent` 규칙 블록(`...with the independent monorepo strategy")`으로 끝나는 블록) **뒤**, tagless 규칙 **앞**에 삽입:

```python
    if repo.get("maintenanceLines") and scopes and any(
            (s.get("scheme") or {}).get("type", "semver") != "semver"
            for s in scopes):
        problems.append("repo.maintenanceLines (hotfix skill) requires semver "
                        "scopes; hotfix patch-bumps do not apply to "
                        "calver/headver schemes")
```

엔진부(tokenize/parse/evaluate/render_template)는 건드리지 않는다.

- [ ] **Step 4: #4 통과 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_maintenance_lines_rejected_for_non_semver_scheme -v`
Expected: PASS. 이어서 `test_maintenance_lines_rejected_for_independent`·`test_release_pr_rejected_for_tagless_scope`도 여전히 PASS(회귀 없음).

- [ ] **Step 5: #2 실패 테스트 작성 — tests/test_assets.py**

`SkillAssetsTest` 클래스의 `test_hotfix_skill_release_pr_path` 메서드에, 기존 어서션들 뒤(마지막 `assertNotIn("{{", out)` 뒤)에 한 줄 추가:

```python
        self.assertIn("수동으로", out)
```

- [ ] **Step 6: #2 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_hotfix_skill_release_pr_path -v`
Expected: FAIL — 현재 hotfix release-pr 분기에 "수동으로" 문구가 없다.

- [ ] **Step 7: #2 구현 — hotfix SKILL.md §5 release-pr 분기 한 줄**

`skills/init/assets/skills/hotfix/SKILL.md`의 §5 마지막 줄(`{{#if repo.releasePath == "direct-push"}}...{{else}}...{{/if}}`)에서, `{{else}}` 분기의 현재 문장:

```
{{else}}확인 후(릴리스 PR 경로): `git checkout -b hotfix/<패치 버전>` → 커밋 → push → `gh pr create --base release/<라인> --head hotfix/<패치 버전>` — **base는 유지보수 라인이다**. PR 머지 후 재개해 6단계(태그)부터 이어가라.{{/if}}
```

를 아래로 교체(direct-push 쪽은 불변, `{{else}}` 분기 끝에 한 문장 추가):

```
{{else}}확인 후(릴리스 PR 경로): `git checkout -b hotfix/<패치 버전>` → 커밋 → push → `gh pr create --base release/<라인> --head hotfix/<패치 버전>` — **base는 유지보수 라인이다**. PR 머지 후 재개해 6단계(태그)부터 이어가라. hotfix는 release 스킬과 달리 중단 상태를 자동 감지하지 않으니 — 머지 후 태그 단계를 **수동으로** 진행하고 체리픽·버전 반영을 반복하지 마라.{{/if}}
```

- [ ] **Step 8: #2 통과 확인 + 골든 바이트 불변**

Run: `cd tests && python3 -m unittest test_assets test_render_pipeline test_golden -v 2>&1 | tail -6`
Expected: 전부 PASS. `git status --porcelain tests/golden` 빈 출력 — hotfix-library 골든은 direct-push라 §5 else가 collapse되어 바이트 불변(재생성 불필요).

- [ ] **Step 9: 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK 확인 후:

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py skills/init/assets/skills/hotfix/SKILL.md tests/test_assets.py
git commit -m "fix: 비semver hotfix render 거부 + hotfix release-pr 재개 한계 명시 (M3b.1 #4·#2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 브랜치 보호 조언 (init 번들 6 + 지식 문서 + 스펙 §13)

**Files:**
- Modify: `skills/init/SKILL.md` (번들 6, decisions 기록 안내)
- Modify: `skills/init/references/branching-and-release-path.md`
- Modify: `docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md` (§13)

**Interfaces:**
- Consumes: Phase 1 스캔이 읽는 protected branch 상태(init SKILL.md Phase 1 단계 2 — `gh api .../branches/<b>/protection`, 404=미보호), config `repo.releasePath`.
- Produces: init이 release-pr + 미보호일 때 보호 설정을 조언하고 `config.decisions`에 `{topic:"branch-protection", ...}`를 기록하는 지시.

이 태스크는 **fat init 스킬·지식 문서·스펙**만 수정한다(골든-복사 대상 아님 — 골든·테스트 무영향). 프로즈 태스크라 RED-GREEN 대신 검증은 grep + 줄 수 + `--strict` + 전체 스위트 무변경으로 한다.

- [ ] **Step 1: init SKILL.md 번들 6 교체**

`skills/init/SKILL.md`의 번들 6 항목 전체(현재 `- **번들 6 — 경로·브랜치**: 커밋 경로 direct-push | release-pr — ...(render가 independent 조합을 거부한다).`)를 아래로 교체:

```
- **번들 6 — 경로·브랜치**: 커밋 경로 direct-push | release-pr — protected branch(+required checks)가 감지되면 직접 push가 불가능하므로 release-pr를 강제 기본으로 제안하고, 아니면 direct-push 기본. release-pr를 선택하면 릴리스가 2단계(PR 생성 → 머지 후 태그 재개)로 진행됨을 안내한다. **release-pr로 정했는데 기본 브랜치가 미보호(Phase 1에서 protection 404)면**, PR 흐름이 강제력을 가지려면 보호가 필요함을 알리고 사용자가 **직접 실행할** 설정을 조언한다 — 현대적 방법은 repository ruleset(`gh api --method POST repos/{owner}/{repo}/rulesets` 로 기본 브랜치에 pull_request 필수 + required_status_checks 규칙), 클래식 방법은 `gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection`, 웹 UI는 Settings → Rules → Rulesets. **init은 이 명령을 실행하지 않는다**(레포 보안 설정 — 사용자 몫). 이미 보호됨이면 조언하지 않는다. 어느 경우든 `decisions`에 `{"topic":"branch-protection","answer":"advised"|"already-protected","rationale":"<근거>","source":"scan","decidedAt":"<date>"}`를 기록한다(gh 미가용으로 보호 상태 미확인이면 answer는 `"unknown"`으로 두고 일반 권고만 언급) / 브랜치 전략 확인(신규는 trunk-based 기본 제안) / 유지보수 라인 운용 여부(스캔 `branches.releaseBranches`가 근거) — 운용하면 `repo.maintenanceLines: true`로 기록하고 hotfix 스킬이 생성됨을 안내한다. **단 semver 단일 스킬 레포 한정** — independent 모노레포·비semver scope에는 후속 표시하고 잠근다(render가 두 조합을 모두 거부한다).
```

- [ ] **Step 2: init SKILL.md 줄 수·정합 확인**

Run:
```bash
grep -c "branch-protection" skills/init/SKILL.md   # 기대: 1 이상
grep -c "rulesets" skills/init/SKILL.md             # 기대: 1 이상
wc -l skills/init/SKILL.md                          # 기대: ≤500
```
Expected: branch-protection·rulesets 문자열 존재, 줄 수 ≤500.

- [ ] **Step 3: branching-and-release-path.md 보강**

`skills/init/references/branching-and-release-path.md`의 "protected branch 감지 시: 릴리스 PR 모드" 절에서, M3b Task 5가 넣은 재개 한계 문단(`릴리스 PR 재개는 **기존 릴리스 태그가 있다는 전제**에 기댄다 ...`) **뒤**에 새 문단을 추가:

```
릴리스 PR 모드를 선택했는데 기본 브랜치가 실제로는 **보호되지 않았다면** 그 PR 흐름은 강제력이 없다 — 누구나 main에 직접 push할 수 있기 때문이다. 그래서 init은 이 조합(release-pr + 미보호)을 감지하면 보호 설정을 **조언**한다. 현대적 방법은 repository ruleset(`gh api --method POST repos/{owner}/{repo}/rulesets` — 기본 브랜치에 `pull_request` 필수와, CI가 있으면 `required_status_checks`를 거는 규칙)이고, 클래식 방법은 branch protection(`gh api --method PUT repos/{owner}/{repo}/branches/{branch}/protection`)이며, 웹 UI로는 Settings → Rules → Rulesets에서 만든다.

이 설정은 레포의 보안·접근 규칙이므로 **사용자가 직접 실행한다** — init·생성 스킬은 명령을 제시할 뿐 대신 실행하지 않는다(감지·조언은 범위, 설정 변경은 비범위). 이는 CI 태그 트리거를 감지·경고만 하고 워크플로를 생성하지 않는 것, dev 채널 immutableId를 기록·안내만 하는 것과 같은 원칙이다.
```

- [ ] **Step 4: 스펙 §13 비범위 "조언은 범위" 명확화**

`docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md` §13 비범위 목록의 현재 항목:

```
- 브랜치 보호 규칙 설정 변경
```

를 아래로 교체:

```
- 브랜치 보호 규칙 설정 **변경** (init·생성 스킬은 규칙을 대신 만들지 않는다 — 단, release-pr + 미보호 감지 시 ruleset/branch-protection 설정 명령을 **조언**하는 것은 범위)
```

- [ ] **Step 5: 정합 검증 + 커밋**

Run:
```bash
grep -n "조언은 범위\|조언" docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md | head -3
grep -c "직접 실행" skills/init/references/branching-and-release-path.md   # 기대: 1 이상
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3     # 기대: OK(프로즈 변경이라 무영향), 골든 clean
cd .. && claude plugin validate . --strict 2>&1 | tail -1                  # 기대: 통과
```

```bash
git add skills/init/SKILL.md skills/init/references/branching-and-release-path.md docs/superpowers/specs/2026-07-09-superrelease-plugin-design.md
git commit -m "feat: init 브랜치 보호 조언(release-pr + 미보호) + 스펙 §13 조언 범위 명확화 (M3b.1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: #5 골든 — release-pr + next-snapshot 상호작용 고정

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/release-pr-snapshot/expected/**` (update_golden 산출)

**Interfaces:**
- Consumes: `helpers.scope_config`(기본 preRelease mutable/SNAPSHOT + postRelease next-snapshot + tag.enabled true + releasePath direct-push), M3b의 release-pr §else·§8 `chore/next-dev` 조건.
- Produces: `GOLDEN` dict 9항목. `test_golden`이 자동 순회한다.

이 태스크는 자산·스크립트를 수정하지 않는다 — release-pr + next-snapshot 조합을 스냅샷으로 고정할 뿐이다. `update_golden.py` 실행이 정상이다.

- [ ] **Step 1: golden_configs.py에 빌더 추가 + GOLDEN 갱신**

`tests/golden_configs.py`의 `hotfix_library` 함수 **뒤**에 추가하고 `GOLDEN` dict를 교체:

```python
def release_pr_snapshot():
    # release-pr + 기본 mutable/next-snapshot → §8이 chore/next-dev 복귀 라인을 렌더한다
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot}
```

- [ ] **Step 2: 골든 생성 + 범위 검증**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden | sort`
Expected: `?? tests/golden/release-pr-snapshot/` **한 항목만**. ` M `으로 시작하는 기존 트리 변경이 하나라도 있으면 STOP(`git checkout -- tests/golden` 후 원인 규명).

- [ ] **Step 3: 스냅샷 스팟 확인**

Run:
```bash
grep -c "gh pr create" tests/golden/release-pr-snapshot/expected/.claude/skills/release/SKILL.md   # 기대: ≥1 (release-pr §else)
grep -c "chore/next-dev" tests/golden/release-pr-snapshot/expected/.claude/skills/release/SKILL.md  # 기대: 1 (§8 next-snapshot + release-pr 인라인)
test -f tests/golden/release-pr-snapshot/expected/.superrelease/templates/release-pr-body.md && echo body-ok  # 기대: body-ok
```
Expected: `gh pr create` ≥1, `chore/next-dev` = 1(이 골든이 #5의 목적 — 이 라인이 다른 골든엔 없다), body-ok.

- [ ] **Step 4: 테스트 통과 + 커밋**

Run: `cd tests && python3 -m unittest test_golden -v 2>&1 | tail -4` → 9 골든 전부 PASS. 이어서 `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add tests/golden_configs.py tests/golden/release-pr-snapshot
git commit -m "test: 골든 release-pr-snapshot 추가 — release-pr+next-snapshot chore/next-dev 상호작용 고정 (M3b.1 #5)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 최종 검증 (컨트롤러 직접 수행, 커밋 없음)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 전체 스위트 + strict + clean**

```bash
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK (144 + 신규 2 테스트 + 1 골든)
cd .. && claude plugin validate . --strict                                # 통과
git status --porcelain                                                    # 비어 있음
```

- [ ] **Step 2: 골든 범위 확인**

```bash
git diff --name-status main..HEAD -- tests/golden | awk '{print $1}' | sort | uniq -c   # 전부 A
git diff --name-status main..HEAD -- tests/golden | grep -vE 'tests/golden/release-pr-snapshot/' || echo "(신규 1트리 외 골든 변경 없음)"
```
Expected: 전부 `A`, release-pr-snapshot 외 골든 변경 없음(기존 8트리 바이트 불변).

- [ ] **Step 3: #4 거부 규칙 e2e 스팟**

기존 골든 골든-복사본으로 확인 — `maintenanceLines`+비semver, `maintenanceLines`+independent, release-pr+tagless 3종이 전부 render exit 1인지 각 테스트가 커버함을 확인:
```bash
cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_maintenance_lines_rejected_for_non_semver_scheme test_render_pipeline.PipelineTest.test_maintenance_lines_rejected_for_independent test_render_pipeline.PipelineTest.test_release_pr_rejected_for_tagless_scope -v 2>&1 | tail -4
```
Expected: 3 tests OK.

- [ ] **Step 4: 결과 보고 + 원장 기록**

`git log --oneline main..HEAD`(3커밋), 골든 9종 상태, 브랜치 보호 조언 프로즈 존재를 원장(`.superpowers/sdd/progress.md`)에 기록하고 최종 whole-branch 리뷰로 넘어간다.

---

## 스펙 커버리지 자체 점검

- A. 브랜치 보호 조언(형태=일회성 안내 / 트리거=release-pr+미보호 / config=decisions 기록 / ruleset 우선·classic 대안 / 실행은 사용자 몫) → Task 2
- A. 스펙 §13 "조언은 범위" 명확화 → Task 2 Step 4
- B. #4 비semver hotfix render 거부 → Task 1 Step 1-4
- B. #5 release-pr+next-snapshot 골든 → Task 3
- B. #2 hotfix+release-pr 재개 한계 문서화 → Task 1 Step 5-7
- 비범위(hotfix preflight 실제 재개 감지 / 첫 릴리스 release-pr 재개 / 중단 감지 오탐) → 계획에 없음(의도적 — 스펙 명시)
