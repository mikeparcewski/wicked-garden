#!/bin/sh
# Cross-platform Python 3 resolver for wicked-garden.
#
# On macOS/Linux, `python3` is standard. On Windows (Git Bash, MSYS2),
# Python may only be available as `python` or `py -3`.
#
# Usage:
#   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" script.py [args...]
#
# This script tries python3, then python, then py -3, and exec's the
# first one that exists. If none are found, exits with an error.

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$@"
elif command -v py >/dev/null 2>&1; then
    exec py -3 "$@"
else
    echo '{"ok": false, "reason": "Python 3 not found. Install Python 3 and ensure python3, python, or py is on PATH."}' >&2
    exit 1
fi
