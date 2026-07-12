# superrelease M3c-1 (노트 목적지 fragment + tag-message) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** superrelease의 `notes.destinations`에 두 목적지를 추가한다 — **fragment**(노트 소스: `changelog.d/{id}.{category}.md` 조각을 취합·소비), **tag-message**(노트 sink: annotated/signed 태그 메시지에 노트 전문 내장). 산술·엔진 무변경, 렌더는 동결 dialect의 `{{#each}}`+`{{#if this == "lit"}}` 배열 멤버십으로 조건 렌더한다.

**Architecture:** 단일 release 스킬은 조건 블록(`{{#each scope.notes.destinations}}{{#if this == "fragment"}}...{{/if}}{{/each}}` — 두 값이 없는 기존 config는 0바이트로 collapse → 골든 바이트 불변), 모노레포 release 스킬은 무조건 런타임 프로즈(scope 무인라인, pnpm-monorepo 골든 1파일 재생성). render.py `validate_config`에 검증 규칙 2건(tag-message 요건·fragment sink). init 번들 5·references 정합. 골든 `fragment-app` 신규 1트리.

**Tech Stack:** Python 3.9+ stdlib, 동결 template dialect(엔진 수정 금지 — `{{#each}}`+`{{#if this == "lit"}}` 활용, 검증 완료), git.

**스펙:** [docs/superpowers/specs/2026-07-12-superrelease-m3c1-notes-destinations-design.md](../specs/2026-07-12-superrelease-m3c1-notes-destinations-design.md). 베이스: main `7c61679`(M1~M3b.1, 145 테스트, 골든 9종). 실행 컨트롤러는 main에서 `feat/superrelease-m3c1` 브랜치를 만들어 진행한다.

## Global Constraints

- **스크립트 산술·render 엔진 무변경.** version.py·next-version.py·changed-packages.py·scan.py, render.py 엔진부(render_template/evaluate/parse/tokenize) 수정 금지. 유일한 Python 변경은 render.py **`validate_config` 규칙 2건**(render.py는 골든-복사 대상 아님, 골든 무영향).
- **골든 규율:** Task 1·2(render 규칙 + 단일 스킬 조건 블록)은 골든 변경 **0** — 기존 9 config는 destinations에 fragment/tag-message가 없어 블록이 collapse. `update_golden.py` 금지, `python3 -m unittest test_golden`(from tests/) GREEN + `git status --porcelain tests/golden` 빈 출력이 증명. Task 3(모노레포 무조건 프로즈)은 `pnpm-monorepo`의 release SKILL.md 1파일만 재생성. Task 5(fragment-app)만 신규 1트리. 예고 밖 골든 변경이 나오면 STOP(`git checkout -- tests/golden`).
- **동결 dialect만:** `{{path}}`, `{{#if}}`(`{{else}}`, `== "lit"`/`!= "lit"`), `{{#unless}}`, `{{#each}}`. **배열 멤버십 = `{{#each scope.notes.destinations}}{{#if this == "값"}}...{{/if}}{{/each}}`**(엔진에서 검증됨: 값이 있으면 1회 emit, 없으면 0바이트). 생성 SKILL.md ≤149줄, init SKILL.md ≤500줄.
- **바이트 불변 규율:** 단일 스킬에 조건 블록을 넣을 때 `{{#each}}...{{/each}}` 태그를 **기존 텍스트에 밀착** 배치해, fragment/tag-message가 없는 config에서 collapse 시 주변 바이트가 한 글자도 바뀌지 않게 한다(M3a Task 2 선례).
- **모노레포 무인라인:** 모노레포 변형은 scope별 값 인라인 금지 — 런타임 프로즈만("그 scope의 destinations에 fragment면...").
- 코드·스크립트 메시지 영어, 생성 문서·init 프로즈 한국어. Python 3.9+ stdlib, exit 0/1/2.
- 테스트: `cd tests && python3 -m unittest discover -p 'test_*.py'`. 커밋: Conventional Commits + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 파일 구조 (M3c-1 전체)

```
수정  skills/init/scripts/render.py                          # Task 1: validate_config 규칙 2건
수정  tests/test_render_pipeline.py                          # Task 1: 검증 테스트
수정  skills/init/assets/skills/release/SKILL.md             # Task 2: §5 fragment 프리앰블·tag-message 불릿, §7 tag-message 블록
수정  tests/test_assets.py                                   # Task 2·3: 렌더 스모크
수정  skills/init/assets/skills/release-monorepo/SKILL.md    # Task 3: §5·§8 런타임 프로즈
갱신  tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md  # Task 3: 재생성
수정  skills/init/SKILL.md                                   # Task 4: 번들 5 해제
수정  skills/init/references/notes-and-changelog.md          # Task 4: fragment/tag-message 확정
수정  tests/golden_configs.py                                # Task 5: fragment_app 빌더
생성  tests/golden/fragment-app/expected/**                  # Task 5: update_golden
```

책임 분리: fragment 취합·삭제, tag-message `-F` 절차 = 생성 스킬 프로즈, 목적지 조합 유효성 = render 검증(결정론), destinations = config(SSOT).

---

### Task 1: render.py 검증 규칙 2건 (tag-message 요건 · fragment sink)

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Consumes: scope `notes.destinations`(list), `tag.enabled`/`tag.annotated`/`tag.signed`.
- Produces: 검증 규칙 — (1) `tag-message` ∈ destinations인데 그 scope가 tag.enabled + (annotated 또는 signed)가 아니면 exit 1. (2) `fragment` ∈ destinations인데 sink(changelog/release-file/github-release/tag-message) 중 하나도 없으면 exit 1.

- [ ] **Step 1: 실패 테스트 작성 — tests/test_render_pipeline.py**

`PipelineTest` 클래스(이미 `scope_config` import, `self.write_config`/`self.render` 헬퍼)에서 기존 `test_maintenance_lines_rejected_for_non_semver_scheme` 메서드 **뒤**에 추가:

```python
    def test_tag_message_rejected_without_annotated_or_signed(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["destinations"] = ["tag-message"]
        cfg["scopes"][0]["tag"] = {"enabled": True, "format": "v{version}",
                                   "annotated": False, "signed": False,
                                   "movingMajorTag": False}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("tag-message", r.stderr)

    def test_tag_message_ok_with_annotated(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["destinations"] = ["tag-message"]
        # default scope_config tag is annotated=True → valid
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_fragment_rejected_without_sink(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["destinations"] = ["fragment"]
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("fragment", r.stderr)

    def test_fragment_ok_with_sink(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["destinations"] = ["fragment", "changelog"]
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_tag_message_rejected_without_annotated_or_signed test_render_pipeline.PipelineTest.test_fragment_rejected_without_sink -v`
Expected: 두 테스트 FAIL(현재는 exit 0으로 렌더 — 미검증). `..._ok_...` 2건은 이미 PASS(현재도 통과).

- [ ] **Step 3: 규칙 구현 — render.py validate_config**

`skills/init/scripts/render.py`의 `validate_config` 함수에서, 기존 `release-pr` + tagless 규칙 블록(`...resume relies on tag detection")`으로 끝남) **뒤**, `return problems` **앞**에 삽입:

```python
    sinks = {"changelog", "release-file", "github-release", "tag-message"}
    for i, s in enumerate(scopes or []):
        dests = (s.get("notes") or {}).get("destinations") or []
        tag = s.get("tag") or {}
        if "tag-message" in dests and not (
                tag.get("enabled") and (tag.get("annotated") or tag.get("signed"))):
            problems.append('scopes[{}]: notes destination "tag-message" requires '
                            "an annotated or signed tag".format(i))
        if "fragment" in dests and not (sinks & set(dests)):
            problems.append('scopes[{}]: notes destination "fragment" needs at '
                            "least one sink (changelog/release-file/"
                            "github-release/tag-message)".format(i))
```

엔진부(tokenize/parse/evaluate/render_template)는 건드리지 않는다.

- [ ] **Step 4: 통과 확인 (4 테스트 + 회귀)**

Run: `cd tests && python3 -m unittest test_render_pipeline -v 2>&1 | tail -6`
Expected: 신규 4건 포함 전부 PASS. 기존 거부 규칙(independent·tagless·비semver) 테스트도 회귀 없이 PASS.

- [ ] **Step 5: 골든 불변 + 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest test_golden 2>&1 | tail -3` → OK(재생성 없이). `git status --porcelain tests/golden` 빈 출력 확인. 이어서 `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: render 검증 — tag-message 요건·fragment sink 규칙 (M3c-1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 단일 release 스킬 — fragment 소스 + tag-message sink 조건 블록

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md` (§5, §7)
- Test: `tests/test_assets.py`

**Interfaces:**
- Consumes: `scope.notes.destinations`(list), Task 1의 검증(잘못된 조합은 애초에 렌더되지 않음).
- Produces: fragment/tag-message 조건 블록. Task 5 골든 `fragment-app`이 스냅샷한다. **기존 골든 바이트 불변**(collapse).

- [ ] **Step 1: 실패 테스트 작성 — tests/test_assets.py**

`SkillAssetsTest` 클래스에서 `test_release_skill_semver_default_has_no_new_blocks` 메서드 **뒤**에 추가:

```python
    def test_release_skill_fragment_and_tag_message(self):
        ctx = base_ctx()
        ctx["scope"]["notes"]["destinations"] = ["fragment", "changelog", "tag-message"]
        out = self.render_asset("skills/release/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("changelog.d", out)          # fragment 프리앰블
        self.assertIn("git rm", out)               # 소비 조각 삭제
        self.assertIn("-F <노트 파일>", out)        # tag-message 메커니즘
        self.assertLessEqual(len(out.splitlines()), 149)

    def test_release_skill_default_has_no_fragment_or_tag_message(self):
        out = self.render_asset("skills/release/SKILL.md")  # 기본 destinations = changelog+github-release
        self.assertNotIn("changelog.d", out)
        self.assertNotIn("-F <노트 파일>", out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_release_skill_fragment_and_tag_message -v`
Expected: FAIL(현재 fragment/tag-message 블록 없음). `..._default_has_no_...`는 PASS(회귀 핀).

- [ ] **Step 3: §5 fragment 프리앰블 삽입**

`skills/init/assets/skills/release/SKILL.md` §5의 현재 도입부:

```
`.claude/skills/release-notes/SKILL.md` 절차로 초안을 작성하고, config `scopes[].notes.destinations`의 목적지별로 반영하라:

- `changelog`: `.superrelease/templates/changelog-entry.md` 골격으로 CHANGELOG.md 최신 항목으로 삽입 (Unreleased 섹션이 있으면 그 아래)
```

를 아래로 교체 (fragment 프리앰블 each-블록을 `- \`changelog\`` **바로 앞**에 밀착 삽입 — 블록 앞의 `\n\n`은 고정, 블록은 collapse 시 0바이트라 바이트 불변. present면 프리앰블 뒤 빈 줄까지 emit):

```
`.claude/skills/release-notes/SKILL.md` 절차로 초안을 작성하고, config `scopes[].notes.destinations`의 목적지별로 반영하라:

{{#each scope.notes.destinations}}{{#if this == "fragment"}}노트 소스로 `changelog.d/*.md` 조각을 category별로 취합하라 — 파일명 `{id}.{category}.md`의 category가 `breaking`이면 Breaking Changes, `feature`면 하이라이트·변경 사항, `fix`·`misc`(및 미인식)이면 변경 사항에 넣는다. 취합한 조각 파일은 릴리스 커밋에서 `git rm`으로 삭제하고 6단계 프리뷰에 명시하라(bump 결정에는 쓰지 않는다 — bump는 커밋·PR 소스 그대로).

{{/if}}{{/each}}- `changelog`: `.superrelease/templates/changelog-entry.md` 골격으로 CHANGELOG.md 최신 항목으로 삽입 (Unreleased 섹션이 있으면 그 아래)
```

**바이트 불변 확인**: fragment 없는 config에서 `{{#each}}...{{/each}}`는 "" → `반영하라:\n\n- \`changelog\``(원본과 동일). 프리앰블 문단과 다음 빈 줄은 전부 `{{#if}}` 안에 있어 collapse된다.

- [ ] **Step 4: §5 tag-message 불릿 삽입**

§5의 현재 `github-release` 불릿:

```
- `github-release`: 7단계 Release 본문으로 사용
```

를 아래로 교체 (tag-message each-블록을 `사용` **바로 뒤 같은 줄**에 밀착 — 개행은 `{{#if}}` **안**에 두어 collapse 시 0바이트. github-release 줄 뒤의 원본 `\n\n## 6.`은 그대로 유지):

```
- `github-release`: 7단계 Release 본문으로 사용{{#each scope.notes.destinations}}{{#if this == "tag-message"}}
- `tag-message`: 7단계 태그 메시지에 노트 전문을 넣는다(아래 참조){{/if}}{{/each}}
```

**바이트 불변 확인**: tag-message 없으면 each는 "" → `...사용`(원본과 동일, 뒤의 `\n\n## 6.` 불변). present면 `...사용\n- \`tag-message\`: ...참조)` emit. 개행이 `{{#if}}` 안에 있어야 함 — 밖에 두면 collapse 시 빈 줄이 남아 골든이 깨진다.

- [ ] **Step 5: §7 tag-message 메커니즘 삽입**

§7의 현재 태그 생성 불릿(line 80 부근):

```
- {{#if scope.tag.signed}}signed 태그: `git tag -s <태그> -m "<한 줄 요약>"`{{else}}{{#if scope.tag.annotated}}annotated 태그: `git tag -a <태그> -m "<한 줄 요약>"`{{else}}태그: `git tag <태그>`{{/if}}{{/if}} → `git push origin <태그>`{{#if scope.tag.movingMajorTag}}
```

를 아래로 교체 (tag-message each-블록을 `git push origin <태그>` **바로 뒤**, `{{#if scope.tag.movingMajorTag}}` **앞**에 밀착 삽입):

```
- {{#if scope.tag.signed}}signed 태그: `git tag -s <태그> -m "<한 줄 요약>"`{{else}}{{#if scope.tag.annotated}}annotated 태그: `git tag -a <태그> -m "<한 줄 요약>"`{{else}}태그: `git tag <태그>`{{/if}}{{/if}} → `git push origin <태그>`{{#each scope.notes.destinations}}{{#if this == "tag-message"}}
- **tag-message**: 위 태그 명령의 `-m "<한 줄 요약>"`를 `-F <노트 파일>`로 바꿔 5단계 노트 전문을 태그 메시지에 넣어라 (annotated/signed 태그에만 유효){{/if}}{{/each}}{{#if scope.tag.movingMajorTag}}
```

**바이트 불변 확인**: tag-message 없으면 each는 "" → `...\`git push origin <태그>\`{{#if scope.tag.movingMajorTag}}`(원본과 동일). 개행이 `{{#if this == "tag-message"}}` 안에 있어 collapse 시 사라진다.

- [ ] **Step 6: 통과 확인 + 골든 바이트 불변**

Run: `cd tests && python3 -m unittest test_assets test_golden -v 2>&1 | tail -6`
Expected: 전부 PASS. `git status --porcelain tests/golden` 빈 출력 — 기존 9골든은 destinations에 fragment/tag-message가 없어 세 블록이 collapse → 바이트 불변(재생성 불필요).

- [ ] **Step 7: 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py
git commit -m "feat: 단일 release 스킬 fragment 소스·tag-message sink 조건 블록 (기존 렌더 바이트 불변, M3c-1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 모노레포 release 스킬 — fragment/tag-message 런타임 프로즈

**Files:**
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (§5, §8)
- Test: `tests/test_assets.py`
- 갱신: `tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md` (update_golden)

**Interfaces:**
- Consumes: scope별 `notes.destinations`(런타임에 각 scope에서 읽음 — 인라인 금지).
- Produces: 모노레포 fragment/tag-message 프로즈. pnpm-monorepo 골든 1파일 재생성.

- [ ] **Step 1: 실패 테스트 작성 — tests/test_assets.py**

`MonorepoAssetsTest` 클래스에서 `test_release_monorepo_scheme_and_counter_prose` 메서드 **뒤**에 추가:

```python
    def test_release_monorepo_fragment_and_tag_message_prose(self):
        out = self.render_asset("skills/release-monorepo/SKILL.md")
        self.assertIn("changelog.d", out)     # fragment 취합 프로즈
        self.assertIn("tag-message", out)     # tag-message 프로즈
        self.assertIn("-F", out)              # -F 노트 파일
        # scope 무인라인 유지 — asset에 {{scope. 리터럴 없음
        self.assertNotIn("{{scope.", (ASSETS / "skills/release-monorepo/SKILL.md")
                         .read_text(encoding="utf-8"))
        self.assertLessEqual(len(out.splitlines()), 149)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.MonorepoAssetsTest.test_release_monorepo_fragment_and_tag_message_prose -v`
Expected: FAIL(현재 프로즈 없음).

- [ ] **Step 3: §5 fragment/tag-message 프로즈 추가**

`skills/init/assets/skills/release-monorepo/SKILL.md` §5의 현재 마지막 불릿:

```
- `github-release`: 8단계 Release 본문으로 사용
```

를 아래로 교체 (무조건 프로즈 2줄 추가 — scope 무인라인):

```
- `github-release`: 8단계 Release 본문으로 사용
- `fragment`가 그 scope의 목적지면: 그 scope 경로의 `changelog.d/*.md` 조각을 category별(`breaking`→Breaking Changes, `feature`→하이라이트·변경, `fix`·`misc`→변경)로 취합해 노트 소스로 쓰고, 소비한 조각을 릴리스 커밋에서 `git rm`으로 삭제하라(7단계 프리뷰에 명시). fragment는 최소 1개 sink 목적지와 함께 쓴다.
- `tag-message`가 그 scope의 목적지면: 8단계 태그 메시지에 5단계 노트 전문을 넣는다(아래 참조).
```

- [ ] **Step 4: §8 tag-message 프로즈 추가**

§8의 현재 태그 생성 불릿:

```
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
```

를 아래로 교체 (tag-message 프로즈 한 줄 추가):

```
- 태그 생성: 그 scope의 `tag.signed`가 true면 `git tag -s <태그> -m "<한 줄 요약>"`, 아니고 `tag.annotated`가 true면 `git tag -a <태그> -m "<한 줄 요약>"`, 둘 다 아니면 `git tag <태그>` → `git push origin <태그>`
- 그 scope의 목적지에 `tag-message`가 있으면 위 `-m "<한 줄 요약>"`를 `-F <노트 파일>`로 바꿔 노트 전문을 태그 메시지에 넣어라(그 scope가 annotated/signed 태그일 때만 — render가 그 조합을 강제한다).
```

- [ ] **Step 5: pnpm-monorepo 골든 재생성 + 범위 검증**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden | sort`
Expected: `M tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md` **한 파일만**. 그 외 골든(다른 8트리)이 변경되면 STOP(`git checkout -- tests/golden` 후 원인 규명 — 무조건 프로즈가 다른 트리를 건드릴 리 없다).

- [ ] **Step 6: 골든 diff 스팟 + 통과 확인**

Run:
```bash
git diff tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md | grep -E "^\+" | grep -c "changelog.d\|tag-message"   # 기대: ≥2 (추가 프로즈)
cd tests && python3 -m unittest test_assets test_golden 2>&1 | tail -3     # 기대: OK
```

- [ ] **Step 7: 전체 스위트 + 커밋**

Run: `cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add skills/init/assets/skills/release-monorepo/SKILL.md tests/test_assets.py tests/golden/pnpm-monorepo/expected/.claude/skills/release/SKILL.md
git commit -m "feat: 모노레포 release 스킬 fragment/tag-message 런타임 프로즈 (M3c-1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: init 번들 5 해제 + notes-and-changelog.md 정합

**Files:**
- Modify: `skills/init/SKILL.md` (번들 5)
- Modify: `skills/init/references/notes-and-changelog.md`

**Interfaces:**
- Consumes: Task 1~3의 실동작(fragment 소비·삭제·sink 필요, tag-message annotated 요건).
- Produces: init이 fragment/tag-message를 선택지로 제시하고 요건을 안내하는 지시. 프로즈 태스크(골든-복사 아님 — 골든·테스트 무영향, 검증은 grep + 줄 수 + strict).

- [ ] **Step 1: init SKILL.md 번들 5 교체**

`skills/init/SKILL.md` 번들 5 항목 전체(현재 `- **번들 5 — 노트·GitHub Release**: destinations 복수 선택(M1: changelog | release-file | github-release; fragment·tag-message는 M3 표시) / ...`)를 아래로 교체:

```
- **번들 5 — 노트·GitHub Release**: destinations 복수 선택(changelog | release-file | github-release | fragment | tag-message) — `fragment`는 노트 소스(`changelog.d/{id}.{category}.md` 조각 취합·소비, category `breaking`/`feature`/`fix`/`misc`)이며 **최소 1개 sink**(changelog/release-file/github-release/tag-message)와 함께 써야 한다(render가 강제), `tag-message`는 노트 sink(태그 메시지에 노트 전문)이며 **annotated 또는 signed 태그**가 필요하다(plain·tagless면 잠금·render 거부) / release-file이면 perReleasePath(기본 `docs/releases/`) / 언어(ko 기본 | en | both)·독자·어조 / GitHub Release 사용·generateNotes 하이브리드·release.yml 생성 여부.
```

- [ ] **Step 2: init SKILL.md config 각주 갱신**

`skills/init/SKILL.md`의 config 각주 목록에서 노트 목적지 관련 줄(현재 `- 노트 목적지: changelog/release-file/github-release — fragment/tag-message는 M3c`)을 아래로 교체:

```
- 노트 목적지: changelog/release-file/github-release/fragment/tag-message 지원 — fragment는 sink 동반 필수, tag-message는 annotated/signed 태그 필수(render가 검증)
```

- [ ] **Step 3: notes-and-changelog.md 표 갱신**

`skills/init/references/notes-and-changelog.md`의 5종 표에서 두 행(현재 `| fragment | \`changelog.d/\` 조각 → 취합 | M3 |`, `| tag-message | annotated 태그 메시지 | M3 |`)의 "M3"를 "지원"으로 교체:

```
| fragment | `changelog.d/` 조각 → 취합 | 지원 |
| tag-message | annotated 태그 메시지 | 지원 |
```

- [ ] **Step 4: notes-and-changelog.md fragment 절 확정**

현재 fragment 절의 미룬 문장:

```
superrelease가 이 방식을 지원하게 될 때 정확히 어떤 파일명 규칙을 쓸지는 M3에서 확정할 세부 사항이며, 여기서는 fragment 방식의 일반적인 동작 원리만 배경 지식으로 다룬다.
```

를 아래로 교체:

```
superrelease는 towncrier식 규약을 쓴다: `changelog.d/{id}.{category}.md`(예: `142.feature.md`). `id`는 PR·이슈 번호나 slug, `category`는 노트 섹션에 매핑된다 — `breaking`→Breaking Changes, `feature`→하이라이트·변경 사항, `fix`·`misc`(및 미인식)→변경 사항. 릴리스 시 release 스킬이 조각을 취합해 노트 소스로 쓰고 **소비한 조각을 릴리스 커밋에서 삭제**한다. superrelease는 조각을 **취합만** 하며 생성하지 않는다(조각은 기여자가 PR에서 직접 추가하는 규약). category는 노트 그룹핑 전용이고 bump 결정에는 쓰지 않는다. fragment는 노트 소스이므로 **최소 1개 sink 목적지**(changelog/release-file/github-release/tag-message)와 함께 써야 한다 — 단독이면 취합·삭제 후 노트가 유실되어 render가 거부한다.
```

- [ ] **Step 5: notes-and-changelog.md M1 문단 + tag-message 요건 갱신**

현재 문단:

```
**M1은 `changelog` / `release-file` / `github-release` 세 목적지를 지원한다.**

fragment와 tag-message는 M3에서 지원될 예정이며, M1 단계에서는 선택지로 제공하지 않는다.
```

를 아래로 교체:

```
**다섯 목적지 모두 지원된다** — `changelog` / `release-file` / `github-release` / `fragment` / `tag-message`.

`tag-message`는 노트 전문을 annotated 태그 메시지에 `git tag -a <태그> -F <노트 파일>`(signed면 `-s ... -F`)로 넣는다. plain 태그나 태그를 안 쓰는 scope에는 적용할 수 없어 init·render가 그 조합을 막는다.
```

- [ ] **Step 6: 정합 검증 + 커밋**

Run:
```bash
grep -c "M3" skills/init/references/notes-and-changelog.md   # fragment/tag-message의 M3 표기가 사라졌는지(다른 M3 언급이 있으면 수치만 참고)
grep -c "fragment\|tag-message" skills/init/SKILL.md          # ≥1
wc -l skills/init/SKILL.md                                    # ≤500
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK, 골든 clean
cd .. && claude plugin validate . --strict 2>&1 | tail -1     # 통과
```

```bash
git add skills/init/SKILL.md skills/init/references/notes-and-changelog.md
git commit -m "feat: init 번들5 fragment/tag-message 해제 + notes-and-changelog 정합 (M3c-1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 골든 fragment-app 신규

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/fragment-app/expected/**` (update_golden 산출)

**Interfaces:**
- Consumes: `helpers.scope_config`(기본 tag annotated=true), Task 2의 단일 스킬 조건 블록.
- Produces: `GOLDEN` dict 10항목. `test_golden`이 자동 순회.

- [ ] **Step 1: golden_configs.py에 빌더 추가 + GOLDEN 갱신**

`tests/golden_configs.py`의 `release_pr_snapshot` 함수 **뒤**에 추가하고 `GOLDEN` dict를 교체:

```python
def fragment_app():
    # fragment(소스) + changelog·tag-message(sink) — tag는 기본 annotated
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["scopes"][0]["notes"]["destinations"] = ["fragment", "changelog", "tag-message"]
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app}
```

- [ ] **Step 2: 골든 생성 + 범위 검증**

Run: `python3 tests/update_golden.py && git status --porcelain tests/golden | sort`
Expected: `?? tests/golden/fragment-app/` **한 항목만**. ` M `으로 시작하는 기존 트리 변경이 하나라도 있으면 STOP(`git checkout -- tests/golden`).

- [ ] **Step 3: 스냅샷 스팟 확인**

Run:
```bash
grep -c "changelog.d" tests/golden/fragment-app/expected/.claude/skills/release/SKILL.md    # 기대: ≥1 (fragment 프리앰블)
grep -c -- "-F <노트 파일>" tests/golden/fragment-app/expected/.claude/skills/release/SKILL.md  # 기대: 1 (tag-message)
grep -c "git rm" tests/golden/fragment-app/expected/.claude/skills/release/SKILL.md          # 기대: ≥1
```
Expected: 세 값 모두 충족(이 상호작용은 다른 골든엔 없다).

- [ ] **Step 4: 테스트 통과 + 커밋**

Run: `cd tests && python3 -m unittest test_golden -v 2>&1 | tail -4` → 10 골든 전부 PASS. 이어서 `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3` → OK.

```bash
git add tests/golden_configs.py tests/golden/fragment-app
git commit -m "test: 골든 fragment-app 추가 — fragment 소스·tag-message sink 조건 블록 고정 (M3c-1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 최종 검증 (컨트롤러 직접 수행, 커밋 없음)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 전체 스위트 + strict + clean**

```bash
cd tests && python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -3   # OK (145 + 신규 테스트)
cd .. && claude plugin validate . --strict                                # 통과
git status --porcelain                                                    # 비어 있음
```

- [ ] **Step 2: 골든 범위 확인**

```bash
git diff --name-status main..HEAD -- tests/golden | awk '{print $1}' | sort | uniq -c
git diff --name-status main..HEAD -- tests/golden | grep -vE 'tests/golden/(fragment-app/|pnpm-monorepo/expected/.claude/skills/release/SKILL.md)'  || echo "(fragment-app 신규 + pnpm 1파일 재생성 외 골든 변경 없음)"
```
Expected: 신규 `fragment-app` 트리(A) + `pnpm-monorepo` release SKILL.md(M) 1파일만. 그 외 기존 8트리 바이트 불변.

- [ ] **Step 3: 검증 규칙 e2e 스팟**

```bash
cd tests && python3 -m unittest \
  test_render_pipeline.PipelineTest.test_tag_message_rejected_without_annotated_or_signed \
  test_render_pipeline.PipelineTest.test_fragment_rejected_without_sink \
  test_render_pipeline.PipelineTest.test_fragment_ok_with_sink 2>&1 | tail -3
```
Expected: 3 tests OK.

- [ ] **Step 4: 결과 보고 + 원장 기록**

`git log --oneline main..HEAD`(5커밋), 골든 10종 상태, fragment/tag-message 렌더 존재를 원장(`.superpowers/sdd/progress.md`)에 기록하고 최종 whole-branch 리뷰로 넘어간다.

---

## 스펙 커버리지 자체 점검

- 렌더 메커니즘(`{{#each}}`+`{{#if this == "lit"}}` 배열 멤버십, 바이트 불변) → Task 2·3 (엔진 검증 완료)
- A. fragment 소스(취합·category 매핑·소비 삭제·sink 필요) → Task 2(단일)·Task 3(모노레포)·Task 1(sink 검증)·Task 4(문서)
- B. tag-message sink(`-F` 노트 전문·annotated/signed 요건) → Task 2·Task 3·Task 1(요건 검증)·Task 4(문서)
- C. init 번들 5 해제 → Task 4
- D. references 정합 → Task 4
- E. 골든 fragment-app + 기존 불변·pnpm 재생성 → Task 5, Task 2·3 바이트 규율
- F. render 검증 규칙 2건 → Task 1
- 비범위(fragment 생성 도우미 / category를 bump 소스로 / backfill=M3c-2 / trains=M3c-3) → 계획에 없음(의도적)
