# jj-agentic-workflow

A practical methodology for running coding agents — including several in parallel — on
[Jujutsu (jj)](https://github.com/jj-vcs/jj) repositories, without them destroying each
other's work.

It is not a plugin and not bound to any project. It is a set of **skills** (instructions
agents load on demand), **mechanisms** (guarded wrappers, config that enforces the
rules the skills state), and **tests** that prove the hazards the rules guard against are
real on the current jj version.

## Install: hand this to your agent

You do not install this by hand. Give your agent the repository URL (or a local clone
path) and say:

> Read AGENTS.md in this repository and install the workflow on this machine, then
> onboard my projects.

[`AGENTS.md`](AGENTS.md) is a complete, agent-executable procedure: it installs the
mechanisms and config, retires old JJ hook registrations, places the skills, runs the test suite
to verify the installation, and then onboards your repositories following
[`skills/working-with-jj/references/onboarding.md`](skills/working-with-jj/references/onboarding.md)
— which lives inside the skill, so an already-installed agent can re-onboard any new
project later without this repository at hand. The installer backs up touched settings, preserves unrelated entries, and reports its rollback
receipt. Active workspaces are not migrated.

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
  moved into explicit wrappers and config; the skills only carry what cannot be mechanised.
- **It self-verifies and self-corrects.** The test suite asserts the hazards are still
  real on your jj version, and the built-in reflection loop reviews recorded guard events
  to propose moving rules between layers — including deleting them.

## Why this exists

Agents differ from human committers in three ways: they lose context (compaction,
restarts), they run in parallel with humans and other agents, and they generate volume
cheaply. jj is the best VCS substrate for that — automatic snapshotting, first-class
conflicts, cheap workspaces — but several of its properties are actively dangerous in a
multi-writer repository, and none of them are documented as such:

- `jj op restore` rewinds shared repository state. JJ 0.46 guards `undo`/`redo` across
  workspaces, but shared-workspace writers and old operations still require ownership checks.
- Ordinary reads can mutate state: even `jj status` snapshots the working copy, absorbing
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
3. **Explicit completion** — check state and land/park within the task; no response/Stop hooks.
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
| `bin/` | `jj-land`, `jj-agent`, `jj-agent-install`, event and reflection tools |
| `config/jj-config-snippet.toml` | `[git]` safety settings and the `park`/`land`/`orphans` aliases |
| `lib/` | Shared library for explicitly invoked workspace commands |
| `hooks/` | Explicitly selected context/action handlers plus retired regression fixtures |
| `tests/` | Hazard, lifecycle, hook-contract and installer/rollback tests in temporary repos |
| `docs/DESIGN.md` | Design rationale and honest trade-offs |
| `CONTRIBUTING.md` | What a new rule needs before it earns a place |

## Compatibility

Current baseline: **jj 0.46.0**, Git **2.42+**, Python **3.11+** for the installer.
New child workspaces use JJ's native Git colocation. Existing active workspaces stay unchanged.
See [workspace lifecycle](skills/working-with-jj/references/workspace-lifecycle.md),
[Codex integration](skills/working-with-jj/references/codex.md), and
[Claude integration](skills/working-with-jj/references/claude-code.md).

Skills share one canonical source across hosts. **Completion-blocking JJ hooks were retired on 2026-10-16**
after a Stop hook displaced a substantive answer. The default installer adds no hooks. Explicit
selection may add read-only context and action-specific checks; plugin subscriptions must be
controlled separately before enabling Codex hooks. See the [selected-hook report](docs/SELECTED-HOOKS-2026-10-16.md).

The [0.46 validation report](docs/VALIDATION-0.46.md) records installed versions, test evidence,
host limitations and rollback procedures.

## Contributing

Rules here are earned, not invented — a new one needs a reproduction and a named layer.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Useful links

- [Jujutsu (jj)](https://github.com/jj-vcs/jj) — the VCS everything here is built on, and
  its [official documentation](https://jj-vcs.github.io/jj/latest/).
- [VisualJJ](https://www.visualjj.com/) — a jj extension for VS Code, JetBrains IDEs and
  Visual Studio. A graphical view of the operation log and the change graph is the fastest
  way for a human to check what agents did to a repository, and to recover from an
  operation without guessing at revsets.
- [agentic-jayjay](https://github.com/CodeAlive-AI/agentic-jayjay) — a native macOS GUI
  for jj (Rust + SwiftUI): DAG graph, side-by-side diffs, interdiff, conflict resolution.
  Useful when supervising parallel agents, where reading a graph beats reading log output.

## License

MIT — see [LICENSE](LICENSE).
