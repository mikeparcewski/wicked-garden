#!/usr/bin/env python3
"""
_logger.py — Structured operational logging for wicked-garden hook scripts.

Writes one JSONL line per call to $TMPDIR/wicked-ops-{session_id}.jsonl.
Fail-silent: never raises, never crashes the caller.

Usage:
    from _logger import log

    log("bootstrap", "normal", "onboarding.status", ok=True, detail={"has_memories": True})
    log("smaht", "verbose", "prompt.routed", detail={"path": "fast", "turn": 1})
    log("post_tool", "debug", "hook.end", ms=1.23)

Level hierarchy: normal (0) < verbose (1) < debug (2)
Effective level is resolved from: WICKED_LOG_LEVEL env var > SessionState.log_level > "normal"
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Level constants
# ---------------------------------------------------------------------------

_LEVELS = {"normal": 0, "verbose": 1, "debug": 2}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_session_id() -> str:
    """Read and sanitize CLAUDE_SESSION_ID for use in filenames."""
    import re
    raw = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", raw)
    return safe or "unknown"


def _log_file(session_id: str) -> Path:
    """Return path to the ops JSONL log file for the given session."""
    tmpdir = os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()
    return Path(tmpdir) / f"wicked-ops-{session_id}.jsonl"


def _resolve_level() -> str:
    """Determine the effective log level.

    Priority order:
    1. WICKED_LOG_LEVEL environment variable
    2. SessionState.log_level (read directly from raw JSON — no import)
    3. Default: "normal"
    """
    # 1. Environment variable (highest priority)
    env = os.environ.get("WICKED_LOG_LEVEL", "").strip().lower()
    if env in _LEVELS:
        return env

    # 2. SessionState JSON file (avoid circular import: read raw JSON directly)
    try:
        import json as _json
        _sid = _get_session_id()
        _tmpdir = os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()
        _state_path = Path(_tmpdir) / f"wicked-garden-session-{_sid}.json"
        if _state_path.exists():
            _data = _json.loads(_state_path.read_text(encoding="utf-8"))
            _level = _data.get("log_level", "").strip().lower()
            if _level in _LEVELS:
                return _level
    except Exception:
        pass  # Fail open — use default

    # 3. Default
    return "normal"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log(
    domain: str,
    level: str,
    event: str,
    ok: bool = True,
    ms: float | None = None,
    detail: dict | None = None,
) -> None:
    """Write a structured log entry to the session ops JSONL file.

    Args:
        domain: Source domain, e.g. "bootstrap", "smaht", "kanban"
        level:  Log level — "normal", "verbose", or "debug"
        event:  Dot-separated event name, e.g. "onboarding.status"
        ok:     Outcome indicator (default True)
        ms:     Elapsed milliseconds, rounded to 2 decimal places (optional)
        detail: Arbitrary JSON-safe payload dict (optional)

    This function never raises. All exceptions are silently swallowed.
    """
    try:
        # Resolve effective level and filter
        effective_level = _resolve_level()
        event_rank = _LEVELS.get(level, 2)  # Unknown levels treated as debug (most permissive)
        effective_rank = _LEVELS.get(effective_level, 0)

        if event_rank > effective_rank:
            return  # Silently discard — event is more verbose than the threshold

        # Build the log entry
        session_id = _get_session_id()
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        ms_val = round(ms, 2) if ms is not None else None

        # Serialize detail safely
        detail_val: dict | None
        if detail is None:
            detail_val = None
        else:
            try:
                json.dumps(detail)  # Probe serializability
                detail_val = detail
            except (TypeError, ValueError):
                detail_val = {"_raw": str(detail)}

        entry = {
            "ts": ts,
            "session": session_id,
            "domain": domain,
            "level": level,
            "event": event,
            "ok": ok,
            "ms": ms_val,
            "detail": detail_val,
        }

        # Write one JSONL line — append mode, no fsync
        log_path = _log_file(session_id)
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # I/O errors are silently swallowed

    except Exception:
        pass  # Outer catch — logger must never crash the caller
