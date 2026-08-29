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
- **Commit identity**: whose name goes in the author field, which env vars to export
  (`JJ_USER`, `JJ_EMAIL`), which trailers are required (agent co-authorship, model id).
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

## The order matters

1. Machine mechanisms first (config, wrappers, hooks) — rules that exist only as prose get
   violated under pressure.
2. Skills second — they reference the mechanisms by name.
3. AGENTS.md last — by then it only has to state facts, which is why it stays short.
