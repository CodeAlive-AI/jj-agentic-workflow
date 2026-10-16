# Claude Code integration

JJ lifecycle and response hooks are retired as of 2026-10-16. Do not install WorktreeCreate,
WorktreeRemove, SessionStart, world-watch, abandon or Stop handlers from this workflow.
The installer only removes retired registrations and installs explicit commands.

Use an explicitly assigned colocated workspace prepared with `jj-agent prepare`, verify matching
roots with `jj-agent doctor`, then start Claude in that exact directory. An inherited working
directory does not authorize a delegate to write; parallel writers need separately assigned roots.
Do not request native `--worktree` / worktree isolation expecting it to invoke JJ.

Run setup and tests in the assigned root. Land or park your own work and invoke `jj-agent finish`
explicitly. Removal is a separate authorized `--remove` step that checks ignored/untracked files.
Complete these steps without replacing the user's substantive answer with a landing reminder.

The previous hook contracts remain historical fixtures, not a supported host integration. Existing
sessions must restart to unload removed handlers. On this machine only the general sensitive-file
edit protection remains user-level; project-specific push gates/cloud setup are separate policies.
