#!/usr/bin/env python3
"""
Merges the always-pnpm PreToolUse hook into a Claude Code settings.json or Codex hooks.json
(both use the same {"hooks": {"PreToolUse": [...]}} format).
"""

import os
import shlex
import sys
import json


def merge_hook(path, script_path):
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)  # bad JSON raises: never overwrite a config we can't read

    # Older installs wrote Codex hooks at the top level; drop our stale entries there.
    legacy = data.get("PreToolUse")
    if isinstance(legacy, list):
        legacy[:] = [item for item in legacy if "rewrite_npm.py" not in json.dumps(item)]
        if not legacy:
            del data["PreToolUse"]

    # setdefault raises on unexpected types instead of silently replacing user config
    pre_hooks = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
    command = f"python3 {shlex.quote(script_path)}"
    ours = [h for item in pre_hooks if isinstance(item, dict) and isinstance(item.get("hooks"), list)
            for h in item["hooks"] if isinstance(h, dict) and "rewrite_npm.py" in str(h.get("command", ""))]
    for h in ours:
        h["command"] = command
    if not ours:
        pre_hooks.append({"matcher": "Bash", "hooks": [{"type": "command", "command": command, "timeout": 10}]})

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return data


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: config_merger.py <config_file> <script_path>")
    try:
        merge_hook(sys.argv[1], os.path.abspath(sys.argv[2]))
    except (ValueError, AttributeError) as e:
        sys.exit(f"always-pnpm: can't update {sys.argv[1]} ({e}). Fix the file and re-run install.sh.")
