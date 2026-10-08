---
title: Stop Letting AI Agents Fill Your SSD With npm
published: true
description: AI coding agents love npm install. Here is how always-pnpm catches agent tool calls and rewrites them to pnpm before execution.
tags: javascript, webdev, ai, programming
cover_image: https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/assets/devto/cover.png
canonical_url: https://github.com/youxufkhan/always-pnpm
---

Last week I asked an AI agent to prototype three small web apps. It spun up three Vite projects, configured Tailwind, and ran test builds.

Thirty minutes in, my laptop showed a low disk space alert.

The agent had downloaded three separate copies of React, Vite, TypeScript, and ESLint. Each project had its own 600 MB `node_modules` directory. If you run multiple subagents or test throwaway ideas during the week, you lose dozens of gigabytes to duplicate JavaScript packages.

![always-pnpm Dev.to Banner](https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/assets/devto/cover.png)

## The default to npm

Language models learn from millions of public repositories, tutorials, and issue threads that tell people to run `npm install`. When an agent needs a library, it types `npm i`.

You can write "use pnpm" in your prompt. It works for a few messages. Then the context window rolls over, a subagent spawns without prompt history, or the model runs a one-off shell check and goes back to `npm`.

## Hard links versus duplicate folders

Standard npm isolates each project by copying every package into the local `node_modules` folder. Five projects using TypeScript put five full copies of TypeScript on disk.

pnpm writes packages once to a global store at `~/.local/share/pnpm/store`. Projects link to those files using filesystem hard links. Ten projects using the same library version share one physical copy on disk.

![Storage Architecture: npm vs always-pnpm](https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/assets/devto/comparison.png)

## Intercepting terminal commands

I built [always-pnpm](https://github.com/youxufkhan/always-pnpm) to stop fighting prompt instructions.

The tool hooks directly into the agent runtime. When Antigravity, Claude Code, OpenCode, or Codex runs a shell command starting with `npm` or `npx`, `always-pnpm` parses the string and rewrites it to `pnpm` in under three milliseconds.

![Deterministic Hook Lifecycle Flow](https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/assets/devto/workflow.png)

Agent proposal:
```bash
npm install express lodash
```

Command executed in your shell:
```bash
pnpm add express lodash
```

The model gets its packages, the project runs, and your drive stores those files once.

## Command mapping

The parser translates common flags and subcommands:

* `npm i -D <pkgs>` becomes `pnpm add -D <pkgs>`
* `npx <cmd>` becomes `pnpm dlx <cmd>`
* `npm ci` becomes `pnpm install --frozen-lockfile`
* `npm cache clean --force` becomes `pnpm store prune`
* `npm init <template>` becomes `pnpm create <template>`

Commands that only mention `npm` inside strings or arguments, like `git commit -m "fix npm bug"` or `grep -r "npm" .`, stay untouched.

## Setup

Run the installer to detect your agent runtimes and configure their native hooks:

```bash
curl -fsSL https://raw.githubusercontent.com/youxufkhan/always-pnpm/main/scripts/install.sh | bash
```

You can also target specific agents directly:

```bash
# Target Claude Code
./scripts/install.sh --claude

# Target Antigravity
./scripts/install.sh --antigravity

# Target OpenCode or Codex
./scripts/install.sh --opencode
./scripts/install.sh --codex
```

The repository and test suite are on GitHub: [github.com/youxufkhan/always-pnpm](https://github.com/youxufkhan/always-pnpm).
