# Onboarding a project into the jj agent workflow

This file answers one question: **what to write where** when wiring a machine and a repository
for agent work with jj. The layering rule governs everything below: instructions live in skills,
project *facts* live in AGENTS.md, machine *facts* live in global config. Never copy skill
content into AGENTS.md or CLAUDE.md — a duplicated rule drifts, and the stale copy wins because
it loads first.

## Global (user-level: `~/.claude/CLAUDE.md` or `~/.agents/` equivalent)

Only cross-project invariants, stated in one line each with a pointer to the skill:

- "Use jj by default whenever the repository supports it; load the `working-with-jj` skill
  first."
- "Follow the `maintaining-vcs-hygiene` culture in every repository, git or jj."
- The trunk invariants your host mechanisms enforce: bookmarks move only forward and only via
  `jj land`; never publish a tip that does not contain the local trunk.
- "Never create branches, worktrees, or workspaces unless explicitly requested or assigned."

That is the whole global entry — four bullets, no procedures. The skills carry the procedures;
explicit wrappers and configuration carry the enforcement.

## Per repository (`AGENTS.md` in the repo root)

Facts an agent cannot discover reliably, or that differ from defaults:

- **Trunk bookmark name** if it is not `main`/`master`/`trunk` (the wrappers autodetect those).
- **Commit identity**: the account-linked committer, any approved agent author address,
  and required trailers. Set agent authorship with `jj metaedit --author`; do not
  override `JJ_USER`/`JJ_EMAIL` for attribution because rewrites also use them for
  the committer.
- **Workspace layout** for parallel work: where managed workspaces live, which launcher command
  creates them, and the rule that agents never create one on their own initiative.
- **Push policy**: who may push, from which checkout, and what gates run.
- **Ignore rules that must exist before work starts** (build output, coverage, scratch
  locations) — because jj snapshots new files immediately, this is an onboarding step, not a
  cleanup step.
- **Scratch location** for hosts that do not provide a session scratchpad (Claude Code does;
  Codex does not): one absolute directory outside the checkout, such as
  `${TMPDIR:-/tmp}/<repo>/<session>`. It is temporary by design; anything meant to outlive the
  session belongs in a change.
- **Forbidden paths**, if any: the fact here, the mechanism in each clone's repository config
  (`jj config set --repo land.forbidden '<fileset>'`), which `jj land` refuses to land.
- **Land check**, if any: the fact here, the command in each clone's repository config
  (`jj config set --repo land.check "'<command>'"`, a TOML string). `jj land` runs it from the
  workspace root with the target's full commit id appended and `JJ_LAND_TARGET`, `JJ_LAND_BASE`,
  `JJ_LAND_BOOKMARK` set, and refuses the land on a non-zero exit. Have the command read the
  checker from the target commit, not from a working copy that may be stale. Keep the setup
  command in the repository so every clone can reproduce it.
- A pointer to any repository-specific companion skill, loaded *in addition to* the two core
  skills, never instead of them.

Keep it under a page. If a paragraph in AGENTS.md explains *how* to do something rather than
*what is true here*, it belongs in a skill.

## Per machine (config and mechanisms)

Applied once per machine, not per repository:

- `~/.config/jj/config.toml`: the `park`/`land`/`orphans` aliases, and the `[git]` safety
  section (`abandon-unreachable-commits = false`, `private-commits` for `wip:`/`private:`
  prefixes).
- `~/.local/bin/`: `jj-land` (guarded trunk move), `jj-agent-event` (guardrail event log),
  `jj-agent-reflect` (reflection report), and `jj-agent` (owned workspace lifecycle).
- Explicit `jj-agent` commands for workspace preparation, inspection and completion. JJ agent
  hooks are retired; do not register completion or response handlers.
- The agent host's own Git automation, switched off **with the user's approval** (next section).

## Agent-host Git automation

Desktop agent apps assume a Git branch workflow: they fetch in the background, create a worktree
per session, clean worktrees up and merge pull requests. Under jj each of those is a writer nobody
asked for — a worktree is a second checkout outside `jj workspace`, a deleted Git ref can take
file content with it (see parallel-agents.md), and a background fetch **moves your bookmarks**.
jj imports the fetched `refs/remotes/*` on its next command and merges them into tracked
bookmarks. Reproduced on 0.44.0 with a plain `git fetch` in a colocated repository:

- local `main` untouched → it fast-forwards to the remote tip. Trunk moved, no `jj land` ran.
- local `main` already moved (landed, not yet pushed) → `main` becomes **conflicted** (`main??`),
  and every command that names `main` fails until someone reconciles it.

Host integration is version-specific. Back up settings and modify only the requested scope.
For current setup use [codex.md](codex.md) and [claude-code.md](claude-code.md):

- Codex: keep JJ hooks unregistered; use prepared colocated workspaces in Local mode.
  Native Git worktree creation/handoff/archive are not our JJ lifecycle.
- Claude: start in the prepared workspace; invoke lifecycle commands explicitly. Do not install
  JJ lifecycle or response hooks.
- Keep active workspaces unchanged. An old non-colocated child can expose its parent's Git
  root; report that mismatch and use a new colocated workspace for the next assigned task.
- Dependency setup remains explicit in each project. VCS root agreement is not app readiness.

Do not wrap Git or rename remotes to block fetch; that can break `jj git fetch`. Observation
reports bookmark changes but does not stop background Git writers. Review remaining host behavior
on upgrades, and restart agents after hook/settings changes. A host that is unavailable can have
its hook contracts tested, but must be reported as lacking live verification.

## The order matters

1. Machine mechanisms first (config and explicit wrappers) — rules that exist only as prose get
   violated under pressure.
2. Skills second — they reference the mechanisms by name.
3. AGENTS.md last — by then it only has to state facts, which is why it stays short.
