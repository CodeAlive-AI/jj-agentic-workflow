"""Shared jj 0.46 workspace lifecycle. Reads never snapshot or merge operations."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
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


def prepare(cwd, name, revision, destination=None, session=None, snapshot_caller=False):
    version_check()
    if not snapshot_caller:
        raise Failure("Creation snapshots the caller. Use --snapshot-caller only in an exclusively owned workspace")
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
        # JJ 0.46 requires working-copy updates even for workspace add. The caller
        # explicitly authorized its snapshot; --ignore-working-copy fails halfway.
        run(["jj", "workspace", "add", "--colocate", "--name", name,
                      "-r", base, "-m", f"Task: {name}", str(dest)], workspace)
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


def unaddressed(workspace, base):
    record = manifest(workspace)
    owned = f'({base}..@) | change_id("{record["initial_change"]}")::'
    conflicts = jj(workspace, "log", "-r", f'({owned}) & conflicts()',
                   "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
    if conflicts:
        raise Failure("Resolve conflicts before finishing: " + ", ".join(conflicts))
    return jj(workspace, "log", "-r",
              f'({owned}) & ~::bookmarks() & ~::remote_bookmarks() & ~empty()',
              "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()


def finish(cwd, remove=False, discard_paths=()):
    workspace = root(cwd)
    data = manifest(workspace)
    with lifecycle_lock(workspace):
        jj(workspace, "status", mutate=True)
        outstanding = unaddressed(workspace, data["base"])
        if outstanding:
            raise Failure("Land or park the workspace's changes first: " + ", ".join(outstanding))
        report = {"path": str(workspace), "name": data["name"], "commit": commit(workspace, "@"),
                  "operation": operation(workspace), "removed": False}
        if not remove:
            return report
        doctor(workspace)
        # File names only: never open ignored files. Deleting them requires explicit paths.
        paths = set()
        for extra in [[], ["--ignored"]]:
            paths.update(run(["git", "ls-files", "--others", "--exclude-standard", "-z", *extra],
                             workspace).stdout.split("\0"))
        paths.discard("")
        allowed = []
        for value in discard_paths:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or str(path) in (".", ".jj", ".git"):
                raise Failure(f"Invalid discard path: {value}")
            allowed.append(path)
        leftovers = [p for p in paths if Path(p).parts[0] not in (".jj", ".git")
                     and not any(Path(p) == a or Path(p).is_relative_to(a) for a in allowed)]
        if leftovers:
            raise Failure("Untracked/ignored files would be lost; preserve them before removal: "
                          + ", ".join(sorted(leftovers)[:10]))
        # Retain a recovery receipt outside the deleted workspace.
        receipt = state_dir() / "finished" / (hashlib.sha256(str(workspace).encode()).hexdigest() + ".json")
        atomic_json(receipt, {**data, **report})
        run(["jj", "workspace", "remove", data["name"]], workspace)
        if workspace.exists():
            raise Failure(f"JJ did not remove the directory; inspect it: {workspace}")
        report["removed"] = True
        atomic_json(receipt, {**data, **report})
        return report
