#!/usr/bin/env python3
"""PreToolUse guard: `jj abandon` is the back door around every trunk guard.

`jj land` refuses to move a bookmark sideways or backwards. `jj abandon` moves
it without asking anything: on jj 0.44 a bookmark pointing at an abandoned
commit is *deleted* outright ("Deleted bookmarks: main"), and descendants are
rebased onto the parent. One command therefore removes trunk and rewrites
landed history, and reports it in the same tone as any other success.

The failure mode that produced this guard, twice: an agent resolved a revision
in one command, another writer moved the shared working copy in between, and
the later `jj abandon $old` hit somebody else's landed commit. A revision is
resolved when the command runs, not when the variable was assigned.

Refuses three shapes and prints what to run instead:
  * a target that comes from a shell substitution ($var, $(...), `...`) — its
    value cannot be re-checked here, and staleness is exactly the hazard;
  * a target carrying a bookmark — abandoning it deletes that bookmark;
  * a target already reachable from a bookmark — that is landed history.
Everything else (abandoning your own unlanded change) passes untouched.
Fails open on any error: a guard that breaks the shell is worse than no guard.
"""
import json, os, re, shlex, subprocess, sys

EVENT = os.path.expanduser("~/.local/bin/jj-agent-event")
SUBST = re.compile(r"\$\(|\$\{|\$[A-Za-z_]|`")


def ev(*args):
    subprocess.run([EVENT, *args], capture_output=True, timeout=5, check=False)


def jj(cwd, *args):
    r = subprocess.run(["jj", "--ignore-working-copy", *args],
                       capture_output=True, text=True, timeout=15, cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def abandon_targets(command):
    """Yield the revset arguments of every `jj abandon` in a shell command line."""
    for segment in re.split(r"&&|\|\||[;\n|]", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if len(tokens) < 2 or os.path.basename(tokens[0]) != "jj":
            continue
        # Skip jj's own global flags to find the subcommand.
        i, rest = 1, []
        while i < len(tokens):
            t = tokens[i]
            if t in ("-R", "--repository", "--at-op", "--config", "--config-file"):
                i += 2
                continue
            if t.startswith("-"):
                i += 1
                continue
            rest = tokens[i:]
            break
        if not rest or rest[0] != "abandon":
            continue
        targets, j = [], 1
        while j < len(rest):
            t = rest[j]
            if t in ("-r", "--revisions"):
                if j + 1 < len(rest):
                    targets.append(rest[j + 1])
                j += 2
                continue
            if not t.startswith("-"):
                targets.append(t)
            j += 1
        yield targets or ["@"], segment


def refuse(rule, message):
    ev("abandon-guard-refused", f"rule={rule}")
    print(message, file=sys.stderr)
    return 2


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if "abandon" not in command:
        return 0
    cwd = data.get("cwd") or "."
    if not jj(cwd, "root"):
        return 0

    for targets, segment in abandon_targets(command):
        for target in targets:
            if SUBST.search(target):
                return refuse("abandon-target-from-shell-substitution",
                    f"REFUSED: `jj abandon {target}` takes its target from a shell substitution.\n"
                    "A revision resolves when the command runs, not when the variable was assigned — "
                    "in a shared working copy another writer can move `@` in between, and this is how "
                    "a co-worker's landed commit (and the trunk bookmark on it) gets abandoned.\n"
                    "Resolve and read the target in the same breath, then pass the full commit id:\n"
                    f"  jj --ignore-working-copy log -r {shlex.quote(target)} "
                    "--no-graph -T 'commit_id ++ \" \" ++ bookmarks ++ \" \" ++ description.first_line()'\n"
                    "  jj abandon 'commit_id(\"<full-id-you-just-read>\")'")

            ids = [c for c in jj(cwd, "log", "-r", target, "--no-graph",
                                 "-T", 'commit_id ++ "\\n"').splitlines() if c]
            for cid in ids:
                marks = jj(cwd, "log", "-r", f'commit_id("{cid}")', "--no-graph", "-T", "bookmarks")
                if marks:
                    return refuse("abandon-would-delete-bookmark",
                        f"REFUSED: `jj abandon {target}` resolves to {cid[:12]}, which carries "
                        f"bookmark(s): {marks}.\n"
                        "jj DELETES bookmarks pointing at an abandoned commit (and rebases its "
                        "descendants), so this removes the bookmark and rewrites what it named — "
                        "the move `jj land` exists to refuse, through a back door.\n"
                        "If you meant to move the bookmark, move it: `jj land <rev>`. If you really "
                        "meant to drop this commit, say so explicitly with --retain-bookmarks and "
                        "state to the user that the bookmark moves backwards.")
                landed = jj(cwd, "log", "-r",
                            f'commit_id("{cid}") & ::(bookmarks() | remote_bookmarks())',
                            "--no-graph", "-T", "commit_id")
                if landed:
                    return refuse("abandon-landed-history",
                        f"REFUSED: `jj abandon {target}` resolves to {cid[:12]}, which is already "
                        "reachable from a bookmark — landed history, possibly someone else's.\n"
                        "Abandoning it rebases every descendant and silently changes what the "
                        "bookmark contains. Recover forward instead (`jj new`, `jj restore --from`, "
                        "`jj describe`), or state the case to the user before rewriting landed work.")
    return 0


try:
    sys.exit(main())
except Exception:
    sys.exit(0)
