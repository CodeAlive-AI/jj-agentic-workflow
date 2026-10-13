#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

INSTALL = Path(__file__).resolve().parents[1] / "bin/jj-agent-install"


class InstallTest(unittest.TestCase):
    def test_preserves_other_hooks_is_repeatable_and_rolls_back(self):
        with tempfile.TemporaryDirectory(prefix="jj-install-pilot-") as temp:
            home = Path(temp)
            (home / ".codex").mkdir()
            (home / ".claude").mkdir()
            config = home / ".codex/config.toml"
            config.write_text('# keep comment\nmodel="fixture"\n[features]\nhooks = false # existing\n')
            hooks = home / ".codex/hooks.json"
            original = {"hooks": {"PreToolUse": [{"matcher": "^Bash$", "hooks": [
                {"type": "command", "command": "unrelated-check"}]}]}}
            hooks.write_text(json.dumps(original))
            settings = home / ".claude/settings.json"
            settings.write_text('{"worktree":{"baseRef":"head"},"permissions":{"deny":["fixture"]}}')
            before = {p: p.read_bytes() for p in [config, hooks, settings]}
            def run(*args, success=True):
                result = subprocess.run([str(INSTALL), "--target-home", str(home), *args], capture_output=True, text=True)
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                return result
            installed = json.loads(run().stdout)
            self.assertTrue(tomllib.loads(config.read_text())["features"]["hooks"])
            self.assertIn("# keep comment", config.read_text())
            data = json.loads(hooks.read_text())
            self.assertEqual(data["hooks"]["PreToolUse"][0], original["hooks"]["PreToolUse"][0])
            self.assertNotIn("WorktreeCreate", json.loads(settings.read_text())["hooks"])
            self.assertEqual(json.loads(settings.read_text())["permissions"], {"deny": ["fixture"]})
            self.assertEqual(json.loads(run().stdout)["changed"], [])
            config.write_text(config.read_text() + "# concurrent edit\n")
            result = run("--rollback", installed["receipt"], success=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Changed since installation", result.stderr)
            config.write_text(config.read_text().replace("# concurrent edit\n", ""))
            run("--rollback", installed["receipt"])
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            self.assertFalse((home / ".local/bin/jj-agent").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
