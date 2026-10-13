# Package 1 validation — 2026-10-13

## Installed

- Homebrew JJ upgraded from 0.45.1 to **0.46.0**. The old keg remains available; no automatic
  downgrade of stores written by a newer JJ is promised.
- Git **2.55.0**, Python **3.14.7**; minimums for this package are Git 2.42 and Python 3.11.
- Shared runtime release **769a918494d21d50** installed under
  `~/.local/share/jj-agentic-workflow/releases/`; `~/.local/bin/jj-agent` points to it.
- Codex/Claude user hook configuration merged with backups; unrelated settings and handlers
  preserved. Old installed hook scripts retained for sessions already using them.
- Codex `features.hooks=true`. All seven JJ hooks were individually reviewed/trusted through
  the native `/hooks` UI; unrelated untrusted handlers were left as they were.
- Existing skill symlinks for both hosts still point to this repository. Core skill bodies
  are approximately 1815 and 1987 tokens; skill review reports zero errors/warnings.
- No active project workspace was converted, rebased, reset, snapshotted or removed. Changes
  to VCS state were confined to this workflow checkout and disposable pilot repositories.

## Evidence

| Check | Result |
|---|---|
| `bash tests/multi-writer-hazards.sh` | 42 passed, 0 failed |
| `python3 -B tests/test_workspace_integration.py` | 9 passed |
| `python3 -B tests/test_install.py` | 1 passed; preservation, repeat install, rollback and concurrent edit refusal |
| Codex CLI 0.162.1 `hooks/list` | 7 JJ hooks enabled/trusted, no load errors/warnings |
| Desktop bundled CLI 0.162.0-alpha.17.2 `hooks/list` | Same 7 hooks enabled/trusted, no load errors/warnings |
| Actual Codex CLI ephemeral turn | SessionStart JJ context received; direct `jj abandon main` blocked by bookmark guard; doctor roots agree |
| Claude event contracts with real JJ/Git | WorktreeCreate path, colocation and guarded WorktreeRemove pass |
| Claude live runtime | Not run: host unavailable |
| Native desktop Git create/handoff/archive | Not validated or adopted; use prepared JJ workspace as Local project |

The initial generic hooks validator rejected modern event names because its event list was old.
After supplying the documented SubagentStart/PostCompact/WorktreeCreate/WorktreeRemove names
to that validator in memory, all three installed documents passed structural validation.
Codex's own runtime independently accepted the definitions. Claude contract tests do not replace
a live Claude run. Startup warnings for unrelated unavailable CodeAlive MCP servers did not affect
the Codex pilot; their configuration was not changed.

## Findings that changed the implementation

1. JJ 0.46 `workspace add --ignore-working-copy` creates partial state, then errors. Normal
   creation snapshots the caller. Preparation requires `--snapshot-caller` and exclusive caller
   ownership; no hidden fallback or migration of active workspaces.
2. Child `.jj/repo` is a pointer file. The old directory-based world watcher could miss every
   update. It now reads operation IDs through the public CLI without snapshots/op merges.
3. Cross-workspace `undo` is refused on 0.46. `op restore` still damages the other workspace in
   the hazard fixture. Forward recovery remains the shared-repository default.
4. Stop is scoped to a managed workspace's recorded main owner. An inspecting session and
   inherited subagents do not land/park the owner's work. Stop never deletes a directory.
5. Removal checks task lineage plus ignored/untracked filenames. A parked commit alone does
   not authorize deleting ignored files. The test confirms explicit disposal preserves parked work.

## Operation and rollback

Restart hosts after configuration changes. For new tasks, use the
[workspace lifecycle](../skills/working-with-jj/references/workspace-lifecycle.md) and the
[Codex](../skills/working-with-jj/references/codex.md) or
[Claude](../skills/working-with-jj/references/claude-code.md) adapter guide.

Claude lifecycle replacement is installed only in the disposable pilot. Enable it per inactive
JJ project with `bin/jj-agent-install --project /absolute/root --project-only`; it is deliberately
absent from global settings and existing active projects.

Installation receipts and previous settings are under `~/.local/state/jj-agent/installations/`:

- `1791885925629172000/receipt.json`: initial install, including the previous hooks flag.
- `1791886169724707000/receipt.json`: final runtime and hook paths.

Use `bin/jj-agent-install --rollback /absolute/receipt.json` in reverse installation order.
Native hook trust updates the Codex config after installation; a full-file rollback can therefore
refuse that file. In that case review and restore only the intended settings from the backup,
preserving later edits. Never force overwrite concurrent changes. Immutable release directories
and receipts remain for diagnosis; rollback does not downgrade JJ.

Dependencies, multi-remote push, `file edit/delete`, and live Claude/Desktop lifecycle testing
remain outside this first package. A VCS doctor pass is not an application readiness check.

## Sources

- [JJ 0.46 release](https://github.com/jj-vcs/jj/releases/tag/v0.46.0)
- [JJ workspace creation implementation](https://github.com/jj-vcs/jj/blob/v0.46.0/cli/src/commands/workspace/add.rs)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Claude hook contracts](https://code.claude.com/docs/en/hooks)
