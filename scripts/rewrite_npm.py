#!/usr/bin/env python3
"""
always-pnpm: Antigravity PreToolUse hook for run_command.
Intercepts shell commands and transparently rewrites npm/npx invocations to pnpm.
"""

import sys
import json
import re


ALIAS = {"i": "add", "rm": "remove", "uninstall": "remove", "up": "update", "t": "test", "list": "ls", "explain": "why"}

# Leading KEY=VAL assignments, then the npm/npx word itself.
CMD_RE = re.compile(r"""(\s*(?:[A-Za-z_]\w*=(?:'[^']*'|"(?:[^"\\]|\\.)*"|\\.|[^\s'"\\])*\s+)*)(np[mx])(?=\s|$)(.*)""", re.S)

# ponytail: common npm flags that take a separate value; extend when another one shows up.
VALUE_FLAGS = {"--prefix", "--registry", "--cache", "--userconfig", "--tag", "-w", "--workspace"}


def translate(cmd, words):
    """Return (new_head, n_words_consumed_after_cmd, words_to_drop)."""
    if cmd == "npx":
        return "pnpm dlx", 0, ()
    if not words:
        return "pnpm", 0, ()
    sub = ALIAS.get(words[0], words[0])
    rest = words[1:]
    if sub in ("install", "add"):
        # 'npm install' -> 'pnpm install'; 'npm install <pkgs>' -> 'pnpm add <pkgs>'
        pkgs = [w for prev, w in zip([""] + rest, rest) if not w.startswith("-") and prev not in VALUE_FLAGS]
        return ("pnpm add" if pkgs else "pnpm install"), 1, ()
    if sub == "ci":
        return "pnpm install --frozen-lockfile", 1, ()
    if sub == "init":
        if rest and not rest[0].startswith("-"):
            return "pnpm create", 1, ()
        return "pnpm init", 1, ("-y",)
    if sub == "exec":
        return "pnpm dlx", 1, ()
    if sub == "audit" and rest[:1] == ["fix"]:
        return "pnpm audit --fix", 2, ()
    if sub == "cache" and rest[:1] == ["clean"]:
        return "pnpm store prune", 2, ("--force",)
    return f"pnpm {sub}", 1, ()


def rewrite_segment(seg):
    """Rewrite one simple command, splicing only the npm head so args, quotes and spacing survive."""
    m = CMD_RE.match(seg)
    if not m:
        return seg
    env, cmd, tail = m.groups()
    head, n, drop = translate(cmd, tail.split())
    tail = re.sub(r"^(?:\s+\S+){%d}" % n, "", tail)
    for w in drop:
        tail = re.sub(r"\s+%s(?!\S)" % re.escape(w), "", tail)
    return env + head + tail


def split_shell_pipeline(cmd_line):
    """
    Splits a compound shell command line by operators (&&, ||, ;, |, &, newline)
    outside of quotes. Returns [(segment, delimiter)]; joining them gives back cmd_line.
    """
    segments = []
    current = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(cmd_line)

    while i < n:
        c = cmd_line[i]
        if escaped:
            current.append(c)
            escaped = False
            i += 1
            continue

        if c == '\\' and not in_single:
            escaped = True
            current.append(c)
            i += 1
            continue

        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if cmd_line[i:i+2] in ("&&", "||"):
                segments.append((''.join(current), cmd_line[i:i+2]))
                current = []
                i += 2
                continue
            # '&' inside a redirection (2>&1, &>file, >&2) is not a separator
            redirect = c == "&" and ((i and cmd_line[i-1] in "<>") or cmd_line[i+1:i+2] == ">")
            if c in ";|&\n" and not redirect:
                segments.append((''.join(current), c))
                current = []
                i += 1
                continue

        current.append(c)
        i += 1

    segments.append((''.join(current), ''))
    return segments


def rewrite_command_line(cmd_line):
    """
    Takes a shell command line string, rewrites any npm/npx invocations,
    and returns (rewritten_cmd_line, bool_changed).
    """
    try:
        rewritten = "".join(rewrite_segment(seg) + delim for seg, delim in split_shell_pipeline(cmd_line))
        return rewritten, rewritten != cmd_line
    except Exception:
        return cmd_line, False


def process_hook_payload(payload):
    """
    Processes hook JSON payloads for Antigravity, Claude Code, and Codex.
    """
    if not isinstance(payload, dict):
        return {"decision": "allow"}

    # 1. Claude Code / Codex payload: {"tool_name": "Bash", "tool_input": {"command": "..."}}
    if payload.get("tool_name") == "Bash":
        tool_input = payload.get("tool_input", {})
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        if command and isinstance(command, str):
            rewritten, changed = rewrite_command_line(command)
            if changed:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"always-pnpm: 'npm' is blocked. Run '{rewritten}' instead."
                    }
                }
        return None

    # 2. Antigravity payload: {"toolCall": {"name": "run_command", "args": {"CommandLine": "..."}}}
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else None
    args = tool_call.get("args", {}) if isinstance(tool_call, dict) else {}

    if tool_name == "run_command" and isinstance(args, dict):
        command_line = args.get("CommandLine", "")
        if command_line and isinstance(command_line, str):
            rewritten, changed = rewrite_command_line(command_line)
            if changed:
                return {
                    "decision": "allow",
                    "reason": f"always-pnpm: rewritten '{command_line}' -> '{rewritten}'",
                    "overwrite": {
                        "CommandLine": rewritten
                    }
                }

    return {"decision": "allow"}


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--translate", "-t"):
        if len(sys.argv) > 2:
            cmd = " ".join(sys.argv[2:])
        else:
            cmd = ""
        rewritten, changed = rewrite_command_line(cmd)
        print(rewritten)
        sys.exit(0 if changed else 1)

    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        response = process_hook_payload(payload)
        if response:
            print(json.dumps(response))
    except Exception:
        # Failsafe: never block agent execution on unexpected internal script error
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
