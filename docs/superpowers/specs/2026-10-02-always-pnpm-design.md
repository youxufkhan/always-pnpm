# Design Spec: `always-pnpm` Antigravity Plugin

## 1. Overview and Problem Statement

In JavaScript and TypeScript development, using standard `npm` leads to massive disk space consumption and redundant package installations across projects due to nested or duplicated `node_modules`. `pnpm` solves this problem by using a content-addressable store and hard links, saving gigabytes of storage and speeding up installations.

However, AI coding assistants (such as Antigravity and Antigravity CLI) frequently default to executing `npm install`, `npx`, or `npm run` commands based on generic model training or boilerplate prompts.

`always-pnpm` is an open-source Antigravity plugin that enforces the exclusive use of `pnpm` across all Antigravity and Antigravity CLI sessions. It combines:
1. **Upfront Cognitive Rules (`rules/AGENTS.md`)**: Prompts the LLM to choose `pnpm` natively, avoid `npm`/`npx`, migrate legacy `package-lock.json` files, and use proper workspace flags.
2. **Deterministic Lifecycle Hook (`hooks.json` + `scripts/rewrite_npm.py`)**: Intercepts `run_command` in `PreToolUse`. Automatically and transparently rewrites `npm` and `npx` commands to their exact `pnpm` equivalents using Antigravity's `overwrite` contract.
3. **Deep Operational Skill (`skills/always-pnpm/SKILL.md`)**: Educates the agent on workspace management, store pruning (`pnpm store prune`), and performance tuning.
4. **Community Distribution Suite**: One-line installer, developer symlink workflow, automated unit test suite, and open-source documentation.

---

## 2. Repository Layout

```text
always-pnpm/
├── plugin.json                 # Antigravity plugin manifest
├── hooks.json                  # Lifecycle hook registration (PreToolUse)
├── rules/
│   └── AGENTS.md               # Upfront cognitive rules & migration guidance
├── skills/
│   └── always-pnpm/
│       └── SKILL.md            # Deep pnpm workflow & store guide
├── scripts/
│   ├── rewrite_npm.py          # Fast, zero-dependency translation engine
│   └── install.sh              # 1-command installer (global, symlink, local)
├── tests/
│   └── test_rewrite_npm.py     # Comprehensive test suite
├── README.md                   # Open-source documentation and quickstart
├── LICENSE                     # MIT License
└── .gitignore
```

---

## 3. Component Architecture & Data Flow

### 3.1 Hook Execution Lifecycle

```
Agent issues run_command (e.g. "npm install lodash")
                       │
                       ▼
         Antigravity PreToolUse Event
                       │
                       ▼
       scripts/rewrite_npm.py (via stdin)
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
Command has npm/npx?       No npm/npx command?
         │                           │
         │                           ▼
         │                 Allow unchanged:
         │                 {"decision": "allow"}
         ▼
  Parse command tokens,
  preserve quoted strings,
  translate to pnpm
         │
         ▼
  Emit rewrite payload:
  {
    "decision": "allow",
    "reason": "always-pnpm: rewritten '...' -> '...'",
    "overwrite": { "CommandLine": "pnpm add lodash" }
  }
         │
         ▼
Antigravity updates CommandLine & executes pnpm
         │
         ▼
Agent receives command output + rewrite notice
```

---

## 4. Detailed Component Specifications

### 4.1 Manifest (`plugin.json`)
Declares the plugin metadata:
```json
{
  "name": "always-pnpm",
  "description": "Enforces pnpm exclusively across all Antigravity CLI and agent sessions, automatically rewriting npm and npx commands to pnpm.",
  "version": "1.0.0",
  "author": "Antigravity Community"
}
```

### 4.2 Lifecycle Hook (`hooks.json`)
Registers `PreToolUse` on `run_command`:
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

### 4.3 Translation Engine (`scripts/rewrite_npm.py`)

#### Shell Segmentation & Safety Guardrails
* **Compound Pipeline Parsing**: Splits command lines by shell separators (`&&`, `||`, `;`, `|`, `&`, `\n`) while respecting single quotes, double quotes, and subshell parentheses.
* **Environment Variable Preservation**: Detects and preserves leading environment variables (e.g. `NODE_ENV=production PORT=3000 npm start` $\rightarrow$ `NODE_ENV=production PORT=3000 pnpm start`).
* **Quoted Content Immunity**: Protects commands where `npm` appears only as an argument or in string literals (e.g. `git commit -m "fix npm issue"`, `grep -r "npm" .`, `echo "npm install"`).
* **Fault Tolerance**: If any parsing exception occurs, it safely outputs `{"decision": "allow"}` to avoid disrupting the agent loop.

#### Translation Matrix

| Input Pattern | Rewritten Output | Description |
| :--- | :--- | :--- |
| `npm i <pkgs>` / `npm install <pkgs>` | `pnpm add <pkgs>` | Package installation |
| `npm i -D <pkgs>` / `--save-dev` | `pnpm add -D <pkgs>` | Dev dependency |
| `npm i -E <pkgs>` / `--save-exact` | `pnpm add -E <pkgs>` | Exact version |
| `npm i -O <pkgs>` / `--save-optional` | `pnpm add -O <pkgs>` | Optional dependency |
| `npm i --save-peer <pkgs>` | `pnpm add --save-peer <pkgs>` | Peer dependency |
| `npm i -g <pkgs>` / `--global` | `pnpm add -g <pkgs>` | Global package install |
| `npm i` / `npm install` (no args) | `pnpm install` | Install from lockfile |
| `npm ci` | `pnpm install --frozen-lockfile` | CI frozen lockfile install |
| `npm update` / `npm up` | `pnpm update` | Update dependencies |
| `npm uninstall` / `npm rm` / `npm remove` | `pnpm remove` | Uninstall dependencies |
| `npm prune` | `pnpm prune` | Prune unneeded packages |
| `npx <cmd>` / `npm exec <cmd>` | `pnpm dlx <cmd>` | Execute package binary |
| `npm run <script>` | `pnpm run <script>` | Execute npm script |
| `npm test` / `npm t` | `pnpm test` | Test script shortcut |
| `npm start` | `pnpm start` | Start script shortcut |
| `npm stop` / `npm restart` | `pnpm stop` / `pnpm restart` | Lifecycle shortcuts |
| `npm init <template>` / `npm create <template>` | `pnpm create <template>` | Scaffolding |
| `npm init` / `npm init -y` | `pnpm init` | Package initialization |
| `npm ls` / `npm list` | `pnpm ls` | List installed packages |
| `npm why <pkg>` / `npm explain <pkg>` | `pnpm why <pkg>` | Dependency explanation |
| `npm outdated` | `pnpm outdated` | Check outdated packages |
| `npm audit` / `npm audit fix` | `pnpm audit` | Audit dependencies |
| `npm cache clean --force` | `pnpm store prune` | Disk reclamation |
| `npm link` / `npm unlink` | `pnpm link` / `pnpm unlink` | Symlinking |
| `npm pack` / `npm publish` | `pnpm pack` / `pnpm publish` | Packaging & publishing |
| `npm rebuild` | `pnpm rebuild` | Rebuild native modules |

---

### 4.4 Cognitive Rules (`rules/AGENTS.md`)

Instructs the agent:
1. **Tooling Standard**: Always use `pnpm` for JavaScript/TypeScript projects. Never run `npm`, `npx`, or `yarn`.
2. **Scaffolding & Scripts**: When generating project READMEs, CI scripts, or package setup commands, strictly write `pnpm` commands (`pnpm install`, `pnpm dlx`, etc.).
3. **Legacy Migration**:
   * If a project has `package-lock.json` and no `pnpm-lock.yaml`, run `pnpm import` to convert the dependency tree.
   * Remove `package-lock.json` to prevent dual lockfiles.
4. **Monorepo Conventions**:
   * Use `-w` for workspace root installs (`pnpm add -w <pkg>`).
   * Use `--filter <pkg>` to target specific packages (`pnpm --filter web build`).

---

### 4.5 Operational Skill (`skills/always-pnpm/SKILL.md`)

Provides deep domain knowledge:
* How pnpm's content-addressable store (`~/.local/share/pnpm/store`) works.
* How to configure `pnpm-workspace.yaml`.
* Cleaning unused dependencies via `pnpm store prune`.
* Enforcing package manager via `"packageManager": "pnpm@..."` in `package.json` with Node corepack.

---

### 4.6 Installer Script (`scripts/install.sh`)

Supports three installation modes:
* **Global Install (Default)**:
  `./scripts/install.sh` copies the plugin to `~/.gemini/config/plugins/always-pnpm`.
* **Symlink Mode (`--symlink`)**:
  `./scripts/install.sh --symlink` creates a symlink from the current repo to `~/.gemini/config/plugins/always-pnpm` for continuous live editing.
* **Workspace Local (`--local`)**:
  `./scripts/install.sh --local` installs into `.agents/plugins/always-pnpm` in the current project root.
* **System Checks**: Verifies that Python 3 and `pnpm` are installed on the host, warning with installation hints if either is missing.

---

## 5. Verification & Testing Strategy

### 5.1 Unit Tests (`tests/test_rewrite_npm.py`)
* Matrix of all 25+ command variations.
* Compound pipelines (`cd frontend && npm install && npm run build`).
* Non-npm commands and false positives (`git commit -m "npm"`, `echo "npm"`, `node script.js`).
* Malformed input / unclosed quotes graceful handling.

### 5.2 Antigravity Hook Contract Validation
* Test standard stdin JSON payloads and verify expected stdout structure:
  ```json
  {
    "decision": "allow",
    "reason": "always-pnpm: rewritten 'npm i express' -> 'pnpm add express'",
    "overwrite": {
      "CommandLine": "pnpm add express"
    }
  }
  ```

---

## 6. Open-Source Readiness

* **Documentation**: Clear `README.md` with problem description, visual comparisons, one-line curl install instructions, manual install instructions, and contributing guidelines.
* **License**: MIT License.
* **Git Hygiene**: Clean `.gitignore` excluding temporary Python caches, test outputs, or virtual environments.
