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
