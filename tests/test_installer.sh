#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_TMP="$(mktemp -d)"

cleanup() {
  rm -rf "$TEST_TMP"
}
trap cleanup EXIT

# Test local install
export HOME="$TEST_TMP"
MOCK_CONFIG="$TEST_TMP/.gemini/config/plugins"
mkdir -p "$MOCK_CONFIG"

# Run install in symlink mode
"$SCRIPT_DIR/scripts/install.sh" --symlink

# Verify symlink exists
if [ -L "$MOCK_CONFIG/always-pnpm" ]; then
  echo "PASS: Symlink created successfully"
else
  echo "FAIL: Symlink not found"
  exit 1
fi

# Run install in copy mode to a new mock home
TEST_TMP2="$(mktemp -d)"
export HOME="$TEST_TMP2"
"$SCRIPT_DIR/scripts/install.sh"

if [ -f "$TEST_TMP2/.gemini/config/plugins/always-pnpm/plugin.json" ] && [ -x "$TEST_TMP2/.gemini/config/plugins/always-pnpm/scripts/rewrite_npm.py" ]; then
  echo "PASS: Copy mode created valid plugin installation"
  rm -rf "$TEST_TMP2"
else
  echo "FAIL: Copy mode installation invalid"
  rm -rf "$TEST_TMP2"
  exit 1
fi

echo "All installer tests passed!"
