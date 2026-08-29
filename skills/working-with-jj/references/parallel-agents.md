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
