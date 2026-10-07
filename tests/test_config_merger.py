import unittest
import os
import tempfile
import json
from scripts.config_merger import merge_claude_settings, merge_codex_hooks


class TestConfigMerger(unittest.TestCase):
    def test_merge_claude_empty_or_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "settings.json")
            merged = merge_claude_settings(conf_path, "/path/to/rewrite_npm.py")
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

            merged = merge_claude_settings(conf_path, "/path/to/rewrite_npm.py")
            self.assertEqual(merged["theme"], "dark")
            self.assertTrue(merged["otherSetting"])
            self.assertIn("hooks", merged)

    def test_merge_codex_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conf_path = os.path.join(tmpdir, "hooks.json")
            merged = merge_codex_hooks(conf_path, "/path/to/rewrite_npm.py")
            self.assertIn("PreToolUse", merged)
            self.assertEqual(merged["PreToolUse"][0]["matcher"], "bash")


if __name__ == "__main__":
    unittest.main()
