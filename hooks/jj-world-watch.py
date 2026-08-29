#!/usr/bin/env python3
"""Tell the agent when the repository moved under it.

Agents are blind not by choice: they hold a snapshot taken minutes ago while
other writers keep committing, landing and pushing. This hook makes the change
arrive on its own. It is nearly free when nothing happened: the jj operation
head is a filename, so an unchanged repo costs one directory listing.

On a real change it compares against the last state this session saw and speaks
up only about things that invalidate an agent's plan:
  * the trunk bookmark became CONFLICTED (its name stops being a usable revset)
  * local trunk and its remote DIVERGED (neither contains the other)
  * the remote advanced (your base is now stale)
  * another writer moved the trunk
Reports once per distinct state, never repeats itself.
"""
import hashlib, json, os, subprocess, sys

CACHE = os.path.expanduser("~/.cache/jj-world")
EVENT = os.path.expanduser("~/.local/bin/jj-agent-event")


def jj(root, *args, timeout=10):
    r = subprocess.run(["jj", "--ignore-working-copy", *args],
                       capture_output=True, text=True, timeout=timeout, cwd=root)
    return r.stdout.strip() if r.returncode == 0 else ""


def find_root(cwd):
    p = os.path.abspath(cwd)
    while True:
        if os.path.isdir(os.path.join(p, ".jj")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def op_head(root):
    d = os.path.join(root, ".jj", "repo", "op_heads", "heads")
    try:
        return ",".join(sorted(os.listdir(d)))
    except OSError:
        return ""


def trunk_name(root):
    for cand in ("main", "master", "trunk"):
        if jj(root, "log", "-r", f'bookmarks(exact:"{cand}")', "--no-graph", "-T", "commit_id"):
            return cand
    return None


def read_state(root):
    name = trunk_name(root)
    if not name:
        return None
    heads = [l for l in jj(root, "log", "-r", f'bookmarks(exact:"{name}")',
                           "--no-graph", "-T", 'commit_id ++ "\\n"').splitlines() if l]
    remote = jj(root, "log", "-r", f"{name}@origin", "--no-graph", "-T", "commit_id")
    st = {"trunk": name, "local": sorted(heads), "remote": remote, "rel": ""}
    if len(heads) == 1 and remote:
        local = heads[0]
        if local == remote:
            st["rel"] = "same"
        else:
            fwd = jj(root, "log", "-r", f"::{local} & {remote}", "--no-graph", "-T", "commit_id")
            back = jj(root, "log", "-r", f"::{remote} & {local}", "--no-graph", "-T", "commit_id")
            st["rel"] = "ahead" if fwd else ("behind" if back else "diverged")
    return st


def describe(old, new):
    """Return (severity, rule, message) for a meaningful transition, else three Nones."""
    name = new["trunk"]
    if len(new["local"]) > 1:
        if not old or len(old.get("local", [])) <= 1:
            return "high", "bookmark-conflicted", (
                f"The '{name}' bookmark is now CONFLICTED — it points at "
                f"{len(new['local'])} revisions ({', '.join(c[:12] for c in new['local'])}). "
                f"While conflicted, '{name}' is an ambiguous revset: `jj log -r {name}` errors and "
                f"git merge-base answers about only one side, so ANY ancestry claim you make about "
                f"it is unfounded. Reconcile before reasoning or reporting.")
        return None, None, None
    if new["rel"] == "diverged" and (not old or old.get("rel") != "diverged"):
        return "high", "trunk-diverged", (
            f"Local '{name}' and {name}@origin have DIVERGED — neither contains the other "
            f"(local {new['local'][0][:12]}, remote {new['remote'][:12]}). Landing or pushing now "
            f"would drop published work. Rebase the unpublished side onto {name}@origin.")
    if old and new["remote"] and old.get("remote") and new["remote"] != old["remote"]:
        if new["rel"] == "behind":
            return "medium", "remote-advanced-base-stale", (
                f"{name}@origin advanced to {new['remote'][:12]} while you were working: your base "
                f"is stale. Anything you build or verify from the old base may not reflect the "
                f"published trunk.")
        return "medium", "remote-moved", (
            f"{name}@origin moved to {new['remote'][:12]} while you were working (local is "
            f"'{new['rel']}'). Re-check any conclusion that depended on the remote.")
    if old and new["local"] and old.get("local") and new["local"] != old["local"] and len(new["local"]) == 1:
        return "medium", "concurrent-writer-moved-trunk", (
            f"Another writer moved '{name}' to {new['local'][0][:12]} while you were working. "
            f"Re-verify anything you concluded about what is landed. This repository has "
            f"concurrent writers: rewinding operations (jj undo / op restore) would revert their "
            f"work, and a bare jj command in their workspace would snapshot their tree. See "
            f"working-with-jj references/parallel-agents.md.")
    return None, None, None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    root = find_root(data.get("cwd") or ".")
    if not root:
        return 0
    key = hashlib.sha256(root.encode()).hexdigest()[:16]
    session = (data.get("session_id") or "nosession")[:16]
    path = os.path.join(CACHE, f"{key}.{session}.json")
    op = op_head(root)
    try:
        prev = json.load(open(path))
    except Exception:
        prev = None
    if prev and prev.get("op") == op:
        return 0                      # nothing happened — the cheap path
    new = read_state(root)
    if not new:
        return 0
    os.makedirs(CACHE, exist_ok=True)
    sev, rule, msg = describe(prev.get("state") if prev else None, new)
    json.dump({"op": op, "state": new}, open(path, "w"))
    if not prev or not msg:
        return 0                      # first sighting establishes the baseline
    subprocess.run([EVENT, "world-watch-fired", f"rule={rule}",
                    f"severity={sev}", f"repo={os.path.basename(root)}"],
                   capture_output=True, timeout=5, check=False)
    print(f"[repo state changed] {msg}", file=sys.stderr)
    return 2 if sev in ("high", "medium") else 0


try:
    sys.exit(main())
except Exception:
    sys.exit(0)
