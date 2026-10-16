# Codex integration

Use only the user's selected hook subscriptions. Completion-blocking JJ/Grok Stop remains retired.
The approved SessionStart/PostCompact handler `jj-context.py` observes root, commit, operation
and Git/JJ agreement with `--ignore-working-copy --at-op=@`. It never snapshots files, writes
ownership or handles Stop. The selected ARAI push router `jj-push-gate.py` inspects roots without
snapshots and delegates actual publication checks only to that repository's existing push gate.

The old project hook command expanded `$(jj root)` before every shell tool. Keep that original
subscription disabled; the scoped user-level router replaces it without editing active workspaces.
Claude-only attribution advice must not be registered in Codex.

Before enabling `[features].hooks`, disable unselected plugin subscriptions using native hook
state. All five Warp hooks remain disabled. Review only the selected definitions through `/hooks`;
new or modified untrusted hooks are skipped. Do not fabricate trust hashes. App/CLI native
`hooks/list` must show the intended enabled/trusted set. Restart hosts after changing settings.

For a newly assigned workspace use `jj-agent prepare <name> -r <full-base-id>`, verify with doctor,
then `codex -C /absolute/root` or open that folder as a Local project. Default preparation does not
snapshot the caller; it checks out saved state into the child only. Dependencies remain explicit.
Git views use detached HEAD at `@-`; JJ remains authoritative for bookmarks and conflicts.

Land/park and `jj-agent finish [--remove]` remain explicit. Native Git create/handoff/archive are
not established JJ lifecycle operations. Do not move an active default checkout or substitute a
VCS reminder for the answer the user requested.
