#!/usr/bin/env python3
"""Claude WorktreeCreate/Remove adapter; install per jj project, never globally."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import Failure, finish, jj, prepare, root


def main():
    data = json.load(sys.stdin)
    event = data["hook_event_name"]
    if event == "WorktreeCreate":
        workspace = root(data["cwd"])
        # Project opt-in authorizes snapshotting the exclusively owned parent.
        # Snapshot before resolving @ so the child includes the current task work.
        jj(workspace, "status", mutate=True)
        revision = jj(workspace, "log", "-r", "@", "--no-graph", "-T", "commit_id")
        print(prepare(workspace, data["name"], revision, snapshot_caller=True))
    elif event == "WorktreeRemove":
        finish(data["worktree_path"], remove=True)
    else:
        raise Failure(f"Unsupported lifecycle event: {event}")


try:
    main()
except Exception as error:
    print(f"jj worktree adapter: {error}", file=sys.stderr)
    sys.exit(1)
