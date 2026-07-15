# superrelease dogfooding 후속 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans로 태스크별 구현. 각 태스크는 green으로 끝난다(asset 변경 태스크는 자체 재렌더 포함). 스텝은 `- [ ]` 체크박스.

**Goal:** v0.1.0 dogfooding이 짚은 마찰 3건(scan plugin.json 미감지 · release 스킬 squash 문구 하드코딩 · version.py json-path 재포맷)을 수정하고, superrelease 자기 툴킷을 재렌더해 dogfood 루프를 닫는다.

**Architecture:** #1 scan.py 후보 추가 + superrelease config marketplace 2차 sync · #2 release 템플릿 mergePolicy 반영 + 신규 골든 · #3 version.py surgical json-path write. #2·#3 asset 변경은 self-render 테스트가 재렌더를 강제한다.

**Tech Stack:** Python 3.9+ 표준 라이브러리(scan.py·version.py·render.py·unittest), git.

## Global Constraints

- **동결 dialect** — #2는 기존 `{{#if x == "lit"}}/{{else}}` 중첩만 사용. 새 문법 금지.
- **바이트 불변** — #2 변경은 인라인 조건(개행 추가 없음). 기존 20골든은 전부 mergePolicy squash → "squash 머지로" 바이트 불변. `git status --porcelain tests/golden`에 **`release-pr-merge/`만** 신규.
- **스크립트 무의존** — version.py는 stdlib만(`re` 이미 import). exit 0/1/2 유지.
- **엔진 불변** — render.py 엔진·산술 미변경. #1은 scan.py, #3은 version.py 스크립트 로직.
- **자립성·결정론** — 생성 툴킷은 상대경로만. self-render는 `superrelease`명 디렉터리 + `GIT_CEILING_DIRECTORIES`.
- **테스트** — 루트 `python3 -m unittest discover -s tests -q`. 단일 `cd tests && python3 -m unittest <mod> -v; cd ..`.
- **재렌더** — `python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-07-16T00:00:00+00:00` (마커 present → "update", --force 불필요).
- **검증** — 랜딩 전 `claude plugin validate . --strict` PASS.
- **커밋** — Conventional Commits, 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## File Structure

- Modify: `skills/init/scripts/scan.py` (#1 감지), `skills/init/SKILL.md` (line 142 목록), `.superrelease/config.json` (#1 marketplace 2차 location)
- Modify: `skills/init/assets/scripts/version.py` (#3 surgical) → 재렌더로 `.superrelease/scripts/version.py` 갱신
- Modify: `skills/init/assets/skills/release/SKILL.md` (#2) → 재렌더로 `.claude/skills/release/SKILL.md` 갱신
- Modify: `tests/golden_configs.py` (release_pr_merge) → `tests/golden/release-pr-merge/expected/**` 생성
- Modify: `tests/test_scan.py`, `tests/test_version.py` (신규 케이스)

---

## Task 1: #1 scan plugin.json 감지 + init 목록 + superrelease config marketplace sync

**Files:**
- Modify: `skills/init/scripts/scan.py`, `skills/init/SKILL.md`, `.superrelease/config.json`
- Test: `tests/test_scan.py`

**Interfaces:**
- Produces: scan `versionCandidates`에 `.claude-plugin/plugin.json` json-path `version` 후보(usable).

- [ ] **Step 1: scan 감지 테스트 작성** — `tests/test_scan.py`에 추가(openapi 테스트 근처, `_candidates_by_file` 헬퍼 사용):

```python
    def test_claude_plugin_manifest_is_json_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={".claude-plugin/plugin.json":
                       '{"name": "demo", "version": "1.3.0"}\n'},
                commits=["chore: init"])
            cand = self._candidates_by_file(repo)[".claude-plugin/plugin.json"]
            self.assertEqual(cand["type"], "json-path")
            self.assertEqual(cand["path"], "version")
            self.assertEqual(cand["value"], "1.3.0")
            self.assertNotIn("usable", cand)  # usable 후보는 키를 생략(package.json·openapi와 동일)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v -k plugin_manifest; cd ..`
Expected: FAIL — `KeyError: '.claude-plugin/plugin.json'`(아직 미감지).

- [ ] **Step 3: scan.py에 감지 추가** — `package.json` 블록(현 lines 144–151) **직후**에:

```python
    text = read(repo / ".claude-plugin" / "plugin.json")
    if text:
        try:
            v = json.loads(text).get("version")
            if isinstance(v, str):
                add(".claude-plugin/plugin.json", "json-path", v, path="version")
        except json.JSONDecodeError:
            pass
```

- [ ] **Step 4: 테스트 통과**

Run: `cd tests && python3 -m unittest test_scan -v -k plugin_manifest; cd ..`
Expected: PASS.

- [ ] **Step 5: init SKILL.md 목록 갱신** — line 142 스캔 감지 목록에 `.claude-plugin/plugin.json`을 pom 뒤에 추가:

`… / pom.xml(\`<revision>\` property는 후보, project \`<version>\`은 감지·안내 전용) / .claude-plugin/plugin.json(Claude Code 플러그인 매니페스트 — json-path \`version\`) + node·gradle 모노레포 패키지 …`

- [ ] **Step 6: superrelease config에 marketplace 2차 location** — `.superrelease/config.json`의 scope `versionLocations` 배열에 2번째 요소 추가:

```json
      "versionLocations": [
        {"file": ".claude-plugin/plugin.json", "type": "json-path", "path": "version"},
        {"file": ".claude-plugin/marketplace.json", "type": "json-path", "path": "metadata.version"}
      ],
```

- [ ] **Step 7: verify + 전체 스위트** — config가 두 위치를 일치로 보는지 + self-render(config 유효) 유지:

Run: `python3 .superrelease/scripts/version.py verify`
Expected: exit 0 — `.claude-plugin/plugin.json: 0.1.0` + `.claude-plugin/marketplace.json: 0.1.0` 일치.
Run: `python3 -m unittest discover -s tests -q`
Expected: OK (243 = 242 + scan 1). self-render 그린(versionLocations는 렌더 산출물에 무영향).

- [ ] **Step 8: 커밋**

```bash
git add skills/init/scripts/scan.py skills/init/SKILL.md tests/test_scan.py .superrelease/config.json
git commit -m "$(printf 'feat: scan이 .claude-plugin/plugin.json을 버전 소스로 감지 (#1)\n\nsuperrelease config에 marketplace.json 2차 sync location 추가.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 2: #3 version.py surgical json-path write + 재렌더

**Files:**
- Modify: `skills/init/assets/scripts/version.py`
- Test: `tests/test_version.py`
- 재렌더: `.superrelease/scripts/version.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_version.py`에 fixture + 3케이스 추가:

```python
PLUGIN_INLINE = (
    '{\n'
    '  "name": "demo",\n'
    '  "version": "0.1.0",\n'
    '  "author": { "name": "A", "email": "a@x" },\n'
    '  "keywords": ["a", "b", "c"]\n'
    '}\n')


class JsonPathSurgicalTest(VersionTestBase):
    def test_inline_structures_preserved(self):
        repo = self.repo_with(
            [{"file": "plugin.json", "type": "json-path", "path": "version"}],
            {"plugin.json": PLUGIN_INLINE})
        run_script(vp(repo), "set", "0.2.0")
        expected = PLUGIN_INLINE.replace('"version": "0.1.0"', '"version": "0.2.0"')
        self.assertEqual((Path(repo) / "plugin.json").read_text(encoding="utf-8"), expected)

    def test_noop_leaves_file_untouched(self):
        repo = self.repo_with(
            [{"file": "plugin.json", "type": "json-path", "path": "version"}],
            {"plugin.json": PLUGIN_INLINE})
        r = run_script(vp(repo), "set", "0.1.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((Path(repo) / "plugin.json").read_text(encoding="utf-8"), PLUGIN_INLINE)

    def test_ambiguous_match_falls_back_with_correct_value(self):
        fixture = ('{\n  "version": "1.0.0",\n  "meta": { "version": "1.0.0" }\n}\n')
        repo = self.repo_with(
            [{"file": "f.json", "type": "json-path", "path": "meta.version"}],
            {"f.json": fixture})
        run_script(vp(repo), "set", "2.0.0")
        obj = json.loads((Path(repo) / "f.json").read_text(encoding="utf-8"))
        self.assertEqual(obj["meta"]["version"], "2.0.0")   # 대상만
        self.assertEqual(obj["version"], "1.0.0")           # 최상위 불변(값 정확)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_version.JsonPathSurgicalTest -v; cd ..`
Expected: `test_inline_structures_preserved`·`test_noop_leaves_file_untouched` FAIL(현 dump_json_like가 author·keywords 멀티라인 전개). `test_ambiguous…`는 통과(dump가 이미 올바른 값).

- [ ] **Step 3: version.py surgical 구현** — `set_location`의 json-path 분기(현 lines 182–196)를 교체:

```python
    if t == "json-path":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            fail(str(path) + ": invalid JSON: " + str(e), 1)
        old = json_path_get(obj, loc["path"], path)
        if old == new_version:
            return old  # no-op: leave the file untouched
        key = loc["path"].split(".")[-1]
        vpat = re.compile('("' + re.escape(key) + r'"\s*:\s*")' + re.escape(old) + '(")')
        if len(vpat.findall(text)) == 1:
            text = vpat.sub(lambda m: m.group(1) + new_version + m.group(2), text, count=1)
            write_text_preserving(path, text, crlf)
        else:
            cur = obj
            parts = loc["path"].split(".")
            for part in parts[:-1]:
                cur = cur[part]
            cur[parts[-1]] = new_version
            write_text_preserving(path, dump_json_like(text, obj), crlf)
        if path.name == "package.json":
            sync_package_lock(path, new_version)
        return old
```

- [ ] **Step 4: 테스트 통과 + 기존 json-path 회귀 없음**

Run: `cd tests && python3 -m unittest test_version -v; cd ..`
Expected: 신규 3케이스 PASS + 기존(package.json·roundtrip·package-lock) 계속 PASS.

- [ ] **Step 5: 재렌더(dogfood 루프)** — asset version.py 변경을 커밋 툴킷에 반영:

Run: `python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-07-16T00:00:00+00:00`
Expected: `.superrelease/scripts/version.py` update(release SKILL 등은 unchanged).

- [ ] **Step 6: 전체 스위트(self-render 그린)**

Run: `python3 -m unittest discover -s tests -q`
Expected: OK (246 = 243 + version 3). self-render 그린(커밋 version.py == 재렌더).

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/scripts/version.py .superrelease/scripts/version.py tests/test_version.py
git commit -m "$(printf 'fix: version.py json-path set을 surgical로 — inline JSON 보존·no-op 무변경 (#3)\n\ndump_json_like 전체 재직렬화 대신 유일 매치 값만 치환(애매하면 폴백).\nsuperrelease 툴킷 재렌더 반영.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 3: #2 release 스킬 mergePolicy 반영 + release-pr-merge 골든 + 재렌더

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md`, `tests/golden_configs.py`
- 생성: `tests/golden/release-pr-merge/expected/**`
- 재렌더: `.claude/skills/release/SKILL.md`

- [ ] **Step 1: release/SKILL.md line 79 수정** — 비-gitflow(else) 분기가 mergePolicy를 반영하도록:

기존: `…sha가 바뀐다({{#if repo.branching == "gitflow"}}머지 커밋으로{{else}}squash 머지로{{/if}} sha가…`
→ 수정: `{{else}}` 다음의 `squash 머지로`를 `{{#if repo.mergePolicy == "squash"}}squash 머지로{{else}}머지 커밋으로{{/if}}`로 교체(전체: `{{#if repo.branching == "gitflow"}}머지 커밋으로{{else}}{{#if repo.mergePolicy == "squash"}}squash 머지로{{else}}머지 커밋으로{{/if}}{{/if}}`).

- [ ] **Step 2: release_pr_merge 골든 config 추가** — `tests/golden_configs.py`에 함수 추가 + `GOLDEN` 등록:

```python
def release_pr_merge():
    # release-pr + mergePolicy merge (비-gitflow, 단일 레포) — §6 resume "머지 커밋으로" 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg
```

`GOLDEN` 딕셔너리에 `"release-pr-merge": release_pr_merge` 추가.

- [ ] **Step 3: 골든 생성 + 범위 확인**

Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden`
Expected: **`tests/golden/release-pr-merge/expected/**`만 신규(??)**. 기존 20트리 수정 0건(전부 squash라 바이트 불변). 그 외가 보이면 회귀 — 조사.

- [ ] **Step 4: release-pr-merge 골든이 "머지 커밋으로" 담는지 확인**

Run: `grep -c '머지 커밋으로' tests/golden/release-pr-merge/expected/.claude/skills/release/SKILL.md`
Expected: ≥1 (비-gitflow인데 merge 정책이라 §6 resume이 "머지 커밋으로").
Run: `grep -c 'squash 머지로' tests/golden/release-pr-app/expected/.claude/skills/release/SKILL.md`
Expected: ≥1 (squash 골든은 불변).

- [ ] **Step 5: 재렌더(dogfood 루프)** — release SKILL asset 변경을 커밋 툴킷에 반영(superrelease는 mergePolicy=merge):

Run: `python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-07-16T00:00:00+00:00`
Run: `grep -c '머지 커밋으로' .claude/skills/release/SKILL.md`
Expected: `.claude/skills/release/SKILL.md` update, "머지 커밋으로" 포함(우리 툴킷도 개선됨).

- [ ] **Step 6: 전체 스위트 + validate**

Run: `python3 -m unittest discover -s tests -q`
Expected: OK (247 = 246 + golden 1 subTest). self-render 그린(커밋 release SKILL == 재렌더).
Run: `claude plugin validate . --strict`
Expected: PASS.

- [ ] **Step 7: 커밋**

```bash
git add skills/init/assets/skills/release/SKILL.md .claude/skills/release/SKILL.md tests/golden_configs.py tests/golden/release-pr-merge
git commit -m "$(printf 'fix: release 스킬 resume 문구를 mergePolicy 반영으로 (#2)\n\n비-gitflow release-pr resume이 squash 하드코딩 대신 mergePolicy 분기.\n골든 release-pr-merge 신설 + superrelease 툴킷 재렌더(머지 커밋으로).\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 4: 최종 검증 + friction 백로그 갱신

- [ ] **Step 1: 전체 검증**

Run: `python3 -m unittest discover -s tests -q` → OK (247).
Run: `claude plugin validate . --strict` → PASS.
Run: `git status --porcelain tests/golden` → `release-pr-merge`만.
Run: `cd tests && python3 -m unittest test_dogfood_selfrender -q; cd ..` → OK (재렌더 반영).

- [ ] **Step 2: friction 원장 갱신** — `.superpowers/sdd/progress.md`에 3건 해소 기록(dogfood 후속 완료: #1 scan+config, #2 release+골든, #3 version.py surgical).

- [ ] **Step 3: 커밋(문서/원장은 git-ignored라 커밋 대상 아님 — 필요 시 스펙 §후속만)** — 원장은 git-ignored이므로 커밋 없음. 브랜치는 랜딩(별도)으로 PR.

---

## Self-Review

**1. 스펙 커버리지:** #1(Task 1 scan+init+config) · #2(Task 3 template+golden+재렌더) · #3(Task 2 version.py+재렌더) · dogfood 루프(Task 2·3 재렌더) · 검증/백로그(Task 4). 스펙 전 항목 매핑.

**2. Placeholder 스캔:** 코드·명령·edit 모두 실값. TODO 없음.

**3. 타입/이름 일관성:** scan `add(file, type, value, **kw)` 시그니처 준수 · 테스트는 `_candidates_by_file`/`repo_with`/`vp`/`run_script` 실제 헬퍼 · golden 함수는 `scope_config` 스키마 · version.py surgical은 기존 `json_path_get`/`dump_json_like`/`write_text_preserving`/`re` 재사용. 각 태스크 green(asset 변경은 자체 재렌더).

**리스크:** ① Task 2·3 재렌더 누락 시 self-render red — 각 태스크 Step에 재렌더 포함. ② #2 골든 범위 회귀는 Step 3 `git status tests/golden`가 수용 기준. ③ #3 애매 매치는 폴백 테스트로 커버.
