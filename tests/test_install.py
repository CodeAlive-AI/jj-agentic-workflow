#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

INSTALL = Path(__file__).resolve().parents[1] / "bin/jj-agent-install"


class InstallTest(unittest.TestCase):
    def test_removes_retired_hooks_without_enabling_hosts_and_rolls_back(self):
        with tempfile.TemporaryDirectory(prefix="jj-install-pilot-") as temp:
            home = Path(temp)
            (home / ".codex").mkdir()
            (home / ".claude").mkdir()
            config = home / ".codex/config.toml"
            config.write_text('# keep comment\nmodel="fixture"\n[features]\nhooks = false # existing\n')
            hooks = home / ".codex/hooks.json"
            original = {"hooks": {"PreToolUse": [{"matcher": "^Bash$", "hooks": [
                {"type": "command", "command": "unrelated-check"},
                {"type": "command", "command": "python3 /old/hooks/jj-abandon-guard.py"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "python3 /old/hooks/jj-session.py"}]}]}}
            hooks.write_text(json.dumps(original))
            settings = home / ".claude/settings.json"
            settings.write_text('{"worktree":{"baseRef":"head"},"permissions":{"deny":["fixture"]}}')
            before = {p: p.read_bytes() for p in [config, hooks, settings]}
            def run(*args, success=True):
                result = subprocess.run([sys.executable, str(INSTALL), "--target-home", str(home), *args], capture_output=True, text=True)
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                return result
            installed = json.loads(run().stdout)
            self.assertFalse(tomllib.loads(config.read_text())["features"]["hooks"])
            self.assertEqual(config.read_bytes(), before[config])
            self.assertIn("# keep comment", config.read_text())
            data = json.loads(hooks.read_text())
            self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"],
                             [{"type": "command", "command": "unrelated-check"}])
            self.assertNotIn("Stop", data["hooks"])
            self.assertNotIn("hooks", json.loads(settings.read_text()))
            self.assertEqual(json.loads(settings.read_text())["permissions"], {"deny": ["fixture"]})
            self.assertEqual(json.loads(run().stdout)["changed"], [])
            hooks.write_text(hooks.read_text() + "\n")
            result = run("--rollback", installed["receipt"], success=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Changed since installation", result.stderr)
            hooks.write_text(hooks.read_text().removesuffix("\n"))
            run("--rollback", installed["receipt"])
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            self.assertFalse((home / ".local/bin/jj-agent").exists())

    def test_fresh_install_creates_no_host_settings_or_hooks(self):
        with tempfile.TemporaryDirectory(prefix="jj-command-install-") as temp:
            home = Path(temp)
            result = subprocess.run([sys.executable, str(INSTALL), "--target-home", str(home)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".local/bin/jj-agent").is_file())
            self.assertFalse((home / ".codex").exists())
            self.assertFalse((home / ".claude").exists())
            release = Path(json.loads(result.stdout)["runtime"])
            self.assertFalse((release / "hooks").exists())

    def test_explicit_observation_profile_has_no_stop_and_preserves_switch(self):
        with tempfile.TemporaryDirectory(prefix="jj-selected-install-") as temp:
            home = Path(temp)
            (home / ".codex").mkdir()
            config = home / ".codex/config.toml"
            config.write_text('[features]\nhooks = false\n')
            result = subprocess.run([sys.executable, str(INSTALL), "--target-home", str(home),
                                     "--observational-hooks"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(tomllib.loads(config.read_text())["features"]["hooks"])
            codex = json.loads((home / ".codex/hooks.json").read_text())["hooks"]
            claude = json.loads((home / ".claude/settings.json").read_text())["hooks"]
            self.assertEqual(set(codex), {"SessionStart", "PostCompact", "PreToolUse"})
            self.assertEqual(set(claude), {"SessionStart", "PostCompact", "PostToolUse", "PreToolUse"})
            for hooks in (codex, claude):
                handler = hooks["PreToolUse"][0]
                self.assertEqual(handler["matcher"], "^Bash$")
                self.assertIn("jj-rm-workspace.py", handler["hooks"][0]["command"])
            runtime = Path(json.loads(result.stdout)["runtime"])
            self.assertFalse((runtime / "hooks/jj-session.py").exists())
            second = subprocess.run([sys.executable, str(INSTALL), "--target-home", str(home),
                                     "--observational-hooks"], capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["changed"], [])

    def test_codex_push_profile_requires_an_explicit_project(self):
        with tempfile.TemporaryDirectory(prefix="jj-project-hook-install-") as temp:
            home = Path(temp) / "home"
            project = Path(temp) / "project"
            (project / ".jj").mkdir(parents=True)
            result = subprocess.run([sys.executable, str(INSTALL), "--target-home", str(home),
                "--observational-hooks", "--codex-push-project", str(project)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((home / ".codex/hooks.json").read_text())["hooks"]
            self.assertEqual(set(data), {"SessionStart", "PostCompact", "PreToolUse"})
            handler = data["PreToolUse"][0]["hooks"][0]
            self.assertIn("jj-push-gate.py", handler["command"])
            self.assertIn("jj-rm-workspace.py", data["PreToolUse"][1]["hooks"][0]["command"])
            self.assertIn(str(project), handler["command"])
            self.assertNotIn("$(jj root)", handler["command"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
