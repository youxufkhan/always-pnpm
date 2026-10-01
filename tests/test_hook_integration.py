import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
import subprocess
import json


class TestHookIntegration(unittest.TestCase):
    def test_stdin_stdout_execution(self):
        payload = {
            "conversationId": "test-conv-123",
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "npm install zustand"
                }
            }
        }
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "rewrite_npm.py"))
        proc = subprocess.run(
            [sys.executable, script_path],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "allow")
        self.assertEqual(data["overwrite"]["CommandLine"], "pnpm add zustand")
        self.assertIn("always-pnpm", data["reason"])

    def test_malformed_input_graceful(self):
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "rewrite_npm.py"))
        proc = subprocess.run(
            [sys.executable, script_path],
            input="not-json",
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
