# M9 스캔 확장 에픽 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** scan.py에 모바일·Tauri·Helm·Go/Terraform 파일 타입, uv workspace, scoped 태그, 기존 릴리스 자동화 감지를 추가하고 init 프로즈·references·README를 정합시킨다 — "엔진은 되는데 입구가 없다" 갭 해소.

**Architecture:** 스펙은 [2026-08-12-m9-scan-expansion-design.md](../specs/2026-08-12-m9-scan-expansion-design.md). scan.py(읽기 전용, stdlib 전용)의 기존 함수를 확장하고 신규 함수 1개(`scan_release_automation`)를 추가한다. version.py·next-version.py·render 엔진·asset은 무변경 — **골든·dogfood 무변경 마일스톤**(이것이 최종 검증 불변식이다).

**Tech Stack:** Python 3.9+ stdlib only (tomllib 사용 금지 — 3.11+) · unittest · regex 기반 TOML/YAML 관례 파싱

**실행 모델:** 구현 서브에이전트는 **opus 모델**로 dispatch한다(사용자 지시).

## Global Constraints

- 테스트 러너: 전체 `python3 -m unittest discover -s tests -q`. 단일 모듈 `cd tests && python3 -m unittest test_scan -v; cd ..`. **dotted 형식(`python3 -m unittest tests.test_scan`)은 ModuleNotFoundError — 금지.**
- **모든 새 `*_PATTERN` str 모듈 상수는 캡처 그룹이 정확히 1개**여야 한다 — `tests/test_render_pipeline.py::test_scan_version_patterns_pass_validation`이 `*_PATTERN` 상수를 자동 수집해 `validate_config`(그룹 1개 강제, render.py:398)를 통과시킨다.
- scan.py는 읽기 전용을 유지한다 — 파일 쓰기·git 상태 변경 금지. 모든 새 감지는 파일 부재 시 조용히 스킵(기존 스타일).
- **골든·dogfood 무변경**: 어느 태스크도 `tests/golden/`·`.claude/`·`.superrelease/`·`skills/init/assets/`를 건드리지 않는다. 최종 검증에서 `git status --porcelain tests/golden .claude .superrelease`가 빈 출력이어야 한다.
- 프로즈(init SKILL.md·references·README_KO)는 한국어, 코드·주석·커밋 제목은 영어/Conventional Commits. init SKILL.md ≤500줄(현재 148줄).
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 작업 브랜치 `feat/m9-scan-expansion`(체크아웃됨). push·PR 금지.
- test_scan.py의 기존 스타일을 따른다: 모듈 상단 픽스처 상수 → `tempfile.TemporaryDirectory()` + `helpers.write`/`make_git_repo` → `run_script(SCAN, "--repo", repo)` → `json.loads(r.stdout)` 어서션.

---

### Task 1: 모바일 파일 타입 — pubspec.yaml·xcconfig·versionName + dart/flutter 빌드 시스템

**Files:**
- Modify: `skills/init/scripts/scan.py` (상수 블록 26-46행 근처, `scan_build_systems`, `scan_version_candidates`)
- Test: `tests/test_scan.py`

**Interfaces:**
- Produces: 상수 `PUBSPEC_VERSION_PATTERN`·`XCCONFIG_MARKETING_PATTERN`·`ANDROID_VERSION_NAME_PATTERN`(전부 캡처 그룹 1개), advice 문자열 `"pubspec-build-number"`, buildSystems 항목 `"flutter"`/`"dart"`. Task 6의 init 프로즈가 이 이름들을 인용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scan.py`에 추가 (기존 import·`SCAN` 상수 재사용; 파일 끝의 테스트 클래스 관례에 따라 적절한 클래스에 추가하거나 새 클래스 `MobileScanTest(unittest.TestCase)`를 만든다):

```python
class MobileScanTest(unittest.TestCase):
    def _scan(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for rel, content in files.items():
                write(Path(tmp) / rel, content)
            r = run_script(SCAN, "--repo", tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)

    def test_pubspec_clean_version_is_usable_candidate(self):
        report = self._scan({"pubspec.yaml":
                             "name: demo\nversion: 1.2.3\n\ndependencies:\n  flutter:\n    sdk: flutter\n"})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "pubspec.yaml"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "1.2.3")
        self.assertEqual(cands[0]["type"], "regex")
        self.assertNotIn("usable", cands[0])
        self.assertIn("flutter", report["buildSystems"])

    def test_pubspec_build_number_is_advice_only(self):
        report = self._scan({"pubspec.yaml": "name: demo\nversion: 1.2.3+45\n"})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "pubspec.yaml"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "1.2.3+45")
        self.assertFalse(cands[0]["usable"])
        self.assertEqual(cands[0]["advice"], "pubspec-build-number")
        self.assertIn("dart", report["buildSystems"])  # flutter 의존성 없음

    def test_xcconfig_marketing_version_root_and_ios(self):
        report = self._scan({
            "Config.xcconfig": "MARKETING_VERSION = 2.0.1\nCURRENT_PROJECT_VERSION = 77\n",
            "ios/App.xcconfig": "MARKETING_VERSION = 2.0.1\n"})
        files = sorted(c["file"] for c in report["versionCandidates"]
                       if c["file"].endswith(".xcconfig"))
        self.assertEqual(files, ["Config.xcconfig", "ios/App.xcconfig"])
        for c in report["versionCandidates"]:
            if c["file"].endswith(".xcconfig"):
                self.assertEqual(c["value"], "2.0.1")
        # CURRENT_PROJECT_VERSION(빌드 번호)은 감지하지 않는다
        joined = json.dumps(report["versionCandidates"])
        self.assertNotIn("CURRENT_PROJECT_VERSION", joined)

    def test_android_version_name_conventional_paths(self):
        report = self._scan({
            "android/app/build.gradle":
                'android {\n  defaultConfig {\n    versionCode 45\n    versionName "3.1.0"\n  }\n}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "android/app/build.gradle"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "3.1.0")
        # versionCode(빌드 번호)는 감지하지 않는다
        self.assertNotIn("45", json.dumps(report["versionCandidates"]))
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.MobileScanTest -v; cd ..`
Expected: 4건 전부 FAIL (후보 0건 — 감지 코드 없음)

- [ ] **Step 3: scan.py 구현**

(a) 상수 블록(`OPENAPI_YAML_PATTERN` 아래)에 추가:

```python
PUBSPEC_VERSION_PATTERN = "^version:\\s*(\\S+)"
XCCONFIG_MARKETING_PATTERN = "^MARKETING_VERSION\\s*=\\s*(\\S+)"
ANDROID_VERSION_NAME_PATTERN = "versionName\\s+['\\\"]([^'\\\"]+)['\\\"]"
ANDROID_GRADLE_PATHS = ("app/build.gradle.kts", "app/build.gradle",
                        "android/app/build.gradle.kts", "android/app/build.gradle")
```

(b) `scan_build_systems`의 rust 블록 뒤에 추가:

```python
    text = read(repo / "pubspec.yaml")
    if text:
        found.append("flutter" if re.search(r"^\s+flutter:", text, re.M) else "dart")
```

(c) `scan_version_candidates`의 OPENAPI 루프 앞에 추가:

```python
    text = read(repo / "pubspec.yaml")
    if text:
        m = re.search(PUBSPEC_VERSION_PATTERN, text, re.M)
        if m:
            if "+" in m.group(1):
                # build number rides in the version field; version.py set would
                # rewrite it away, so this is detect-and-advise only
                add("pubspec.yaml", "regex", m.group(1),
                    usable=False, advice="pubspec-build-number")
            else:
                add("pubspec.yaml", "regex", m.group(1),
                    pattern=PUBSPEC_VERSION_PATTERN)
    for cfg_path in sorted(repo.glob("*.xcconfig")) + sorted((repo / "ios").glob("*.xcconfig")):
        text = read(cfg_path)
        if text:
            m = re.search(XCCONFIG_MARKETING_PATTERN, text, re.M)
            if m:
                add(cfg_path.relative_to(repo).as_posix(), "regex", m.group(1),
                    pattern=XCCONFIG_MARKETING_PATTERN)
    for rel in ANDROID_GRADLE_PATHS:
        text = read(repo / rel)
        if text:
            m = re.search(ANDROID_VERSION_NAME_PATTERN, text)
            if m:
                add(rel, "regex", m.group(1),
                    pattern=ANDROID_VERSION_NAME_PATTERN)
```

- [ ] **Step 4: 패턴 전수 테스트 하한 갱신 + 통과 확인**

`tests/test_render_pipeline.py`의 `test_scan_version_patterns_pass_validation`에서 `self.assertGreaterEqual(len(patterns), 9, ...)`의 하한을 `12`로 올린다(기존 9 + 이 태스크의 상수 3개 — Task 2가 1개를 더해 최종 13이 되지만, 하한 갱신은 태스크별로 자기 몫만 반영한다).

Run: `cd tests && python3 -m unittest test_scan.MobileScanTest test_render_pipeline -v 2>&1 | tail -5; cd ..`
Expected: MobileScanTest 4건 PASS + `test_scan_version_patterns_pass_validation` PASS (새 상수 3개 자동 포섭)

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py tests/test_render_pipeline.py
git commit -m "feat(scan): 모바일 마케팅 버전 감지 — pubspec·xcconfig·versionName (B-8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Tauri·Helm·Go/Terraform — tauri.conf.json, Chart.yaml appVersion, charts/*, buildSystems

**Files:**
- Modify: `skills/init/scripts/scan.py` (`scan_build_systems`, `scan_version_candidates`, `scan_monorepo`)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: Task 1이 만든 `MobileScanTest._scan` 헬퍼 패턴(같은 파일 안이므로 클래스 상속 또는 동일 구조 복제 대신 **모듈 함수로 추출해 공유**: `def scan_tmp(testcase, files)` — 아래 Step 1 참조).
- Produces: 상수 `CHART_APP_VERSION_PATTERN`(그룹 1개), advice 문자열 `"chart-app-version"`, buildSystems 항목 `"go"`·`"terraform"`, monorepo 신호 `"charts/: Chart.yaml children"`, packages `buildSystem: "helm"`.

- [ ] **Step 1: 헬퍼 추출 + 실패하는 테스트 작성**

`tests/test_scan.py`에서 Task 1의 `_scan`을 모듈 함수로 추출한다(MobileScanTest는 이 함수를 호출하도록 수정):

```python
def scan_tmp(testcase, files):
    with tempfile.TemporaryDirectory() as tmp:
        for rel, content in files.items():
            write(Path(tmp) / rel, content)
        r = run_script(SCAN, "--repo", tmp)
        testcase.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)
```

새 테스트 클래스:

```python
class TauriHelmInfraScanTest(unittest.TestCase):
    def test_tauri_v2_top_level_version(self):
        report = scan_tmp(self, {"src-tauri/tauri.conf.json":
                                 '{"productName": "demo", "version": "0.5.0"}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "src-tauri/tauri.conf.json"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "0.5.0")
        self.assertEqual(cands[0]["path"], "version")

    def test_tauri_v1_package_version_fallback(self):
        report = scan_tmp(self, {"src-tauri/tauri.conf.json":
                                 '{"package": {"productName": "demo", "version": "0.4.2"}}\n'})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "src-tauri/tauri.conf.json"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "0.4.2")
        self.assertEqual(cands[0]["path"], "package.version")

    def test_chart_app_version_is_advice_only(self):
        report = scan_tmp(self, {"Chart.yaml":
                                 "apiVersion: v2\nname: demo\nversion: 1.4.0\nappVersion: \"2.9.1\"\n"})
        chart = [c for c in report["versionCandidates"] if c["file"] == "Chart.yaml"]
        self.assertEqual(len(chart), 2)  # version(기존) + appVersion(신규)
        app = [c for c in chart if c.get("advice") == "chart-app-version"]
        self.assertEqual(len(app), 1)
        self.assertFalse(app[0]["usable"])

    def test_charts_children_become_helm_packages(self):
        report = scan_tmp(self, {
            "charts/api/Chart.yaml": "apiVersion: v2\nname: api\nversion: 0.3.0\n",
            "charts/web/Chart.yaml": "apiVersion: v2\nname: web\nversion: 0.8.0\n"})
        self.assertIn("charts/: Chart.yaml children", report["monorepo"]["signals"])
        helm = [p for p in report["monorepo"]["packages"]
                if p["buildSystem"] == "helm"]
        self.assertEqual([(p["path"], p["version"]) for p in helm],
                         [("charts/api", "0.3.0"), ("charts/web", "0.8.0")])
        self.assertTrue(report["monorepo"]["suspected"])

    def test_go_and_terraform_build_systems(self):
        report = scan_tmp(self, {"go.mod": "module example.com/demo\n\ngo 1.22\n",
                                 "main.tf": 'resource "null_resource" "x" {}\n'})
        self.assertIn("go", report["buildSystems"])
        self.assertIn("terraform", report["buildSystems"])
        self.assertEqual(report["versionCandidates"], [])  # 버전 후보 아님
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.TauriHelmInfraScanTest -v; cd ..`
Expected: 5건 전부 FAIL

또한 `tests/test_render_pipeline.py`의 패턴 하한을 `12` → `13`으로 올린다(이 태스크의 `CHART_APP_VERSION_PATTERN` 몫).

- [ ] **Step 3: scan.py 구현**

(a) 상수 추가(`PUBSPEC_VERSION_PATTERN` 근처):

```python
CHART_APP_VERSION_PATTERN = "^appVersion:\\s*[\"']?([^\"'\\s]+)"
```

(b) `scan_build_systems` 끝(pubspec 블록 뒤)에 추가:

```python
    if (repo / "go.mod").is_file():
        found.append("go")
    if any(repo.glob("*.tf")):
        found.append("terraform")
```

(c) `scan_version_candidates`의 기존 Chart.yaml 블록을 확장(version 감지 뒤에 appVersion 감지 추가):

```python
    text = read(repo / "Chart.yaml")
    if text:
        m = re.search(CHART_VERSION_PATTERN, text, re.M)
        if m:
            add("Chart.yaml", "regex", m.group(1), pattern=CHART_VERSION_PATTERN)
        m = re.search(CHART_APP_VERSION_PATTERN, text, re.M)
        if m:
            # appVersion tracks the app, version tracks the chart — which one
            # drives a release is a per-repo decision; detect-and-advise only
            add("Chart.yaml", "regex", m.group(1),
                usable=False, advice="chart-app-version")
```

(d) `scan_version_candidates`의 pubspec 블록 뒤에 tauri 감지 추가:

```python
    text = read(repo / "src-tauri" / "tauri.conf.json")
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            v = data.get("version")
            pkg = data.get("package")
            v1 = pkg.get("version") if isinstance(pkg, dict) else None
            if isinstance(v, str):
                add("src-tauri/tauri.conf.json", "json-path", v, path="version")
            elif isinstance(v1, str):
                add("src-tauri/tauri.conf.json", "json-path", v1,
                    path="package.version")
```

(e) `scan_monorepo`의 packages 병합 뒤(`packages += [g for g in _gradle_packages...]` 다음)에 추가:

```python
    charts_dir = repo / "charts"
    if charts_dir.is_dir():
        chart_children = sorted(d for d in charts_dir.iterdir()
                                if d.is_dir() and (d / "Chart.yaml").is_file())
        if chart_children:
            signals.append("charts/: Chart.yaml children")
            for d in chart_children:
                ctext = read(d / "Chart.yaml") or ""
                m = re.search(CHART_VERSION_PATTERN, ctext, re.M)
                packages.append({"path": d.relative_to(repo).as_posix(),
                                 "name": d.name,
                                 "version": m.group(1) if m else None,
                                 "buildSystem": "helm"})
```

주의: `signals.append`가 `suspected` 계산(`bool(signals) or len(packages) > 1`)보다 앞서도록 return 문 앞에 두어라.

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_scan -v 2>&1 | tail -5; cd ..`
Expected: 전부 PASS (기존 39개 + Task 1·2 신규 — Chart.yaml 기존 테스트가 후보 개수를 핀하고 있으면 appVersion 추가로 깨질 수 있다: 그 경우 기존 테스트의 전제를 확인하고 개수 어서션을 갱신하되, 갱신 사유를 커밋 메시지에 남겨라)

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py tests/test_render_pipeline.py
git commit -m "feat(scan): tauri·Chart appVersion·charts/*·go/terraform 감지 (B-8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: uv workspace + maven modules 힌트

**Files:**
- Modify: `skills/init/scripts/scan.py` (신규 `_python_packages`·`_maven_module_hints`, `scan_monorepo` 확장)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `scan_tmp` 헬퍼(Task 2), `PYPROJECT_VERSION_PATTERN`(기존).
- Produces: monorepo 리포트에 `buildSystem: "python"` packages, `internalDependencies`에 python 항목, 신규 키 `mavenModuleHints`(list), 신호 `"pyproject.toml: [tool.uv.workspace]"`·`"pom.xml: <modules>"`.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
class WorkspaceScanTest(unittest.TestCase):
    def test_uv_workspace_members_and_internal_deps(self):
        report = scan_tmp(self, {
            "pyproject.toml":
                '[project]\nname = "root"\nversion = "0.0.0"\n\n'
                '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
            "packages/core/pyproject.toml":
                '[project]\nname = "demo-core"\nversion = "1.1.0"\ndependencies = []\n',
            "packages/api/pyproject.toml":
                '[project]\nname = "demo-api"\nversion = "2.0.0"\n'
                'dependencies = ["demo-core>=1.0", "fastapi>=0.100"]\n'})
        self.assertIn("pyproject.toml: [tool.uv.workspace]",
                      report["monorepo"]["signals"])
        py = [p for p in report["monorepo"]["packages"]
              if p["buildSystem"] == "python"]
        self.assertEqual([(p["path"], p["name"], p["version"]) for p in py],
                         [("packages/api", "demo-api", "2.0.0"),
                          ("packages/core", "demo-core", "1.1.0")])
        internal = report["monorepo"]["internalDependencies"]
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal[0]["fromName"], "demo-api")
        self.assertEqual(internal[0]["toName"], "demo-core")

    def test_maven_modules_become_hints_not_packages(self):
        report = scan_tmp(self, {
            "pom.xml":
                "<project>\n  <modelVersion>4.0.0</modelVersion>\n"
                "  <artifactId>parent</artifactId>\n  <version>${revision}</version>\n"
                "  <properties>\n    <revision>1.0.0</revision>\n  </properties>\n"
                "  <modules>\n    <module>core</module>\n    <module>api</module>\n"
                "  </modules>\n</project>\n"})
        self.assertEqual(report["monorepo"]["mavenModuleHints"], ["api", "core"])
        self.assertIn("pom.xml: <modules>", report["monorepo"]["signals"])
        self.assertEqual([p for p in report["monorepo"]["packages"]
                          if p["buildSystem"] == "maven"], [])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.WorkspaceScanTest -v; cd ..`
Expected: 2건 FAIL (KeyError `mavenModuleHints` 포함)

- [ ] **Step 3: scan.py 구현**

(a) `_node_packages` 아래에 신규 함수 2개:

```python
def _python_packages(repo):
    """uv workspace members (regex-parsed — no tomllib on 3.9) with the same
    trailing-glob expansion rule as _node_packages."""
    text = read(repo / "pyproject.toml")
    if not text:
        return []
    sec = re.search(r"^\[tool\.uv\.workspace\]\s*$(.*?)(?=^\[|\Z)",
                    text, re.M | re.S)
    if not sec:
        return []
    arr = re.search(r"members\s*=\s*\[(.*?)\]", sec.group(1), re.S)
    if not arr:
        return []
    globs = re.findall(r"['\"]([^'\"]+)['\"]", arr.group(1))
    seen, packages = set(), []
    for g in globs:
        if g.endswith("/**"):
            base = g[:-3]
        elif g.endswith("/*"):
            base = g[:-2]
        else:
            base = g
        base_dir = repo / base
        if not base_dir.is_dir():
            continue
        candidates = [base_dir] if g == base else sorted(
            d for d in base_dir.iterdir() if d.is_dir())
        for d in candidates:
            ptext = read(d / "pyproject.toml")
            if not ptext:
                continue
            rel = d.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            name_m = re.search(r"^name\s*=\s*['\"]([^'\"]+)['\"]", ptext, re.M)
            ver_m = re.search(PYPROJECT_VERSION_PATTERN, ptext, re.M)
            deps = set()
            blocks = []
            dep_m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", ptext, re.M | re.S)
            if dep_m:
                blocks.append(dep_m.group(1))
            opt = re.search(r"^\[project\.optional-dependencies\]\s*$(.*?)(?=^\[|\Z)",
                            ptext, re.M | re.S)
            if opt:
                blocks += re.findall(r"=\s*\[(.*?)\]", opt.group(1), re.S)
            for block in blocks:
                for item in re.findall(r"['\"]([^'\"]+)['\"]", block):
                    nm = re.match(r"[A-Za-z0-9._-]+", item)
                    if nm:
                        deps.add(nm.group(0))
            packages.append({"path": rel,
                             "name": name_m.group(1) if name_m else None,
                             "version": ver_m.group(1) if ver_m else None,
                             "buildSystem": "python", "_deps": sorted(deps)})
    return packages


def _maven_module_hints(repo):
    text = read(repo / "pom.xml")
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    def local(el):
        return el.tag.rsplit("}", 1)[-1]

    hints = []
    for child in root:
        if local(child) == "modules":
            for mod in child:
                if local(mod) == "module" and (mod.text or "").strip():
                    hints.append(mod.text.strip())
    return sorted(set(hints))
```

(b) `scan_monorepo`를 확장 — 기존 internal 매칭을 node+python 공용으로 바꾼다. 기존 코드:

```python
    packages = _node_packages(repo)
    names = {p["name"]: p["path"] for p in packages if p.get("name")}
    internal = []
    for p in packages:
        for dep in p.pop("_deps", []):
            if dep in names and names[dep] != p["path"]:
                internal.append({"fromPath": p["path"], "fromName": p.get("name"),
                                 "toPath": names[dep], "toName": dep})
```

를 다음으로 교체:

```python
    packages = _node_packages(repo)
    py_packages = _python_packages(repo)
    if py_packages:
        signals.append("pyproject.toml: [tool.uv.workspace]")
    dep_scoped = packages + py_packages
    names = {p["name"]: p["path"] for p in dep_scoped if p.get("name")}
    internal = []
    for p in dep_scoped:
        for dep in p.pop("_deps", []):
            if dep in names and names[dep] != p["path"]:
                internal.append({"fromPath": p["path"], "fromName": p.get("name"),
                                 "toPath": names[dep], "toName": dep})
    packages = packages + py_packages
```

(c) maven 힌트 — `scan_monorepo`의 return 직전에:

```python
    maven_hints = _maven_module_hints(repo)
    if maven_hints:
        signals.append("pom.xml: <modules>")
```

return dict에 `"mavenModuleHints": maven_hints,` 추가 (`gradleModuleHints` 옆).

주의: `signals`에 추가되는 두 신호는 `suspected` 계산 전에 이뤄져야 한다 — return 문에서 `suspected`를 계산하는 기존 구조를 유지하면 자동 충족.

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_scan -v 2>&1 | tail -5; cd ..`
Expected: 전부 PASS. 기존 monorepo 테스트가 return 키 집합을 핀하면 `mavenModuleHints` 추가로 깨질 수 있다 — 그 경우 어서션에 새 키를 반영.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat(scan): uv workspace 멤버·내부 의존성 + pom modules 힌트 (B-8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: scoped 태그 클래스 + scopedPrefixes

**Files:**
- Modify: `skills/init/scripts/scan.py` (`TAG_PATTERNS`, `scan_tags`)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `helpers.make_git_repo(tmp, files, commits, tags)` — 태그 생성 픽스처.
- Produces: `TAG_PATTERNS["scoped"]`, `tags.scopedPrefixes`(list, 빈도순 최대 10) — Task 6의 init 프로즈가 인용.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
class ScopedTagScanTest(unittest.TestCase):
    def test_scoped_tags_classified_and_prefixes_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_git_repo(tmp, {"f.txt": "x\n"}, ["chore: seed"],
                          tags=["core@1.0.0", "core@1.1.0", "api@0.2.0", "v9.9.9"])
            r = run_script(SCAN, "--repo", tmp)
            report = json.loads(r.stdout)
        tags = report["tags"]
        self.assertEqual(tags["byPattern"]["scoped"], 3)
        self.assertEqual(tags["byPattern"]["semver-v"], 1)
        self.assertEqual(tags["otherCount"], 0)
        self.assertTrue(tags["mixed"])  # scoped + semver-v 두 그룹
        self.assertEqual(tags["scopedPrefixes"], ["core", "api"])  # 빈도순

    def test_no_scoped_tags_gives_empty_prefixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_git_repo(tmp, {"f.txt": "x\n"}, ["chore: seed"], tags=["v1.0.0"])
            r = run_script(SCAN, "--repo", tmp)
            report = json.loads(r.stdout)
        self.assertEqual(report["tags"]["scopedPrefixes"], [])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.ScopedTagScanTest -v; cd ..`
Expected: 2건 FAIL (KeyError `scoped`/`scopedPrefixes`)

- [ ] **Step 3: scan.py 구현**

(a) `TAG_PATTERNS`에 추가:

```python
TAG_PATTERNS = {
    "semver-v": r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "semver": r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
    "short": r"^v?\d+\.\d+$",
    "scoped": r"^@?[A-Za-z0-9._/-]+@v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$",
}
```

(b) `scan_tags`의 return 앞에:

```python
    prefix_counts = {}
    for t in by_pattern.get("scoped", []):
        prefix = t.rsplit("@", 1)[0]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    scoped_prefixes = [p for p, _ in sorted(
        prefix_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
```

return dict에 `"scopedPrefixes": scoped_prefixes,` 추가.

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_scan -v 2>&1 | tail -5; cd ..`
Expected: 전부 PASS. 기존 태그 테스트가 `byPattern` 키 집합이나 `other` 분류(`pkg@x.y.z`류가 other였던 전제)를 핀하면 갱신 — scoped 태그는 이제 other가 아니다.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat(scan): scoped 태그 클래스 + scopedPrefixes 리포트 (B-8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: B-6 — scan_release_automation

**Files:**
- Modify: `skills/init/scripts/scan.py` (신규 함수 + `main` 리포트 키)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `scan_tmp` 헬퍼(Task 2).
- Produces: top-level 리포트 키 `releaseAutomation` = `{"tools": [{"name", "signals", ("pendingFragments")}], "ciWorkflows": [...]}` — Task 6의 init 프로즈가 이 스키마를 인용.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
class ReleaseAutomationScanTest(unittest.TestCase):
    def test_changesets_with_pending_count(self):
        report = scan_tmp(self, {
            ".changeset/README.md": "readme\n",
            ".changeset/config.json": "{}\n",
            ".changeset/wild-cats-jump.md": "---\n'demo': patch\n---\nfix\n",
            ".changeset/tame-dogs-sit.md": "---\n'demo': minor\n---\nfeat\n"})
        tools = {t["name"]: t for t in report["releaseAutomation"]["tools"]}
        self.assertIn("changesets", tools)
        self.assertEqual(tools["changesets"]["pendingFragments"], 2)  # README 제외

    def test_semantic_release_via_releaserc_and_package_json(self):
        report = scan_tmp(self, {
            ".releaserc.json": "{}\n",
            "package.json": '{"name": "d", "version": "1.0.0", '
                            '"devDependencies": {"semantic-release": "^24.0.0"}}\n'})
        tools = {t["name"]: t for t in report["releaseAutomation"]["tools"]}
        self.assertIn("semantic-release", tools)
        self.assertIn(".releaserc.json", tools["semantic-release"]["signals"])
        self.assertIn("package.json:devDependencies",
                      tools["semantic-release"]["signals"])

    def test_release_please_and_towncrier(self):
        report = scan_tmp(self, {
            "release-please-config.json": "{}\n",
            "pyproject.toml": '[tool.towncrier]\ndirectory = "changelog.d"\n'})
        names = [t["name"] for t in report["releaseAutomation"]["tools"]]
        self.assertIn("release-please", names)
        self.assertIn("towncrier", names)

    def test_ci_workflow_referencing_tool_is_listed(self):
        report = scan_tmp(self, {
            ".changeset/config.json": "{}\n",
            ".github/workflows/release.yml":
                "on: push\njobs:\n  r:\n    steps:\n"
                "      - uses: changesets/action@v1\n"})
        self.assertEqual(report["releaseAutomation"]["ciWorkflows"],
                         [".github/workflows/release.yml"])

    def test_clean_repo_reports_empty(self):
        report = scan_tmp(self, {"README.md": "# demo\n"})
        self.assertEqual(report["releaseAutomation"],
                         {"tools": [], "ciWorkflows": []})
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.ReleaseAutomationScanTest -v; cd ..`
Expected: 5건 FAIL (KeyError `releaseAutomation`)

- [ ] **Step 3: scan.py 구현**

(a) 상수 블록에:

```python
AUTOMATION_CI_MARKERS = ("changesets/action", "release-please",
                         "semantic-release", "towncrier")
SEMANTIC_RELEASE_FILES = (".releaserc", ".releaserc.json", ".releaserc.yaml",
                          ".releaserc.yml", ".releaserc.js", ".releaserc.cjs",
                          "release.config.js", "release.config.cjs",
                          "release.config.mjs")
```

(b) `scan_ci` 아래에 신규 함수:

```python
def scan_release_automation(repo):
    """Existing release-automation tooling (detect only — migration guidance
    lives in the init skill; nothing here mutates or disables anything)."""
    tools = []
    ch_dir = repo / ".changeset"
    if ch_dir.is_dir():
        pending = [p for p in ch_dir.glob("*.md") if p.name != "README.md"]
        tools.append({"name": "changesets", "signals": [".changeset/"],
                      "pendingFragments": len(pending)})
    signals = [n for n in SEMANTIC_RELEASE_FILES if (repo / n).is_file()]
    text = read(repo / "package.json")
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            if isinstance(data.get("release"), dict):
                signals.append("package.json:release")
            for key in ("dependencies", "devDependencies"):
                block = data.get(key)
                if isinstance(block, dict) and "semantic-release" in block:
                    signals.append("package.json:" + key)
    if signals:
        tools.append({"name": "semantic-release", "signals": signals})
    rp = [n for n in ("release-please-config.json",
                      ".release-please-manifest.json") if (repo / n).is_file()]
    if rp:
        tools.append({"name": "release-please", "signals": rp})
    tc = []
    if (repo / "towncrier.toml").is_file():
        tc.append("towncrier.toml")
    ptext = read(repo / "pyproject.toml")
    if ptext and re.search(r"^\[tool\.towncrier[\].]", ptext, re.M):
        tc.append("pyproject.toml:[tool.towncrier]")
    if tc:
        tools.append({"name": "towncrier", "signals": tc})
    ci = []
    workflows = repo / ".github" / "workflows"
    if workflows.is_dir():
        for f in sorted(workflows.iterdir()):
            if f.suffix in (".yml", ".yaml"):
                wtext = read(f) or ""
                if any(mk in wtext for mk in AUTOMATION_CI_MARKERS):
                    ci.append(f.relative_to(repo).as_posix())
    return {"tools": tools, "ciWorkflows": ci}
```

(c) `main`의 report dict에서 `"ci": scan_ci(repo),` 다음 줄에:

```python
        "releaseAutomation": scan_release_automation(repo),
```

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: 전부 OK

- [ ] **Step 6: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat(scan): 기존 릴리스 자동화 감지 — changesets·semantic-release·release-please·towncrier (B-6)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: init SKILL.md 프로즈 + references 레시피

**Files:**
- Modify: `skills/init/SKILL.md` (Phase 1 감지 목록 라인, Phase 2 도입부)
- Modify: `skills/init/references/edge-cases.md` (절 추가)

init SKILL.md는 렌더 asset이 아니다 — 골든·dogfood 무관, 자동 프로즈 테스트 없음. 아래 문구를 그대로 적용하라.

- [ ] **Step 1: Phase 1 감지 목록 갱신**

`skills/init/SKILL.md`의 스캔 감지 라인(현재 141행 근처)에서:

```
- 스캔 감지: gradle.properties / build.gradle(.kts) / package.json / pyproject.toml / Cargo.toml / Dockerfile LABEL / Chart.yaml / README 배지 / VERSION / openapi·swagger(json·yaml) / pom.xml(`<revision>` property는 후보, project `<version>`은 감지·안내 전용) / .claude-plugin/plugin.json(Claude Code 플러그인 매니페스트 — json-path `version`) + node·gradle 모노레포 패키지 — libs.versions.toml(의존성 카탈로그)·gradle 내부 의존성·pom 직접 쓰기(xml-path)는 지원하지 않는다
```

을 다음으로 교체한다:

```
- 스캔 감지: gradle.properties / build.gradle(.kts) / package.json / pyproject.toml / Cargo.toml / Dockerfile LABEL / Chart.yaml(version은 후보, appVersion은 감지·안내 전용) / README 배지 / VERSION / openapi·swagger(json·yaml) / pom.xml(`<revision>` property는 후보, project `<version>`은 감지·안내 전용) / .claude-plugin/plugin.json(Claude Code 플러그인 매니페스트 — json-path `version`) / pubspec.yaml(`+빌드번호` 포함 값은 감지·안내 전용 — advice `pubspec-build-number`) / *.xcconfig MARKETING_VERSION(루트·ios/) / app/·android/app/의 build.gradle(.kts) versionName / src-tauri/tauri.conf.json + node·gradle 모노레포 패키지·uv workspace 멤버·charts/* 헬름 차트·pom `<modules>` 힌트·scoped 태그(`pkg@1.2.3` — `tags.scopedPrefixes`가 scope 이름 후보)·기존 릴리스 자동화(changesets·semantic-release·release-please·towncrier → `releaseAutomation`) / go.mod·*.tf는 빌드 시스템 인식만(버전 후보 아님) — libs.versions.toml(의존성 카탈로그)·gradle 내부 의존성·pom 직접 쓰기(xml-path)·빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)은 지원하지 않는다
```

- [ ] **Step 2: Phase 2 도입부에 B-6 안내 단락 삽입**

`## Phase 2 — 질문` 헤딩과 `**패스트트랙 먼저.**` 단락 사이에 다음 단락을 삽입한다:

```
**기존 자동화 먼저.** 스캔 `releaseAutomation.tools`가 비어 있지 않으면 번들 질문 전에 안내하라: ① 감지된 도구와 `ciWorkflows` 목록을 보여주고, 그 워크플로가 살아 있는 동안 superrelease가 태그·Release를 만들면 **같은 태그·버전을 두 시스템이 경합**함을 경고한다(워크플로 비활성화는 사용자 몫 — init은 실행하지 않는다) ② changesets `pendingFragments` > 0이면 펜딩 조각을 기존 도구로 소진(마지막 릴리스)하거나 수동 반영한 뒤 전환할 것을 안내 ③ 기존 도구가 쓰던 per-package CHANGELOG는 전환 후 갱신되지 않음을 고지 ④ 기존 도구가 publish까지 맡고 있었다면 superrelease는 태그·GitHub Release까지만 하므로, publish는 태그 트리거 워크플로로 옮기는 방향을 한 단락으로 안내(실행 없음). 마친 뒤 `decisions`에 `{"topic":"existing-automation","answer":"migrating"|"coexist-warned","rationale":"<감지 도구·조각 수>","source":"scan","decidedAt":"<date>"}`를 기록한다.
```

- [ ] **Step 3: references/edge-cases.md에 레시피 절 추가**

파일 끝(`## init 충돌` 절 뒤)에 추가:

```markdown
## 스캔 밖 수동 등록 레시피

스캔이 감지하지 못하는 파일은 번들 2의 후보 0건 분기(또는 후보 추가)에서 수동 versionLocation으로 등록한다. 자주 나오는 케이스:

- **iOS Info.plist** — `CFBundleShortVersionString`은 키와 값이 별도 줄(`<key>…</key>` 다음 줄 `<string>1.2.3</string>`)이라 단일행 regex 위치로 안전하게 잡을 수 없다. Xcode 프로젝트라면 xcconfig로 버전을 옮기고(`MARKETING_VERSION = 1.2.3`, Info.plist는 `$(MARKETING_VERSION)` 참조) 그 xcconfig를 위치로 등록하는 것이 표준 경로다 — 스캔도 xcconfig는 감지한다.
- **Tauri v1** — 버전이 `src-tauri/tauri.conf.json`의 `package.version`에 있다(v2는 최상위 `version`). 스캔이 둘 다 감지하지만, 수동 등록 시 json-path를 버전 위치에 맞게 구분하라.
- **Android** — `versionName`은 관례상 `app/build.gradle(.kts)` 또는 `android/app/build.gradle(.kts)`의 `defaultConfig`에 있다. `versionCode`(빌드 번호)는 버전 위치로 등록하지 마라 — 산술 모델이 다르다(단조 증가 정수).
- **빌드 번호 축 공통** — `versionCode`·`CFBundleVersion`·pubspec `+N`은 superrelease의 버전 모델 밖이다. 마케팅 버전만 superrelease로 관리하고 빌드 번호는 CI가 올리는 구성을 권장한다.
```

- [ ] **Step 4: 검증**

```bash
wc -l skills/init/SKILL.md
python3 -m unittest discover -s tests -q 2>&1 | tail -3
```

Expected: ≤500줄(148 ± 2) / 전부 OK

- [ ] **Step 5: 커밋**

```bash
git add skills/init/SKILL.md skills/init/references/edge-cases.md
git commit -m "docs(init): 스캔 감지 목록 갱신 + 기존 자동화 안내 단락 + 수동 등록 레시피 (B-6·B-8)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: README 양판 + CHANGELOG + 최종 검증

**Files:**
- Modify: `README.md`·`README_KO.md` (알려진 한계 절)
- Modify: `CHANGELOG.md` ([Unreleased])

- [ ] **Step 1: README_KO.md 한계 절 갱신**

모바일 불릿:

```
- **모바일(Flutter/iOS/Android/React Native)** — 마케팅 버전은 regex 위치로
  동작하지만 scan이 해당 파일을 감지하지 못하고, 빌드 번호 축(`versionCode`,
  `CFBundleVersion`, pubspec `+N`)은 모델 자체가 없습니다.
  `next-version.py`는 build metadata가 섞인 버전(`1.2.3+45`)을 조용히
  드롭하는 대신 명시적으로 거부합니다.
```

을 다음으로 교체:

```
- **모바일(Flutter/iOS/Android/React Native)** — 마케팅 버전 축은 scan이
  감지합니다(pubspec.yaml, `*.xcconfig`의 `MARKETING_VERSION`,
  `app/`·`android/app/`의 `versionName`). 빌드 번호 축(`versionCode`,
  `CFBundleVersion`, pubspec `+N`)은 여전히 모델이 없습니다 —
  `next-version.py`는 build metadata가 섞인 버전(`1.2.3+45`)을 조용히
  드롭하는 대신 명시적으로 거부합니다.
```

기존 자동화 불릿:

```
- **기존 릴리스 자동화** — changesets / semantic-release / release-please를
  감지하지 않습니다. 전환 전에 기존 파이프라인을 직접 내리세요 — 그러지
  않으면 두 시스템이 같은 태그를 두고 경합합니다.
```

을 다음으로 교체:

```
- **기존 릴리스 자동화** — changesets / semantic-release / release-please /
  towncrier를 init이 감지해 이중 자동화 경고와 이주 방향(펜딩 조각 소진,
  태그 트리거 publish 전환)을 안내합니다. 파이프라인을 내리는 실행 자체는
  사용자 몫입니다 — 내리기 전까지는 두 시스템이 같은 태그를 두고 경합합니다.
```

- [ ] **Step 2: README.md(영문) 대응 갱신**

모바일 불릿:

```
- **Mobile (Flutter/iOS/Android/React Native)** — the marketing version works
  through regex locations, but scan does not detect these files, and the
  build-number axis (`versionCode`, `CFBundleVersion`, pubspec `+N`) has no
  model; `next-version.py` rejects versions carrying build metadata
  (`1.2.3+45`) instead of silently dropping it.
```

을 다음으로 교체:

```
- **Mobile (Flutter/iOS/Android/React Native)** — scan now detects the
  marketing-version axis (pubspec.yaml, `MARKETING_VERSION` in `*.xcconfig`,
  `versionName` under `app/`·`android/app/`). The build-number axis
  (`versionCode`, `CFBundleVersion`, pubspec `+N`) still has no model;
  `next-version.py` rejects versions carrying build metadata (`1.2.3+45`)
  instead of silently dropping it.
```

기존 자동화 불릿:

```
- **Existing release automation** — changesets / semantic-release /
  release-please are not detected; retire the old pipeline before switching,
  or both systems will compete over the same tags.
```

을 다음으로 교체:

```
- **Existing release automation** — init detects changesets /
  semantic-release / release-please / towncrier and walks you through the
  dual-automation warning and migration direction (drain pending fragments,
  move publish to a tag-triggered workflow). Actually retiring the old
  pipeline is on you — until then both systems compete over the same tags.
```

- [ ] **Step 3: README 양판 "자동 감지하지 못하는 포맷" 예시 갱신**

M9로 예시 파일들(pubspec·xcconfig·tauri)이 전부 자동 감지되므로 문구를 갱신한다. `README_KO.md`의:

```
버전 위치는 포맷에 매이지 않습니다 — `properties-key`, `json-path`,
단일 캡처 `regex`를 임의의 텍스트 파일에 걸 수 있고 여러 파일을
동기화합니다. 그래서 scan이 자동 감지하지 못하는 포맷(`pubspec.yaml`,
`.xcconfig`, `tauri.conf.json` 등)도 버전 위치 질문에서 직접 등록하면
동작합니다.
```

을 다음으로 교체:

```
버전 위치는 포맷에 매이지 않습니다 — `properties-key`, `json-path`,
단일 캡처 `regex`를 임의의 텍스트 파일에 걸 수 있고 여러 파일을
동기화합니다. 그래서 scan이 자동 감지하지 못하는 포맷(사내 매니페스트,
커스텀 배포 스크립트 등)도 버전 위치 질문에서 직접 등록하면
동작합니다.
```

`README.md`의:

```
Version locations are format-agnostic — `properties-key`, `json-path` and
single-capture `regex` over any text file, with multiple files kept in
sync — so formats scan doesn't auto-detect (`pubspec.yaml`, `.xcconfig`,
`tauri.conf.json`, …) can still be registered by hand at the
version-locations question.
```

을 다음으로 교체:

```
Version locations are format-agnostic — `properties-key`, `json-path` and
single-capture `regex` over any text file, with multiple files kept in
sync — so formats scan doesn't auto-detect (in-house manifests, custom
deploy scripts, …) can still be registered by hand at the
version-locations question.
```

- [ ] **Step 4: CHANGELOG [Unreleased]에 M9 항목 추가**

`### Added` 섹션(M8이 만든) 끝에 불릿 2개 추가:

```markdown
- **scan이 모바일·Tauri·Helm·인프라 입구를 연다** — pubspec.yaml(빌드 번호
  포함 값은 감지·안내 전용)·`*.xcconfig`의 MARKETING_VERSION·`app/`와
  `android/app/`의 versionName·src-tauri/tauri.conf.json(v1/v2)·Chart.yaml
  appVersion(감지·안내 전용)·charts/* 헬름 차트·uv workspace 멤버(내부
  의존성 포함)·pom `<modules>` 힌트·scoped 태그(`pkg@1.2.3`, 프리픽스
  리포트)를 감지하고, go.mod·`*.tf`는 빌드 시스템으로 인식한다. 빌드 번호
  축(versionCode·CFBundleVersion·pubspec `+N`)은 여전히 범위 밖이다.
- **init이 기존 릴리스 자동화를 감지하고 이주를 안내한다** — changesets(펜딩
  조각 수 포함)·semantic-release·release-please·towncrier와 이를 참조하는
  CI 워크플로를 감지해, 이중 자동화 경합 경고·펜딩 조각 처리·태그 트리거
  publish 전환 방향을 안내한다. 파이프라인 변경 실행은 하지 않는다.
```

- [ ] **Step 5: 최종 검증 (골든·dogfood 무변경 불변식 포함)**

```bash
python3 -m unittest discover -s tests -q 2>&1 | tail -3
claude plugin validate . --strict
git status --porcelain tests/golden .claude .superrelease skills/init/assets
git status --porcelain
```

Expected: 전부 OK / Validation passed / **셋째 명령은 빈 출력**(골든·dogfood·asset 무변경 — 이 마일스톤의 핵심 불변식) / 넷째는 이 태스크에서 편집한 3개 파일만.

- [ ] **Step 6: 커밋**

```bash
git add CHANGELOG.md README.md README_KO.md
git commit -m "docs: CHANGELOG M9 기입 + README 모바일·자동화 한계 문구 갱신

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
