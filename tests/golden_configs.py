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
          "gitflow-app": gitflow_app, "release-pr-nogh": release_pr_nogh,
          "release-pr-merge": release_pr_merge, "claude-plugin": claude_plugin}
