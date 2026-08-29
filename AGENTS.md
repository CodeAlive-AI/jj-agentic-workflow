# Installing jj-agentic-workflow

You are an agent asked to install this workflow on the current machine. Follow the steps
in order — mechanisms before skills, skills before project docs. Ask the user before
overwriting anything that already exists; never merge silently.

## 0. Preconditions

- `jj --version` ≥ 0.44. If jj is absent, ask the user before installing it.
- Identify the host: Claude Code (`~/.claude/`), Codex (`~/.agents/`), or other. Skills go
  to the host's user-level skills directory; hooks only apply on Claude Code.

## 1. Mechanisms

1. Copy `bin/jj-land`, `bin/jj-agent-event`, `bin/jj-agent-reflect` to `~/.local/bin/`
   (or another directory on PATH — then update the `land` alias path accordingly) and
   `chmod +x` them.
2. Merge `config/jj-config-snippet.toml` into `~/.config/jj/config.toml`:
   - If the user already has `[git]` or `[aliases]` entries with the same keys, show the
     difference and ask.
   - Before setting `private-commits`, check no existing unpublished commit matches the
     revset (it would block their next push): run the revset in each active repository
     and report matches instead of silently installing.

## 2. Hooks (Claude Code only)

Copy `hooks/*.py` to `~/.claude/hooks/` and register them in `~/.claude/settings.json`:
`jj-world-watch.py` on PostToolUse, `jj-session-end-check.py` on Stop. Both fail open.

## 3. Skills

Copy `skills/working-with-jj/` and `skills/maintaining-vcs-hygiene/` to the host's
user-level skills directory. Keep directory names identical to the frontmatter `name`.
If a skill with the same name exists, diff and ask — do not overwrite.

## 4. Verify

Run the hazard suite in a scratch directory (it creates its own temporary repos, never
touches real ones):

```bash
bash tests/multi-writer-hazards.sh
```

All checks must pass. If a hazard check *fails* on a newer jj, report it as "rule possibly
obsolete on jj <version>", not as an installation error.

## 5. Onboard the user's projects

Read `skills/working-with-jj/references/onboarding.md` and apply it: four one-line
invariants in the global agent memory file, a short facts-only AGENTS.md per repository.
Do not copy skill content into either — state facts, point at skills.

## 6. Report

Tell the user: what was installed where, what was skipped and why, the test result, and
that `jj-agent-reflect --days 30` is the periodic review entry point.
