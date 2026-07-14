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
    # fragment(소스) + changelog·tag-message(sink) — tag는 기본 annotated
    cfg = scope_config(
        [{"file": "gradle.properties", "type": "properties-key", "key": "version"}])
    cfg["scopes"][0]["notes"]["destinations"] = ["fragment", "changelog", "tag-message"]
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


def train_monorepo():
    # independent + train 객체 → release-train 스킬 + notes-train 템플릿 생성
    cfg = monorepo_config()
    cfg["train"] = {"enabled": True,
                    "scheme": {"type": "calver", "pattern": "YYYY.MICRO"},
                    "tag": {"format": "train-{version}", "annotated": True,
                            "signed": False}}
    return cfg


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo,
          "rc-library": rc_library, "calver-app": calver_app,
          "release-pr-app": release_pr_app, "hotfix-library": hotfix_library,
          "release-pr-snapshot": release_pr_snapshot, "fragment-app": fragment_app,
          "backfill-app": backfill_app, "train-monorepo": train_monorepo,
          "backfill-monorepo": backfill_monorepo,
          "backfill-release-pr": backfill_release_pr}
