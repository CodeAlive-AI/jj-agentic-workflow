#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Project-scoped Claude lifecycle; never snapshot the caller or guess ownership."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import Failure, atomic_json, commit, finish, manifest, prepare, repo_store, root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    project = parser.parse_args().project.resolve(strict=True)
    data = json.load(sys.stdin)
    session = data.get("session_id")
    if not isinstance(session, str) or not session:
        raise Failure("Claude lifecycle requires a session ID")
    caller = root(data["cwd"])
    if repo_store(caller) != repo_store(project):
        raise Failure("Caller is outside the explicitly configured project repository")
    event = data.get("hook_event_name")
    if event == "WorktreeCreate":
        base = commit(caller, "@")  # saved JJ state only; unsaved caller files remain untouched
        child = prepare(caller, data["name"], base, session=session)
        record = manifest(child)
        record["lifecycle_host"] = "claude"
        atomic_json(child / ".jj/jj-agent.json", record)
        print(child)
    elif event == "WorktreeRemove":
        path = Path(data["worktree_path"])
        if not path.is_absolute() or path != path.resolve() or root(path) != path:
            raise Failure("Removal requires the exact non-symlink managed workspace root")
        record = manifest(path)
        if record.get("owner_session") != session or record.get("lifecycle_host") != "claude":
            raise Failure("Workspace is not owned by this Claude lifecycle session")
        if repo_store(path) != repo_store(project):
            raise Failure("Removal target belongs to a different repository")
        finish(path, remove=True)
    else:
        raise Failure(f"Unsupported lifecycle event: {event}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Claude JJ lifecycle refused: {error}", file=sys.stderr)
        sys.exit(1)
