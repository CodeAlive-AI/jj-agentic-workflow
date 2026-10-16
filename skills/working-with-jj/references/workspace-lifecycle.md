# Explicit workspace lifecycle (jj 0.46+)

Use this only after a user or launcher assigns a new workspace. Existing active workspaces
are not migrated, reset, claimed or removed by the installer.

## Prepare

The caller must be exclusively yours. JJ 0.46 snapshots the caller during `workspace add`;
`--ignore-working-copy` fails after partial creation and is not a safe workaround.

```sh
jj-agent prepare task-name -r <full-base-commit-id> --snapshot-caller
jj-agent -R /absolute/new/workspace doctor
```

Default destination: `<caller>/.workspaces/<name>`. It must be ignored before creation.
Alternatively pass `--destination /absolute/separate/path`. The wrapper resolves exactly one
base before creating, locks its own lifecycle operations, uses `--colocate`, and verifies `@-`
and matching Git/JJ roots. Partial errors retain evidence: inspect before retrying. The lock
does not serialize arbitrary jj commands or other writers.

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
assigned workspaces. Do not install JJ session/subagent hooks.

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
