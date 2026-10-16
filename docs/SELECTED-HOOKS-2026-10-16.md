# Selected hooks — 2026-10-16

The user selected eight functions in the interactive catalogue. Six are configured (nine host
subscriptions); the paired Claude lifecycle functions are prepared and tested locally, but not
activated because the native removal pilot failed before dispatching WorktreeRemove.

| Function | Codex | Claude Code |
|---|---|---|
| Sensitive-file edit confirmation | Not selected | Existing user hook preserved |
| ARAI push gate | Scoped user-level router; old project subscription disabled | Existing project hook preserved |
| Description attribution advice | Not selected | New PostToolUse advisory |
| Cloud environment setup | Not applicable | Existing ARAI cloud-only setup preserved |
| JJ context at session start | New read-only SessionStart | New read-only SessionStart |
| JJ context after compaction | New read-only PostCompact | New read-only PostCompact |
| JJ workspace creation through Claude | Not selected | Prepared, not registered |
| JJ workspace removal through Claude | Not selected | Prepared, not registered |

## Corrections

`jj-context.py` only reports the saved root, commit, operation and Git/JJ agreement. It does not
claim ownership, snapshot files or handle Stop. Its output cannot make a completion decision.

`jj-attribution.py` checks the commit ID actually reported by the just-completed direct JJ
command. It does not inspect a guessed neighbouring commit, invoke repository checker code,
rewrite descriptions or block a response. All reads use `--ignore-working-copy --at-op=@`.
If the tool result cannot identify one changed commit, it reports that the check was not made.
Compound/redirected commands are outside its direct-command evidence boundary.
Revision-selected describe/commit, squash/split and new --no-edit are not checked: their printed
working-copy status does not identify the changed target reliably.

The previous Codex project push hook expanded `$(jj root)` before every Bash call, so even
non-push commands could snapshot a working copy. It is now disabled through native hook state.
The replacement user-level `jj-push-gate.py --project <ARAI-root>` does no JJ work for ordinary
commands, resolves scope without snapshots, and delegates actual push checking to ARAI's existing
script only for that shared repository. Ambiguous cd/-R/-C routing is refused. The existing
project script's behaviour on an actual push is preserved; it is not claimed to be pure/read-only.
No ARAI source or active workspace configuration was edited.

Default `jj-agent prepare` now uses an explicit two-stage path: native workspace add with ignored
caller and full sparsity, followed by update-stale only in the new child. The plain sparse-copy
mode's earlier partial failure is not retried as a fallback. The child uses saved caller state;
unsaved caller files are neither captured nor copied. `--snapshot-caller` remains an explicit
opt-in mode, not a requirement or an automatic fallback.

The lifecycle candidate binds the new child's creator session and host in its manifest. Removal
requires the same Claude session, exact root and shared project store; other owners, unaddressed
work and ignored/untracked files are refused. These checks do not prevent arbitrary external
writers racing a removal, so exclusive ownership is still required.

## Verification

- 19 Python tests passed: 6 new behavioural tests, 4 installer tests, 9 existing integration tests.
- The multi-writer hazard suite passed all 45 checks. The six selected-hook tests were rerun after
  adding refusal to guess attribution targets for revision-selected commands and squash/split.
- New regressions verify no caller snapshot, no ownership mutation by context hooks, no Stop
  output, exact reported-commit attribution, no neighbouring-commit checking, project-scoped push
  routing, wrong-owner removal refusal, and ignored-file preservation.
- Installer profiles are explicit. A default fresh install creates no host configuration. The
  observational profile creates no Stop/SubagentStop handlers and does not enable the global
  Codex hook switch itself.
- Codex CLI 0.162.1 and desktop bundled CLI 0.162.0-alpha.17.2 are checked using native hooks/list.
  Only three user handlers are enabled/trusted: SessionStart, PostCompact and the ARAI push router.
  All five installed Warp plugin subscriptions and the old project push handler are disabled.
- Codex live ephemeral turn received root/commit/operation and ended with OBSERVATION_OK.
- Claude 2.1.300 live tool turn received advice about the exact described commit's missing Model
  and Agent-Session trailers, left the description as instructed, and ended with ATTRIBUTION_OK.
- PostCompact response logic is fixture-tested and accepted by both native schemas; an actual
  compaction was not forced.
- Existing cloud setup was preserved, not executed on this Mac. The real ARAI deployment gate
  was preserved, not run against or pushed to a production remote.

## Claude lifecycle limit

The live --worktree pilot successfully dispatched WorktreeCreate, produced a colocated JJ child,
and injected correct read-only context. The caller's saved commit remained unchanged while an
unsaved caller-only fixture file stayed out of the child.

ExitWorktree(action=remove) refused because Claude could not determine the JJ worktree's state.
The same failure reproduced with a local bare origin and published main. WorktreeRemove was not
called at all. No discard_changes/force workaround was used. A successful creation alone therefore
does not justify deploying the pair. Both are absent from ARAI pending a host-compatible design.
Until then use explicit prepare/finish/remove for assigned workspaces.

## Settings and rollback

Only user-level Codex/Claude hook settings, Codex native per-hook state, and the installed runtime
link were changed. Native approval, sandbox, model/provider and unrelated settings were preserved.
Existing active workspaces were not reset, migrated or mass-reconfigured. Restart agents after
settings changes; already-running sessions may hold older definitions.

Backups before enabling the selected profile:
`~/.local/state/jj-agent/selected-hook-backups/1792130123053292000/receipt.json`.
Final runtime installation receipt:
`~/.local/state/jj-agent/installations/1792130999831809000/receipt.json`.
Runtime release: `12d6c06e7b146367` (only the newly reviewed implementations are shipped).

Rollback receipts refuse files edited afterward. Native trust edits config.toml, so restore only
reviewed fields from the backup if a full-file rollback refuses. Do not restore retired blocking
Stop handlers from historical receipts. The previous disabled handler stubs remain untouched.

Sources: [Codex hook trust and per-hook management](https://learn.chatgpt.com/docs/hooks),
[Claude WorktreeCreate/Remove contracts](https://code.claude.com/docs/en/hooks#worktreecreate).
