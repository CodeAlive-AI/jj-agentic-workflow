---
name: working-with-jj
description: Use Jujutsu safely in any jj-enabled repository. Use when changing files, mutating version control, recovering work, resolving conflicts, coordinating workspaces, or preparing a push when `jj root` succeeds. Do not use outside jj repositories unless explicitly migrating one.
---

# Work with jj

Baseline: **jj 0.46+**, **Git 2.42+** for colocated workspaces. Load
`maintaining-vcs-hygiene` and any repository-specific companion alongside this skill.

## Establish ownership

Run `jj --ignore-working-copy --at-op=@ root` in the assigned directory. If it fails, do not
apply this skill unless explicitly migrating a repository. Stay in the assigned write root.
Never create a branch, worktree or workspace without a user request or launcher assignment.
If another writer owns the checkout, inspect only; `jj new` there still moves their working copy.

For an assigned new workspace use `jj-agent prepare <name> -r <full-base-id> --snapshot-caller`
from an exclusively owned caller, then `jj-agent -R <new-root> doctor`. Creation snapshots the
caller. Existing active workspaces stay unchanged. Doctor checks VCS roots, not dependencies;
run the project's explicit setup and readiness checks in the new root.

Read [workspace-lifecycle.md](references/workspace-lifecycle.md) for prepare/finish and ownership,
[codex.md](references/codex.md) for Codex, or [claude-code.md](references/claude-code.md) for Claude.
Parallel writers need separately assigned roots. Pass the exact root to each delegate.

## Observe without changing state

Ordinary jj commands can snapshot files and merge operation heads. Inspect with
`jj --ignore-working-copy --at-op=@ <command>`; never run bare commands in another writer's root.
A failure to inspect is not evidence that nothing changed. For your own mutations, run `jj status`
afterward to verify the result.

Git is read-only in a colocated repository; mutations go through jj, non-interactively.
Git HEAD normally tracks `@-`, not `@`, and is detached. Git UI status can show your entire current
JJ change. Do not fix branch-dependent tools with `git checkout`; use a separately authorized
scratch clone. JJ is authoritative for conflicted bookmarks and ancestry.

A conflicted bookmark (`main??`) is ambiguous, and a divergent change has multiple commit
versions. Stop and reconcile before integration or publication. Read
[parallel-agents.md](references/parallel-agents.md). A revset matching nothing returns empty,
not an error: check surprising absence a second way. Judge ancestry with `A::B`, not a listing.

## Describe and edit

Describe intent before the first edit, keep one logical unit per change, and refine the message
as understanding improves. Follow the attribution and description rules in `maintaining-vcs-hygiene`.

```sh
jj describe -m "<intent>"
# edit and test
jj status
jj diff --git
jj new -m "<next logical unit>"
```

Always supply messages: `describe -m`, `commit -m`, `squash -m` or
`--use-destination-message`, `split -m` with filesets. Do not open an editor, pager or diff TUI.
If an editor fails, recover the message from the reported `*.jjdescription` path.
For prior intent use `jj file annotate <path>` then `jj show <change-id>`; read-only Git `log -L`
is available for line-range history.

By default new non-ignored files enter the next snapshot. Establish narrow ignore rules before
work starts. Ignoring an already tracked file does not untrack it: `jj file untrack <path>` keeps
it on disk. A captured secret remains in evolution history after untracking; report the exposure
and need for rotation, not a completed cleanup. See [secrets-and-litter.md](references/secrets-and-litter.md).
If the new-file size limit blocks snapshots, follow the one-shot hint or deliberately configure
`snapshot.max-new-file-size`; work is not recorded while snapshotting fails.

## Land or park your work

By session end your work must be landed or parked, with blockers reported. Landing your finished
stack locally is the default unless project/user policy says otherwise. Integrating others' work,
pushing, releasing or deploying needs explicit authorization. Inspectors do not finish an owner's work.

- `jj land [<rev>] [--to <bookmark>]`: guarded forward-only trunk move; default revision `@-`.
  Refuses conflicted trunk/stacks, divergent changes, sideways/backwards moves, missing published
  ancestry, ambiguous targets, repository-forbidden files and a failing repository `land.check`
  (a fix in the change, never a bypass). Follow its scoped recovery hint;
  do not bypass it with raw `jj bookmark set main`. Read every warning and hanging-heads report.
- `jj park <name> [<rev>]`: names work `parked/<name>`. Positional arguments, no flags. Default
  `@` when non-empty or described, otherwise `@-`. Verify the resulting commit ID.
- `jj orphans`: non-empty heads unreachable from bookmarks. Integrate, park or report relevant
  items; never silently discard another writer's heads.

Landing moves a bookmark, not another workspace's files. Report the landing and write root
separately. Never reset/move an active default checkout; a clean recorded commit does not prove
its disk has no unsaved edits. In managed workspaces, run `jj-agent finish`; removal is a separate
explicit `--remove` step that refuses ignored/untracked files. Stop is a turn boundary, not cleanup.

Before an authorized push, verify local trunk is contained in the exact push tip with
`jj log -r 'main & ~::<push-tip>'`: empty output or stop. Use an explicit remote and bookmark;
see [publishing.md](references/publishing.md). Do not assume the new default push revset matches
project gates. Multi-remote publication is not enabled by this package.

## Recover forward

Inspect operation/evolution history to locate lost work, then use scoped `jj new <lost-commit>`,
`jj restore --from <rev>`, `jj describe`, or `jj abandon` to bring the intended state forward.
Before destructive commands resolve and inspect the target, then pass its full commit ID.
Do not reuse a stale revision variable or moving `@`/`@-` for abandonment.

`jj abandon` can delete bookmarks and rebase descendants, bypassing landing guards. Abandon only
your own unlanded change, never bookmark-reachable history. The host guard covers detected direct
shell invocations; it is not a shell sandbox or a substitute for ownership.

JJ 0.46 records workspace metadata and refuses cross-workspace undo/redo. An intentional undo
still requires inspecting the operation and confirming exclusive ownership. Never force past
that refusal. Old operations may lack metadata; two writers in one workspace share an identity.
`jj op restore` remains repository-wide and requires exclusive maintenance. Mutating under
`--at-op` forks the operation log: use it only for inspection in this workflow.

If stale, inspect the operation history before `jj workspace update-stale`: it may create a
recovery commit from disk. Do not integrate or push conflicts. Detailed recovery evidence:
[parallel-agents.md](references/parallel-agents.md); mixed changes:
[history-cleanup.md](references/history-cleanup.md).

## Handoff and onboarding

Report write root, checks, conflicts, remaining work, **change ID**, **full commit ID**, and
**operation ID**. A change ID identifies the evolving change; the commit ID identifies the exact
version; the operation identifies the observed repository state. Recheck before acting later.

For machine/project setup and where rules belong, read [onboarding.md](references/onboarding.md).
Keep shared instructions in skills, host mechanisms in configuration, and project facts in AGENTS.md.
