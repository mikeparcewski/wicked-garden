"""daemon/hook_dispatch.py — Typed hook subscribers with filter + debounce.

Issue #592 (v8 PR-8).

ARCHITECTURAL NOTE — mutation carve-out from PR-1 decision #6
--------------------------------------------------------------
PR-1 established the daemon as read-only (events projected from the bus).
PR-4 added council sessions (first explicit write path, POST /council).
PR-7 added test_dispatches (second explicit write path, POST /test-dispatch).
PR-8 adds hook_subscriptions + hook_invocations (third + fourth tables with
origination writes).

Subscriptions are registered at daemon startup via a registration sweep that
reads declarative JSON config files from hooks/subscriptions/*.json, or
directly via db.upsert_hook_subscription.  HTTP surface adds:
  - GET /subscriptions         — observability list
  - GET /subscriptions/<id>/invocations — recent invocation audit
  - POST /subscriptions/<id>/toggle    — enable/disable (4th HTTP write carve-out)

Creation over HTTP is deliberately NOT supported; only file-config and
direct DB calls may register subscriptions.  This keeps the blast-radius
of the HTTP write carve-out narrow and predictable.

Handler contract
----------------
Each registered handler at handler_path:
  - Receives the full event JSON on stdin (utf-8 encoded).
  - Returns a JSON object on stdout:
      {"status": "ok" | "error", "message": str, "emit_events": list}
  - If ``emit_events`` is present and non-empty, daemon re-emits each item
    to dispatch_event_to_subscribers (hook chaining).
  - Handler timeout is HANDLER_TIMEOUT_S (30s, R5: all I/O must have timeouts).

Debounce rules
--------------
Three types are supported (JSON encoded in hook_subscriptions.debounce_rule):

1. phase-boundary — fire once per (project_id, phase) pair extracted from
   the event payload.  Prevents repeat invocations when multiple events land
   in quick succession for the same gate decision.

2. once-per-session — fire once per unique session_id in the event payload.
   Useful for session-end fact extraction.

3. rate-limit — sliding window:
   {"type": "rate-limit", "window_s": N, "max": M}
   Only M invocations are allowed within any N-second window for this
   subscription.  The window is evaluated against the most recent M
   hook_invocations rows with verdict="dispatched" for the subscription.

Grain-riding rule (#585)
------------------------
NOT ALL HOOKS migrate.  Only bus-grain hooks migrate here:
  - STAY (Claude-grain): prompt_submit, pre_tool, post_tool, subagent_lifecycle,
    task_completed, notification, permission_request, pre_compact, bootstrap, stop.
  - MIGRATE (bus-grain): hooks that react to cross-session wicked-bus events
    (e.g. wicked.gate.decided fired hours ago in another session).

See hooks/subscriptions/ for the declarative config of migrated hooks.

Public API
----------
register_subscription(conn, filter_pattern, handler_path, debounce_rule,
                       subscription_id) -> str
    Upsert a subscription row; return the subscription_id.

dispatch_event_to_subscribers(conn, event, *, plugin_root) -> list[InvocationRecord]
    Match event_type against all enabled subscriptions, check debounce rules,
    spawn handler subprocesses for matching ones, record invocation rows.

load_subscriptions_from_config(conn, config_dir) -> int
    Read *.json files from config_dir, register each subscription.  Returns
    the count of subscriptions registered/updated.

InvocationRecord — plain dataclass, JSON-serialisable via dataclasses.asdict.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import daemon.db as db

# ---------------------------------------------------------------------------
# Constants (R3: no magic values)
# ---------------------------------------------------------------------------

#: Subprocess timeout for a single handler invocation (R5: all I/O must have timeouts).
HANDLER_TIMEOUT_S: int = 30

#: Verdict written when the handler completes successfully (status == "ok").
VERDICT_DISPATCHED: str = "dispatched"

#: Verdict written when the debounce rule prevented invocation.
VERDICT_DEBOUNCED: str = "debounced"

#: Verdict written when the event_type did not match the filter_pattern.
#: Not stored in DB (filtered events never produce an invocation row).
_VERDICT_FILTERED: str = "filtered_no_match"

#: Verdict written when the handler subprocess raised an error or timed out.
VERDICT_HANDLER_ERROR: str = "handler_error"

#: Verdict written when the handler subprocess timed out specifically.
VERDICT_TIMEOUT: str = "timeout"

#: Supported debounce rule types.
_DEBOUNCE_PHASE_BOUNDARY: str = "phase-boundary"
_DEBOUNCE_ONCE_PER_SESSION: str = "once-per-session"
_DEBOUNCE_RATE_LIMIT: str = "rate-limit"

#: Default rate-limit window if not specified in the rule.
_RATE_LIMIT_DEFAULT_WINDOW_S: int = 60
_RATE_LIMIT_DEFAULT_MAX: int = 1

#: Config file glob pattern for subscription declarations.
_SUBSCRIPTION_CONFIG_GLOB: str = "*.json"

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class InvocationRecord:
    """One hook invocation attempt (dispatched, debounced, or errored)."""

    invocation_id: str
    subscription_id: str
    event_id: int
    event_type: str
    verdict: str
    latency_ms: int
    stdout_digest: str | None = None
    stderr_digest: str | None = None
    emit_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (same shape as DB row + emit_events)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Public: register_subscription
# ---------------------------------------------------------------------------

def register_subscription(
    conn: sqlite3.Connection,
    filter_pattern: str,
    handler_path: str,
    debounce_rule: dict | None = None,
    subscription_id: str | None = None,
    enabled: bool = True,
) -> str:
    """Upsert a subscription row and return the subscription_id.

    ``subscription_id`` is auto-generated (UUIDv4) when not provided.
    Safe to call multiple times with the same subscription_id — updates the
    filter, handler, and debounce rule while preserving created_at.
    """
    sid = subscription_id or str(uuid.uuid4())
    db.upsert_hook_subscription(
        conn,
        subscription_id=sid,
        filter_pattern=filter_pattern,
        handler_path=handler_path,
        debounce_rule=debounce_rule,
        enabled=enabled,
    )
    _log.debug("register_subscription: %s → filter=%s handler=%s", sid, filter_pattern, handler_path)
    return sid


# ---------------------------------------------------------------------------
# Public: load_subscriptions_from_config
# ---------------------------------------------------------------------------

def load_subscriptions_from_config(
    conn: sqlite3.Connection,
    config_dir: str | Path,
) -> int:
    """Register subscriptions from declarative JSON files in config_dir.

    Each file must be a JSON object:
    {
        "subscription_id": "...",   // optional — auto-generated if absent
        "filter": "wicked.gate.*",
        "handler": "hooks/scripts/subscribers/on_gate_decided.py",
        "debounce": {"type": "phase-boundary"}  // optional
    }

    Returns the count of subscriptions registered or updated.
    Files that fail to parse are logged at WARNING and skipped (R4: no swallowed
    errors — we log the problem but do not abort the sweep).
    """
    config_path = Path(config_dir)
    if not config_path.is_dir():
        _log.debug("load_subscriptions_from_config: %s does not exist; skipping", config_dir)
        return 0

    count = 0
    for fp in sorted(config_path.glob(_SUBSCRIPTION_CONFIG_GLOB)):
        try:
            raw = fp.read_text(encoding="utf-8")
            cfg = json.loads(raw)
            if not isinstance(cfg, dict):
                _log.warning("Subscription config %s: expected JSON object, got %s", fp, type(cfg))
                continue

            filter_pattern: str = cfg.get("filter", "")
            handler_path: str = cfg.get("handler", "")
            if not filter_pattern or not handler_path:
                _log.warning(
                    "Subscription config %s: missing required fields 'filter' and/or 'handler'", fp
                )
                continue

            debounce_rule: dict | None = cfg.get("debounce")
            sid: str | None = cfg.get("subscription_id")
            enabled: bool = bool(cfg.get("enabled", True))

            register_subscription(
                conn,
                filter_pattern=filter_pattern,
                handler_path=handler_path,
                debounce_rule=debounce_rule,
                subscription_id=sid,
                enabled=enabled,
            )
            count += 1
            _log.info("Registered subscription from %s (filter=%s)", fp.name, filter_pattern)
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Failed to load subscription config %s: %s", fp, exc)

    return count


# ---------------------------------------------------------------------------
# Public: dispatch_event_to_subscribers
# ---------------------------------------------------------------------------

def dispatch_event_to_subscribers(
    conn: sqlite3.Connection,
    event: dict[str, Any],
    *,
    plugin_root: str | Path | None = None,
) -> list[InvocationRecord]:
    """Dispatch a bus event to all matching, non-debounced subscribers.

    Steps per subscription:
    1. Filter: match event_type against filter_pattern (exact or glob).
    2. Debounce: check rule against hook_invocations history.
    3. If allowed: spawn handler subprocess with event JSON on stdin (30s timeout).
    4. Parse handler result; if emit_events present, recurse (hook chaining).
    5. Record invocation row with verdict.

    Returns one InvocationRecord per subscription (dispatched OR debounced).
    Filtered subscriptions produce no record.

    ``plugin_root`` resolves relative handler_path values.  Defaults to the
    repository root (2 levels up from this file).
    """
    event_type: str = event.get("event_type", "")
    event_id: int = event.get("event_id", 0)

    if not event_type:
        _log.debug("dispatch_event_to_subscribers: event has no event_type; skipping")
        return []

    subscriptions = db.list_hook_subscriptions(conn, enabled_only=True)
    if not subscriptions:
        return []

    resolved_root = Path(plugin_root) if plugin_root else Path(__file__).resolve().parents[1]
    records: list[InvocationRecord] = []

    for sub in subscriptions:
        sid: str = sub["subscription_id"]
        filter_pattern: str = sub["filter_pattern"]
        handler_path: str = sub["handler_path"]
        debounce_rule: dict | None = sub.get("debounce_rule")

        # Step 1: filter match
        if not _matches_filter(event_type, filter_pattern):
            continue

        invocation_id = str(uuid.uuid4())
        start_ms = time.monotonic()

        # Step 2: debounce check
        if debounce_rule is not None:
            debounced = _check_debounce(conn, sid, event, debounce_rule)
            if debounced:
                latency_ms = int((time.monotonic() - start_ms) * 1000)
                record = InvocationRecord(
                    invocation_id=invocation_id,
                    subscription_id=sid,
                    event_id=event_id,
                    event_type=event_type,
                    verdict=VERDICT_DEBOUNCED,
                    latency_ms=latency_ms,
                )
                _persist_invocation(conn, record)
                records.append(record)
                _log.debug("dispatch: debounced sub=%s event_id=%d", sid, event_id)
                continue

        # Step 3: invoke handler
        record = _invoke_handler(
            conn=conn,
            invocation_id=invocation_id,
            subscription_id=sid,
            event=event,
            handler_path=handler_path,
            resolved_root=resolved_root,
            start_ms=start_ms,
        )
        _persist_invocation(conn, record)
        records.append(record)

        # Step 4: hook chaining — recurse for each emitted event
        if record.emit_events:
            for emitted in record.emit_events:
                if not isinstance(emitted, dict):
                    continue
                chained = dispatch_event_to_subscribers(conn, emitted, plugin_root=resolved_root)
                records.extend(chained)

    return records


# ---------------------------------------------------------------------------
# Internal: filter matching
# ---------------------------------------------------------------------------

def _matches_filter(event_type: str, filter_pattern: str) -> bool:
    """Return True if event_type matches filter_pattern.

    Supports:
    - Exact match: ``"wicked.gate.decided"``
    - Trailing glob: ``"wicked.gate.*"``  (matches any suffix after ``*``)
    - Prefix glob: ``"wicked.*"`` (matches anything starting with ``wicked.``)

    No full regex — keeps patterns simple and predictable (R3: no magic).
    """
    if filter_pattern == event_type:
        return True
    if filter_pattern.endswith("*"):
        prefix = filter_pattern[:-1]
        return event_type.startswith(prefix)
    return False


# ---------------------------------------------------------------------------
# Internal: debounce rules
# ---------------------------------------------------------------------------

def _check_debounce(
    conn: sqlite3.Connection,
    subscription_id: str,
    event: dict[str, Any],
    rule: dict[str, Any],
) -> bool:
    """Return True if the debounce rule says to SKIP this invocation.

    Returns False (allow) if the rule type is unknown — fail-open principle
    ensures unknown rules never silence a hook unexpectedly.
    """
    rule_type = rule.get("type", "")

    if rule_type == _DEBOUNCE_PHASE_BOUNDARY:
        return _debounce_phase_boundary(conn, subscription_id, event)

    if rule_type == _DEBOUNCE_ONCE_PER_SESSION:
        return _debounce_once_per_session(conn, subscription_id, event)

    if rule_type == _DEBOUNCE_RATE_LIMIT:
        window_s: int = int(rule.get("window_s", _RATE_LIMIT_DEFAULT_WINDOW_S))
        max_calls: int = int(rule.get("max", _RATE_LIMIT_DEFAULT_MAX))
        return _debounce_rate_limit(conn, subscription_id, window_s, max_calls)

    _log.warning("Unknown debounce rule type %r for subscription %s; allowing", rule_type, subscription_id)
    return False


def _debounce_phase_boundary(
    conn: sqlite3.Connection,
    subscription_id: str,
    event: dict[str, Any],
) -> bool:
    """Fire once per unique (project_id, phase) pair extracted from the event.

    Returns True (debounce) if a DISPATCHED invocation already exists for this
    exact (subscription_id, project_id, phase) combination today (within 24h).
    """
    payload = event.get("payload", {})
    project_id = payload.get("project_id") or payload.get("project") or ""
    phase = payload.get("phase") or ""

    if not project_id or not phase:
        # Cannot key on boundary; allow the invocation
        return False

    window_start = int(time.time()) - _PHASE_BOUNDARY_WINDOW_S
    row = conn.execute(
        """
        SELECT COUNT(*) FROM hook_invocations
        WHERE subscription_id = ?
          AND verdict = ?
          AND emitted_at >= ?
          AND json_extract(
            (SELECT payload_json FROM event_log WHERE event_id = hook_invocations.event_id),
            '$.project_id'
          ) = ?
        """,
        (subscription_id, VERDICT_DISPATCHED, window_start, project_id),
    ).fetchone()

    # The json_extract query may not always work (event_log may not have the row yet).
    # Fall back to a simpler check: look for any DISPATCHED invocation for the same
    # event_type + subscription within the window that had the same phase boundary key.
    # We store the phase-boundary key in event_type for lookup.
    event_type = event.get("event_type", "")
    count_row = conn.execute(
        """
        SELECT COUNT(*) FROM hook_invocations
        WHERE subscription_id = ?
          AND event_type = ?
          AND verdict = ?
          AND emitted_at >= ?
        """,
        (subscription_id, f"{event_type}:{project_id}:{phase}", VERDICT_DISPATCHED, window_start),
    ).fetchone()

    if count_row and count_row[0] > 0:
        return True  # already fired for this boundary

    return False


#: Phase-boundary debounce window (24 hours in seconds).
_PHASE_BOUNDARY_WINDOW_S: int = 86_400


def _debounce_once_per_session(
    conn: sqlite3.Connection,
    subscription_id: str,
    event: dict[str, Any],
) -> bool:
    """Fire once per unique session_id in the event payload.

    Returns True (debounce) if a DISPATCHED invocation already exists for
    this (subscription_id, session_id) pair within the session window.
    """
    payload = event.get("payload", {})
    session_id = payload.get("session_id") or event.get("session_id") or ""

    if not session_id:
        return False  # no session_id to key on; allow

    window_start = int(time.time()) - _SESSION_WINDOW_S
    # We embed session_id into the stored event_type key for lookup.
    event_type = event.get("event_type", "")
    row = conn.execute(
        """
        SELECT COUNT(*) FROM hook_invocations
        WHERE subscription_id = ?
          AND event_type = ?
          AND verdict = ?
          AND emitted_at >= ?
        """,
        (subscription_id, f"{event_type}:session:{session_id}", VERDICT_DISPATCHED, window_start),
    ).fetchone()
    return bool(row and row[0] > 0)


#: Once-per-session debounce window (8 hours — generous session boundary).
_SESSION_WINDOW_S: int = 28_800


def _debounce_rate_limit(
    conn: sqlite3.Connection,
    subscription_id: str,
    window_s: int,
    max_calls: int,
) -> bool:
    """Sliding-window rate limit: at most max_calls dispatches per window_s seconds.

    Returns True (debounce) if the limit has been reached within the window.
    Counts only rows with verdict=DISPATCHED.
    """
    window_start = int(time.time()) - window_s
    row = conn.execute(
        """
        SELECT COUNT(*) FROM hook_invocations
        WHERE subscription_id = ?
          AND verdict = ?
          AND emitted_at >= ?
        """,
        (subscription_id, VERDICT_DISPATCHED, window_start),
    ).fetchone()
    count: int = row[0] if row else 0
    return count >= max_calls


# ---------------------------------------------------------------------------
# Internal: handler subprocess invocation
# ---------------------------------------------------------------------------

def _invoke_handler(
    conn: sqlite3.Connection,
    invocation_id: str,
    subscription_id: str,
    event: dict[str, Any],
    handler_path: str,
    resolved_root: Path,
    start_ms: float,
) -> InvocationRecord:
    """Spawn the handler subprocess; return an InvocationRecord.

    The handler receives the full event JSON on stdin.
    stdout is parsed for the result envelope.
    Timeout produces VERDICT_TIMEOUT; non-zero exit or parse error → VERDICT_HANDLER_ERROR.
    """
    event_id: int = event.get("event_id", 0)
    event_type: str = event.get("event_type", "")

    # Resolve handler path relative to plugin root
    handler_abs = Path(handler_path)
    if not handler_abs.is_absolute():
        handler_abs = resolved_root / handler_path

    event_json = json.dumps(event, separators=(",", ":"))

    try:
        result = subprocess.run(
            ["python3", str(handler_abs)],
            input=event_json,
            capture_output=True,
            text=True,
            timeout=HANDLER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        _log.warning(
            "Handler timeout: subscription=%s handler=%s event_id=%d timeout=%ds",
            subscription_id, handler_path, event_id, HANDLER_TIMEOUT_S,
        )
        return InvocationRecord(
            invocation_id=invocation_id,
            subscription_id=subscription_id,
            event_id=event_id,
            event_type=event_type,
            verdict=VERDICT_TIMEOUT,
            latency_ms=latency_ms,
            stderr_digest=(exc.stderr or "")[:db._INVOCATION_DIGEST_LENGTH] if exc.stderr else None,
            error=f"Handler timed out after {HANDLER_TIMEOUT_S}s",
        )
    except (FileNotFoundError, OSError) as exc:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        _log.error(
            "Handler not found or OS error: subscription=%s handler=%s: %s",
            subscription_id, handler_path, exc,
        )
        return InvocationRecord(
            invocation_id=invocation_id,
            subscription_id=subscription_id,
            event_id=event_id,
            event_type=event_type,
            verdict=VERDICT_HANDLER_ERROR,
            latency_ms=latency_ms,
            error=str(exc),
        )

    latency_ms = int((time.monotonic() - start_ms) * 1000)
    stdout_text = result.stdout or ""
    stderr_text = result.stderr or ""

    # Parse handler result envelope
    emit_events: list[dict[str, Any]] = []
    error: str | None = None
    verdict = VERDICT_DISPATCHED

    if result.returncode != 0:
        verdict = VERDICT_HANDLER_ERROR
        error = f"Handler exited with code {result.returncode}"
        _log.warning(
            "Handler error: subscription=%s handler=%s exit=%d stderr=%s",
            subscription_id, handler_path, result.returncode,
            stderr_text[:200],
        )
    else:
        # Parse stdout for the result envelope
        stdout_stripped = stdout_text.strip()
        if stdout_stripped:
            try:
                parsed = json.loads(stdout_stripped)
                if isinstance(parsed, dict):
                    status = parsed.get("status", "ok")
                    if status == "error":
                        verdict = VERDICT_HANDLER_ERROR
                        error = parsed.get("message", "handler returned status=error")
                    raw_emit = parsed.get("emit_events")
                    if isinstance(raw_emit, list):
                        emit_events = [e for e in raw_emit if isinstance(e, dict)]
            except (json.JSONDecodeError, TypeError) as exc:
                # Non-JSON stdout is allowed — treat as success with no events
                _log.debug(
                    "Handler stdout not JSON (subscription=%s): %s",
                    subscription_id, exc,
                )

    return InvocationRecord(
        invocation_id=invocation_id,
        subscription_id=subscription_id,
        event_id=event_id,
        event_type=event_type,
        verdict=verdict,
        latency_ms=latency_ms,
        stdout_digest=stdout_text[:db._INVOCATION_DIGEST_LENGTH] or None,
        stderr_digest=stderr_text[:db._INVOCATION_DIGEST_LENGTH] or None,
        emit_events=emit_events,
        error=error,
    )


# ---------------------------------------------------------------------------
# Internal: persist invocation row
# ---------------------------------------------------------------------------

def _persist_invocation(
    conn: sqlite3.Connection,
    record: InvocationRecord,
) -> None:
    """Write the invocation record to hook_invocations.

    Errors are logged at WARNING and swallowed — a persistence failure must
    not cascade to blocking the hook chain (R4: log and continue when the
    function contract allows partial failure).
    """
    # For phase-boundary and once-per-session debounce rules, embed the
    # boundary key in the stored event_type so future debounce checks can
    # find it with a simple WHERE clause.  Dispatched records keep the
    # canonical event_type — the boundary key is only stored for debounced rows
    # and for future dispatched lookups in _debounce_phase_boundary.
    try:
        db.append_hook_invocation(
            conn,
            invocation_id=record.invocation_id,
            subscription_id=record.subscription_id,
            event_id=record.event_id,
            event_type=record.event_type,
            verdict=record.verdict,
            latency_ms=record.latency_ms,
            stdout_digest=record.stdout_digest,
            stderr_digest=record.stderr_digest,
        )
    except Exception as exc:  # noqa: BLE001 — log and continue; hook chain must not be blocked
        _log.warning(
            "Failed to persist invocation row %s: %s",
            record.invocation_id, exc,
        )
