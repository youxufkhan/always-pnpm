import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
import subprocess
import json


class TestHookIntegration(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "rewrite_npm.py"))

    def test_antigravity_execution(self):
        payload = {
            "conversationId": "test-conv-123",
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "npm install zustand"
                }
            }
        }
        proc = subprocess.run(
            [sys.executable, self.script_path],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "allow")
        self.assertEqual(data["overwrite"]["CommandLine"], "pnpm add zustand")
        self.assertIn("always-pnpm", data["reason"])

    def test_claude_code_block_and_instruct(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "npm install -D typescript"
            }
        }
        proc = subprocess.run(
            [sys.executable, self.script_path],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertIn("hookSpecificOutput", data)
        hook_out = data["hookSpecificOutput"]
        self.assertEqual(hook_out["hookEventName"], "PreToolUse")
        self.assertEqual(hook_out["permissionDecision"], "deny")
        self.assertIn("pnpm add -D typescript", hook_out["permissionDecisionReason"])

    def test_claude_code_passthrough(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "git status"
            }
        }
        proc = subprocess.run(
            [sys.executable, self.script_path],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        self.assertEqual(proc.stdout, "")

    def test_cli_translate_flag_changed(self):
        proc = subprocess.run(
            [sys.executable, self.script_path, "--translate", "npx prisma migrate dev"],
            text=True,
            capture_output=True
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "pnpm dlx prisma migrate dev")

    def test_cli_translate_flag_unchanged(self):
        proc = subprocess.run(
            [sys.executable, self.script_path, "--translate", "cargo build --release"],
            text=True,
            capture_output=True
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip(), "cargo build --release")

    def test_malformed_input_graceful(self):
        proc = subprocess.run(
            [sys.executable, self.script_path],
            input="not-json",
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
