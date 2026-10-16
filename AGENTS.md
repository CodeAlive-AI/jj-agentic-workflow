# Installing jj-agentic-workflow

You are an agent asked to install this workflow on the current machine. Follow the steps
in order — mechanisms before skills, skills before project docs. Back up existing settings and show the resulting changes. An explicit request to update this
workflow authorizes scoped merges; preserve unrelated settings. Never migrate active workspaces.

## 0. Preconditions

- `jj --version` ≥ 0.46; Git ≥ 2.42 for colocated workspaces. If jj is absent, ask the user before installing it.
- Identify the host: Claude Code (`~/.claude/`), Codex (`~/.agents/`), or other. Skills go
  to the host's user-level skills directory; the workflow uses explicit commands in Codex and Claude Code.

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

## 2. Host integration: explicit commands only

JJ agent hooks are retired as of 2026-10-16 after a Stop hook displaced a substantive agent
answer with a landing reminder. Do not register, enable or trust JJ lifecycle/response hooks.

Run `uv run --no-project --python 3.14 --script bin/jj-agent-install`. It installs `jj-agent`
and its library, removes old JJ registrations from existing user JSON configs, preserves unrelated
settings, and records rollback copies. It does not enable host hooks or create host config files.
`--project /absolute/root --project-only` only removes retired JJ project hook registrations.
Never restore pre-retirement hook settings from an old receipt without a new explicit request.

Use pre-created colocated JJ workspaces as Local projects. Prepare, doctor, finish and cleanup
are explicit commands. Complete VCS checks without replacing the requested answer. Keep active
workspaces untouched and restart hosts after removing already-loaded hooks.

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
