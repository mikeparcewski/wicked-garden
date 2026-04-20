#!/usr/bin/env python3
"""
_bus.py — wicked-bus integration shim for wicked-garden.

Fire-and-forget event emission + poll-on-invoke consumption.
Bus unavailable = no-op. Never blocks the caller. Never raises.

Usage:
    from _bus import emit_event, poll_pending, BUS_EVENT_MAP

    # Emit (fire-and-forget, returns immediately)
    emit_event("wicked.phase.transitioned", {
        "project_id": "abc", "phase_from": "clarify", "phase_to": "design",
    }, chain_id="abc123.root")

    # Poll (returns list of events, acks after processing)
    events = poll_pending(event_type_prefix="wicked.gate.")
"""

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("wicked-garden.bus")

# ---------------------------------------------------------------------------
# Static event catalog — Phase 1 events only (those with wired consumers).
# New events are added here when their emit points + consumers ship.
# ---------------------------------------------------------------------------

BUS_EVENT_MAP: Dict[str, Dict[str, str]] = {
    # Crew domain — phase_manager.py + propose-process facilitator skill
    "wicked.project.created": {
        "domain": "wicked-garden",
        "subdomain": "crew.project",
        "description": "New crew project created with complexity scoring",
    },
    "wicked.project.completed": {
        "domain": "wicked-garden",
        "subdomain": "crew.project",
        "description": "Crew project completed (final phase approved)",
    },
    "wicked.project.complexity_scored": {
        "domain": "wicked-garden",
        "subdomain": "crew.scoring",
        "description": "Complexity score computed for a project",
    },
    "wicked.phase.transitioned": {
        "domain": "wicked-garden",
        "subdomain": "crew.phase",
        "description": "Phase approved and advanced to next",
    },
    "wicked.gate.decided": {
        "domain": "wicked-garden",
        "subdomain": "crew.gate",
        "description": "Gate returned APPROVE, CONDITIONAL, or REJECT",
    },
    "wicked.gate.blocked": {
        "domain": "wicked-garden",
        "subdomain": "crew.gate",
        "description": "Gate returned REJECT — phase advancement blocked",
    },
    "wicked.rework.triggered": {
        "domain": "wicked-garden",
        "subdomain": "crew.rework",
        "description": "Rework initiated after gate REJECT or CONDITIONAL",
    },
    # Jam domain — jam.py
    "wicked.session.started": {
        "domain": "wicked-garden",
        "subdomain": "jam.session",
        "description": "Brainstorm or council session started",
    },
    "wicked.session.synthesized": {
        "domain": "wicked-garden",
        "subdomain": "jam.session",
        "description": "Session synthesis completed",
    },
    "wicked.session.synthesis_ready": {
        "domain": "wicked-garden",
        "subdomain": "jam.session",
        "description": "All expected Round 1 personas contributed or timeout elapsed — facilitator may synthesize",
    },
    "wicked.council.voted": {
        "domain": "wicked-garden",
        "subdomain": "jam.council",
        "description": "Council evaluation completed with model votes",
    },
    "wicked.persona.contributed": {
        "domain": "wicked-garden",
        "subdomain": "jam.persona",
        "description": "Persona contributed a perspective in a brainstorm round",
    },
    # QE domain
    "wicked.scenario.run": {
        "domain": "wicked-garden",
        "subdomain": "qe.scenario",
        "description": "Test scenario executed with pass/fail result",
    },
    "wicked.coverage.changed": {
        "domain": "wicked-garden",
        "subdomain": "qe.coverage",
        "description": "Test coverage metrics changed",
    },
    # Platform domain
    "wicked.security.finding_raised": {
        "domain": "wicked-garden",
        "subdomain": "platform.security",
        "description": "Security review raised a finding",
    },
    "wicked.guard.findings": {
        "domain": "wicked-garden",
        "subdomain": "platform.guard",
        "description": "Autonomous session-close guard pipeline surfaced findings (Issue #448)",
    },
    "wicked.compliance.passed": {
        "domain": "wicked-garden",
        "subdomain": "platform.compliance",
        "description": "Compliance check passed for a framework",
    },
    "wicked.compliance.failed": {
        "domain": "wicked-garden",
        "subdomain": "platform.compliance",
        "description": "Compliance check failed for a framework",
    },
    # Delivery domain
    "wicked.rollout.decided": {
        "domain": "wicked-garden",
        "subdomain": "delivery.rollout",
        "description": "Rollout go/no-go decision made",
    },
    "wicked.experiment.concluded": {
        "domain": "wicked-garden",
        "subdomain": "delivery.experiment",
        "description": "A/B experiment concluded with results",
    },
    # Auto-advance audit event
    "wicked.phase.auto_advanced": {
        "domain": "wicked-garden",
        "subdomain": "crew.phase",
        "description": "Phase auto-advanced for low-complexity project (audit trail)",
    },
    # Yolo scope-increase revoke — emitted by _apply_scope_increase_revoke when
    # an augment/re-tier-up mutation flips yolo_approved_by_user to False.
    "wicked.crew.yolo_revoked": {
        "domain": "wicked-garden",
        "subdomain": "crew.yolo",
        "description": "Yolo auto-approval revoked due to scope-increase mutation (audit + observability)",
    },
    # Smaht domain — fact_extractor.py → brain auto-memorize subscriber
    "wicked.fact.extracted": {
        "domain": "smaht",
        "subdomain": "facts",
        "description": "Structured fact extracted from conversation (consumed by wicked-brain auto-memorize)",
    },
    # wicked-testing integration — verdict events (#549, AC-25)
    "wicked.verdict.recorded": {
        "domain": "wicked-testing",
        "subdomain": "gate.verdict",
        "description": "wicked-testing reviewer recorded a gate verdict (PASS/FAIL/N-A/SKIP)",
    },
    # Delivery domain — telemetry.py + drift.py (Issue #443)
    "wicked.quality.drift_detected": {
        "domain": "wicked-garden",
        "subdomain": "delivery.telemetry",
        "description": "Cross-session quality metric drifted past baseline threshold (special-cause or >=15% drop)",
    },
}

# Payload deny-list — these fields must NEVER appear in bus payloads.
# Enforced by _sanitize_payload() before emission.
_PAYLOAD_DENY_LIST = frozenset({
    "content", "body", "diff", "patch", "raw_text", "thinking",
    "memory_content", "file_content", "source_code", "prompt",
    "password", "secret", "token", "api_key", "credential",
})

# Per-event-type allow-list overrides — explicit exceptions where a normally
# denied key is part of the event's contract. Event types listed here get their
# named fields passed through the deny-list unchanged. Keep this list short and
# justified: every entry is a deliberate carve-out auditable at review time.
#
# wicked.fact.extracted — content is the whole point of the event. The brain
# auto-memorize subscriber requires payload.content to produce a memory.
_PAYLOAD_ALLOW_OVERRIDES: Dict[str, frozenset] = {
    "wicked.fact.extracted": frozenset({"content"}),
}

# ---------------------------------------------------------------------------
# Availability cache — 60s TTL, reset on failure
# ---------------------------------------------------------------------------

_bus_available: Optional[bool] = None
_bus_checked_at: float = 0.0
_bus_binary: Optional[str] = None
_CACHE_TTL_SECONDS = 60.0
_EMIT_TIMEOUT_SECONDS = 5.0

# Cursor ID for poll-on-invoke (set on first registration)
_cursor_id: Optional[str] = None
_CURSOR_FILE = os.path.join(
    os.path.expanduser("~"),
    ".something-wicked", "wicked-garden", "local",
    "wicked-garden", "_bus_cursor.json",
)


def _is_disabled() -> bool:
    """Check if bus is disabled via env var."""
    return os.environ.get("WICKED_BUS_DISABLED", "").strip() in ("1", "true", "yes")


def _resolve_binary() -> Optional[str]:
    """Resolve the wicked-bus binary path once, cache it."""
    global _bus_binary
    if _bus_binary is not None:
        return _bus_binary

    # Try direct binary first (faster than npx)
    path = shutil.which("wicked-bus")
    if path:
        _bus_binary = path
        return _bus_binary

    # Fallback: verify npx can find it
    try:
        result = subprocess.run(
            ["npx", "wicked-bus", "status", "--json"],
            capture_output=True, text=True,
            timeout=_EMIT_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            _bus_binary = "npx"
            return _bus_binary
    except Exception:
        pass  # fail open

    return None


def _check_available() -> bool:
    """Check bus availability with 60s TTL cache."""
    global _bus_available, _bus_checked_at

    now = time.monotonic()
    if _bus_available is not None and (now - _bus_checked_at) < _CACHE_TTL_SECONDS:
        return _bus_available

    if _is_disabled():
        _bus_available = False
        _bus_checked_at = now
        return False

    binary = _resolve_binary()
    if binary is None:
        _bus_available = False
        _bus_checked_at = now
        return False

    _bus_available = True
    _bus_checked_at = now
    return True


def _invalidate_cache() -> None:
    """Reset availability cache on failure."""
    global _bus_available, _bus_checked_at
    _bus_available = None
    _bus_checked_at = 0.0


def _build_cmd(*args: str) -> List[str]:
    """Build command list using cached binary path."""
    if _bus_binary == "npx":
        return ["npx", "wicked-bus", *args]
    elif _bus_binary:
        return [_bus_binary, *args]
    return ["npx", "wicked-bus", *args]


def _sanitize_payload(payload: Dict[str, Any], event_type: str = "") -> Dict[str, Any]:
    """Remove denied fields from payload. Never send content to the bus.

    Per-event allow overrides (see _PAYLOAD_ALLOW_OVERRIDES) let specific event
    types pass named denied fields through — these are explicit, audited carve-outs
    for events whose contract requires a denied key (e.g. wicked.fact.extracted
    must ship content to the brain auto-memorize subscriber).
    """
    allow = _PAYLOAD_ALLOW_OVERRIDES.get(event_type, frozenset())
    return {k: v for k, v in payload.items() if k not in _PAYLOAD_DENY_LIST or k in allow}


# ---------------------------------------------------------------------------
# Emit — fire-and-forget
# ---------------------------------------------------------------------------

def emit_event(
    event_type: str,
    payload: Dict[str, Any],
    chain_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit an event to wicked-bus. Fire-and-forget — returns immediately.

    Args:
        event_type: Must be a key in BUS_EVENT_MAP.
        payload: Event data. Denied fields are stripped automatically.
        chain_id: Crew causality chain ID. Added to metadata.
        metadata: Additional operational context (not indexed, not filtered).
    """
    if not _check_available():
        return

    event_def = BUS_EVENT_MAP.get(event_type)
    if event_def is None:
        return  # Unknown event type — fail silently

    safe_payload = _sanitize_payload(payload, event_type)

    cmd = _build_cmd(
        "emit",
        "--type", event_type,
        "--domain", event_def["domain"],
        "--subdomain", event_def["subdomain"],
        "--payload", json.dumps(safe_payload, default=str),
        "--json",
    )

    # Merge chain_id into metadata
    meta = dict(metadata or {})
    if chain_id:
        meta["chain_id"] = chain_id

    if meta:
        cmd.extend(["--metadata", json.dumps(meta, default=str)])

    def _fire():
        try:
            subprocess.run(
                cmd,
                timeout=_EMIT_TIMEOUT_SECONDS,
                capture_output=True,
            )
        except Exception:
            _invalidate_cache()

    threading.Thread(target=_fire, daemon=True).start()


# ---------------------------------------------------------------------------
# Poll — on-invoke consumption
# ---------------------------------------------------------------------------

def _load_cursor() -> Optional[str]:
    """Load cursor ID from persistent storage."""
    global _cursor_id
    if _cursor_id:
        return _cursor_id
    try:
        with open(_CURSOR_FILE, "r") as f:
            data = json.load(f)
            _cursor_id = data.get("cursor_id")
            return _cursor_id
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _save_cursor(cursor_id: str) -> None:
    """Persist cursor ID for cross-session continuity."""
    global _cursor_id
    _cursor_id = cursor_id
    try:
        os.makedirs(os.path.dirname(_CURSOR_FILE), exist_ok=True)
        with open(_CURSOR_FILE, "w") as f:
            json.dump({"cursor_id": cursor_id, "updated_at": time.time()}, f)
    except OSError:
        pass  # fail open


def _ensure_registered() -> Optional[str]:
    """Register wicked-garden as a bus subscriber if not already registered."""
    cursor = _load_cursor()
    if cursor:
        return cursor

    if not _check_available():
        return None

    try:
        result = subprocess.run(
            _build_cmd(
                "register",
                "--plugin", "wicked-garden",
                "--role", "subscriber",
                "--filter", "wicked.*",
                "--json",
            ),
            capture_output=True, text=True,
            timeout=_EMIT_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            cursor_id = data.get("cursor_id")
            if cursor_id:
                _save_cursor(cursor_id)
                return cursor_id
    except Exception:
        _invalidate_cache()

    return None


def poll_pending(
    event_type_prefix: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Poll for pending events since last ack. Returns list of event dicts.

    Call at command startup (poll-on-invoke pattern). Returns empty list
    if bus is unavailable or no events pending.

    Args:
        event_type_prefix: Filter events by type prefix (e.g., "wicked.gate.").
        limit: Max events to return per poll.
    """
    if not _check_available():
        return []

    cursor = _ensure_registered()
    if not cursor:
        return []

    try:
        # Read cursor's last_event_id from registration
        result = subprocess.run(
            _build_cmd("list", "--json"),
            capture_output=True, text=True,
            timeout=_EMIT_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return []

        subs = json.loads(result.stdout)
        last_event_id = 0
        for sub in subs:
            if sub.get("cursor_id") == cursor:
                last_event_id = sub.get("last_event_id", 0)
                break

        # Replay from last acked position
        replay_result = subprocess.run(
            _build_cmd(
                "replay",
                "--cursor-id", cursor,
                "--from-event-id", str(last_event_id),
                "--json",
            ),
            capture_output=True, text=True,
            timeout=_EMIT_TIMEOUT_SECONDS,
        )

        if replay_result.returncode != 0:
            return []

        data = json.loads(replay_result.stdout)
        events = data.get("events", [])

        # Filter by event_type prefix if specified
        if event_type_prefix and events:
            events = [e for e in events if e.get("event_type", "").startswith(event_type_prefix)]

        return events[:limit]

    except Exception:
        _invalidate_cache()
        return []


def ack_events(last_event_id: int) -> bool:
    """Acknowledge events up to last_event_id. Advances the cursor.

    Call after successfully processing events from poll_pending().
    """
    cursor = _load_cursor()
    if not cursor or not _check_available():
        return False

    try:
        result = subprocess.run(
            _build_cmd(
                "ack",
                "--cursor-id", cursor,
                "--last-event-id", str(last_event_id),
                "--json",
            ),
            capture_output=True, text=True,
            timeout=_EMIT_TIMEOUT_SECONDS,
        )
        return result.returncode == 0
    except Exception:
        _invalidate_cache()
        return False


# ---------------------------------------------------------------------------
# Idempotency ledger — keyed on (event_type, chain_id)
# ---------------------------------------------------------------------------

_LEDGER_FILE = os.path.join(
    os.path.expanduser("~"),
    ".something-wicked", "wicked-garden", "local",
    "wicked-garden", "_bus_processed.json",
)


def _load_ledger() -> Dict[str, float]:
    """Load processed events ledger. Returns {key: timestamp}."""
    try:
        with open(_LEDGER_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_ledger(ledger: Dict[str, float]) -> None:
    """Persist processed events ledger."""
    try:
        os.makedirs(os.path.dirname(_LEDGER_FILE), exist_ok=True)
        with open(_LEDGER_FILE, "w") as f:
            json.dump(ledger, f)
    except OSError:
        pass  # fail open


def is_processed(event_type: str, chain_id: str) -> bool:
    """Check if an event has already been processed."""
    key = f"{event_type}:{chain_id}"
    ledger = _load_ledger()
    return key in ledger


def mark_processed(event_type: str, chain_id: str) -> None:
    """Mark an event as processed in the idempotency ledger."""
    key = f"{event_type}:{chain_id}"
    ledger = _load_ledger()
    ledger[key] = time.time()

    # Prune entries older than 7 days to prevent unbounded growth
    cutoff = time.time() - (7 * 86400)
    ledger = {k: v for k, v in ledger.items() if v > cutoff}

    _save_ledger(ledger)


# ---------------------------------------------------------------------------
# Consumer registry — static manifest at scripts/_bus_consumers.json.
# Enforces the max_consumers budget at load time. Does not reject duplicates
# (idempotent), logs an error when the registered count exceeds the budget.
# ---------------------------------------------------------------------------

_CONSUMERS_MANIFEST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "_bus_consumers.json",
)


def load_consumer_registry(
    manifest_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Load the bus consumer registry and validate it against max_consumers.

    Returns a dict with keys:
        consumers: list of consumer entries (may be empty on error)
        max_consumers: int budget (defaults to 8 if absent)
        registered: int count of consumer entries
        over_budget: bool — True when registered > max_consumers
        error: optional str — set when the manifest is missing / malformed

    Fail-open: never raises. A malformed or missing manifest logs an error
    and returns a registry dict with empty consumers so the bus still boots.
    Idempotent at load time — duplicate consumer ids are not rejected.
    """
    path = manifest_path or _CONSUMERS_MANIFEST
    result: Dict[str, Any] = {
        "consumers": [],
        "max_consumers": 8,
        "registered": 0,
        "over_budget": False,
        "error": None,
    }
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        result["error"] = f"consumer manifest not found: {path}"
        logger.debug(result["error"])
        return result
    except (json.JSONDecodeError, OSError) as exc:
        result["error"] = f"consumer manifest malformed: {exc}"
        logger.error("bus consumer registry: %s", result["error"])
        return result

    if not isinstance(data, dict):
        result["error"] = "consumer manifest root is not an object"
        logger.error("bus consumer registry: %s", result["error"])
        return result

    consumers = data.get("consumers", [])
    if not isinstance(consumers, list):
        result["error"] = "consumer manifest 'consumers' is not a list"
        logger.error("bus consumer registry: %s", result["error"])
        consumers = []

    max_budget = data.get("max_consumers", 8)
    try:
        max_budget = int(max_budget)
    except (TypeError, ValueError):
        max_budget = 8

    registered = len(consumers)
    over_budget = registered > max_budget

    result.update({
        "consumers": consumers,
        "max_consumers": max_budget,
        "registered": registered,
        "over_budget": over_budget,
    })

    if over_budget:
        logger.error(
            "bus consumer registry over budget: %d consumers registered, max %d. "
            "Review %s before adding more consumers.",
            registered, max_budget, path,
        )

    return result
