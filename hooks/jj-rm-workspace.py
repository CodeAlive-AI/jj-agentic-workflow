#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Redirect `rm -r <jj workspace root>` to `jj-agent finish --remove`.

Session history (2026-07..11): agents deleted a workspace root with rm -r 836 times. That
leaves jj with a stale workspace entry and loses unlanded work silently. `jj-agent finish
--remove` removes any secondary workspace, managed or made with raw `jj workspace add`,
and refuses only when unlanded changes or unsaved files would be lost.

Only the exact root of a secondary jj workspace is matched (`.jj/repo` is a pointer
file there); removing scratch or build output anywhere else passes silently. No jj call:
the check reads the filesystem only, so it stays fast on every Bash call.
"""
import glob
import json
import os
from pathlib import Path
import re
import shlex
import sys

SEPARATORS = re.compile(r"&&|\|\||[;|\n]")


def recursive(flags):
    return any(flag == "--recursive" or re.fullmatch(r"-[A-Za-z]*[rR][A-Za-z]*", flag) for flag in flags)


def targets(command, cwd):
    """(workspace root, written target) for each rm -r argument that is one."""
    here = cwd
    for segment in SEPARATORS.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        while words and (words[0] in ("sudo", "command", "builtin") or re.fullmatch(r"\w+=\S*", words[0])):
            words = words[1:]
        if not words:
            continue
        if words[0] == "cd" and len(words) == 2 and "$" not in words[1]:
            here = (here / os.path.expanduser(words[1])).resolve()
            continue
        if Path(words[0]).name != "rm":
            continue
        options = [w for w in words[1:] if w.startswith("-") and w != "--"]
        if not recursive(options):
            continue
        for word in words[1:]:
            if word.startswith("-") or "$" in word or "`" in word:
                continue
            expanded = os.path.expanduser(word)
            for match in (glob.glob(expanded, root_dir=here) if glob.has_magic(expanded) else [expanded]):
                path = (here / match).resolve()
                if (path / ".jj" / "repo").is_file():
                    yield path, word


def main():
    data = json.load(sys.stdin)
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    if isinstance(command, list):
        command = shlex.join(command)
    if "rm" not in command:
        return
    found = list(targets(command, Path(data.get("cwd") or ".").resolve()))
    if not found:
        return
    lines = [f"`{word}` is a jj workspace. Remove it with:" for _, word in found[:1]]
    lines += [f"  jj-agent -R {shlex.quote(str(path))} finish --remove" for path, _ in found]
    lines.append("It works for any workspace, including ones made with raw `jj workspace add`. "
                 "It removes the directory and jj's record of it, discards node_modules and other "
                 "rebuildable caches, and stops only if unlanded changes or unsaved files would be "
                 "lost, printing the exact next command. Run it from outside the workspace.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                      "permissionDecision": "deny", "permissionDecisionReason": "\n".join(lines)}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # A hint must never block ordinary work when it fails.
