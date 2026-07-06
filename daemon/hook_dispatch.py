"""
hook_dispatch.py — Hook dispatcher for the wicked-garden daemon.

Routes wicked-bus events to registered garden hooks. Hooks are shell scripts or
Python files in the garden's ``hooks/`` directory. Matched by filename prefix
convention::

    on-{event_type_with_dots_replaced_by_dashes}.*

Examples:
    - ``on-wicked-garden-skill-installed.sh``
    - ``on-wicked-council-voted.py``

Execution:
    - ``.py`` hooks are invoked with the active Python interpreter.
    - All other hooks (shell scripts, executables) are invoked directly.
    - The event payload is passed as a JSON string via the ``WICKED_EVENT_PAYLOAD``
      environment variable, and also as the first positional argument.
    - Hook stdout/stderr is captured and logged at DEBUG level.
    - Hook failures are logged but never propagate — graceful degradation.

Usage::

    from daemon.hook_dispatch import HookDispatcher

    dispatcher = HookDispatcher(db_conn, hooks_dir=Path("hooks"))
    dispatcher.dispatch("wicked.garden.skill.installed", {"skill": "foo"})
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from daemon._internal import generate_id, now_iso
from daemon.db import get_write_lock

logger = logging.getLogger("wicked-garden.daemon.hook_dispatch")

_HOOK_TIMEOUT_S = 30


def _event_type_to_prefix(event_type: str) -> str:
    """Convert ``wicked.garden.skill.installed`` → ``on-wicked-garden-skill-installed``."""
    return "on-" + event_type.replace(".", "-")


class HookDispatcher:
    """Finds and executes garden hooks for incoming events.

    Args:
        db_conn: Open sqlite3 connection (check_same_thread=False).
        hooks_dir: Path to the garden's hooks directory. May not exist yet;
                   that is not an error.
    """

    def __init__(self, db_conn: sqlite3.Connection, hooks_dir: Path) -> None:
        self._conn = db_conn
        self._hooks_dir = Path(hooks_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(self, event_type: str, payload: dict[str, Any]) -> list[str]:
        """Find and execute matching hooks for an event.

        Args:
            event_type: The event type string (e.g. ``wicked.garden.skill.installed``).
            payload: The event payload dict.

        Returns:
            List of hook file names that were dispatched (empty if none found).
        """
        hooks = self._find_hooks(event_type)
        if not hooks:
            logger.debug("No hooks found for event %s", event_type)
            return []

        dispatched: list[str] = []
        for hook_path in hooks:
            success = self._execute_hook(hook_path, event_type, payload)
            self._record_execution(hook_path, event_type, payload, success)
            if success:
                dispatched.append(hook_path.name)

        return dispatched

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_hooks(self, event_type: str) -> list[Path]:
        """Return all hook files that match the event type prefix convention."""
        if not self._hooks_dir.is_dir():
            return []

        prefix = _event_type_to_prefix(event_type)
        matches: list[Path] = []

        for candidate in sorted(self._hooks_dir.iterdir()):
            if candidate.is_file() and candidate.stem == prefix:
                matches.append(candidate)
            elif candidate.is_file() and candidate.name.startswith(prefix + "."):
                # e.g. on-wicked-garden-skill-installed.sh
                matches.append(candidate)

        return matches

    def _execute_hook(
        self,
        hook_path: Path,
        event_type: str,
        payload: dict[str, Any],
    ) -> bool:
        """Execute a single hook file. Returns True on success, False on failure."""
        payload_str = json.dumps(payload, default=str)
        env = {**os.environ, "WICKED_EVENT_PAYLOAD": payload_str, "WICKED_EVENT_TYPE": event_type}

        if hook_path.suffix == ".py":
            cmd = [sys.executable, str(hook_path), payload_str]
        else:
            cmd = [str(hook_path), payload_str]

        logger.debug("Dispatching hook %s for event %s", hook_path.name, event_type)
        try:
            result = subprocess.run(
                cmd,
                timeout=_HOOK_TIMEOUT_S,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.stdout:
                logger.debug("Hook %s stdout: %s", hook_path.name, result.stdout.strip())
            if result.stderr:
                logger.debug("Hook %s stderr: %s", hook_path.name, result.stderr.strip())

            if result.returncode != 0:
                logger.warning(
                    "Hook %s exited %d for event %s",
                    hook_path.name, result.returncode, event_type,
                )
                return False
            return True
        except PermissionError as exc:
            logger.warning("Hook %s not executable: %s", hook_path.name, exc)
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Hook %s timed out after %ds", hook_path.name, _HOOK_TIMEOUT_S)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Hook %s raised: %s", hook_path.name, exc, exc_info=True)
            return False

    def _record_execution(
        self,
        hook_path: Path,
        event_type: str,
        payload: dict[str, Any],
        success: bool,
    ) -> None:
        """Persist hook execution record to the hitl_prompts table (reused as audit log)."""
        try:
            record_id = generate_id()
            status = "completed" if success else "failed"
            prompt_text = f"hook:{hook_path.name} event:{event_type}"
            with get_write_lock():
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO hitl_prompts
                        (id, session_id, prompt, status, created_at, responded_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (record_id, None, prompt_text, status, now_iso(), now_iso()),
                )
                self._conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to record hook execution: %s", exc)
