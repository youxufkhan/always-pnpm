#!/usr/bin/env python3
"""
always-pnpm: Antigravity PreToolUse hook for run_command.
Intercepts shell commands and transparently rewrites npm/npx invocations to pnpm.
"""

import sys
import json
import re
import shlex


def translate_subcommand_tokens(tokens):
    """
    Translates a list of shell tokens for a single command invocation.
    Returns (rewritten_tokens, bool_changed).
    """
    if not tokens:
        return tokens, False

    # Find index of the command executable, skipping environment variable assignments (KEY=VAL)
    cmd_idx = 0
    while cmd_idx < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=.*', tokens[cmd_idx]):
        cmd_idx += 1

    if cmd_idx >= len(tokens):
        return tokens, False

    cmd = tokens[cmd_idx]
    args = tokens[cmd_idx + 1:]

    # Handle npx -> pnpm dlx
    if cmd == "npx":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "dlx"] + args
        return new_tokens, True

    # If not npm, return unchanged
    if cmd != "npm":
        return tokens, False

    # Handle bare 'npm'
    if not args:
        return list(tokens[:cmd_idx]) + ["pnpm"], True

    sub = args[0]
    sub_args = args[1:]

    # Install mappings
    if sub in ("install", "i", "add"):
        # Distinguish between 'npm install' (no package args) and 'npm install <pkgs>'
        # Options/flags start with '-'
        pkg_args = [a for a in sub_args if not a.startswith("-")]
        if not pkg_args:
            # e.g., 'npm install' -> 'pnpm install'
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "install"] + sub_args
        else:
            # e.g., 'npm install express' -> 'pnpm add express'
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "add"] + sub_args
        return new_tokens, True

    if sub == "ci":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "install", "--frozen-lockfile"] + sub_args
        return new_tokens, True

    if sub in ("uninstall", "rm", "remove"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "remove"] + sub_args
        return new_tokens, True

    if sub in ("update", "up"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "update"] + sub_args
        return new_tokens, True

    if sub == "prune":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "prune"] + sub_args
        return new_tokens, True

    if sub == "run":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "run"] + sub_args
        return new_tokens, True

    if sub in ("test", "t"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "test"] + sub_args
        return new_tokens, True

    if sub in ("start", "stop", "restart"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
        return new_tokens, True

    if sub in ("create", "init"):
        if sub == "create":
            new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "create"] + sub_args
        else:  # init
            if sub_args and not sub_args[0].startswith("-"):
                new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "create"] + sub_args
            else:
                new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "init"] + [a for a in sub_args if a != "-y"]
        return new_tokens, True

    if sub == "exec":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "dlx"] + sub_args
        return new_tokens, True

    if sub in ("ls", "list"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "ls"] + sub_args
        return new_tokens, True

    if sub in ("why", "explain"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "why"] + sub_args
        return new_tokens, True

    if sub == "outdated":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "outdated"] + sub_args
        return new_tokens, True

    if sub == "audit":
        filtered_sub_args = [a for a in sub_args if a != "fix"]
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "audit"] + filtered_sub_args
        return new_tokens, True

    if sub == "cache" and sub_args and sub_args[0] == "clean":
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", "store", "prune"]
        return new_tokens, True

    if sub in ("link", "unlink", "pack", "publish", "rebuild"):
        new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
        return new_tokens, True

    # Generic fallback: npm <subcommand> -> pnpm <subcommand>
    new_tokens = list(tokens[:cmd_idx]) + ["pnpm", sub] + sub_args
    return new_tokens, True


def split_shell_pipeline(cmd_line):
    """
    Splits a compound shell command line by operators (&&, ||, ;, |, &)
    outside of quotes, preserving operators and delimiters.
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
            current.append(c)
            i += 1
            continue

        if c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
            continue

        if not in_single and not in_double:
            if i + 1 < n and cmd_line[i:i+2] in ("&&", "||"):
                op = cmd_line[i:i+2]
                segments.append((''.join(current), op))
                current = []
                i += 2
                continue
            elif c in (";", "|", "&"):
                segments.append((''.join(current), c))
                current = []
                i += 1
                continue

        current.append(c)
        i += 1

    segments.append((''.join(current), ''))
    return segments


def quote_token(token):
    """
    Format a token for shell re-assembly, quoting only if needed.
    """
    if not token:
        return '""'
    if re.search(r'[\s"\'*?~<>|;&$`(){}\[\]]', token):
        return shlex.quote(token)
    return token


def rewrite_command_line(cmd_line):
    """
    Takes a shell command line string, identifies any npm/npx invocations,
    and returns (rewritten_cmd_line, bool_changed).
    """
    try:
        segments = split_shell_pipeline(cmd_line)
        rewritten_parts = []
        any_changed = False

        for sub_cmd, delimiter in segments:
            stripped = sub_cmd.strip()
            if not stripped:
                rewritten_parts.append(sub_cmd + (f" {delimiter} " if delimiter else ""))
                continue

            try:
                tokens = shlex.split(stripped, posix=True)
            except Exception:
                # If shlex fails on syntax, leave segment as-is
                rewritten_parts.append(sub_cmd + (f" {delimiter} " if delimiter else ""))
                continue

            new_tokens, changed = translate_subcommand_tokens(tokens)
            def format_delim(delim):
                if not delim:
                    return ""
                if delim == ";":
                    return "; "
                return f" {delim} "

            if changed:
                any_changed = True
                leading_ws = sub_cmd[:len(sub_cmd) - len(sub_cmd.lstrip())]
                trailing_ws = sub_cmd[len(sub_cmd.rstrip()):]
                reconstructed = leading_ws + " ".join(quote_token(t) for t in new_tokens) + trailing_ws
                reconstructed += format_delim(delimiter)
                rewritten_parts.append(reconstructed)
            else:
                formatted = sub_cmd + format_delim(delimiter)
                rewritten_parts.append(formatted)

        if any_changed:
            final_cmd = "".join(rewritten_parts).strip()
            final_cmd = re.sub(r' +', ' ', final_cmd)
            return final_cmd, True
        return cmd_line, False
    except Exception:
        return cmd_line, False


def process_hook_payload(payload):
    """
    Processes hook JSON payloads for Antigravity, Claude Code, and Codex.
    """
    if not isinstance(payload, dict):
        return {"decision": "allow"}

    # 1. Claude Code payload: {"tool_name": "Bash", "tool_input": {"command": "..."}}
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
        return {"decision": "allow"}

    # 2. Codex payload: {"tool": "bash", "command": "..."}
    if payload.get("tool") == "bash":
        command = payload.get("command", "")
        if command and isinstance(command, str):
            rewritten, changed = rewrite_command_line(command)
            if changed:
                return {
                    "decision": "deny",
                    "reason": f"always-pnpm: 'npm' is blocked. Run '{rewritten}' instead."
                }
        return {"decision": "allow"}

    # 3. Antigravity payload: {"toolCall": {"name": "run_command", "args": {"CommandLine": "..."}}}
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
        print(json.dumps(response))
    except Exception:
        # Failsafe: never block agent execution on unexpected internal script error
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
