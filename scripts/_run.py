#!/usr/bin/env python3
"""Smart script runner with automatic help recovery.

Two modes:
  1. Usage mode:  _run.py --usage <script> [subcommand]
     Shows --help output so the caller knows exact CLI syntax.

  2. Run mode:    _run.py <script> [subcommand] [args...]
     Executes normally. On argparse errors (exit code 2),
     automatically appends --help output for self-correction.

Script paths are resolved relative to CLAUDE_PLUGIN_ROOT (or this
script's parent directory as fallback).

Examples:
  # Show usage before invoking
  python3 scripts/_run.py --usage scripts/search/unified_search.py index

  # Run with auto-help on error
  python3 scripts/_run.py scripts/search/unified_search.py index /path --project foo

  # Works with uv for scripts that need deps
  cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/search/unified_search.py index /path
"""

import json
import os
import subprocess
import sys


def resolve_script(script: str) -> str:
    """Resolve script path relative to plugin root."""
    if os.path.isabs(script):
        return script
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(plugin_root, script)


def find_subcommand(args: list[str]) -> str | None:
    """Find the first positional arg (likely a subcommand)."""
    for a in args:
        if not a.startswith("-"):
            return a
    return None


def build_help_cmd(script_path: str, args: list[str]) -> list[str]:
    """Build a --help command, including subcommand if present."""
    cmd = [sys.executable, script_path]
    sub = find_subcommand(args)
    if sub:
        cmd.append(sub)
    cmd.append("--help")
    return cmd


def run_usage(script_path: str, args: list[str]) -> int:
    """Show --help output for a script/subcommand."""
    cmd = build_help_cmd(script_path, args)
    result = subprocess.run(cmd, capture_output=True, text=True)

    output = {
        "ok": result.returncode == 0,
        "mode": "usage",
        "command": " ".join(cmd),
        "usage": result.stdout.strip(),
    }
    if result.stderr.strip():
        output["stderr"] = result.stderr.strip()

    print(json.dumps(output, indent=2))
    return 0


def run_script(script_path: str, args: list[str]) -> int:
    """Execute script, auto-recovering with help on argparse errors."""
    cmd = [sys.executable, script_path] + args
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 2:
        # Argparse error -- fetch help for recovery
        help_cmd = build_help_cmd(script_path, args)
        help_result = subprocess.run(help_cmd, capture_output=True, text=True)

        output = {
            "ok": False,
            "mode": "error_recovery",
            "error": result.stderr.strip(),
            "usage": help_result.stdout.strip(),
        }
        print(json.dumps(output, indent=2))
        return 2

    # Pass through normal output
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: _run.py [--usage] <script.py> [args...]\n"
            "  --usage  Show help for a script/subcommand\n"
            "  (omit)   Run script with auto-help on argument errors",
            file=sys.stderr,
        )
        return 1

    usage_mode = sys.argv[1] == "--usage"
    script_args = sys.argv[2:] if usage_mode else sys.argv[1:]

    if not script_args:
        print("Error: no script specified", file=sys.stderr)
        return 1

    script_path = resolve_script(script_args[0])
    remaining = script_args[1:]

    if not os.path.isfile(script_path):
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        return 1

    if usage_mode:
        return run_usage(script_path, remaining)
    else:
        return run_script(script_path, remaining)


if __name__ == "__main__":
    sys.exit(main())
