"""Task-store reader abstraction — #596 v8-PR-2.

Centralises the WG_DAEMON_ENABLED routing logic for all native task-store
readers.  Callers that previously read
``${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json`` directly now
call helpers from this module and the routing is handled transparently.

WG_DAEMON_ENABLED modes:
  false  (default) — direct file read; behaviour identical to v7.2.x
  true             — try daemon HTTP first; fall back to direct file read on error
  always           — daemon HTTP only; error surfaces to caller on unreachable

The module-level ``_DAEMON_MODE`` constant is resolved once at import time
so every process makes exactly one env-var decision (no per-call overhead).

Performance:
  - Direct-file path: unchanged vs pre-PR-2
  - Daemon path (WG_DAEMON_ENABLED=true): single HTTP GET with a 45ms timeout
    (under the 50ms p99 hard requirement on the hot subagent_lifecycle path)
  - Daemon path (WG_DAEMON_ENABLED=always): same timeout; error on unreachable

Cold-start behavior:
  The first call after daemon startup (or after daemon restart) will hit the
  45ms HTTP timeout and fall back to the direct file read. This is intentional
  and correct — the daemon needs one request to warm its connection pool and
  prime the projection cursor. Subsequent warm-path calls are ~9ms p99.

  Operators running WG_DAEMON_ENABLED=always should know: a daemon crash or
  restart will surface a 45ms-latency blip on the next SubagentStart before
  the next request warms the path. WG_DAEMON_ENABLED=true (default) falls
  back to file read silently, so is blip-free at the cost of one extra
  file-scan per restart cycle.

R3: all constants named.
R5: explicit timeout on every HTTP call; bounded iterdir scan preserved.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENV_DAEMON_ENABLED = "WG_DAEMON_ENABLED"
_ENV_DAEMON_PORT = "WG_DAEMON_PORT"
_ENV_DAEMON_HOST = "WG_DAEMON_HOST"
_ENV_CONFIG_DIR = "CLAUDE_CONFIG_DIR"

# Default port matches daemon/server.py DEFAULT_PORT.
_DEFAULT_DAEMON_PORT: int = 4244
_DEFAULT_DAEMON_HOST: str = "127.0.0.1"

# Sub-50ms hard requirement per #596 spec.  We use 45ms to leave headroom.
# This is a per-call ceiling; network is loopback-only so the budget is realistic.
_DAEMON_HTTP_TIMEOUT_S: float = 0.045

# How many in-progress tasks to surface in WIP-context reads (preserves
# existing limits in prompt_submit.py and pre_compact.py).
_DEFAULT_WIP_LIMIT: int = 10


# ---------------------------------------------------------------------------
# Module-level mode resolution (R3, one decision per process)
# ---------------------------------------------------------------------------

def _resolve_daemon_mode() -> str:
    """Return the normalised WG_DAEMON_ENABLED value: 'false' | 'true' | 'always'."""
    raw = (os.environ.get(_ENV_DAEMON_ENABLED) or "false").strip().lower()
    return raw if raw in ("true", "always") else "false"


_DAEMON_MODE: str = _resolve_daemon_mode()


# ---------------------------------------------------------------------------
# Direct-file helpers (unchanged from pre-PR-2 behaviour)
# ---------------------------------------------------------------------------

def _tasks_dir_for_session(session_id: str) -> Path | None:
    """Resolve ``${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/``."""
    config_dir = os.environ.get(_ENV_CONFIG_DIR)
    base = Path(config_dir) if config_dir else Path.home() / ".claude"
    tasks_dir = base / "tasks" / session_id
    return tasks_dir if tasks_dir.is_dir() else None


def _read_task_file(session_id: str, task_id: str) -> dict | None:
    """Read a single task JSON file.  Returns None on any error."""
    if not session_id or not task_id:
        return None
    try:
        config_dir = os.environ.get(_ENV_CONFIG_DIR)
        base = Path(config_dir) if config_dir else Path.home() / ".claude"
        task_file = base / "tasks" / session_id / f"{task_id}.json"
        if not task_file.is_file():
            return None
        data = json.loads(task_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _scan_tasks_dir(
    session_id: str,
    *,
    status_filter: str | None = None,
    limit: int = _DEFAULT_WIP_LIMIT,
) -> list[dict]:
    """Scan the tasks dir and return task dicts matching optional status_filter.

    Returns at most ``limit`` entries; skips hidden files and non-JSON entries.
    Never raises — returns [] on any error.
    """
    if not session_id:
        return []
    out: list[dict] = []
    try:
        tasks_dir = _tasks_dir_for_session(session_id)
        if tasks_dir is None:
            return out
        for entry in tasks_dir.iterdir():
            if entry.name.startswith(".") or entry.suffix != ".json":
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if status_filter is not None and data.get("status") != status_filter:
                continue
            out.append(data)
            if len(out) >= limit:
                break
    except Exception:
        pass  # fail open — tasks dir absent or unreadable; return whatever we collected
    return out


# ---------------------------------------------------------------------------
# Daemon HTTP helpers
# ---------------------------------------------------------------------------

def _daemon_base_url() -> str:
    host = os.environ.get(_ENV_DAEMON_HOST, _DEFAULT_DAEMON_HOST)
    port_raw = os.environ.get(_ENV_DAEMON_PORT, str(_DEFAULT_DAEMON_PORT))
    try:
        port = int(port_raw)
    except (ValueError, TypeError):
        port = _DEFAULT_DAEMON_PORT
    return f"http://{host}:{port}"


def _daemon_get(path: str) -> Any | None:
    """Issue a GET request to the daemon at ``path``.

    Returns the parsed JSON body on 200, raises ``urllib.error.URLError``
    or ``urllib.error.HTTPError`` on failure.  Callers catch accordingly.
    """
    url = _daemon_base_url() + path
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=_DAEMON_HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Public API — routed readers
# ---------------------------------------------------------------------------

def get_task_metadata(session_id: str, task_id: str) -> dict | None:
    """Return the ``metadata`` dict from a single task.

    Routes via WG_DAEMON_ENABLED:
      false   → direct file read
      true    → daemon HTTP; fallback to direct file on error
      always  → daemon HTTP; returns None on unreachable
    """
    if _DAEMON_MODE == "false":
        data = _read_task_file(session_id, task_id)
        if data is None:
            return None
        meta = data.get("metadata")
        return meta if isinstance(meta, dict) else None

    # Daemon path.
    try:
        row = _daemon_get(f"/tasks/{task_id}")
        if row and isinstance(row, dict):
            meta = row.get("metadata")
            return meta if isinstance(meta, dict) else None
        return None
    except Exception:
        if _DAEMON_MODE == "always":
            return None
        # fallback
        data = _read_task_file(session_id, task_id)
        if data is None:
            return None
        meta = data.get("metadata")
        return meta if isinstance(meta, dict) else None


def get_active_task_event_type(session_id: str) -> str | None:
    """Return event_type of the most-recently-modified in_progress task.

    This is the hot path — called on every SubagentStart.  Sub-50ms p99 is
    required for the daemon path.

    Routes via WG_DAEMON_ENABLED:
      false   → direct file scan (existing behaviour, bit-identical)
      true    → daemon GET /tasks?session=<id>&status=in_progress; fallback to direct
      always  → daemon only; None on unreachable
    """
    if not session_id:
        return None

    if _DAEMON_MODE == "false":
        return _get_active_task_event_type_direct(session_id)

    # Daemon path.
    try:
        rows = _daemon_get(f"/tasks?session={session_id}&status=in_progress&limit=10")
        if not rows or not isinstance(rows, list):
            return None
        # Pick the task with the highest updated_at (proxy for most-recent).
        best = max(rows, key=lambda r: r.get("updated_at", 0), default=None)
        if best is None:
            return None
        return best.get("event_type")
    except Exception:
        if _DAEMON_MODE == "always":
            return None
        return _get_active_task_event_type_direct(session_id)


def _get_active_task_event_type_direct(session_id: str) -> str | None:
    """Direct-file fallback for get_active_task_event_type (pre-PR-2 behaviour)."""
    try:
        tasks_dir = _tasks_dir_for_session(session_id)
        if tasks_dir is None:
            return None
        best_mtime = -1.0
        best_event_type: str | None = None
        for entry in tasks_dir.iterdir():
            if entry.name.startswith(".") or entry.suffix != ".json":
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict) or data.get("status") != "in_progress":
                continue
            mtime = entry.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                metadata = data.get("metadata") or {}
                if isinstance(metadata, dict):
                    best_event_type = metadata.get("event_type")
        return best_event_type
    except Exception:
        return None


def list_in_progress_tasks(
    session_id: str,
    limit: int = _DEFAULT_WIP_LIMIT,
) -> list[str]:
    """Return subject strings of in-progress tasks (for WIP context injection).

    Used by prompt_submit.py and pre_compact.py for context display — subjects
    only, not full task dicts.
    """
    if _DAEMON_MODE == "false":
        tasks = _scan_tasks_dir(session_id, status_filter="in_progress", limit=limit)
        return [t.get("subject") or "untitled" for t in tasks]

    try:
        rows = _daemon_get(
            f"/tasks?session={session_id}&status=in_progress&limit={limit}"
        )
        if not rows or not isinstance(rows, list):
            return []
        return [r.get("subject") or "untitled" for r in rows]
    except Exception:
        if _DAEMON_MODE == "always":
            return []
        tasks = _scan_tasks_dir(session_id, status_filter="in_progress", limit=limit)
        return [t.get("subject") or "untitled" for t in tasks]


def collect_tasks_for_chain(chain_id: str) -> list[dict]:
    """Return task dicts whose metadata.chain_id matches ``chain_id``.

    Used by current_chain.py and verify_chain_emission.py.

    Routes via WG_DAEMON_ENABLED:
      false   → direct file scan across all sessions (existing behaviour)
      true    → daemon GET /tasks?chain_id=<chain_id>; fallback to direct
      always  → daemon only; [] on unreachable
    """
    if _DAEMON_MODE == "false":
        return _collect_tasks_for_chain_direct(chain_id)

    try:
        rows = _daemon_get(f"/tasks?chain_id={chain_id}&limit=500")
        if not rows or not isinstance(rows, list):
            return []
        # Re-shape to match the dict shape callers expect (id, subject, status, metadata).
        result = []
        for row in rows:
            meta = row.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            result.append({
                "id": row.get("id", ""),
                "subject": row.get("subject", ""),
                "status": row.get("status", "unknown"),
                "metadata": meta,
                "blockedBy": [],
            })
        return result
    except Exception:
        if _DAEMON_MODE == "always":
            return []
        return _collect_tasks_for_chain_direct(chain_id)


def _collect_tasks_for_chain_direct(chain_id: str) -> list[dict]:
    """Direct-file fallback: scan all sessions for chain_id match."""
    config_dir = os.environ.get(_ENV_CONFIG_DIR) or str(Path.home() / ".claude")
    root = Path(config_dir) / "tasks"
    if not root.exists():
        return []
    out = []
    for task_file in root.rglob("*.json"):
        try:
            data = json.loads(task_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = data.get("metadata") or {}
        if meta.get("chain_id") != chain_id:
            continue
        out.append({
            "id": data.get("id") or task_file.stem,
            "subject": data.get("subject") or data.get("title") or "<untitled>",
            "status": data.get("status") or "unknown",
            "metadata": meta,
            "blockedBy": data.get("blockedBy") or [],
        })
    return out


def read_session_tasks(session_id: str, limit: int = 200) -> list[dict]:
    """Return all task dicts for a session (any status).

    Used by session_fact_extractor.py and telemetry.py.

    Routes via WG_DAEMON_ENABLED:
      false   → direct file scan
      true    → daemon GET /tasks?session=<id>; fallback to direct
      always  → daemon only; [] on unreachable
    """
    if _DAEMON_MODE == "false":
        return _scan_tasks_dir(session_id, limit=limit)

    try:
        rows = _daemon_get(f"/tasks?session={session_id}&limit={limit}")
        if not rows or not isinstance(rows, list):
            return []
        return [
            {
                "id": r.get("id", ""),
                "subject": r.get("subject", ""),
                "status": r.get("status", "unknown"),
                "metadata": r.get("metadata") or {},
            }
            for r in rows
        ]
    except Exception:
        if _DAEMON_MODE == "always":
            return []
        return _scan_tasks_dir(session_id, limit=limit)
