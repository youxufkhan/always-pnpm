# Design Specification: Multi-Agent Support for `always-pnpm`

**Date:** 2026-10-08  
**Status:** Approved  
**Targets:** Antigravity, Claude Code, OpenCode, Codex  

---

## 1. Executive Summary

`always-pnpm` transparently enforces `pnpm` usage across AI coding sessions to eliminate duplicate `node_modules` overhead and disk bloat. Originally built as an Antigravity plugin, this design extends first-class support to **Claude Code**, **OpenCode**, and **Codex** by combining cognitive prompt alignment (`AGENTS.md`, `CLAUDE.md`) with deterministic native runtime hooks and plugins.

---

## 2. Architectural Overview

### 2.1 Single Source of Truth
All command parsing, shell tokenization, pipeline splitting (`&&`, `||`, `;`, `|`), and translation logic remain centralized in `scripts/rewrite_npm.py`. Neither agent plugins nor prompt files maintain separate regex or lookup tables.

### 2.2 System Topology

```text
                                always-pnpm
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
      Antigravity               Claude Code                OpenCode                   Codex
 (PreToolUse Hook)           (PreToolUse Hook)         (Lifecycle Plugin)       (PreToolUse Hook)
         │                           │                         │                        │
         │ stdin JSON                │ stdin JSON              │ child_process CLI      │ stdin JSON
         ▼                           ▼                         ▼                        ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                                scripts/rewrite_npm.py                                  │
  │   - CLI Mode: --translate "<cmd>"                                                     │
  │   - Payload Autodetection (Antigravity vs. Claude Code vs. Codex)                      │
  └────────────────────────────────────────────────────────────────────────────────────────┘
         │                           │                         │                        │
  Overwrite Command           Deny & Educate           In-Flight Mutate          Deny / Block
 {"decision":"allow",        {"permissionDecision":    output.args.command =     Refusal with
  "overwrite":{...}}          "deny", ...}              rewritten_cmd             pnpm solution
```

---

## 3. Component Specifications

### 3.1 Poly-Agent Engine (`scripts/rewrite_npm.py`)

#### 3.1.1 CLI Mode
- **Invocation**: `python3 scripts/rewrite_npm.py --translate "<command>"` (or `-t "<command>"`)
- **Behavior**:
  - Translates `<command>` using `rewrite_command_line()`.
  - Outputs the rewritten command string to `stdout`.
  - Exits with code `0` if the command was rewritten.
  - Exits with code `1` if the command was unchanged or untouched.

#### 3.1.2 Payload Autodetection & Handlers
When reading JSON from `stdin`:
1. **Antigravity Payload**:
   - Condition: `payload.get("toolCall", {}).get("name") == "run_command"`
   - Output:
     ```json
     {
       "decision": "allow",
       "reason": "always-pnpm: rewritten '<old>' -> '<new>'",
       "overwrite": {
         "CommandLine": "<new>"
       }
     }
     ```
   - If unchanged: `{"decision": "allow"}`
2. **Claude Code Payload**:
   - Condition: `payload.get("tool_name") == "Bash"`
   - Input structure: `{"tool_name": "Bash", "tool_input": {"command": "..."}}`
   - Output when `npm`/`npx` detected:
     ```json
     {
       "hookSpecificOutput": {
         "hookEventName": "PreToolUse",
         "permissionDecision": "deny",
         "permissionDecisionReason": "always-pnpm: 'npm' is blocked. Run '<rewritten>' instead."
       }
     }
     ```
   - Output when no changes needed: Empty `{}` or exit code `0` allowing transparent execution.
3. **Codex Payload**:
   - Condition: `payload.get("tool") == "bash"` or matching Codex PreToolUse schemas.
   - Output: Refusal block instructing the model with the exact `pnpm` command.
4. **Failsafe**:
   - If JSON is malformed or unhandled, gracefully exit 0 and output `{"decision": "allow"}` to guarantee zero disruption.

---

### 3.2 OpenCode Plugin (`plugins/opencode/always-pnpm.js`)

- **Location**: `plugins/opencode/always-pnpm.js` (installed to `~/.config/opencode/plugins/always-pnpm.js` or `.opencode/plugins/always-pnpm.js`).
- **Implementation**:
  - Hooks into `tool.execute.before`.
  - Matches `input.tool === "bash"` or `input.tool === "execute"`.
  - Checks if command contains `npm` or `npx`.
  - Executes `python3 <PATH_TO_SCRIPT>/rewrite_npm.py --translate "<cmd>"` via synchronous child process (`execFileSync`) with a 3000ms timeout.
  - If a rewritten string is returned, sets `output.args.command = rewritten`.
  - Swallows errors cleanly to fail open.

---

### 3.3 Rule & Instruction Mapping

- **Antigravity**: `rules/AGENTS.md` (read via Antigravity plugin loader).
- **Claude Code**: `rules/CLAUDE.md` (deployed to `~/.claude/CLAUDE.md` or project root `CLAUDE.md`).
- **OpenCode**: `rules/AGENTS.md` (deployed to `~/.config/opencode/AGENTS.md` or project root `AGENTS.md`).
- **Codex**: `rules/AGENTS.md` (deployed to `~/.codex/AGENTS.md` or project root `AGENTS.md`).

---

### 3.4 Safe Configuration Merging & Universal Installer (`scripts/install.sh`)

#### 3.4.1 Targets & Detection
1. **Antigravity**: Binary `antigravity` or directory `~/.gemini/`
2. **Claude Code**: Binary `claude` or directory `~/.claude/`
3. **OpenCode**: Binary `opencode` or directory `~/.config/opencode/`
4. **Codex**: Binary `codex` or directory `~/.codex/`

#### 3.4.2 CLI Flags
- `./scripts/install.sh` (default: auto-detects and installs to all detected agents)
- `./scripts/install.sh --all` (installs to all four agents regardless of presence)
- `./scripts/install.sh --antigravity`
- `./scripts/install.sh --claude`
- `./scripts/install.sh --opencode`
- `./scripts/install.sh --codex`
- `./scripts/install.sh --symlink` (symlinks repository files for development)
- `./scripts/install.sh --local` (installs into current workspace: `.claude/`, `.opencode/`, `.codex/`, `.agents/`)

#### 3.4.3 Configuration Merging Strategy
Existing configuration files (`~/.claude/settings.json`, `~/.codex/hooks.json`) are preserved. A Python-assisted helper parses existing JSON, inserts or updates the `PreToolUse` hook matcher without duplicating entries, and writes back indented JSON.

---

## 4. Verification and Testing

1. **Unit Tests (`tests/test_rewrite_npm.py`)**:
   - Ensure all translation matrix rules continue to function.
2. **Multi-Agent Protocol Tests (`tests/test_hook_integration.py`)**:
   - Test Antigravity payload (returns allow + overwrite).
   - Test Claude Code payload (returns deny + informative guidance).
   - Test Claude Code non-npm command (returns allow).
   - Test CLI `--translate` mode (exit code 0 for rewritten, 1 for unchanged).
   - Test malformed payloads (fail-safe allow).
3. **Installer Verification (`tests/test_installer.sh`)**:
   - Test clean installation for each individual agent in mocked `$HOME` environments.
   - Test multi-agent combined installation.
   - Test JSON preservation when merging into pre-existing `settings.json`.
   - Test `--symlink` and `--local` modes.

---

## 5. File Layout Changes

```text
always-pnpm/
├── plugin.json
├── hooks.json
├── rules/
│   ├── AGENTS.md
│   └── CLAUDE.md
├── skills/
│   └── always-pnpm/
│       └── SKILL.md
├── scripts/
│   ├── rewrite_npm.py
│   ├── install.sh
│   └── config_merger.py
├── plugins/
│   └── opencode/
│       └── always-pnpm.js
├── tests/
│   ├── test_rewrite_npm.py
│   ├── test_hook_integration.py
│   └── test_installer.sh
└── README.md
```
