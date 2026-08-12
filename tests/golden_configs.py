"""Representative configs for golden-render snapshots."""
from helpers import monorepo_config, scope_config


def gradle_app():
    return scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])


def npm_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    cfg["scopes"][0]["notes"]["destinations"] = ["release-file", "github-release"]
    cfg["repo"]["tagTriggersDeployment"] = True
    return cfg


def jvm_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["github"]["releaseYml"] = False
    cfg["scopes"][0]["notes"]["language"] = "both"
    return cfg


def pnpm_monorepo():
    return monorepo_config()


def rc_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["scopes"][0]["preRelease"] = {"style": "counter", "qualifier": "rc"}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    cfg["scopes"][0]["tag"]["movingMajorTag"] = True
    return cfg


def calver_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["scheme"] = {"type": "calver", "pattern": "YYYY.MM.MICRO"}
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def release_pr_app():
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def hotfix_library():
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["kind"] = "library"
    cfg["repo"]["maintenanceLines"] = True
    return cfg


def release_pr_snapshot():
    # release-pr + 기본 mutable/next-snapshot → §8이 chore/next-dev 복귀 라인을 렌더한다
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def fragment_app():
    # fragment(소스) + changelog(sink)
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["scopes"][0]["notes"]["destinations"] = ["fragment", "changelog"]
    return cfg


def backfill_app():
    # repo.backfill=true → backfill 스킬 생성 (기존 태그 CHANGELOG 소급)
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["backfill"] = True
    return cfg


def backfill_monorepo():
    # independent + backfill + merge → 모노레포 순회 분기 + non-squash(#6) 한 트리에
    cfg = monorepo_config()
    cfg["repo"]["backfill"] = True
    cfg["repo"]["mergePolicy"] = "merge"
    return cfg


def backfill_release_pr():
    # backfill + release-pr → #4 release-pr 커밋경로 블록
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["backfill"] = True
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def headver_app():
    # headver + pre/post none (validate가 non-semver 조합을 강제)
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["scopes"][0]["scheme"] = {"type": "headver", "pattern": "1"}
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


def fixed_monorepo():
    # fixed = 단일 root scope에 전 패키지 버전 파일 — 흐름은 단일 레포와 동일
    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"},
         {"file": "packages/a/package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = "fixed"
    return cfg


def tagless_app():
    # tagless: anchor.value가 범위 기준. GitHub Release는 태그 필수라 비활성
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["scopes"][0]["tag"] = {"enabled": False, "format": "v{version}",
                               "annotated": False, "signed": False,
                               "movingMajorTag": False}
    cfg["scopes"][0]["anchor"] = {"type": "ref", "value": None}
    cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
    cfg["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
    return cfg


def monorepo_release_pr():
    # independent 모노레포 × release-pr — release-monorepo의 PR 분기 고정
    cfg = monorepo_config()
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def gitflow_app():
    # gitflow: develop cut → main 머지·태그 → back-merge. release-pr 전용(validate 강제)
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    return cfg


def gitflow_monorepo_bundle():
    # imstargg 모양: 공유 gradle.properties 키 3개 + frontend json-path,
    # 전 scope tagless, gitflow(develop), bundle 라운드 노트, GitHub Release 없음
    def app(name, path, locations):
        return {"name": name, "path": path,
                "scheme": {"type": "semver", "pattern": None},
                "versionLocations": locations,
                "tag": {"enabled": False, "format": name + "@{version}",
                        "annotated": False, "signed": False,
                        "movingMajorTag": False},
                "bump": {"mode": "auto-confirm",
                         "sources": ["conventional-commits"],
                         "fallback": "diff", "compatCheck": None},
                "preRelease": {"style": "mutable", "qualifier": "SNAPSHOT"},
                "devChannel": {"enabled": False, "qualifier": None,
                               "immutableId": []},
                "postRelease": {"bump": "next-snapshot"},
                "notes": {"destinations": ["changelog"], "language": "ko",
                          "audience": "developers", "tone": "neutral",
                          "template": "notes-package.md",
                          "perReleasePath": "docs/releases/"},
                "anchor": {"type": "ref", "value": None},
                "dependents": []}

    def prop(key):
        return [{"file": "../../gradle.properties",
                 "type": "properties-key", "key": key}]

    cfg = scope_config(
        [{"file": "package.json", "type": "json-path", "path": "version"}])
    cfg["repo"]["kind"] = "monorepo"
    cfg["repo"]["monorepoStrategy"] = "independent"
    cfg["repo"]["branching"] = "gitflow"
    cfg["repo"]["developBranch"] = "develop"
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["repo"]["releaseCommitFormat"] = "chore(release): {scope}@{version}"
    cfg["github"] = {"release": False, "generateNotes": False,
                     "releaseYml": False}
    cfg["bundle"] = {"enabled": True,
                     "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                     "notesPath": "docs/releases/"}
    cfg["scopes"] = [
        app("core-api", "backend/apps/api", prop("apiVersion")),
        app("core-batch", "backend/apps/batch", prop("batchVersion")),
        app("core-worker", "backend/apps/worker", prop("workerVersion")),
        app("frontend", "frontend",
            [{"file": "package.json", "type": "json-path", "path": "version"}]),
    ]
    return cfg


def release_pr_nogh():
    # release-pr + github.release=false — gh preflight의 release-pr 분기를 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["scopes"][0]["notes"]["destinations"] = ["changelog"]
    cfg["github"] = {"release": False, "generateNotes": False, "releaseYml": False}
    return cfg


def release_pr_merge():
    # release-pr + mergePolicy merge (비-gitflow, 단일 레포) — §6 resume "머지 커밋으로" 핀
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["repo"]["releasePath"] = "release-pr"
    cfg["repo"]["mergePolicy"] = "merge"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


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


def trunk_monorepo_bundle():
    # trunk × independent × bundle — bundle 라운드 노트의 비-gitflow 경로 핀
    cfg = monorepo_config()
    cfg["bundle"] = {"enabled": True,
                     "scheme": {"type": "calver", "pattern": "YYYY.0M.MICRO"},
                     "notesPath": "docs/releases/"}
    return cfg


def fragment_monorepo():
    # independent × fragment(+changelog sink) — §5가 fragment 취합 프로즈와
    # changelog 줄만 렌더하고 release-file·github-release 줄은 collapse함을
    # 핀한다(목적지 합집합 게이트). validate_config의 per-scope 규칙
    # (fragment는 sink 동반 필수)이 2-scope independent에서 통과함도 함께.
    cfg = monorepo_config()
    for s in cfg["scopes"]:
        s["notes"]["destinations"] = ["fragment", "changelog"]
    return cfg


def release_file_monorepo():
    # independent × release-file+github-release — §5가 그 둘만 렌더하고
    # changelog·fragment 줄은 collapse함을 핀한다(fragment_monorepo와 정반대
    # 조합이라 둘이 서로의 대조군이다). validate_config의 per-scope 규칙
    # (release-file은 notes.perReleasePath 필수)이 2-scope independent에서
    # 통과함도 함께.
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


def flutter_app():
    cfg = scope_config(
        [{"file": "pubspec.yaml", "type": "regex",
          "pattern": "^version:\\s*(\\d[^+\\s]*)"}])
    cfg["repo"]["buildNumber"] = "ci"
    cfg["scopes"][0]["preRelease"] = {"style": "none", "qualifier": None}
    cfg["scopes"][0]["postRelease"] = {"bump": "none"}
    return cfg


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


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app,
          "backfill-monorepo": backfill_monorepo,
          "backfill-release-pr": backfill_release_pr,
          "headver-app": headver_app, "fixed-monorepo": fixed_monorepo,
          "tagless-app": tagless_app, "monorepo-release-pr": monorepo_release_pr,
          "gitflow-app": gitflow_app,
          "gitflow-monorepo-bundle": gitflow_monorepo_bundle,
          "release-pr-nogh": release_pr_nogh,
          "release-pr-merge": release_pr_merge, "claude-plugin": claude_plugin,
          "trunk-monorepo-bundle": trunk_monorepo_bundle,
          "fragment-monorepo": fragment_monorepo,
          "release-file-monorepo": release_file_monorepo,
          "hotfix-release-pr": hotfix_release_pr,
          "backfill-gitflow": backfill_gitflow,
          "gitflow-tagless-hotfix": gitflow_tagless_hotfix,
          "gitflow-fixed-monorepo": gitflow_fixed_monorepo,
          "python-library": python_library,
          "mixed-tags-monorepo": mixed_tags_monorepo,
          "flutter-app": flutter_app}
