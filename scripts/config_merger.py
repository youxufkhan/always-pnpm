#!/usr/bin/env python3
"""
Safely merges always-pnpm hooks into existing Claude Code and Codex configurations.
"""

import os
import sys
import json


def load_json_safe(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def merge_claude_settings(settings_path, script_path):
    data = load_json_safe(settings_path)
    if "hooks" not in data or not isinstance(data["hooks"], dict):
        data["hooks"] = {}

    hooks_dict = data["hooks"]
    if "PreToolUse" not in hooks_dict or not isinstance(hooks_dict["PreToolUse"], list):
        hooks_dict["PreToolUse"] = []

    pre_hooks = hooks_dict["PreToolUse"]
    # Check if always-pnpm matcher already present
    existing = False
    for item in pre_hooks:
        if isinstance(item, dict) and item.get("matcher") == "Bash":
            for h in item.get("hooks", []):
                if "rewrite_npm.py" in h.get("command", ""):
                    h["command"] = f"python3 {script_path}"
                    existing = True
            if not existing:
                item.setdefault("hooks", []).append({
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                })
                existing = True

    if not existing:
        pre_hooks.append({
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                }
            ]
        })

    save_json(settings_path, data)
    return data


def merge_codex_hooks(hooks_path, script_path):
    data = load_json_safe(hooks_path)
    if "PreToolUse" not in data or not isinstance(data["PreToolUse"], list):
        data["PreToolUse"] = []

    pre_hooks = data["PreToolUse"]
    existing = False
    for item in pre_hooks:
        if isinstance(item, dict) and item.get("matcher") == "bash":
            for h in item.get("hooks", []):
                if "rewrite_npm.py" in h.get("command", ""):
                    h["command"] = f"python3 {script_path}"
                    existing = True
            if not existing:
                item.setdefault("hooks", []).append({
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                })
                existing = True

    if not existing:
        pre_hooks.append({
            "matcher": "bash",
            "hooks": [
                {
                    "type": "command",
                    "command": f"python3 {script_path}",
                    "timeout": 10
                }
            ]
        })

    save_json(hooks_path, data)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: config_merger.py <claude|codex> <config_file> <script_path>")
        sys.exit(1)

    target_type = sys.argv[1].lower()
    conf_file = sys.argv[2]
    script = os.path.abspath(sys.argv[3])

    if target_type == "claude":
        merge_claude_settings(conf_file, script)
    elif target_type == "codex":
        merge_codex_hooks(conf_file, script)
    else:
        print(f"Unknown target: {target_type}")
        sys.exit(1)
