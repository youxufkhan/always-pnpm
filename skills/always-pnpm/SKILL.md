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

## Multi-Agent Lifecycle Enforcement
`always-pnpm` actively guards against accidental `npm` usage across multiple AI coding agents:
- **Antigravity**: Intercepts `run_command` in `hooks.json` to transparently rewrite `npm` to `pnpm` in-flight.
- **Claude Code**: Intercepts `Bash` via `PreToolUse` in `.claude/settings.json`, blocking `npm` and instructing the agent with the exact `pnpm` command.
- **OpenCode**: Modifies commands via the `tool.execute.before` plugin (`always-pnpm.js`).
- **Codex**: Blocks `npm` in `PreToolUse` hook (`hooks.json`) and guides the model to use `pnpm`.
