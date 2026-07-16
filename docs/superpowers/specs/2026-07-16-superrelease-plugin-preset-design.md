# superrelease Level 2 — init Claude Code 플러그인 프리셋 (설계)

> 상태: 설계 승인됨 (2026-07-16). 다음 단계: writing-plans.

## 목표

init이 **Claude Code 플러그인 레포를 인식**하고 맞춤 프리셋(SemVer · `.claude-plugin/plugin.json` 버전 소스 · self-listed면 marketplace.json 2차 sync · changelog+github-release)을 추천하도록 한다. dogfooding 후속에서 plugin.json **감지**·수동 config까지 했으니, 이번엔 init **추천 로직**을 얹어 실사용 플러그인 저자(superrelease의 실제 audience)가 자동으로 올바른 config를 얻게 한다.

## 배경

- 후속 마일스톤(landed): scan이 `.claude-plugin/plugin.json`을 json-path `version` 후보로 감지, superrelease 자기 config에 marketplace 2차 sync 수동 지정.
- 남은 갭: init이 "이건 Claude Code 플러그인"임을 인식·프리셋 추천하지 못함. 일반 app/library 흐름으로만 진행. marketplace.json sync도 자동 제안 없음.

## 스코프

**In:** scan `pluginManifest` 신호 · init 플러그인 프리셋 인식(prose) · self-listed marketplace sync 제안 · `claude-plugin` 골든 · scan 테스트.
**Out:** 플러그인 전용 스킬/템플릿(불필요 — 기존 release 툴킷 그대로) · libs.versions.toml 등 무관 후속.

---

## scan.py — `pluginManifest` 신호

신규 top-level report 키. `.claude-plugin/plugin.json`이 있고 `version`이 문자열이면 객체, 아니면 `null`:

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

report 조립에 `"pluginManifest": scan_plugin_manifest(repo),` 추가.

- **self-listed** = marketplace가 로컬 소스(`.`|`./`)로 **이 플러그인 하나만** 나열(name 일치). 이때만 `metadata.version`이 플러그인 버전 mirror로 간주 → sync 추천 대상. 다중 플러그인 카탈로그면 `marketplaceSelfListed=false`(카탈로그 버전이라 sync 부적절).
- `read`는 기존 헬퍼(없으면 빈 문자열/None). JSON 파싱 실패·version 누락은 안전 폴백.

## init SKILL.md — 플러그인 프리셋 인식 (prose)

- **bundle 1(성격)** 에 추가: `pluginManifest.detected`면 성격을 "Claude Code 플러그인"(app 계열 단일 레포)으로 선두 추천하고 프리셋을 제시 — SemVer · 버전 소스 `.claude-plugin/plugin.json`(json-path `version`) · tag `v{version}` · notes changelog+github-release · pre/post none(플러그인은 SNAPSHOT 관례 없음). 경로·브랜치·유지보수 라인은 bundle 6을 따른다.
- **bundle 2(버전 위치)** 에 추가: 플러그인이면 `.claude-plugin/plugin.json`을 기본 위치로 제안. `pluginManifest.marketplaceSelfListed`면 `.claude-plugin/marketplace.json`(`metadata.version`)을 **2차 sync 위치**로 함께 추천(두 매니페스트를 같은 버전으로 유지). self-listed가 아니면 marketplace는 제안하지 않는다(카탈로그 버전).

prose만 바뀌며 init은 ≤500줄·한국어 유지. init SKILL.md는 렌더/골든/unittest 직접 대상이 아니다.

## 골든 `claude-plugin` (프리셋 render 핀)

`tests/golden_configs.py`:

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

`GOLDEN`에 `"claude-plugin": claude_plugin` 등록 → `update_golden.py`로 `tests/golden/claude-plugin/expected/**` 생성. 단일 scope **다중 json-path location** render + release-pr·merge·github(release only)·pre/post none을 명시 검증(superrelease 실제 프리셋과 동형). `git status tests/golden`에 `claude-plugin`만 신규(기존 21트리 불변).

## test_scan.py

전체 report(`json.loads(run_script(SCAN, "--repo", repo).stdout)`)의 `pluginManifest`를 검증:
- plugin.json 단독 → `detected=True`·`version` 일치·`marketplaceVersion` 부재.
- plugin + self-listed marketplace(1 plugin·source `./`·name 일치) → `marketplaceVersion` 설정·`marketplaceSelfListed=True`.
- plugin + 다중 플러그인 marketplace → `marketplaceSelfListed=False`.
- 비-플러그인(예: package.json만) → `pluginManifest is None`.

## 실행 모델

코드(scan)+골든+prose 중심 → **인라인**(직전 후속과 동일, 강한 자동 게이트). 각 태스크 green. 랜딩은 feat 브랜치 → PR → merge(gh `Cho-D-YoungRae` 전환 후 복원). whole-branch 리뷰로 마감.

## 성공 기준

- scan이 `pluginManifest`(detected·version·marketplaceVersion·marketplaceSelfListed) 산출(test 4종).
- init prose가 플러그인 프리셋·self-listed marketplace sync를 추천(사람 검수).
- `claude-plugin` 골든이 프리셋 render를 핀(`git status tests/golden`에 그것만).
- 전체 스위트 green(scan +4) · `plugin validate . --strict` PASS · 기존 골든 바이트 불변.

## 리스크 / 엣지 케이스

- **self-listed 휴리스틱** — source가 하위 경로(`./plugins/x`)면 self-listed=False(보수적). 추천용 advisory라 오검출해도 사용자가 확인(치명 아님).
- **marketplace metadata.version 누락** — `marketplaceVersion` 부재로 두고 sync 미제안(안전).
- **init prose 자동 테스트 없음** — scan 신호(deterministic)·골든·사람 검수로 커버. 프리셋은 추천값이라 강제 아님.
- **골든 범위 회귀** — `update_golden` 후 `git status tests/golden`에 `claude-plugin`만 = 수용 기준.

## 후속 (백로그)

- M4b-2 gitflow hotfix · 문서 소소 정리 · libs.versions.toml·gradle 내부 의존성·pom xml-path.
