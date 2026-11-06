#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Route only a configured project's push checks; ordinary Bash never snapshots JJ."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jj_agent import repo_store, root


def deny(message, reason="tool"):
    try:
        subprocess.run([os.path.expanduser("~/.local/bin/jj-agent-event"), "push-refused",
                        "rule=push-gate", f"reason={reason}"], capture_output=True, timeout=5, check=False)
    except Exception:
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny", "permissionDecisionReason": message}}))


SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&"}
PREFIXES = {"sudo", "command", "builtin", "exec", "env", "time", "nohup", "nice"}
SHELLS = {"bash", "sh", "zsh", "dash"}
JJ_VALUE_OPTIONS = {"-R", "--repository", "--at-op", "--at-operation", "--config", "--config-file", "--color"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def subcommands(words, value_options):
    """The words after the program that are not options or option values."""
    found, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif word in value_options:
            skip = True
        elif not word.startswith("-"):
            found.append(word)
    return found


def find_push(command, depth=0):
    """Return (preceded_by_cd, push_words) for the first real jj/git push, or None.

    Quoted text, search patterns and file names that mention a push are not pushes;
    `bash -c '...'` and `eval ...` are read inside. Unparseable input falls back to
    a conservative pattern so a real push is never waved through.
    """
    try:
        lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        if re.search(r"\b(?:jj|git)\b.*\bpush\b", command):
            return (bool(re.search(r"(?:^|[;&|])\s*cd\s", command)), command.split())
        return None
    moved = False
    segment = []
    for token in [*tokens, ";"]:
        if token not in SEPARATORS:
            segment.append(token)
            continue
        words = segment
        segment = []
        while words:
            if words[0] in PREFIXES:
                words = words[1:]
                while words and words[0].startswith("-"):
                    words = words[1:]
            elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
                words = words[1:]
            else:
                break
        if not words:
            continue
        name = Path(words[0]).name
        if name in ("cd", "pushd"):
            moved = True
        elif name in SHELLS and "-c" in words[1:] and depth < 3:
            body = words[words.index("-c") + 1:words.index("-c") + 2]
            found = find_push(body[0], depth + 1) if body else None
            if found:
                return (moved or found[0], found[1])
        elif name == "eval" and depth < 3:
            found = find_push(" ".join(words[1:]), depth + 1)
            if found:
                return (moved or found[0], found[1])
        elif name == "jj" and subcommands(words, JJ_VALUE_OPTIONS)[:2] == ["git", "push"]:
            return (moved, words)
        elif name == "git" and subcommands(words, GIT_VALUE_OPTIONS)[:1] == ["push"]:
            return (moved, words)
    return None


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
    push = find_push(command)
    if push is None:
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
    moved, words = push
    if moved or any(w in ("-R", "-C", "--repository") or w.startswith(("-R", "-C", "--repository="))
                    for w in words):
        return deny("Nothing in this command ran. A push routed through cd, -R, -C or --repository "
                    "cannot be checked against the right tip. Run the push as its own command with the "
                    f"tool cwd set to the workspace: {' '.join(words)}", reason="route")
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
