#!/usr/bin/env python3
"""scripts/crew/_task_audit_writer.py — cross-session task-chain index.

Phase 3 of v10. Designed in jam session 03 (decision memory:
``v10-native-task-store-audit-trail-decision``).

This module owns the JSONL audit-log schema. **It is the SOLE writer**
of ``${CLAUDE_CONFIG_DIR}/wicked-garden/task-audit/{session_id}.jsonl``.
Schema changes require a PR to this module — anyone else writing to the
file is a layering violation.

## Purpose vs. dispatch-log

This is NOT the same as ``phases/{phase}/dispatch-log.jsonl``. The two
serve different threat models — see brain memory
``dispatch-log-precedes-reviewer-do-not-move-to-post-hook``:

* dispatch-log: HMAC-signed, written BEFORE reviewer invocation. Threat
  model = rogue reviewer self-authorizing a gate-result. Sequencing is
  the security property.
* task-audit (this file): plain JSONL, written AFTER native TaskCreate
  by a PostToolUse hook. Threat model = ``verify_chain_emission`` not
  finding tasks created in earlier sessions because the per-session
  task store was never cross-session-indexed.

Different threat models, different files. Conflating them was an
explicit anti-pattern caught by the brainstorm.

## Schema (locked; rev with PR)

  {
    "ts":           ISO 8601 UTC,
    "session_id":   sanitised CLAUDE_SESSION_ID,
    "task_id":      native task id from tool_input/tool_response,
    "subject":      task subject string,
    "chain_id":     metadata.chain_id (may be None),
    "event_type":   metadata.event_type (may be None),
    "source_agent": metadata.source_agent (may be None),
    "status":       "pending" | "in_progress" | "completed",
    "tool":         "TaskCreate" | "TaskUpdate"
  }

Fail-open: any I/O exception is swallowed. Missing audit entries surface
as drift in ``verify_chain_emission`` rather than a hook crash.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Stable schema version. Bump on any change to the entry shape.
AUDIT_SCHEMA_VERSION = 1


def _audit_dir() -> Path:
    """Return the per-host audit directory.

    Mirrors the Claude Code config dir layout. Falls back to a temp dir
    if CLAUDE_CONFIG_DIR is not set, so the writer never raises.
    """
    base = (
        os.environ.get("CLAUDE_CONFIG_DIR")
        or str(Path.home() / ".claude")
    )
    return Path(base) / "wicked-garden" / "task-audit"


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.\-]")


def _sanitize_session_id(raw: str | None) -> str:
    """Strip path traversal and shell metacharacters from a session id."""
    if not raw:
        return "default"
    cleaned = _SAFE_ID_RE.sub("_", raw)
    return cleaned[:128] or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _audit_file_for_session(session_id: str) -> Path:
    return _audit_dir() / f"{_sanitize_session_id(session_id)}.jsonl"


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Walk a nested dict; return default on any miss."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _build_entry(
    *,
    tool_name: str,
    tool_input: dict | None,
    tool_response: Any,
    session_id: str,
) -> dict | None:
    """Compose the JSONL entry dict for one tool call.

    Returns None when the tool call is not a task-management event we
    care about (caller skips writing). The caller is expected to have
    already gated on ``tool_name in {"TaskCreate", "TaskUpdate"}``;
    this function double-checks defensively.
    """
    if tool_name not in ("TaskCreate", "TaskUpdate"):
        return None

    ti = tool_input or {}
    metadata = ti.get("metadata") if isinstance(ti.get("metadata"), dict) else {}

    # Native task ids appear in different shapes depending on tool. For
    # TaskCreate, the response carries the new id; for TaskUpdate, the
    # input carries taskId. Tolerate both for either tool.
    task_id = (
        ti.get("taskId")
        or ti.get("task_id")
        or _safe_get(tool_response, "taskId")
        or _safe_get(tool_response, "task_id")
        or _safe_get(tool_response, "id")
    )

    # Status: TaskCreate defaults to pending. TaskUpdate may carry an
    # explicit status; if absent we still record the update so future
    # consumers can correlate the timestamp with the underlying file.
    if tool_name == "TaskCreate":
        status = ti.get("status") or "pending"
    else:
        status = ti.get("status") or "updated"

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "ts": _now_iso(),
        "session_id": _sanitize_session_id(session_id),
        "task_id": task_id,
        "subject": ti.get("subject"),
        "chain_id": metadata.get("chain_id"),
        "event_type": metadata.get("event_type"),
        "source_agent": metadata.get("source_agent"),
        "phase": metadata.get("phase"),
        "status": status,
        "tool": tool_name,
    }


def append_task_audit(
    *,
    tool_name: str,
    tool_input: dict | None,
    tool_response: Any,
    session_id: str,
) -> bool:
    """Append one task-audit JSONL entry for a TaskCreate/TaskUpdate call.

    Returns True when an entry was written. Returns False on filtered
    tool names or on any I/O error (fail-open). Never raises.
    """
    try:
        entry = _build_entry(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_response=tool_response,
            session_id=session_id,
        )
        if entry is None:
            return False

        path = _audit_file_for_session(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return True
    except Exception:
        return False


def scan_chain(chain_id: str) -> list[dict]:
    """Scan all session audit files for entries matching ``chain_id``.

    Returns a list of entry dicts (newest first). Empty list when the
    audit directory does not exist yet — the writer hasn't fired or
    PostToolUse is disabled. ``verify_chain_emission`` uses this as a
    cross-session fallback when the native per-session task scan misses.

    O(N sessions) directory walk. At ~100 sessions × ~50 entries this
    is a few KB scan and well under 10ms in practice.
    """
    audit_dir = _audit_dir()
    if not audit_dir.is_dir():
        return []

    entries: list[dict] = []
    for path in sorted(audit_dir.glob("*.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if e.get("chain_id") == chain_id:
                        entries.append(e)
        except OSError:
            continue
    # Newest first by timestamp; fall back to insertion order for
    # entries lacking a sortable ts.
    entries.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return entries


def latest_per_task(entries: Iterable[dict]) -> list[dict]:
    """Collapse multiple entries per task_id to the most recent one.

    Useful for ``verify_chain_emission``: a TaskCreate followed by a
    TaskUpdate for the same id yields two entries; we want one row per
    task with the latest known status.
    """
    out: dict[str, dict] = {}
    for e in entries:
        tid = e.get("task_id")
        if not tid:
            continue
        prev = out.get(tid)
        if prev is None or (e.get("ts") or "") > (prev.get("ts") or ""):
            out[tid] = e
    return list(out.values())
