#!/usr/bin/env python3
"""Real jj/Git pilot fixtures; no existing repository or workspace is modified."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "lib"))
from jj_agent import Failure, commit, doctor, finish, jj, operation, prepare as raw_prepare

def prepare(*args, **kwargs):
    return raw_prepare(*args, snapshot_caller=True, **kwargs)


class WorkspacePilot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jj-agent-pilot-")
        self.lab = Path(self.temp.name).resolve()
        self.repo = self.lab / "repo"
        self.repo.mkdir()
        self.config = self.lab / "jj.toml"
        self.config.write_text('[user]\nname="Pilot Fixture"\nemail="pilot@example.invalid"\n'
                               '[git]\nabandon-unreachable-commits=false\n')
        self.old_env = {k: os.environ.get(k) for k in ["JJ_CONFIG", "JJ_AGENT_STATE", "JJ_WORLD_CACHE"]}
        os.environ.update(JJ_CONFIG=str(self.config), JJ_AGENT_STATE=str(self.lab / "state"),
                          JJ_WORLD_CACHE=str(self.lab / "world"))
        self.cmd("jj", "git", "init", "--colocate")
        (self.repo / "base.txt").write_text("base\n")
        (self.repo / ".gitignore").write_text(".workspaces/\n.local-ignore.txt\n")
        self.cmd("jj", "describe", "-m", "base")
        self.cmd("jj", "bookmark", "create", "main", "-r", "@")
        self.cmd("jj", "new", "-m", "parent task")

    def tearDown(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp.cleanup()

    def cmd(self, *args, cwd=None):
        result = subprocess.run(args, cwd=cwd or self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def hook(self, script, cwd, event, session="owner", **fields):
        return subprocess.run([sys.executable, str(SOURCE / "hooks" / script)], input=json.dumps(
            {"cwd": str(cwd), "hook_event_name": event, "session_id": session, **fields}),
            capture_output=True, text=True)

    def test_prepare_defaults_to_saved_caller_and_allows_explicit_snapshot(self):
        (self.repo / "unsaved.txt").write_text("caller work\n")
        old_commit = commit(self.repo, "@")
        safe = raw_prepare(self.repo, "safe", "main")
        self.assertEqual(commit(self.repo, "@"), old_commit)
        self.assertTrue((safe / "base.txt").exists())
        self.assertFalse((safe / "unsaved.txt").exists())
        child = prepare(self.repo, "child", "main")
        self.assertNotEqual(commit(self.repo, "@"), old_commit)
        self.assertTrue((self.repo / "unsaved.txt").exists())
        report = doctor(child)
        self.assertEqual(report["root"], report["git_root"])
        before = operation(child)
        doctor(child)
        self.assertEqual(operation(child), before)
        self.assertEqual(commit(child, "@-"), commit(self.repo, "main"))
        with self.assertRaises(Failure):
            prepare(self.repo, "child", "main")

    def test_world_watch_observes_shared_store_from_child(self):
        child = prepare(self.repo, "watch", "main")
        first = self.hook("jj-world-watch.py", child, "PostToolUse")
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.repo / "advance.txt").write_text("new trunk\n")
        self.cmd("jj", "describe", "-m", "advance")
        self.cmd("jj", "bookmark", "set", "main", "-r", "@")
        result = self.hook("jj-world-watch.py", child, "PostToolUse")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Another writer moved", result.stderr)

    def test_finish_refuses_floating_work_and_ignored_files(self):
        child = prepare(self.repo, "finish", "main")
        (child / "task.txt").write_text("work\n")
        with self.assertRaisesRegex(Failure, "Land or park"):
            finish(child, remove=True)
        self.cmd("jj", "bookmark", "create", "parked/task", "-r", "@", cwd=child)
        (child / ".local-ignore.txt").write_text("disposable fixture\n")
        with self.assertRaisesRegex(Failure, "would be lost"):
            finish(child, remove=True)
        self.assertTrue(child.exists())
        result = finish(child, remove=True, discard_paths=[".local-ignore.txt"])
        self.assertTrue(result["removed"])
        self.assertFalse(child.exists())
        self.assertIn("task.txt", self.cmd("jj", "--ignore-working-copy", "file", "list", "-r", "parked/task"))
        self.assertNotIn(str(child), self.cmd("git", "worktree", "list", "--porcelain"))

    def raw_workspace(self, name, *flags):
        path = self.repo / ".workspaces" / name
        path.parent.mkdir(exist_ok=True)
        self.cmd("jj", "workspace", "add", *flags, "--name", name, "-r", "main", str(path))
        return path

    def test_finish_adopts_raw_workspaces_and_discards_rebuildable_caches(self):
        for flags in [(), ("--colocate",)]:
            child = self.raw_workspace("raw" + "".join(flags).replace("-", ""), *flags)
            (child / "node_modules/pkg").mkdir(parents=True)
            (child / "node_modules/pkg/index.js").write_text("cache\n")
            (child / "sub/__pycache__").mkdir(parents=True)
            (child / "sub/__pycache__/m.pyc").write_text("cache\n")
            (self.repo / ".gitignore").write_text(".workspaces/\n.local-ignore.txt\nnode_modules/\n__pycache__/\n")
            (child / ".gitignore").write_text((self.repo / ".gitignore").read_text())
            self.cmd("jj", "describe", "-m", "ignore caches", cwd=child)
            self.cmd("jj", "bookmark", "create", "parked/" + child.name, "-r", "@", cwd=child)
            result = finish(child, remove=True)
            self.assertTrue(result["removed"] and result["adopted"], result)
            self.assertIn("node_modules", result["discarded_regenerable"])
            self.assertFalse(child.exists())
            self.assertNotIn(child.name, self.cmd("jj", "workspace", "list"))

    def test_adopted_finish_still_refuses_lost_work(self):
        child = self.raw_workspace("rawwork")
        (child / "task.txt").write_text("work\n")
        with self.assertRaisesRegex(Failure, "Land or park"):
            finish(child, remove=True)
        self.cmd("jj", "bookmark", "create", "parked/rawwork", "-r", "@", cwd=child)
        (child / ".local-ignore.txt").write_text("notes\n")
        with self.assertRaisesRegex(Failure, "--discard-path .local-ignore.txt"):
            finish(child, remove=True)
        self.assertTrue(child.exists())
        self.assertTrue(finish(child, remove=True, discard_paths=[".local-ignore.txt"])["removed"])

    def test_finish_clears_a_directory_jj_already_forgot(self):
        child = self.raw_workspace("forgot")
        (child / "task.txt").write_text("work\n")
        self.cmd("jj", "status", cwd=child)
        self.cmd("jj", "workspace", "forget", "forgot")
        with self.assertRaisesRegex(Failure, "Land or park"):
            finish(child, remove=True)
        head = finish.__globals__["last_checkout"](child)
        self.assertEqual(head[1], "forgot")
        commit_id = self.cmd("jj", "--ignore-working-copy", f"--at-op={head[0]}", "log", "-r", "forgot@",
                             "--no-graph", "-T", "commit_id")
        self.cmd("jj", "bookmark", "create", "parked/forgot", "-r", commit_id)
        import time; time.sleep(0.05)
        (child / "base.txt").write_text("edited after the last snapshot\n")
        with self.assertRaisesRegex(Failure, "base.txt"):
            finish(child, remove=True)
        result = finish(child, remove=True, discard_paths=["base.txt"])
        self.assertTrue(result["removed"])
        self.assertFalse(child.exists())

    def test_primary_checkout_is_never_finished(self):
        with self.assertRaisesRegex(Failure, "holds the repository"):
            finish(self.repo, remove=True)
        self.assertTrue((self.repo / ".jj/repo").is_dir())

    def test_rm_hook_redirects_only_workspace_roots(self):
        child = self.raw_workspace("rmhint")
        (child / "scratch").mkdir()
        def decision(command, cwd=self.repo):
            result = self.hook("jj-rm-workspace.py", cwd, "PreToolUse", tool_name="Bash",
                               tool_input={"command": command})
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else None
        for command, cwd in [("rm -rf .workspaces/rmhint", self.repo), (f"rm -fr {child}/", self.lab),
                             ("cd .workspaces && rm -r -f rmhint", self.repo), ("rm -rf .workspaces/*", self.repo)]:
            output = decision(command, cwd)
            self.assertEqual(output["permissionDecision"], "deny", command)
            self.assertIn(f"jj-agent -R {child} finish --remove", output["permissionDecisionReason"])
        for command in ["rm -rf .workspaces/rmhint/scratch", "rm .workspaces/rmhint/base.txt",
                        "rm -rf \"$WS\"", "echo rm -rf", "rm -rf ."]:
            self.assertIsNone(decision(command), command)
        self.assertTrue(child.exists())

    def test_stop_only_checks_owner(self):
        child = prepare(self.repo, "ownership", "main")
        started = self.hook("jj-session.py", child, "SessionStart")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("Git and jj roots agree", started.stdout)
        (child / "task.txt").write_text("owned\n")
        result = self.hook("jj-session.py", child, "Stop", session="reviewer")
        self.assertEqual(result.stdout, "")
        result = self.hook("jj-session.py", child, "Stop")
        self.assertEqual(json.loads(result.stdout)["decision"], "block")
        result = self.hook("jj-session.py", child, "Stop", stop_hook_active=True)
        self.assertEqual(result.stdout, "")
        result = self.hook("jj-session.py", child, "SubagentStop")
        self.assertEqual(result.stdout, "")

    def test_claude_lifecycle_contract_and_safe_cleanup(self):
        result = self.hook("jj-worktree.py", self.repo, "WorktreeCreate", name="claude-pilot")
        self.assertEqual(result.returncode, 0, result.stderr)
        child = Path(result.stdout.strip())
        self.assertEqual(doctor(child)["root"], str(child))
        result = self.hook("jj-worktree.py", self.repo, "WorktreeRemove", worktree_path=str(child))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(child.exists())

    def test_cross_workspace_undo_refused_and_forward_recovery_preserves_work(self):
        child = prepare(self.repo, "undo", "main")
        self.cmd("jj", "describe", "-m", "caller mistake")
        (child / "other.txt").write_text("keep\n")
        self.cmd("jj", "describe", "-m", "other real work", cwd=child)
        saved = commit(child, "@")
        result = subprocess.run(["jj", "undo"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace", result.stderr)
        self.assertEqual(commit(child, "@"), saved)
        self.cmd("jj", "describe", "-m", "caller fixed")
        self.assertEqual(commit(child, "@"), saved)

    def test_abandon_guard_contracts(self):
        for command in ["jj abandon main", ["jj", "abandon", "main"], "jj -R /unknown abandon main"]:
            result = self.hook("jj-abandon-guard.py", self.repo, "PreToolUse", tool_name="Bash",
                               tool_input={"command": command})
            self.assertEqual(result.returncode, 2, result.stderr)
        result = self.hook("jj-abandon-guard.py", self.repo, "PreToolUse", tool_name="Bash",
                           tool_input={"command": "jj status"})
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.hook("jj-abandon-guard.py", self.lab, "PreToolUse", tool_name="Bash",
                           tool_input={"command": "echo abandon"})
        self.assertEqual(result.returncode, 0, result.stderr)
        own = commit(self.repo, "@")
        result = self.hook("jj-abandon-guard.py", self.repo, "PreToolUse", tool_name="Bash",
                           tool_input={"command": f"jj abandon {own}"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stepping_off_task_does_not_hide_unaddressed_work(self):
        child = prepare(self.repo, "stepped", "main")
        (child / "task.txt").write_text("keep\n")
        self.cmd("jj", "describe", "-m", "owned task", cwd=child)
        self.cmd("jj", "new", "main", "-m", "new task", cwd=child)
        with self.assertRaisesRegex(Failure, "Land or park"):
            finish(child, remove=True)

    def test_observation_failure_is_visible(self):
        # Removing the binary from PATH must not turn failure into "unchanged".
        child = prepare(self.repo, "failure", "main")
        result = subprocess.run([sys.executable, str(SOURCE / "hooks/jj-world-watch.py")],
                                input=json.dumps({"cwd": str(child), "session_id": "test"}),
                                env={**os.environ, "PATH": "/no-tools"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("observation unavailable", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
