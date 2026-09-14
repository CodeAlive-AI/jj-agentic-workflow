---
name: maintaining-vcs-hygiene
description: AI-native version-control culture for agents in git and jj repositories. Use when committing or describing changes, parking or handing off work, cleaning a repository, coordinating with other agents or humans in one checkout, deciding where scratch output belongs, closing a work session, or reviewing how well agent guardrails are working. Complements repository-specific VCS skills; does not replace their procedures. Not for choosing VCS commands or syntax, resolving merge conflicts, or CI/CD pipeline configuration.
---

# Maintaining VCS hygiene

Agents differ from human committers in three ways, and every rule here compensates one of them:
agents lose context (compaction, restarts), they run in parallel with humans and other agents,
and they generate volume cheaply.

This skill is the culture layer; it pairs with `working-with-jj` for the command layer. Each
works alone, but in a jj repository load both — culture without safe commands, or commands
without culture, each recreates half of the incidents these rules came from.

## 1. The repository is a shared, addressed space

- Nothing enters the working tree unless a future reader needs it. Scratch output, logs,
  downloads, analysis scripts, and bundles go to a scratch directory outside the checkout — the
  host's session scratchpad, or the one the repository's AGENTS.md names — never the repository.
- Before the first edit, establish whose work the working copy holds (jj: `jj log -r @`;
  git: `git status` + current branch). Humans and other agent CLIs count as writers; edits in
  an auto-snapshotting VCS silently join whatever change is checked out.

## 2. Work is always addressable

- No orphaned work. At any pause, every edit is either landed, or parked on a described
  change/branch, or explicitly abandoned with a stated reason.
- Commit at milestones and at least every 20 minutes while dirty — an agent can die mid-task,
  and an uncommitted tree at handoff is a defect, not a style choice.
- At session end, sweep for strays and resolve them: jj `jj log -r 'all() & ~::<trunk>'`;
  git `git branch --no-merged` plus a reflog check for detached work. Sweep the *undescribed*
  too, wherever they sit — jj `jj log -r 'description(exact:"") & ~root()'` — because an
  unpushed range hides them until it is pushed (§4).
- **A working copy is not evidence of unlanded work.** A workspace parked on an
  already-landed commit presents exactly like a large uncommitted change: `status` lists
  files, and a diff against its parent shows the whole change. Decide by ancestry, never by
  appearance — jj `jj log -r '<rev> & ::<trunk>'`, git `git merge-base --is-ancestor <rev>
  <trunk>` — and do it before forming any opinion about the work. Comparing its *contents*
  against trunk answers a different question and answers it misleadingly: trunk holding a
  newer version of the same files reads as "superseded duplicate" when the truth may be that
  trunk was built from this very commit and moved on. The sweep revset above already encodes
  this; the mistake is reaching a working copy by another route — a workspace listing, a
  colleague's checkout — and judging it on its diff.

## 3. Descriptions carry intent

- First line: what changed. Body: why now, alternatives rejected and the reason, invariants
  preserved, deliberate deferrals, sequencing or deploy constraints, who authorized contract
  changes, verification evidence. Assume the reviewer sees only the repository, never the chat.
- State what was NOT verified and why, not only what was — partial verification presented as
  complete is the same defect as a partial tree presented as done.
- Committing on another writer's behalf is legitimate when their work would otherwise be
  stranded — say so in the body.
- Read before you write: when code looks wrong or oddly deliberate, run annotate/`git log -L`
  on those lines and read the description body before "fixing" it — it may be someone's fence.
  A deliberate trap in code also deserves a comment at the site; the body holds the why.

## 4. History is a deliverable

- Land honest units: one logical change each; fold "WIP"/"fix"/"next" noise into its parent
  before integrating. Placeholder descriptions are acceptable only on empty changes.
- **An empty change with no description at all is push-blocking litter, and it surfaces
  late.** jj refuses the whole push over one of them (`Won't push commit <id> since it has no
  description`), and such a commit is typically an abandoned working copy from an earlier
  session sitting *in the middle* of history — invisible in the local log, harmless for weeks,
  and discovered only when a push finally reaches that far. An empty change that carries a
  description pushes without complaint, so the distinction is description, not emptiness.
  Clearing it rebases every descendant: seconds while the range is unpublished, impossible
  once it is not. Describe or abandon an empty change when you step off it, not when the gate
  finds it.
- Never rewrite published history or force-push without explicit authorization. When the VCS
  refuses an abandon, squash or rebase as immutable, that refusal is evidence about the
  commit, not an obstacle to route around: it says the commit is already published. Stop and
  re-derive why you thought it was disposable.
- Attribute the executing agent as the author while preserving the configured committer
  identity. In Git, use `git commit --author="Agent Name <approved-agent-email>"`;
  in jj, use `jj metaedit --author "Agent Name <approved-agent-email>"` on your own
  change. Use an existing, user-approved agent address; do not invent one. If none is established, preserve
  the configured author and identify the agent in a commit trailer.
- Do not change `user.name`/`user.email`, pass identity-wide `git -c user.*` or
  `jj --config user.*` overrides, or set `GIT_COMMITTER_*`/`JJ_USER`/`JJ_EMAIL` merely
  to attribute agent work. These also change the committer, even in isolated clones.
  Preserve existing co-authorship and never impersonate another writer.
- Keep signing enabled where required and the committer email linked to the signing
  account. A valid local signature is not proof of GitHub verification. Inspect the
  resulting author, committer and signature before pushing; do not disable signing
  or rewrite published history to repair identity without explicit authorization.
- Record the executing model in a `Model: <exact-model-id>` trailer when known,
  including for spawned workers. Model attribution must not change the signing
  identity or repository user configuration.
- Attribution and message shape are checked on the result, not on the command that produced it,
  because `--stdin`, an editor, a script, or another agent CLI writes descriptions no
  command-lint can see. Where the repository ships the check, missing attribution, a subject
  over 72 characters, or an unwrapped body blocks the push — so fix a description when you are
  told, not at the gate.

## 5. Litter is removed at the source

- A stray artifact in `status` output usually means output was written to the wrong place — fix
  the destination first. Add an ignore rule only for output that must live in the checkout, and
  scope it narrowly: over-broad patterns (`bin/`, `*.so`) silently swallow real files such as test
  fixtures and vendored sources, and the loss surfaces only in CI or never.
- Close what you opened: delete merged branches and bookmarks you created, remove finished
  workspaces and scratch clones, drop stale remotes and bundles.

## 6. Claims require evidence

- Say "committed", "pushed", or "deployed" only after verifying the ref actually moved; name
  the commit and the gates that ran.
- Report uncommitted files, conflicts, and skipped checks honestly at handoff. A partial tree
  presented as done is the same defect as a job that reports success while losing data.

## 7. Guardrails are reviewed, not accumulated

When guards keep firing, a documented rule keeps being violated, or the instruction set has grown
past what an agent actually reads, run a reflection pass:
[reflection.md](references/reflection.md). The core doctrine: an instruction that gets violated
should become a mechanism, not a louder instruction — and every addition is paired with a removal
candidate. Reflection proposes; it never edits its own constraints without review.

## Onboarding a project

What belongs in global CLAUDE.md versus a repository's AGENTS.md, and what must never be
duplicated out of skills: see `working-with-jj` [onboarding.md](../working-with-jj/references/onboarding.md)
(jj-specific parts apply only there; the layering rules apply everywhere).
