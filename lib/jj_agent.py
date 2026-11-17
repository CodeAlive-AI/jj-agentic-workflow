"""Shared jj 0.47 workspace lifecycle. Reads never snapshot or merge operations."""
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


def run(argv, cwd, check=True, timeout=120):
    try:
        result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure(f"{Path(argv[0]).name} did not finish within {timeout} s; rerun when the machine is less busy")
    if check and result.returncode:
        raise Failure(result.stderr.strip() or f"Command failed: {argv[0]}")
    return result


def jj(cwd, *args, mutate=False, at="@"):
    flags = [] if mutate else ["--ignore-working-copy", f"--at-op={at}"]
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
    for command, minimum in [("jj", (0, 47, 0)), ("git", (2, 42, 0))]:
        text = run([command, "--version"], Path.cwd()).stdout.strip()
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
        if not match or tuple(map(int, match.groups())) < minimum:
            raise Failure(f"Requires {command} >= {'.'.join(map(str, minimum))}; found {text}")


def operation(workspace):
    return jj(workspace, "op", "log", "-n", "1", "--no-graph", "-T", "id")


def commit(workspace, expression, at="@"):
    ids = jj(workspace, "log", "-r", expression, "--no-graph", "-T", 'commit_id ++ "\n"', at=at).splitlines()
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
        # One saved-state view: the base and the caller's commit come from the operation
        # that workspace add then builds on.
        op = operation(workspace)
        base = commit(workspace, revision, at=op)
        caller = commit(workspace, "@", at=op)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # jj 0.47 refuses `workspace add --ignore-working-copy`. Loading an exact operation ID
        # (never `@`, which jj treats as the head and snapshots) leaves the caller's disk
        # unread and still materializes the new child. If another process wrote an operation
        # meanwhile, jj reconciles the two heads on the child's next command, as for any
        # concurrent writer. Full sparsity avoids the sparse-copy step. Never retry a failed mode.
        flags = [] if snapshot_caller else [f"--at-op={op}"]
        run(["jj", *flags, "workspace", "add", "--sparse-patterns", "full", "--colocate", "--name", name,
                      "-r", base, "-m", f"Task: {name}", str(dest)], workspace)
        run(["jj", "status"], dest)
        parent = commit(dest, "@-")
        if parent != base:
            raise Failure(f"Unexpected workspace base; keep and inspect {dest}")
        if not snapshot_caller and commit(workspace, "@") != caller:
            raise Failure(f"The caller's working-copy commit changed during preparation (another writer "
                          f"in the caller?); keep {dest}, read `jj op log` in the caller, then decide")
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
# A repository names its own rebuildable caches here, one directory or file name per line.
REGENERABLE_FILE = ".jj-agent-regenerable"


def regenerable_names(workspace):
    path = workspace / REGENERABLE_FILE
    names = set(REGENERABLE)
    if not path.is_file():
        return names
    for line in path.read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if not name:
            continue
        if "/" in name or name in (".", "..", ".jj", ".git"):
            raise Failure(f"{REGENERABLE_FILE}: invalid name {name!r}; list bare cache names such as .impact")
        names.add(name)
    return names


KEPT = "::(bookmarks() | remote_bookmarks() | tags())"


def task_sessions(workspace, data):
    """Agent-Session values of the task's own commits, plus the recorded owner."""
    own = f'change_id("{data["initial_change"]}") | (({data["base"]}..@) ~ {KEPT})'
    found = {s for row in commit_rows(workspace, own) for s in row["sessions"]}
    return found | ({data["owner_session"]} if data.get("owner_session") else set())


def unaddressed(workspace, data):
    if data.get("initial_change"):
        # Descendants of the initial change keep work stacked off @, but once it lands they
        # also hold other workspaces' working copies; what those stand on is theirs.
        initial = f'change_id("{data["initial_change"]}")'
        direct = f'({data["base"]}..@) | {initial}'
        stacked = f'({initial}:: ~ ::(working_copies() ~ @)) ~ ({direct})'
        owned = f'{direct} | {stacked}'
        # Once a bookmark holds the initial change, other writers build on it too. A stacked
        # commit that names only other Agent-Sessions is theirs (2026-11-09: landed tasks
        # could not be removed for other sessions' floating commits). Unsigned ones stay ours.
        if jj(workspace, "log", "-r", f"{initial} & {KEPT}", "--no-graph", "-T", "commit_id"):
            mine = task_sessions(workspace, data)
            foreign = [row["commit"] for row in commit_rows(workspace, f"({stacked}) ~ {KEPT}")
                       if mine and row["sessions"] and not mine.intersection(row["sessions"])]
            if foreign:
                owned = f'({owned}) ~ ({" | ".join(foreign)})'
    elif data.get("forgotten"):
        owned = f'::{data["head"]} & ~{KEPT}'
    else:
        owned = f"::@ & ~{KEPT}"
    conflicts = jj(workspace, "log", "-r", f'({owned}) & conflicts()',
                   "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()
    if conflicts:
        raise Failure("Resolve conflicts before finishing: " + ", ".join(conflicts))
    return jj(workspace, "log", "-r",
              f'({owned}) & ~::bookmarks() & ~::remote_bookmarks() & ~empty()',
              "--no-graph", "-T", 'commit_id ++ "\n"').splitlines()


def untracked(workspace, revision="@", since=None, caches=None):
    """Files on disk that jj does not track, each under its top untracked directory.

    Walks the tree itself rather than asking Git, so a non-colocated workspace is checked
    the same way. Rebuildable cache directories are pruned and listed apart, so a directory
    holding only caches is not reported. Names only: no file is opened.
    """
    caches = regenerable_names(workspace) if caches is None else caches
    tracked = set(jj(workspace, "file", "list", "-r", revision, "-T", 'path ++ "\n"').splitlines())
    tracked_dirs = {str(d) for p in tracked for d in Path(p).parents}
    files, regenerable = [], []
    for current, subdirs, names in os.walk(workspace):
        rel = Path(current).relative_to(workspace)
        if rel == Path("."):
            subdirs[:] = [d for d in subdirs if d not in (".jj", ".git")]
            names = [n for n in names if n != ".git"]
        regenerable += [str(rel / d) for d in subdirs if d in caches]
        subdirs[:] = [d for d in subdirs if d not in caches]
        for name in names:
            path = rel / name
            if name in caches:
                regenerable.append(str(path))
            elif str(path) not in tracked:
                files.append(path)
            elif since is not None:
                try:
                    info = (Path(current) / name).lstat()
                except FileNotFoundError:
                    continue  # Deleted while walking: nothing left to lose.
                if max(info.st_mtime, info.st_ctime) > since:
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


def open_files():
    """(command, path) for every file, directory and mapping other processes hold open.

    One pass for the whole machine: `lsof +D <dir>` per workspace stats every file of the
    tree and on a loaded VM outlived the subprocess timeout (2026-11-17). Linux reads /proc;
    macOS runs one `lsof` without +D. Processes this user cannot inspect are not listed.
    """
    me, held = os.getpid(), []
    proc = Path("/proc")
    if (proc / "self" / "fd").is_dir():
        for entry in proc.iterdir():
            if not entry.name.isdigit() or int(entry.name) == me:
                continue
            try:
                command = (entry / "comm").read_text().strip()
                links = [entry / "cwd", entry / "root", entry / "exe", *(entry / "fd").iterdir()]
            except OSError:
                continue  # Exited, or another user's process.
            paths = set()
            for link in links:
                try:
                    paths.add(os.readlink(link))
                except OSError:
                    pass
            try:
                paths.update(line.split(None, 5)[5] for line in (entry / "maps").read_text().splitlines()
                             if len(line.split(None, 5)) == 6)
            except OSError:
                pass
            held += [(command, p) for p in paths if p.startswith("/")]
        return held
    result = run(["lsof", "-n", "-P", "-w", "-F", "pcn"], Path("/"), check=False)
    pid = command = None
    for line in result.stdout.splitlines():
        if line.startswith("p"):
            pid, command = int(line[1:]), None
        elif line.startswith("c"):
            command = line[1:]
        elif line.startswith("n") and pid != me and command:
            held.append((command, line[1:]))
    return held


def open_processes(path, held=None):
    """Commands holding files or a working directory under path, deduplicated."""
    held = open_files() if held is None else held
    inside = str(Path(path).resolve())
    return sorted({command for command, p in held if p == inside or p.startswith(inside + os.sep)})


def commit_rows(workspace, revset):
    template = ('commit_id ++ "\\t" ++ description.first_line() ++ "\\t" ++ '
                'description.lines().filter(|l| l.starts_with("Agent-Session:")).join(" ") ++ "\\n"')
    rows = []
    for line in jj(workspace, "log", "-r", revset, "--no-graph", "-T", template).splitlines():
        commit_id, title, sessions = (line.split("\t") + ["", ""])[:3]
        rows.append({"commit": commit_id, "title": title,
                     "sessions": sorted({s.strip() for s in sessions.split("Agent-Session:") if s.strip()})})
    return rows


def survey(cwd, idle_hours=24.0):
    """Read-only report on every workspace of the repository: what still keeps it.

    Never snapshots, rebases or removes. `removable` means `finish --remove` should succeed
    and nothing touched the directory within idle_hours; it cannot know that an idle owner
    session will be resumed, so ask a live owner first.
    """
    version_check()
    here = root(cwd)
    now = time.time()
    rows = []
    try:
        held, held_error = open_files(), None
    except (Failure, OSError) as error:
        held, held_error = None, f"open files could not be listed ({error}); ask before removing"
    for name, path in sorted(workspace_names(here).items()):
        row = {"name": name, "path": str(path), "reasons": []}
        rows.append(row)
        if (path / ".jj" / "repo").is_dir():
            row["verdict"] = "primary"
            continue
        if not path.is_dir():
            row["verdict"] = "missing"
            row["reasons"].append(f"directory is gone; run: jj workspace forget {shlex.quote(name)}")
            continue
        try:
            data = record(path)
            row["owner_session"] = data.get("owner_session")
            state = path / ".jj/working_copy/tree_state"
            snapshot = state.stat().st_mtime if state.exists() else None
            row["last_snapshot"] = (time.strftime("%Y-%m-%d %H:%M", time.localtime(snapshot))
                                    if snapshot else None)
            head = data.get("head") or commit(path, "@")
            outstanding = unaddressed(path, data)
            if outstanding:
                row["outstanding"] = commit_rows(path, " | ".join(outstanding))
                row["reasons"].append("unlanded, unparked commits (land or park them, or ask their owner)")
            if data.get("initial_change"):
                row["sessions"] = sorted(task_sessions(path, data))
            found, _ = untracked(path, head, snapshot)
            if found:
                row["unsaved"] = found[:20]
                row["reasons"].append("files jj has not recorded (untracked, ignored or edited since the "
                                      "last snapshot); finish --remove would refuse")
            if held_error:
                row["reasons"].append(held_error)
            processes = open_processes(path, held) if held is not None else []
            if processes:
                row["open_by"] = processes
                row["reasons"].append("processes have files open inside")
            if snapshot and now - snapshot < idle_hours * 3600:
                row["reasons"].append(f"used within the last {idle_hours:g} h")
        except (Failure, OSError) as error:
            # One workspace changing under the survey (agents work meanwhile) is a reason, not a crash.
            row["reasons"].append(str(error))
        if not row["reasons"]:
            row["verdict"] = "removable"
            row["next"] = f"jj-agent -R {shlex.quote(str(path))} finish --remove"
        elif row.get("open_by") or any(r.startswith("used within") for r in row["reasons"]):
            row["verdict"] = "active"
        else:
            row["verdict"] = "blocked"
    return rows
