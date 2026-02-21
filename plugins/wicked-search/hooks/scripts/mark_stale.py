#!/usr/bin/env python3
"""PostToolUse hook: Mark files as stale when modified via Write/Edit tools.

Reads the tool input from stdin to extract the file path, then appends it
to ~/.something-wicked/wicked-search/stale_files.json so the next
/wicked-search:index run can do an incremental update.
"""
import json
import sys
from pathlib import Path

STALE_FILE = Path.home() / ".something-wicked" / "wicked-search" / "stale_files.json"


def main():
    try:
        raw = sys.stdin.read()
    except IOError:
        raw = ""

    # Parse hook input to get the file path
    file_path = None
    try:
        event = json.loads(raw) if raw.strip() else {}
        # PostToolUse provides tool_input with the file_path or file
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("file")
    except (json.JSONDecodeError, AttributeError):
        pass

    if not file_path:
        # Nothing to track — succeed silently
        print(json.dumps({"ok": True}))
        return

    # Load existing stale files
    stale_files = []
    if STALE_FILE.exists():
        try:
            stale_files = json.loads(STALE_FILE.read_text())
            if not isinstance(stale_files, list):
                stale_files = []
        except (json.JSONDecodeError, OSError):
            stale_files = []

    # Add the file if not already tracked
    if file_path not in stale_files:
        stale_files.append(file_path)

    # Write back
    try:
        STALE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STALE_FILE.write_text(json.dumps(stale_files, indent=2))
    except OSError:
        pass  # Fail gracefully

    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
