# Claude Code integration

The selected user hooks are sensitive-file edit protection, read-only JJ context at SessionStart
and PostCompact, and advisory description checks after Bash tools. ARAI's existing push gate and
cloud setup stay project-scoped. Do not register Stop, SubagentStop, abandon or world-watch hooks.

`jj-context.py` never claims a workspace. `jj-attribution.py` checks only the commit ID emitted in
the successful direct JJ command's tool result; it never reads neighbouring `@-` by assumption or
runs repository-provided checker code. It skips ambiguous/compound commands with an observable
not-checked result where evidence is missing. All JJ inspection is non-snapshotting. Advice uses
additionalContext with exit 0; it cannot block completion and never rewrites descriptions.

The lifecycle candidate `jj-claude-worktree.py` is not activated in ARAI. Its WorktreeCreate
registers a child with full sparsity while ignoring the caller, then updates only the new child's
stale working copy. Saved caller state is copied; unsaved caller files remain untouched. The
manifest records the creating Claude session and host. Removal refuses another owner/project,
unaddressed work and ignored/untracked files. It never infers disposal permission.

Live Claude 2.1.300 created the colocated child and received correct context without changing the
caller. ExitWorktree(action=remove) could not check its state and refused before WorktreeRemove
was dispatched, including with a local origin configured. Do not force past that refusal or pair
a creation hook with native Git cleanup. Both registrations stay pending a host-compatible design.
Use explicit `jj-agent prepare` and `finish --remove` meanwhile.

A hook-contract test is not live dispatch evidence. Restart Claude after settings changes.
