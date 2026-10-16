#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read-only JJ context for SessionStart/PostCompact; no completion decisions."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import commit, doctor, operation, root


def main(data):
    event = data.get("hook_event_name")
    if event not in ("SessionStart", "PostCompact"):
        return
    cwd = Path(data.get("cwd") or ".").resolve()
    if not any((p / ".jj").is_dir() for p in (cwd, *cwd.parents)):
        return
    try:
        workspace = root(cwd)
        message = (f"JJ root: {workspace}; commit: {commit(workspace, '@')}; "
                   f"operation: {operation(workspace)}. ")
        try:
            doctor(workspace)
            message += "Git and JJ roots agree."
        except Exception as error:
            message += f"Root check unavailable: {error}."
        message += " This is an observation only; workspace ownership was not changed."
    except Exception as error:
        message = f"JJ context unavailable: {error}. Verify state explicitly when needed."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                            "additionalContext": message}}))


if __name__ == "__main__":
    try:
        main(json.load(sys.stdin))
    except Exception as error:
        print(f"JJ context input unavailable: {error}", file=sys.stderr)
