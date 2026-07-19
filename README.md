# superrelease

> 한국어 문서: [README_KO.md](README_KO.md)

**One fat `init`, a lean per-project release toolkit.**

superrelease is a Claude Code plugin that analyzes your repository, asks a few
questions, and generates a self-contained release toolkit — project skills,
dependency-free scripts, a config file and note templates — committed into your
repo. After init, day-to-day releases run on the generated toolkit alone (just
say "release it"); the plugin is only needed to (re)initialize.

```
┌─ superrelease plugin ─────────────┐      ┌─ your repo ──────────────────────┐
│ init skill (fat)                  │      │ .claude/skills/release/          │
│  scan.py → questions → render.py ─┼─────▶│ .claude/skills/release-notes/    │
│  references/ (domain knowledge)   │      │ .superrelease/{config,scripts,   │
│  assets/ (skeletons)              │      │               templates}         │
└───────────────────────────────────┘      │ .github/release.yml (optional)   │
                                           └──────────────────────────────────┘
```

Design principles:

- `.superrelease/config.json` is the single source of truth for every policy
  decision; generated files can always be re-rendered from it.
- The version's source of truth is your build file (`gradle.properties`,
  `package.json`, …); tags are derived from it.
- Deterministic work (version parsing, edits, arithmetic) is done by scripts,
  never by the LLM. Judgment (bump proposals, release notes) stays with Claude.
- Every side-effecting step shows a dry-run preview and asks before running.

## Requirements

- Claude Code with plugin support
- Python 3.9+ (standard library only — the generated scripts have zero dependencies)
- `gh` CLI (authenticated) or a connected GitHub MCP server — only if you use GitHub Releases or the release-PR path

## Install

```
/plugin marketplace add Cho-D-YoungRae/superrelease
/plugin install superrelease@superrelease
```

Local development: `claude --plugin-dir .` · validate with
`claude plugin validate . --strict` · reload with `/reload-plugins`.

## Quick start

1. In your project, run `/superrelease:init` (or say "릴리스 관리 셋업해줘" / "set up release management").
2. Review the scan-based recommendation table — accept everything, or tune it
   bundle by bundle (scheme, version locations, tags, bump sources, pre-release,
   notes, GitHub Releases, …).
3. Confirm the render preview. init generates the toolkit and, with your OK,
   commits it.
4. From then on:
   - "릴리스해줘" / "release it" — preflight → bump proposal with rationale →
     version files updated → notes → commit & push → tag + GitHub Release →
     post-release (e.g. back to `-SNAPSHOT`)
   - "릴리스 준비됐는지 봐줘" — status only (stops after the bump proposal)
   - "이번 릴리스 노트만 미리 써줘" — drafts notes, no side effects

## Use cases

**How init gathers what it needs.** init never guesses silently. `scan.py`
reads build files, version-string candidates, tags, recent commits
(Conventional-Commits rate, squash evidence), branches (including a
develop-branch guess) and monorepo signals — all read-only — and checks branch
protection via `gh`. Everything inferable is presented as a recommendation
table with its evidence ("accept all / tune per item"); only what can't be
inferred becomes a question. On a fresh repo with no signals, init switches to
proposal mode: it asks the repo's character first, offers a preset (library /
app / Claude Code plugin) and includes creating the missing version file in
the render. Re-init asks only about what changed since the last run.

### Skill roles

| Skill | Generated | Say | Role |
|---|---|---|---|
| release | always | "릴리스해줘" / "release it" / "릴리스 준비됐는지 봐줘" | The orchestrator: preflight gates → change range → bump proposal with rationale → version files → notes → commit or release PR → tag + GitHub Release → post-release. Status-style requests stop after the bump proposal. |
| release-notes | always | "release notes만 미리 써줘" / "changelog 정리" | Drafts notes only — no file writes, no push. The release skill reuses it at its notes step. |
| hotfix | `maintenanceLines` or gitflow | "핫픽스" / "1.2.x에 패치" | Patch release on a maintenance line (`release/1.2.x`), or the gitflow production-hotfix cycle from the default branch. |
| backfill | `backfill` | "백필해줘" / "CHANGELOG 소급" | One-time: reconstructs missing CHANGELOG entries from existing tag history. Idempotent, touches CHANGELOG.md only. |

Each skill's frontmatter description embeds the project name and both Korean
and English trigger phrases, so Claude picks the right skill from natural
requests — no slash command needed. Committing the toolkit is what makes this
work for every teammate's Claude, not just yours.

### On gitflow, which skill runs where

| Branch | What happens |
|---|---|
| `feature/*` | Normal development — no release skill involved. Conventional Commits written here become the bump evidence later (and `changelog.d/` fragments, if configured). |
| `develop` | Where a release starts. "릴리스해줘" → the release skill verifies it is on `develop`, proposes the bump from `anchor..HEAD`, strips `-SNAPSHOT`, writes notes, cuts `release/<version>` and opens a PR to the default branch — then stops. |
| `release/<version>` | A short-lived PR branch the skill created. Humans review and **merge with a merge commit** (squash would break the next release's range). Not a long-lived stabilization branch — those are not part of this cycle. |
| `main` | After the merge, "릴리스해줘" again: preflight detects the merged-but-untagged state and resumes — tag on the merge commit (+ GitHub Release), then back-merge into `develop` and return it to the next `-SNAPSHOT`. |
| hotfix | "핫픽스" → the hotfix skill cuts `hotfix/<patch>` from the default branch HEAD, PRs back to it, tags after merge, then back-merges into `develop`. |

### Walkthrough 1 — new backend service (single repo, Gradle multi-module, gitflow)

A fresh Spring-style backend: one repo, several Gradle modules, one deployable.

- No signals yet → proposal mode. Character: **app**. A multi-module build
  that ships as one deployable is a **single version** (one root scope) — not
  a monorepo; init asks rather than assuming from `settings.gradle`.
- init proposes creating `gradle.properties` with `version=0.1.0-SNAPSHOT`,
  SemVer, mutable `-SNAPSHOT` + next-snapshot, tag `v{version}`,
  changelog + GitHub Releases.
- Choosing gitflow locks the release path to release-pr, records
  `developBranch`, and — since the branch doesn't exist yet — init tells you
  to create and push `develop`, and advises (never runs) branch protection.
  The hotfix skill is generated in its gitflow flavor.
- Day-to-day follows the branch table above.

### Walkthrough 2 — existing monorepo (frontend + multi-module backend, per-app SemVer)

A monorepo with a frontend package and a backend whose bootable modules
(api / batch / worker) version independently.

- scan lists workspace/module packages with their versions and internal
  dependencies; you confirm the **independent** strategy and the scope list.
  Each scope gets its own `pkg@{version}` tag namespace;
  `changed-packages.py` detects which scopes changed since their last tag,
  and `dependents` propagates patch releases through internal dependencies.
- Version locations are flexible: `properties-key` can target different keys
  in a **shared** file (e.g. one backend `gradle.properties` holding
  `apiVersion` / `batchVersion` / `workerVersion`). scan won't auto-detect
  custom key names — add them at the version-locations question.
- Existing tags but a thin CHANGELOG → init offers **backfill**.
- Honest limits: gitflow and bundle round notes are both supported for
  independent monorepos now — see the Branching table and the `bundle` row
  under *Editing config.json* below. The one limit left: the release-pr path
  requires tags **when branching is trunk** (`tag.enabled: false` is rejected
  there). Tags are optional under direct-push (always were) and under
  gitflow (new in M5 — the default branch is the range anchor).

### Walkthrough 3 — new Claude Code plugin

- With `.claude-plugin/plugin.json` present, scan detects it and init leads
  with the plugin preset: SemVer, `plugin.json` as the version source, tag
  `v{version}`, changelog + GitHub Releases, no SNAPSHOT convention. On a
  brand-new repo without the manifest, answer "Claude Code plugin" in
  proposal mode and init includes creating `plugin.json` in the render.
- If the repo self-lists its marketplace (`marketplace.json` pointing at
  `"./"`), `metadata.version` is kept in sync as a second location.
- Protected `main` → release-pr path. superrelease itself runs on exactly
  this toolkit (dogfooding).

## What gets generated (commit all of it)

| Path | Role |
|---|---|
| `.claude/skills/release/SKILL.md` | Release orchestrator skill for this project |
| `.claude/skills/release-notes/SKILL.md` | Notes drafting skill (no side effects) |
| `.superrelease/config.json` | Single source of truth for every decision |
| `.superrelease/scripts/version.py` | Read/write/verify the version across all configured locations |
| `.superrelease/scripts/next-version.py` | Version arithmetic (bump/release/qualifier) |
| `.superrelease/scripts/changed-packages.py` | Detect changed packages per scope (independent monorepos only) |
| `.superrelease/templates/*.md` | Note & changelog skeletons (hand-editable) |
| `.github/release.yml` | Label-based release-note categories (optional) |
| `.claude/skills/hotfix/SKILL.md` | Hotfix skill for maintenance lines (conditional: `maintenanceLines`) |
| `.claude/skills/backfill/SKILL.md` | One-time CHANGELOG backfill from tags (conditional: `backfill`) |
| `.superrelease/templates/release-pr-body.md` | Release-PR body skeleton (conditional: `release-pr`) |
| `.superrelease/templates/notes-package.md` | Per-package note skeleton (conditional: independent monorepo) |

Committing the toolkit is what makes it a team tool: teammates without the
plugin can release too — the generated files reference only `.superrelease/…`
paths, never the plugin.

## Re-init & customization

- Change policy: edit `.superrelease/config.json`, then run init again —
  unchanged answers are not re-asked and files re-render deterministically.
- Templates under `.superrelease/templates/` are the only hand-edit zone:
  remove the `generated by superrelease` marker line and re-init will preserve
  your version.
- Everything else regenerates on re-init; the marker line warns against manual
  edits.

## Branching

| Strategy | Fits | Release path |
|---|---|---|
| trunk / GitHub flow | most new projects | release from `main` |
| gitflow | teams releasing from a `develop` integration branch | single-repo and independent-monorepo projects, release-pr only (cut from develop → merge to main → tag (optional) → back-merge) |

gitflow support is limited to the release-pr path (single-repo and
independent-monorepo projects); direct-push gitflow is not supported. On
gitflow, tags are optional — the default branch is the range anchor for
change detection and stall/resume, tagged or not.

## What superrelease detects

`init` scans (read-only) for version-string locations and repo signals:
`gradle.properties`, `build.gradle(.kts)`, `package.json`, `pyproject.toml`,
`Cargo.toml`, `Dockerfile` LABEL, `Chart.yaml`, README badge, `VERSION`,
`openapi`/`swagger` (json·yaml), `pom.xml` (`<revision>` property is a usable
location; a plain project `<version>` is detected but flagged not-usable),
plus node and Gradle monorepo packages. Not detected: `libs.versions.toml`
(a dependency catalog), Gradle internal dependencies.

## Upgrading

The plugin is only needed to (re)init. When a new plugin version ships,
re-run `/superrelease:init` in an already-initialized repo: unchanged answers
are not re-asked, and files re-render deterministically. The
`generated by superrelease vX.Y.Z` marker line in each generated file records
the version it was rendered from. Editing `.superrelease/config.json` by hand
and re-running init is the official customization path.

## Editing config.json

`.superrelease/config.json` is the single source of truth. Key fields:

| Field | Values | Notes |
|---|---|---|
| `repo.branching` | `trunk` \| `gitflow` | gitflow requires `releasePath: release-pr` + `developBranch` |
| `repo.releasePath` | `direct-push` \| `release-pr` | release-pr is two-phase (PR → merge → tag) |
| `scopes[].scheme.type` | `semver` \| `calver` \| `headver` | calver/headver require `preRelease.style: none` + `postRelease.bump: none` |
| `scopes[].preRelease.style` | `none` \| `mutable` \| `counter` | mutable = `-SNAPSHOT`; counter = `-rc.N` |
| `scopes[].tag.enabled` | explicit boolean | required; `github.release: true` needs it true |
| `scopes[].notes.destinations` | `changelog` \| `release-file` \| `github-release` \| `fragment` | `fragment` needs at least one other destination as a sink |
| `bundle` | `{enabled, scheme: calver+pattern, notesPath}` | independent monorepos: CalVer-named round note bundling each release round |

Invalid combinations are rejected at render time with a message pointing to
the fix — run init again after editing.

## Version schemes

| Scheme | Fits | Links |
|---|---|---|
| SemVer | Libraries (de facto mandatory), general apps | [semver.org](https://semver.org/) |
| CalVer | Release trains, periodically shipped services | [calver.org](https://calver.org/) |
| HeadVer | Apps/services (`{head}.{yearweek}.{build}`) | [line/headver](https://github.com/line/headver) |

SemVer, CalVer and HeadVer are all supported; date/week/counter arithmetic
is handled by `next-version.py` (deterministic, `--today`-injectable).

## Using the scripts directly (no plugin, no Claude)

```bash
python3 .superrelease/scripts/version.py get            # print current version
python3 .superrelease/scripts/version.py verify         # check all locations agree
python3 .superrelease/scripts/version.py set 1.3.0      # write everywhere (+ lockfile)
python3 .superrelease/scripts/next-version.py --release            # 1.3.0-SNAPSHOT → 1.3.0
python3 .superrelease/scripts/next-version.py --bump minor --qualifier SNAPSHOT
python3 .superrelease/scripts/changed-packages.py --json   # monorepo: changes since each package's last tag
```

Exit codes: `0` success · `1` validation failure · `2` usage/config error.
On Windows, replace `python3` with `py -3`.

## FAQ

- **Do teammates need the plugin?** No. The generated skills and scripts are
  self-contained; the plugin is only for (re)init.
- **No `gh` CLI?** The skills fall back to a connected GitHub MCP server, or
  offer a tag-only limited mode.
- **Why doesn't it publish artifacts?** Publishing belongs to CI. The
  recommended boundary: superrelease creates the tag (and GitHub Release), your
  CI publishes on the tag push.
- **A bad version went out?** Never re-tag. Ship the next patch over it and use
  ecosystem recalls (`npm deprecate`, PyPI yank) — the skills will guide you.
- **Dev-server builds?** Keep `-SNAPSHOT` (no bump) and pair it with an
  immutable identifier (commit SHA via Spring build-info, Docker `sha-…` tags).
- **Uninstall?** Delete `.superrelease/` and `.claude/skills/{release*,hotfix,backfill}`
  (and `.github/release.yml` if unused).

## Roadmap

- **M1 (shipped)** — single repo: SemVer, mutable `-SNAPSHOT`, CHANGELOG /
  per-release files / GitHub Releases, direct push
- **M2 (shipped)** — monorepo: fixed/independent strategies, changed-package
  detection, `{pkg}@{ver}` tag namespaces, dependency propagation
- **M3a (shipped)** — version schemes: CalVer/HeadVer arithmetic, counter
  pre-releases (`-rc.N`), moving major tags
- **M3b (shipped)** — release paths: release-PR mode for protected branches
  (two-phase: PR → merge → tag), hotfix flow on maintenance lines
- **M3c (shipped)** — release trains (dual-scheme monorepos), CHANGELOG
  backfill, `changelog.d/` fragments, tag-message notes
- **M4 (shipped)** — hardening: gitflow branching (single-skill repos,
  release-pr only), scan coverage (Maven/Gradle monorepo/openapi/VERSION),
  correctness fixes
- **Scope trim (unreleased)** — removed release trains (dual-scheme monorepos)
  and the `tag-message` notes destination; both are rejected at render time
  with a pointer to the supported alternative
- **M5 (unreleased)** — gitflow monorepos (round release from develop),
  tag-optional gitflow, CalVer bundle round notes (imstargg-style)

Not planned (out of scope, no support promised): sequential versioning,
direct-push gitflow, release trains (root tags — the removed dual-scheme
train; distinct from the supported bundle round notes label above),
`tag-message` notes, `pom.xml` project `<version>` direct writes,
`libs.versions.toml`, artifact publishing, CI workflow generation.
