#!/usr/bin/env python3
"""Stop hook: a writing session may not end with unlanded, unparked jj work.

Invariant: by session end every change is either an ancestor of a bookmark
(landed/parked) or does not exist. If the working-copy lineage holds non-empty
changes outside all bookmarks, block the stop once and tell the agent to
`jj land` or `jj park <name>` (or report a genuine blocker to the user).
Fails open on any error; never blocks twice (stop_hook_active).
"""
import os, json, subprocess, sys

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0
    cwd = data.get("cwd") or "."
    def jj(*args):
        r = subprocess.run(["jj", "--ignore-working-copy", *args],
                           capture_output=True, text=True, timeout=15, cwd=cwd)
        return r.returncode, r.stdout.strip()
    try:
        rc, _ = jj("root")
        if rc != 0:
            return 0
        # Unlanded non-empty work in the working copy's own stack only —
        # other writers' heads are not this session's to block on.
        rc, out = jj("log", "-r",
                     "(::@ | @::) & ~::bookmarks() & ~::remote_bookmarks() & ~empty() & ~conflicts()",
                     "--no-graph", "-T",
                     'commit_id.short() ++ " " ++ description.first_line() ++ "\\n"')
        if rc != 0 or not out:
            return 0
        subprocess.run([os.path.expanduser("~/.local/bin/jj-agent-event"),
                        "session-end-blocked", "rule=unlanded-work-at-session-end",
                        f"heads={len(out.splitlines())}"],
                       capture_output=True, timeout=5, check=False)
        print("This session's jj stack still holds unlanded work:\n" + out +
              "\nLand it (`jj land`), park it (`jj park <name>`), or state the blocker "
              "to the user explicitly. A session may not end with floating changes.",
              file=sys.stderr)
        return 2
    except Exception:
        return 0

sys.exit(main())
