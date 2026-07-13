# M3c-3a — release trains (이중 체계 모노레포) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `independent` 모노레포 위에 루트 CalVer release train을 얹어, 포함 패키지들의 마지막 릴리스 버전을 한 train 버전으로 스냅샷 고정하고 통합 노트·`train-{version}` 태그를 내보내는 `release-train` 스킬을 조건부 생성한다.

**Architecture:** 이중 체계 = `monorepoStrategy: "independent"` + top-level `train` 객체(file-less, SSOT=최신 `train-*` 태그). 패키지는 기존 independent 기계를 그대로 쓰고 train은 순수 additive로 얹힌다. train 버전 산술은 `next-version.py` 순수 calver 모드로, 패키지 스냅샷은 `changed-packages.py --json` anchor로 재사용해 **스크립트는 무변경**이며 유일한 Python 변경은 `validate_config` 규칙 3건이다.

**Tech Stack:** Python 3.9+ stdlib, 동결 template dialect(`{{path}}`/`{{#if}}`/`{{#unless}}`/`{{#each}}`), unittest, golden 스냅샷 테스트.

## Global Constraints

- 동결 template dialect — 확장 금지. 조건은 `{{#if path}}`, `{{#if path == "lit"}}`, `{{#unless}}`, 중첩 `{{#if}}`만.
- 생성 SKILL.md ≤150줄, init SKILL.md ≤500줄.
- render 엔진·스크립트(version.py·next-version.py·changed-packages.py) 산술·조작 **무변경**. 유일한 Python 변경은 `skills/init/scripts/render.py`의 `validate_config` 규칙 3건.
- 생성 스킬 자립성: `.superrelease/`·`.claude/` 상대 경로만 참조. 플러그인 경로(`${CLAUDE_PLUGIN_ROOT}`) 참조 금지. 다른 생성 스킬·템플릿은 프로즈로 참조 허용.
- 생성 스킬 description: 3인칭·pushy·한국어 트리거+영어 키워드·`{{project.name}}` 포함.
- manifest `when` = if-표현식 문법(dot-path truthy, `==`/`!=`). 부재 top-level 키는 `lookup`이 `_MISSING`→falsy 반환(검증 완료) — 비-train config는 `train.enabled` falsy로 안전 스킵.
- CalVer 어휘는 기존 7토큰(`YYYY·YY·0M·MM·0D·DD·MICRO`, MICRO≤1). train 기본 패턴 `YYYY.MICRO`. Spring Cloud 3파트는 비범위.
- 첫 train은 `next-version.py --current ""`(빈 문자열)로 호출 — `--current` 생략은 config 조회로 실패한다(실측). `--current ""` → MICRO=0.
- exit code 0/1/2. 코드·메시지 영어, 생성 문서·init 프로즈 한국어.
- TDD. 각 태스크 끝에 전체 스위트(`python3 -m unittest discover -s tests -q`) 통과. 최종 `claude plugin validate . --strict` + 골든 범위 확인.
- 골든 config는 스냅샷 대상 아님(harness가 config.json 스킵). render.py 변경은 골든 무영향.

**베이스 스펙:** `docs/superpowers/specs/2026-07-13-superrelease-m3c3a-release-trains-design.md`. **베이스 커밋:** main `2f7c0b7`.

---

### Task 1: render.py train 검증 규칙 3건

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`, 현재 line 220-222 backfill 규칙 뒤 · line 223 `sinks = {...}` 앞에 삽입)
- Test: `tests/test_render_pipeline.py` (line 163 `test_backfill_rejected_for_independent` 뒤에 5개 메서드 추가)

**Interfaces:**
- Consumes: `validate_config(config)` — `config.get("train")`, `repo.get("monorepoStrategy")`(지역변수 `strategy`), `problems` 리스트.
- Produces: train 객체 3규칙. 검증 통과하는 유효 train config = `monorepo_config()` + `cfg["train"] = {"enabled": True, "scheme": {"type": "calver", "pattern": "YYYY.MICRO"}, "tag": {"format": "train-{version}", "annotated": True, "signed": False}}`. Task 2·4가 이 형태를 재사용한다.

- [ ] **Step 1: 실패 테스트 5개 작성**

`tests/test_render_pipeline.py`의 `test_backfill_rejected_for_independent` 메서드(현재 line 157-163) 바로 뒤에 삽입:

```python
    def test_train_rejected_for_non_independent(self):
        cfg = scope_config(
            [{"file": "gradle.properties", "type": "properties-key",
              "key": "version"}])
        cfg["train"] = {"enabled": True,
                        "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                        "tag": {"format": "train-{version}", "annotated": True,
                                "signed": False}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("train", r.stderr)

    def test_train_rejected_for_non_calver_scheme(self):
        cfg = monorepo_config()
        cfg["train"] = {"enabled": True,
                        "scheme": {"type": "semver", "pattern": None},
                        "tag": {"format": "train-{version}", "annotated": True,
                                "signed": False}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("calver", r.stderr)

    def test_train_requires_pattern(self):
        cfg = monorepo_config()
        cfg["train"] = {"enabled": True,
                        "scheme": {"type": "calver", "pattern": ""},
                        "tag": {"format": "train-{version}", "annotated": True,
                                "signed": False}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("train.scheme.pattern", r.stderr)

    def test_train_requires_version_in_tag_format(self):
        cfg = monorepo_config()
        cfg["train"] = {"enabled": True,
                        "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                        "tag": {"format": "train-release", "annotated": True,
                                "signed": False}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("train.tag.format", r.stderr)

    def test_train_ok_for_independent_calver(self):
        cfg = monorepo_config()
        cfg["train"] = {"enabled": True,
                        "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                        "tag": {"format": "train-{version}", "annotated": True,
                                "signed": False}}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 0, r.stderr)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest tests.test_render_pipeline -v 2>&1 | grep -E "train|FAIL|ERROR"`
Expected: 5개 중 최소 4개 FAIL (reject 4개는 현재 exit 0이라 `assertEqual(1)` 실패; ok 1개는 이미 통과 가능).

- [ ] **Step 3: validate_config에 3규칙 구현**

`skills/init/scripts/render.py`에서 backfill 규칙(현재 line 220-222):

```python
    if repo.get("backfill") and strategy == "independent":
        problems.append("repo.backfill is not supported with the independent "
                        "monorepo strategy (monorepo backfill is deferred)")
```

바로 뒤(그리고 `sinks = {...}` 앞)에 삽입:

```python
    train = config.get("train") or {}
    if train.get("enabled"):
        if strategy != "independent":
            problems.append("train (release-train) requires the independent "
                            "monorepo strategy (dual-scheme = independent "
                            "packages + a CalVer train)")
        if (train.get("scheme") or {}).get("type") != "calver":
            problems.append('train.scheme.type must be "calver" '
                            "(the release train root uses CalVer)")
        if not (train.get("scheme") or {}).get("pattern"):
            problems.append("train.scheme.pattern is required "
                            "(a CalVer pattern, e.g. YYYY.MICRO)")
        tag_format = (train.get("tag") or {}).get("format")
        if not (tag_format and "{version}" in tag_format):
            problems.append('train.tag.format is required and must contain '
                            '"{version}" (e.g. train-{version})')
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest tests.test_render_pipeline -v 2>&1 | tail -3`
Expected: OK (train 5개 포함 전부 통과)

- [ ] **Step 5: 전체 스위트 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 162 tests ... OK` (157 + 5)

- [ ] **Step 6: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "feat: render 검증 — train은 independent+calver+pattern·tag.format 필수 (M3c-3a)"
```

---

### Task 2: release-train 스킬 + notes-train 템플릿 + manifest 2엔트리

**Files:**
- Create: `skills/init/assets/skills/release-train/SKILL.md`
- Create: `skills/init/assets/templates/notes-train.md`
- Modify: `skills/init/assets/manifest.json` (backfill 스킬 엔트리 뒤 + notes-package 템플릿 엔트리 뒤)
- Test: `tests/test_assets.py` (module-level `train_ctx` 헬퍼 + 렌더 스모크 6개)

**Interfaces:**
- Consumes: render 컨텍스트 = config 전체 + `project.name`·`plugin.version`·`generated.at`·`scope`(대표 scope). train 객체 필드 `train.scheme.pattern`·`train.tag.format`·`train.tag.signed`·`train.tag.annotated`. `changed-packages.py --json`(scope별 anchor)·`next-version.py --current <ver> --scheme calver --pattern <p> --today <d>`·`version.py get --scope <n>` 재사용.
- Produces: `.claude/skills/release-train/SKILL.md`(dest)·`.superrelease/templates/notes-train.md`(dest), 둘 다 `when: "train.enabled"`. Task 4 골든이 렌더 결과를 고정한다.

- [ ] **Step 1: release-train 스킬 작성**

`skills/init/assets/skills/release-train/SKILL.md` 생성 (아래 전문 그대로):

````markdown
---
name: release-train
description: {{project.name}} 모노레포의 루트 release train을 릴리스한다. 사용자가 train 릴리스, 릴리스 트레인, 통합 릴리스, 루트 릴리스, train 태그 따줘, 이번 train에 뭐 들어가, 다음 train 버전, release train 등 패키지 개별이 아닌 루트 train 단위 릴리스를 요청하면 반드시 이 스킬을 사용한다.
---

# release-train — {{project.name}} 루트 release train 릴리스

이 레포는 이중 체계다 — 패키지는 각자 SemVer로 개별 릴리스하고(release 스킬), 루트 **release train**은 그 패키지들의 마지막 릴리스 버전 조합을 하나의 CalVer 버전으로 묶어 스냅샷한다. 이 스킬은 **루트 train 릴리스 전용**이며 패키지 개별 릴리스와 별개의 릴리스 타입이다. 정책 SSOT는 `.superrelease/config.json`의 `train` 객체다.

공통 규칙:

- 버전 산술은 스크립트로만: `python3 .superrelease/scripts/<script>` (Windows는 `py -3`).
- 부작용 있는 동작(파일 수정, 커밋, push, 태그{{#if github.release}}, Release 생성{{/if}})은 **dry-run 프리뷰 → 사용자 확인 → 실행**. 확인은 AskUserQuestion을 쓰되 도구가 없으면 텍스트로 물어라.
- train은 **패키지 버전 파일을 수정하지 않는다** — 스냅샷은 읽기 전용이고, 이 스킬이 쓰는 것은 통합 노트 파일과 train 태그뿐이다. 버전 bump·패키지 태그는 release 스킬 소관이다.
{{#if github.release}}- GitHub 접근: gh CLI 우선. 미가용이면 연결된 GitHub MCP 도구를 찾아 쓰고, 둘 다 없으면 "태그까지만" 제한 모드를 제안하라.{{/if}}

status 모드: "이번 train에 뭐 들어가", "다음 train 버전" 류 요청은 2~4단계만 수행해 스냅샷·다음 버전을 보고하고 멈춘다.

## 1. preflight — 모두 통과해야 진행

1. 현재 브랜치: `git branch --show-current` 결과가 `{{repo.defaultBranch}}` 여야 함
2. clean working tree: `git status --porcelain` 출력이 비어 있어야 함
3. 원격 동기화: `git fetch origin` 후 `git rev-list HEAD..origin/{{repo.defaultBranch}} --count` 가 0
{{#if github.release}}4. gh 인증: `gh auth status` — 실패 시 GitHub MCP 폴백, 둘 다 없으면 제한 모드(태그까지만) 확인{{/if}}
5. 중단된 패키지 릴리스 확인: 어떤 패키지 scope의 파일 버전(수식어 제외)이 마지막 태그보다 높은데 그 버전 태그가 없으면 개별 릴리스가 진행 중인 것 — train은 릴리스된 조합을 묶으므로, 먼저 그 패키지 릴리스를 마치라고 안내하고 멈춰라.

## 2. 현재 train 버전

- `git tag --list`로 태그를 모으고 `{{train.tag.format}}` 포맷({version} 자리에 CalVer)에 맞는 태그만 남긴다.
- 버전 순으로 정렬해 최신 태그에서 접두사를 떼면 현재 train 버전이다. 맞는 태그가 하나도 없으면 **첫 train**이다.

## 3. 다음 train 버전

- 계산은 스크립트로만(LLM 산술 금지): `python3 .superrelease/scripts/next-version.py --current <현재 train 버전> --scheme calver --pattern {{train.scheme.pattern}} --today <오늘 YYYY-MM-DD>`.
- **첫 train**이면 `--current ""`(빈 문자열)로 호출한다. 같은 기간이면 MICRO를 증가시키고, 기간이 바뀌면 0으로 리셋하며, 첫 train은 MICRO 0이다.

## 4. 패키지 버전 스냅샷

- `python3 .superrelease/scripts/changed-packages.py --json`을 실행한다 — 스크립트가 scope마다 자기 마지막 태그(anchor)를 내부적으로 해석한다. 각 scope의 anchor가 그 패키지의 **마지막 릴리스 버전**이다.
- anchor가 태그가 아닌 scope(tagless — anchor가 커밋 sha)는 `python3 .superrelease/scripts/version.py get --scope <이름>`으로 파일 버전을 폴백하되, `-SNAPSHOT`·`-dev` 등 개발 수식어가 붙어 있으면 "미릴리스 개발 버전"으로 표시하라.
- 결과를 (패키지 | 버전) 표로 정리한다 — 이 조합이 train이 고정하는 스냅샷이다.

## 5. 통합 노트

- `.claude/skills/release-notes/SKILL.md` 절차로 train 통합 노트 초안을 쓴다. 소스는 각 scope의 `<anchor>..HEAD` 커밋이다: `git log <anchor>..HEAD --pretty=format:"%h %s" -- <scope.path>`{{#if repo.mergePolicy == "squash"}} — squash 레포이므로 커밋 제목의 `(#N)`으로 PR을 역참조하고 PR 메타데이터를 1차 소스로 써라{{/if}}.
- `.superrelease/templates/notes-train.md` 골격으로 작성한다: 4단계 스냅샷 표 + 하이라이트 + 주요 변경 + 포함 패키지들의 Breaking Changes rollup.

## 6. dry-run 프리뷰 → 커밋{{#if repo.releasePath == "release-pr"}}/PR{{/if}}

프리뷰에 다음을 보여주고 확인받아라:

- 패키지 버전 스냅샷 표
- 다음 train 버전과 생성될 태그명(`{{train.tag.format}}`의 {version}에 다음 버전 대입)
- 실행될 명령 목록(노트 커밋, {{#if repo.releasePath == "release-pr"}}PR 생성{{else}}push{{/if}}, 태그{{#if github.release}}, Release{{/if}})
- 통합 노트 미리보기

{{#if repo.releasePath == "direct-push"}}확인 후: 통합 노트 파일을 커밋하고 `git push origin {{repo.defaultBranch}}`. 이어서 7단계.{{else}}확인 후 **릴리스 PR 경로**: `release/train-<다음 버전>` 브랜치를 만들어 통합 노트 커밋을 쌓고 push → PR 1건 생성(`gh pr create --base {{repo.defaultBranch}}` — 본문에 스냅샷 표와 통합 노트를 넣어라; gh 미가용이면 GitHub MCP 폴백) → **중단**(태그는 머지 후). 머지 후 재개: PR 머지를 확인하고 `git checkout {{repo.defaultBranch}} && git pull` 한 뒤 7단계부터 이어가라. PR이 열려 있으면 대기 중임을 보고하고 멈춰라.{{/if}}

## 7. train 태그{{#if github.release}} + GitHub Release{{/if}}

- push 직전 충돌 재확인: `git ls-remote --tags origin <태그>` 가 비어 있어야 함 — 결과가 있으면 **즉시 중단**(동시 릴리스 락, 버전 재사용 금지).
- 태그 생성: {{#if train.tag.signed}}`git tag -s <태그> -F <통합 노트 파일>`{{else}}{{#if train.tag.annotated}}`git tag -a <태그> -F <통합 노트 파일>`{{else}}`git tag <태그>` — lightweight 태그라 노트는 통합 노트 파일에만 남는다{{/if}}{{/if}} → `git push origin <태그>`.
{{#if github.release}}- gh 경로: `gh release create <태그> --title "<태그>" --notes-file <통합 노트 파일>`
- MCP 폴백: 5단계 통합 노트로 Release를 생성하라.
{{/if}}

## 실패 시

어디까지 진행됐는지(노트 커밋 / {{#if repo.releasePath == "release-pr"}}PR / {{/if}}태그{{#if github.release}} / Release{{/if}}) 명시하라. **push된 태그는 되돌리지 않는다** — 잘못 나간 train은 다음 train으로 덮는다.
````

- [ ] **Step 2: notes-train 템플릿 작성**

`skills/init/assets/templates/notes-train.md` 생성 (아래 전문 그대로):

```markdown
{{#unless scope.notes.language == "en"}}<!-- release train 통합 노트 템플릿. {version}, {date}는 작성 시점에 채운다. 해당 없는 섹션은 생략한다. -->
# {{project.name}} train {version} — {date}

## 포함 버전 스냅샷
<!-- | 패키지 | 버전 | — 이 train이 고정하는 조합 -->

## 하이라이트
<!-- 이 train에서 가장 중요한 변경 1~3개를 한 문단으로 -->

## 주요 변경
<!-- - 패키지 전반의 사용자 관점 변경 요약 (#PR번호) -->

## Breaking Changes
<!-- 포함 패키지들의 breaking 취합. 없으면 섹션 삭제. 있으면 마이그레이션 가이드 필수 -->
{{/unless}}{{#unless scope.notes.language == "ko"}}<!-- Release-train notes template. Fill {version} and {date} when drafting; drop empty sections. -->
# {{project.name}} train {version} — {date}

## Version Snapshot
<!-- | Package | Version | — the combination this train pins -->

## Highlights

## Changes

## Breaking Changes
{{/unless}}
```

- [ ] **Step 3: manifest 2엔트리 추가**

`skills/init/assets/manifest.json`에서 backfill 스킬 엔트리(현재 line 33-38):

```json
    {
      "src": "skills/backfill/SKILL.md",
      "dest": ".claude/skills/backfill/SKILL.md",
      "render": true,
      "when": "repo.backfill"
    },
```

바로 뒤에 삽입:

```json
    {
      "src": "skills/release-train/SKILL.md",
      "dest": ".claude/skills/release-train/SKILL.md",
      "render": true,
      "when": "train.enabled"
    },
```

그리고 notes-package 템플릿 엔트리(현재 line 65-71):

```json
    {
      "src": "templates/notes-package.md",
      "dest": ".superrelease/templates/notes-package.md",
      "render": true,
      "preserve": "template",
      "when": "repo.monorepoStrategy == \"independent\""
    },
```

바로 뒤에 삽입:

```json
    {
      "src": "templates/notes-train.md",
      "dest": ".superrelease/templates/notes-train.md",
      "render": true,
      "preserve": "template",
      "when": "train.enabled"
    },
```

- [ ] **Step 4: 렌더 스모크 테스트 작성**

`tests/test_assets.py`의 module-level에서 `mono_ctx` 함수(현재 line 24-32) 바로 뒤에 `train_ctx` 헬퍼 추가:

```python
def train_ctx(**overrides):
    cfg = monorepo_config()
    cfg["train"] = {"enabled": True,
                    "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                    "tag": {"format": "train-{version}", "annotated": True,
                            "signed": False}}
    cfg.update(overrides)
    ctx = dict(cfg)
    ctx["project"] = {"name": "demo-mono"}
    ctx["plugin"] = {"version": "0.1.0"}
    ctx["generated"] = {"at": "2026-01-01T00:00:00+00:00"}
    ctx["scope"] = cfg["scopes"][0]
    return ctx
```

그리고 `tests/test_assets.py` 파일 **맨 끝**에 새 테스트 클래스를 추가한다(별도 클래스라 어느 render_asset과도 무관하게 `ctx`를 명시 전달):

```python
class ReleaseTrainAssetsTest(unittest.TestCase):
    def render_asset(self, rel, ctx):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        return render.render_template(text, ctx)

    def test_release_train_renders_clean(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("demo-mono", out)
        self.assertIn("changed-packages.py --json", out)
        self.assertIn("--pattern YYYY.MICRO", out)
        self.assertIn("train-{version}", out)  # tag.format 단일 중괄호 보존

    def test_release_train_direct_push_path(self):
        out = self.render_asset("skills/release-train/SKILL.md", train_ctx())
        self.assertIn("git push origin main", out)
        self.assertIn("git tag -a", out)
        self.assertNotIn("release/train-", out)

    def test_release_train_release_pr_path(self):
        ctx = train_ctx()
        ctx["repo"]["releasePath"] = "release-pr"
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertNotIn("{{", out)
        self.assertIn("release/train-", out)
        self.assertIn("gh pr create", out)
        self.assertNotIn("통합 노트 파일을 커밋하고 `git push origin main`", out)

    def test_release_train_signed_tag(self):
        ctx = train_ctx()
        ctx["train"]["tag"]["signed"] = True
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertIn("git tag -s", out)
        self.assertNotIn("git tag -a", out)

    def test_release_train_omits_github_when_disabled(self):
        ctx = train_ctx()
        ctx["github"]["release"] = False
        out = self.render_asset("skills/release-train/SKILL.md", ctx)
        self.assertNotIn("gh release create", out)
        self.assertNotIn("gh auth status", out)

    def test_notes_train_renders_clean_ko(self):
        out = self.render_asset("templates/notes-train.md", train_ctx())
        self.assertNotIn("{{", out)
        self.assertIn("포함 버전 스냅샷", out)
        self.assertIn("demo-mono train {version}", out)  # 헤딩 단일 중괄호 보존
        self.assertNotIn("Version Snapshot", out)  # en 블록은 ko에서 드롭
```

- [ ] **Step 5: 렌더 스모크 통과 확인**

Run: `python3 -m unittest tests.test_assets -v 2>&1 | grep -E "train|FAIL|ERROR" | head`
Expected: train 6개 전부 ok, FAIL/ERROR 없음. (`{{` 잔존이 있으면 조건 블록 오타 — 수정)

- [ ] **Step 6: 전체 스위트 + 스킬 줄 수 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3 && wc -l skills/init/assets/skills/release-train/SKILL.md`
Expected: `Ran 168 tests ... OK` (162 + 6), release-train ≤150줄.

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/skills/release-train/SKILL.md skills/init/assets/templates/notes-train.md skills/init/assets/manifest.json tests/test_assets.py
git commit -m "feat: release-train 스킬 + notes-train 템플릿 + manifest 2엔트리 (M3c-3a)"
```

---

### Task 3: init 번들 1·2 해제 + config 템플릿(train 객체) + references 정합

**Files:**
- Modify: `skills/init/SKILL.md` (번들1 line 48 / 번들2 line 49 / config 템플릿 line 77 / 각주 line 118 뒤 / 지원 범위 line 143)
- Modify: `tests/helpers.py` (line 73 `"train": False,` 제거)
- Modify: `skills/init/references/monorepo.md` (이중 체계 절 line 23-26 · 지원 현황 line 86)
- Modify: `skills/init/references/version-schemes.md` (CalVer 절 line 71 뒤)

**Interfaces:**
- Consumes: 없음(문서·픽스처 정합).
- Produces: init이 "이중" 선택 시 `monorepoStrategy: "independent"` + `train` 객체를 쓰도록 canonical 스키마 갱신. `repo.train` 불리언 폐기(→ `train` 객체 승격).

- [ ] **Step 1: helpers.py에서 vestigial repo.train 제거**

`tests/helpers.py` line 73:

```python
        "maintenanceLines": False, "train": False,
```

를 다음으로 교체:

```python
        "maintenanceLines": False,
```

(train 게이트는 이제 top-level `train.enabled`. `repo.train`은 폐기 — 픽스처에서 죽은 필드 제거.)

- [ ] **Step 2: 전체 스위트 그대로 통과 확인 (픽스처 변경 무해)**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 168 tests ... OK` (repo.train 참조 테스트 없음 — 사전 확인 완료)

- [ ] **Step 3: init 번들 1 — 이중 체계 해제**

`skills/init/SKILL.md` 번들 1(line 48)에서:

```
- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). monorepo면 전략을 묻는다 — fixed(전 패키지 버전 공유) | independent(패키지별 독립) | 이중 체계(M3 예정 표시). independent면 스캔 리포트 `monorepo.packages`를 표로 제시해 scope 목록(이름 = 패키지 이름 또는 디렉터리명, path, 버전 파일)을 확정한다. fixed면 단일 root scope의 versionLocations에 전 패키지 버전 파일을 모은다(릴리스 흐름은 단일 레포와 동일).
```

를 다음으로 교체:

```
- **번들 1 — 성격·전략**: 레포 성격(library | app/service | monorepo). monorepo면 전략을 묻는다 — fixed(전 패키지 버전 공유) | independent(패키지별 독립) | 이중 체계(루트 CalVer train + 패키지 개별 SemVer). independent·이중 체계면 스캔 리포트 `monorepo.packages`를 표로 제시해 scope 목록(이름 = 패키지 이름 또는 디렉터리명, path, 버전 파일)을 확정한다(이중 체계는 `monorepoStrategy: "independent"` 위에 top-level `train` 객체를 얹는다 — 번들 2에서 train CalVer·태그를 묻는다). fixed면 단일 root scope의 versionLocations에 전 패키지 버전 파일을 모은다(릴리스 흐름은 단일 레포와 동일).
```

- [ ] **Step 4: init 번들 2 — train CalVer·태그 질문 추가**

`skills/init/SKILL.md` 번들 2(line 49) 문장 **끝**(마지막 `결정).` 뒤)에 다음을 이어 붙인다:

```
 **(이중 체계) train 루트**: train은 CalVer가 기본이며 pattern을 묻는다(기본 `YYYY.MICRO` — `2026.0`, `2026.1`; 어휘는 scope와 동일한 YYYY/YY/0M/MM/0D/DD/MICRO, MICRO 최대 1회) / train 태그 포맷(기본 `train-{version}` — 패키지 `<scope>@{version}`와 별도 네임스페이스)·annotated(기본 yes)·signed. 이 값들을 top-level `train` 객체로 기록한다.
```

- [ ] **Step 5: config 템플릿 — repo.train 제거 + train 각주**

`skills/init/SKILL.md` config 템플릿 repo 블록(line 77):

```
    "backfill": false,
    "train": false,
    "releaseCommitFormat": "chore(release): {version}",
```

를 다음으로 교체(`"train": false,` 줄 삭제):

```
    "backfill": false,
    "releaseCommitFormat": "chore(release): {version}",
```

그리고 backfill 각주(line 118, `- backfill: ...`) 바로 뒤에 train 각주를 추가:

```
- 이중 체계(train): `monorepoStrategy`가 "independent"이고 이중 체계를 택하면 config 최상위에 `train` 객체를 추가한다 — `{ "enabled": true, "scheme": { "type": "calver", "pattern": "YYYY.MICRO" }, "tag": { "format": "train-{version}", "annotated": true, "signed": false } }`. 그러면 `.claude/skills/release-train/SKILL.md`와 `.superrelease/templates/notes-train.md`가 생성된다(루트 train 릴리스 — 패키지들의 마지막 릴리스 버전을 CalVer 한 버전으로 스냅샷, 태그·노트만; render가 train은 independent+calver+pattern·tag.format을 요구한다).
```

- [ ] **Step 6: 지원 범위 갱신**

`skills/init/SKILL.md` 지원 범위(line 143):

```
- 모노레포 이중 체계(루트 train + 패키지 SemVer)와 release-train 스킬: M3c
```

를 다음으로 교체:

```
- 모노레포 이중 체계(루트 CalVer train + 패키지 SemVer)와 release-train 스킬: 지원 — `train` 객체(file-less, 최신 `train-{version}` 태그가 SSOT), 패키지 마지막 릴리스 버전 스냅샷, direct-push·release-pr 양쪽. Spring Cloud식 3파트 CalVer·train 버전 파일(BOM)·모노레포 backfill은 후속(M3c-3b)
```

- [ ] **Step 7: monorepo.md — 이중 체계 실동작 서술**

`skills/init/references/monorepo.md`의 이중 체계 항목(line 23-26):

```
**이중 체계**: 루트에는 CalVer 기반 release train 버전을 두고, 그 안에 포함된 개별 패키지는 자기 SemVer를 그대로 유지한다.

- 대표 사례: Spring Cloud. 루트 train은 `2020.0.x`처럼 CalVer 스타일 이름을 쓰지만, 그 train에 포함된 `spring-cloud-config`, `spring-cloud-netflix` 같은 모듈들은 각자의 SemVer 버전을 유지한다.
- 의도: "이번 train에 어떤 조합의 모듈 버전들이 함께 검증됐는가"를 train 버전 하나로 표현한다.
```

를 다음으로 교체:

```
**이중 체계**: 루트에는 CalVer 기반 release train 버전을 두고, 그 안에 포함된 개별 패키지는 자기 SemVer를 그대로 유지한다.

- 대표 사례: Spring Cloud. 루트 train은 `2020.0.x`처럼 CalVer 스타일 이름을 쓰지만, 그 train에 포함된 `spring-cloud-config`, `spring-cloud-netflix` 같은 모듈들은 각자의 SemVer 버전을 유지한다.
- 의도: "이번 train에 어떤 조합의 모듈 버전들이 함께 검증됐는가"를 train 버전 하나로 표현한다.
- superrelease 구현: `monorepoStrategy: "independent"`(패키지는 개별 릴리스 그대로) + top-level `train` 객체. train은 **file-less** — 버전 SSOT는 최신 `train-{version}` 태그이고, 버전 파일을 두지 않는다. 루트 train 릴리스는 별도 `release-train` 스킬이 담당한다: 각 패키지의 **마지막 릴리스(태그) 버전**을 스냅샷하고(개발 `-SNAPSHOT` 버전이 아니라 태그 버전이라야 "검증된 조합"이 정확), 통합 노트(notes-train)를 쓰고, CalVer `train-{version}` 태그를 단다. direct-push·release-pr(보호 브랜치) 양쪽을 지원한다.
- train CalVer 어휘 한계: superrelease의 CalVer는 `YYYY·YY·0M·MM·0D·DD·MICRO` 7토큰(MICRO 최대 1회)만 계산하므로 Spring Cloud의 3파트 `2020.0.1`(연도.MINOR.PATCH)은 그대로 표현할 수 없다 — `YYYY.MICRO`(`2026.0`, `2026.1`)를 기본으로 제안한다.
```

- [ ] **Step 8: monorepo.md 지원 현황 갱신**

`skills/init/references/monorepo.md` 지원 현황(line 86):

```
**이중 체계(dual-system)와 release-train은 M3**(조건부 기능)로 미뤄진다 — M2에서도 이중 체계 질문은 아직 등장하지 않는다.
```

를 다음으로 교체:

```
**이중 체계(dual-system)와 release-train은 M3c-3a에서 지원된다** — init이 이중 체계를 물어 `train` 객체를 기록하면 조건부로 `release-train` 스킬이 생성된다. 모노레포 backfill(패키지 태그 네임스페이스 순회)은 후속 M3c-3b로 남는다.
```

- [ ] **Step 9: version-schemes.md — train CalVer 한계 명시**

`skills/init/references/version-schemes.md`의 CalVer 절, Spring Cloud 문장(line 71):

```
Spring Cloud가 대표적인 사례다 — 개별 모듈은 SemVer를 쓰면서 루트 release train 이름만 `2020.0.x` 같은 CalVer 스타일로 옮겨갔다(모노레포에서의 이중 체계 조합은 `monorepo.md` 참고).
```

를 다음으로 교체:

```
Spring Cloud가 대표적인 사례다 — 개별 모듈은 SemVer를 쓰면서 루트 release train 이름만 `2020.0.x` 같은 CalVer 스타일로 옮겨갔다(모노레포에서의 이중 체계 조합은 `monorepo.md` 참고). 다만 superrelease의 CalVer는 위 7토큰(MICRO 최대 1회)만 계산하므로 Spring Cloud의 3파트 `2020.0.1`은 그대로 표현할 수 없다 — release train 루트에는 `YYYY.MICRO`(`2026.0`, `2026.1`)처럼 단일 MICRO 패턴을 권장한다.
```

- [ ] **Step 10: 정합·줄 수·strict 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -2 && wc -l skills/init/SKILL.md && grep -c "train" skills/init/SKILL.md`
Expected: OK, init SKILL.md ≤500줄, train 언급 존재.

Run: `claude plugin validate . --strict 2>&1 | tail -3`
Expected: 통과(에러 없음).

- [ ] **Step 11: 커밋**

```bash
git add skills/init/SKILL.md tests/helpers.py skills/init/references/monorepo.md skills/init/references/version-schemes.md
git commit -m "feat: init 번들1·2 이중 체계 해제 + config train 객체 + references 정합 (M3c-3a)"
```

---

### Task 4: 골든 train-monorepo 신규 + 최종 검증

**Files:**
- Modify: `tests/golden_configs.py` (train_monorepo 빌더 + GOLDEN 엔트리)
- Create: `tests/golden/train-monorepo/expected/**` (update_golden.py 산출)

**Interfaces:**
- Consumes: `monorepo_config()`(helpers), Task 2의 manifest 엔트리·스킬·템플릿, Task 1의 validate 규칙.
- Produces: 12번째 골든 트리 `train-monorepo`. 기존 11골든 바이트 불변.

- [ ] **Step 1: train_monorepo 빌더 + GOLDEN 엔트리 추가**

`tests/golden_configs.py`의 `backfill_app` 함수(현재 line 86-91) 뒤에 추가:

```python
def train_monorepo():
    # independent + train 객체 → release-train 스킬 + notes-train 템플릿 생성
    cfg = monorepo_config()
    cfg["train"] = {"enabled": True,
                    "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                    "tag": {"format": "train-{version}", "annotated": True,
                            "signed": False}}
    return cfg
```

그리고 파일 상단 import(line 2)를 `monorepo_config`도 포함하도록 갱신:

```python
from helpers import monorepo_config, scope_config
```

(이미 `scope_config`만 import돼 있으면 위처럼 `monorepo_config`를 추가한다.)

그리고 GOLDEN 딕셔너리(line 94-99)에 엔트리 추가:

```python
GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app, "train-monorepo": train_monorepo}
```

- [ ] **Step 2: 골든 재생성**

Run: `python3 tests/update_golden.py`
Expected: 무오류 종료.

- [ ] **Step 3: 골든 범위 확인 — 신규 트리만 추가, 기존 11 불변**

Run: `git status --porcelain tests/golden tests/golden_configs.py`
Expected: `tests/golden_configs.py` 수정 1건 + `tests/golden/train-monorepo/...` 신규만. **기존 11골든 트리에 변경(`M`)이 있으면 안 된다** — 있으면 Task 2의 조건 블록이 비-train config에서 바이트를 흘린 것 → 회귀로 조사.

Run: `ls tests/golden/train-monorepo/expected/.claude/skills/ && ls tests/golden/train-monorepo/expected/.superrelease/templates/`
Expected: `release/  release-notes/  release-train/` (스킬 3종) + templates에 `notes-package.md  notes-train.md ...` 포함. release-train/SKILL.md·notes-train.md에 `{{` 없음:

Run: `grep -rl "{{" tests/golden/train-monorepo/expected/ || echo "no-braces-clean"`
Expected: `no-braces-clean`.

- [ ] **Step 4: 전체 스위트 + strict 최종 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: `Ran 168 tests ... OK` (골든 테스트가 train-monorepo 포함 12트리 비교).

Run: `claude plugin validate . --strict 2>&1 | tail -3`
Expected: 통과.

- [ ] **Step 5: e2e — train config 렌더 확인(임시 git 레포)**

Run:
```bash
tmp=$(mktemp -d) && git -C "$tmp" init -q -b main && \
python3 -c "import json,sys; sys.path.insert(0,'tests'); from golden_configs import train_monorepo; open('$tmp/cfg.json','w').write(json.dumps(train_monorepo()))" && \
mkdir -p "$tmp/.superrelease" && cp "$tmp/cfg.json" "$tmp/.superrelease/config.json" && \
python3 skills/init/scripts/render.py --config "$tmp/.superrelease/config.json" --assets skills/init/assets --repo "$tmp" && \
ls "$tmp/.claude/skills/release-train/SKILL.md" "$tmp/.superrelease/templates/notes-train.md" && \
grep -c "train-{version}" "$tmp/.claude/skills/release-train/SKILL.md"; rm -rf "$tmp"
```
Expected: 두 파일 경로 출력 + `train-{version}` 매치 ≥1 (렌더 성공, 자립 생성 확인).

- [ ] **Step 6: 커밋**

```bash
git add tests/golden_configs.py tests/golden/train-monorepo
git commit -m "test: 골든 train-monorepo 추가 — release-train 스킬·notes-train 생성 고정 (M3c-3a)"
```

---

## Self-Review

**1. Spec coverage:**

| 스펙 섹션 | 태스크 |
|---|---|
| A. 전략 인코딩(independent+train) | T1(validate independent 요구), T3(init 번들1·각주) |
| B. config train 객체(file-less, repo.train 승격) | T3(config 템플릿·helpers), T4(골든 config) |
| C. render 검증 3규칙 | T1 |
| D. release-train 스킬(§0~§8, direct-push/release-pr, 첫 train `--current ""`) | T2 |
| E. notes-train 템플릿 | T2 |
| F. init 번들 1·2 + config | T3 |
| G. references(monorepo·version-schemes) | T3 |
| H. 골든 train-monorepo + 기존 불변 | T4 |
| 제약(스크립트 무변경·자립성·줄 수·strict) | 전 태스크 검증 스텝 |

갭 없음.

**2. Placeholder scan:** 모든 코드 스텝에 실제 코드·명령·기대 출력 명시. "TBD"·"적절히"·"비슷하게" 없음. 스킬·템플릿 전문 수록.

**3. Type consistency:** train 객체 형태 `{"enabled": True, "scheme": {"type": "calver", "pattern": "YYYY.MICRO"}, "tag": {"format": "train-{version}", "annotated": True, "signed": False}}`가 T1 테스트·T2 train_ctx·T4 빌더에서 동일. manifest `when: "train.enabled"`가 스킬·템플릿 두 엔트리 일치. validate 메시지 키워드("train"/"calver"/"train.scheme.pattern"/"train.tag.format")가 T1 테스트 assertIn과 일치. 스킬 렌더 문자열("changed-packages.py --json"/"--pattern YYYY.MICRO"/"train-{version}"/"release/train-"/"git tag -a"/"git tag -s")이 T2 테스트 assert와 일치.

**4. 테스트 수 회계:** 157(base) → +5(T1) = 162 → +6(T2) = 168 → T3 불변 168 → T4 불변 168(골든 트리 수만 11→12). 각 태스크 검증 스텝의 기대 카운트와 일치.
