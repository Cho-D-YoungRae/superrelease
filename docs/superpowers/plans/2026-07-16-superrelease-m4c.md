# superrelease M4c 스캔 커버리지 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** scan.py의 감지 사각(pom.xml·VERSION·openapi·gradle 모노레포·develop 변형)을 닫고 PEP 440 한계를 문서화한다 — versionCandidates에 usable/advice 구분을 도입해 "쓰기 가능한 후보"와 "감지·안내 전용"을 구조적으로 분리한다.

**Architecture:** 스펙 [2026-07-16-superrelease-m4c-scan-coverage-design.md](../specs/2026-07-16-superrelease-m4c-scan-coverage-design.md)의 접근 A — scan.py 인라인 확장(기존 함수에 추가). render 엔진·자산 스크립트·생성 스킬·템플릿 전부 무변경이라 **골든 diff 0인 마일스톤**이다(scan.py·init SKILL.md·references는 골든 미복사).

**Tech Stack:** Python 3.9+ 표준 라이브러리(xml.etree.ElementTree 포함), unittest, fixture 기반 스캔 테스트.

**베이스:** 브랜치 `feat/superrelease-m4c` (스펙 커밋 `272dcc5`, main `e171ace`에서 분기).

## Global Constraints

- 전체 테스트: 레포 루트에서 `python3 -m unittest discover -s tests -q`. 단일 모듈: `cd tests && python3 -m unittest test_scan -v; cd ..` — dotted 형식 금지(ModuleNotFoundError). pytest 미설치.
- scan.py는 읽기 전용·stdlib-only·exit 0/2. 기존 리포트 필드는 전부 하위호환(추가만 — `hasDevelop`은 의미 확장이나 develop 존재 시 기존 true 유지).
- **골든 diff 0**: 매 태스크 커밋 전 `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력 확인(생성물 무변경의 증명).
- init SKILL.md ≤500줄(현재 148). 코드·에러 영어 / 프로즈 한국어.
- 커밋 Conventional Commits 한국어 + `(M4c)` 접미, 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 별도 줄. 각 커밋 뒤 전체 스위트 green.
- libs.versions.toml은 감지하지 않는다(스펙 결정 — 의존성 카탈로그라 오탐 기본값).

---

### Task 1: scan_version_candidates 확장 — pom·VERSION·openapi + usable/advice

**Files:**
- Modify: `skills/init/scripts/scan.py:25-36` (상수 추가), `:16-20` (import), `:77-129` (scan_version_candidates + 헬퍼)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: 없음.
- Produces: versionCandidates 엔트리 선택 필드 규약 — `usable: false`(위치로 사용 불가, 필드 부재 = 사용 가능) + `advice: "maven-project-version"`(안내 코드). 신규 모듈 상수 `POM_REVISION_PATTERN`·`VERSION_FILE_PATTERN`·`OPENAPI_YAML_PATTERN`·`VERSIONISH_RE`·`OPENAPI_FILES`, 신규 헬퍼 `_pom_project_fields(text) -> (version|None, revision|None)`. T4의 init 프로즈가 advice 코드를 참조한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_scan.py`. 파일 상단(DEPLOY_YML 아래)에 fixture 상수 추가:

```python
POM_WITH_REVISION = (
    '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <groupId>com.example</groupId>\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>${revision}</version>\n"
    "  <properties>\n"
    "    <revision>1.2.0-SNAPSHOT</revision>\n"
    "  </properties>\n"
    "</project>\n")

POM_PLAIN_VERSION = (
    "<project>\n"
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <parent>\n"
    "    <groupId>g</groupId>\n"
    "    <artifactId>p</artifactId>\n"
    "    <version>9.9.9</version>\n"
    "  </parent>\n"
    "  <artifactId>demo</artifactId>\n"
    "  <version>1.2.0</version>\n"
    "</project>\n")

POM_PARENT_ONLY = (
    "<project>\n"
    "  <modelVersion>4.0.0</modelVersion>\n"
    "  <parent>\n"
    "    <groupId>g</groupId>\n"
    "    <artifactId>p</artifactId>\n"
    "    <version>9.9.9</version>\n"
    "  </parent>\n"
    "  <artifactId>demo</artifactId>\n"
    "</project>\n")

OPENAPI_YAML = (
    "openapi: 3.0.3\n"
    "info:\n"
    "  title: Demo API\n"
    "  version: 2.4.0\n"
    "paths: {}\n")
```

`ScanTest` 클래스에 테스트 메서드 추가:

```python
    def _candidates_by_file(self, repo):
        data = json.loads(run_script(SCAN, "--repo", repo).stdout)
        return {c["file"]: c for c in data["versionCandidates"]}

    def test_pom_revision_property_is_usable_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_WITH_REVISION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "1.2.0-SNAPSHOT")
            self.assertEqual(cand["pattern"], "<revision>([^<]+)</revision>")
            self.assertNotIn("usable", cand)

    def test_pom_plain_version_detected_but_not_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_PLAIN_VERSION},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["pom.xml"]
            self.assertEqual(cand["value"], "1.2.0")  # parent의 9.9.9가 아니라 project 직계
            self.assertIs(cand["usable"], False)
            self.assertEqual(cand["advice"], "maven-project-version")
            self.assertNotIn("pattern", cand)

    def test_pom_parent_only_yields_no_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"pom.xml": POM_PARENT_ONLY},
                                 commits=["chore: init"])
            self.assertNotIn("pom.xml", self._candidates_by_file(repo))

    def test_version_file_versionish_content_is_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.4.2\n"},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["VERSION"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "1.4.2")
            self.assertEqual(cand["pattern"], "^(\\S+)\\s*$")

    def test_version_file_prose_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"VERSION": "see docs for versioning policy\n"},
                commits=["chore: init"])
            self.assertNotIn("VERSION", self._candidates_by_file(repo))

    def test_openapi_json_info_version_is_json_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"openapi.json":
                       '{"openapi": "3.0.3", "info": {"title": "x", "version": "2.4.0"}}\n'},
                commits=["chore: init"])
            cand = self._candidates_by_file(repo)["openapi.json"]
            self.assertEqual(cand["type"], "json-path")
            self.assertEqual(cand["path"], "info.version")
            self.assertEqual(cand["value"], "2.4.0")

    def test_openapi_yaml_indented_info_version_is_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"swagger.yaml": OPENAPI_YAML},
                                 commits=["chore: init"])
            cand = self._candidates_by_file(repo)["swagger.yaml"]
            self.assertEqual(cand["type"], "regex")
            self.assertEqual(cand["value"], "2.4.0")

    def test_openapi_yaml_toplevel_version_key_not_matched(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp, files={"openapi.yaml": "version: 9.9.9\npaths: {}\n"},
                commits=["chore: init"])
            self.assertNotIn("openapi.yaml", self._candidates_by_file(repo))
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..`
Expected: 신규 8개 중 후보 존재/필드를 단언하는 5개(revision·plain-usable·VERSION·openapi json·yaml)는 KeyError로 FAIL, 부재를 단언하는 3개(parent-only·prose·toplevel)는 현행에도 감지가 없어 PASS(회귀 핀).

- [ ] **Step 3: 구현** — `skills/init/scripts/scan.py`.

import 블록(:16-20)에 추가:

```python
import xml.etree.ElementTree as ET
```

상수 블록(BADGE_VERSION_PATTERN 아래, TAG_PATTERNS 위)에 추가:

```python
POM_REVISION_PATTERN = "<revision>([^<]+)</revision>"
VERSION_FILE_PATTERN = "^(\\S+)\\s*$"
OPENAPI_YAML_PATTERN = "^[ \\t]+version:\\s*[\"']?([0-9][^\"'\\s#]*)"
VERSIONISH_RE = re.compile(r"^v?\d[\w.+-]*$")
OPENAPI_FILES = ("openapi.json", "openapi.yaml", "openapi.yml",
                 "swagger.json", "swagger.yaml", "swagger.yml")
```

`scan_version_candidates` 위에 헬퍼 추가:

```python
def _pom_project_fields(text):
    """Return (project version, revision property) from a POM, matching tags
    by localname so namespaced and plain POMs both parse. (None, None) on
    parse failure or non-project root."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, None

    def local(el):
        return el.tag.rsplit("}", 1)[-1]

    if local(root) != "project":
        return None, None
    version = revision = None
    for child in root:
        name = local(child)
        if name == "version" and (child.text or "").strip():
            version = child.text.strip()
        elif name == "properties":
            for prop in child:
                if local(prop) == "revision" and (prop.text or "").strip():
                    revision = prop.text.strip()
    return version, revision
```

`scan_version_candidates` 안, build.gradle 블록(:90-95)과 package.json 블록 사이에 pom 감지 삽입:

```python
    text = read(repo / "pom.xml")
    if text:
        version, revision = _pom_project_fields(text)
        if revision is not None:
            add("pom.xml", "regex", revision, pattern=POM_REVISION_PATTERN)
        elif version is not None:
            add("pom.xml", "regex", version,
                usable=False, advice="maven-project-version")
```

README.md 배지 블록(:124-128) 뒤, `return out` 앞에 VERSION·openapi 감지 삽입:

```python
    text = read(repo / "VERSION")
    if text:
        stripped = text.strip()
        if stripped and "\n" not in stripped and VERSIONISH_RE.match(stripped):
            add("VERSION", "regex", stripped, pattern=VERSION_FILE_PATTERN)
    for name in OPENAPI_FILES:
        text = read(repo / name)
        if not text:
            continue
        if name.endswith(".json"):
            try:
                info = json.loads(text).get("info")
            except (json.JSONDecodeError, AttributeError):
                continue
            v = info.get("version") if isinstance(info, dict) else None
            if isinstance(v, str) and v.strip():
                add(name, "json-path", v.strip(), path="info.version")
                break
        else:
            m = re.search(OPENAPI_YAML_PATTERN, text, re.M)
            if m and VERSIONISH_RE.match(m.group(1)):
                add(name, "regex", m.group(1), pattern=OPENAPI_YAML_PATTERN)
                break
```

- [ ] **Step 4: 통과 + 전체 스위트 + 골든 무영향**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..` → 전부 PASS
Run: `python3 -m unittest discover -s tests -q` → OK
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat: scan — pom(revision 후보/project 감지)·VERSION·openapi 버전 후보 + usable/advice 구분 (M4c)"
```

---

### Task 2: scan_monorepo gradle 확장 — _gradle_packages + buildSystem 대칭

**Files:**
- Modify: `skills/init/scripts/scan.py` (`_node_packages`의 append에 buildSystem, `_gradle_packages` 신설, `scan_monorepo` 합류)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: 기존 `GRADLE_VERSION_PATTERN`, `_module_hints`(무변경 유지 — 하위호환 필드).
- Produces: `monorepo.packages` 엔트리에 `buildSystem: "node"|"gradle"` 필드(전 엔트리), gradle 엔트리 스키마 `{"path","name","version","buildSystem"}`(name = 경로 마지막 세그먼트). `internalDependencies`는 node 전용 유지.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_scan.py`의 `ScanTest`에 추가:

```python
    def test_gradle_multimodule_packages_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"settings.gradle":
                           'rootProject.name = "demo"\n'
                           'include(":app")\n'
                           "include ':lib-a', ':lib-b'\n"
                           'include(":nested:core")\n',
                       "app/build.gradle": 'version = "1.0.0"\n',
                       "lib-a/gradle.properties": "version=2.0.0\n",
                       "lib-b/build.gradle.kts": 'version = "3.0.0"\n',
                       "nested/core/build.gradle": "// no version\n"},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            mono = data["monorepo"]
            self.assertTrue(mono["suspected"])
            by_path = {p["path"]: p for p in mono["packages"]}
            self.assertEqual(sorted(by_path),
                             ["app", "lib-a", "lib-b", "nested/core"])
            self.assertEqual(by_path["app"]["version"], "1.0.0")
            self.assertEqual(by_path["lib-a"]["version"], "2.0.0")   # properties 우선
            self.assertEqual(by_path["lib-b"]["version"], "3.0.0")
            self.assertIsNone(by_path["nested/core"]["version"])
            self.assertEqual(by_path["nested/core"]["name"], "core")
            self.assertTrue(all(p["buildSystem"] == "gradle"
                                for p in mono["packages"]))

    def test_node_packages_carry_build_system_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
                       "packages/a/package.json":
                           '{"name": "a", "version": "0.1.0"}\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual(data["monorepo"]["packages"][0]["buildSystem"],
                             "node")

    def test_gradle_module_missing_dir_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(
                tmp,
                files={"settings.gradle": 'include(":ghost")\ninclude(":real")\n',
                       "real/build.gradle": 'version = "1.0.0"\n'},
                commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual([p["path"] for p in data["monorepo"]["packages"]],
                             ["real"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..`
Expected: 신규 3개 FAIL(gradle packages 미수집, buildSystem 필드 부재).

- [ ] **Step 3: 구현** — `skills/init/scripts/scan.py`.

`_node_packages`의 `packages.append(...)`(:257-259)에 buildSystem 필드 추가:

```python
            packages.append({"path": rel, "name": data.get("name"),
                             "version": data.get("version"),
                             "buildSystem": "node",
                             "_deps": sorted(deps)})
```

`_node_packages` 아래에 `_gradle_packages` 신설:

```python
def _gradle_packages(repo):
    """Resolve settings.gradle(.kts) include paths (":a:b" -> "a/b") and
    collect each existing module's version (gradle.properties key first,
    then build.gradle(.kts) assignment)."""
    seen, packages = set(), []
    for name in ("settings.gradle", "settings.gradle.kts"):
        text = read(repo / name)
        if not text:
            continue
        for line in text.splitlines():
            if not re.match(r"^\s*include[ (]", line):
                continue
            for mod in re.findall(r"['\"]:?([A-Za-z0-9._:-]+)['\"]", line):
                rel = mod.replace(":", "/")
                if rel in seen:
                    continue
                seen.add(rel)
                d = repo / rel
                if not d.is_dir():
                    continue
                version = None
                props = read(d / "gradle.properties")
                if props:
                    m = re.search(r"^\s*version\s*=\s*(\S+)\s*$", props, re.M)
                    if m:
                        version = m.group(1)
                if version is None:
                    for bname in ("build.gradle.kts", "build.gradle"):
                        btext = read(d / bname)
                        if btext:
                            m = re.search(GRADLE_VERSION_PATTERN, btext, re.M)
                            if m:
                                version = m.group(1)
                                break
                packages.append({"path": rel,
                                 "name": rel.rsplit("/", 1)[-1],
                                 "version": version,
                                 "buildSystem": "gradle"})
    return packages
```

`scan_monorepo`에서 internalDependencies 계산 뒤(gradle은 node 의존성 그래프와 무관), `return` 앞에 합류:

```python
    node_paths = {p["path"] for p in packages}
    packages += [g for g in _gradle_packages(repo)
                 if g["path"] not in node_paths]
```

(`suspected`의 `len(packages) > 1`은 return 시점 계산이라 gradle 합류가 자동 반영된다.)

- [ ] **Step 4: 통과 + 전체 스위트 + 골든 무영향**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..` → 전부 PASS (기존 node 테스트들도 buildSystem 추가에 무영향 — 필드 단언이 아닌 path/version 단언)
Run: `python3 -m unittest discover -s tests -q` → OK
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat: scan — gradle 멀티모듈 패키지 수집(include 경로 해석) + buildSystem 필드 대칭 (M4c)"
```

---

### Task 3: scan_branches — developBranchGuess

**Files:**
- Modify: `skills/init/scripts/scan.py:176-188` (scan_branches)
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: 없음.
- Produces: 리포트 필드 `branches.developBranchGuess: str|null`(우선순위 develop > development > dev 첫 매치), `branches.hasDevelop = (guess is not None)`. 모듈 상수 `DEVELOP_BRANCH_NAMES`. T4의 init 번들 6 프로즈가 이 필드명을 참조한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_scan.py`의 `ScanTest`에 추가 (상단 import에 `subprocess` 추가):

```python
    def _branch(self, repo, name):
        subprocess.run(["git", "-C", str(repo), "branch", name],
                       check=True, capture_output=True)

    def test_develop_branch_guess_variants(self):
        for branch, expect in (("develop", "develop"),
                               ("development", "development"),
                               ("dev", "dev")):
            with self.subTest(branch=branch), \
                    tempfile.TemporaryDirectory() as tmp:
                repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                     commits=["chore: init"])
                self._branch(repo, branch)
                data = json.loads(run_script(SCAN, "--repo", repo).stdout)
                self.assertTrue(data["branches"]["hasDevelop"])
                self.assertEqual(data["branches"]["developBranchGuess"], expect)

    def test_develop_wins_over_dev(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                 commits=["chore: init"])
            self._branch(repo, "dev")
            self._branch(repo, "develop")
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertEqual(data["branches"]["developBranchGuess"], "develop")

    def test_no_develop_branch_guess_is_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_git_repo(tmp, files={"VERSION": "1.0.0\n"},
                                 commits=["chore: init"])
            data = json.loads(run_script(SCAN, "--repo", repo).stdout)
            self.assertFalse(data["branches"]["hasDevelop"])
            self.assertIsNone(data["branches"]["developBranchGuess"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..`
Expected: `developBranchGuess` KeyError로 신규 2개 FAIL, dev/development 서브테스트 FAIL. (null 테스트는 KeyError로 FAIL.)

- [ ] **Step 3: 구현** — `skills/init/scripts/scan.py`. TAG_PATTERNS 아래에 상수:

```python
DEVELOP_BRANCH_NAMES = ("develop", "development", "dev")
```

`scan_branches`의 return(:185-188)을 교체:

```python
    guess = next((n for n in DEVELOP_BRANCH_NAMES if n in names), None)
    return {"current": current, "defaultGuess": default,
            "hasDevelop": guess is not None,
            "developBranchGuess": guess,
            "releaseBranches": sorted(n for n in names if n.startswith("release/")),
            "hotfixBranches": sorted(n for n in names if n.startswith("hotfix/"))}
```

- [ ] **Step 4: 통과 + 전체 스위트 + 골든 무영향**

Run: `cd tests && python3 -m unittest test_scan -v; cd ..` → PASS
Run: `python3 -m unittest discover -s tests -q` → OK
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py
git commit -m "feat: scan — developBranchGuess(develop>development>dev 우선순위) (M4c)"
```

---

### Task 4: PEP 440 문서화 + init 정합 (번들 1·2·4·6·지원 범위)

**Files:**
- Modify: `skills/init/references/version-schemes.md:47` 근처(SemVer 절 끝)
- Modify: `skills/init/references/prerelease-and-dev-channel.md:69` 근처(post-release 절 뒤)
- Modify: `skills/init/SKILL.md:48,49,51,53,140-148`

**Interfaces:**
- Consumes: T1의 advice 코드 `maven-project-version`·usable 규약, T3의 `developBranchGuess` 필드명.
- Produces: 최종 문서 정합 — 이후 없음. (references·init은 골든 미복사 — 골든 무영향.)

- [ ] **Step 1: version-schemes.md — SemVer 절에 PEP 440 경고 추가.** `- \`next-version.py --release\` (현재 버전이 \`1.3.0-SNAPSHOT\`일 때) → \`1.3.0\`` 줄과 `참고: [semver.org]...` 줄 사이에 삽입:

```markdown

**PEP 440 비호환 주의**: superrelease의 버전 산술(next-version.py)은 SemVer 문법 전용이다. Python PEP 440 고유 형식 — `1.2.0.dev0`(점 구분 dev), `1.2.0.post0`, epoch(`1!2.0.0`), 정규형 pre-release(`1.2.0rc1` — 구분자 없음) — 은 파싱하지 못하고 exit 1로 거부한다. Python 프로젝트의 권장 운용은 `prerelease-and-dev-channel.md`의 해당 절을 참고하라.
```

- [ ] **Step 2: prerelease-and-dev-channel.md — Python 절 신설.** `## post-release 정책` 절 마지막 문단(`...최신 개발 버전을 미리 검증해볼 수 있다.`)과 `## config 매핑` 사이에 삽입:

```markdown

## Python(PEP 440) 프로젝트의 한계와 권장 운용

Python 생태계의 표준 버전 문법(PEP 440)은 SemVer와 겹치지만 다르다 — 개발 버전은 `1.2.0.dev0`(점 구분, 하이픈 없음), 사후 릴리스는 `1.2.0.post0`, pre-release 정규형은 `1.2.0rc1`(구분자 없음)이다. superrelease의 next-version.py는 SemVer 문법만 파싱하므로 이런 문자열은 exit 1로 거부된다.

따라서 Python 프로젝트에는 다음 운용을 권장한다.

- `preRelease.style: none` + `postRelease.bump: none` — 파일 버전은 항상 마지막 릴리스 버전이고, bump는 릴리스 시점에만 일어난다. mutable dev 채널(`-SNAPSHOT`류)과 next-snapshot 복귀는 PEP 440 관례와 맞지 않으므로 쓰지 않는다.
- pre-release가 필요하면 SemVer 문법 `-rc.N`(counter 스타일)을 쓴다. 단 PyPI 업로드 시 도구가 PEP 440 정규형(`1.2.0rc1`)으로 정규화해 파일·태그 표기(`1.2.0-rc.1`)와 달라질 수 있음을 인지하고 결정하라.

init은 pyproject.toml이 버전 후보에 있으면 번들 4에서 이 한계를 한 줄로 안내한다.
```

- [ ] **Step 3: init SKILL.md 번들 프로즈 4곳 수정.**

번들 1(:48): `스캔 리포트 \`monorepo.packages\`를 표로 제시해` → 다음으로 교체:

```
스캔 리포트 `monorepo.packages`(node·gradle 패키지가 `buildSystem` 필드로 구분되어 함께 온다)를 표로 제시해
```

번들 2(:49): `버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 \`versionLocations\`가 된다` → 다음으로 교체:

```
버전 위치 확정 — 스캔 후보를 표로 제시하고 추가·제외를 확인, 이 목록이 `versionLocations`가 된다(`usable: false` 후보는 위치로 제안하지 말고 감지 사실과 advice만 안내하라 — `maven-project-version`이면 pom의 project `<version>`은 regex로 parent/dependency와 구분할 수 없으니 versions-maven-plugin 운용 또는 CI-friendly `<revision>` property 전환을 권장)
```

번들 4(:51): 줄 끝 `...앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안).` → 다음으로 교체:

```
...앱→none 기본(단 SNAPSHOT dev 채널이면 next-snapshot 제안) / pyproject.toml이 버전 후보에 있으면 PEP 440 고유 형식(`1.2.0.dev0` 등)은 미지원이며 Python 프로젝트는 none 스타일 권장임을 한 줄 안내하라(references/prerelease-and-dev-channel.md 참고).
```

(교체 시 기존 문장 전체를 문자열 매치로 찾아 끝부분만 확장한다.)

번들 6(:53): `스캔 \`branches.hasDevelop\`이 true면 명시적으로 묻는다` → `스캔 \`branches.developBranchGuess\`가 있으면(develop/development/dev 우선순위 감지) 명시적으로 묻는다` 로, `\`repo.developBranch\`(감지된 통합 브랜치명, 관례 기본 develop)` → `\`repo.developBranch\`(\`developBranchGuess\` 값, 관례 기본 develop)` 로, `hasDevelop이 false면 trunk 기본 제안` → `developBranchGuess가 null이면 trunk 기본 제안` 으로 교체(3곳).

- [ ] **Step 4: init SKILL.md 지원 범위 절에 스캔 감지 목록 추가.** `- 브랜칭: trunk / gitflow...` 줄 앞에 삽입:

```
- 스캔 감지: gradle.properties / build.gradle(.kts) / package.json / pyproject.toml / Cargo.toml / Dockerfile LABEL / Chart.yaml / README 배지 / VERSION / openapi·swagger(json·yaml) / pom.xml(`<revision>` property는 후보, project `<version>`은 감지·안내 전용) + node·gradle 모노레포 패키지 — libs.versions.toml(의존성 카탈로그)·gradle 내부 의존성·pom 직접 쓰기(xml-path)는 후속
```

- [ ] **Step 5: 검증 + 골든 무영향 + 라인 예산**

Run: `python3 -m unittest discover -s tests -q` → OK (문서 변경 — 테스트 무영향)
Run: `python3 tests/update_golden.py && git status --porcelain tests/golden` → 빈 출력
Run: `wc -l skills/init/SKILL.md` → ≤500 (예상 ~150)

- [ ] **Step 6: 커밋**

```bash
git add skills/init/references/version-schemes.md skills/init/references/prerelease-and-dev-channel.md skills/init/SKILL.md
git commit -m "docs: PEP 440 한계 문서화 + init 스캔 정합(번들1·2·4·6·지원범위) (M4c)"
```

---

### Task 5: 최종 검증

**Files:** 없음 (검증 전용 — 문제 발견 시에만 수정 커밋)

**Interfaces:**
- Consumes: T1~T4 전부.
- Produces: M4c 완료 판정.

- [ ] **Step 1: 전체 검증 실행 및 기록**

```bash
python3 -m unittest discover -s tests -q            # OK (214 + T1 8 + T2 3 + T3 3 = 228개 예상)
claude plugin validate . --strict                    # PASS
python3 tests/update_golden.py && git status --porcelain tests/golden   # 빈 출력 (골든 diff 0 마일스톤)
wc -l skills/init/SKILL.md skills/init/scripts/scan.py                  # init ≤500, scan ~430
git status --porcelain                               # clean
git log --oneline 272dcc5..HEAD                     # T1~T4 커밋 4개
```

- [ ] **Step 2: 스펙 대비 완료 기준 확인**

| 스펙 항목 | 태스크 |
|---|---|
| A pom(revision/감지·안내)·VERSION·openapi + usable/advice | T1 |
| A libs.versions.toml 제외(근거는 스펙 기록) | 작업 없음 — T4의 지원범위 줄이 후속 표시 |
| B gradle 패키지 수집 + buildSystem 대칭 + suspected 반영 | T2 |
| C developBranchGuess + hasDevelop 하위호환 | T3 |
| D PEP 440 references 2건 | T4 |
| E init 정합(번들 1·2·4·6·지원범위) | T4 |
| F fixture 테스트 + 골든 diff 0 게이트 | T1~T4 각 태스크 + T5 |

문제가 없으면 커밋 없이 종료. 발견 시 수정 후 `fix: ... (M4c)` 커밋.
