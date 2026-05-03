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
    # Crew domain — issue #717 (resolve skill: classify-don't-retry path).
    # Emitted per accepted resolution by `crew:resolve --accept`. The verdict
    # on gate-result.json is NEVER mutated by this event — the resolution is
    # surfaced as a first-class bus event so downstream consumers can audit
    # who accepted what without crawling sidecar files. Pairs with the
    # "bus-as-truth" decision from #732.
    "wicked.gate.condition.resolved": {
        "domain": "wicked-garden",
        "subdomain": "crew.condition",
        "description": "Mechanical CONDITIONAL finding resolved via crew:resolve skill (verdict unchanged)",
    },
    # Site 5 of bus-cutover (#746): condition verification flip.
    # Emitted from conditions_manifest.mark_cleared() BEFORE the disk
    # writes (sidecar + manifest).  The projector handler
    # _condition_marked_cleared in daemon/projector.py replays the same
    # atomic two-step write order: sidecar first, then manifest flip.
    # chain_id MUST include condition_id for per-condition idempotency
    # (see ``memory/bus-chain-id-must-include-uniqueness-segment-gotcha.md``).
    "wicked.condition.marked_cleared": {
        "domain": "wicked-garden",
        "subdomain": "crew.condition",
        "description": "Condition verification flipped to verified=True via mark_cleared() (Site 5 cutover)",
    },
    # Site W1 of bus-cutover wave-2 (#787): solo_mode inline-HITL
    # evidence record.  Emitted from solo_mode.dispatch_human_inline()
    # BEFORE the disk write at phases/{phase}/inline-review-context.md.
    # Solo-mode also fires wicked.gate.decided for the same gate which
    # carries the verdict + conditions; this event is for the markdown
    # evidence file specifically (separate artifact, separate event).
    # chain_id format: {project}.{phase}.gate (one inline-review-context
    # per gate per phase, no per-condition split).
    "wicked.crew.inline_review_context_recorded": {
        "domain": "wicked-garden",
        "subdomain": "crew.solo_mode",
        "description": "Inline-HITL gate review evidence recorded by solo_mode (Site W1 cutover)",
    },
    # Wave-2 Tranche A summary emits — these are AUDIT MARKERS, not file
    # projection events.  The corresponding scripts (adopt_legacy.py,
    # migrate_qe_evaluator_name.py, log_retention.py) are EXEMPT from
    # full bus-cutover per docs/v9/wave-2-cutover-plan.md §W2/W3/W4: the
    # writes themselves are migration/maintenance side-effects (one-shot
    # transformations or rotation) that don't fit the projector replay
    # model.  These summary emits give the audit log a marker so future
    # forensics can identify projects that went through legacy adoption
    # / qe-evaluator rename / log rotation.  No projector handlers; no
    # entries in _PROJECTION_RESOLVERS.
    "wicked.crew.legacy_adopted": {
        "domain": "wicked-garden",
        "subdomain": "crew.migration",
        "description": "Legacy beta.3 → v6.0 project migration applied via adopt_legacy.py (audit marker)",
    },
    "wicked.crew.qe_evaluator_migrated": {
        "domain": "wicked-garden",
        "subdomain": "crew.migration",
        "description": "qe-evaluator → gate-adjudicator rename applied via migrate_qe_evaluator_name.py (audit marker)",
    },
    "wicked.log.rotated": {
        "domain": "wicked-garden",
        "subdomain": "platform.log_retention",
        "description": "Log file rotated by log_retention.rotate_if_needed (audit marker)",
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
    # Crew domain — Part C of #734 (bus-as-truth emit additions paired with
    # the load-bearing artifact writes the resume projector + bus-emit lint
    # need to track. See PR #735 audit for the silent-write inventory.)
    "wicked.dispatch.log_entry_appended": {
        "domain": "wicked-garden",
        "subdomain": "crew.dispatch",
        "description": "HMAC-signed dispatch-log.jsonl entry appended (orphan-check sentinel)",
    },
    "wicked.consensus.report_created": {
        "domain": "wicked-garden",
        "subdomain": "crew.consensus",
        "description": "Consensus gate report written to consensus-report.json",
    },
    "wicked.consensus.evidence_recorded": {
        "domain": "wicked-garden",
        "subdomain": "crew.consensus",
        "description": "Consensus rejection evidence written to consensus-evidence.json (audit trail)",
    },
    # Site 3 of bus-cutover (#746): reviewer-report.md write sites
    # (hooks/scripts/post_tool.py lines 963, 970, 984).
    # Two events, not three:
    #   gate_completed — emitted after each _write_reviewer_report call
    #                    (both the append-to-existing and create-new branches)
    #   gate_pending   — emitted after _write_pending_reviewer_report
    #                    (failure path: no consensus_result available)
    "wicked.consensus.gate_completed": {
        "domain": "wicked-garden",
        "subdomain": "crew.consensus",
        "description": "Consensus gate verdict written to reviewer-report.md (append or create)",
    },
    "wicked.consensus.gate_pending": {
        "domain": "wicked-garden",
        "subdomain": "crew.consensus",
        "description": "Pending consensus gate placeholder written to reviewer-report.md (evaluation failed)",
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
# wicked.dispatch.log_entry_appended — `raw_payload` is the canonical JSONL
# bytes the projector replays into the `dispatch_log_entries` table under
# Site 1 of the bus-cutover (#746).  Without it the projector cannot
# reproduce the on-disk line.  Audit note in the PR body: this carve-out
# only ships an already-on-disk dispatch record (HMAC-signed), so payload
# inspection here is bounded by what the orphan check already trusts.
_PAYLOAD_ALLOW_OVERRIDES: Dict[str, frozenset] = {
    "wicked.fact.extracted": frozenset({"content"}),
    "wicked.dispatch.log_entry_appended": frozenset({"raw_payload"}),
    # Site 2 of bus-cutover (#746): the consensus report and evidence emits
    # carry the canonical on-disk JSON bytes via `raw_payload` so the
    # projector can reproduce the file byte-for-byte.  Without the carve-out
    # the deny-list strips it as if it were generic file content.  Council
    # Condition C10 — `raw_payload` is REQUIRED for both emits.
    "wicked.consensus.report_created": frozenset({"raw_payload"}),
    "wicked.consensus.evidence_recorded": frozenset({"raw_payload"}),
    # Site 3 of bus-cutover (#746): reviewer-report.md emits also ship
    # raw_payload so the projector can reproduce the file byte-for-byte.
    "wicked.consensus.gate_completed": frozenset({"raw_payload"}),
    "wicked.consensus.gate_pending": frozenset({"raw_payload"}),
}

# ---------------------------------------------------------------------------
# Emit health counters — module-level, protected by _emit_counter_lock.
#
# _EMIT_ATTEMPTED: incremented AFTER _check_available() + BUS_EVENT_MAP
#   validation pass (bus-absent no-ops must NOT inflate the denominator).
# _EMIT_SUCCEEDED: incremented inside _fire() on returncode == 0.
#
# Public accessor: bus_emit_stats() — pure reader, no side effects.
# Test-teardown helper: _bus_reset_stats() — resets both to 0 atomically.
#
# Threshold for the 99.9% SLO lives in .claude-plugin/gate-policy.json
# under bus_health.emit_success_threshold — NOT as a constant here.
# See Site 3 cutover decision memory:
#   site-3-threshold-lives-in-gate-policy-user-override-2026-05-02.md
# ---------------------------------------------------------------------------

_EMIT_ATTEMPTED: int = 0
_EMIT_SUCCEEDED: int = 0
_emit_counter_lock: threading.Lock = threading.Lock()

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


# ---------------------------------------------------------------------------
# Default-ON set for _bus_as_truth_enabled — shipped cutover sites whose
# flag falls through to the default map.  All five planned sites (1-5) have
# shipped.  Keep this frozenset in sync with PROJECTION_FILE_FLAGS in
# scripts/crew/reconcile_v2.py.
# ---------------------------------------------------------------------------

_BUS_AS_TRUTH_DEFAULT_ON: frozenset = frozenset({
    "DISPATCH_LOG",          # Site 1 — dispatch-log.jsonl (PR #751)
    "CONSENSUS_REPORT",      # Site 2 — consensus-report.json (PR #758)
    "CONSENSUS_EVIDENCE",    # Site 2 — consensus-evidence.json (PR #758)
    "REVIEWER_REPORT",       # Site 3 — reviewer-report.md (PR #776)
    "GATE_RESULT",           # Site 4 — gate-result.json (PR #782 + #784)
    "CONDITIONS_MANIFEST",   # Site 5 — conditions-manifest.json (PR #785)
    "INLINE_REVIEW_CONTEXT", # Site W1 — inline-review-context.md (#787, this PR)
})


def _bus_as_truth_enabled(site: str = "DISPATCH_LOG") -> bool:
    """Resolve flag state for ``site`` token.

    Site 1 (#751) introduced this helper hardcoded to ``DISPATCH_LOG``.
    Site 2 (#746) added the ``site`` parameter so multiple cutover handlers
    can each gate on their own flag while sharing one helper.  Default keeps
    Site 1 callers working unchanged.

    Reading the env var directly in projector handlers or emitters is
    forbidden — every read MUST go through this helper so we have one place
    to flip and one place to audit.  Cutover Sites 3-5 pass their own site
    name (``REVIEWER_REPORT``, ``GATE_RESULT``, ``CONDITIONS_MANIFEST``).

    Resolution order (flag-fold PR #777):
      1. Explicit ``"on"``  (case/whitespace normalised) → True.
      2. Explicit ``"off"`` (case/whitespace normalised) → False.
         Operator opt-out beats the default map — ``OFF``, ``Off``, `` off ``
         all opt out correctly.
      3. Empty / any other value → default map.
         Shipped sites (``_BUS_AS_TRUTH_DEFAULT_ON``) return True;
         unshipped sites return False.

    This resolves four findings from the dual-bot review (#777):
      Finding #1 — non-"on"/"off" values now fall through to the default map
                   consistently for both shipped and unshipped sites.
      Finding #3 — ``.strip().lower()`` normalises case + whitespace.
      Finding #4 — asymmetric truthy-value handling eliminated; shipped and
                   unshipped sites both go through the same fall-through path.

    Args:
        site: Cutover site identifier (uppercase token).  Composed into the
            env var name as ``WG_BUS_AS_TRUTH_<site>``.  Site 2 callers pass
            ``"CONSENSUS_REPORT"`` and ``"CONSENSUS_EVIDENCE"``.
    """
    raw = os.environ.get(f"WG_BUS_AS_TRUTH_{site}", "").strip().lower()
    if raw == "on":
        return True
    if raw == "off":
        return False
    return site in _BUS_AS_TRUTH_DEFAULT_ON


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

    # Count attempts only AFTER availability + event-map validation pass.
    # Bus-absent no-ops (early returns above) must NOT inflate the denominator.
    global _EMIT_ATTEMPTED, _EMIT_SUCCEEDED
    with _emit_counter_lock:
        _EMIT_ATTEMPTED += 1

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

    def _fire() -> None:
        global _EMIT_SUCCEEDED
        try:
            result = subprocess.run(
                cmd,
                timeout=_EMIT_TIMEOUT_SECONDS,
                capture_output=True,
            )
            if result.returncode == 0:
                with _emit_counter_lock:
                    _EMIT_SUCCEEDED += 1
        except Exception:
            _invalidate_cache()

    threading.Thread(target=_fire, daemon=True).start()


def bus_emit_stats() -> Dict[str, Any]:
    """Return current emit health counters as a plain dict.

    Pure reader — no logging, no side effects. Callers (e.g.
    wicked-garden:platform:plugin-health) are responsible for alerting
    when ratio falls below the threshold defined in gate-policy.json
    bus_health.emit_success_threshold.

    Returns:
        {
            "attempted": int,   -- emits past availability + BUS_EVENT_MAP check
            "succeeded": int,   -- returncode-0 subprocess completions
            "ratio": float,     -- succeeded / attempted; 0.0 when attempted == 0
        }
    """
    with _emit_counter_lock:
        attempted = _EMIT_ATTEMPTED
        succeeded = _EMIT_SUCCEEDED
    ratio = succeeded / attempted if attempted > 0 else 0.0
    return {"attempted": attempted, "succeeded": succeeded, "ratio": ratio}


def _bus_reset_stats() -> None:
    """Reset emit health counters to zero.

    TEST-TEARDOWN HELPER ONLY — not for production use. Wired into
    tests/conftest.py autouse fixture so counter isolation is automatic
    across the suite. Resets both counters atomically under the lock.
    """
    global _EMIT_ATTEMPTED, _EMIT_SUCCEEDED
    with _emit_counter_lock:
        _EMIT_ATTEMPTED = 0
        _EMIT_SUCCEEDED = 0


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
