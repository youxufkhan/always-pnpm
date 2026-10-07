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
