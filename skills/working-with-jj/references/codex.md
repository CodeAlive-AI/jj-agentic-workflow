# Codex integration

JJ agent hooks were retired on 2026-10-16 after a Stop hook replaced a substantive answer with
a landing reminder. Keep this workflow hook-free. Do not register SessionStart, Stop, world-watch,
abandon or subagent handlers. The installer does not change `features.hooks` or trust state.

On this machine Codex hooks are disabled with `[features].hooks = false`, including plugin hooks.
Restart existing agents so they unload previously registered handlers. This does not change normal
Codex approvals or sandbox settings.

## Start and finish a task

Stay in the assigned root. Only when a new workspace is explicitly assigned, prepare it with
`jj-agent prepare <name> -r <full-base-id> --snapshot-caller` from an exclusively owned caller.
Run `jj-agent -R /absolute/workspace doctor`, then `codex -C /absolute/workspace` or open that
folder as a Local project in the desktop app. Set up application dependencies explicitly.

Native Git creation/handoff/archive are not verified JJ lifecycle operations. Git HEAD normally
tracks `@-` and can show the current JJ change as a diff. Use JJ for bookmark/conflict/ancestry checks.

Check state, land or park your own changes, and invoke `jj-agent finish [--remove]` explicitly.
Do not move an active default checkout. Provide the substantive answer the user asked for;
VCS details belong in a short relevant delivery note, not a substituted final response.

Use read-only `jj --ignore-working-copy --at-op=@` observations when reassessing shared state.
The explicit-command installer preserves unrelated settings and records rollback copies. Old
receipts may contain hooks: do not restore them without a new explicit request.
