#!/usr/bin/env bash
# always-pnpm: Universal Multi-Agent Installer
# Supports: Antigravity, Claude Code, OpenCode, and Codex.
# Usage: ./install.sh [--all | --antigravity | --claude | --opencode | --codex] [--symlink | --local]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_MODE="copy"
TARGET_ANTIGRAVITY=false
TARGET_CLAUDE=false
TARGET_OPENCODE=false
TARGET_CODEX=false
EXPLICIT_TARGET=false

for arg in "$@"; do
  case "$arg" in
    --symlink) INSTALL_MODE="symlink" ;;
    --local) INSTALL_MODE="local" ;;
    --antigravity) TARGET_ANTIGRAVITY=true; EXPLICIT_TARGET=true ;;
    --claude) TARGET_CLAUDE=true; EXPLICIT_TARGET=true ;;
    --opencode) TARGET_OPENCODE=true; EXPLICIT_TARGET=true ;;
    --codex) TARGET_CODEX=true; EXPLICIT_TARGET=true ;;
    --all)
      TARGET_ANTIGRAVITY=true; TARGET_CLAUDE=true; TARGET_OPENCODE=true; TARGET_CODEX=true
      EXPLICIT_TARGET=true ;;
    --help|-h)
      echo "always-pnpm - Universal Multi-Agent Installer"
      echo "Usage: ./install.sh [TARGETS] [OPTIONS]"
      echo ""
      echo "Targets (auto-detected if none specified):"
      echo "  --all          Install across Antigravity, Claude Code, OpenCode, and Codex"
      echo "  --antigravity  Install for Antigravity only"
      echo "  --claude       Install for Claude Code only"
      echo "  --opencode     Install for OpenCode only"
      echo "  --codex        Install for Codex only"
      echo ""
      echo "Options:"
      echo "  --symlink      Symlink files for live development"
      echo "  --local        Install locally into current workspace (.agents/, .claude/, .opencode/, .codex/)"
      exit 0
      ;;
  esac
done

echo "==> Installing always-pnpm..."

# Check prerequisites
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not installed." >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "Notice: pnpm is not found on PATH. Install via: npm install -g pnpm or corepack enable."
fi

# In local mode, configure all workspace targets
if [ "$INSTALL_MODE" = "local" ]; then
  TARGET_ANTIGRAVITY=true
  TARGET_CLAUDE=true
  TARGET_OPENCODE=true
  TARGET_CODEX=true
elif [ "$EXPLICIT_TARGET" = false ]; then
  # Auto-detect installed agents
  echo "==> Auto-detecting installed agents..."
  if command -v antigravity >/dev/null 2>&1 || [ -d "${HOME}/.gemini" ]; then
    TARGET_ANTIGRAVITY=true
    echo "  [x] Antigravity detected"
  fi
  if command -v claude >/dev/null 2>&1 || [ -d "${HOME}/.claude" ]; then
    TARGET_CLAUDE=true
    echo "  [x] Claude Code detected"
  fi
  if command -v opencode >/dev/null 2>&1 || [ -d "${HOME}/.config/opencode" ]; then
    TARGET_OPENCODE=true
    echo "  [x] OpenCode detected"
  fi
  if command -v codex >/dev/null 2>&1 || [ -d "${HOME}/.codex" ]; then
    TARGET_CODEX=true
    echo "  [x] Codex detected"
  fi

  # Fallback if none specifically detected: install to all standard paths
  if [ "$TARGET_ANTIGRAVITY" = false ] && [ "$TARGET_CLAUDE" = false ] && [ "$TARGET_OPENCODE" = false ] && [ "$TARGET_CODEX" = false ]; then
    echo "  No specific agent detected. Defaulting to all agent configurations."
    TARGET_ANTIGRAVITY=true
    TARGET_CLAUDE=true
    TARGET_OPENCODE=true
    TARGET_CODEX=true
  fi
fi

# Determine canonical script path
if [ "$INSTALL_MODE" = "local" ]; then
  CANONICAL_SCRIPT="$(pwd)/.agents/plugins/always-pnpm/scripts/rewrite_npm.py"
elif [ "$INSTALL_MODE" = "symlink" ]; then
  CANONICAL_SCRIPT="$SCRIPT_DIR/scripts/rewrite_npm.py"
else
  CANONICAL_DIR="${HOME}/.local/share/always-pnpm/scripts"
  mkdir -p "$CANONICAL_DIR"
  cp -f "$SCRIPT_DIR/scripts/rewrite_npm.py" "$CANONICAL_DIR/"
  chmod +x "$CANONICAL_DIR/rewrite_npm.py"
  CANONICAL_SCRIPT="$CANONICAL_DIR/rewrite_npm.py"
fi

# Append rules to the user's instruction file once, never clobber it.
# ponytail: re-install won't refresh an already-appended block; edit it by hand if rules change.
add_rules() {
  grep -qsF "Mandatory pnpm Usage" "$1" && return
  [ -s "$1" ] && echo >> "$1"
  cat "$SCRIPT_DIR/rules/AGENTS.md" >> "$1"
}

# 1. Antigravity Installation
if [ "$TARGET_ANTIGRAVITY" = true ]; then
  echo "-> Configuring Antigravity..."
  if [ "$INSTALL_MODE" = "local" ]; then
    AG_DIR="$(pwd)/.agents/plugins/always-pnpm"
  else
    AG_DIR="${HOME}/.gemini/config/plugins/always-pnpm"
  fi

  if [ "$INSTALL_MODE" = "symlink" ]; then
    mkdir -p "$(dirname "$AG_DIR")"
    rm -rf "$AG_DIR"
    ln -s "$SCRIPT_DIR" "$AG_DIR"
  else
    mkdir -p "$AG_DIR/rules" "$AG_DIR/skills/always-pnpm" "$AG_DIR/scripts"
    cp -f "$SCRIPT_DIR/plugin.json" "$AG_DIR/"
    cp -f "$SCRIPT_DIR/hooks.json" "$AG_DIR/"
    cp -f "$SCRIPT_DIR/rules/AGENTS.md" "$AG_DIR/rules/"
    cp -f "$SCRIPT_DIR/skills/always-pnpm/SKILL.md" "$AG_DIR/skills/always-pnpm/"
    cp -f "$SCRIPT_DIR/scripts/rewrite_npm.py" "$AG_DIR/scripts/"
    chmod +x "$AG_DIR/scripts/rewrite_npm.py"
  fi
  echo "  ✓ Antigravity configured at $AG_DIR"
fi

# 2. Claude Code Installation
if [ "$TARGET_CLAUDE" = true ]; then
  echo "-> Configuring Claude Code..."
  if [ "$INSTALL_MODE" = "local" ]; then
    CLAUDE_DIR="$(pwd)/.claude"
  else
    CLAUDE_DIR="${HOME}/.claude"
  fi
  mkdir -p "$CLAUDE_DIR"
  
  # Safe settings merge
  SETTINGS_FILE="$CLAUDE_DIR/settings.json"
  python3 "$SCRIPT_DIR/scripts/config_merger.py" "$SETTINGS_FILE" "$CANONICAL_SCRIPT"
  add_rules "$CLAUDE_DIR/CLAUDE.md"
  echo "  ✓ Claude Code configured at $CLAUDE_DIR"
fi

# 3. OpenCode Installation
if [ "$TARGET_OPENCODE" = true ]; then
  echo "-> Configuring OpenCode..."
  if [ "$INSTALL_MODE" = "local" ]; then
    OPEN_DIR="$(pwd)/.opencode"
  else
    OPEN_DIR="${HOME}/.config/opencode"
  fi
  mkdir -p "$OPEN_DIR/plugins" "$OPEN_DIR/skills/always-pnpm"
  python3 -c 'import json, sys; src, dst, path = sys.argv[1:]; open(dst, "w").write(open(src).read().replace("\"__ALWAYS_PNPM_SCRIPT__\"", json.dumps(path)))' \
    "$SCRIPT_DIR/plugins/opencode/always-pnpm.js" "$OPEN_DIR/plugins/always-pnpm.js" "$CANONICAL_SCRIPT"
  add_rules "$OPEN_DIR/AGENTS.md"
  cp -f "$SCRIPT_DIR/skills/always-pnpm/SKILL.md" "$OPEN_DIR/skills/always-pnpm/"
  echo "  ✓ OpenCode configured at $OPEN_DIR"
fi

# 4. Codex Installation
if [ "$TARGET_CODEX" = true ]; then
  echo "-> Configuring Codex..."
  if [ "$INSTALL_MODE" = "local" ]; then
    CODEX_DIR="$(pwd)/.codex"
  else
    CODEX_DIR="${HOME}/.codex"
  fi
  mkdir -p "$CODEX_DIR"

  # Safe hooks merge
  HOOKS_FILE="$CODEX_DIR/hooks.json"
  python3 "$SCRIPT_DIR/scripts/config_merger.py" "$HOOKS_FILE" "$CANONICAL_SCRIPT"
  add_rules "$CODEX_DIR/AGENTS.md"
  echo "  ✓ Codex configured at $CODEX_DIR"
fi

echo ""
echo "✨ always-pnpm is successfully configured! All active agents will now use pnpm."
