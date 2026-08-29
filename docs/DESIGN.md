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
  bookmark refusal) mechanically excludes the destructive failure modes;
- unlanded floating work turned out to be the bigger loss channel in practice: an agent
  dies, the session compacts, and un-addressed work silently rots;
- pushing/publishing remains human-gated — the blast radius of a bad landing is local and
  recoverable via `jj op log`.

If your risk tolerance differs, keep the skills and guards and simply withhold landing
authorization in your project AGENTS.md; the session-end hook then forces `jj park`
instead, which is the supervised model.

## Trade-off: operation rewind is banned, not wrapped

`jj undo`/`op restore` could in principle be wrapped with a "single workspace only" check.
We ban them in prose instead of wrapping, because jj does not record which workspace made
an operation — the wrapper could not distinguish "safe to rewind" reliably, and a guard
that sometimes lies is worse than a rule. Forward recovery is always available.

## Trade-off: event log is local and unauthenticated

`jj-agent-event` appends plain JSONL with no signing and logs only rule names, ids and
counts — never file contents or credentials. It is telemetry for reflection, not an audit
trail; treating it as evidence of anything security-relevant would be a mistake.
