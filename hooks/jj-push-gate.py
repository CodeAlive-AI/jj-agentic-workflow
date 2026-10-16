#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Route only a configured project's push checks; ordinary Bash never snapshots JJ."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import repo_store, root


def deny(message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny", "permissionDecisionReason": message}}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    project = parser.parse_args().project.resolve()
    data = json.load(sys.stdin)
    if data.get("hook_event_name") != "PreToolUse" or data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    if isinstance(command, list):
        command = shlex.join(command)
    if not re.search(r"\bpush\b", command):
        return
    cwd = Path(data.get("cwd") or ".").resolve()
    try:
        workspace = root(cwd)
    except Exception:
        if cwd.is_relative_to(project):
            deny("Project push check cannot establish the JJ root. Inspect the workspace before pushing.")
        return
    if repo_store(workspace) != repo_store(project):
        return
    if re.search(r"(?:^|[;&|])\s*cd\s|(?:^|\s)(?:-R|-C|--repository)(?:=|\s)", command):
        return deny("Push routing via cd/-R/-C is ambiguous. Run the push directly from the assigned project root.")
    result = subprocess.run(["bash", str(project / "scripts/pre-push-lint.sh")],
                            input=json.dumps(data), capture_output=True, text=True,
                            cwd=workspace, timeout=880)
    if result.returncode:
        return deny("The configured project push check failed to run: " + result.stderr[-1000:])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        deny(f"Project push check unavailable: {error}. The push was not approved.")
