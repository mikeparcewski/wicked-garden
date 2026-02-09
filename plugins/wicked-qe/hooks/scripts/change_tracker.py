#!/usr/bin/env python3
"""
PostToolUse hook for Write|Edit — tracks changed files per session.

When 3+ unique files have been modified, suggests running verification
(tests, type checks, imports) to catch cascading bugs early.

Emits a non-blocking system message nudge, never blocks the tool.
"""

import json
import os
import sys
import tempfile
from pathlib import Path


# Threshold: suggest verification after this many unique files changed
CHANGE_THRESHOLD = 3


def get_tracker_path() -> Path:
    """Get path to session change tracker file."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-qe-changes-{session_id}"


def load_changed_files() -> set:
    """Load set of changed file paths from tracker."""
    tracker = get_tracker_path()
    try:
        data = json.loads(tracker.read_text())
        return set(data.get("files", []))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return set()


def save_changed_files(files: set, nudged: bool = False):
    """Save changed file set to tracker."""
    tracker = get_tracker_path()
    tracker.write_text(json.dumps({
        "files": sorted(files),
        "nudged": nudged,
    }))


def was_already_nudged() -> bool:
    """Check if we already nudged for this batch."""
    tracker = get_tracker_path()
    try:
        data = json.loads(tracker.read_text())
        return data.get("nudged", False)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return False


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Extract the file path from Write or Edit tool input
        file_path = tool_input.get("file_path", "")
        if not file_path:
            print(json.dumps({"continue": True}))
            return

        # Track the change
        changed = load_changed_files()
        changed.add(file_path)
        unique_count = len(changed)

        # Check if we should nudge
        already_nudged = was_already_nudged()
        if unique_count >= CHANGE_THRESHOLD and not already_nudged:
            # Build a concise file list
            short_paths = []
            for f in sorted(changed):
                p = Path(f)
                short_paths.append(p.name)

            save_changed_files(changed, nudged=True)

            nudge = (
                f"[QE] {unique_count} files changed this session "
                f"({', '.join(short_paths[:5])}). "
                "Consider running tests or verifying imports before "
                "continuing with more changes."
            )
            print(json.dumps({
                "continue": True,
                "systemMessage": nudge,
            }))
        else:
            # Preserve nudged state so we don't re-nudge
            save_changed_files(changed, nudged=already_nudged)
            print(json.dumps({"continue": True}))

    except Exception:
        # Never block on tracker errors
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
