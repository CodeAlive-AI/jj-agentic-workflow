"""Shared jj 0.46 workspace lifecycle. Reads never snapshot or merge operations."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time


class Failure(RuntimeError):
    pass


def run(argv, cwd, check=True):
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=120)
    if check and result.returncode:
        raise Failure(result.stderr.strip() or f"Command failed: {argv[0]}")
    return result


def jj(cwd, *args, mutate=False):
    flags = [] if mutate else ["--ignore-working-copy", "--at-op=@"]
    result = run(["jj", "--no-pager", *flags, *args], cwd)
    if mutate:
        run(["jj", "--no-pager", "status"], cwd)
    return result.stdout.strip()


def root(cwd):
    return Path(jj(cwd, "root")).resolve()


def repo_store(workspace):
    entry = workspace / ".jj" / "repo"
    if entry.is_dir():
        return entry.resolve()
    if entry.is_file():
        return (entry.parent / entry.read_text().strip()).resolve(strict=True)
    raise Failure(f"Missing jj repository pointer: {entry}")


def state_dir():
    return Path(os.environ.get("JJ_AGENT_STATE", Path.home() / ".local/state/jj-agent"))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def lifecycle_lock(workspace):
    key = hashlib.sha256(str(repo_store(workspace)).encode()).hexdigest()
    directory = state_dir() / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / key).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def version_check():
    for command, minimum in [("jj", (0, 46, 0)), ("git", (2, 42, 0))]:
        text = run([command, "--version"], Path.cwd()).stdout.strip()
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
        if not match or tuple(map(int, match.groups())) < minimum:
            raise Failure(f"Requires {command} >= {'.'.join(map(str, minimum))}; found {text}")


def operation(workspace):
    return jj(workspace, "op", "log", "-n", "1", "--no-graph", "-T", "id")


def commit(workspace, expression):
    ids = jj(workspace, "log", "-r", expression, "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
    if len(ids) != 1:
        raise Failure(f"Revision must resolve to exactly one commit: {expression}")
    return ids[0]


def manifest(workspace):
    path = workspace / ".jj/jj-agent.json"
    if not path.is_file():
        raise Failure("Unmanaged workspace: lifecycle operations require jj-agent prepare")
    data = json.loads(path.read_text())
    if data["path"] != str(workspace) or data["store"] != str(repo_store(workspace)):
        raise Failure("Workspace identity differs from its creation record")
    return data


def workspace_names(workspace):
    rows = jj(workspace, "workspace", "list", "-T", 'name ++ "\t" ++ self.root() ++ "\n"').splitlines()
    return {name: Path(path).resolve() for name, _, path in (row.partition("\t") for row in rows) if path}


def last_checkout(workspace):
    """(operation id, workspace name) from the working copy's own checkout record.

    The record is a two-field protobuf: 0x12 <len> operation-id bytes, 0x1a <len> name.
    """
    data = (workspace / ".jj/working_copy/checkout").read_bytes()
    fields, at = {}, 0
    while at + 2 <= len(data):
        tag, size = data[at], data[at + 1]
        fields[tag] = data[at + 2:at + 2 + size]
        at += 2 + size
    if 0x12 not in fields or 0x1a not in fields:
        raise Failure(f"Cannot read the working-copy record of {workspace}; inspect it by hand")
    return fields[0x12].hex(), fields[0x1a].decode()


def record(workspace):
    """The creation record, or one adopted for a workspace made with raw `jj workspace add`.

    An adopted workspace has no recorded base, so its own work is everything under @
    that no bookmark keeps: the same set a person would check before deleting it. A
    directory whose workspace jj already forgot is judged by its last snapshot.
    """
    if (workspace / ".jj/jj-agent.json").is_file():
        return manifest(workspace)
    if (workspace / ".jj" / "repo").is_dir():
        raise Failure(f"{workspace} holds the repository itself; it is never finished or removed")
    known = workspace_names(workspace)
    names = [name for name, path in known.items() if path == workspace]
    data = {"path": str(workspace), "store": str(repo_store(workspace)), "base": None,
            "initial_change": None, "owner_session": None, "adopted": True}
    if len(names) == 1:
        return {**data, "name": names[0]}
    op, name = last_checkout(workspace)
    if name in known:
        raise Failure(f"Workspace {name} now lives at {known[name]}, not {workspace}; inspect both")
    head = run(["jj", "--no-pager", "--ignore-working-copy", f"--at-op={op}", "log", "-r", f"{name}@",
                "--no-graph", "-T", "commit_id"], workspace).stdout.strip()
    snapshot = (workspace / ".jj/working_copy/tree_state").stat().st_mtime
    return {**data, "name": name, "forgotten": True, "head": head, "snapshot_time": snapshot}


def prepare(cwd, name, revision, destination=None, session=None, snapshot_caller=False):
    version_check()
    workspace = root(cwd)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise Failure("Workspace name must be 1–64 letters, digits, underscores or hyphens")
    dest = Path(destination).absolute() if destination else workspace / ".workspaces" / name
    if dest != dest.resolve():
        raise Failure("Workspace destination must be normalized and contain no symlinks")
    if dest.exists():
        raise Failure(f"Destination already exists; inspect it instead of retrying: {dest}")
    if workspace == dest or workspace.is_relative_to(dest):
        raise Failure("Destination must not contain the current workspace")
    if dest.is_relative_to(workspace):
        ignored = run(["git", "check-ignore", "--quiet", str(dest.relative_to(workspace))], workspace, False)
        if ignored.returncode != 0:
            raise Failure("Commit a narrow ignore rule for the workspace directory before preparation")
    with lifecycle_lock(workspace):
        base = commit(workspace, revision)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Explicit full sparsity avoids workspace-add's intermediate sparse-copy
        # mutation. Creation can then ignore the caller and materialize only the
        # newly owned child through update-stale. Never retry a failed mode.
        flags = [] if snapshot_caller else ["--ignore-working-copy"]
        run(["jj", *flags, "workspace", "add", "--sparse-patterns", "full", "--colocate", "--name", name,
                      "-r", base, "-m", f"Task: {name}", str(dest)], workspace)
        if not snapshot_caller:
            if any(p.name not in (".jj", ".git") for p in dest.iterdir()):
                raise Failure(f"New workspace is not metadata-only; keep and inspect {dest}")
            run(["jj", "workspace", "update-stale"], dest)
        run(["jj", "status"], dest)
        parent = commit(dest, "@-")
        if parent != base:
            raise Failure(f"Unexpected workspace base; keep and inspect {dest}")
        data = {"name": name, "path": str(dest), "store": str(repo_store(dest)),
                "base": base, "initial_change": jj(dest, "log", "-r", "@", "--no-graph", "-T", "change_id"),
                "owner_session": session, "created_at": int(time.time())}
        atomic_json(dest / ".jj/jj-agent.json", data)
        doctor(dest)
    return dest


def doctor(cwd):
    version_check()
    workspace = root(cwd)
    git_root = Path(run(["git", "rev-parse", "--show-toplevel"], workspace).stdout.strip()).resolve()
    if git_root != workspace:
        raise Failure(f"Git root {git_root} differs from jj root {workspace}; use a new colocated workspace")
    return {"root": str(workspace), "store": str(repo_store(workspace)),
            "operation": operation(workspace), "commit": commit(workspace, "@"),
            "git_root": str(git_root), "managed": (workspace / ".jj/jj-agent.json").is_file()}


# Ignored directories every toolchain rebuilds; removal discards them without asking.
REGENERABLE = {"node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
               ".next", ".turbo", ".venv", ".eslintcache", ".DS_Store"}


def unaddressed(workspace, data):
    if data.get("initial_change"):
        # Descendants of the initial change keep work stacked off @, but once it lands they
        # also hold other workspaces' working copies; what those stand on is theirs.
        initial = f'change_id("{data["initial_change"]}")'
        owned = f'({data["base"]}..@) | {initial} | ({initial}:: ~ ::(working_copies() ~ @))'
    elif data.get("forgotten"):
        owned = f'::{data["head"]} & ~::(bookmarks() | remote_bookmarks() | tags())'
    else:
        owned = "::@ & ~::(bookmarks() | remote_bookmarks() | tags())"
    conflicts = jj(workspace, "log", "-r", f'({owned}) & conflicts()',
                   "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
    if conflicts:
        raise Failure("Resolve conflicts before finishing: " + ", ".join(conflicts))
    return jj(workspace, "log", "-r",
              f'({owned}) & ~::bookmarks() & ~::remote_bookmarks() & ~empty()',
              "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()


def untracked(workspace, revision="@", since=None):
    """Files on disk that jj does not track, each under its top untracked directory.

    Walks the tree itself rather than asking Git, so a non-colocated workspace is checked
    the same way. Rebuildable cache directories are pruned and listed apart, so a directory
    holding only caches is not reported. Names only: no file is opened.
    """
    tracked = set(jj(workspace, "file", "list", "-r", revision, "-T", 'path ++ "\n"').splitlines())
    tracked_dirs = {str(d) for p in tracked for d in Path(p).parents}
    files, regenerable = [], []
    for current, subdirs, names in os.walk(workspace):
        rel = Path(current).relative_to(workspace)
        if rel == Path("."):
            subdirs[:] = [d for d in subdirs if d not in (".jj", ".git")]
            names = [n for n in names if n != ".git"]
        regenerable += [str(rel / d) for d in subdirs if d in REGENERABLE]
        subdirs[:] = [d for d in subdirs if d not in REGENERABLE]
        for name in names:
            path = rel / name
            if name in REGENERABLE:
                regenerable.append(str(path))
            elif str(path) not in tracked:
                files.append(path)
            elif since is not None and max((info := (Path(current) / name).lstat()).st_mtime, info.st_ctime) > since:
                files.append(path)  # Changed after jj's last snapshot of a forgotten workspace.
    found = set()
    for path in files:
        top = path
        for parent in reversed(path.parents[:-1]):
            if str(parent) not in tracked_dirs:
                top = parent
                break
        found.add(str(top) + ("/" if top != path else ""))
    return sorted(found), sorted(regenerable)


def finish(cwd, remove=False, discard_paths=()):
    workspace = root(cwd)
    data = record(workspace)
    with lifecycle_lock(workspace):
        if not data.get("forgotten"):
            try:
                jj(workspace, "status", mutate=True)
            except Failure as error:
                if "stale" not in str(error):
                    raise
                run(["jj", "workspace", "update-stale"], workspace)
                jj(workspace, "status", mutate=True)
        outstanding = unaddressed(workspace, data)
        if outstanding:
            raise Failure("Land or park the workspace's changes first (`jj land <rev>` or "
                          "`jj park <name> <rev>`): " + ", ".join(outstanding))
        head = data.get("head") or commit(workspace, "@")
        report = {"path": str(workspace), "name": data["name"], "commit": head,
                  "operation": operation(workspace), "removed": False, "adopted": bool(data.get("adopted"))}
        if not remove:
            return report
        if (workspace / ".git").exists() and not data.get("forgotten"):
            doctor(workspace)
        allowed = []
        for value in discard_paths:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or str(path) in (".", ".jj", ".git"):
                raise Failure(f"Invalid discard path: {value}")
            allowed.append(path)
        found, regenerable = untracked(workspace, head, data.get("snapshot_time"))
        leftovers = [p for p in found if not any(Path(p) == a or Path(p).is_relative_to(a) for a in allowed)]
        if leftovers:
            flags = " ".join(f"--discard-path {shlex.quote(p.rstrip('/'))}" for p in leftovers[:20])
            raise Failure("Untracked or ignored files would be lost: " + ", ".join(leftovers[:20])
                          + ("" if len(leftovers) <= 20 else f" and {len(leftovers) - 20} more")
                          + ". Move anything worth keeping out, then discard the rest with: "
                          + f"jj-agent -R {shlex.quote(str(workspace))} finish --remove {flags}")
        report["discarded_regenerable"] = regenerable
        # Retain a recovery receipt outside the deleted workspace.
        receipt = state_dir() / "finished" / (hashlib.sha256(str(workspace).encode()).hexdigest() + ".json")
        atomic_json(receipt, {**data, **report})
        if not data.get("forgotten"):
            run(["jj", "workspace", "remove", data["name"]], workspace)
        if workspace.exists():
            # Only already-checked regenerable directories can remain; jj no longer knows the path.
            shutil.rmtree(workspace)
        report["removed"] = True
        atomic_json(receipt, {**data, **report})
        return report
