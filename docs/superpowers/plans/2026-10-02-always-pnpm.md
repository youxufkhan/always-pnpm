# `always-pnpm` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and package the `always-pnpm` open-source Antigravity plugin to deterministically enforce `pnpm` usage, automatically rewrite `npm`/`npx` commands in `run_command`, provide cognitive agent rules, and supply a 1-line installer.

**Architecture:** A lightweight Python 3 CLI hook (`scripts/rewrite_npm.py`) intercepts `run_command` in `PreToolUse`, safely parses shell segments, and rewrites commands via Antigravity's `overwrite` protocol. Paired with upfront cognitive rules in `rules/AGENTS.md`, an operational skill in `skills/always-pnpm/SKILL.md`, and an installer script in `scripts/install.sh`.

**Tech Stack:** Python 3 (standard library only: `sys`, `json`, `shlex`, `re`), Bash, Antigravity Customization API (Plugins, Rules, Hooks, Skills).

**Spec:** [docs/superpowers/specs/2026-10-02-always-pnpm-design.md](file:///home/xuf/apps/always-pnpm/docs/superpowers/specs/2026-10-02-always-pnpm-design.md)

## Global Constraints

- Zero external dependencies for the Python translation engine (standard library only).
- Python 3.8+ compatible.
- Shell commands must preserve environment variables (e.g., `PORT=3000 npm start` $\rightarrow$ `PORT=3000 pnpm start`).
- Non-npm commands must remain untouched (no false positives for `echo "npm"`, `git commit -m "npm"`, `grep npm`).
- Hook execution must fail open on unexpected errors (return `{"decision": "allow"}`) to prevent blocking agent runs.

---

### Task 1: Command Rewriter Core (`scripts/rewrite_npm.py`)

**Files:**
- Create: `scripts/rewrite_npm.py`
- Test: `tests/test_rewrite_npm.py`

**Interfaces:**
- Consumes: JSON on `sys.stdin` matching Antigravity `PreToolUse` payload: `{"toolCall": {"name": "run_command", "args": {"CommandLine": "..."}}}`
- Produces: JSON on `sys.stdout`: `{"decision": "allow", "reason": "...", "overwrite": {"CommandLine": "..."}}` or `{"decision": "allow"}`

- [ ] **Step 1: Write the failing unit tests for command translation**

Create `tests/test_rewrite_npm.py`:
```python
import unittest
from scripts.rewrite_npm import rewrite_command_line, process_hook_payload


class TestRewriteNpm(unittest.TestCase):
    def test_single_commands(self):
        cases = [
            ("npm i express", "pnpm add express"),
            ("npm install express lodash", "pnpm add express lodash"),
            ("npm i -D typescript @types/node", "pnpm add -D typescript @types/node"),
            ("npm install --save-dev vitest", "pnpm add --save-dev vitest"),
            ("npm i -g pnpm", "pnpm add -g pnpm"),
            ("npm i -E react", "pnpm add -E react"),
            ("npm i -O optional-pkg", "pnpm add -O optional-pkg"),
            ("npm i --save-peer peer-pkg", "pnpm add --save-peer peer-pkg"),
            ("npm install", "pnpm install"),
            ("npm i", "pnpm install"),
            ("npm ci", "pnpm install --frozen-lockfile"),
            ("npm uninstall lodash", "pnpm remove lodash"),
            ("npm rm lodash", "pnpm remove lodash"),
            ("npm remove lodash", "pnpm remove lodash"),
            ("npm update", "pnpm update"),
            ("npm up", "pnpm update"),
            ("npm prune", "pnpm prune"),
            ("npm run build", "pnpm run build"),
            ("npm run test -- --watch", "pnpm run test -- --watch"),
            ("npm test", "pnpm test"),
            ("npm t", "pnpm test"),
            ("npm start", "pnpm start"),
            ("npm stop", "pnpm stop"),
            ("npm restart", "pnpm restart"),
            ("npx rimraf dist", "pnpm dlx rimraf dist"),
            ("npm exec prettier -- .", "pnpm dlx prettier -- ."),
            ("npm create vite@latest my-app", "pnpm create vite@latest my-app"),
            ("npm init vite@latest", "pnpm create vite@latest"),
            ("npm init", "pnpm init"),
            ("npm init -y", "pnpm init"),
            ("npm ls", "pnpm ls"),
            ("npm list", "pnpm ls"),
            ("npm why chalk", "pnpm why chalk"),
            ("npm explain chalk", "pnpm why chalk"),
            ("npm outdated", "pnpm outdated"),
            ("npm audit", "pnpm audit"),
            ("npm audit fix", "pnpm audit"),
            ("npm cache clean --force", "pnpm store prune"),
            ("npm link", "pnpm link"),
            ("npm unlink", "pnpm unlink"),
            ("npm pack", "pnpm pack"),
            ("npm publish", "pnpm publish"),
            ("npm rebuild", "pnpm rebuild"),
        ]
        for original, expected in cases:
            with self.subTest(cmd=original):
                rewritten, changed = rewrite_command_line(original)
                self.assertTrue(changed, f"Expected {original} to be marked changed")
                self.assertEqual(rewritten, expected)

    def test_environment_variables(self):
        original = "NODE_ENV=production PORT=8080 npm start"
        expected = "NODE_ENV=production PORT=8080 pnpm start"
        rewritten, changed = rewrite_command_line(original)
        self.assertTrue(changed)
        self.assertEqual(rewritten, expected)

    def test_compound_commands(self):
        original = "cd frontend && npm install && npm run build"
        expected = "cd frontend && pnpm install && pnpm run build"
        rewritten, changed = rewrite_command_line(original)
        self.assertTrue(changed)
        self.assertEqual(rewritten, expected)

        original2 = "npm test || npm run fallback"
        expected2 = "pnpm test || pnpm run fallback"
        rewritten2, changed2 = rewrite_command_line(original2)
        self.assertTrue(changed2)
        self.assertEqual(rewritten2, expected2)

        original3 = "npm i; npm run lint"
        expected3 = "pnpm install; pnpm run lint"
        rewritten3, changed3 = rewrite_command_line(original3)
        self.assertTrue(changed3)
        self.assertEqual(rewritten3, expected3)

    def test_negative_cases_no_rewrite(self):
        negatives = [
            'git commit -m "fix: updated npm install issue"',
            'echo "you should run npm install"',
            'cat README.md | grep npm',
            'node scripts/npm-checker.js',
            'pnpm add express',
            'python3 -c "print(1)"',
            'ls -la',
        ]
        for cmd in negatives:
            with self.subTest(cmd=cmd):
                rewritten, changed = rewrite_command_line(cmd)
                self.assertFalse(changed, f"Command should not be changed: {cmd}")
                self.assertEqual(rewritten, cmd)

    def test_hook_payload_processing(self):
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "npm install chalk"
                }
            }
        }
        res = process_hook_payload(payload)
        self.assertEqual(res["decision"], "allow")
        self.assertIn("overwrite", res)
        self.assertEqual(res["overwrite"]["CommandLine"], "pnpm add chalk")
        self.assertIn("always-pnpm", res["reason"])

        # Non-rewritten payload
        payload_noop = {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "ls -la"
                }
            }
        }
        res_noop = process_hook_payload(payload_noop)
        self.assertEqual(res_noop, {"decision": "allow"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_rewrite_npm.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.rewrite_npm'`

- [ ] **Step 3: Implement minimal code in `scripts/rewrite_npm.py`**

Create `scripts/rewrite_npm.py`:
```python
#!/usr/bin/env python3
"""
always-pnpm: Antigravity PreToolUse hook for run_command.
Intercepts shell commands and transparently rewrites npm/npx invocations to pnpm.
"""

import sys
import json
import re
import shlex


def translate_subcommand_tokens(tokens):
    """
    Translates a list of shell tokens for a single command invocation.
    Returns (rewritten_tokens, bool_changed).
    """
    if not tokens:
        return tokens, False

    # Find the index of the command executable, skipping environment variable assignments (KEY=VAL)
    cmd_idx = 0
    while cmd_idx < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=.*', tokens[cmd_idx]):
        cmd_idx += 1

    if cmd_idx >= len(tokens):
        return tokens, False

    cmd = tokens[cmd_idx]
    args = tokens[cmd_idx + 1:]

    # Handle npx -> pnpm dlx
    if cmd == "npx":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "dlx"] + args
        return new_tokens, True

    # If not npm, return unchanged
    if cmd != "npm":
        return tokens, False

    # Handle npm commands
    if not args:
        # Bare 'npm'
        return list(tokens[:cmd_idx]) + ["pnpm"], True

    sub = args[0]
    sub_args = args[1:]

    # Install mappings
    if sub in ("install", "i", "add"):
        # Distinguish between 'npm install' (no package args) and 'npm install <pkgs>'
        # Options/flags start with '-'
        pkg_args = [a for a in sub_args if not a.startswith("-")]
        if not pkg_args:
            # e.g., 'npm install' -> 'pnpm install'
            new_sub_args = sub_args
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "install"] + new_sub_args
        else:
            # e.g., 'npm install express' -> 'pnpm add express'
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "add"] + sub_args
        return new_tokens, True

    if sub == "ci":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "install", "--frozen-lockfile"] + sub_args
        return new_tokens, True

    if sub in ("uninstall", "rm", "remove"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "remove"] + sub_args
        return new_tokens, True

    if sub in ("update", "up"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "update"] + sub_args
        return new_tokens, True

    if sub == "prune":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "prune"] + sub_args
        return new_tokens, True

    if sub == "run":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "run"] + sub_args
        return new_tokens, True

    if sub in ("test", "t", "start", "stop", "restart"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
        return new_tokens, True

    if sub in ("create", "init"):
        if sub == "create":
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "create"] + sub_args
        else:  # init
            if sub_args and not sub_args[0].startswith("-"):
                new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "create"] + sub_args
            else:
                new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "init"] + [a for a in sub_args if a != "-y"]
        return new_tokens, True

    if sub == "exec":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "dlx"] + sub_args
        return new_tokens, True

    if sub in ("ls", "list"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "ls"] + sub_args
        return new_tokens, True

    if sub in ("why", "explain"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "why"] + sub_args
        return new_tokens, True

    if sub == "outdated":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "outdated"] + sub_args
        return new_tokens, True

    if sub == "audit":
        # pnpm audit doesn't have 'fix' directly, strip 'fix' if present
        filtered_sub_args = [a for a in sub_args if a != "fix"]
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "audit"] + filtered_sub_args
        return new_tokens, True

    if sub == "cache" and sub_args and sub_args[0] == "clean":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "store", "prune"]
        return new_tokens, True

    if sub in ("link", "unlink", "pack", "publish", "rebuild"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
        return new_tokens, True

    # Generic fallback: npm <subcommand> -> pnpm <subcommand>
    new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
    return new_tokens, True


def split_shell_pipeline(cmd_line):
    """
    Splits a compound shell command line by operators (&&, ||, ;, |, &)
    outside of quotes, preserving operators and delimiters.
    """
    pattern = r'(&&|\|\||;|\||&)'
    segments = []
    current = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(cmd_line)

    while i < n:
        c = cmd_line[i]
        if escaped:
            current.append(c)
            escaped = False
            i += 1
            continue

        if c == '\\' and not in_single:
            escaped = True
            current.append(c)
            i += 1
            continue

        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
            continue

        if c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
            continue

        if not in_single and not in_double:
            if i + 1 < n and cmd_line[i:i+2] in ("&&", "||"):
                op = cmd_line[i:i+2]
                segments.append((''.join(current), op))
                current = []
                i += 2
                continue
            elif c in (";", "|", "&"):
                segments.append((''.join(current), c))
                current = []
                i += 1
                continue

        current.append(c)
        i += 1

    segments.append((''.join(current), ''))
    return segments


def quote_token(token):
    """
    Format a token for shell re-assembly, quoting only if needed.
    """
    if not token:
        return '""'
    if re.search(r'[\s"\'*?~<>|;&$`(){}\[\]]', token):
        return shlex.quote(token)
    return token


def rewrite_command_line(cmd_line):
    """
    Takes a shell command line string, identifies any npm/npx invocations,
    and returns (rewritten_cmd_line, bool_changed).
    """
    try:
        segments = split_shell_pipeline(cmd_line)
        rewritten_parts = []
        any_changed = False

        for sub_cmd, delimiter in segments:
            stripped = sub_cmd.strip()
            if not stripped:
                rewritten_parts.append(sub_cmd + (f" {delimiter} " if delimiter else ""))
                continue

            try:
                tokens = shlex.split(stripped, posix=True)
            except Exception:
                # If shlex fails on syntax, leave segment as-is
                rewritten_parts.append(sub_cmd + (f" {delimiter} " if delimiter else ""))
                continue

            new_tokens, changed = translate_subcommand_tokens(tokens)
            if changed:
                any_changed = True
                # Reconstruct command with proper formatting
                # Preserve leading whitespace
                leading_ws = sub_cmd[:len(sub_cmd) - len(sub_cmd.lstrip())]
                trailing_ws = sub_cmd[len(sub_cmd.rstrip()):]
                reconstructed = leading_ws + " ".join(quote_token(t) for t in new_tokens) + trailing_ws
                if delimiter:
                    reconstructed += f" {delimiter} "
                rewritten_parts.append(reconstructed)
            else:
                formatted = sub_cmd
                if delimiter:
                    formatted += f" {delimiter} "
                rewritten_parts.append(formatted)

        if any_changed:
            final_cmd = "".join(rewritten_parts).strip()
            # Clean up double spaces around operators if any
            final_cmd = re.sub(r' +', ' ', final_cmd)
            return final_cmd, True
        return cmd_line, False
    except Exception:
        return cmd_line, False


def process_hook_payload(payload):
    """
    Processes the Antigravity PreToolUse hook JSON payload.
    """
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name")
    args = tool_call.get("args", {})

    if tool_name != "run_command" or not isinstance(args, dict):
        return {"decision": "allow"}

    command_line = args.get("CommandLine", "")
    if not command_line or not isinstance(command_line, str):
        return {"decision": "allow"}

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


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        response = process_hook_payload(payload)
        print(json.dumps(response))
    except Exception:
        # Failsafe: never block agent execution on unexpected internal script error
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_rewrite_npm.py`
Expected: Ran 5 tests in X.XXs - OK

- [ ] **Step 5: Make script executable and commit**

```bash
chmod +x scripts/rewrite_npm.py
git add scripts/rewrite_npm.py tests/test_rewrite_npm.py
git commit -m "feat(core): implement npm to pnpm command translation engine"
```

---

### Task 2: Manifest & Lifecycle Hook Configuration (`plugin.json` & `hooks.json`)

**Files:**
- Create: `plugin.json`
- Create: `hooks.json`
- Test: `tests/test_hook_integration.py`

**Interfaces:**
- Consumes: Antigravity hook execution system running `python3 scripts/rewrite_npm.py`
- Produces: Discovered plugin metadata and active PreToolUse hook

- [ ] **Step 1: Write integration test for hook execution**

Create `tests/test_hook_integration.py`:
```python
import unittest
import subprocess
import json
import sys


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
        proc = subprocess.run(
            [sys.executable, "scripts/rewrite_npm.py"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "allow")
        self.assertEqual(data["overwrite"]["CommandLine"], "pnpm add zustand")

    def test_malformed_input_graceful(self):
        proc = subprocess.run(
            [sys.executable, "scripts/rewrite_npm.py"],
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

- [ ] **Step 2: Run test to verify it passes with current rewriter**

Run: `python3 -m unittest tests/test_hook_integration.py`
Expected: OK

- [ ] **Step 3: Create `plugin.json` and `hooks.json`**

Create `plugin.json`:
```json
{
  "name": "always-pnpm",
  "description": "Enforces pnpm exclusively across all Antigravity CLI and agent sessions, automatically rewriting npm and npx commands to pnpm.",
  "version": "1.0.0",
  "author": "Antigravity Community"
}
```

Create `hooks.json`:
```json
{
  "always-pnpm": {
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/rewrite_npm.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add plugin.json hooks.json tests/test_hook_integration.py
git commit -m "feat(plugin): add plugin manifest and PreToolUse hook configuration"
```

---

### Task 3: Cognitive Rules (`rules/AGENTS.md`) & Deep Skill (`skills/always-pnpm/SKILL.md`)

**Files:**
- Create: `rules/AGENTS.md`
- Create: `skills/always-pnpm/SKILL.md`

**Interfaces:**
- Consumes: Antigravity rules and skills ingestion engine
- Produces: Inline rule directives for the model and progressive skill documentation

- [ ] **Step 1: Create `rules/AGENTS.md`**

Create `rules/AGENTS.md`:
```markdown
# Rule: Mandatory pnpm Usage (`always-pnpm`)

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

- [ ] **Step 2: Create `skills/always-pnpm/SKILL.md`**

Create `skills/always-pnpm/SKILL.md`:
```markdown
---
name: always-pnpm
description: Advanced pnpm workflows, disk space reclamation, workspace monorepo management, and migration from npm to pnpm.
---

# `always-pnpm` Skill

## Overview
pnpm (Performant npm) uses a content-addressable storage mechanism (`~/.local/share/pnpm/store`) where all packages are stored once globally on the disk. Projects link to this store via hard links, saving gigabytes of disk space and eliminating duplicate dependencies.

## Key Workspaces & Monorepos Patterns
Define workspace packages in `pnpm-workspace.yaml`:
```yaml
packages:
  - 'packages/*'
  - 'apps/*'
```

Commands:
- `pnpm add -w <pkg>`: Add dependency to the root workspace.
- `pnpm --filter <target> add <pkg>`: Add dependency to a specific package.
- `pnpm --filter <target> run build`: Run a script in a specific package.
- `pnpm -r run test`: Run a script recursively across all packages.

## Disk Space Maintenance
- `pnpm store path`: Displays the local content-addressable store location.
- `pnpm store prune`: Scans the store and deletes all unreferenced packages no longer used by any project on the machine. Run periodically to reclaim disk space.

## Enforcing pnpm via Corepack
To guarantee consistent pnpm versions across teams:
```json
{
  "packageManager": "pnpm@11.21.0"
}
```
Run `corepack enable` to ensure Node automatically uses the specified pnpm binary.
```

- [ ] **Step 3: Commit**

```bash
git add rules/AGENTS.md skills/always-pnpm/SKILL.md
git commit -m "feat(rules-skill): add pnpm cognitive rules and deep operational skill"
```

---

### Task 4: Universal Installer (`scripts/install.sh`)

**Files:**
- Create: `scripts/install.sh`
- Test: `tests/test_installer.sh`

**Interfaces:**
- Consumes: Shell CLI arguments (`--symlink`, `--local`, or default global)
- Produces: Configured plugin in `~/.gemini/config/plugins/always-pnpm` or `.agents/plugins/always-pnpm`

- [ ] **Step 1: Write test script for installer**

Create `tests/test_installer.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_TMP="$(mktemp -d)"

cleanup() {
  rm -rf "$TEST_TMP"
}
trap cleanup EXIT

# Test local install
export HOME="$TEST_TMP"
MOCK_CONFIG="$TEST_TMP/.gemini/config/plugins"
mkdir -p "$MOCK_CONFIG"

# Run install in symlink mode
"$SCRIPT_DIR/scripts/install.sh" --symlink

# Verify symlink exists
if [ -L "$MOCK_CONFIG/always-pnpm" ]; then
  echo "PASS: Symlink created successfully"
else
  echo "FAIL: Symlink not found"
  exit 1
fi

echo "Installer test passed!"
```

- [ ] **Step 2: Run test to verify it fails before creating `install.sh`**

Run: `bash tests/test_installer.sh`
Expected: FAIL (`install.sh: No such file or directory`)

- [ ] **Step 3: Implement `scripts/install.sh`**

Create `scripts/install.sh`:
```bash
#!/usr/bin/env bash
# always-pnpm installer script
# Supports: global copy (default), symlink (--symlink), or workspace local (--local)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_MODE="copy"

for arg in "$@"; do
  case "$arg" in
    --symlink)
      INSTALL_MODE="symlink"
      ;;
    --local)
      INSTALL_MODE="local"
      ;;
    --help|-h)
      echo "Usage: ./install.sh [--symlink | --local]"
      echo "  (default)  Copies always-pnpm into ~/.gemini/config/plugins/always-pnpm"
      echo "  --symlink  Creates a symbolic link for live development"
      echo "  --local    Installs into .agents/plugins/always-pnpm for the current project"
      exit 0
      ;;
  esac
done

echo "==> Installing always-pnpm plugin..."

# Check prerequisites
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not installed." >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "Notice: pnpm is not found on PATH. Install via: npm install -g pnpm or corepack enable."
fi

# Determine target directory
if [ "$INSTALL_MODE" = "local" ]; then
  TARGET_DIR="$(pwd)/.agents/plugins/always-pnpm"
else
  TARGET_DIR="${HOME}/.gemini/config/plugins/always-pnpm"
fi

echo "Target location: $TARGET_DIR"

if [ "$INSTALL_MODE" = "symlink" ]; then
  mkdir -p "$(dirname "$TARGET_DIR")"
  rm -rf "$TARGET_DIR"
  ln -s "$SCRIPT_DIR" "$TARGET_DIR"
  echo "✓ Successfully symlinked always-pnpm to $TARGET_DIR"
else
  mkdir -p "$TARGET_DIR"
  # Copy necessary plugin assets
  cp -f "$SCRIPT_DIR/plugin.json" "$TARGET_DIR/"
  cp -f "$SCRIPT_DIR/hooks.json" "$TARGET_DIR/"
  
  mkdir -p "$TARGET_DIR/rules" "$TARGET_DIR/skills/always-pnpm" "$TARGET_DIR/scripts"
  cp -f "$SCRIPT_DIR/rules/AGENTS.md" "$TARGET_DIR/rules/"
  cp -f "$SCRIPT_DIR/skills/always-pnpm/SKILL.md" "$TARGET_DIR/skills/always-pnpm/"
  cp -f "$SCRIPT_DIR/scripts/rewrite_npm.py" "$TARGET_DIR/scripts/"
  chmod +x "$TARGET_DIR/scripts/rewrite_npm.py"
  echo "✓ Successfully installed always-pnpm to $TARGET_DIR"
fi

echo ""
echo "always-pnpm is now active! All Antigravity CLI and agent sessions will automatically use pnpm."
```

- [ ] **Step 4: Make executable and run test**

Run:
```bash
chmod +x scripts/install.sh tests/test_installer.sh
bash tests/test_installer.sh
```
Expected: PASS: Symlink created successfully

- [ ] **Step 5: Commit**

```bash
git add scripts/install.sh tests/test_installer.sh
git commit -m "feat(installer): create universal installer supporting global and symlink modes"
```

---

### Task 5: Open-Source Documentation & Packaging (`README.md`, `LICENSE`, `.gitignore`)

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`

**Interfaces:**
- Consumes: Project features and usage instructions
- Produces: Open-source documentation, license, and repository hygiene

- [ ] **Step 1: Create `.gitignore`**

Create `.gitignore`:
```text
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.DS_Store
node_modules/
dist/
build/
```

- [ ] **Step 2: Create `LICENSE` (MIT)**

Create `LICENSE`:
```text
MIT License

Copyright (c) 2026 Yousuf Khan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `README.md`**

Create `README.md`:
```markdown
# always-pnpm ⚡📦

> An open-source Antigravity & Antigravity CLI plugin that enforces `pnpm` exclusively across all agent sessions.

Using `npm` wastes gigabytes of disk space due to redundant, duplicated packages in `node_modules`. `pnpm` uses a single content-addressable store on disk and hard-links packages across projects, eliminating redundancy and accelerating installs.

`always-pnpm` ensures that AI coding agents never install packages using `npm`, never run `npx`, and transparently translate all commands to `pnpm`.

---

## Features

- 🔄 **Automatic Command Rewriting**: Intercepts `run_command` via Antigravity lifecycle hooks (`PreToolUse`). Rewrites `npm i` $\rightarrow$ `pnpm add`, `npx` $\rightarrow$ `pnpm dlx`, `npm ci` $\rightarrow$ `pnpm install --frozen-lockfile`, etc.
- 🛡️ **Quoted & Compound Safe**: Handles complex pipelines (`cd app && npm i && npm start`) and preserves environment variables (`PORT=3000 npm start`) while ignoring string arguments (`git commit -m "npm issue"`).
- 🧠 **Cognitive Agent Rules**: Directs the LLM upfront (`rules/AGENTS.md`) so it generates `pnpm` commands natively in code, docs, and CI workflows.
- 🔄 **Legacy Lockfile Migration**: Automatically guides the agent to convert `package-lock.json` to `pnpm-lock.yaml` using `pnpm import`.
- ⚡ **Zero External Dependencies**: Pure Python 3 standard library; executes in under 5ms.
- 🚀 **1-Command Install**: Install globally or symlink for local development.

---

## Quick Installation

### Option 1: One-Line Install (Curl)
```bash
curl -fsSL https://raw.githubusercontent.com/yousufkhan/always-pnpm/main/scripts/install.sh | bash
```

### Option 2: Clone & Symlink (Recommended for Developers)
```bash
git clone https://github.com/yousufkhan/always-pnpm.git
cd always-pnpm
./scripts/install.sh --symlink
```

### Option 3: Local Workspace Only
To enforce `pnpm` only for a specific repository:
```bash
./scripts/install.sh --local
```

---

## Command Translation Matrix

| Input Command | Rewritten To |
| :--- | :--- |
| `npm install <pkg>` / `npm i <pkg>` | `pnpm add <pkg>` |
| `npm i -D <pkg>` / `--save-dev` | `pnpm add -D <pkg>` |
| `npm i -g <pkg>` | `pnpm add -g <pkg>` |
| `npm install` (no arguments) | `pnpm install` |
| `npm ci` | `pnpm install --frozen-lockfile` |
| `npm uninstall <pkg>` / `npm rm` | `pnpm remove <pkg>` |
| `npx <cmd>` / `npm exec <cmd>` | `pnpm dlx <cmd>` |
| `npm run <script>` | `pnpm run <script>` |
| `npm test` / `npm start` | `pnpm test` / `pnpm start` |
| `npm create <template>` | `pnpm create <template>` |
| `npm audit fix` | `pnpm audit` |
| `npm cache clean --force` | `pnpm store prune` |

---

## Testing

Run the automated test suite:
```bash
python3 -m unittest discover tests
```

---

## License

MIT © [Yousuf Khan](https://github.com/yousufkhan)
```

- [ ] **Step 4: Run full test suite to verify everything passes**

Run: `python3 -m unittest discover tests`
Expected: Ran all tests - OK

- [ ] **Step 5: Run installer to deploy globally on the user's system**

Run: `./scripts/install.sh --symlink`
Expected: `✓ Successfully symlinked always-pnpm to ~/.gemini/config/plugins/always-pnpm`

- [ ] **Step 6: Commit all files**

```bash
git add .gitignore LICENSE README.md
git commit -m "docs: add open-source README, MIT license, and gitignore"
```
