# M10 모바일 이중 버전 축소 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)을 실행 없이 감지·질문·기록·안내로 1급화하고, Flutter pubspec `+N`을 마케팅-only 캡처로 usable 후보 승격한다 (+B-30 모바일 preRelease none 안내, M9 이월 minor 2건).

**Architecture:** 스펙은 [2026-08-12-m10-mobile-build-number-design.md](../specs/2026-08-12-m10-mobile-build-number-design.md). 엔진·스크립트 산술 무변경 — `validate_config` 규칙 1건 + scan 개선 + release asset 게이트 한 줄 + init·references 프로즈 + 신규 골든 `flutter-app` 1종. `version.py set`이 캡처 그룹 범위만 치환하므로 마케팅-only 패턴에서 `+N`이 보존된다(검증 완료).

**Tech Stack:** Python 3.9+ stdlib · unittest · 동결 template dialect(`{{#if x == "lit"}}` 인라인 게이트)

**실행 모델:** 구현 서브에이전트는 **opus 모델**로 dispatch한다(사용자 지시).

## Global Constraints

- 테스트 러너: 전체 `python3 -m unittest discover -s tests -q`. 단일 모듈 `cd tests && python3 -m unittest test_scan -v; cd ..`. **dotted 형식 금지(ModuleNotFoundError).**
- 새 `*_PATTERN` str 상수(`PUBSPEC_MARKETING_PATTERN`)는 캡처 그룹 정확히 1개 — 패턴 전수 테스트 하한 13→14.
- **바이트 불변**: asset 게이트는 `repo.buildNumber` 부재/null config에서 0바이트 collapse — 공백을 `{{#if}}` 안에. 골든 재생성 후 `git status --porcelain tests/golden`에 신규 `flutter-app` 트리 **추가만** 보여야 한다(기존 골든 변경 = 회귀, 즉시 중단·보고).
- dogfood: superrelease 자신은 `buildNumber` 부재 — 재렌더가 **바이트 불변**이어야 한다(변화 = 회귀).
- 어서션은 규칙 고유 문구 핀. 프로즈 한국어, 커밋 Conventional Commits, 트레일러 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 작업 브랜치 `feat/m10-mobile-build-number`(체크아웃됨). push·PR 금지.
- init SKILL.md ≤500줄(현재 150줄).

---

### Task 1: scan — pubspec 마케팅-only 승격 + xcconfig 게이트 + flutter 분류

**Files:**
- Modify: `skills/init/scripts/scan.py` (상수 블록, `scan_build_systems`, `scan_version_candidates`)
- Test: `tests/test_scan.py`, `tests/test_render_pipeline.py`(패턴 하한)

**Interfaces:**
- Produces: 상수 `PUBSPEC_MARKETING_PATTERN = "^version:\\s*(\\d[^+\\s]*)"`(캡처 1개), pubspec 후보의 extra 필드 `buildNumber`(str). Task 4의 flutter-app 골든 config와 Task 5의 init 프로즈가 이 패턴·필드를 인용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scan.py`에서 기존 `test_pubspec_build_number_is_advice_only`(MobileScanTest)를 **삭제**하고 그 자리에 아래 3개를 추가한다:

```python
    def test_pubspec_build_number_becomes_marketing_only_candidate(self):
        # M10: `+N`이 있으면 마케팅 부분만 캡처하는 usable 후보로 승격 —
        # set()이 캡처 그룹만 치환하므로 +N은 보존된다. advice-only는 폐지.
        report = scan_tmp(self, {"pubspec.yaml": "name: demo\nversion: 1.2.3+45\n"})
        cands = [c for c in report["versionCandidates"]
                 if c["file"] == "pubspec.yaml"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], "1.2.3")
        self.assertEqual(cands[0]["buildNumber"], "45")
        self.assertNotIn("usable", cands[0])
        self.assertEqual(cands[0]["pattern"], "^version:\\s*(\\d[^+\\s]*)")
        self.assertIn("dart", report["buildSystems"])

    def test_xcconfig_build_setting_reference_is_skipped(self):
        # M10(M9 이월): $(inherited) 같은 빌드 세팅 참조는 후보가 아니다.
        report = scan_tmp(self, {
            "Base.xcconfig": "MARKETING_VERSION = $(inherited)\n",
            "App.xcconfig": "MARKETING_VERSION = 2.0.1\n"})
        files = [c["file"] for c in report["versionCandidates"]
                 if c["file"].endswith(".xcconfig")]
        self.assertEqual(files, ["App.xcconfig"])

    def test_flutter_classification_top_level_section(self):
        # M10(M9 이월): ^[ \t]*flutter: — 최상위 flutter: 섹션도 Flutter 신호,
        # 개행 관통 메커니즘에는 의존하지 않는다.
        top = scan_tmp(self, {"pubspec.yaml":
                              "name: demo\nversion: 1.2.3\n\nflutter:\n  uses-material-design: true\n"})
        self.assertIn("flutter", top["buildSystems"])
        plain = scan_tmp(self, {"pubspec.yaml": "name: demo\nversion: 1.2.3\n"})
        self.assertIn("dart", plain["buildSystems"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_scan.MobileScanTest -v; cd ..`
Expected: 신규 1번(마케팅-only)·2번(xcconfig) FAIL, 3번은 top 케이스가 이미 통과할 수 있으나(기존 `\s+`의 개행 관통이 우연히 매치) 최소 1·2는 FAIL.

- [ ] **Step 3: scan.py 구현**

(a) 상수 블록의 `PUBSPEC_VERSION_PATTERN` 아래에 추가:

```python
PUBSPEC_MARKETING_PATTERN = "^version:\\s*(\\d[^+\\s]*)"
```

(b) `scan_build_systems`의 pubspec 분류를 교체:

```python
    text = read(repo / "pubspec.yaml")
    if text:
        found.append("flutter" if re.search(r"^[ \t]*flutter:", text, re.M) else "dart")
```

(c) `scan_version_candidates`의 pubspec 블록(라인 218-229)을 교체:

```python
    text = read(repo / "pubspec.yaml")
    if text:
        m = re.search(PUBSPEC_VERSION_PATTERN, text, re.M)
        if m:
            if "+" in m.group(1):
                # marketing part is a usable location (set() replaces only the
                # capture group, so +N survives); the build number is CI-managed
                marketing, build = m.group(1).split("+", 1)
                if marketing and marketing[0].isdigit():
                    add("pubspec.yaml", "regex", marketing,
                        pattern=PUBSPEC_MARKETING_PATTERN, buildNumber=build)
            else:
                add("pubspec.yaml", "regex", m.group(1),
                    pattern=PUBSPEC_VERSION_PATTERN)
```

(d) xcconfig 루프의 후보 조건에 VERSIONISH 게이트 추가 — `if m:` 을 `if m and VERSIONISH_RE.match(m.group(1)):` 로 교체(그 외 동일).

- [ ] **Step 4: 패턴 하한 13→14 + 통과 확인**

`tests/test_render_pipeline.py`의 `test_scan_version_patterns_pass_validation` 하한을 `13` → `14`로 올린다.

Run: `cd tests && python3 -m unittest test_scan test_render_pipeline -v 2>&1 | tail -5; cd ..`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/scan.py tests/test_scan.py tests/test_render_pipeline.py
git commit -m "feat(scan): pubspec +N을 마케팅-only usable 후보로 승격 + xcconfig 게이트·flutter 분류 (B-7 축소)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: validate — repo.buildNumber 닫힌 집합

**Files:**
- Modify: `skills/init/scripts/render.py` (`validate_config`의 mergePolicy 규칙 근처, 라인 245-252)
- Modify: `tests/helpers.py` (`scope_config`의 repo dict)
- Test: `tests/test_render_pipeline.py`

**Interfaces:**
- Produces: config 필드 `repo.buildNumber`(`"ci"`|`"manual"`|None) + 거부 메시지 `repo.buildNumber must be "ci", "manual" or null` — Task 3의 게이트, Task 4의 골든 config가 이 필드를 쓴다. helpers의 기본값 `None`은 모든 테스트 ctx에 키가 존재하게 해 템플릿 게이트의 missing-key 의존을 없앤다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render_pipeline.py`에 추가(기존 validate 직접 호출 스타일 — `load_module`·`scope_config`는 이미 import돼 있다):

```python
    def test_build_number_rejects_unknown_value(self):
        render_mod = load_module(PLUGIN_SCRIPTS / "render.py", "render_bn")
        cfg = scope_config([{"file": "x", "type": "regex", "pattern": "v(1)"}])
        cfg["repo"]["buildNumber"] = "auto"
        problems = render_mod.validate_config(cfg)
        self.assertTrue(any('repo.buildNumber must be "ci", "manual" or null'
                            in p for p in problems), problems)

    def test_build_number_valid_values_pass(self):
        render_mod = load_module(PLUGIN_SCRIPTS / "render.py", "render_bn2")
        for bn in (None, "ci", "manual"):
            with self.subTest(buildNumber=bn):
                cfg = scope_config([{"file": "x", "type": "regex",
                                     "pattern": "v(1)"}])
                cfg["repo"]["buildNumber"] = bn
                self.assertEqual(render_mod.validate_config(cfg), [])
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_render_pipeline -v 2>&1 | tail -5; cd ..`
Expected: `test_build_number_rejects_unknown_value` FAIL (규칙 없음 → problems 비어 있음).

- [ ] **Step 3: 구현**

(a) `render.py`의 mergePolicy 규칙 블록 바로 뒤에 추가:

```python
    build_number = repo.get("buildNumber")
    if build_number is not None and build_number not in ("ci", "manual"):
        problems.append('repo.buildNumber must be "ci", "manual" or null '
                        '(got "{}")'.format(build_number))
```

(b) `tests/helpers.py`의 `scope_config` 안 repo dict에 기본값 추가 — `"monorepoStrategy": None,` 줄 다음에:

```python
        "buildNumber": None,
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m unittest discover -s tests -q 2>&1 | tail -3`
Expected: 전부 OK (helpers 변경이 기존 테스트·골든에 영향 없는지 이 전체 실행이 확인한다 — config.json은 골든 스냅샷 대상이 아니다).

- [ ] **Step 5: 커밋**

```bash
git add skills/init/scripts/render.py tests/helpers.py tests/test_render_pipeline.py
git commit -m "feat(validate): repo.buildNumber 닫힌 집합(ci|manual|null) (B-7 축소)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: release asset 빌드 번호 게이트

**Files:**
- Modify: `skills/init/assets/skills/release/SKILL.md` (`## 4. 버전 반영` 섹션, 라인 51)
- Test: `tests/test_assets.py` (`SkillAssetsTest`)

**Interfaces:**
- Consumes: Task 2의 `repo.buildNumber`(helpers 기본 None — base_ctx에 키 존재).
- Produces: 렌더 고유 문구 "빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)" — Task 4의 flutter-app 골든이 ci 게이트 렌더를 핀한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_assets.py`의 `SkillAssetsTest`에 추가:

```python
    def test_release_skill_build_number_gate(self):
        # M10: repo.buildNumber ci/manual일 때만 빌드 번호 안내가 렌더된다 —
        # null/부재에서는 0바이트 collapse.
        ci_ctx = base_ctx()
        ci_ctx["repo"]["buildNumber"] = "ci"
        ci_out = self.render_asset("skills/release/SKILL.md", ci_ctx)
        self.assertIn("빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)은 건드리지 마라", ci_out)

        manual_ctx = base_ctx()
        manual_ctx["repo"]["buildNumber"] = "manual"
        manual_out = self.render_asset("skills/release/SKILL.md", manual_ctx)
        self.assertIn("수동 증가가 필요함을 릴리스 요약에 리마인드", manual_out)
        self.assertNotIn("CI가 올린다", manual_out)

        default_out = self.render_asset("skills/release/SKILL.md")  # buildNumber None
        self.assertNotIn("빌드 번호 축", default_out)
```

- [ ] **Step 2: 실패 확인**

Run: `cd tests && python3 -m unittest test_assets.SkillAssetsTest.test_release_skill_build_number_gate -v; cd ..`
Expected: FAIL (`'빌드 번호 축…' not found`).

- [ ] **Step 3: asset 수정**

`skills/init/assets/skills/release/SKILL.md` 라인 51의 문장 끝 `실행 전 6단계 프리뷰에 포함하라.` 바로 뒤(같은 줄, 개행 앞)에 삽입 — **선행 공백이 게이트 안**:

```
{{#if repo.buildNumber == "ci"}} 빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)은 건드리지 마라 — CI가 올린다. 버전 파일에 남아 있는 빌드 번호 부분은 그대로 보존된다(마케팅 부분만 치환).{{/if}}{{#if repo.buildNumber == "manual"}} 빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)은 이 커밋에서 올리지 않는다 — 스토어 업로드 전 수동 증가가 필요함을 릴리스 요약에 리마인드로 포함하라.{{/if}}
```

- [ ] **Step 4: 통과 확인**

Run: `cd tests && python3 -m unittest test_assets -v 2>&1 | tail -5; cd ..`
Expected: test_assets 전부 PASS(골든 비교는 test_assets 밖이므로 여기서는 안 깨진다 — buildNumber None collapse로 기존 렌더 불변).

- [ ] **Step 5: 커밋**

```bash
git add skills/init/assets/skills/release/SKILL.md tests/test_assets.py
git commit -m "feat(assets): 릴리스 4단계에 빌드 번호 보존 안내 게이트 — repo.buildNumber ci|manual (B-7 축소)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: flutter-app 골든 신설 + 골든·dogfood 불변 확인

**Files:**
- Modify: `tests/golden_configs.py`
- Create(생성물): `tests/golden/flutter-app/expected/**` (update_golden.py가 생성)

**Interfaces:**
- Consumes: Task 1의 `PUBSPEC_MARKETING_PATTERN` 문자열, Task 2의 `repo.buildNumber`, Task 3의 ci 게이트 렌더.

- [ ] **Step 1: golden_configs.py에 flutter_app 추가**

`python_library()` 함수 뒤에 추가:

```python
def flutter_app():
    cfg = scope_config(
        [{"file": "pubspec.yaml", "type": "regex",
          "pattern": "^version:\\s*(\\d[^+\\s]*)"}])
    cfg["repo"]["buildNumber"] = "ci"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg
```

`GOLDEN` dict에 `"flutter-app": flutter_app,` 추가(사전순 배치 무관 — 기존 스타일 따라 끝에).

- [ ] **Step 2: 골든 재생성 + 범위 확인**

```bash
python3 tests/update_golden.py
git status --porcelain tests/golden
```

Expected: `tests/golden/flutter-app/` 신규 트리 **추가만**(?? 표시). 기존 골든이 하나라도 M(수정)이면 바이트 불변 위반 — **즉시 중단·보고**.

- [ ] **Step 3: 신규 골든에 게이트 렌더 확인**

```bash
grep -c "빌드 번호 축" tests/golden/flutter-app/expected/.claude/skills/release/SKILL.md
grep -rc "빌드 번호 축" tests/golden/gradle-app/expected/.claude/skills/release/SKILL.md || true
```

Expected: flutter-app에 1 이상 / gradle-app에 0(collapse).

- [ ] **Step 4: dogfood 불변 확인 + 전체 테스트**

```bash
NOW=$(python3 -c "import json; print(json.load(open('.superrelease/config.json'))['superrelease']['generatedAt'])")
python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now "$NOW"
git status --porcelain .claude .superrelease
python3 -m unittest discover -s tests -q 2>&1 | tail -3
claude plugin validate . --strict 2>&1 | tail -1
```

Expected: dogfood **빈 출력**(superrelease는 buildNumber null — 바이트 불변) / 전부 OK / Validation passed.

- [ ] **Step 5: 커밋**

```bash
git add tests/golden_configs.py tests/golden/flutter-app
git commit -m "test(golden): flutter-app 골든 신설 — 마케팅-only pubspec + buildNumber ci 게이트 핀

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: init 프로즈 + references 갱신

**Files:**
- Modify: `skills/init/SKILL.md` (번들 4, 라인 53)
- Modify: `skills/init/references/edge-cases.md` ("빌드 번호 축 공통" 불릿)

init SKILL.md·references는 렌더 asset이 아니다 — 골든·dogfood 무관, 자동 테스트 없음. 아래 문구를 그대로 적용하라.

- [ ] **Step 1: 번들 4(라인 53)에 빌드 번호 질문 + B-30 삽입**

라인 53의 끝(`references/prerelease-and-dev-channel.md 참고)를 한 줄 안내하라` 뒤 문장 끝, 줄 끝 개행 앞)에 ` / ` + 아래 텍스트를 삽입한다:

```
**(모바일)** buildSystems에 `flutter`/`dart`가 있거나, xcconfig·`app/`·`android/app/` versionName 후보 또는 pubspec 후보의 `buildNumber` 필드가 있으면 빌드 번호 축(versionCode·CFBundleVersion·pubspec `+N`)의 관리 방식을 물어라 — CI 자동 증가(권장 — `github.run_number`·`flutter build --build-number`·fastlane `increment_build_number`·agvtool 스니펫 방향만 안내) | 수동. 답을 `repo.buildNumber`(`"ci"`|`"manual"`)에 기록하고 `decisions`에 `{"topic":"build-number","answer":"ci"|"manual","rationale":"<감지 신호>","source":"scan","decidedAt":"<date>"}`를 기록한다. superrelease는 빌드 번호를 절대 수정하지 않는다(pubspec 마케팅-only 패턴은 캡처 그룹만 치환해 `+N` 보존). 모바일 앱은 preRelease none 권장 — 스토어 베타(TestFlight/Play 트랙)는 빌드번호+트랙 기반이라 버전 qualifier 모델 밖이다. 비모바일 레포는 묻지 말고 `repo.buildNumber`를 null로 둔다
```

- [ ] **Step 2: edge-cases.md "빌드 번호 축 공통" 불릿 교체**

```
- **빌드 번호 축 공통** — `versionCode`·`CFBundleVersion`·pubspec `+N`은 superrelease의 버전 모델 밖이다. 마케팅 버전만 superrelease로 관리하고 빌드 번호는 CI가 올리는 구성을 권장한다.
```

을 다음으로 교체한다:

```
- **빌드 번호 축 공통** — superrelease는 빌드 번호(`versionCode`·`CFBundleVersion`·pubspec `+N`)의 값을 올리지 않는다 — `repo.buildNumber`(`ci`|`manual`)가 관리 방식만 기록하고 release 스킬이 보존을 안내한다. pubspec은 `+N` 감지 시 스캔이 마케팅-only 패턴(`^version:\s*(\d[^+\s]*)`)을 자동 제안한다 — `version.py set`이 캡처 그룹만 치환해 `+N`이 보존된다. 빌드 번호 증가는 CI 몫(`github.run_number`·`--build-number`·fastlane·agvtool).
```

- [ ] **Step 3: 검증**

```bash
wc -l skills/init/SKILL.md
python3 -m unittest discover -s tests -q 2>&1 | tail -3
```

Expected: ≤500줄(150 유지) / 전부 OK.

- [ ] **Step 4: 커밋**

```bash
git add skills/init/SKILL.md skills/init/references/edge-cases.md
git commit -m "docs(init): 빌드 번호 축 질문·기록·안내 + 모바일 preRelease none 권장 (B-7 축소·B-30)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: README 양판 + CHANGELOG + 최종 검증

**Files:**
- Modify: `README.md`·`README_KO.md` (모바일 한계 불릿, config 표, 골든 핀 목록·개수)
- Modify: `CHANGELOG.md` ([Unreleased])

- [ ] **Step 1: README_KO.md 모바일 불릿 교체**

```
- **모바일(Flutter/iOS/Android/React Native)** — 마케팅 버전 축은 scan이
  감지합니다(pubspec.yaml, `*.xcconfig`의 `MARKETING_VERSION`,
  `app/`·`android/app/`의 `versionName`). 빌드 번호 축(`versionCode`,
  `CFBundleVersion`, pubspec `+N`)은 여전히 모델이 없습니다 —
  `next-version.py`는 build metadata가 섞인 버전(`1.2.3+45`)을 조용히
  드롭하는 대신 명시적으로 거부합니다.
```

을 다음으로 교체:

```
- **모바일(Flutter/iOS/Android/React Native)** — 마케팅 버전 축은 scan이
  감지하고(pubspec.yaml, `*.xcconfig`의 `MARKETING_VERSION`,
  `app/`·`android/app/`의 `versionName`), 빌드 번호 축(`versionCode`,
  `CFBundleVersion`, pubspec `+N`)은 CI-관리 모델로 지원합니다 — init이
  관리 방식을 물어 `repo.buildNumber`에 기록하고, release가 보존을
  보장합니다(pubspec `+N`은 마케팅-only 패턴으로 보존). 빌드 번호 값을
  올리는 실행은 하지 않습니다 — CI 몫입니다.
```

- [ ] **Step 2: README.md(영문) 대응 교체**

```
- **Mobile (Flutter/iOS/Android/React Native)** — scan now detects the
  marketing-version axis (pubspec.yaml, `MARKETING_VERSION` in `*.xcconfig`,
  `versionName` under `app/`·`android/app/`). The build-number axis
  (`versionCode`, `CFBundleVersion`, pubspec `+N`) still has no model;
  `next-version.py` rejects versions carrying build metadata (`1.2.3+45`)
  instead of silently dropping it.
```

을 다음으로 교체:

```
- **Mobile (Flutter/iOS/Android/React Native)** — scan detects the
  marketing-version axis (pubspec.yaml, `MARKETING_VERSION` in `*.xcconfig`,
  `versionName` under `app/`·`android/app/`), and the build-number axis
  (`versionCode`, `CFBundleVersion`, pubspec `+N`) is supported as a
  CI-managed model: init asks how it is managed, records it in
  `repo.buildNumber`, and the release skill guarantees preservation
  (pubspec `+N` survives via a marketing-only pattern). superrelease never
  bumps build numbers itself — that stays in CI.
```

- [ ] **Step 3: config 표에 repo.buildNumber 행 추가(양판)**

`README_KO.md`의 `| \`repo.mergePolicy\` | ...` 행 다음에:

```
| `repo.buildNumber` | `ci` \| `manual` \| null | 모바일 빌드 번호 축의 관리 방식 기록(기본 null — 비모바일). superrelease는 값을 올리지 않음 |
```

`README.md`의 `| \`repo.mergePolicy\` | ...` 행 다음에:

```
| `repo.buildNumber` | `ci` \| `manual` \| null | records how the mobile build-number axis is managed (default null — non-mobile). superrelease never bumps it |
```

- [ ] **Step 4: 골든 핀 목록·개수 갱신(양판)**

- `README_KO.md`·`README.md`의 "프로젝트 유형(골든 핀)"/"Project types (golden-pinned)" 행에 Flutter 항목 추가: KO는 `JVM 라이브러리/백엔드(...)` 앞뒤 목록에 ` · Flutter 앱(pubspec 마케팅-only + 빌드 번호 CI 관리)` 를, EN에는 ` · Flutter app (marketing-only pubspec + CI-managed build number)` 를 목록 끝(플러그인 항목 뒤·Maven 각주 앞)에 삽입.
- 골든 개수 언급 전수 갱신: `grep -rn "31종\|31 " README.md README_KO.md`로 대표 config 개수 언급(README_KO.md:153 "대표 config 31종" 등)을 찾아 **32**로 갱신(31이 골든 개수를 뜻하는 경우만 — 무관한 31은 건드리지 않는다).

- [ ] **Step 5: CHANGELOG [Unreleased]에 M10 항목 추가**

`### Added` 목록 끝(M9의 2불릿 뒤)에:

```markdown
- **모바일 빌드 번호 축을 CI-관리 모델로 지원한다** — init이 모바일
  신호(flutter/dart·xcconfig·versionName·pubspec `+N`)를 보면 빌드 번호
  관리 방식(CI 자동 증가 권장 | 수동)을 물어 `repo.buildNumber`에 기록하고,
  release 스킬은 버전 반영 시 빌드 번호를 건드리지 않음을 안내한다.
  모바일은 preRelease `none` 권장 안내(스토어 베타는 빌드번호+트랙 기반)도
  함께 한다. 값을 올리는 실행은 하지 않는다 — CI 몫. flutter-app 골든으로
  핀(대표 config 32종).
```

`### Changed` 목록 끝(M7·M8 불릿 뒤)에:

```markdown
- **pubspec `+N` 감지가 감지·안내 전용에서 마케팅-only usable 후보로** —
  M9는 빌드 번호가 섞인 pubspec을 등록 불가로 안내만 했지만, 이제 마케팅
  부분만 캡처하는 패턴을 제안한다. `version.py set`은 캡처 그룹만 치환하므로
  `+N`은 보존된다.
```

- [ ] **Step 6: 최종 검증**

```bash
python3 -m unittest discover -s tests -q 2>&1 | tail -3
claude plugin validate . --strict 2>&1 | tail -1
git status --porcelain
```

Expected: 전부 OK / Validation passed / 이 태스크에서 편집한 3개 파일만.

- [ ] **Step 7: 커밋**

```bash
git add CHANGELOG.md README.md README_KO.md
git commit -m "docs: CHANGELOG M10 기입 + README 모바일 CI-관리 모델·config 표·골든 32종

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
