# Installing jj-agentic-workflow

You are an agent asked to install this workflow on the current machine. Follow the steps
in order — mechanisms before skills, skills before project docs. Back up existing settings and show the resulting changes. An explicit request to update this
workflow authorizes scoped merges; preserve unrelated settings. Never migrate active workspaces.

## 0. Preconditions

- `jj --version` ≥ 0.47; Git ≥ 2.42 for colocated workspaces. If jj is absent, ask the user before installing it.
- Identify the host: Claude Code (`~/.claude/`), Codex (`~/.agents/`), or other. Skills go
  to the host's user-level skills directory; the workflow uses explicit commands in Codex and Claude Code.

## 1. Mechanisms

1. Run `uv run --no-project --python 3.14 --script bin/jj-agent-install` (add the hook flags of
   step 2 only when selected). It copies `bin/` and `lib/` into an immutable release and links
   `jj-agent`, `jj-land`, `jj-agent-event` and `jj-agent-reflect` in `~/.local/bin/` to it,
   replacing each atomically and backing up what was there; the `land` alias calls
   `~/.local/bin/jj-land`. Never copy the commands by hand: a copy outlives every later release.
2. Merge `config/jj-config-snippet.toml` into `~/.config/jj/config.toml`:
   - If the user already has `[git]` or `[aliases]` entries with the same keys, show the
     difference and ask.
   - Before setting `private-commits`, check no existing unpublished commit matches the
     revset (it would block their next push): run the revset in each active repository
     and report matches instead of silently installing.

## 2. Host integration: explicit selection

The default installer adds no hooks. Completion-blocking JJ/Grok Stop hooks remain retired.
A user may explicitly select read-only context and action-specific checks; do not revive the old
shared `jj-session.py` handler, world watcher, abandon guard or unused SubagentStop implicitly.

The selected profile is installed with:
`uv run --no-project --python 3.14 --script bin/jj-agent-install --observational-hooks --codex-push-project /absolute/approved/project`.
It adds SessionStart/PostCompact on both hosts, Claude-only attribution advice, a PreToolUse hint on
both hosts that redirects `rm -r <workspace root>` to `jj-agent finish --remove` (filesystem check only;
it never fires for other paths), and an explicitly project-scoped Codex push router. Existing sensitive-file and cloud setup hooks remain separate.
The installer backs up changes and does not flip the global Codex switch. Disable unselected
plugin/project hooks through native hook state before enabling Codex hooks, then review/trust only
selected definitions through `/hooks`. Never fabricate trust hashes or change sandbox/permissions.

Claude lifecycle is experimental: `--claude-lifecycle --project /absolute/root --project-only`.
Its new implementation avoids caller snapshots and checks creator session/project before removal.
Do not deploy it until the actual host can dispatch safe removal without forcing native checks.
Claude 2.1.300's ExitWorktree failed before invoking removal in the live pilot, so both lifecycle
subscriptions remain absent from ARAI. Never create an unpaired registration that restores Git cleanup.

Use explicit prepare/doctor/finish meanwhile. Restart agents after settings changes. Active
workspaces are never migrated or mass-reconfigured.

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
