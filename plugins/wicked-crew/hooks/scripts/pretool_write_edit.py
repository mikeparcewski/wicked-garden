#!/usr/bin/env python3
"""
PreToolUse hook for Write|Edit — enforces orchestrator-only principle.

When an active crew project exists and no specialist has been dispatched
this session, warns the model about direct file writes:
- Test files → stronger warning mentioning wicked-qe
- Implementation files → generic specialist delegation warning

Non-blocking: always returns {"continue": true}.
One-time warning per session to avoid noise.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path


# Patterns that identify test files
TEST_PATTERNS = [
    r"tests?/",           # tests/ or test/ directory
    r"__tests__/",        # Jest convention
    r"\.spec\.",          # .spec.ts, .spec.js, etc.
    r"\.test\.",          # .test.ts, .test.js, etc.
    r"_test\.",           # _test.go, _test.py
    r"test_[^/]*\.py$",  # test_foo.py (Python convention)
]

# File extensions that are considered code (not config/docs)
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".swift", ".kt", ".scala", ".c", ".cpp", ".h",
    ".cs", ".sh", ".bash", ".zsh",
}

# Files to always ignore (config, docs, etc.)
IGNORE_PATTERNS = [
    r"\.md$",
    r"\.json$",
    r"\.yaml$",
    r"\.yml$",
    r"\.toml$",
    r"\.cfg$",
    r"\.ini$",
    r"\.env",
    r"CHANGELOG",
    r"README",
    r"LICENSE",
    r"\.lock$",
]


def get_session_file() -> Path:
    """Get path to session state file."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-crew-session-{session_id}.json"


def load_session_state() -> dict:
    """Load session state, returning empty state on any error."""
    try:
        return json.loads(get_session_file().read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return {"specialist_dispatches": [], "write_guard_warned": False}


def save_session_state(state: dict) -> None:
    """Save session state. Silently ignores errors."""
    try:
        get_session_file().write_text(json.dumps(state))
    except OSError:
        pass


def has_active_crew_project() -> bool:
    """Check if there's an active (non-archived) crew project."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return False

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        project_file = project_dir / "project.json"
        if not project_file.exists():
            continue
        try:
            data = json.loads(project_file.read_text())
            # Archived projects are not active
            if data.get("archived", False):
                continue
            # A project with a current_phase set is active (most robust check)
            current_phase = data.get("current_phase", "")
            if current_phase:
                # Double-check: any phase not yet fully done?
                phases = data.get("phases", {})
                if not phases:
                    # Empty phases dict but current_phase set = newly created = active
                    return True
                for phase_state in phases.values():
                    if isinstance(phase_state, dict) and phase_state.get("status") in ("pending", "in_progress", "complete"):
                        return True
        except (json.JSONDecodeError, OSError, ValueError):
            continue

    return False


def is_test_file(file_path: str) -> bool:
    """Check if a file path matches test file patterns."""
    for pattern in TEST_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def is_code_file(file_path: str) -> bool:
    """Check if a file is a code file (not config/docs)."""
    # Check ignore patterns first
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, file_path):
            return False

    # Check extension
    ext = Path(file_path).suffix.lower()
    return ext in CODE_EXTENSIONS


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_input = input_data.get("tool_input", {})

        file_path = tool_input.get("file_path", "")
        if not file_path:
            print(json.dumps({"continue": True}))
            return

        # Skip non-code files silently
        if not is_code_file(file_path):
            print(json.dumps({"continue": True}))
            return

        # Check for active crew project
        if not has_active_crew_project():
            print(json.dumps({"continue": True}))
            return

        # Load session state
        state = load_session_state()

        # If specialist already dispatched this session, no warning needed
        dispatches = state.get("specialist_dispatches", [])
        if dispatches:
            print(json.dumps({"continue": True}))
            return

        # Check if already warned this session
        if state.get("write_guard_warned", False):
            print(json.dumps({"continue": True}))
            return

        # Determine warning level
        if is_test_file(file_path):
            message = (
                "[Crew] Writing test files without wicked-qe dispatch. "
                "Test strategy and coverage are wicked-qe's domain — "
                "consider delegating via Task(subagent_type=\"wicked-qe:...\")."
            )
        else:
            message = (
                "[Crew] Writing implementation without specialist dispatch. "
                "Consider delegating via Task(subagent_type=\"...\") "
                "to route through the appropriate specialist."
            )

        # Mark as warned (one-time per session)
        state["write_guard_warned"] = True
        save_session_state(state)

        print(json.dumps({
            "continue": True,
            "systemMessage": message,
        }))

    except Exception:
        # Never block on errors
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
