#!/usr/bin/env python3
"""Small state briefing and ownership-aware Stop guard for Codex and Claude."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import Failure, atomic_json, commit, doctor, jj, lifecycle_lock, manifest, operation, root, unaddressed


def context(event, message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}))


def main():
    data = json.load(sys.stdin)
    cwd = Path(data.get("cwd", ".")).resolve()
    if not any((p / ".jj").is_dir() for p in [cwd, *cwd.parents]):
        return 0
    workspace = root(cwd)
    event = data["hook_event_name"]
    if event == "SubagentStart":
        context(event, f"JJ root: {workspace}. An inherited working directory is shared. "
                "Read-only delegates may observe it with --ignore-working-copy --at-op=@. "
                "A writing delegate needs an explicitly assigned separate workspace and exact tool cwd.")
        return 0
    managed = (workspace / ".jj/jj-agent.json").is_file()
    record = manifest(workspace) if managed else None
    session = data.get("session_id")
    if event == "SessionStart" and record and not record.get("owner_session") and session:
        with lifecycle_lock(workspace):
            record = manifest(workspace)
            if not record.get("owner_session"):
                record["owner_session"] = session
                atomic_json(workspace / ".jj/jj-agent.json", record)
    if event in ("SessionStart", "PostCompact"):
        state = f"JJ workspace {workspace}; commit {commit(workspace, '@')}; operation {operation(workspace)}. "
        try:
            doctor(workspace)
            state += "Git and jj roots agree. "
        except Exception as error:
            state += f"Integration check: {error}. "
        state += "Load working-with-jj and maintaining-vcs-hygiene. "
        state += "Work through jj; host Git commit/handoff/cleanup controls are outside this workflow."
        if record and record.get("owner_session") != session:
            state += " This workspace belongs to another session; inspect only until explicitly reassigned."
        context(event, state)
    elif event in ("Stop", "SubagentStop"):
        # Never make an inspecting session land another writer's work. Subagents
        # do not acquire ownership merely by inheriting the parent's session id.
        if event == "SubagentStop" or not record or record.get("owner_session") != session:
            return 0
        if data.get("stop_hook_active"):
            return 0
        jj(workspace, "status", mutate=True)
        try:
            pending = unaddressed(workspace, record)
        except Failure as error:
            print(json.dumps({"decision": "block", "reason": str(error)}))
            return 0
        if pending:
            print(json.dumps({"decision": "block", "reason":
                  "Your JJ workspace has unaddressed work. Land or park it, or report the blocker. "
                  + ", ".join(pending)}))
    return 0


try:
    sys.exit(main())
except Exception as error:
    print(f"[jj session check unavailable] {error}; verify manually before delivery.", file=sys.stderr)
    sys.exit(0)
