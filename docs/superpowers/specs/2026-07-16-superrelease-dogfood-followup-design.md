# superrelease dogfooding 후속 — 마찰 3건 수정 (설계)

> 상태: 설계 승인됨 (2026-07-16). 다음 단계: writing-plans.

## 목표

v0.1.0 dogfooding 릴리스가 실전에서 짚은 마찰 3건을 수정한다. #2·#3은 asset을 바꾸므로 **superrelease 자기 툴킷 재렌더**로 이어져(self-render 테스트가 강제), 플러그인이 자기 산출물을 개선하는 dogfooding 루프가 닫힌다.

## 배경 — 발견된 마찰 (v0.1.0 dogfooding)

1. scan이 `.claude-plugin/plugin.json`을 버전 소스로 미감지 → 릴리스 때 location 수동 지정.
2. release 스킬 §6 비-gitflow release-pr resume 문구가 "squash 머지로"를 하드코딩 → mergePolicy=merge 레포(superrelease 자신 포함)에서 부정확.
3. `version.py set`이 no-op(동일 버전)에도 inline JSON(`author`·`keywords`)을 멀티라인으로 재포맷 → `dump_json_like`가 전체 객체를 `json.dumps(indent=…)`로 재직렬화하기 때문. regex·properties-key 타입은 surgical이라 무관.

## 스코프

**In:** 위 3건 수정 + superrelease 자기 config에 marketplace.json 2차 sync + 자기 툴킷 재렌더.
**Out:** libs.versions.toml·gradle 내부 의존성·pom 직접 쓰기(xml-path) 등 기존 후속(무관).

---

## #1 — 플러그인 매니페스트 버전 소스 감지

### scan.py
`package.json` 감지(현 lines 144–151) 패턴을 그대로 따라, `.claude-plugin/plugin.json`의 `version`을 json-path 후보로 추가한다:

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

- **marketplace.json은 제외한다** — `metadata.version`은 마켓플레이스 카탈로그 메타 버전으로, 플러그인 버전과 의미가 다르다(카탈로그는 여러 플러그인을 서로 다른 버전으로 나열할 수 있다). 일반 플러그인 저자에게 자동 sync는 오탐이다.
- `usable`(기본값) — json-path는 안전하게 read/write 가능.

### init SKILL.md
line 142 스캔 감지 목록에 `.claude-plugin/plugin.json`을 추가한다(pom·VERSION·openapi와 나란히). 예: `… / VERSION / openapi·swagger(json·yaml) / pom.xml(…) / .claude-plugin/plugin.json(Claude Code 플러그인 매니페스트, json-path version) + node·gradle 모노레포 패키지 …`.

### test_scan.py
`.claude-plugin/plugin.json`을 둔 레포가 `.claude-plugin/plugin.json` json-path `version` 후보(`usable`)를 산출하는지 검증하는 테스트를 추가한다(기존 scan 후보 테스트 패턴 준수).

### superrelease 자기 config (marketplace 2차 sync)
`.superrelease/config.json`의 scope `versionLocations`에 2차 location을 추가한다:

```json
{"file": ".claude-plugin/marketplace.json", "type": "json-path", "path": "metadata.version"}
```

- superrelease는 plugin+marketplace 단일 레포이고 두 매니페스트의 버전이 mirror(현재 둘 다 0.1.0)이므로, 릴리스 시 함께 bump되도록 sync한다. #3 surgical 덕에 다음 bump가 marketplace.json도 깨끗이 고친다.
- **렌더 산출물엔 무영향** — 템플릿은 `versionLocations`를 보간하지 않는다(런타임에 version.py가 config를 읽는다). 따라서 self-render 트리는 이 변경에 불변. 단 `version.py verify`는 이제 두 위치(plugin.json·marketplace.json, 둘 다 0.1.0)를 확인 → 일치 → exit 0.

---

## #2 — release 스킬 resume 문구 (mergePolicy 반영)

### release/SKILL.md
현재 line 79의 비-gitflow(else) 분기가 "squash 머지로"를 하드코딩한다. mergePolicy를 반영하도록 고친다:

- **현재**: `… sha가 바뀐다({{#if repo.branching == "gitflow"}}머지 커밋으로{{else}}squash 머지로{{/if}} …`
- **수정**: `… sha가 바뀐다({{#if repo.branching == "gitflow"}}머지 커밋으로{{else}}{{#if repo.mergePolicy == "squash"}}squash 머지로{{else}}머지 커밋으로{{/if}}{{/if}} …`

- release-monorepo 등 다른 스킬엔 이 문구가 없다(확인 완료) → **1곳만 수정**.
- **동결 dialect 준수** — 기존 `{{#if x == "lit"}}/{{else}}` 조합만 중첩. 새 문법 없음.

### 바이트 불변 + 신규 골든
- 기존 release-pr 골든(release-pr-app·release-pr-snapshot·backfill-release-pr·release-pr-nogh·monorepo-release-pr·gitflow-app)은 전부 mergePolicy squash(기본) → "squash 머지로" **바이트 불변**. gitflow-app은 gitflow 분기라 무관.
- release-pr + mergePolicy merge(비-gitflow, 단일 레포) 조합 골든이 없어 "머지 커밋으로" 분기가 미검증 → **신규 골든 `release-pr-merge`** 추가로 핀:

```python
def release_pr_merge():
    # release-pr + mergePolicy merge (비-gitflow, 단일 레포) — §6 resume "머지 커밋으로" 분기 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg
```

`GOLDEN` 딕셔너리에 등록 후 `update_golden.py`로 `tests/golden/release-pr-merge/expected/**` 생성. 이 골든은 §2(squash 역참조 collapse)와 §6("머지 커밋으로") 양쪽에서 merge 정책 렌더를 검증한다.

---

## #3 — version.py surgical json-path write

### version.py `set_location` json-path 분기
현재는 `json.loads → obj[path]=new → dump_json_like(text, obj)`로 전체 재직렬화한다. 이를 surgical로 바꾼다:

1. `obj = json.loads(text)`로 파싱(검증) 후 `old = json_path_get(obj, loc["path"], path)`.
2. **no-op 단락**: `old == new_version`이면 쓰지 않고 `return old`(파일 미변경).
3. **surgical**: `key = loc["path"].split(".")[-1]`로 마지막 키를 잡고, `re.compile('("' + re.escape(key) + r'"\s*:\s*")' + re.escape(old) + '(")')`의 매치가 **정확히 1개**면 그 값만 치환(`pat.sub(lambda m: m.group(1) + new_version + m.group(2), text, count=1)`) → `write_text_preserving`.
4. **폴백**: 매치가 0 또는 2개 이상(애매)이면 기존 `dump_json_like` 경로로 안전하게 재직렬화(항상 올바른 값은 보장).
5. package.json이면 기존대로 `sync_package_lock` 호출.

regex·properties-key 타입과 동일하게 **최소 diff**가 되어 inline `author`·`keywords`가 보존된다. 유일 매치 가드 + dump 폴백으로 중복 키·이스케이프 값 등 엣지에서도 정확한 값은 항상 보장한다.

### test_version.py
- inline 배열/객체(`"keywords": [...]` 한 줄, `"author": {...}` 한 줄)를 가진 JSON에서 json-path set 후 그 두 줄이 **바이트 보존**되고 version만 바뀌는지.
- no-op set(old==new)이 파일을 **전혀 변경하지 않는지**.
- 같은 키가 두 번 나오는(애매) JSON에서 폴백으로도 **올바른 값**이 쓰이는지.
- 기존 json-path(package.json·package-lock sync) 테스트가 계속 통과하는지.

---

## dogfood 루프 폐합 (재렌더)

#2(release/SKILL.md)·#3(version.py)이 asset을 바꾸므로, **superrelease 커밋 툴킷이 asset과 드리프트**한다 → `test_dogfood_selfrender`가 실패한다. 재렌더로 닫는다:

```
python3 skills/init/scripts/render.py --config .superrelease/config.json --assets skills/init/assets --repo . --now 2026-07-16T00:00:00+00:00
```

- 재렌더 결과: `.claude/skills/release/SKILL.md`가 "머지 커밋으로"(우리는 mergePolicy=merge)로, `.superrelease/scripts/version.py`가 surgical 버전으로 갱신 → **플러그인이 자기 툴킷을 개선**.
- 재렌더는 **asset 변경(#2·#3) 후**에 수행한다. config의 marketplace 2차 location(#1)은 렌더 산출물에 무영향이나, 순서상 config 편집 후 재렌더한다.
- 마커의 plugin_version은 0.1.0 유지(버전 미변경)라 self-render 일치.

## 테스트 / 골든 규율

- **신규**: `test_scan`(plugin.json 감지) · `test_version`(surgical) 3~4케이스 · 골든 `release-pr-merge`.
- **골든 범위**: `git status --porcelain tests/golden`에 **`release-pr-merge/`만** 신규로 보여야 한다. 기존 20트리 바이트 불변(전부 squash).
- **self-render**: 재렌더로 `.claude/skills/release/SKILL.md`·`.superrelease/scripts/version.py`가 갱신되어 통과(이건 tests/golden이 아니라 레포 트리 대상).

## 실행 모델

코드+테스트+골든 중심 → **SDD 또는 인라인**(writing-plans 핸드오프에서 선택). asset 변경 → 재렌더 → 전체 green + `plugin validate --strict` PASS. 랜딩은 M4 패턴(feat 브랜치 → PR → merge, gh `Cho-D-YoungRae` 전환 후 복원).

## 성공 기준

- scan이 `.claude-plugin/plugin.json`을 json-path `version` 후보로 감지(test).
- version.py json-path set이 surgical — inline 포맷 보존·no-op 무변경(test).
- release 스킬이 mergePolicy를 반영(골든 `release-pr-merge` "머지 커밋으로" + 재렌더된 superrelease 툴킷).
- superrelease config에 marketplace.json 2차 location, `version.py verify` exit 0(두 위치 0.1.0 일치).
- 전체 스위트 green(신규 테스트 포함) · `plugin validate . --strict` PASS · `git status tests/golden`에 `release-pr-merge`만.
- self-render green(재렌더 반영).

## 리스크 / 엣지 케이스

- **#3 surgical regex** — 값에 정규식 특수문자(버전의 `.`)는 `re.escape`로 처리. 중복 키/값은 유일 매치 가드로 걸러 dump 폴백(정확한 값 보장). 테스트로 폴백 경로 커버.
- **재렌더 순서** — 반드시 #2·#3 asset 변경 후. 그 전 self-render는 red(정상 중간 상태).
- **marketplace.json surgical** — `metadata.version`의 마지막 키 `version`이 marketplace.json에 유일 → 1매치 surgical. 다른 "version" 키가 없어 안전.
- **바이트 불변 회귀** — #2는 인라인 조건(개행 추가 없음)이라 개행 회계 이슈 없음. `update_golden` 후 `git status tests/golden` 범위 확인이 수용 기준.

## 후속 (백로그)

- Level 2 확장: init 프리셋에 "Claude Code 플러그인" 성격 추가 등(이번엔 감지·수동 config로 충분).
- 기존: M4b-2 gitflow hotfix · 문서 소소 정리 · libs.versions.toml 등.
