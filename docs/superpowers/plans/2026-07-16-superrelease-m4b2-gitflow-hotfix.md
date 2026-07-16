# superrelease M4b-2 gitflow hotfix 구현 계획

> **For agentic workers:** 인라인 실행. 각 태스크 green으로 종료. 스텝은 `- [ ]` 체크박스. **바이트 불변**이 핵심 게이트 — hotfix 스킬 gitflow 분기는 trunk에서 0바이트 collapse해 hotfix-library 골든이 바이트 동일해야 한다.

**Goal:** gitflow 레포에서 production hotfix(main cut → 태그 → develop back-merge)를 hotfix 스킬로 수행하게 하고, gitflow 레포에도 hotfix 스킬을 생성한다.

**Architecture:** hotfix 스킬에 `{{#if repo.branching == "gitflow"}}` 분기(§1·§2·§4·§5·§7) 추가 → manifest에 gitflow 게이트 엔트리 추가 → gitflow-app 골든이 hotfix 스킬(gitflow 흐름)을 렌더.

**Tech Stack:** 동결 template dialect(render.py), git, unittest.

## Global Constraints

- **동결 dialect** — `{{#if x == "lit"}}/{{else}}/{{/if}}` 중첩만. 새 문법 금지.
- **바이트 불변** — gitflow 분기 블록의 개행을 블록 **안**에 두어 trunk에서 collapse. `update_golden` 후 **hotfix-library**(trunk+maintenanceLines) hotfix 스킬 **바이트 불변**이 수용 게이트. gitflow 외 19트리도 불변.
- **골든 변화** — `git status --porcelain tests/golden`에 **gitflow-app에 `.claude/skills/hotfix/SKILL.md` 신규**만(+ hotfix-library 불변). 신규 골든 config 없음.
- **self-render 무영향** — superrelease는 trunk+maintenanceLines=false라 hotfix 미생성 → 커밋 툴킷·self-render 불변.
- **엔진 불변** — render.py·validate 미변경. dual-entry는 manifest만.
- **테스트** — 루트 `python3 -m unittest discover -s tests -q`. init ≤500줄.
- **검증** — `claude plugin validate . --strict` PASS.
- **커밋** — Conventional Commits + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## File Structure

- Modify: `skills/init/assets/skills/hotfix/SKILL.md` (gitflow 분기)
- Modify: `skills/init/assets/manifest.json` (gitflow 게이트 엔트리)
- Modify: `skills/init/references/branching-and-release-path.md` (line 43 + 흐름)
- Modify: `skills/init/SKILL.md` (번들 6 gitflow hotfix 안내)
- Golden(생성): `tests/golden/gitflow-app/expected/.claude/skills/hotfix/SKILL.md`

---

## Task 1: hotfix 스킬 gitflow 분기 + manifest 이중 엔트리 + 골든

**Files:** `skills/init/assets/skills/hotfix/SKILL.md`, `skills/init/assets/manifest.json`, `tests/golden/gitflow-app/**`

- [ ] **Step 1: hotfix 스킬 gitflow 분기** — 아래 섹션을 `{{#if repo.branching == "gitflow"}}gitflow{{else}}trunk(현행){{/if}}`로 분기한다. **else 블록은 현재 텍스트와 바이트 동일**해야 하고, 개행은 블록 안에 둔다.

  - **§1 대상 결정** — gitflow: "현 production은 `{{repo.defaultBranch}}`의 최신 릴리스(릴리스 후 main은 릴리스 버전 유지). 최신 릴리스 태그 `git -c versionsort.suffix=- tag --list '<glob>' --sort=-v:refname | head -n 1`. 수정이 `{{repo.developBranch}}`/`{{repo.defaultBranch}}`에 있는지(체리픽 sha) 또는 hotfix 브랜치 직접." / else: 현행(release/`<라인>`).
  - **§2 preflight 1번** — gitflow: `git fetch origin` → `git checkout {{repo.defaultBranch}}` → `git pull`. / else: 현행(`git checkout release/<라인>`).
  - **§4 anchor** — gitflow: 범위 anchor는 `{{repo.defaultBranch}}`의 최신 릴리스 태그(위 §1 glob). / else: 현행(라인 최신 태그 `git describe`).
  - **§5 release-pr 커밋** — gitflow: `git checkout -b hotfix/<패치>`(main에서) → 커밋 → push → `gh pr create --base {{repo.defaultBranch}} --head hotfix/<패치>` — **base=`{{repo.defaultBranch}}`**. 머지 후 재개해 6단계. / else: 현행(base=`release/<라인>`). (direct-push 분기는 gitflow에 해당 없음 — gitflow는 release-pr 전용이나, 현행 `{{#if repo.releasePath == "direct-push"}}`는 gitflow에서 자연히 false라 유지.)
  - **§7 post-release** — gitflow: **develop back-merge** — `git checkout {{repo.developBranch}} && git pull` → `git merge {{repo.defaultBranch}}`(버전 파일 충돌은 main 릴리스 버전 취함) → 프리뷰·확인 후 push(거부 시 back-merge PR). 이어서 `{{#if scope.postRelease.bump == "next-snapshot"}}develop에서 SNAPSHOT 복귀: next-version.py --bump patch --qualifier {{scope.preRelease.qualifier}} → version.py set → 커밋·push{{/if}}. / else: 현행(라인 post-release + `{{repo.defaultBranch}}` 체리픽백 + CHANGELOG 반영). 기존 §7의 `{{#if repo.branching == "gitflow"}}develop 반영 확인{{/if}}` 힌트는 이 분기에 흡수(중복 제거).

- [ ] **Step 2: manifest gitflow 게이트 엔트리** — `skills/init/assets/manifest.json`의 hotfix 엔트리 **뒤에** 동일 src·dest·`render:true`, `when: "repo.branching == \"gitflow\""` 엔트리를 추가.

```json
    {
      "src": "skills/hotfix/SKILL.md",
      "dest": ".claude/skills/hotfix/SKILL.md",
      "render": true,
      "when": "repo.branching == \"gitflow\""
    },
```

- [ ] **Step 3: 골든 재생성 + 범위 게이트**

Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden | grep -v '^??' || echo "(기존 수정 0)"`
Expected: **기존 골든 수정 0** — 특히 hotfix-library의 hotfix SKILL.md 바이트 불변(gitflow 블록 collapse). 수정이 보이면 개행 회계 오류 → §1 재조정.
Run: `git status --porcelain tests/golden | grep '^??'`
Expected: `?? tests/golden/gitflow-app/expected/.claude/skills/hotfix/SKILL.md` (신규).

- [ ] **Step 4: gitflow-app hotfix가 gitflow 흐름인지 확인**

Run: `grep -c 'back-merge\|{{repo.developBranch}}\|develop' tests/golden/gitflow-app/expected/.claude/skills/hotfix/SKILL.md` (렌더 후이므로 `develop`)
Expected: ≥1 (develop back-merge 존재 = gitflow 흐름).
Run: `grep -c 'release/<라인>\|release/1.2.x' tests/golden/gitflow-app/expected/.claude/skills/hotfix/SKILL.md`
Expected: 0 (유지보수 라인 아님).
Run: `grep -c 'release/1.2.x' tests/golden/hotfix-library/expected/.claude/skills/hotfix/SKILL.md`
Expected: ≥1 (trunk는 현행 유지).

- [ ] **Step 5: dual-entry gitflow+maintenanceLines 즉석 렌더 확인** — 두 엔트리가 모두 fire해도 깨끗한지(스크래치):

Run: config를 스크래치에 작성(gitflow_app 기반 + `maintenanceLines: true`) 후 `render.py ... --repo <scratch>` → exit 0, `.claude/skills/hotfix/SKILL.md` 1개 존재 확인.
Expected: exit 0, hotfix 파일 1개(이중 write는 동일 바이트라 무해).

- [ ] **Step 6: 전체 스위트 + validate**

Run: `python3 -m unittest discover -s tests -q` → OK (252, 골든 subTest 카운트 무변).
Run: `claude plugin validate . --strict` → PASS.

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/skills/hotfix/SKILL.md skills/init/assets/manifest.json tests/golden/gitflow-app
git commit -m "$(printf 'feat: gitflow production hotfix — hotfix 스킬 gitflow 분기 + gitflow 게이트\n\nmain cut → 태그 → develop back-merge. manifest 이중 엔트리로 gitflow\n레포에도 hotfix 생성. trunk(hotfix-library) 바이트 불변.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 2: reference + init 프로즈

**Files:** `skills/init/references/branching-and-release-path.md`, `skills/init/SKILL.md`

- [ ] **Step 1: reference line 43 갱신** — "gitflow의 **hotfix 흐름**…은 후속 지원 예정이다. 그때까지…" 문장을 **지원됨**으로 교체: gitflow production hotfix 흐름(main HEAD에서 `hotfix/*` cut → patch bump → main 머지·태그 → develop back-merge + SNAPSHOT 복귀)이 hotfix 스킬로 수행되며, `maintenanceLines` 없이 gitflow 레포에 생성됨을 서술. line 51/60의 gitflow 관련 문구와 정합(중복·모순 제거).

- [ ] **Step 2: init SKILL.md 번들 6 gitflow hotfix 안내** — gitflow 선택 시 "hotfix 스킬이 production hotfix 흐름(main cut → develop back-merge)으로 생성됨(maintenanceLines와 독립)"을 유지보수 라인 문구 근처에 추가.

- [ ] **Step 3: 줄 수·스위트·validate**

Run: `wc -l skills/init/SKILL.md` → ≤500.
Run: `python3 -m unittest discover -s tests -q` → OK (252, 프로즈 무영향).
Run: `claude plugin validate . --strict` → PASS.

- [ ] **Step 4: 커밋**

```bash
git add skills/init/references/branching-and-release-path.md skills/init/SKILL.md
git commit -m "$(printf 'docs: gitflow hotfix 지원 반영 (reference·init 번들 6)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 3: 최종 검증 + whole-branch 리뷰

- [ ] **Step 1: 전체 검증** — `python3 -m unittest discover -s tests -q`(252 OK) · `claude plugin validate . --strict`(PASS) · `git status --porcelain tests/golden`(gitflow-app hotfix 신규만).
- [ ] **Step 2: 바이트 불변 재확인** — `git diff main -- tests/golden` 범위가 gitflow-app hotfix 신규 파일 1개인지.
- [ ] **Step 3: whole-branch 독립 리뷰**(opus) — gitflow hotfix 흐름 정확성(main cut·develop back-merge 안전성)·바이트 불변·dual-entry·prose 정합 중점. Critical/Important만 수정.
- [ ] **Step 4: 원장 갱신** — `.superpowers/sdd/progress.md`에 M4b-2 완료 기록.

---

## Self-Review

**1. 스펙 커버리지:** gitflow 흐름 분기(T1 §1·§2·§4·§5·§7) · dual-entry 게이트(T1) · 골든 gitflow-app(T1) · reference/init(T2) · 검증/리뷰(T3). 스펙 전 항목 매핑.

**2. Placeholder 스캔:** manifest 엔트리·명령 실값. gitflow 섹션 내용은 서술(정확 개행은 update_golden 대조로 확정 — 바이트 불변 게이트가 수용 기준). TODO 없음.

**3. 타입/이름 일관성:** `{{repo.defaultBranch}}`·`{{repo.developBranch}}`·`{{scope.preRelease.qualifier}}`·`{{scope.postRelease.bump}}`는 release 스킬 gitflow §8과 동일 바인딩. manifest 엔트리는 기존 스키마. 각 태스크 green.

**리스크:** ① 바이트 불변 개행 회계 — Step 3 hotfix-library 불변이 게이트, 틀리면 반복 조정. ② dual-entry 이중 write — Step 5 즉석 렌더로 확인. ③ prose 자동 테스트 없음 — 골든·바이트 불변·T3 사람/에이전트 리뷰로 커버.
