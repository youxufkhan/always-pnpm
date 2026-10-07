# Multi-Agent Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend `always-pnpm` to natively support Claude Code, OpenCode, and Codex alongside Antigravity, using a centralized Python rewriter engine and agent-specific lifecycle hooks and plugins.

**Architecture:** A multi-protocol Python core (`scripts/rewrite_npm.py`) detects incoming payloads (Antigravity `run_command`, Claude Code `Bash`, Codex `bash`, or CLI `--translate`), executing transparent command overwriting, blocking-with-guidance, or command mutation respectively. An OpenCode plugin (`plugins/opencode/always-pnpm.js`) and universal installer (`scripts/install.sh`) with safe config merging (`scripts/config_merger.py`) configure all four environments seamlessly.

**Tech Stack:** Python 3 (standard library: `sys`, `json`, `re`, `shlex`, `argparse`, `os`), Node.js / JavaScript (OpenCode plugin), Bash (Installer), unittest.

**Spec:** [docs/superpowers/specs/2026-10-08-multi-agent-support-design.md](file:///home/xuf/apps/always-pnpm/docs/superpowers/specs/2026-10-08-multi-agent-support-design.md)

## Global Constraints

- Zero external Python dependencies (must run on vanilla Python 3.8+ using only standard library).
- Never clobber existing user configurations when updating `settings.json` or `hooks.json`.
- Failsafe guarantee: malformed JSON or unhandled tool payloads must fail open (allow) without blocking agent execution.
- Maintain full backward compatibility with existing Antigravity installations and tests.

---

### Task 1: Poly-Agent Core Rewriter (`scripts/rewrite_npm.py`) & Multi-Protocol Tests

**Files:**
- Modify: `scripts/rewrite_npm.py`
- Modify: `tests/test_hook_integration.py`

**Interfaces:**
- CLI Mode: `python3 scripts/rewrite_npm.py --translate "<command>"`: prints rewritten string to stdout. Exit `0` if changed, exit `1` if unchanged.
- Function: `process_hook_payload(payload: dict) -> dict`: handles Antigravity, Claude Code, and Codex payload structures.

- [x] **Step 1: Write failing multi-protocol tests in `tests/test_hook_integration.py`**

```python
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
        data = json.loads(proc.stdout)
        self.assertEqual(data.get("decision"), "allow")

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
```

- [x] **Step 2: Run test to verify new tests fail**

Run: `python3 -m unittest tests/test_hook_integration.py`  
Expected: FAIL on `test_claude_code_block_and_instruct` and CLI translate tests.

- [x] **Step 3: Update `scripts/rewrite_npm.py` to support CLI mode and Claude/Codex payloads**

Update `scripts/rewrite_npm.py`:
- Add CLI argument parsing for `--translate` / `-t`.
- Update `process_hook_payload(payload)` to handle Claude Code (`tool_name == "Bash"`) and Codex (`tool == "bash"` or `toolCall`).

```python
def process_hook_payload(payload):
    """
    Processes hook JSON payloads for Antigravity, Claude Code, and Codex.
    """
    # 1. Claude Code payload: {"tool_name": "Bash", "tool_input": {"command": "..."}}
    if payload.get("tool_name") == "Bash":
        tool_input = payload.get("tool_input", {})
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        if command:
            rewritten, changed = rewrite_command_line(command)
            if changed:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"always-pnpm: 'npm' is blocked. Run '{rewritten}' instead."
                    }
                }
        return {"decision": "allow"}

    # 2. Codex payload: {"tool": "bash", "command": "..."}
    if payload.get("tool") == "bash":
        command = payload.get("command", "")
        if command:
            rewritten, changed = rewrite_command_line(command)
            if changed:
                return {
                    "decision": "deny",
                    "reason": f"always-pnpm: 'npm' is blocked. Run '{rewritten}' instead."
                }
        return {"decision": "allow"}

    # 3. Antigravity payload: {"toolCall": {"name": "run_command", "args": {"CommandLine": "..."}}}
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name")
    args = tool_call.get("args", {})

    if tool_name == "run_command" and isinstance(args, dict):
        command_line = args.get("CommandLine", "")
        if command_line and isinstance(command_line, str):
            rewritten, changed = rewrite_command_line(command_line)
            if changed:
                return {
                    "decision": "allow",
                    "reason": f"always-pnpm: rewritten '{command_line}' -> '{rewritten}'",
                    "overwrite": {
                        "CommandLine": rewritten
                    }
                }

    return {"decision": "allow"}
```

In `main()`:
```python
def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--translate", "-t"):
        if len(sys.argv) > 2:
            cmd = " ".join(sys.argv[2:])
        else:
            cmd = ""
        rewritten, changed = rewrite_command_line(cmd)
        print(rewritten)
        sys.exit(0 if changed else 1)

    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        response = process_hook_payload(payload)
        print(json.dumps(response))
    except Exception:
        print(json.dumps({"decision": "allow"}))
```

- [x] **Step 4: Run tests to verify all tests pass**

Run: `python3 -m unittest discover tests`  
Expected: All 11 tests pass.

- [x] **Step 5: Commit**

```bash
git add scripts/rewrite_npm.py tests/test_hook_integration.py
git commit -m "feat: add multi-protocol payload handling and CLI translation to rewriter"
```

---

### Task 2: Configuration Merger Utility (`scripts/config_merger.py`)

**Files:**
- Create: `scripts/config_merger.py`
- Create: `tests/test_config_merger.py`

**Interfaces:**
- Produces: `merge_claude_settings(existing_path: str, script_path: str) -> dict`
- Produces: `merge_codex_hooks(existing_path: str, script_path: str) -> dict`
- CLI: `python3 scripts/config_merger.py claude <settings_json_path> <script_path>`
- CLI: `python3 scripts/config_merger.py codex <hooks_json_path> <script_path>`

- [x] **Step 1: Write test for configuration merger**

Create `tests/test_config_merger.py`:
```python
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
```

- [x] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_config_merger.py`  
Expected: ModuleNotFoundError for `scripts.config_merger`.

- [x] **Step 3: Implement `scripts/config_merger.py`**

Create `scripts/config_merger.py`:
```python
#!/usr/bin/env python3
"""
Safely merges always-pnpm hooks into existing Claude Code and Codex configurations.
"""

import os
import sys
import json


def load_json_safe(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def merge_claude_settings(settings_path, script_path):
    data = load_json_safe(settings_path)
    if "hooks" not in data or not isinstance(data["hooks"], dict):
        data["hooks"] = {}

    hooks_dict = data["hooks"]
    if "PreToolUse" not in hooks_dict or not isinstance(hooks_dict["PreToolUse"], list):
        hooks_dict["PreToolUse"] = []

    pre_hooks = hooks_dict["PreToolUse"]
    # Check if always-pnpm matcher already present
    existing = False
    for item in pre_hooks:
        if isinstance(item, dict) and item.get("matcher") == "Bash":
            for h in item.get("hooks", []):
                if "rewrite_npm.py" in h.get("command", ""):
                    h["command"] = f"python3 {script_path}"
                    existing = True
            if not existing:
                item.setdefault("hooks", []).append({
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                })
                existing = True

    if not existing:
        pre_hooks.append({
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                }
            ]
        })

    save_json(settings_path, data)
    return data


def merge_codex_hooks(hooks_path, script_path):
    data = load_json_safe(hooks_path)
    if "PreToolUse" not in data or not isinstance(data["PreToolUse"], list):
        data["PreToolUse"] = []

    pre_hooks = data["PreToolUse"]
    existing = False
    for item in pre_hooks:
        if isinstance(item, dict) and item.get("matcher") == "bash":
            for h in item.get("hooks", []):
                if "rewrite_npm.py" in h.get("command", ""):
                    h["command"] = f"python3 {script_path}"
                    existing = True
            if not existing:
                item.setdefault("hooks", []).append({
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                })
                existing = True

    if not existing:
        pre_hooks.append({
            "matcher": "bash",
            "hooks": [
                {
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                }
            ]
        })

    save_json(hooks_path, data)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: config_merger.py <claude|codex> <config_file> <script_path>")
        sys.exit(1)

    target_type = sys.argv[1].lower()
    conf_file = sys.argv[2]
    script = os.path.abspath(sys.argv[3])

    if target_type == "claude":
        merge_claude_settings(conf_file, script)
    elif target_type == "codex":
        merge_codex_hooks(conf_file, script)
    else:
        print(f"Unknown target: {target_type}")
        sys.exit(1)
```

- [x] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests/test_config_merger.py`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add scripts/config_merger.py tests/test_config_merger.py
git commit -m "feat: add safe configuration merger utility for claude and codex"
```

---

### Task 3: OpenCode Plugin & Agent Instruction Rules

**Files:**
- Create: `plugins/opencode/always-pnpm.js`
- Create: `rules/CLAUDE.md`
- Create: `tests/test_opencode_plugin.py`

**Interfaces:**
- `plugins/opencode/always-pnpm.js`: exports OpenCode plugin hooking `tool.execute.before`, mutating `output.args.command` when `npm` is detected.
- `rules/CLAUDE.md`: cognitive guidance matching `rules/AGENTS.md` for Claude Code.

- [x] **Step 1: Write integration test for OpenCode plugin behavior**

Create `tests/test_opencode_plugin.py` to test the JS plugin syntax and Node invocation:
```python
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
```

- [x] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_opencode_plugin.py`  
Expected: FAIL ("Plugin file must exist").

- [x] **Step 3: Implement `plugins/opencode/always-pnpm.js` and `rules/CLAUDE.md`**

Create `plugins/opencode/always-pnpm.js`:
```javascript
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REWRITER_PATH = process.env.ALWAYS_PNPM_SCRIPT || path.resolve(__dirname, "../../scripts/rewrite_npm.py");

export const AlwaysPnpmPlugin = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!input || !output || !output.args) return;
      if (input.tool === "bash" || input.tool === "execute") {
        const cmd = output.args.command;
        if (!cmd || typeof cmd !== "string") return;
        if (!cmd.includes("npm") && !cmd.includes("npx")) return;

        try {
          const rewritten = execFileSync(
            "python3",
            [REWRITER_PATH, "--translate", cmd],
            { encoding: "utf8", timeout: 3000 }
          ).trim();

          if (rewritten && rewritten !== cmd) {
            output.args.command = rewritten;
          }
        } catch (err) {
          // If exit code is 1 (no changes) or process error, fail open safely
        }
      }
    },
  };
};

export default AlwaysPnpmPlugin;
```

Create `rules/CLAUDE.md` (identical mandate to `rules/AGENTS.md` tailored to Claude Code):
```markdown
# Mandatory pnpm Usage (`always-pnpm`)

## 1. Core Mandate
* **NEVER** use `npm`, `npx`, or `yarn`. You must exclusively use **`pnpm`** for all JavaScript and TypeScript projects.
* Do not propose, run, or write shell commands using `npm` or `npx`.
* When writing documentation, `README.md`, setup guides, or CI/CD pipelines, always write commands using `pnpm` (e.g. `pnpm install`, `pnpm run build`, `pnpm dlx`).

## 2. Command Equivalents Quick Reference
* Installing a package: `pnpm add <pkg>` (NOT `npm i <pkg>`)
* Installing a dev dependency: `pnpm add -D <pkg>` (NOT `npm i -D <pkg>`)
* Installing from lockfile: `pnpm install`
* Running scripts: `pnpm run <script>` or `pnpm <script>`
* Running one-off executables: `pnpm dlx <tool>` (NOT `npx <tool>`)
* Scaffolding: `pnpm create <template>` (NOT `npm create` or `npm init`)
* Removing a package: `pnpm remove <pkg>` (NOT `npm rm` or `npm uninstall`)

## 3. Monorepos and Workspaces
* Root-level dependencies in a monorepo must use `-w`: `pnpm add -w -D <pkg>`.
* Targeting specific workspace packages: `pnpm --filter <pkg-name> <cmd>`.

## 4. Handling Existing Projects (Migration)
* If an existing project has `package-lock.json` or `yarn.lock` and no `pnpm-lock.yaml`:
  1. Run `pnpm import` to convert existing dependencies into `pnpm-lock.yaml`.
  2. Remove `package-lock.json` or `yarn.lock` to avoid duplicate lockfiles.
  3. Ensure `pnpm-lock.yaml` is checked into version control.
```

- [x] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests/test_opencode_plugin.py`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add plugins/opencode/always-pnpm.js rules/CLAUDE.md tests/test_opencode_plugin.py
git commit -m "feat: add opencode plugin and claude code rules file"
```

---

### Task 4: Universal Multi-Agent Installer (`scripts/install.sh`) & Installer Tests

**Files:**
- Modify: `scripts/install.sh`
- Modify: `tests/test_installer.sh`

**Interfaces:**
- Installer auto-detects installed agents if no explicit agent flag is passed.
- Flags: `--all`, `--antigravity`, `--claude`, `--opencode`, `--codex`, `--symlink`, `--local`.

- [x] **Step 1: Write test cases for multi-agent installer**

Update `tests/test_installer.sh`:
- Test auto-detection with mock home directories for Claude, OpenCode, Codex, Antigravity.
- Test `--claude` installs `CLAUDE.md` and merges `~/.claude/settings.json`.
- Test `--opencode` installs `always-pnpm.js` in `~/.config/opencode/plugins/` and `AGENTS.md`.
- Test `--codex` installs `~/.codex/hooks.json` and `AGENTS.md`.
- Test `--local` in current workspace creates local `.claude/`, `.opencode/`, `.codex/`, `.agents/`.
- Test `--all` flag.

- [x] **Step 2: Run `tests/test_installer.sh` to observe current limitations**

Run: `bash tests/test_installer.sh`

- [x] **Step 3: Update `scripts/install.sh` with poly-agent support**

Rewrite `scripts/install.sh` to:
1. Parse flags: `--all`, `--antigravity`, `--claude`, `--opencode`, `--codex`, `--symlink`, `--local`, `--help`.
2. If no target specified and not `--local`: auto-detect present agents via binary and home config directories (`~/.gemini`, `~/.claude`, `~/.config/opencode`, `~/.codex`).
3. For Antigravity: install plugin manifest, hooks.json, rules, skills, scripts.
4. For Claude Code: install `CLAUDE.md`, run `config_merger.py claude ~/.claude/settings.json <script>`.
5. For OpenCode: install `plugins/opencode/always-pnpm.js` to `~/.config/opencode/plugins/`, copy `AGENTS.md` and skills.
6. For Codex: install `AGENTS.md` to `~/.codex/`, run `config_merger.py codex ~/.codex/hooks.json <script>`.
7. Handle `--local` by creating local project configs (`.claude/`, `.opencode/`, `.codex/`, `.agents/`).

- [x] **Step 4: Run full installer tests**

Run: `bash tests/test_installer.sh`  
Expected: All installer tests pass cleanly.

- [x] **Step 5: Commit**

```bash
git add scripts/install.sh tests/test_installer.sh
git commit -m "feat: implement universal multi-agent installer with auto-detection"
```

---

### Task 5: Documentation & Visual Compatibility Matrix (`README.md`)

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update README.md with Multi-Agent Support**

Add sections for:
- Supported Agents Matrix: Antigravity, Claude Code, OpenCode, Codex.
- Multi-Agent Quickstart & One-Line Install command.
- Target-specific flags guide.
- Explanation of enforcement model for each agent:
  - Antigravity: In-flight transparent overwrite via `run_command` hook.
  - OpenCode: In-flight transparent mutate via `tool.execute.before` plugin.
  - Claude Code: Block & Instruct via `PreToolUse` on `Bash`.
  - Codex: Block & Instruct via `PreToolUse` on `bash`.
- Testing commands across all suites.

- [x] **Step 2: Run all test suites across Python and Bash**

Run:
```bash
python3 -m unittest discover tests
bash tests/test_installer.sh
```
Expected: All tests pass.

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document multi-agent support for claude code, opencode, and codex"
```

---
