#!/usr/bin/env python3
"""
_session.py — Session state shared across hook script invocations.

Hook scripts run as separate processes, so they cannot share in-memory state.
This module persists a lightweight JSON state file keyed by CLAUDE_SESSION_ID
so all hooks within a session read/write a consistent view.

State file location:
    ${TMPDIR:-/tmp}/wicked-garden-session-{SESSION_ID}.json

Atomic writes: write to .tmp, then os.replace — prevents partial reads.

Usage (hook scripts):
    from _session import SessionState

    state = SessionState.load()
    state.turn_count += 1
    state.save()

    # Or update multiple fields at once:
    state.update(cp_available=True, cp_version="1.2.3")
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Session ID resolution
# ---------------------------------------------------------------------------

_SESSION_ID_ENV = "CLAUDE_SESSION_ID"
_FALLBACK_SESSION_ID = "default"

# Characters that could be used for path traversal — strip them from session IDs
_SAFE_ID_RE = None  # initialized lazily


def _get_session_id() -> str:
    """Read and sanitize the Claude session ID from the environment.

    Returns a safe string usable as a filename component.
    """
    import re

    raw = os.environ.get(_SESSION_ID_ENV, _FALLBACK_SESSION_ID)
    # Strip any path traversal or shell-special characters — keep only
    # alphanumerics, hyphens, and underscores.
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", raw)
    return safe or _FALLBACK_SESSION_ID


def _state_file_path() -> Path:
    """Return the path to the session state JSON file for the current session."""
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    session_id = _get_session_id()
    filename = f"wicked-garden-session-{session_id}.json"
    return Path(tmpdir) / filename


# ---------------------------------------------------------------------------
# SessionState dataclass
# ---------------------------------------------------------------------------


@dataclass
class SessionState:
    """Lightweight session state persisted across hook script invocations.

    All fields have safe defaults so a missing or partial state file never
    causes a hook to crash.

    Fields:
        cp_available:   True when the control plane health check passed at
                        session start.
        cp_version:     Reported control plane version string, or "".
        setup_complete: True when config.json has setup_complete == true.
        fallback_mode:  True when CP was unreachable and we are using local
                        file fallback for this session.
        active_project: Dict summary of the active crew project, or None.
        kanban_board:   Dict summary of the current kanban board, or None.
        agents_loaded:  Number of agents loaded (disk + CP overlay) at bootstrap.
        turn_count:     Number of user prompts in this session (incremented by
                        prompt_submit.py on each UserPromptSubmit hook).
    """

    cp_available: bool = False
    cp_version: str = ""
    setup_complete: bool = False
    fallback_mode: bool = False
    active_project: dict | None = None
    kanban_board: dict | None = None
    agents_loaded: int = 0
    turn_count: int = 0
    session_ended: bool = False
    cp_last_checked_at: float = 0.0

    # Kanban sync: maps Claude TaskCreate subjects → kanban task IDs.
    # Session-scoped (task IDs are ephemeral).
    kanban_sync: dict | None = None

    # One-time nudge flags (reset per session)
    task_suggest_shown: bool = False

    # Stale files accumulated this session (flushed to SM on demand)
    stale_files: list | None = None

    # QE change tracking nudge flag
    qe_nudged: bool = False

    # Failure counts per tool (for issue reporter threshold)
    failure_counts: dict | None = None

    # Queued issue records (pending_issues + mismatches)
    pending_issues: list | None = None

    # CP errors recorded by _control_plane.py for hook surfacing
    cp_errors: list | None = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "SessionState":
        """Load state from the session file.

        Returns a fresh default-valued SessionState if the file does not exist
        or contains invalid JSON — ensures hooks never crash on missing state.
        """
        path = _state_file_path()

        if not path.exists():
            return cls()

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            # Corrupted or unreadable state — return clean defaults
            return cls()

        # Build from dict; unknown keys are silently ignored so older state
        # files remain compatible with newer code that adds fields.
        return cls._from_dict(data)

    def save(self) -> None:
        """Atomically persist the current state to the session file."""
        path = _state_file_path()
        tmp_path = path.with_suffix(".tmp")

        data = asdict(self)

        try:
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp_path, path)
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to save session state: {exc}",
                file=sys.stderr,
            )

    def update(self, **kwargs: Any) -> None:
        """Update one or more fields and immediately save to disk.

        Only recognised field names are applied; unknown keys are silently
        dropped so callers cannot accidentally corrupt the state schema.

        Args:
            **kwargs: Field name -> new value pairs.
        """
        valid_fields = {f for f in self.__dataclass_fields__}
        for key, value in kwargs.items():
            if key in valid_fields:
                object.__setattr__(self, key, value)
            else:
                print(
                    f"[wicked-garden] SessionState.update: unknown field {key!r} ignored",
                    file=sys.stderr,
                )
        self.save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_dict(cls, data: dict) -> "SessionState":
        """Construct a SessionState from a dict, ignoring unknown keys."""
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Return a plain dict representation (JSON-safe)."""
        return asdict(self)

    def is_online(self) -> bool:
        """Convenience: True when CP is available and not in fallback mode."""
        return self.cp_available and not self.fallback_mode

    def mark_online(self, version: str) -> None:
        """Mark the session as having a live CP connection and save."""
        self.update(cp_available=True, cp_version=version, fallback_mode=False)

    def mark_offline(self, reason: str = "") -> None:
        """Mark the session as operating in offline fallback mode and save."""
        if reason:
            print(
                f"[wicked-garden] Offline mode: {reason}",
                file=sys.stderr,
            )
        self.update(cp_available=False, fallback_mode=True)

    def increment_turn(self) -> int:
        """Increment turn_count, persist, and return the new value."""
        self.turn_count += 1
        self.save()
        return self.turn_count

    # ------------------------------------------------------------------
    # Session file cleanup (called by stop.py)
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Remove the session state file at session end.

        Silently succeeds if the file does not exist.
        """
        path = _state_file_path()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to delete session state file: {exc}",
                file=sys.stderr,
            )
