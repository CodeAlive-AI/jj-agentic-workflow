# Reflect on agent guardrails

Reflection here is not "read the transcripts and give advice". It is a bounded question asked of
recorded evidence: **for every rule that fired, which layer should have caught it — and what can
now be removed?**

## Why the usual version fails

- It produces sentiment ("be more careful with bookmarks") instead of a change anyone can apply.
- It only ever adds. Each incident appends a rule, nothing is retired, and the instruction file
  grows until agents stop reading it. An instruction set that is too large to be read is a worse
  outcome than the incident that grew it.
- It optimises for the most recent incident rather than the most frequent one.

## Gather evidence first

```bash
jj-agent-reflect --days 30 --instructions ~/.claude/skills/working-with-jj/SKILL.md
```

Counting is deterministic and already done for you. Do not re-derive counts by reading logs or
transcripts; spend the effort on the judgement the tool deliberately refuses to make.

If the report says no events were recorded, establish whether the guards are instrumented in this
environment before concluding that nothing went wrong. Silence from an uninstrumented guard looks
exactly like success.

## The only question worth asking

For each rule in the report:

| Evidence | Verdict | Change |
|---|---|---|
| Guard fired, agent recovered correctly | the system worked | none |
| Same guard fired repeatedly, close together | the **hint** is unusable | fix the message the tool prints, not the rule |
| A documented rule was violated anyway | the rule is in the wrong layer | move it down: instruction → mechanism |
| Damage happened and nothing fired | coverage gap | propose a new guard, and a test that proves the hazard |

The third row is the load-bearing one. **An instruction that gets violated should become a
mechanism, not a louder instruction.** A rule that can be enforced by a wrapper, a hook, or a
config setting does not belong in prose, where compliance is optional and silent.

## Subtraction is half the job

Every proposal that adds inline text must be paired against the budget in the report. When
instructions are over budget, a rule earns its inline slot only if it has fired, or a test in the
hazard suite proves the hazard is still real on the current tool version. Rules meeting neither
condition are candidates to demote into a reference file or to delete outright.

State removals as explicitly as additions. "Nothing to remove" is a claim that needs the same
evidence as any other.

## Output contract

Produce a list of proposed **layer moves**, each with: the rule, the evidence (count, dates,
bounce or violation), the target layer, and the exact edit. Rank by frequency, not recency.

Propose only. Do not edit instruction files, tool wrappers, hooks, or configuration as part of
reflection: an agent that rewrites its own constraints without review has no constraints. Apply
changes only after the user accepts them, one at a time, and re-run the hazard suite afterwards.
