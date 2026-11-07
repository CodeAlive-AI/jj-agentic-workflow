#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read-only observation and exact lifecycle ownership regressions."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_workspace_integration as fixtures

sys.path.insert(0, str(fixtures.SOURCE / "lib"))
from jj_agent import commit, operation, prepare


class SelectedHooks(unittest.TestCase):
    setUp = fixtures.WorkspacePilot.setUp
    tearDown = fixtures.WorkspacePilot.tearDown
    cmd = fixtures.WorkspacePilot.cmd
    hook = fixtures.WorkspacePilot.hook

    def lifecycle(self, event, session="owner", cwd=None, **fields):
        return subprocess.run([sys.executable, str(fixtures.SOURCE / "hooks/jj-claude-worktree.py"),
                               "--project", str(self.repo)], input=json.dumps({
                                   "hook_event_name": event, "session_id": session,
                                   "cwd": str(cwd or self.repo), **fields}), text=True, capture_output=True)

    def test_context_cannot_claim_snapshot_or_block(self):
        child = prepare(self.repo, "read-only", "main")
        record = child / ".jj/jj-agent.json"
        before_record = record.read_bytes()
        before_commit, before_op = commit(child, "@"), operation(child)
        (child / "unsaved.txt").write_text("must not be captured\n")
        for event in ["SessionStart", "PostCompact", "Stop", "SubagentStop"]:
            result = self.hook("jj-context.py", child, event)
            self.assertEqual(result.returncode, 0, result.stderr)
            if event in ("SessionStart", "PostCompact"):
                message = json.loads(result.stdout)
                self.assertEqual(set(message), {"hookSpecificOutput"})
                self.assertIn("Git and JJ roots agree", result.stdout)
            else:
                self.assertEqual(result.stdout, "")
            self.assertEqual(record.read_bytes(), before_record)
            self.assertEqual(commit(child, "@"), before_commit)
            self.assertEqual(operation(child), before_op)

    def test_attribution_checks_emitted_commit_not_neighbour(self):
        (self.repo / "owned.txt").write_text("owned\n")
        message = "Own work\n\nModel: fixture\nAgent-Session: owner"
        result = subprocess.run(["jj", "describe", "-m", message], cwd=self.repo,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        before = commit(self.repo, "@")
        (self.repo / "unsaved.txt").write_text("not part of the report\n")
        response = {"stdout": result.stdout, "stderr": result.stderr, "exit_code": 0}
        checked = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                            tool_input={"command": "jj describe -m 'Own work'"}, tool_response=response)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout, "")  # Parent has no attribution; it must not be checked.
        self.assertEqual(commit(self.repo, "@"), before)

    def test_attribution_ignores_unparseable_shell(self):
        command = "python3 - <<'EOF'\nprint(\"it's\")\nEOF"
        checked = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                            tool_input={"command": command},
                            tool_response={"stdout": "it's\n", "stderr": "", "exit_code": 0})
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout, "")

    def test_attribution_advice_never_blocks_and_requires_output_evidence(self):
        (self.repo / "owned.txt").write_text("owned\n")
        result = subprocess.run(["jj", "describe", "-m", "Own work"], cwd=self.repo,
                                capture_output=True, text=True)
        own = commit(self.repo, "@")
        checked = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                            tool_input={"command": ["jj", "describe", "-m", "Own work"]},
                            tool_response={"stdout": result.stdout, "stderr": result.stderr})
        self.assertEqual(checked.returncode, 0)
        data = json.loads(checked.stdout)
        self.assertEqual(set(data), {"hookSpecificOutput"})
        self.assertIn(own[:12], checked.stdout)
        self.assertIn("Model, Agent-Session", checked.stdout)
        no_evidence = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                                tool_input={"command": "jj describe -m x"}, tool_response={"stdout": ""})
        self.assertIn("not checked", no_evidence.stdout)
        spoofed = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                           tool_input={"command": "jj describe -m x; echo fake"},
                           tool_response={"stderr": result.stderr})
        self.assertEqual(spoofed.stdout, "")
        for command in ["jj describe -r @- -m x", "jj describe @- -m x",
                        "jj squash -m x", "jj split -m x owned.txt", "jj new --no-edit"]:
            uncertain = self.hook("jj-attribution.py", self.repo, "PostToolUse", tool_name="Bash",
                                  tool_input={"command": command},
                                  tool_response={"stderr": result.stderr})
            self.assertIn("not checked", uncertain.stdout)
            self.assertNotIn(own[:12], uncertain.stdout)
        stop = self.hook("jj-attribution.py", self.repo, "Stop", tool_name="Bash",
                        tool_input={"command": "jj describe -m x"})
        self.assertEqual(stop.stdout, "")

    def test_create_leaves_unsaved_caller_and_binds_only_child(self):
        before = commit(self.repo, "@")
        (self.repo / "unsaved.txt").write_text("caller only\n")
        created = self.lifecycle("WorktreeCreate", name="isolated")
        self.assertEqual(created.returncode, 0, created.stderr)
        child = Path(created.stdout.strip())
        self.assertEqual(commit(self.repo, "@"), before)
        self.assertTrue((child / "base.txt").is_file())
        self.assertFalse((child / "unsaved.txt").exists())
        record = json.loads((child / ".jj/jj-agent.json").read_text())
        self.assertEqual(record["owner_session"], "owner")
        self.assertEqual(record["lifecycle_host"], "claude")

    def test_remove_refuses_other_owner_and_ignored_files(self):
        created = self.lifecycle("WorktreeCreate", name="cleanup")
        self.assertEqual(created.returncode, 0, created.stderr)
        child = Path(created.stdout.strip())
        before = operation(child)
        wrong = self.lifecycle("WorktreeRemove", session="reviewer", worktree_path=str(child))
        self.assertNotEqual(wrong.returncode, 0)
        self.assertEqual(operation(child), before)
        (child / ".local-ignore.txt").write_text("keep\n")
        ignored = self.lifecycle("WorktreeRemove", worktree_path=str(child))
        self.assertNotEqual(ignored.returncode, 0)
        self.assertTrue(child.exists())
        (child / ".local-ignore.txt").unlink()
        removed = self.lifecycle("WorktreeRemove", worktree_path=str(child))
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(child.exists())

    def test_push_router_never_snapshots_on_normal_commands_and_fails_loudly(self):
        script = fixtures.SOURCE / "hooks/jj-push-gate.py"
        (self.repo / "unsaved.txt").write_text("caller only\n")
        before = commit(self.repo, "@")
        def check(command):
            return subprocess.run([sys.executable, str(script), "--project", str(self.repo)],
                input=json.dumps({"cwd": str(self.repo), "hook_event_name": "PreToolUse",
                                  "tool_name": "Bash", "tool_input": {"command": command}}),
                capture_output=True, text=True)
        normal = check("jj log")
        self.assertEqual(normal.stdout, "")
        self.assertEqual(commit(self.repo, "@"), before)
        missing = check("jj git push --bookmark main")
        self.assertEqual(json.loads(missing.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(commit(self.repo, "@"), before)
        # Commands that only mention a push are not pushes, even with -R or cd.
        for mention in ("grep -R push scripts", "echo 'jj git push'", "git log --grep push",
                        "cd sub && rg 'git push' .", "ssh host 'rg push'"):
            self.assertEqual(check(mention).stdout, "", mention)
        routed = json.loads(check("cd sub && jj git push -b main").stdout)["hookSpecificOutput"]
        self.assertEqual(routed["permissionDecision"], "deny")
        self.assertIn("Nothing in this command ran", routed["permissionDecisionReason"])
        self.assertIn("-b main", routed["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
