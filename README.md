<p align="center">
  <img src="assets/readme/hero.svg" alt="always-pnpm - Zero Package Redundancy. 100% Deterministic pnpm Enforcement for Antigravity" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/youxufkhan/always-pnpm/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT" /></a>
  <a href="https://github.com/youxufkhan/always-pnpm"><img src="https://img.shields.io/badge/Antigravity-Plugin-f97316.svg?style=flat-square" alt="Antigravity Plugin" /></a>
  <a href="https://pnpm.io"><img src="https://img.shields.io/badge/pnpm-100%25%20Enforced-orange.svg?style=flat-square" alt="pnpm Enforced" /></a>
  <img src="https://img.shields.io/badge/Python-3.8+-38bdf8.svg?style=flat-square" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/Tests-7%20Passing-10b981.svg?style=flat-square" alt="Tests 7 Passing" />
</p>

<p align="center">
  <img src="assets/readme/section-why.svg" alt="Why always-pnpm?" width="100%" />
</p>

In modern web development, running `npm install` across multiple projects duplicates hundreds of megabytes of identical dependencies in local `node_modules` folders, rapidly consuming tens of gigabytes of disk space.

`pnpm` solves this fundamentally by storing packages **once** in a global content-addressable store (`~/.local/share/pnpm/store`) and linking them into projects via filesystem hard links.

However, AI coding agents (such as Antigravity and Antigravity CLI) frequently default to `npm` or `npx` commands. **`always-pnpm`** intercepts commands at the tool lifecycle level, automatically rewriting `npm` and `npx` invocations to `pnpm` in under 3ms with zero agent friction.

<p align="center">
  <img src="assets/readme/comparison.svg" alt="Storage Architecture Comparison: npm vs always-pnpm" width="100%" />
</p>

---

<p align="center">
  <img src="assets/readme/section-how.svg" alt="How It Works" width="100%" />
</p>

<p align="center">
  <img src="assets/readme/workflow.svg" alt="always-pnpm Hook Execution Lifecycle" width="100%" />
</p>

1. **Cognitive Alignment (`rules/AGENTS.md`)**: Directs the LLM upfront across all sessions to choose `pnpm`, write `pnpm` documentation, and convert legacy `package-lock.json` files via `pnpm import`.
2. **Runtime Interception (`hooks.json`)**: Attaches to Antigravity's `PreToolUse` event for `run_command`.
3. **Smart Shell Tokenization (`scripts/rewrite_npm.py`)**: Uses Python's standard library to parse command tokens and pipeline operators (`&&`, `||`, `;`, `|`), preserving environment variables and ignoring strings in quotes.
4. **Transparent Overwrite**: Returns an updated `CommandLine` payload executed directly by Antigravity with a notice in the agent feed.

---

<p align="center">
  <img src="assets/readme/section-install.svg" alt="Quick Installation" width="100%" />
</p>

### Option 1: One-Line Install (Recommended)
Installs `always-pnpm` globally into `~/.gemini/config/plugins/always-pnpm`:
```bash
curl -fsSL https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/scripts/install.sh | bash
```

### Option 2: Clone & Symlink (For Developers / Live Updates)
Symlinks the repository to your global Antigravity plugins directory so code changes apply immediately:
```bash
git clone https://github.com/youxufkhan/always-pnpm.git
cd always-pnpm
./scripts/install.sh --symlink
```

### Option 3: Repository-Specific Only
Enforces `always-pnpm` strictly inside the current workspace (`.agents/plugins/always-pnpm`):
```bash
./scripts/install.sh --local
```

---

<p align="center">
  <img src="assets/readme/section-matrix.svg" alt="Command Translation Matrix" width="100%" />
</p>

The zero-dependency Python engine translates all common `npm` and `npx` commands and flags:

| Input Command Pattern | Rewritten Output | Description |
| :--- | :--- | :--- |
| `npm install <pkgs>` / `npm i <pkgs>` | `pnpm add <pkgs>` | Add dependency |
| `npm i -D <pkgs>` / `--save-dev` | `pnpm add -D <pkgs>` | Add dev dependency |
| `npm i -E <pkgs>` / `--save-exact` | `pnpm add -E <pkgs>` | Add exact version |
| `npm i -O <pkgs>` / `--save-optional` | `pnpm add -O <pkgs>` | Add optional dependency |
| `npm i --save-peer <pkgs>` | `pnpm add --save-peer <pkgs>` | Add peer dependency |
| `npm i -g <pkgs>` / `--global` | `pnpm add -g <pkgs>` | Global package install |
| `npm install` / `npm i` (no args) | `pnpm install` | Install from lockfile |
| `npm ci` | `pnpm install --frozen-lockfile` | CI frozen lockfile install |
| `npm update` / `npm up` | `pnpm update` | Update dependencies |
| `npm uninstall <pkgs>` / `npm rm` | `pnpm remove <pkgs>` | Remove dependency |
| `npx <cmd>` / `npm exec <cmd>` | `pnpm dlx <cmd>` | Execute package binary |
| `npm run <script>` | `pnpm run <script>` | Execute npm script |
| `npm test` / `npm t` | `pnpm test` | Test script shortcut |
| `npm start` / `npm stop` | `pnpm start` / `pnpm stop` | Lifecycle shortcuts |
| `npm create <template>` | `pnpm create <template>` | Scaffolding |
| `npm init <template>` | `pnpm create <template>` | Initializer mapping |
| `npm init` / `npm init -y` | `pnpm init` | Package initialization |
| `npm ls` / `npm list` | `pnpm ls` | List installed packages |
| `npm why <pkg>` / `npm explain` | `pnpm why <pkg>` | Inspect dependency path |
| `npm outdated` | `pnpm outdated` | Check outdated packages |
| `npm audit` / `npm audit fix` | `pnpm audit` | Security audit |
| `npm cache clean --force` | `pnpm store prune` | Reclaim global disk space |
| `npm link` / `npm unlink` | `pnpm link` / `pnpm unlink` | Link local packages |
| `npm pack` / `npm publish` | `pnpm pack` / `pnpm publish` | Packaging & publishing |
| `npm rebuild` | `pnpm rebuild` | Rebuild native modules |

#### False-Positive Protection
Commands where `npm` appears only as an argument or in string literals remain untouched:
- `git commit -m "fix: npm build error"` $\rightarrow$ *unchanged*
- `echo "install with npm"` $\rightarrow$ *unchanged*
- `grep -r "npm" ./docs` $\rightarrow$ *unchanged*

---

## Testing & Verification

Run the comprehensive unit test suite and installer verification:

```bash
# Run unit & integration tests
python3 -m unittest discover tests

# Run installer test suite
bash tests/test_installer.sh
```

---

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme">
    <img src="assets/readme/footer-badge.svg" alt="README crafted with beautify-github-readme" />
  </a>
</p>

## License

MIT © [Yousuf Khan](https://github.com/youxufkhan)
