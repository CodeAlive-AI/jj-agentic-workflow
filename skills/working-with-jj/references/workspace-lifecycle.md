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

Finish snapshots the owned workspace and refuses unaddressed work in the task lineage or
conflicts. Removal additionally checks ignored/untracked filenames, without reading contents.
Preserve them first. Only explicitly disposable paths may use `--discard-path <relative-path>`;
never discard credentials by default. The recovery receipt lives outside the removed directory
under `~/.local/state/jj-agent/finished/`.

JJ `workspace remove` deletes a directory; snapshots do not protect ignored files. Do not use
raw removal or Git host cleanup as a shortcut. `workspace forget` only forgets metadata and is a
different operation. The wrapper refuses unmanaged workspaces. Stop/SubagentStop never remove
a workspace, and SessionEnd is not configured as a cleanup event.

Deletion is safe only with exclusive ownership: another process can write after the checks.
Stop writers before removing. The metadata lock is not a filesystem lock against arbitrary tools.
