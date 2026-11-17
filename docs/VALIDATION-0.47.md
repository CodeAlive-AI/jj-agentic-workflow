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

## Problems found during the rollout, and their fixes

| Problem | Evidence | Fix |
|---|---|---|
| `jj land @` right after an edit landed trunk on an empty divergent twin (also on 0.46) | Every read ignored the working copy; the final `bookmark set` snapshotted and revived the stale `@` | Snapshot first; own `@` gets `jj new` before the move; another workspace's `@` refused |
| A bookmark on a working-copy commit follows every later snapshot | After `jj land @`, a later edit moved `main` | Same change: the landed commit is never left as a working copy |
| Delete/update trunk conflict seen as one target | `bookmarks(exact:"main")` returns one commit; `jj log -r main` errors | Guard 0 reads the bookmark's `conflict`; own recovery hint |
| Installer linked only `jj-agent`; `jj-land` was a hand copy from 2026-10-18 on both machines | SHA-256 `90bb7844…` installed vs `b72e5619…` in source | All four public commands link to the release, atomically, with backups in the receipt |
| `survey` crashed with a traceback on the VM | `lsof +D` per workspace outlived the 120 s subprocess timeout under load; `TimeoutExpired` was not caught | One open-file pass per survey (`/proc` on Linux, one `lsof` on macOS); a timeout or a vanished file is a row reason |
| Deprecated `git.sign-on-push = true` in two CodeAlive repository configs | 0.47.1 printed a warning on every command there | Replaced with the equivalent `revsets.git-sign-on-push = "~signed() & mine()"` |
| ARAI's own pre-push hook denies a heredoc that only mentions `jj git push` | Quoted strings are stripped, heredoc bodies are not | Handed to the ARAI coordinator; not in this repository |

With these fixes: hazards 61 passed (5 new in section 13; the previous `jj-land` fails exactly
those that test it), integration 23 (VM; the two survey tests also on the Mac), installer 5,
selected hooks 7. A read-only ARAI survey took 33 s on the Mac and 58–117 s per task clone on the
VM; side by side with `lsof +D`, the one-pass listing found the same processes in 5 of 6 active
workspaces, the sixth differing by one short-lived `git`.

## Rollout

| | Mac (arm64) | dev-docker-sg (x86_64) |
|---|---|---|
| jj | Homebrew `jj 0.47.1` (`brew upgrade jj`, old keg kept) | official musl build at `~/.local/share/jj/releases/0.47.1/jj`; `/usr/local/bin/jj` swapped by `ln -sfn` + `mv -T` |
| jj-agent release | `cc11ba4cd85c11c7` (first `3da837d86fee5ad2`, before the fixes above) | the same two releases |
| Public commands | `jj-agent`, `jj-land`, `jj-agent-event`, `jj-agent-reflect` link to the release | same; `/usr/local/bin/jj-land` and `jj-agent` resolve through them |
| Skills | canonical checkout moved onto `main`; both hosts read it through symlinks | copies in `~/.agents/skills/` replaced from the landed commit |
| Selected hooks | unchanged: Claude and Codex still run release `b2783b5e4f42fd2c`, which passes on 0.47.1 | none installed |

The hooks were left on their release on purpose: Codex stores a `trusted_hash` per hook, so new
command paths would switch the JJ hooks off, the ARAI push router included, until the owner
reviews them in Codex `/hooks`. Move them with
`bin/jj-agent-install --observational-hooks --codex-push-project /Users/rodio/my-projects/arai`
only together with that review.

Rollback (no store migration was observed; a read-only survey with 0.46.0 after the upgrade gave
the same result as 0.47.1):

- Mac: `ln -sf ../Cellar/jj/0.46.0/bin/jj /opt/homebrew/bin/jj` (copy also at
  `~/.local/share/jj/releases/0.46.0/jj`), then
  `bin/jj-agent-install --rollback` with the receipts under `~/.local/state/jj-agent/installations/`
  in reverse order; the hand-copied `jj-land` of 2026-10-18 is in
  `~/.local/state/jj-agent/manual-backups/20261118T000002/`.
- VM: `sudo ln -sfn ~/.local/share/jj/releases/0.46.0/jj /usr/local/bin/.jj.new && sudo mv -Tf
  /usr/local/bin/.jj.new /usr/local/bin/jj`, the receipts the same way; previous skills, `jj-land`
  and the old link target are in `~/.local/state/jj-agent/manual-backups/20261117T160056/`.
- The prepare in releases `3da837d8…` and later needs jj 0.47; roll jj-agent back with jj.
