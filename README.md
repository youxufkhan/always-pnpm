# always-pnpm ⚡📦

> An open-source Antigravity & Antigravity CLI plugin that enforces `pnpm` exclusively across all agent sessions.

Using standard `npm` wastes gigabytes of disk space due to redundant, duplicated packages in nested `node_modules`. `pnpm` uses a single content-addressable store on disk and hard-links packages across projects, eliminating redundancy and accelerating installs.

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

| Input Command | Rewritten To | Description |
| :--- | :--- | :--- |
| `npm install <pkg>` / `npm i <pkg>` | `pnpm add <pkg>` | Install dependencies |
| `npm i -D <pkg>` / `--save-dev` | `pnpm add -D <pkg>` | Install dev dependencies |
| `npm i -g <pkg>` | `pnpm add -g <pkg>` | Install global package |
| `npm install` (no arguments) | `pnpm install` | Install from lockfile |
| `npm ci` | `pnpm install --frozen-lockfile` | Strict CI install |
| `npm uninstall <pkg>` / `npm rm` | `pnpm remove <pkg>` | Remove package |
| `npx <cmd>` / `npm exec <cmd>` | `pnpm dlx <cmd>` | Execute package binary |
| `npm run <script>` | `pnpm run <script>` | Run npm script |
| `npm test` / `npm start` | `pnpm test` / `pnpm start` | Lifecycle shortcuts |
| `npm create <template>` | `pnpm create <template>` | Scaffolding |
| `npm audit fix` | `pnpm audit` | Audit dependencies |
| `npm cache clean --force` | `pnpm store prune` | Reclaim disk space |

---

## Testing

Run the automated test suite:
```bash
python3 -m unittest discover tests
bash tests/test_installer.sh
```

---

## License

MIT © [Yousuf Khan](https://github.com/yousufkhan)
