# Codex integration

Verified baseline: CLI 0.162.1; bundled desktop CLI 0.162.0-alpha.17.2. Recheck on host upgrades.
Install the common runtime with `bin/jj-agent-install`; it preserves unrelated hooks, enables
`features.hooks`, and prints a rollback receipt. Skills remain in their canonical symlinked root.

Codex command hooks require trust. Review changed definitions through native `/hooks` after
installation; untrusted/modified hooks are skipped. A saved JSON file alone is not proof they
execute. Do not manufacture hashes under `hooks.state` or use a trust bypass as production proof.
Restart the agent after changing settings. App and CLI use the same user configuration, but
their executable versions and native hook validation still need separate checks.

| Event | Common mechanism |
|---|---|
| SessionStart / PostCompact | Current JJ root, commit, operation and host root check |
| SubagentStart | Explicit write root and ownership reminder |
| PreToolUse, `^Bash$` | Guard detected `jj abandon`; failed target inspection refuses |
| PostToolUse, `^Bash$` | Read-only operation/bookmark observation, including child workspaces |
| Stop | Check only the recorded main owner of a managed workspace |
| SubagentStop | Does not claim or finish the parent's work |

Codex normalizes shell tools to Bash; the adapter accepts command strings and argv lists.
Hook `cwd` is the session directory. Keep shell calls in that assigned root; cross-directory
shell routing is not covered as a safe workflow. Changing only a tool workdir does not establish
a new session root. The abandon guard covers detected direct shell commands, not every shell/Python/MCP
indirection. Observation errors are visible diagnostics, never an "unchanged" result.

## Start a task

Prepare an explicitly assigned colocated JJ workspace with `jj-agent prepare`, verify it with
`doctor`, then use `codex -C /absolute/workspace`. In the desktop app, open/add that exact folder
as a Local project. The colocated Git worktree makes Git and JJ discover the same root.

Native Codex Git worktree creation, handoff, commit and archive are not established JJ lifecycle
operations. Use Local mode and the JJ commands above. Root compatibility does not prove native
Git mutations safe. Do not hand an existing active workspace to automatic cleanup.

Git views normally compare against detached HEAD (`@-`), so status can show the whole current
JJ change. Use JJ for authoritative bookmark/conflict/ancestry decisions.

## Finish and rollback

Land/park in the assigned root, then explicit `jj-agent finish [--remove]`. Do not reset the
default checkout to make a UI look clean. Settings rollback:
`bin/jj-agent-install --rollback /absolute/receipt.json`.
Rollback refuses if a touched file changed afterward, to preserve concurrent configuration edits.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees).
