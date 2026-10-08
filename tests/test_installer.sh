#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_TMP="$(mktemp -d)"

cleanup() {
  rm -rf "$TEST_TMP"
}
trap cleanup EXIT

echo "==> Testing Multi-Agent Installer Suite..."

# --- Test 1: Antigravity Target ---
echo "--- Test 1: Antigravity Target ---"
HOME_ANTI="$TEST_TMP/home_anti"
mkdir -p "$HOME_ANTI"
HOME="$HOME_ANTI" "$SCRIPT_DIR/scripts/install.sh" --antigravity
if [ -f "$HOME_ANTI/.gemini/config/plugins/always-pnpm/plugin.json" ] && [ -x "$HOME_ANTI/.gemini/config/plugins/always-pnpm/scripts/rewrite_npm.py" ]; then
  echo "PASS: Antigravity installation valid"
else
  echo "FAIL: Antigravity installation missing files"
  exit 1
fi

# --- Test 2: Claude Code Target & Config Merge ---
echo "--- Test 2: Claude Code Target ---"
HOME_CLAUDE="$TEST_TMP/home_claude"
mkdir -p "$HOME_CLAUDE/.claude"
echo '{"theme": "dark", "fontSize": 14}' > "$HOME_CLAUDE/.claude/settings.json"
echo "# my personal rules" > "$HOME_CLAUDE/.claude/CLAUDE.md"
HOME="$HOME_CLAUDE" "$SCRIPT_DIR/scripts/install.sh" --claude
HOME="$HOME_CLAUDE" "$SCRIPT_DIR/scripts/install.sh" --claude
grep -q "my personal rules" "$HOME_CLAUDE/.claude/CLAUDE.md" || { echo "FAIL: CLAUDE.md clobbered"; exit 1; }
[ "$(grep -c "Mandatory pnpm Usage" "$HOME_CLAUDE/.claude/CLAUDE.md")" = 1 ] || { echo "FAIL: rules appended twice"; exit 1; }
[ "$(grep -c rewrite_npm.py "$HOME_CLAUDE/.claude/settings.json")" = 1 ] || { echo "FAIL: hook duplicated"; exit 1; }

if [ -f "$HOME_CLAUDE/.claude/CLAUDE.md" ] && grep -q "theme" "$HOME_CLAUDE/.claude/settings.json" && grep -q "rewrite_npm.py" "$HOME_CLAUDE/.claude/settings.json"; then
  echo "PASS: Claude Code installation and settings merge valid"
else
  echo "FAIL: Claude Code installation invalid"
  exit 1
fi

# --- Test 3: OpenCode Target ---
echo "--- Test 3: OpenCode Target ---"
HOME_OPEN="$TEST_TMP/home_open"
mkdir -p "$HOME_OPEN"
HOME="$HOME_OPEN" "$SCRIPT_DIR/scripts/install.sh" --opencode
grep -qF "$HOME_OPEN/.local/share/always-pnpm/scripts/rewrite_npm.py" "$HOME_OPEN/.config/opencode/plugins/always-pnpm.js" || { echo "FAIL: OpenCode rewriter path not substituted"; exit 1; }

if [ -f "$HOME_OPEN/.config/opencode/plugins/always-pnpm.js" ] && [ -f "$HOME_OPEN/.config/opencode/AGENTS.md" ] && [ -f "$HOME_OPEN/.config/opencode/skills/always-pnpm/SKILL.md" ]; then
  echo "PASS: OpenCode installation valid"
else
  echo "FAIL: OpenCode installation invalid"
  exit 1
fi

# --- Test 4: Codex Target ---
echo "--- Test 4: Codex Target ---"
HOME_CODEX="$TEST_TMP/home_codex"
mkdir -p "$HOME_CODEX"
HOME="$HOME_CODEX" "$SCRIPT_DIR/scripts/install.sh" --codex

if [ -f "$HOME_CODEX/.codex/AGENTS.md" ] && [ -f "$HOME_CODEX/.codex/hooks.json" ] && grep -q "rewrite_npm.py" "$HOME_CODEX/.codex/hooks.json"; then
  echo "PASS: Codex installation valid"
else
  echo "FAIL: Codex installation invalid"
  exit 1
fi

# --- Test 5: Auto-Detection Mode ---
echo "--- Test 5: Auto-Detection Mode ---"
HOME_AUTO="$TEST_TMP/home_auto"
mkdir -p "$HOME_AUTO/.claude" "$HOME_AUTO/.config/opencode"
HOME="$HOME_AUTO" "$SCRIPT_DIR/scripts/install.sh"

if [ -f "$HOME_AUTO/.claude/CLAUDE.md" ] && [ -f "$HOME_AUTO/.config/opencode/plugins/always-pnpm.js" ]; then
  echo "PASS: Auto-detection successfully configured detected agents"
else
  echo "FAIL: Auto-detection failed"
  exit 1
fi

# --- Test 6: All Flag ---
echo "--- Test 6: All Flag ---"
HOME_ALL="$TEST_TMP/home_all"
mkdir -p "$HOME_ALL"
HOME="$HOME_ALL" "$SCRIPT_DIR/scripts/install.sh" --all

if [ -f "$HOME_ALL/.gemini/config/plugins/always-pnpm/plugin.json" ] && \
   [ -f "$HOME_ALL/.claude/CLAUDE.md" ] && \
   [ -f "$HOME_ALL/.config/opencode/plugins/always-pnpm.js" ] && \
   [ -f "$HOME_ALL/.codex/AGENTS.md" ]; then
  echo "PASS: --all installed to all four targets"
else
  echo "FAIL: --all failed"
  exit 1
fi

# --- Test 7: Local Workspace Mode ---
echo "--- Test 7: Local Workspace Mode ---"
WORK_DIR="$TEST_TMP/workspace"
mkdir -p "$WORK_DIR"
(
  cd "$WORK_DIR"
  "$SCRIPT_DIR/scripts/install.sh" --local
  if [ -f "$WORK_DIR/.claude/CLAUDE.md" ] && \
     [ -f "$WORK_DIR/.opencode/plugins/always-pnpm.js" ] && \
     [ -f "$WORK_DIR/.codex/AGENTS.md" ] && \
     [ -f "$WORK_DIR/.agents/plugins/always-pnpm/plugin.json" ]; then
    echo "PASS: --local configured all workspace targets"
  else
    echo "FAIL: --local failed"
    exit 1
  fi
)

echo "ALL installer tests passed successfully!"
