#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Advisory Claude PostToolUse check of the commit reported by its own command."""
import json
from pathlib import Path
import re
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import jj, root

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
REPORT = re.compile(r"^\s*(Working copy\s+\(@\)\s+now at|Parent commit\s+\(@-\))\s*:\s+\S+\s+([0-9a-f]{8,40})(?:\s|$)", re.M)


def direct_command(data):
    raw = (data.get("tool_input") or {}).get("command")
    if isinstance(raw, str):
        lexer = shlex.shlex(raw, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            # Heredocs and other shell syntax shlex cannot split are never a plain jj command.
            return None
    else:
        tokens = raw
    if not isinstance(tokens, list) or len(tokens) < 2 or Path(tokens[0]).name != "jj":
        return None
    # A compound shell string is not evidence that JJ produced the attached output.
    if any(t and all(c in ";&|<>" for c in t) for t in tokens):
        return None
    if any(not isinstance(t, str) or any(c in t for c in ("\n", "`", "$")) for t in tokens):
        return None
    if tokens[1] not in ("describe", "commit", "new", "squash", "split"):
        return None
    if any(t in ("-R", "--repository", "--at-op", "--at-operation")
           or t.startswith(("--repository=", "--at-op=", "--at-operation=")) for t in tokens):
        return None
    # JJ prints working-copy status even when a revision selector changed another
    # commit. Only the default describe/commit target proves the reported ID is
    # the result. Squash/split and new --no-edit have similarly different targets.
    if tokens[1] in ("squash", "split") or "--no-edit" in tokens[2:]:
        return "unproven"
    if tokens[1] in ("describe", "commit"):
        args = iter(tokens[2:])
        for arg in args:
            if arg in ("-m", "--message"):
                if next(args, None) is None:
                    return "unproven"
            elif not (arg.startswith("--message=") or (arg.startswith("-m") and len(arg) > 2)):
                return "unproven"
    return tokens[1]


def main(data):
    if data.get("hook_event_name") != "PostToolUse" or data.get("tool_name") != "Bash":
        return
    command = direct_command(data)
    if not command:
        return
    if command == "unproven":
        return advisory("Attribution not checked: this command does not prove that the reported working-copy commit was the changed target; no neighbouring commits were inspected.")
    response = data.get("tool_response")
    if not isinstance(response, dict):
        return advisory("Attribution not checked: this tool response has no structured command output.")
    if response.get("exit_code", response.get("exitCode", 0)) not in (0, None):
        return
    output = ANSI.sub("", "\n".join(str(response.get(k) or "") for k in ("stdout", "stderr")))
    target_label = "Parent commit" if command == "commit" else "Working copy"
    candidates = {sha for label, sha in REPORT.findall(output) if label.startswith(target_label)}
    if len(candidates) != 1:
        return advisory("Attribution not checked: no single changed commit was identified in the command result; no neighbouring commits were inspected.")
    workspace = root(data.get("cwd") or ".")
    sha = next(iter(candidates))
    text = jj(workspace, "log", "-r", f'commit_id("{sha}")', "--no-graph", "-T",
              'commit_id ++ "\\n" ++ if(empty, "empty", "work") ++ "\\n" ++ description')
    parts = text.split("\n", 2)
    if len(parts) != 3:
        return advisory("Attribution not checked: the reported commit is no longer uniquely visible.")
    full, state, description = parts
    if state == "empty":
        return
    missing = [name for name in ("Model", "Agent-Session")
               if not re.search(rf"^{name}:\s*\S", description, re.M)]
    if missing:
        advisory(f"Description check for your command's commit {full[:12]}: missing "
                 + ", ".join(missing) + ". Amend when appropriate; this is an advisory, not a completion requirement. Do not invent model/session identity.")


def advisory(message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                            "additionalContext": message}}))


if __name__ == "__main__":
    try:
        main(json.load(sys.stdin))
    except Exception as error:
        advisory(f"Attribution check unavailable: {error}. No commits were changed.")
