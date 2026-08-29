---
name: working-with-jj
description: Use Jujutsu safely in any jj-enabled repository. Use when changing files, mutating version control, recovering work, resolving conflicts, coordinating workspaces, or preparing a push when `jj root` succeeds. Do not use outside jj repositories unless explicitly migrating one.
---

# Work with jj

## Iron rules

- Raw Git is read-only in a colocated repository; every VCS mutation goes through jj, non-interactively.
- Run `jj status` after each jj mutation.
- By session end every change is landed (`jj land`) or parked (`jj park <name>`); a floating
  unlanded change is a defect, not a state. Landing your own finished stack on local trunk is the
  default and needs no authorization; integrating other writers' work, pushing, releasing, or
  deploying still requires explicit authorization.
- A conflicted bookmark (`main??`, "Name `main` is conflicted") makes that name an ambiguous
  revset: no ancestry claim about it is meaningful, and `git merge-base` against the colocated
  ref answers about only one side. Reconcile it before reasoning — rebase the unpublished side
  onto `<bookmark>@origin`, never the reverse — and state the divergence to the user rather than
  describing the graph from a listing.
- After `jj land`, read its hanging-heads report: integrate, park, or report each item — never
  ignore it.
- If shared `@` holds a change you did not author, open your own change before editing files.
- Never publish a tip that does not contain the local trunk bookmark: landed-but-unpublished
  work exists exactly there, and pushing around it forks the shared trunk (a conflicted
  bookmark for every other writer). Before `jj git push`, verify with
  `jj log -r 'main & ~::<push-tip>'` — empty output or stop.
- Land trunk with `jj land [<rev>]`, never raw `jj bookmark set main`: it enforces forward-only moves (a sideways move orphans the old line) and refuses conflicted stacks. If it refuses, run the rebase it prints and accept the conflicts — conflicts are recoverable, orphaned lines get lost. `jj orphans` lists unreachable non-empty heads; run it when finishing multi-writer work.
- Where more than one workspace exists, never rewind operations — `jj undo`, `jj redo` and
  `jj op restore` all restore the *repository-wide* view and silently revert concurrent writers
  (measured: `undo` left the caller's own mistake in place and reverted a co-worker's change;
  `op restore` fixed the caller and still reverted the co-worker). Recover forward with
  change-scoped commands instead — `jj describe`, `jj abandon`, `jj restore --from`, or
  `jj new <lost-commit>` — which leave other workspaces untouched. For the same reason `--at-op`
  is inspection-only; mutating under it forks the operation log and can drop bookmarks and
  commits from the visible graph.
- A revset that matches nothing returns empty, not an error, so a wrong query reads as "no such
  commit". String predicates need an explicit pattern kind — `description(substring:"fix")`,
  `description(glob:"wip:*")`; bare `description("fix")` silently matches nothing. Before
  concluding that work is absent, run the same question a second way (`jj log -r 'all()'`,
  `jj evolog`).
- Judge ancestry with an explicit predicate — `jj log -r 'A::B'` or `git merge-base --is-ancestor A B` — never by eyeballing `git log A..B` output: a listing shows reachability, not separateness (one commit listed = exactly one ahead, i.e. a direct descendant).

## Land, park, see (host-provided commands)

These wrappers exist on this machine; prefer them over raw bookmark commands.

- `jj land [<rev>] [--to <bookmark>]` — move trunk to `<rev>` (default `@-`). Refuses: a
  conflicted trunk, a sideways move, a target missing published `@origin` work, conflicted
  commits. On refusal it prints the exact rebase to run — run it, then land again. After any
  land it lists heads hanging outside every bookmark: integrate, park, or report each.
- `jj park <name> [<rev>]` — set `parked/<name>`. Positional arguments only, no flags. Default
  revision: `@` when it is non-empty or described, else `@-`. Verify the printed commit id is
  the change you meant.
- `jj orphans` — non-empty heads unreachable from every bookmark; run when finishing
  multi-writer work.

## Establish the write root

Run `jj root` from the intended repository. If it fails, do not apply this skill unless the task
is explicitly migrating the repository to jj.

Stay in the checkout or workspace where the task started or that the launcher assigned. Never
switch to another checkout of the same repository while writing. Do not create branches, Git
worktrees, or jj workspaces unless the user explicitly asks or a launcher assigns one. Any
`jj workspace add` needs an explicit `-r <resolved commit id>`: without `-r` it starts at the
*parents* of the creator's `@`, and with an ambiguous or conflicted name it registers the workspace
anyway on an unintended base. Verify the new workspace's `@-` before working in it.

In a colocated repository Git's HEAD is normally detached, so tooling that asks for the current
branch (`git branch --show-current`, deploy or publish scripts) sees none and may refuse to run.
Do not "fix" this with `git checkout`; run branch-dependent tooling from a scratch clone.

Load any repository-specific jj companion skill before proceeding, and `maintaining-vcs-hygiene`
for the culture layer (litter, parking, handoff claims).

## Work non-interactively

jj has no read-only commands: `status`, `log`, `diff` and even `op log` first snapshot the working
copy, absorbing whatever the filesystem holds (test output, coverage, editor backups) into the
current change. Inspect with `jj --ignore-working-copy <cmd>` (add `--at-op=@` for the exact
current operation), and never run a bare `jj` command inside a workspace you do not own.

Use jj for every VCS mutation:

```bash
jj describe -m "<intent>"
# edit and test
jj status
jj diff --git
jj new -m "<next logical unit>"
```

- Always pass messages explicitly; never open an editor, pager, TUI, or diff editor. Every
  history command has a non-interactive form: `describe -m`, `commit -m`, `squash -m` or
  `squash --use-destination-message`, `split -m` with filesets. If an editor opens anyway and
  fails, the message text survives at the `*.jjdescription` path in the error; retry with the
  flag, do not retype from memory.
- Keep one logical change per jj change.

## The description carries what the code cannot

In jj the description is a living field, not a post-hoc label: state intent at `jj new -m` and
refine it with `jj describe -m` as understanding improves. What belongs in the first line and the
body is `maintaining-vcs-hygiene` §3. The jj-specific rule is that a placeholder ("next") is
acceptable only while the change is still empty — describe it before its first file edit lands,
because undescribed work is invisible intent.

To find the decision behind a line, use `jj file annotate <path>`, then `jj show <change-id>`
for the description body. Line-range history needs colocated read-only `git log -L` (legal).

## A stray file is committed before you notice

jj has no untracked state: every new file that is not ignored joins the current change the moment
any jj command runs. Ignore rules therefore have to exist *before* work starts, and
`.gitignore` is not retroactive — adding an already-tracked path to it does not untrack the file,
and its later edits keep being snapshotted. Untrack with `jj file untrack <path>` (the file stays
on disk).

Treat a captured secret as an exposed credential, not a tidy-up: after untracking, the value is
still readable from that change's evolution history (`jj evolog`), so say so plainly and have the
credential rotated. Never report the deletion as a fix. Details:
[secrets-and-litter.md](references/secrets-and-litter.md).

Adding a file larger than `snapshot.max-new-file-size` (default 1 MiB, e.g. vendored or
generated sources) makes every jj command fail until resolved — and while snapshotting fails,
new work is not being recorded, so the safety net is off. Follow the one-shot hint from the
error, or raise the limit deliberately with `jj config set --repo snapshot.max-new-file-size`.

## Recover and hand off

Inspect before recovery:

```bash
jj status
jj diff --git
jj op log
jj log -r 'all() & ~::<trunk>'   # work no trunk reaches, including commits no bookmark names
```

Recover forward. Read `jj op log` and `jj evolog` to *find* the state you lost, then bring it
forward with change-scoped commands (`jj new <lost-commit>`, `jj restore --from <rev>`,
`jj describe`, `jj abandon`). Rewinding operations is a whole-repository act: reserve
`jj op restore <operation>` for a single-workspace repository, or when you have confirmed no other
writer has operated since that operation — jj's operation log does not record which workspace made
an entry, so in a shared repository you usually cannot establish that. Never `jj undo`.
If a workspace is stale, another writer rewrote its working-copy commit: inspect `jj op log`
to learn what happened before running `jj workspace update-stale`, because the update can
materialise a recovery commit from disk and bury the original incident. Conflicts may live in
commits, but do not integrate or push a conflicted stack.

At handoff, report the write root, checks run, conflicts, and remaining work, and identify the work
three ways: **change ID** (survives rewrites — the logical identity), **full commit ID** (what the
reader must actually find; squash and rebase replace it), and the **operation ID** the claim was
read at. A report carrying only change IDs sends the next agent looking for a commit that no longer
exists under that hash. Follow
the repository-specific companion for integration, workspace cleanup, or push procedures.

Load only the relevant reference:

- More than one writer in the repository, or work that disappeared:
  [parallel-agents.md](references/parallel-agents.md)
- A stray file, litter, or a captured secret in a change:
  [secrets-and-litter.md](references/secrets-and-litter.md)
- Oversized or mixed changes: [history-cleanup.md](references/history-cleanup.md)
- Authorized bookmark or remote work: [publishing.md](references/publishing.md)
- Wiring a new machine or repository (what goes in CLAUDE.md/AGENTS.md vs config vs skills):
  [onboarding.md](references/onboarding.md)
