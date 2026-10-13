# Installing jj-agentic-workflow

You are an agent asked to install this workflow on the current machine. Follow the steps
in order — mechanisms before skills, skills before project docs. Back up existing settings and show the resulting changes. An explicit request to update this
workflow authorizes scoped merges; preserve unrelated settings. Never migrate active workspaces.

## 0. Preconditions

- `jj --version` ≥ 0.46; Git ≥ 2.42 for colocated workspaces. If jj is absent, ask the user before installing it.
- Identify the host: Claude Code (`~/.claude/`), Codex (`~/.agents/`), or other. Skills go
  to the host's user-level skills directory; common hooks support Codex and Claude Code.

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

## 2. Host integration

Run `python3 bin/jj-agent-install`. It installs an immutable common runtime and `jj-agent`,
backs up touched settings, preserves unrelated hooks, and enables Codex hooks. Record its receipt.
Validate both hook documents with the host validator. Review/trust changed Codex hooks through
native `/hooks`; do not fabricate trust state. Restart agents after settings changes.

Only explicitly onboarded, inactive JJ projects get Claude WorktreeCreate/WorktreeRemove:
`bin/jj-agent-install --project /absolute/root --project-only`. Never install lifecycle replacement
hooks globally. Ensure `.workspaces/` and `.claude/settings.local.json` are ignored first.

Read the host references in `skills/working-with-jj/references/`. Use pre-created colocated JJ
workspaces as Local projects in Codex; native Git worktree handoff/archive are outside this workflow.
Do not change unrelated host automation settings implicitly. Rollback uses the receipt and refuses
concurrently edited files.

## 3. Skills

Copy `skills/working-with-jj/` and `skills/maintaining-vcs-hygiene/` to the host's
user-level skills directory. Keep directory names identical to the frontmatter `name`.
Prefer existing canonical symlinks; update their source once. If an unrelated skill has the same
name, reconcile it explicitly instead of replacing it.

## 4. Verify

Run the hazard suite in a scratch directory (it creates its own temporary repos, never
touches real ones):

```bash
python3 -B tests/test_workspace_integration.py
python3 -B tests/test_install.py
bash tests/multi-writer-hazards.sh
```

All checks must pass. Investigate a changed hazard on newer jj and update both evidence and rule;
do not call an unexplained failure a successful installation. Distinguish synthetic hook contracts
from actual host dispatch. Do not launch an unavailable host.

## 5. Onboard the user's projects

Read `skills/working-with-jj/references/onboarding.md` and apply it: four one-line
invariants in the global agent memory file, a short facts-only AGENTS.md per repository.
Do not copy skill content into either — state facts, point at skills.

## 6. Report

Tell the user: what was installed where, what was skipped and why, the test result, and
that `jj-agent-reflect --days 30` is the periodic review entry point.
