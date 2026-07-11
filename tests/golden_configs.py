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


GOLDEN = {"gradle-app": gradle_app, "npm-app": npm_app,
          "jvm-library": jvm_library, "pnpm-monorepo": pnpm_monorepo}
