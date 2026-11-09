# Explicit workspace lifecycle (jj 0.46+)

Use this only after a user or launcher assigns a new workspace. Existing active workspaces
are not migrated, reset, claimed or removed by the installer.

## Prepare

Preparation defaults to saved JJ state and never snapshots the caller. It explicitly combines
`workspace add --ignore-working-copy --sparse-patterns full --colocate` with `workspace update-stale`
in the new metadata-only child. The plain default sparse-copy mode fails partway with ignored
working-copy updates; no failed mode is retried as a hidden fallback.

```sh
jj-agent prepare task-name -r <full-base-commit-id>
jj-agent -R /absolute/new/workspace doctor
```

Unsaved caller files are excluded. The child materializes the full tree, not inherited sparse
patterns. For an explicitly owned caller only, `--snapshot-caller` deliberately requests the old
snapshotting mode. The wrapper resolves one base, serializes its lifecycle calls and verifies the
child's parent and Git/JJ roots. Partial errors retain evidence; inspect before retrying.

Default destination: `<caller>/.workspaces/<name>`, ignored before creation. An explicit external
`--destination` is also supported. The metadata lock does not serialize arbitrary writers.

Work on the described initial change and its descendants. If you start an unrelated stack,
park the previous one first. The lifecycle cannot infer ownership of unrelated orphaned changes.
Dependency provisioning is project-specific: run the repository's explicit setup command in the
new root, then its readiness check. Doctor checks VCS integration, not application dependencies.
Do not copy credential files, installed dependencies or ignored output from another workspace.

## Own

The manifest in `.jj/jj-agent.json` records root, store, base, initial change and owner session.
`--owner-session <id>` records an optional owner at creation. Without it the manifest remains
unbound; there is no SessionStart auto-claim or automatic inspect-only notice. Establish ownership
explicitly. Always pass the exact write root to delegates; parallel writers need separately
assigned workspaces. Selected read-only context hooks do not acquire ownership or provide isolation.

## Finish

Run checks, land your stack or park it under an explicit bookmark, and report change ID, full
commit ID and operation ID. Only then:

```sh
jj-agent finish
jj-agent finish --remove
```

From another directory: `jj-agent -R <workspace> finish --remove`. It works for every secondary
workspace: one made by `prepare` (its own work is what lies under `@` after its base, plus its
initial change and what stacks on it, except what another workspace's working copy stands on, so a
checkout that followed `main` onto the landed task does not block it; once a bookmark holds the
initial change, a stacked commit whose `Agent-Session:` trailers name only other sessions is that
session's, not this task's, while unsigned ones still count), one made with raw
`jj workspace add` (adopted: its own work is
everything under `@` that no bookmark keeps), and a directory jj already forgot (judged by its
last snapshot; files changed after it count as unsaved). It refuses only unaddressed work,
conflicts, or untracked/ignored files that would be lost, and then prints the exact command with
`--discard-path` for what it listed; move anything worth keeping out first and never discard
credentials by default. Rebuildable caches (`node_modules`, `__pycache__`, `.venv`, `.next`, …)
are discarded and reported; a repository adds its own cache names, one per line, in a tracked
`.jj-agent-regenerable` file at its root (bare names, no paths). The primary checkout is never removed. The recovery receipt lives
outside the removed directory under `~/.local/state/jj-agent/finished/`.

Whoever lands or integrates another workspace's parked work (a coordinator landing a delegate's
change, or a copy of it) finishes that workspace too once its work is in: the worker has already
reported and will not come back to it.

`jj-agent -R <repo> survey [--idle-hours 24]` reports every workspace of the repository without
changing anything: `removable` (with the exact `finish --remove` command), `blocked` (unlanded
commits with their `Agent-Session:` owners, or files jj has not recorded) or `active` (open files
or used recently). It cannot know whether an idle owner session will be resumed; ask a live owner
before removing its workspace.

Never `rm -rf` a workspace root: jj keeps a stale record and unlanded work is lost silently.
The selected profile's PreToolUse hook redirects such a command to `finish --remove`.
Stop/SubagentStop never remove a workspace, and SessionEnd is not configured as a cleanup event.

Deletion is safe only with exclusive ownership: another process can write after the checks.
Stop writers before removing. The metadata lock is not a filesystem lock against arbitrary tools.
