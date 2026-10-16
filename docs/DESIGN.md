# Design rationale and honest trade-offs

## Where the rules come from

Nothing here is theoretical. Each iron rule in `skills/working-with-jj/SKILL.md` traces
either to a measured reproduction in `tests/multi-writer-hazards.sh` (run against jj
0.44.0) or to a production incident in a multi-agent development programme. The evidence
tables live in `skills/working-with-jj/references/parallel-agents.md` and
`references/secrets-and-litter.md`.

## Why prose is the last layer, not the first

Instructions compete for a fixed attention budget. A skill over ~2000 tokens stops being
read reliably, so every rule must earn its inline slot: it has fired in practice, or a
test proves the hazard is real. Rules that can be enforced by config, a wrapper, or a
hook are moved there and *removed* from prose. The reflection procedure
(`skills/maintaining-vcs-hygiene/references/reflection.md`) institutionalises that
subtraction.

## Trade-off: agents land their own stacks

This workflow lets an agent fast-forward the local trunk over its own finished work
(`jj land`) without per-landing human review. The alternative — a human supervising every
integration — is safer per landing and is the model some jj tooling authors prefer. We
chose autonomous landing because:

- the guard set (forward-only, no conflicted stacks, never drop published work, conflicted
  bookmark refusal, no divergent change in the range) mechanically excludes the destructive
  failure modes it knows about. It is read-then-move, not atomic: a concurrent writer can
  still change the repository between the checks and the bookmark move;
- unlanded floating work turned out to be the bigger loss channel in practice: an agent
  dies, the session compacts, and un-addressed work silently rots;
- pushing/publishing remains human-gated — the blast radius of a bad landing is local and
  recoverable via `jj op log`.

If your risk tolerance differs, keep the skills and guards and simply withhold landing
authorization in your project AGENTS.md; the agent must explicitly park and report its work
instead, which is the supervised model.

## Trade-off: native undo guard does not establish ownership

JJ 0.46 records workspace metadata and refuses cross-workspace undo/redo. We retain forward
recovery as the shared-repository default because `op restore`, older operations and two writers
sharing a workspace remain outside that protection. The hazard suite now expects undo refusal.

## Trade-off: a shared lifecycle with host adapters

The runtime creates native colocated workspaces, checks root agreement, records ownership, and
refuses cleanup of unaddressed work or ignored files. Creation explicitly acknowledges a caller
snapshot: `workspace add --ignore-working-copy` fails partway on 0.46. A filesystem lock serializes
our lifecycle calls, not arbitrary writers. Removal therefore still requires exclusive ownership.

## Retired approach: host hooks

On 2026-10-16 a JJ Stop hook displaced Astra's substantive methodology answer with a landing
reminder. Ownership checks and successful command-contract tests did not prove answer integrity.
The workflow therefore installs explicit commands only. It removes previous JJ registrations,
never enables host hooks, and keeps copies for rollback. Historic hooks remain test fixtures.

Completion checks belong in the task flow. A Stop event is a turn boundary, not authorization
to substitute a final answer, land another session's work or delete a workspace. `jj abandon`
still requires explicit target/ownership inspection; no agent hook enforcement is claimed.

## Trade-off: file checks at landing are policy, not detection

Litter is decided where output is written; `jj land` is a late backstop. It warns on names and
sizes and refuses only paths a repository explicitly forbids, because a universal filename
blocklist both blocks legitimate files (`.env.example`, public certificates) and misses secrets in
ordinary files. A content scanner was rejected for the same reason in the other direction: it
would read secret values into agent output. Capture happens at snapshot time, before any landing,
so no landing check can undo it — the reference says so instead of implying otherwise.

## Trade-off: event log is local and unauthenticated

`jj-agent-event` appends plain JSONL with no signing and logs only rule names, ids and
counts — never file contents or credentials. It is telemetry for reflection, not an audit
trail; treating it as evidence of anything security-relevant would be a mistake.
