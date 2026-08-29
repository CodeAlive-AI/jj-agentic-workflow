# Contributing

This repository documents rules that were **earned**, not invented. That shapes what a
useful contribution looks like.

## A new rule needs evidence

Open an issue or PR with:

1. **What happened** — the incident or the hazard, concretely enough to reproduce.
2. **A reproduction** — ideally a new check in `tests/multi-writer-hazards.sh` that fails
   on an unguarded setup and passes with the proposed guard. State your jj version.
3. **The layer** — config, wrapper, hook, or prose. Prose is the last resort: a rule that
   a wrapper or a config setting can enforce does not belong in a skill, where compliance
   is optional and silent.
4. **What it replaces** — the skills have a fixed attention budget (~2000 body tokens).
   An addition that pushes a skill over budget should name a rule to demote into
   `references/` or delete.

## A rule that stopped being real

If a jj release fixes one of the documented hazards, that is a valuable contribution too:
show the failing check on the new version, and propose the removal.

## Style

- Skills follow the open `SKILL.md` format; keep the frontmatter `name` identical to the
  directory name and never add `README.md` inside a skill directory.
- Wrappers fail loudly and print the exact command to run next. A guard that refuses
  without telling the agent how to proceed just gets worked around.
- The event log records rule names, ids and counts only — never file contents,
  descriptions, or credentials.
