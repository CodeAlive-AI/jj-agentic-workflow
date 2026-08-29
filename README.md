# jj-agentic-workflow

A practical methodology for running coding agents — including several in parallel — on
[Jujutsu (jj)](https://github.com/jj-vcs/jj) repositories, without them destroying each
other's work.

It is not a plugin and not bound to any project. It is a set of **skills** (instructions
agents load on demand), **mechanisms** (guarded wrappers, config, hooks that enforce the
rules the skills state), and **tests** that prove the hazards the rules guard against are
real on the current jj version.

## Install: hand this to your agent

You do not install this by hand. Give your agent the repository URL (or a local clone
path) and say:

> Read AGENTS.md in this repository and install the workflow on this machine, then
> onboard my projects.

[`AGENTS.md`](AGENTS.md) is a complete, agent-executable procedure: it installs the
mechanisms and config, registers the hooks, places the skills, runs the hazard test suite
to verify the installation, and then onboards your repositories following
[`skills/working-with-jj/references/onboarding.md`](skills/working-with-jj/references/onboarding.md)
— which lives inside the skill, so an already-installed agent can re-onboard any new
project later without this repository at hand. The agent asks before overwriting anything
you already have and finishes with a report of what it did.

Everything below is for humans who want to know what they are installing.

## What makes this different

Most jj guides teach commands; most agent-workflow posts are speculation. This is
neither:

- **It is experience, not theory.** Every rule was earned in months of real multi-agent
  development on production repositories — each traces to a measured reproduction in the
  test suite or to an actual incident (work silently reverted by `jj undo`, a secret
  captured by auto-snapshot, a trunk forked by a push around unpublished work).
- **It is specifically about parallel agents.** The hazards it guards against barely
  exist for a single human user; they dominate the moment several writers — agents and
  humans — share one repository. That focus is the whole point.
- **It enforces instead of exhorting.** Rules that agents kept violating as prose were
  moved into wrappers, config, and hooks; the skills only carry what cannot be mechanised.
- **It self-verifies and self-corrects.** The test suite asserts the hazards are still
  real on your jj version, and the built-in reflection loop reviews recorded guard events
  to propose moving rules between layers — including deleting them.

## Why this exists

Agents differ from human committers in three ways: they lose context (compaction,
restarts), they run in parallel with humans and other agents, and they generate volume
cheaply. jj is the best VCS substrate for that — automatic snapshotting, first-class
conflicts, cheap workspaces — but several of its properties are actively dangerous in a
multi-writer repository, and none of them are documented as such:

- `jj undo` / `jj op restore` rewind the **whole repository view** and silently revert
  concurrent writers in other workspaces (measured, not speculated — see the test suite).
- There are no read-only commands: even `jj status` snapshots the working copy, absorbing
  stray files into the current change.
- There is no untracked state: a secret written to disk is committed the moment any jj
  command runs, and stays readable in `jj evolog` after "deleting" it.
- Deleting a Git ref (with default config) silently abandons commits and can make file
  content vanish from descendants.
- A revset that matches nothing returns empty, not an error — "no work found" and "wrong
  query" are indistinguishable.

Every rule in this workflow traces to one of those measured hazards or to a real incident.

## The layering doctrine

**An instruction that gets violated should become a mechanism, not a louder instruction.**

1. **Config** — `abandon-unreachable-commits = false`, `private-commits` push refusal.
2. **Mechanisms** — `jj land` (forward-only guarded trunk move), `jj park` (named parking),
   `jj orphans` (unreachable-heads sweep), `jj-agent-event` (guardrail event log).
3. **Hooks** — the world moved under the agent; the session may not end with unlanded work.
4. **Skills** — `working-with-jj` (command layer) and `maintaining-vcs-hygiene` (culture
   layer). They recommend each other and work best as a pair, but each stands alone.
5. **Reflection** — recorded guard events are periodically reviewed with one question:
   *which layer should have caught this?* Additions are paired with removals; the agent
   proposes, the human applies.

## Repository layout

| Path | Contents |
|---|---|
| `AGENTS.md` | The installation procedure, written for an agent to execute |
| `skills/working-with-jj/` | jj command-layer skill + references (parallel agents, secrets, cleanup, publishing, onboarding) |
| `skills/maintaining-vcs-hygiene/` | VCS culture skill + the reflection procedure |
| `bin/` | `jj-land`, `jj-agent-event`, `jj-agent-reflect` |
| `config/jj-config-snippet.toml` | `[git]` safety settings and the `park`/`land`/`orphans` aliases |
| `hooks/` | Claude Code hooks (world-watch, session-end); adapt for other hosts |
| `tests/multi-writer-hazards.sh` | 23 checks proving the hazards and the guards, on a scratch repo |
| `docs/DESIGN.md` | Design rationale and honest trade-offs |
| `CONTRIBUTING.md` | What a new rule needs before it earns a place |

## Compatibility

Developed and tested against jj **0.44.0**. The test suite asserts the hazards still
exist; when a future jj release fixes one, the corresponding rule shows up as obsolete
instead of lingering forever.

Skills use the open `SKILL.md` format (Claude Code, Codex, OpenCode and others read it).
The hooks are Claude Code-specific; the mechanisms and config are host-agnostic.

## Contributing

Rules here are earned, not invented — a new one needs a reproduction and a named layer.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
