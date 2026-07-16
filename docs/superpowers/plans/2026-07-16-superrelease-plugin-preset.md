# superrelease Level 2 플러그인 프리셋 구현 계획

> **For agentic workers:** 인라인 실행. 각 태스크는 green으로 끝난다. 스텝은 `- [ ]` 체크박스.

**Goal:** init이 Claude Code 플러그인 레포를 인식(scan `pluginManifest`)하고 프리셋(+self-listed marketplace sync)을 추천하도록 하며, `claude-plugin` 골든으로 프리셋 render를 핀한다.

**Architecture:** scan.py에 `pluginManifest` 신호 추가(render 무관) → init SKILL.md prose가 이를 읽어 프리셋 추천 → golden_configs에 `claude-plugin` 등록.

**Tech Stack:** Python 3.9+ 표준 라이브러리(scan.py·unittest·render.py), git.

## Global Constraints

- **scan 무의존·읽기 전용** — `pluginManifest`는 플러그인 아니면 `null`. report 키 추가는 기존 scan 테스트에 무영향(전체 키셋 assert 없음).
- **render 무관** — scan 신호는 config 기반 render에 영향 없음 → 기존 골든 바이트 불변. 신규 골든 `claude-plugin`만 update_golden으로 추가.
- **init prose** — ≤500줄·한국어. 렌더/골든/unittest 직접 대상 아님(사람 검수).
- **엔진 불변** — render.py·validate_config 미변경.
- **테스트** — 루트 `python3 -m unittest discover -s tests -q`. 단일 `cd tests && python3 -m unittest <mod> -v; cd ..`.
- **검증** — `claude plugin validate . --strict` PASS. `git status --porcelain tests/golden`에 `claude-plugin`만.
- **커밋** — Conventional Commits, 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## File Structure

- Modify: `skills/init/scripts/scan.py` (scan_plugin_manifest + report 키)
- Modify: `skills/init/SKILL.md` (번들 1·2 플러그인 절)
- Modify: `tests/golden_configs.py` (claude_plugin + GOLDEN 등록)
- Create: `tests/golden/claude-plugin/expected/**`
- Modify: `tests/test_scan.py` (4 케이스)

---

## Task 1: scan `pluginManifest` 신호 + 테스트 (TDD)

**Files:**
- Modify: `skills/init/scripts/scan.py`
- Test: `tests/test_scan.py`

- [ ] **Step 1: 실패 테스트 4종** — `tests/test_scan.py`에 추가(ScanTest 클래스, 임의 위치). 각 테스트는 전체 report를 파싱:

```python
    def test_plugin_manifest_detected_plugin_json_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertEqual(pm["detected"], True)
            self.assertEqual(pm["version"], "1.3.0")
            self.assertNotIn("marketplaceVersion", pm)

    def test_plugin_manifest_marketplace_self_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={
                    ".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n',
                    ".claude-plugin/marketplace.json":
                        '{"name": "demo", "metadata": {"version": "1.3.0"},'
                        ' "plugins": [{"name": "demo", "source": "./"}]}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertEqual(pm["marketplaceVersion"], "1.3.0")
            self.assertIs(pm["marketplaceSelfListed"], True)

    def test_plugin_manifest_marketplace_multi_not_self_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={
                    ".claude-plugin/plugin.json": '{"name": "demo", "version": "1.3.0"}\n',
                    ".claude-plugin/marketplace.json":
                        '{"metadata": {"version": "9.9.9"},'
                        ' "plugins": [{"name": "demo", "source": "./"},'
                        ' {"name": "other", "source": "./other"}]}\n'},
                commits=["chore: init"])
            pm = json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"]
            self.assertIs(pm["marketplaceSelfListed"], False)

    def test_plugin_manifest_absent_for_non_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"package.json": '{"name": "x", "version": "1.0.0"}\n'},
                commits=["chore: init"])
            self.assertIsNone(json.loads(run_script(SCAN, "--repo", repo).stdout)["pluginManifest"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v -k plugin_manifest; cd ..`
Expected: FAIL — `KeyError: 'pluginManifest'`(아직 report에 없음).

- [ ] **Step 3: scan.py 구현** — `scan_ci` 근처(또는 `scan_monorepo` 뒤)에 함수 추가:

```python
def scan_plugin_manifest(repo):
    text = read(repo / ".claude-plugin" / "plugin.json")
    if not text:
        return None
    try:
        pj = json.loads(text)
    except json.JSONDecodeError:
        return None
    version = pj.get("version")
    if not isinstance(version, str):
        return None
    out = {"detected": True, "version": version}
    mtext = read(repo / ".claude-plugin" / "marketplace.json")
    if mtext:
        try:
            mp = json.loads(mtext)
        except json.JSONDecodeError:
            mp = None
        if isinstance(mp, dict):
            meta = mp.get("metadata")
            mv = meta.get("version") if isinstance(meta, dict) else None
            if isinstance(mv, str):
                out["marketplaceVersion"] = mv
            plugins = mp.get("plugins")
            out["marketplaceSelfListed"] = bool(
                isinstance(plugins, list) and len(plugins) == 1
                and isinstance(plugins[0], dict)
                and plugins[0].get("source") in (".", "./")
                and plugins[0].get("name") == pj.get("name"))
    return out
```

report 조립 dict(현 line ~462, `"ci": scan_ci(repo),` 뒤)에 추가:
```python
        "pluginManifest": scan_plugin_manifest(repo),
```

- [ ] **Step 4: 테스트 통과 + 회귀 없음**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..`
Expected: 신규 4 PASS + 기존 scan 테스트 계속 PASS.

- [ ] **Step 5: 전체 스위트**

Run: `python3 -m unittest discover -s tests -q`
Expected: OK (247 + 4 = 251).

- [ ] **Step 6: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "$(printf 'feat: scan pluginManifest 신호 (Claude Code 플러그인 감지)\n\ndetected·version·marketplaceVersion·marketplaceSelfListed(self-listed=\n로컬 소스 단일 플러그인·name 일치). init 프리셋 추천 입력.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 2: init SKILL.md 플러그인 프리셋 prose

**Files:**
- Modify: `skills/init/SKILL.md`

- [ ] **Step 1: 번들 1(성격)에 플러그인 인식 추가** — 번들 1 불릿 말미에 삽입:

`**(Claude Code 플러그인)** 스캔 \`pluginManifest.detected\`면 성격을 'Claude Code 플러그인'(app 계열 단일 레포)으로 선두 추천하고 프리셋을 제시한다 — SemVer · 버전 소스 \`.claude-plugin/plugin.json\`(json-path \`version\`) · tag \`v{version}\` · notes changelog+github-release · pre/post none(플러그인은 SNAPSHOT 관례 없음). 경로·브랜치·유지보수 라인은 번들 6을 따른다.`

- [ ] **Step 2: 번들 2(버전 위치)에 marketplace sync 추가** — 번들 2의 "버전 위치 확정" 구절에 삽입:

`플러그인이면(\`pluginManifest.detected\`) \`.claude-plugin/plugin.json\`을 기본 위치로 제안하고, \`pluginManifest.marketplaceSelfListed\`면 \`.claude-plugin/marketplace.json\`(\`metadata.version\`)을 2차 sync 위치로 함께 추천한다(두 매니페스트를 같은 버전으로 유지). self-listed가 아니면(다중 플러그인 카탈로그) marketplace는 카탈로그 버전이므로 제안하지 않는다.`

- [ ] **Step 3: 줄 수·검증**

Run: `wc -l skills/init/SKILL.md`
Expected: ≤500.
Run: `python3 -m unittest discover -s tests -q` → OK (251, prose는 테스트 무영향).
Run: `claude plugin validate . --strict` → PASS.

- [ ] **Step 4: 커밋**

```bash
git add skills/init/SKILL.md
git commit -m "$(printf 'feat: init이 Claude Code 플러그인 프리셋을 추천 (self-listed marketplace sync)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 3: `claude-plugin` 골든

**Files:**
- Modify: `tests/golden_configs.py`
- Create: `tests/golden/claude-plugin/expected/**`

- [ ] **Step 1: claude_plugin config 추가** — `release_pr_merge` 뒤에 함수 추가:

```python
def claude_plugin():
    # Claude Code 플러그인 프리셋 — plugin.json + marketplace.json sync, release-pr, github
    cfg = scope_config([
        {"file": ".claude-plugin/plugin.json", "type": "json-path", "path": "version"},
        {"file": ".claude-plugin/marketplace.json", "type": "json-path", "path": "metadata.version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    cfg["github"] = {"release": True, "generateNotes": False, "releaseYml": False}
    return cfg
```

`GOLDEN`에 `"claude-plugin": claude_plugin` 등록.

- [ ] **Step 2: 골든 생성 + 범위 확인**

Run: `python3 tests/update_golden.py`
Run: `git status --porcelain tests/golden | grep -v '^??' || echo "(기존 수정 0)"`
Expected: 기존 골든 수정 0(바이트 불변).
Run: `git status --porcelain tests/golden | grep '^??'`
Expected: `?? tests/golden/claude-plugin/` 만.

- [ ] **Step 3: 프리셋 특성 확인** — 다중 location이 verify/version.py에 반영되는지(config 내용 확인):

Run: `grep -c 'claude-plugin/marketplace.json' tests/golden/claude-plugin/expected/.superrelease/config.json`
Expected: 1 (2차 location 존재). config.json은 골든 스냅샷 대상 아니나 트리에 존재.

- [ ] **Step 4: 전체 스위트 + validate**

Run: `python3 -m unittest discover -s tests -q` → OK (251, 골든 subTest는 카운트 무변).
Run: `claude plugin validate . --strict` → PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/golden_configs.py tests/golden/claude-plugin
git commit -m "$(printf 'test: claude-plugin 골든 (플러그인 프리셋 render 핀)\n\n다중 json-path location single scope + release-pr·merge·github.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 4: 최종 검증 + whole-branch 리뷰

- [ ] **Step 1: 전체 검증** — `python3 -m unittest discover -s tests -q`(251 OK) · `claude plugin validate . --strict`(PASS) · `git status --porcelain tests/golden`(클린).
- [ ] **Step 2: init prose 검수** — 번들 1·2 삽입문이 문맥에 자연스럽고 프리셋 값이 스펙과 일치하는지 읽어 확인.
- [ ] **Step 3: whole-branch 독립 리뷰**(opus 서브에이전트) — scan 휴리스틱(self-listed 판정 정확성)·골든 범위·init prose 정합 중점. Critical/Important만 수정.
- [ ] **Step 4: 원장 갱신** — `.superpowers/sdd/progress.md`에 Level 2 완료 기록.

---

## Self-Review

**1. 스펙 커버리지:** scan pluginManifest(T1) · init 프리셋 prose(T2) · claude-plugin 골든(T3) · 검증/리뷰(T4). 스펙 전 항목 매핑.

**2. Placeholder 스캔:** 코드·명령·삽입문 실값. TODO 없음.

**3. 타입/이름 일관성:** `scan_plugin_manifest`는 기존 `read`·`json` 재사용, report 키 추가. 골든 함수는 `scope_config` 스키마(2 location — fixed_monorepo 선례). 테스트는 `run_script`·`SCAN`·`make_git_repo` 실제 헬퍼. 각 태스크 green(scan 무렌더영향).

**리스크:** ① init prose 자동 테스트 없음 → T4 사람 검수 + scan 신호·골든이 결정론 커버. ② self-listed 휴리스틱 보수적(하위 경로 소스는 false) — advisory라 무해. ③ 골든 범위는 T3 Step 2 `git status`가 수용 기준.
