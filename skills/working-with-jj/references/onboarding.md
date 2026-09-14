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
the hooks and wrappers carry the enforcement.

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
  `jj-agent-reflect` (reflection report).
- Agent-host hooks where the host supports them: a world-watch hook (repository moved under
  the agent) and a session-end hook (no unlanded work at stop).
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

Nobody asked for either, and the host that ran the fetch logs nothing. Ask the user, back up the
settings file, then turn off what the host allows. Checked September 2026:

| Host | Can be turned off | Cannot be turned off |
|---|---|---|
| Codex App | worktree upstream refresh → `never`; automatic worktree cleanup; PR auto-merge (`allow_auto_merge: false`); run tasks and automations in **Local** mode, not Worktree | background `git status`/`diff` polling ([openai/codex#32986](https://github.com/openai/codex/issues/32986)) |
| Claude Code Desktop | `"worktree": {"baseRef": "head"}` in `~/.claude/settings.json` — new worktrees start from local `HEAD`, no fetch of `origin` first | background `git fetch` on diff refresh ([anthropics/claude-code#84698](https://github.com/anthropics/claude-code/issues/84698)); the per-session worktree itself — use the `claude` CLI without `--worktree` where that matters |

Do not block `git fetch` by renaming remotes or wrapping `git`: that also breaks `jj git fetch`.
What stays on is covered by `jj land`, which refuses a conflicted trunk and prints the rebase, and
by the world-watch hook, which reports when a bookmark moves under the agent. Tell the user what remains on and that the apps need a
restart. Re-check the open issues when a host updates.

## The order matters

1. Machine mechanisms first (config, wrappers, hooks) — rules that exist only as prose get
   violated under pressure.
2. Skills second — they reference the mechanisms by name.
3. AGENTS.md last — by then it only has to state facts, which is why it stays short.
