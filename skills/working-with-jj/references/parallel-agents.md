# Parallel writers in one jj repository

Read when more than one agent, session, or workspace writes to the same repository, or when
diagnosing work that "disappeared". Every hazard below was reproduced on jj 0.44.0.

## Operation rewind is repository-wide, so recover forward

The operation log is shared by every workspace, and an operation restores the whole repository
view — not just the caller's part of it. Measured with agent A fixing its own mistake while agent
B had done real work in another workspace since:

| A's recovery | A's own change | B's change |
|---|---|---|
| `jj undo` | mistake **survives** | **reverted** |
| `jj op restore <A's own op>` | fixed | **reverted** |
| `jj abandon @` | gone, as intended | intact |
| `jj describe -m …` | corrected | intact |

`jj undo` is the worst case: it targets the repository's newest operation, which in a multi-writer
repo belongs to whoever moved last, so it reports success while damaging someone else and leaving
the caller's own mistake in place.

Recover forward instead: read `jj op log` and `jj evolog` to find the lost state, then bring it
forward with `jj new <lost-commit>`, `jj restore --from <rev>`, `jj describe`, or `jj abandon`.

Operation rewind remains the right tool for structural damage (a stack rebased wrongly, a
bookmark moved to the wrong side) — but only in a single-workspace repository, or after
confirming no one else has operated since. jj does not record which workspace made an operation:
by default every entry in `jj op log` carries the same `user@host`, so the check usually cannot be
made from the log alone. A workspace can opt in with
`jj config set --workspace operation.username "agent/<name>"`, which makes later forensics
possible.

The same reasoning forbids mutating commands under `--at-op`: they deliberately fork the operation
log, and a fork that is later reconciled can drop bookmarks and commits out of the visible graph.
`--at-op` is an inspection flag.

## A revision resolves when the command runs, not when you decided on it

Two agents shared one working copy. Agent A captured a revision, agent B landed a commit and
moved `@`, and A's next command — `jj abandon $old` — hit B's landed commit. The variable was
honest when it was assigned and wrong when it was used. This is the ordinary shape of the
mistake: an agent thinks in revisions (`@`, `@-`, "the commit I just made"), but jj resolves the
expression at execution time, and in a shared copy the interval between two of your commands is
long enough for someone else to write.

`jj abandon` turns that into trunk damage, because it is the one command that moves a bookmark
without any of `jj land`'s guards. Reproduced on 0.44.0 — abandoning a commit that `main` points
at:

```
Abandoned 1 commits:
  ykontsyl 15ab10bd main | landed work
Deleted bookmarks: main            <- trunk is gone, not moved back
Rebased 1 descendant commits onto parents of abandoned commits.
```

The bookmark is **deleted**, not moved; `--retain-bookmarks` keeps it but moves it to the parent,
which is the backwards move `jj land` refuses. Either way the trunk guard is bypassed by a
command nobody thought of as a trunk command, and jj reports it in the same tone as a success.

Two consequences, in this order:

1. For any destructive command (`abandon`, `restore`, `squash`, `rebase -s`), resolve the target
   and read it in the same breath, then pass the full commit id:
   `jj --ignore-working-copy log -r <expr> --no-graph -T 'commit_id ++ " " ++ bookmarks ++ " " ++ description.first_line()'`.
   A target that arrives from a shell variable is a target nobody re-checked.
2. Never abandon a commit that carries a bookmark or that a bookmark already reaches. That is
   landed history, and in a shared repository it is usually not yours.

`jj abandon` cannot be wrapped — jj refuses aliases that shadow built-in commands
(`Cannot define an alias that overrides the built-in command 'abandon'`) — so the mechanism sits
one layer out, in the agent host: `hooks/jj-abandon-guard.py` refuses these three shapes on
PreToolUse and prints the resolve-then-abandon commands. Recovery, if it already happened, is
forward as always: `jj bookmark set <name> -r 'commit_id("<full id>")'` back onto the same commit,
then rebase your own change onto it. Never `jj undo` — it would take the other writer with it.

## A conflicted bookmark is not a usable name

Two writers moving the same bookmark to unrelated commits leave it conflicted (`main??`,
"Name `main` is conflicted"). The name then resolves to more than one revision, so `jj log -r main`
errors and every ancestry claim about `main` — landed, ahead, behind, contains — is unfounded until
it is reconciled.

The Git side hides this. jj exports only one side of a conflicted bookmark, so `git branch -v`,
`git merge-base` and any IDE panel show a single healthy `main` and answer questions about one
arbitrary half. A colocated repository is therefore the worst place to diagnose this from Git.

Reconcile by rebasing the *unpublished* side onto the published one, never the reverse:

```
jj rebase -s 'roots(bookmarks(exact:"main") & ~::main@origin)' -d main@origin
jj land <new-tip>
```

`jj land` refuses to move a conflicted bookmark and prints this rebase; the world-watch hook
announces the transition when another writer creates it. Report the divergence to the user rather
than describing the graph from a listing that only sees one side.

## Reads snapshot the working copy

`status`, `log`, `diff`, `op log` all snapshot first. Measured on a repo with one stray file
present, each of those commands created an operation and pulled `stray.txt` into the agent's
change; `--ignore-working-copy` did not.

The dangerous form is inspecting somebody else's workspace: a bare `jj status` there snapshots
*their* tree into *their* change, and if their `@` is already an ancestor of trunk, the snapshot
rewrites landed history. Always inspect other workspaces as
`jj -R <repo> --ignore-working-copy <cmd>`.

## A deleted Git ref can delete file content

With jj's default `git.abandon-unreachable-commits = true`, importing Git refs abandons commits
that became unreachable in Git and rebases their descendants. Reproduction: a commit adding
`work.txt`, a descendant adding `more.txt`, then the Git branch is deleted (an IDE, a cleanup
script, a stray `git branch -D`). After the next jj command the parent is abandoned and the
descendant is rebased — and `work.txt` is **gone from the descendant's tree**. With
`abandon-unreachable-commits = false` it survives.

This machine sets `false` globally. A repository that overrides it back to `true` reopens the
loss channel.

## Workspace creation lands on the wrong base quietly

- Without `-r`, `jj workspace add` starts the new workspace at the *parents* of the creator's `@`.
  An agent that just created its task change and then spawns a workspace gets a base one commit
  behind what it expects.
- With an ambiguous or conflicted `-r <name>`, the command prints `Revision '<name>' doesn't
  exist` **and still registers the workspace** on some other base. The retry then fails with
  `Workspace named '<n>' already exists`, so the agent believes nothing was created. Check
  `jj workspace list` before retrying, and forget the half-built workspace explicitly.
- Serialise workspace creation. Concurrent `jj workspace add` from the same workspace is a known
  upstream failure mode, not a supported pattern.

## Absence is the easiest thing to read wrongly

A revset that matches nothing returns empty, not an error, so a wrong query is indistinguishable
from "no such commit" — and in a shared repository the conclusion you draw from it ("their work is
gone", "nothing is unlanded") is the one that causes damage. String predicates need an explicit
pattern kind: `description(substring:"fix")`, `description(glob:"wip:*")`; bare
`description("fix")` silently matches nothing. Before concluding that work is absent, ask the same
question a second way — `jj log -r 'all()'`, `jj evolog`, `jj op log`.

Ancestry has the same shape of trap. Judge it with an explicit predicate —
`jj log -r 'A::B'`, or `git merge-base --is-ancestor A B` — never by reading `git log A..B` output:
a listing shows reachability, not separateness, so one commit listed means exactly one ahead, i.e.
a direct descendant, and a listing against a conflicted bookmark answers about one side only.

## Identity in reports

Three identifiers, three jobs:

| Identifier | Survives rewrite | Use for |
|---|---|---|
| change ID | yes | the logical change across rebases |
| full commit ID | no | what the next reader must actually find |
| operation ID | n/a | proving which repository state a claim was read at |

A handoff that cites only change IDs sends the next agent looking for a hash that a rebase already
replaced; one that cites only commit IDs loses the thread the moment anything is rebased. Report
both, plus the operation the claim was read at, and re-verify the state before acting on someone
else's report — an operation ID proves provenance, not freshness.
