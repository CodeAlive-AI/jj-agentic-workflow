# Claude Code integration

The common runtime uses payload `cwd`, not `CLAUDE_PROJECT_DIR`; desktop worktree sessions can
retain the parent project directory in environment variables. General observation, abandon and
ownership hooks are user-level and do nothing outside JJ repositories.

WorktreeCreate/WorktreeRemove are **project opt-in**. Installing them globally would replace
Claude's normal creation for Git-only projects. On a quiet, explicitly owned JJ project:

```sh
bin/jj-agent-install --project /absolute/jj/root --project-only
```

This writes `.claude/settings.local.json`. Ignore that exact path before local installation.
Do not install into active workspaces. Do not combine competing lifecycle handlers. The project
must ignore `.workspaces/`; an external destination requires separate launcher configuration.

WorktreeCreate snapshots the owned caller, resolves its current `@` to a full commit ID, then
creates a described colocated workspace. stdout contains only its absolute path. No implicit
fallback to plain Git creation is allowed. A read-only reviewer needs no new workspace.

WorktreeRemove calls the shared guarded finish. Unlanded work or ignored files leave the folder
intact with a diagnostic. Claude may report a removal-hook failure without stopping shutdown;
the retained directory must be handled later. No SessionEnd cleanup is installed.

The first main SessionStart claims an unbound manifest. A second session and inherited
subagents cannot land/park the owner’s work through Stop. Hooks are guardrails, not access control.
Restart Claude after settings changes. Keep `worktree.baseRef=head` where already configured;
the custom hook chooses its own saved JJ base. Dependency setup remains an explicit project step.

Verification boundary: Python hook contracts are tested with real JJ/Git workspaces. Claude Code
was unavailable during this upgrade; CLI/Desktop dispatch and permission UX require a later live
smoke test. Do not call synthetic event tests end-to-end Claude verification.

Sources: [Claude hooks](https://code.claude.com/docs/en/hooks#worktreecreate),
[Claude worktrees](https://code.claude.com/docs/en/worktrees).
