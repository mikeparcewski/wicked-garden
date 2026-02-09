#!/bin/bash
# Cross-platform Python runner for hooks
# Detects available package manager and runs the script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SCRIPT="$1"
shift

cd "$PLUGIN_ROOT" || exit 1

# Try package managers in order of preference
if command -v uv &> /dev/null; then
    exec uv run python "$SCRIPT" "$@"
elif command -v poetry &> /dev/null && [ -f "pyproject.toml" ]; then
    exec poetry run python "$SCRIPT" "$@"
elif [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python "$SCRIPT" "$@"
elif [ -f "venv/bin/python" ]; then
    exec venv/bin/python "$SCRIPT" "$@"
else
    exec python3 "$SCRIPT" "$@"
fi
