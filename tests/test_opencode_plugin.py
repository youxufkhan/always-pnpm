import unittest
import os
import subprocess
import shutil


class TestOpenCodePlugin(unittest.TestCase):
    def test_plugin_file_exists_and_valid_syntax(self):
        plugin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins", "opencode", "always-pnpm.js"))
        self.assertTrue(os.path.exists(plugin_path), "Plugin file must exist")

        # If node is installed, verify JS syntax
        if shutil.which("node"):
            proc = subprocess.run(["node", "--check", plugin_path], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"Syntax error in plugin: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
