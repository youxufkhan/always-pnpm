import unittest
import os
import tempfile
import json
from scripts.config_merger import merge_hook


class TestConfigMerger(unittest.TestCase):
    def test_merge_claude_empty_or_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "settings.json")
            merged = merge_hook(conf_path, "/path/to/rewrite_npm.py")
            self.assertIn("hooks", merged)
            self.assertIn("PreToolUse", merged["hooks"])
            hook_entry = merged["hooks"]["PreToolUse"][0]
            self.assertEqual(hook_entry["matcher"], "Bash")
            self.assertIn("rewrite_npm.py", hook_entry["hooks"][0]["command"])

    def test_merge_claude_preserves_existing_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "settings.json")
            with open(conf_path, "w") as f:
                json.dump({"theme": "dark", "otherSetting": True}, f)

            merged = merge_hook(conf_path, "/path/to/rewrite_npm.py")
            self.assertEqual(merged["theme"], "dark")
            self.assertTrue(merged["otherSetting"])
            self.assertIn("hooks", merged)

    def test_merge_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "hooks.json")
            merged = merge_hook(conf_path, "/path/to/rewrite_npm.py")
            self.assertEqual(merged["hooks"]["PreToolUse"][0]["matcher"], "Bash")

    def test_updates_stale_hook_without_duplicating(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "settings.json")
            user = {"type": "command", "command": "my-hook"}
            stale = {"type": "command", "command": "python3 /old/rewrite_npm.py"}
            with open(conf_path, "w") as f:
                json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [user]},
                                                    {"matcher": "Bash", "hooks": [stale]}]}}, f)
            merged = merge_hook(conf_path, "/new/rewrite_npm.py")
            pre = merged["hooks"]["PreToolUse"]
            self.assertEqual(len(pre), 2)
            self.assertEqual(pre[0]["hooks"], [user])
            self.assertEqual(pre[1]["hooks"][0]["command"], "python3 /new/rewrite_npm.py")

    def test_removes_legacy_codex_entry_and_quotes_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "hooks.json")
            with open(conf_path, "w") as f:
                json.dump({"PreToolUse": [{"matcher": "bash", "hooks": [{"command": "python3 /old/rewrite_npm.py"}]}]}, f)
            merged = merge_hook(conf_path, "/Users/Jane Doe/rewrite_npm.py")
            self.assertNotIn("PreToolUse", merged)
            self.assertEqual(merged["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
                             "python3 '/Users/Jane Doe/rewrite_npm.py'")

    def test_unreadable_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "settings.json")
            with open(conf_path, "w") as f:
                f.write('{"theme": "dark",}')
            with self.assertRaises(ValueError):
                merge_hook(conf_path, "/path/to/rewrite_npm.py")
            with open(conf_path) as f:
                self.assertEqual(f.read(), '{"theme": "dark",}')


if __name__ == "__main__":
    unittest.main()
