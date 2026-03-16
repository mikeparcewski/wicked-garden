#!/usr/bin/env python3
"""
invoke.py — Cross-platform Python script dispatcher for wicked-garden hooks.

On macOS/Linux, `python3` is the standard command. On Windows, Python often
installs as `python` or `py` instead. This dispatcher is itself a Python
script invoked via `python3 || python || py` in hooks.json, and then it
reliably launches the target hook script using the same interpreter that
successfully ran this file (sys.executable).

Usage (from hooks.json):
    "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/invoke.py\" bootstrap || python \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/invoke.py\" bootstrap || py \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/invoke.py\" bootstrap"

The target script name is the first argument (without .py extension).
stdin is forwarded to the target script (hooks receive JSON on stdin).
"""

import os
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(
            '{"ok": false, "reason": "invoke.py: missing script name argument"}',
            file=sys.stderr,
        )
        # Fail open — hooks should not block the user
        print('{"ok": true}')
        return

    script_name = sys.argv[1]
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(scripts_dir, f"{script_name}.py")

    if not os.path.isfile(target):
        print(
            f'{{"ok": false, "reason": "invoke.py: script not found: {script_name}.py"}}',
            file=sys.stderr,
        )
        print('{"ok": true}')
        return

    # Use the same Python interpreter that is running this script.
    # This guarantees we use the correct python on any platform.
    python = sys.executable

    # Read stdin once and pass it to the subprocess (hooks receive JSON on stdin).
    stdin_data = sys.stdin.buffer.read()

    result = subprocess.run(
        [python, target] + sys.argv[2:],
        input=stdin_data,
        capture_output=False,
        timeout=120,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
