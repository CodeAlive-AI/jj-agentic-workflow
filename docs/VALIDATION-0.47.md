# jj 0.47.1 validation — 2026-11-17

Upgrade of the owner's Mac and the dev VM `dev-docker-sg` from jj 0.46.0 to **0.47.1**, after
qualifying this workflow on the new binary. Research that found the blocker:
[benchmarks/2026-11-06-jj047](benchmarks/2026-11-06-jj047/README.md).

## What broke and what changed

| Area | On 0.47.1 | Change |
|---|---|---|
| `jj-agent prepare` (default, saved state) | `workspace add --ignore-working-copy` refused: "This command must be able to update the working copy" | Reads the operation ID, resolves base and caller commit there, runs `jj --at-op=<full ID> workspace add`; verifies child parent, unchanged caller commit, roots. `update-stale` step removed: the child is materialized directly |
| `--snapshot-caller`, Claude lifecycle hook | Same failure via `prepare` | Fixed by the same change |
| `finish`, `finish --remove`, `survey`, `doctor` | Pass unchanged | — |
| `.jj/working_copy/checkout` parsing (forgotten workspaces) | `Checkout` proto unchanged (fields 2 and 3) | — |
| `jj-context`, `jj-attribution` hooks | Pass, including real `describe` output | — |
| `jj-land`, `park`, `orphans` aliases | Pass (hazard suite, alias smoke test) | — |
| `jj undo` in the caller after `workspace add` | Now undoes the child's initial commit, leaving it stale (0.46 refused) | New hazard check; skill and lifecycle rule: discard with `finish --remove` |
| Delete/update bookmark conflict | `bookmark list` shows `+ (absent)`; `self.added_targets()` is `List<Option<Commit>>` | Reference note: test each item, never count revset targets |
| `Timestamp.format()` | jiff syntax: `%+`, `%v` fail; `%Z` is an abbreviation | Skill note; our `%Y-%m-%d[ %H:%M]` formats are unaffected |

The operation-pinned `workspace add` is the workflow's one mutation under `--at-op`. jj's own
`check_new_working_copy_writable` accepts `--at-op` for this command
([add.rs](https://github.com/jj-vcs/jj/blob/v0.47.1/cli/src/commands/workspace/add.rs)); an exact
ID loads without snapshotting the caller, and the new workspace's helper still updates its own
working copy ([cli_util.rs](https://github.com/jj-vcs/jj/blob/v0.47.1/cli/src/cli_util.rs)).
A new test injects another writer's operation between the read and the creation: jj reconciles the
two heads, the child keeps its base and the caller keeps its commit and unsaved file.

## Evidence

Binaries: official release archives, SHA-256 equal to the GitHub release asset digests
(`aarch64-apple-darwin` `50129b52…2255`, `x86_64-unknown-linux-musl` `d4b657f6…cad7`). jj publishes
no GitHub artifact attestations for 0.47.1 (`gh attestation verify` returns 404).

| Suite | Mac (arm64, 0.47.1) | VM (x86_64 musl, 0.47.1) |
|---|---|---|
| `tests/test_workspace_integration.py` | 22 passed | 22 passed |
| `tests/test_install.py` | 4 passed | 4 passed |
| `tests/test_selected_hooks.py` | 7 passed | 7 passed |
| `tests/multi-writer-hazards.sh` | 56 passed | 56 passed |

Before the fix, on 0.47.1: one integration error and three selected-hook failures, all from
`prepare`; hazards 55/55. The new undo hazard fails on 0.46.0, as intended. The fixtures use
temporary repositories only.

Not verified: live Codex/Claude hook dispatch on the new binary, Git signing and pushes to a real
remote, Windows.
