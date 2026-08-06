# M6 하드닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 커버리지 검토가 재현한 정합성 위험(P0 3건)과 validate 침묵 지대를 제거하고 골든 회귀망을 넓힌다 — 선행으로 v0.4.0을 릴리스한다.

**Architecture:** 엔진(렌더 dialect·버전 산술)은 불변. `validate_config`에 거부 규칙을 추가하고(Task 1~3), 스크립트 2종에 입력 가드만 넣으며(Task 4), 골든 트리를 넓히고(Task 5), 혼합태그 프로즈를 파생값으로 게이트한다(Task 6). 스펙: [2026-08-06-superrelease-m6-hardening-design.md](../specs/2026-08-06-superrelease-m6-hardening-design.md).

**Tech Stack:** Python 3.9+ 표준 라이브러리만 · unittest(pytest 아님) · 골든 스냅샷(`tests/golden/`) · 동결 템플릿 dialect.

## Global Constraints

- 스크립트는 Python 3.9+ **표준 라이브러리만**. exit code `0` 성공 / `1` 검증 실패 / `2` 사용법·config 오류.
- 에러 메시지·코드는 **영어**, 문서·스킬 프로즈는 한국어.
- 템플릿은 동결 dialect만: `{{path}}` `{{#if x}}` `{{#if x == "lit"}}` `{{else}}` `{{#unless}}` `{{#each}}` — 확장 금지.
- **바이트 불변**: 조건 블록 추가 시 개행을 블록 **안**에 둬서, 그 기능이 없는 config의 기존 골든이 바이트 동일해야 한다.
- **골든 규율**: `python3 tests/update_golden.py` 후 `git status --porcelain tests/golden`이 의도한 파일만 보여야 한다. 골든 재생성이 필요한 Task는 4(전 22트리의 스크립트 2종만), 5(신규 트리만), 6(tagless 3종+신규 1종)뿐이다.
- **dogfood 재렌더**: `skills/init/assets/` 수정 시 `python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-01-01T00:00:00+00:00` 로 재렌더하고 변경분을 같은 커밋에 포함(`tests/test_dogfood_selfrender.py`가 강제). `--now`는 아무 고정 ISO나 가능 — 마커는 pluginVersion에서 오므로 값은 diff에 안 나타난다.
- 테스트: 전체 `python3 -m unittest discover -s tests -q` / 단일 모듈 `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` (**dotted 형식 `unittest tests.<mod>` 금지** — helpers import가 깨진다).
- 생성 스킬 SKILL.md는 **150줄 이하** 유지 (현재: release 104 · release-monorepo 100 · hotfix 66).
- 커밋: Conventional Commits + 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 플러그인 검증: 랜딩 전 `claude plugin validate . --strict`.

---

### Task 0: Phase 0 — v0.4.0 선릴리스 (⚠️ 메인 세션 전용)

**서브에이전트로 디스패치하지 마라.** push·태그·GitHub Release·gh 계정 전환이 있는 부작용 작업이라 사용자 확인 게이트가 필요하다. 메인 세션이 사용자와 함께 수행한다.

**Files:** 코드 변경 없음 (CHANGELOG.md·버전 파일은 release 스킬이 수정).

- [ ] **Step 1: main 전환 및 최신화** — `git checkout main && git pull`. 작업 트리 clean 확인.
- [ ] **Step 2: 릴리스 플로우 실행** — `.claude/skills/release/SKILL.md` 절차대로 ("릴리스해줘"). 기대 bump: `[Unreleased]`에 `feat!`(train·tag-message 제거)+feat 3건 → 0.x 관례(breaking→minor)로 **0.3.0 → 0.4.0**. release-pr 경로: `release/0.4.0` 브랜치 → PR 생성 후 중단.
- [ ] **Step 3: PR 머지** — `gh auth switch --user Cho-D-YoungRae` → merge → `gh auth switch --user aims-yrcho` (운영 패턴 메모리 준수).
- [ ] **Step 4: 재개** — "릴리스해줘" 재실행 → preflight가 머지-미태그 상태 감지 → `v0.4.0` 태그 + GitHub Release.
- [ ] **Step 5: 정합 확인** — `git rev-parse HEAD`와 `git rev-parse origin/main` 일치, `gh release view v0.4.0` 존재 확인.
- [ ] **Step 6: M6 브랜치 리베이스** — `git checkout fix/m6-hardening && git rebase main`.

---

### Task 1: validate — B-1 releasePath 닫힌 집합 + B-2 next-snapshot 정합

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`, L177~344)
- Test: `tests/test_render_pipeline.py` (`PipelineTest` 클래스 — `self.write_config`/`self.render` 헬퍼 사용, 기존 거부 테스트들이 L145~ 부근에 있다)

**Interfaces:**
- Consumes: `validate_config(config) -> problems 리스트` 기존 구조, `PipelineTest` 헬퍼.
- Produces: 없음 (규칙은 독립적. 이후 Task의 신규 골든 config들은 이 규칙을 통과해야 한다 — Task 5 config는 전부 유효 조합으로 이미 설계됨).

- [ ] **Step 1: 실패하는 테스트 2건 작성** — `PipelineTest` 클래스 끝(예: `test_fragment_ok_with_sink` 뒤)에 추가:

```python
    def test_release_path_typo_rejected(self):
        # 커버리지 검토 P0 재현: "release_pr" 오타가 침묵 통과해
        # release-pr flavor 스킬 + 미렌더 release-pr-body.md 참조를 만들었다
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["releasePath"] = "release_pr"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("releasePath", r.stderr)
        self.assertIn("release_pr", r.stderr)

    def test_next_snapshot_requires_mutable_qualifier(self):
        # 커버리지 검토 P0 재현: qualifier null이면 생성 스킬의
        # `--qualifier ` 명령이 릴리스 시점 argparse 오류로 죽는다
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
        cfg["scopes"][0]["postRelease"] = {"bump": "next-snapshot"}
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("next-snapshot", r.stderr)
        self.assertIn("mutable", r.stderr)
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` → 신규 2건 FAIL(returncode 0 != 1), 나머지 PASS.
- [ ] **Step 3: 구현** — `validate_config`에 규칙 추가. B-1은 `for key in ("kind", "defaultBranch", "releasePath")` 필수 검사 블록(L183~185) **바로 뒤**:

```python
    release_path = repo.get("releasePath")
    if release_path and release_path not in ("direct-push", "release-pr"):
        problems.append('repo.releasePath must be "direct-push" or "release-pr" '
                        '(got "{}")'.format(release_path))
```

B-2는 scheme 검사 scope 루프(L263 `for i, s in enumerate(scopes or []):` — `scheme_type` 검사가 있는 루프) 안에 추가:

```python
        post_bump = (s.get("postRelease") or {}).get("bump") or "none"
        if post_bump == "next-snapshot":
            pre = s.get("preRelease") or {}
            if pre.get("style") != "mutable" or not pre.get("qualifier"):
                problems.append(
                    'scopes[{}]: postRelease.bump "next-snapshot" requires '
                    'preRelease.style "mutable" with a non-empty qualifier — '
                    "the rendered release skill runs next-version.py "
                    "--qualifier <preRelease.qualifier> for the post-release "
                    "bump".format(i))
```

- [ ] **Step 4: 통과 확인** — `python3 -m unittest discover -s tests -q` → 전부 OK. 골든·dogfood(mutable+SNAPSHOT 조합) 무영향이 스위트 통과로 증명된다.
- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "fix(validate): releasePath 닫힌 집합 + next-snapshot은 mutable qualifier 필수

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: validate — B-14 gitflow×maintenanceLines · B-15 movingMajorTag 가드 · B-16 scheme.pattern 필수

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`)
- Test: `tests/test_render_pipeline.py` (`PipelineTest`)

**Interfaces:** Task 1과 동일 (독립 규칙).

- [ ] **Step 1: 실패하는 테스트 4건 작성** — `PipelineTest`에 추가:

```python
    def test_gitflow_maintenance_lines_rejected(self):
        # manifest의 hotfix 이중 entry가 같은 목적지에 렌더 — gitflow flavor만
        # 남고 유지보수 라인 기대가 소리 없이 증발하는 조합
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["branching"] = "gitflow"
        cfg["repo"]["developBranch"] = "develop"
        cfg["repo"]["releasePath"] = "release-pr"
        cfg["repo"]["maintenanceLines"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("maintenanceLines", r.stderr)
        self.assertIn("gitflow", r.stderr)

    def test_moving_major_tag_requires_semver(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
        cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
        cfg["scopes"][0]["postRelease"] = {"bump": "none"}
        cfg["scopes"][0]["tag"]["movingMajorTag"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("movingMajorTag", r.stderr)
        self.assertIn("semver", r.stderr)

    def test_moving_major_tag_rejected_for_independent(self):
        # release-monorepo의 `git tag -f v<major>`는 scope 네임스페이스가 없어
        # 같은 major의 scope끼리 충돌한다
        cfg = monorepo_config()
        cfg["scopes"][0]["tag"]["movingMajorTag"] = True
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("movingMajorTag", r.stderr)
        self.assertIn("independent", r.stderr)

    def test_calver_headver_require_pattern(self):
        for scheme in ("calver", "headver"):
            cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
            cfg["scopes"][0]["scheme"] = {"type": scheme, "pattern": None}
            cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
            cfg["scopes"][0]["postRelease"] = {"bump": "none"}
            self.write_config(cfg)
            r = self.render()
            self.assertEqual(r.returncode, 1, scheme)
            self.assertIn("scheme.pattern", r.stderr)
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` → 신규 4건 FAIL.
- [ ] **Step 3: 구현** — B-14는 기존 maintenanceLines 규칙 블록(L206~214) 뒤에:

```python
    if repo.get("maintenanceLines") and repo.get("branching") == "gitflow":
        problems.append("repo.maintenanceLines is not supported with gitflow "
                        "branching — the gitflow production-hotfix flavor "
                        "replaces it (both would render to the same hotfix "
                        "skill path); use trunk branching for maintenance "
                        "lines")
```

B-15·B-16은 scheme 검사 루프(Task 1 Step 3의 B-2와 같은 루프) 안에:

```python
        if scheme_type in ("calver", "headver") and not (s.get("scheme") or {}).get("pattern"):
            problems.append("scopes[{}]: scheme.pattern is required for {} "
                            "(calver pattern / headver head number) — "
                            "next-version.py fails at release time without it"
                            .format(i, scheme_type))
        if (s.get("tag") or {}).get("movingMajorTag"):
            if (scheme_type or "semver") != "semver":
                problems.append("scopes[{}]: tag.movingMajorTag requires the "
                                "semver scheme (a moving v<major> tag is "
                                "meaningless for calver/headver)".format(i))
            if strategy == "independent":
                problems.append("scopes[{}]: tag.movingMajorTag is not "
                                "supported with the independent monorepo "
                                "strategy — the moving v<major> tag is not "
                                "scope-namespaced and would collide across "
                                "scopes".format(i))
```

- [ ] **Step 4: 통과 확인** — `python3 -m unittest discover -s tests -q` → 전부 OK (rc-library 골든: movingMajorTag+semver+단일 → 통과 유지 확인 포함).
- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "fix(validate): gitflow×maintenanceLines 거부, movingMajorTag semver·비independent 한정, calver/headver pattern 필수

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: validate — B-17 묶음 (scopes=1·유일성·perReleasePath·placeholder·닫힌 집합)

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`)
- Test: `tests/test_render_pipeline.py` (`PipelineTest`)

**Interfaces:** Task 1과 동일.

- [ ] **Step 1: 실패하는 테스트 6건 작성** — `PipelineTest`에 추가:

```python
    def test_multiple_scopes_require_independent(self):
        cfg = monorepo_config(strategy="fixed")  # 2 scopes + fixed
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("independent", r.stderr)

    def test_duplicate_scope_names_rejected(self):
        cfg = monorepo_config()
        cfg["scopes"][1]["name"] = cfg["scopes"][0]["name"]
        cfg["scopes"][1]["tag"]["format"] = "dup2@{version}"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unique", r.stderr)

    def test_duplicate_tag_formats_rejected(self):
        cfg = monorepo_config()
        cfg["scopes"][1]["tag"]["format"] = cfg["scopes"][0]["tag"]["format"]
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("tag.format", r.stderr)

    def test_release_file_requires_per_release_path(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["destinations"] = ["release-file"]
        cfg["scopes"][0]["notes"]["perReleasePath"] = None
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("perReleasePath", r.stderr)

    def test_release_commit_format_placeholders(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["releaseCommitFormat"] = "chore(release): {scope}@{version}"
        self.write_config(cfg)  # 단일 레포에 {scope}
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("{scope}", r.stderr)
        cfg["repo"]["releaseCommitFormat"] = "release commit"  # {version} 없음
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("{version}", r.stderr)

    def test_closed_sets_language_destinations_merge_policy(self):
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["scopes"][0]["notes"]["language"] = "jp"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("notes.language", r.stderr)
        cfg["scopes"][0]["notes"]["language"] = "ko"
        cfg["scopes"][0]["notes"]["destinations"] = []
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("destinations", r.stderr)
        cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
        cfg["repo"]["mergePolicy"] = "ff-only"
        self.write_config(cfg)
        r = self.render()
        self.assertEqual(r.returncode, 1)
        self.assertIn("mergePolicy", r.stderr)
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_render_pipeline -v; cd ..` → 신규 6건 FAIL. (`test_multiple_scopes_require_independent`은 `monorepo_config`의 `strategy` 인자를 쓴다 — helpers.py:139 시그니처 `monorepo_config(strategy="independent")` 확인됨.)
- [ ] **Step 3: 구현** — repo 수준 규칙은 `strategy` 관련 블록(L198~208) 근처에:

```python
    if strategy != "independent" and scopes and len(scopes) > 1:
        problems.append("multiple scopes require the independent monorepo "
                        "strategy — other configs use exactly one scope "
                        "(the rendered single-repo skills only see scopes[0])")
    names = [s.get("name") for s in scopes or [] if s.get("name")]
    if len(names) != len(set(names)):
        problems.append("scope names must be unique")
    tag_formats = [(s.get("tag") or {}).get("format") for s in scopes or []
                   if (s.get("tag") or {}).get("enabled")
                   and (s.get("tag") or {}).get("format")]
    if len(tag_formats) != len(set(tag_formats)):
        problems.append("tag.format must be unique across tag-enabled scopes "
                        "(a shared format cross-contaminates anchor "
                        "detection)")
    fmt = repo.get("releaseCommitFormat") or ""
    if fmt and "{version}" not in fmt:
        problems.append('repo.releaseCommitFormat must contain "{version}"')
    if "{scope}" in fmt and strategy != "independent":
        problems.append('repo.releaseCommitFormat: "{scope}" is only valid '
                        "with the independent monorepo strategy")
    merge_policy = repo.get("mergePolicy")
    if merge_policy not in ("merge", "squash", "rebase", "unknown"):
        problems.append('repo.mergePolicy must be "merge", "squash", "rebase" '
                        'or "unknown" (got "{}")'.format(merge_policy))
```

scope 수준 규칙은 notes destinations 루프(L248~262, `dests` 변수가 있는 루프) 안에:

```python
        if not dests:
            problems.append("scopes[{}]: notes.destinations must not be empty"
                            .format(i))
        if "release-file" in dests and not (s.get("notes") or {}).get("perReleasePath"):
            problems.append('scopes[{}]: notes destination "release-file" '
                            "requires notes.perReleasePath (an explicit null "
                            "drops release files into the repo root)".format(i))
        lang = (s.get("notes") or {}).get("language")
        if lang not in ("ko", "en", "both"):
            problems.append('scopes[{}]: notes.language must be "ko", "en" or '
                            '"both" (got "{}")'.format(i, lang))
```

- [ ] **Step 4: 통과 확인** — `python3 -m unittest discover -s tests -q` → 전부 OK. 특히 `test_dogfood_selfrender`(dogfood config가 신규 규칙 통과)와 골든 22종 전부 통과가 "합법 config 무영향"의 증명이다.
- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/test_render_pipeline.py
git commit -m "fix(validate): scope 수·이름·tag.format 유일성, perReleasePath 필수, releaseCommitFormat placeholder·닫힌 집합 검증

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 스크립트 가드 — B-3 regex 단일 매치 + B-4 build metadata 거부 (+docstring), 골든 churn 1회

**Files:**
- Modify: `skills/init/assets/scripts/version.py` (`read_location` L135~140, `set_location` L211~220)
- Modify: `skills/init/assets/scripts/next-version.py` (docstring L13, semver 절 L295 뒤)
- Test: `tests/test_version.py` (`RegexGuardTest`, L198), `tests/test_next_version.py` (`PureModeTest` — 기존 `test_build_metadata_dropped`를 **교체**)
- Regenerate: `tests/golden/*/expected/.superrelease/scripts/{version,next-version}.py` (verbatim 복사 21곳) + dogfood `.superrelease/scripts/`

**Interfaces:**
- Consumes: `fail(msg, code)` 헬퍼(양쪽 스크립트에 이미 존재), `SEMVER_RE`(그룹 5 = build metadata).
- Produces: regex 다중 매치 시 exit 1 (`... matched N times ...` 메시지), `+meta` 산술 입력 시 exit 1 (`build metadata ...` 메시지). **산술 결과는 전 케이스 불변** — 가드는 입력 검증만.

- [ ] **Step 1: 실패하는 테스트 작성 (version.py)** — `RegexGuardTest`(tests/test_version.py:198)에 추가:

```python
    def test_multi_match_get_exits_1(self):
        # set은 전 매치 치환·get/verify는 첫 매치만 읽던 비대칭 — 다중 매치는
        # Cargo [dependencies]·pyproject [tool.*] 라인을 조용히 오염시킨다
        toml = 'version = "1.2.3"\n\n[dependencies.demo]\nversion = "0.9.0"\n'
        repo = self.repo_with(
            [{"file": "Cargo.toml", "type": "regex",
              "pattern": '^version\\s*=\\s*"([^"]+)"'}],
            {"Cargo.toml": toml})
        r = run_script(vp(repo), "get")
        self.assertEqual(r.returncode, 1)
        self.assertIn("matched 2", r.stderr)

    def test_multi_match_set_exits_1_without_writing(self):
        toml = 'version = "1.2.3"\n\n[dependencies.demo]\nversion = "0.9.0"\n'
        repo = self.repo_with(
            [{"file": "Cargo.toml", "type": "regex",
              "pattern": '^version\\s*=\\s*"([^"]+)"'}],
            {"Cargo.toml": toml})
        r = run_script(vp(repo), "set", "1.2.4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("matched 2", r.stderr)
        self.assertEqual((Path(repo) / "Cargo.toml").read_text(encoding="utf-8"),
                         toml)
```

- [ ] **Step 2: 실패하는 테스트 작성 (next-version.py)** — `PureModeTest`의 기존 `test_build_metadata_dropped`(현재 드롭을 어서션)를 **삭제하고 교체**:

```python
    def test_build_metadata_rejected(self):
        # 커버리지 검토 G3 실측: 1.2.3+45 --bump patch가 stderr 0바이트로
        # 1.2.4를 내며 스토어 빌드번호를 조용히 소실시켰다 — 이제 거부한다
        for args in (["--current", "1.2.3+build.5", "--bump", "patch"],
                     ["--current", "1.2.3+45", "--release"],
                     ["--current", "1.2.3+45", "--qualifier", "SNAPSHOT"]):
            r = out(*args)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("build metadata", r.stderr)
```

- [ ] **Step 3: 실패 확인** — `cd tests && python3 -m unittest test_version test_next_version -v; cd ..` → 신규 3건 FAIL, 기존 PASS (교체한 dropped 테스트는 사라짐).
- [ ] **Step 4: version.py 구현** — `read_location`의 regex 분기, `if not matches: fail(...)` (L138~139) **바로 뒤**에:

```python
        if len(matches) > 1:
            fail(str(path) + ": pattern '" + loc["pattern"] + "' matched "
                 + str(len(matches)) + " times — ambiguous location; narrow "
                 "the pattern (anchor it or add surrounding context) so it "
                 "matches exactly once", 1)
```

`set_location`의 regex 분기, `if not matches: fail(...)` (L214~215) **바로 뒤**에도 동일 블록 삽입 (치환 루프 `for m in reversed(matches)`는 그대로 둔다 — 가드 후엔 원소 1개).

- [ ] **Step 5: next-version.py 구현** — semver 절의 `current = args.current if args.current else current_from_config(args.scope)` (L295) **바로 뒤**에:

```python
    m_meta = SEMVER_RE.match(current)
    if m_meta and m_meta.group(5):
        fail("build metadata is not preserved by semver arithmetic: " + current
             + " — capture the marketing version only (narrow the version "
             "location pattern so '+...' stays out of the captured value)", 1)
```

docstring L13 교체 — old: `Two input modes: --current VER (pure, config-free) or config mode, which reads` → new: `Three input modes: --current VER (pure, config-free), --current-among VER...` + 이어서 `(calver: highest pattern-matching candidate), or config mode, which reads` (문단 나머지는 유지).

- [ ] **Step 6: 단위 테스트 통과 확인** — `cd tests && python3 -m unittest test_version test_next_version -v; cd ..` → 전부 PASS. 이 시점에 `test_golden`·`test_dogfood_selfrender`는 **깨져 있는 게 정상**(verbatim 복사 stale).
- [ ] **Step 7: 골든 재생성 + dogfood 재렌더 (churn 1회)**

```bash
python3 tests/update_golden.py
python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-01-01T00:00:00+00:00
git status --porcelain tests/golden .superrelease
```

기대: 전 골든 트리(22종)의 `expected/.superrelease/scripts/version.py`·`next-version.py`만 M, dogfood `.superrelease/scripts/{version,next-version}.py`만 M. **그 외 파일(SKILL.md·템플릿 등)이 보이면 회귀 — 중단하고 원인 파악.**
- [ ] **Step 8: 전체 테스트** — `python3 -m unittest discover -s tests -q` → 전부 OK.
- [ ] **Step 9: 커밋**

```bash
git add skills/init/assets/scripts tests/test_version.py tests/test_next_version.py tests/golden .superrelease/scripts
git commit -m "fix(scripts): regex 다중 매치 거부(조용한 오염 차단) + semver 산술의 build metadata 거부(무경고 드롭 제거)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 골든 공백 채우기 — B-18 신규 9종

**Files:**
- Modify: `tests/golden_configs.py` (config 함수 9개 + `GOLDEN` 등록)
- Modify: `tests/test_golden.py` (content 어서션 클래스 추가)
- Modify: `skills/init/SKILL.md` (지원 범위 fixed×gitflow 문구 1곳)
- Create: `tests/golden/{trunk-monorepo-bundle,fragment-monorepo,release-file-monorepo,hotfix-release-pr,backfill-gitflow,gitflow-tagless-hotfix,gitflow-fixed-monorepo,python-library,maven-revision}/expected/**`

**Interfaces:**
- Consumes: `scope_config`/`monorepo_config`(tests/helpers.py), `GOLDEN` dict(tests/golden_configs.py:247), `GOLDEN_ROOT`(test_golden.py).
- Produces: 골든 이름 9종(위 Create 목록의 디렉터리명) — Task 6이 이 중 `gitflow-tagless-hotfix`를 재생성 대상으로 다룬다.

- [ ] **Step 1: config 함수 9개 추가** — `tests/golden_configs.py`의 `claude_plugin()` 뒤에:

```python
def trunk_monorepo_bundle():
    # trunk × independent × bundle — bundle 라운드 노트의 비-gitflow 경로 핀
    cfg = monorepo_config()
    cfg["bundle"] = {"enabled": True,
                     "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                     "notesPath": "docs/releases/"}
    return cfg


def fragment_monorepo():
    # independent × fragment(+changelog sink) — scope 경로 조각 취합 분기 핀
    cfg = monorepo_config()
    for s in cfg["scopes"]:
        s["notes"]["destinations"] = ["fragment", "changelog"]
    return cfg


def release_file_monorepo():
    # independent × release-file — scope별 릴리스 파일 경로 분기 핀
    cfg = monorepo_config()
    for s in cfg["scopes"]:
        s["notes"]["destinations"] = ["release-file", "github-release"]
    return cfg


def hotfix_release_pr():
    # maintenanceLines × release-pr — hotfix 스킬의 PR 경로(base=유지보수 라인) 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["repo"]["maintenanceLines"] = True
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def backfill_gitflow():
    # backfill × gitflow(단일) — 두 조건 분기의 공존 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["backfill"] = True
    return cfg


def gitflow_tagless_hotfix():
    # 단일 gitflow tagless — hotfix gitflow flavor의 태그 collapse(M5 T8b 수동
    # 검증분)를 회귀망에 편입
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["scopes"][0]["tag"] = {"enabled": False, "format": "v{version}",
                               "annotated": False, "signed": False,
                               "movingMajorTag": False}
    cfg["scopes"][0]["anchor"] = {"type": "ref", "value": None}
    cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
    cfg["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
    return cfg


def gitflow_fixed_monorepo():
    # fixed 모노레포 × gitflow — 단일 root scope라 단일 gitflow와 동일 렌더임을 핀
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"},
         {"file": "packages/a/package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = "fixed"
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def python_library():
    # pyproject regex + none/none — Python 라이브러리 대표 관행 핀 (scan 패턴 그대로)
    cfg = scope_config(
        [{"file": "pyproject.toml", "type": "regex",
          "pattern": "^version\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]"}])
    cfg["repo"]["kind"] = "library"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def maven_revision():
    # pom <revision> property regex — Maven CI-friendly 관행 핀 (scan 패턴 그대로)
    cfg = scope_config(
        [{"file": "pom.xml", "type": "regex",
          "pattern": "<revision>([^<]+)</revision>"}])
    return cfg
```

`GOLDEN` dict에 9개 항목 추가 (함수명을 하이픈 이름으로):

```python
          "trunk-monorepo-bundle": trunk_monorepo_bundle,
          "fragment-monorepo": fragment_monorepo,
          "release-file-monorepo": release_file_monorepo,
          "hotfix-release-pr": hotfix_release_pr,
          "backfill-gitflow": backfill_gitflow,
          "gitflow-tagless-hotfix": gitflow_tagless_hotfix,
          "gitflow-fixed-monorepo": gitflow_fixed_monorepo,
          "python-library": python_library,
          "maven-revision": maven_revision,
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_golden -v; cd ..` → 신규 9종이 "golden missing — run: python3 tests/update_golden.py"로 FAIL.
- [ ] **Step 3: 골든 생성** — `python3 tests/update_golden.py` → `git status --porcelain tests/golden` 기대: **신규 9 트리 추가(`??` 또는 A)만, 기존 트리 M 없음.** 기존 트리가 바뀌면 회귀 — 중단.
- [ ] **Step 4: content 어서션 추가** — `tests/test_golden.py`에 클래스 추가:

```python
class GoldenContentTest(unittest.TestCase):
    """스냅샷 동일성 위에, 신규 골든의 의도(핵심 분기)를 명시적으로 고정한다."""

    def read(self, name, rel):
        return (GOLDEN_ROOT / name / "expected" / rel).read_text(encoding="utf-8")

    def test_gitflow_tagless_hotfix_collapses_tag_section(self):
        skill = self.read("gitflow-tagless-hotfix", ".claude/skills/hotfix/SKILL.md")
        self.assertNotIn("## 6. 태그", skill)

    def test_trunk_monorepo_bundle_renders_round_notes(self):
        skill = self.read("trunk-monorepo-bundle", ".claude/skills/release/SKILL.md")
        self.assertIn("bundle 라운드 노트", skill)
        self.assertIn("--current-among", skill)

    def test_hotfix_release_pr_uses_maintenance_base(self):
        skill = self.read("hotfix-release-pr", ".claude/skills/hotfix/SKILL.md")
        self.assertIn("release/<라인>", skill)

    def test_gitflow_fixed_monorepo_renders_single_flavor(self):
        skill = self.read("gitflow-fixed-monorepo", ".claude/skills/release/SKILL.md")
        self.assertIn("## 7. 태그", skill)  # 단일 flavor 섹션 번호 (모노레포는 ## 8)
```

- [ ] **Step 5: 지원 범위 문구 확정 (fixed×gitflow)** — `skills/init/SKILL.md` L142의 old: `단일 레포·independent 모노레포 지원, gitflow에서는 태그가 선택사항` → new: `단일 레포·independent 모노레포 지원(fixed 모노레포는 단일 root scope라 단일 레포와 동일 사이클로 동작), gitflow에서는 태그가 선택사항`. 이는 검증된 기존 동작의 명문화다(신규 지원 약속 아님 — 골든이 핀).
- [ ] **Step 6: 전체 테스트** — `python3 -m unittest discover -s tests -q` → 전부 OK.
- [ ] **Step 7: 커밋**

```bash
git add tests/golden_configs.py tests/test_golden.py tests/golden skills/init/SKILL.md
git commit -m "test(golden): 조합 공백 9종 핀 — trunk bundle·모노레포 fragment/release-file·hotfix PR·backfill gitflow·tagless hotfix·fixed gitflow·python·maven

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: B-36 — 혼합태그 프로즈 게이트 (`derived.allTagEnabled`)

**Files:**
- Modify: `skills/init/scripts/render.py` (`build_context`, L360~371)
- Modify: `skills/init/assets/skills/release-monorepo/SKILL.md` (§7 프리뷰 L73, §8 L80~82, 실패 시 L~97)
- Modify: `skills/init/assets/skills/release/SKILL.md` (§6 프리뷰 L68, 실패 시 L104)
- Modify: `skills/init/assets/skills/hotfix/SKILL.md` (§5 프리뷰 L46, 실패 시 L66)
- Modify: `tests/golden_configs.py` + `tests/test_golden.py` (mixed 골든 1종 + 어서션)
- Regenerate: `tests/golden/{tagless-app,gitflow-monorepo-bundle,gitflow-tagless-hotfix}/expected/**` + 신규 `mixed-tags-monorepo`

**Interfaces:**
- Consumes: `ctx["derived"]` dict(render.py L368), 동결 dialect `{{#if}}`/`{{#unless}}`.
- Produces: 템플릿 컨텍스트 키 `derived.allTagEnabled` (모든 scope의 tag.enabled가 참일 때 true).

- [ ] **Step 1: 실패하는 테스트 작성 (derived 값)** — `PipelineTest`(test_render_pipeline.py)의 `ASSET_FILES` 중 `skills/release/SKILL.md` 값 끝에 `"{{#unless derived.allTagEnabled}}MIXED\n{{/unless}}"`를 덧붙이고(합성 미니 asset — 실제 asset 아님), 테스트 추가:

```python
    def test_derived_all_tag_enabled(self):
        r = self.render()  # 단일 tagged scope → all=true → MIXED 미출력
        self.assertEqual(r.returncode, 0, r.stderr)
        skill = (self.repo / ".claude/skills/release/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("MIXED", skill)
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_render_pipeline.PipelineTest.test_derived_all_tag_enabled -v; cd ..` → FAIL. 실패 양상은 엔진의 미정의 키 처리에 따라 두 갈래다: (a) unknown placeholder로 returncode 1, 또는 (b) 미정의 키가 falsy로 처리돼 MIXED가 렌더됨 — 어느 쪽이든 이 테스트는 실패한다. (합성 asset 변경이 같은 클래스의 다른 테스트를 일시적으로 깨뜨릴 수 있으니 이 단계에서는 단일 테스트만 실행.)
- [ ] **Step 3: build_context 구현** — render.py L368~370 old:

```python
    ctx["derived"] = {"anyTagEnabled": any(
        (s.get("tag") or {}).get("enabled")
        for s in config.get("scopes") or [])}
```

new:

```python
    scopes_list = config.get("scopes") or []
    ctx["derived"] = {
        "anyTagEnabled": any((s.get("tag") or {}).get("enabled") for s in scopes_list),
        "allTagEnabled": bool(scopes_list) and all(
            (s.get("tag") or {}).get("enabled") for s in scopes_list),
    }
```

- [ ] **Step 4: 프로즈 게이트 6곳** — 각 old→new (문자열은 파일에서 정확 확인 후 치환):
  1. release-monorepo §8(L82 `- 태그명: 그 scope의...` 라인 **앞**)에 삽입: `{{#unless derived.allTagEnabled}}- 태그를 쓰지 않는 scope(config \`tag.enabled\` false)는 이 단계 전체를 건너뛴다 — 아래 항목은 tag.enabled scope에만 적용된다.\n{{/unless}}` (개행이 블록 안 — all-tagged 골든 0바이트 collapse).
  2. release-monorepo §7 프리뷰 L73: `와 태그명(그 scope의 config \`tag.format\` — 네임스페이스는 포맷에 포함, 예: \`my-pkg@1.2.0\`)` → `{{#if derived.anyTagEnabled}}와 태그명(그 scope의 config \`tag.format\` — 네임스페이스는 포맷에 포함, 예: \`my-pkg@1.2.0\`){{/if}}`
  3. release-monorepo 실패 시: `(파일 수정 / 커밋 / push / 태그 / Release)` → `(파일 수정 / 커밋 / push{{#if derived.anyTagEnabled}} / 태그{{/if}} / Release)` 그리고 `**push된 태그는 되돌리지 않는다** — ` → `{{#if derived.anyTagEnabled}}**push된 태그는 되돌리지 않는다** — {{/if}}`
  4. release §6 프리뷰 L68: `의 {version} 치환)와 태그명` → `의 {version} 치환){{#if scope.tag.enabled}}와 태그명{{/if}}`
  5. release 실패 시 L104: 3번과 동일 패턴(단 게이트는 `scope.tag.enabled`).
  6. hotfix §5 프리뷰 L46: `·커밋 메시지·태그명·명령 목록` → `·커밋 메시지{{#if derived.anyTagEnabled}}·태그명{{/if}}·명령 목록` / hotfix 실패 시 L66: 3번과 동일 패턴(`derived.anyTagEnabled`).
- [ ] **Step 5: mixed 골든 추가** — `tests/golden_configs.py`:

```python
def mixed_tags_monorepo():
    # independent 혼합 태그(a=tagged, b=tagless) — §8 per-scope skip 안내 핀
    cfg = monorepo_config()
    cfg["scopes"][1]["tag"] = {"enabled": False, "format": "b@{version}",
                               "annotated": False, "signed": False,
                               "movingMajorTag": False}
    cfg["scopes"][1]["anchor"] = {"type": "ref", "value": None}
    for s in cfg["scopes"]:
        s["notes"]["destinations"] = ["changelog"]
    cfg["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
    return cfg
```

`GOLDEN`에 `"mixed-tags-monorepo": mixed_tags_monorepo,` 추가. `GoldenContentTest`에 어서션:

```python
    def test_mixed_tags_monorepo_notes_per_scope_skip(self):
        skill = self.read("mixed-tags-monorepo", ".claude/skills/release/SKILL.md")
        self.assertIn("태그를 쓰지 않는 scope", skill)
```

- [ ] **Step 6: 재생성 + 범위 검증** — `python3 tests/update_golden.py && git status --porcelain tests/golden` 기대: **신규 mixed-tags-monorepo 트리 + tagless 3종(tagless-app, gitflow-monorepo-bundle, gitflow-tagless-hotfix)의 SKILL.md만 M.** tagged 골든(gradle-app·pnpm-monorepo 등)이 M으로 나오면 바이트 불변 위반 — `{{#if}}` 개행 위치를 재점검하라.
- [ ] **Step 7: dogfood 재렌더** — Global Constraints의 재렌더 명령 실행. dogfood는 tagged 단일이라 기대 diff 없음(`git status --porcelain .superrelease .claude` 빈 출력). diff가 나오면 tagged 경로 프로즈가 변한 것 — Step 4를 재점검.
- [ ] **Step 8: 전체 테스트 + 줄수 확인** — `python3 -m unittest discover -s tests -q` → OK. `wc -l skills/init/assets/skills/{release,release-monorepo,hotfix}/SKILL.md` → 전부 ≤150.
- [ ] **Step 9: 커밋**

```bash
git add skills/init/scripts/render.py skills/init/assets/skills tests/golden_configs.py tests/test_golden.py tests/test_render_pipeline.py tests/golden
git commit -m "fix(assets): 혼합태그 모노레포 프로즈 게이트 — derived.allTagEnabled, §8 per-scope skip 안내, 태그명·실패 시 tagless 게이트

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 프로즈 정확성 2건 — init gitflow 태그 문구 + bundleNotesGuess 오탐

**Files:**
- Modify: `skills/init/SKILL.md` (L53 번들 6, L142 지원 범위 — 골든 무관, 플러그인 소스)
- Modify: `skills/init/scripts/scan.py` (L45 `BUNDLE_NOTE_RE`)
- Test: `tests/test_scan.py`

**Interfaces:** 없음 (문구·휴리스틱 정리).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_scan.py`의 기존 테스트 클래스에 추가 (이 파일의 기존 import 방식대로 scan 모듈을 로드해 사용 — 모듈 로드가 없다면 `from helpers import PLUGIN_SCRIPTS, load_module` 후 `scan = load_module(PLUGIN_SCRIPTS / "scan.py", "scan_module")`):

```python
    def test_bundle_note_re_requires_dot_separated_groups(self):
        # ^\d{4}[.\d]+$ 는 순수 8자리(20260101)도 매치했다 — 점 구분 필수로 조인다
        scan = load_module(PLUGIN_SCRIPTS / "scan.py", "scan_module")
        self.assertIsNotNone(scan.BUNDLE_NOTE_RE.match("2026.07.1"))
        self.assertIsNotNone(scan.BUNDLE_NOTE_RE.match("2026.07"))
        self.assertIsNone(scan.BUNDLE_NOTE_RE.match("20260101"))
        self.assertIsNone(scan.BUNDLE_NOTE_RE.match("2026"))
```

- [ ] **Step 2: 실패 확인** — `cd tests && python3 -m unittest test_scan -v; cd ..` → `20260101` 매치로 FAIL.
- [ ] **Step 3: 구현** — scan.py L45 old: `BUNDLE_NOTE_RE = re.compile(r"^\d{4}[.\d]+$")` → new: `BUNDLE_NOTE_RE = re.compile(r"^\d{4}(?:\.\d+)+$")`.
- [ ] **Step 4: init 프로즈 2곳** —
  1. L53 old: `릴리스 사이클(develop에서 cut → PR to 기본 브랜치 → 머지 후 태그 → develop back-merge·SNAPSHOT 복귀)을 안내하라` → new: `릴리스 사이클(develop에서 cut → PR to 기본 브랜치 → 머지 후 태그(사용 시) → develop back-merge·SNAPSHOT 복귀)을 안내하라`
  2. L142 old: `gitflow(release-pr 전용 — develop cut → 기본 브랜치 태그 → back-merge 정식 사이클` → new: `gitflow(release-pr 전용 — develop cut → 기본 브랜치 머지·태그(사용 시) → back-merge 정식 사이클`
- [ ] **Step 5: 통과 확인** — `python3 -m unittest discover -s tests -q` → 전부 OK (init SKILL.md는 렌더 대상 아님 — 골든 무영향).
- [ ] **Step 6: 커밋**

```bash
git add skills/init/SKILL.md skills/init/scripts/scan.py tests/test_scan.py
git commit -m "docs(init): gitflow 태그 프로즈 '(사용 시)' 한정 + fix(scan): bundleNotesGuess 8자리 오탐 조임

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 최종 검증 + 랜딩 준비

**Files:** 변경 없음 (검증 전용 — 실패 시 해당 Task로 돌아가 수정).

- [ ] **Step 1: 전체 게이트**

```bash
python3 -m unittest discover -s tests -q
claude plugin validate . --strict
git status --porcelain tests/golden
```

기대: 테스트 전부 OK(기존 266+신규 ~20) · validate 통과 · 골든 워킹트리 clean.
- [ ] **Step 2: 스펙 §10 완료 기준 대조** — 6항 각각을 커밋·테스트 이름으로 확인해 체크리스트로 기록: ① 재현 config 역테스트(Task 1) ② 규칙별 거부/무영향 쌍(Task 1~3) ③ 스크립트 가드 고정+산술 불변(Task 4) ④ 골든 신규 9+1종·churn 1회(Task 4~6) ⑤ 전체 게이트(Step 1) ⑥ v0.4.0 출하·[Unreleased] 소진(Task 0).
- [ ] **Step 3: CHANGELOG [Unreleased] 기입** — v0.4.0 릴리스로 비워진 `[Unreleased]`에 M6 변경 요약 추가 (Added: validate 규칙 강화·golden 확대 / Fixed: regex 다중 매치·build metadata 가드 / Changed: 혼합태그 프로즈). 커밋: `docs: M6 변경분 CHANGELOG 기입`.
- [ ] **Step 4: 랜딩** — push 후 PR 생성은 메인 세션에서 (gh 계정 전환 절차 — Task 0 Step 3과 동일). PR 본문은 한국어, 스펙·플랜 링크 포함.

---

## Self-Review 결과 (플랜 작성 시 수행)

- **스펙 커버리지**: §3→Task 0, §4→Task 1, §5→Task 2·3, §6→Task 4, §7→Task 5, §8→Task 6, §9→Task 7(+docstring은 Task 4 편승), §10→Task 8. 전 섹션 매핑 확인.
- **B-2·B-16·B-15 규칙과 기존 골든 22종 전수 대조 완료** — helpers 기본값(mutable+SNAPSHOT), rc-library(movingMajorTag+semver+단일), calver/headver(pattern 있음), fixed-monorepo(단일 scope), 모노레포 태그 포맷 유일 — 전부 통과 유지.
- **주의 승계**: `test_alternation_single_group_replaces_participating_matches`(test_version.py:226)는 참여 매치 1개 케이스라 B-3 가드와 공존한다 — 가드는 참여 매치 수 기준.
