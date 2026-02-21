#!/usr/bin/env python3
"""PostToolUse hook: Mark files as stale when modified via Write/Edit tools.

Reads the tool input from stdin to extract the file path, then appends it
to a per-project stale file list under
~/.something-wicked/wicked-search/projects/{project}/stale_files.json
so the next /wicked-search:index run can do an incremental update.
"""
import json
import sys
from pathlib import Path

PROJECT_NAME = Path.cwd().name
STALE_FILE = (
    Path.home()
    / ".something-wicked"
    / "wicked-search"
    / "projects"
    / PROJECT_NAME
    / "stale_files.json"
)


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

    # Load existing stale files into a set for O(1) dedup
    stale_set = set()
    if STALE_FILE.exists():
        try:
            existing = json.loads(STALE_FILE.read_text())
            if isinstance(existing, list):
                stale_set.update(existing)
        except (json.JSONDecodeError, OSError):
            pass

    # Add the file
    stale_set.add(file_path)

    # Write back as sorted list for deterministic output
    try:
        STALE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STALE_FILE.write_text(json.dumps(sorted(stale_set), indent=2))
    except OSError:
        pass  # Fail gracefully

    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
