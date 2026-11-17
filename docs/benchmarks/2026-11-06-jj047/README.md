# JJ 0.47.1: adoption research for our agent workflow

Date: 2026-11-06. Status: **research and implementation proposal, not an activated workflow**.

2026-11-17: the preparation blocker below is resolved and jj 0.47.1 is deployed; see
[VALIDATION-0.47.md](../../VALIDATION-0.47.md). The observation layer and conflict export remain proposals.

The new APIs fit our workflow, but upgrading the executable first would break the current
`jj-agent prepare`. Qualify its replacement and install the shared tools consistently before
raising the deployed JJ baseline. The highest-value feature is a shared, operation-pinned
observation layer; conflict export is the next addition. A general autonomous conflict solver
and more hooks are not justified by these findings.

## Evidence and reproduction

The official ARM64 macOS binary reports
`jj 0.47.1-d16ee1fc88a72c54142241b079a34bbf3b033bc0`.
Its release archive SHA-256, checked against the GitHub release asset digest, is
`50129b527f7cd6aef82aebd4bb2b670bb56766adc509ef3279c4327aa3592255`.
The installed Homebrew executable remains **0.46.0**. No production repository was opened
with the experimental binary; all 0.47.1 mutations happened in disposable fixture repositories.

Run with Node 24 and a separately verified binary:

```sh
node docs/benchmarks/2026-11-06-jj047/verify.ts \
  /absolute/path/to/jj-0.47.1 /absolute/path/to/new-results
```

[verify.ts](verify.ts) creates its own temporary repositories and isolated JJ configuration.
It performs no network calls, paid calls, installation or publication. It intentionally forks
operations to create hazards; those commands are fixtures, not recovery instructions.
[results.json](results.json) records the final run: **16 checks passed**. Some checks prove
incompatibility or unsafe behavior; this is not a green qualification of our existing workflow.
The final run printed a Node module-type warning due to the host's parent package configuration;
execution completed successfully. No unrelated package configuration was changed.
[run-history.json](run-history.json) records the exploratory and corrected fixture runs,
including failed assumptions; none was an automatic retry.

| Checked property | Observed result |
|---|---|
| Three-way file conflict | Three positive and two negative terms, including repeated base IDs |
| Commit count versus file count | One conflicted commit held two conflicted files |
| Git object retrieval | A regular-file object ID returned its original bytes via read-only `git cat-file blob` |
| `revset()` in operation templates | `jj op log -T` rejected it; commit templates accepted it |
| Missing `Option<Commit>` | Exit 0, but `<Error: No value set to Option<Commit>>` instead of JSON |
| Read-only observation | No new operation and no capture of an unsnapshotted file |
| Task-specific range | Zero conflicts for the clean task while the repository-wide count was one |
| Operation pinning | Reading the captured operation still returned the earlier working-copy commit |
| Delete/modify file conflict | The deleted side was preserved as JSON `null` |
| `:editor`, three sides, two hunks | A script resolved one hunk; the other remained a JJ conflict |
| Multiple operation heads | Explicit observation failed instead of silently merging them |
| Divergence | Two commit versions represented one unique change ID |
| Delete/update bookmark conflict | `.conflict()` was true despite only one non-null revset target |
| Two workspaces at one commit | Two `current_working_copy()` matches, exactly one `current_workspace()` |
| Invalid workspace revision | No destination was created |
| Current preparation recipe | `--ignore-working-copy` was rejected, including with full sparsity |
| Preparation alternatives | `--at-op=@` captured caller edits; an exact operation ID preserved them |

The table splits some combined checks for readability. Early probes exposed incorrect template
construction (maps outside `json()`, an unescaped nested revset string, remote bookmark rows),
which were fixed in the reproducer. A first invalid-revision probe was rejected for its
`--ignore-working-copy` flag before testing the revision; the final test removes that flag and
asserts the actual missing-revision error. The attempted `--at-op=@` preparation failed the
preservation assertion; its final check explicitly records that unsafe behavior.

Not qualified here: Linux or Windows, the full hazard/lifecycle/installer suites, simultaneous
writers during the proposed preparation, executable-bit/symlink/submodule/binary conflict
resolution, live host hook dispatch, real fetch/index races, push or signing. No latency or
token-savings claim follows from these small fixtures.

## The upgrade blocker: workspace preparation

Our current `lib/jj_agent.py:prepare()` uses:

```sh
jj --ignore-working-copy workspace add --sparse-patterns full --colocate ...
jj workspace update-stale  # in the new metadata-only child
```

JJ 0.47.1 rejects the first command before creation:

```text
Error: This command must be able to update the working copy.
Hint: Don't use --ignore-working-copy.
```

This is an explicit check in upstream
[workspace/add.rs](https://github.com/jj-vcs/jj/blob/v0.47.1/cli/src/commands/workspace/add.rs).
Simply dropping the flag captures the caller's edits. Replacing it with `--at-op=@` does too.
Upstream [cli_util.rs](https://github.com/jj-vcs/jj/blob/v0.47.1/cli/src/cli_util.rs) treats
`@` specially as the head operation, eligible for snapshotting; a full operation ID is different.

The **candidate**, verified in a single-process fixture, is:

1. Read the exact operation ID without snapshotting or operation reconciliation.
2. Resolve the requested base at that operation, requiring exactly one commit.
3. Create the child with `--at-op=<full-operation-id>`, full sparsity, colocation and that base.
4. Verify the caller's recorded commit stayed unchanged, the child parent equals the base,
   and Git/JJ roots agree. The child is already materialized; the old metadata-only assertion
   and `update-stale` step do not apply.

Do not publish this as an agent command yet. It needs concurrent-operation tests, failure/partial
creation tests and preservation of existing creator-session/ownership behavior. It also needs
a narrow documented lifecycle exception to our present inspection-only `--at-op` guidance;
it does not authorize using historical operations for general mutations or recovery.
No fallback may silently switch to caller snapshotting when this path fails.

## Existing installation and consistency

Observed canonical sources:

| Consumer | Source and finding |
|---|---|
| `working-with-jj` | Codex and Claude links resolve to this repository's `skills/working-with-jj` |
| `maintaining-vcs-hygiene` | Codex and Claude links resolve to this repository's matching skill |
| `pragmatic-orchestration` | Codex, Claude and OpenCode links resolve to `/Users/rodio/my-projects/pragmatic-orchestration/skills/pragmatic-orchestration` |
| ARAI orchestration | Project skill at `/Users/rodio/my-projects/arai/.agents/skills/orchestrating-autonomous-delivery` |
| `jj-agent` | Installed symlink uses immutable runtime release `c9fcb50c5956d50b` |
| `jj-land` | Installed standalone copy differs from the source and runtime copy |

The duplicate auditor reported **alias**, with no canonical-source decision needed, for all
three global skills. No third-party skill was installed or updated.

Source `bin/jj-land` and the runtime copy have SHA-256
`b72e5619e72d1c4220f5c3fb36ff3145f26b267cd1098d3dede4d7327560755a`;
the executing `~/.local/bin/jj-land` has
`90bb78446bb386ecdb6fef343735f2a63a8917dc4052aba1abde8886846e80c4`.
The difference is the improved distinction between a failed check, an unavailable environment
and a killed check. The installed copy still describes all three as a failed check.

The cause is visible in `bin/jj-agent-install`: it copies all `bin`/`lib` files into the
immutable release, but only repoints `~/.local/bin/jj-agent`. Installation instructions still
separately copy `jj-land` and event tools. A refreshed runtime therefore does not refresh every
executed command. This is a concrete installation defect, not a need for more agent prose.

Proposed fix: install the workflow's public commands from one versioned runtime with backed-up
links and receipts, preserve existing aliases, and report the resolved executable paths and
release identities in `doctor`. Verify installation repeatability and rollback before deployment.
Skill files stay in their canonical sources; no duplicate per-agent copies. Until the tool is
installed, skill prose must not tell agents that the proposed commands already exist.

## Proposed observation layer

Implement once in `lib/jj_agent.py`, with an explicit command such as
`jj-agent inspect --base <commit> --rev <commit> --json` (proposed, not available now).
`doctor`, the selected context hook, handoff and landing preflight consume the same implementation.
`doctor` retains its filesystem/Git-root checks; graph output cannot replace them.

Observation sequence:

1. Resolve a single operation using `--ignore-working-copy --at-op=@ op log -n 1 -G -T id`.
2. Run graph templates with `--ignore-working-copy --at-op=<that-id>`, never a fresh `@`
   for each query. Resolve names and ranges in that same view.
3. Read bookmark records at that operation when needed. Parse JSON/JSONL and validate its schema,
   field types and expected record cardinality as well as the process exit status.
4. Return identities, facts and problems, with an explicit saved-state scope. Never convert a
   command/template/schema error into zero conflicts or an empty list.

This is usually an operation-ID read plus a graph query, with explicit bookmark/workspace
queries where needed; it is not literally one call for every fact. Fixed revsets can be evaluated
once during template parsing; dynamic ones are evaluated per call. Use a single anchor commit
for a summary rather than repeating repository-wide queries for every displayed commit.

Suggested report fields:

- `schema_version`, executable/runtime versions, root and workspace identity;
- full `operation_id`, `change_id`, `commit_id`, base, target and resolved trunk IDs;
- scoped conflicted commit IDs and divergent versions grouped by change ID;
- bookmark conflict flags and optional positive/negative targets, preserving `null`;
- whether the selected target is reachable from trunk and whether it contains the published tip;
- separately labelled repository-wide diagnostics, when requested.

Preserve three distinctions: commit conflicts versus file conflicts; divergent versions versus
unique changes; saved JJ state versus current disk edits. A worker snapshots its own files before
handoff; a supervisor never snapshots them just to observe. `WorkspaceRef.current_workspace()`
identifies a workspace, not its owner or process liveness. The manifest still carries ownership.

One operation view makes the facts internally consistent, but it is not a transaction with a
later `land` or push. Recheck relevant target/trunk/published identities before mutation and
retain the existing movement checks. An unrelated operation alone should not become a new
reason to refuse useful work. Do not introduce a new repository-wide conflict gate.

The existing `jj-land` conflict-bookmark check counts revset targets. Our delete/update fixture
shows why that count is insufficient: one live commit plus deletion is still conflicted.
The later bare-name lookup does error, so this research does **not** claim the current command
incorrectly lands it. The improvement is explicit `CommitRef.conflict()` detection and a useful
recovery diagnosis. Keep local and remote records distinct; `bookmark list` can emit both.

## Conflict export and resolution

Add an on-demand exporter, for example `jj-agent conflicts --rev <commit> --json`, using the
same pinned observation layer. [conflicts.template](conflicts.template) is a tested prototype;
it does not itself enforce authorization or implement a solver.

Preserve the path, side count, ordered negative and positive terms, object IDs, types,
executable bits and missing values. These are merge-algebra terms, not an author list or a
universal base/ours/theirs triple. Repeated negative terms must not be deduplicated. Object IDs
alone do not explain why a change was made; include parent/evolution context when resolving it.

For this Git-backed workflow, retrieve an explicitly selected regular-file blob with
read-only Git object access. Do not generalize that to all JJ storage backends or treat a
submodule commit, symlink or tree as a regular text blob. Export metadata by default; fetch
only relevant, authorized file contents on demand, never entire trees or secrets.

This improves conflict triage and lets a resolver receive exact sides and task intent. A
resolver still edits only an assigned integration workspace, reads the complete affected code,
checks the result and runs relevant tests. No automatic ours/theirs choice, new metered model
calls or default spawning is justified by the API.

`:editor` is useful when an explicit noninteractive script must receive JJ's temporary conflict
file. Set that editor for one invocation, not globally. The fixture proves partial progress is
preserved even with three sides. A zero exit status does not mean all conflicts disappeared;
query the resulting tree. Ordinary direct edits to markers remain a reasonable path for an
agent with file-editing tools. Do not replace that path with a mandatory interactive editor.

## Exact skill update map

| Location | Change after the mechanism is qualified | What it replaces or avoids |
|---|---|---|
| `working-with-jj/SKILL.md` | Short entry for shared observation and scoped conflict export; update deployed baseline only after rollout | Ad hoc graph parsing and long inline templates |
| `working-with-jj/references/workspace-lifecycle.md` | Qualified 0.47 preparation, full operation ID distinction, revised materialization step | Incompatible metadata-only recipe; no broad `--at-op` mutation permission |
| `working-with-jj/references/parallel-agents.md` | Count semantics, bookmark deletion conflicts, remaining concurrency hazards | Remove the stale claim that the retired world-watch hook announces changes |
| New `working-with-jj/references/structured-state.md` | Schema, tested examples, null/error handling, scope and conflict terms | One maintained API reference, not copies in every skill |
| `maintaining-vcs-hygiene` | Prefer the shared evidence report at handoff; keep ownership/intent/delivery responsibilities | Repeated JJ syntax; no extra hooks or completion ceremony |
| `pragmatic-orchestration/references/delegate-vcs.md` | Consume the shared report in the worker's exact root at launch/handoff/integration | Duplicate observer implementations and treating no diff as inactivity |
| ARAI `orchestrating-autonomous-delivery` | Use task-scoped evidence when accepting a delegate and before integration | Global `mutable()` counts as a gate for unrelated work |
| Installer, README, AGENTS and host references | One deployed release identity and qualified version; preserve owner decisions | Documentation announcing tools that PATH does not execute |

Draft core wording for review, not installed instructions:

> Observe from the assigned workspace using the shared inspector. Its operation ID identifies
> saved JJ state; disk edits and ownership are separate. Inspect the integration range and use
> the conflict exporter only when needed. Recheck the target before mutation; observation is
> not permission to land or publish.

Keep detailed new API mechanics in the one reference. Do not expand both core skill bodies
with release notes. ARAI retains its project facts: task workspace default, `jj land`, default
checkout delivery and explicit publication approval. Product-agent skills do not need JJ
internals merely because development agents benefit from them.

## Rollout and useful outcome

1. **Compatibility first:** qualify the exact-operation preparation adapter and its narrowly
   scoped instruction change, then fix installer/runtime drift. Retain current 0.46 operation
   until the replacement is ready; do not upgrade into a broken `prepare`.
2. **Observation:** implement and test the shared schema, expose it explicitly, then connect
   existing consumers. Migrate the `jj-land` read layer only with equivalent refusal tests and
   its current publication/ancestry protections preserved.
3. **Conflict support:** ship metadata export and the tested noninteractive editor recipe;
   add actual content/type cases before claiming general conflict resolution.
4. **Synchronized adoption:** after owner agreement, install 0.47.1 and matching runtime on
   each participating host, verify the actual paths, and update canonical skill references.
   Inventory remote hosts first; their versions were not inspected in this research.
5. **Measure real benefit:** compare subprocess counts and output size for identical observation
   tasks, incorrect/ambiguous state reports, and time spent recovering integration conflicts.
   Record failed-query classification and caller-preservation tests. No savings percentage or
   latency estimate is available yet.

The fetch/index fixes are a reason to adopt the release after compatibility work, not evidence
that shared worktrees, snapshotting, arbitrary Git writes or repository-wide rewind are safe.
The newer timestamp formats and optional bookmark targets also need compatibility coverage.
Our inspected timestamp formats use `%Y-%m-%d`, which does not need migration.

Current local signing settings are `signing.behavior=own` and `git.sign-on-push=false`.
Selective push signing has little immediate value here. Preserve the current signing policy;
do not switch to `drop` or sign other agents' commits merely to use the new option. If adopted
later, account for signing's separate operation and changed commit IDs when tying publication
to qualification evidence.

This record and fixtures can land locally without activating the proposal. Changes to shared
instructions/tools/settings wait for owner agreement under
`improving-agent-experience`, “What waits for the owner”. No push, deployment, shared skill
edit, global setting change, hook installation or system binary upgrade occurred in this study.

## Official sources

- [JJ 0.47.0 release](https://github.com/jj-vcs/jj/releases/tag/v0.47.0): new APIs and concurrency fixes.
- [JJ 0.47.1 release](https://github.com/jj-vcs/jj/releases/tag/v0.47.1): Linux dependency fix and selective push signing.
- [Versioned templates](https://github.com/jj-vcs/jj/blob/v0.47.1/docs/templates.md): types, evaluation and optional values.
- [Resolve implementation](https://github.com/jj-vcs/jj/blob/v0.47.1/cli/src/commands/resolve.rs): editor behavior.
- [Versioned signing configuration](https://github.com/jj-vcs/jj/blob/v0.47.1/docs/config.md): signing policy and separate operation.
- Workspace creation and snapshot behavior are linked at the blocker above; fixtures supply the local evidence.
