#!/usr/bin/env python3
"""
crew/rigor_escalator.py — First behavior subscriber for ``wicked.steer.escalated``.

PR-3 of the steering detector epic (#679). Closes the loop end-to-end:

    detector emits  -->  bus delivers  -->  THIS subscriber mutates rigor_tier
                                            on the active project, then emits
                                            ``wicked.steer.applied`` for audit.

Design constraints (mirroring PR-1 and PR-2):

  * Pure stdlib. No external deps.
  * The decision logic (``apply_steering_event``) is a pure function of
    ``(event, project_state)`` so it can be unit-tested without a live bus.
  * The CLI subscriber wraps ``apply_steering_event`` and streams events from
    ``wicked-bus subscribe`` (same pattern as ``steering_tail.py``).
  * Every decision branch (escalated, redundant, no-op, error) emits a
    follow-up ``wicked.steer.applied`` audit event so the Auditor persona can
    trace what the subscriber did. ``--dry-run`` suppresses the audit emit.
  * **Never de-escalate** — a project that is already at ``rigor_tier=full``
    stays full. A second ``force-full-rigor`` recommendation logs a redundant
    decision, emits an audit event, and does not mutate the project. This is
    the brainstorm-mandated guardrail.
  * **In-session idempotency** — the subscriber tracks
    ``(project_slug, event_id)`` pairs in a process-local set. Cross-session
    idempotency is the bus's job (cursor-poll); we only protect against the
    bus replaying an event within the same subscriber lifetime.
  * **Fail-open** — phase_manager errors, schema errors, missing projects,
    bus emit failures — all log to stderr and continue. The subscriber must
    never crash the steering loop.

Action -> mutation mapping:

  =========================  ====================================================
  recommended_action          effect on project state
  =========================  ====================================================
  force-full-rigor            set rigor_tier = "full" (unless already full)
  regen-test-strategy         keep tier; mark a regen-test-strategy task in
                              ``rigor_escalation_history`` (no schema change)
  require-council-review      keep tier; record a pending council-mode upgrade
                              for the next gate dispatch
  notify-only                 no mutation; log only
  =========================  ====================================================

Usage (CLI)::

    python3 scripts/crew/rigor_escalator.py
    python3 scripts/crew/rigor_escalator.py --dry-run
    python3 scripts/crew/rigor_escalator.py --from-cursor=<id>

Usage (programmatic)::

    from crew.rigor_escalator import apply_steering_event
    decision = apply_steering_event(event, dry_run=True)
    # decision = {"action_taken": "escalated", "previous_tier": "minimal", ...}
"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Allow running directly as a script. When imported as a package the package
# import already resolved sys.path, so this is a no-op in that case.
_REPO_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_REPO_SCRIPTS))

from crew.steering_event_schema import (  # noqa: E402  (sys.path tweak above)
    KNOWN_EVENT_TYPES,
    validate_payload,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Subscriber identity — passed to ``wicked-bus subscribe --plugin``.
SUBSCRIBER_PLUGIN = "wicked-garden:crew:rigor-escalator"

#: Filter applied at the bus layer. Only ``escalated`` events drive mutations;
#: ``advised`` is informational and ignored by this subscriber.
BUS_FILTER = "wicked.steer.escalated@wicked-garden"

#: The audit event type emitted after every decision. This is how the
#: Auditor persona traces what the subscriber did.
APPLIED_EVENT_TYPE = "wicked.steer.applied"
APPLIED_EVENT_DOMAIN = "wicked-garden"
APPLIED_EVENT_SUBDOMAIN = "crew.rigor-escalator"

#: Rigor tier ordering — higher = stricter. Used by the never-de-escalate
#: guard and by the (action -> tier) mapping.
_TIER_RANK: Dict[str, int] = {
    "minimal": 1,
    "standard": 2,
    "full": 3,
}

#: Default action -> rigor tier mapping. ``None`` means "do not change tier".
#: Tests can override this via ``apply_steering_event(... action_map=...)``.
DEFAULT_ACTION_TO_TIER: Dict[str, Optional[str]] = {
    "force-full-rigor": "full",
    "regen-test-strategy": None,        # keep tier; record task
    "require-council-review": None,     # keep tier; record gate-mode upgrade
    "notify-only": None,                # log only
}

#: Decision action_taken vocabulary — also reused as the audit-event tag.
ACTION_ESCALATED = "escalated"          # tier was bumped
ACTION_REDUNDANT = "redundant"          # already at recommended tier (no-op)
ACTION_NO_OP = "no-op"                  # action does not change tier
ACTION_ERROR = "error"                  # validation/load/persist failed

#: Probe / emit timeouts mirror PR-1/PR-2 (5s probe budget, 10s emit budget).
_BUS_PROBE_TIMEOUT_SECONDS = 5.0
_BUS_EMIT_TIMEOUT_SECONDS = 10.0


# ---------------------------------------------------------------------------
# Bus resolution (mirrors steering_tail.py / sensitive_path.py for consistency)
# ---------------------------------------------------------------------------

def _resolve_bus_command() -> Optional[List[str]]:
    """Find the wicked-bus binary or fall back to npx. Returns argv prefix.

    Mirrors ``scripts/_bus.py:_resolve_binary`` — direct binary first, then
    npx with a status probe so we don't accidentally trigger an npx package
    download on a slow first run.
    """
    direct = shutil.which("wicked-bus")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx is None:
        return None
    try:
        result = subprocess.run(
            [npx, "wicked-bus", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=_BUS_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return [npx, "wicked-bus"]


# ---------------------------------------------------------------------------
# Decision core — pure(-ish) function used by both the CLI and unit tests
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """ISO8601 UTC ``Z`` timestamp matching the steering-event schema regex."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_decision(
    *,
    action_taken: str,
    previous_tier: Optional[str],
    new_tier: Optional[str],
    project_slug: str,
    event_id: str,
    reason: str,
    recommended_action: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured decision record.

    Centralized so the CLI and the audit emitter both see the same fields.
    """
    return {
        "action_taken": action_taken,
        "previous_tier": previous_tier,
        "new_tier": new_tier,
        "project_slug": project_slug,
        "event_id": event_id,
        "reason": reason,
        "recommended_action": recommended_action,
        "decided_at": _utc_now_iso(),
    }


def _event_id(event: Dict[str, Any]) -> str:
    """Best-effort stable id for an event.

    wicked-bus stamps ``event_id`` (integer) and ``idempotency_key`` (uuid)
    on every event before delivery — we prefer ``idempotency_key`` because the
    bus uses it for cross-session dedup and it's already a string. Falls back
    to ``event_id``, then ``id`` (legacy / test envelopes), then a synthetic
    id from payload timestamp + detector + signal so events that arrive
    without any envelope still have a stable idempotency key.
    """
    for key in ("idempotency_key", "event_id", "id"):
        raw = event.get(key)
        if raw is not None and str(raw):
            return str(raw)
    # No envelope id at all — synthesize from payload.
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = event
    parts = [
        str(payload.get("timestamp", "")),
        str(payload.get("detector", "")),
        str(payload.get("signal", "")),
    ]
    return "|".join(parts) or "<unknown>"


def _extract_payload(event: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Return ``(event_type, payload_dict)`` from a bus event envelope.

    wicked-bus delivers events on the wire as a JSON envelope where ``payload``
    is itself a **JSON-encoded string** (not a nested object). Examples:

      * Live bus delivery::

            {"event_id": 45098, "event_type": "wicked.steer.escalated",
             "payload": "{\\"detector\\": \\"sensitive-path\\", ...}",
             "idempotency_key": "...", ...}

      * In-process test envelope (already-parsed dict)::

            {"id": "evt-1", "event_type": "wicked.steer.escalated",
             "payload": {"detector": "sensitive-path", ...}}

      * Bare payload (programmatic caller skipping the envelope)::

            {"detector": "sensitive-path", ...}

    All three shapes resolve to the same ``(event_type, payload_dict)`` tuple.
    A payload string that fails to parse is returned as an empty dict so the
    schema validator produces a clear "missing required field" error rather
    than a swallowed exception.
    """
    if "payload" in event:
        raw_payload = event["payload"]
        event_type = str(event.get("event_type", "wicked.steer.escalated"))
        if isinstance(raw_payload, dict):
            return event_type, raw_payload
        if isinstance(raw_payload, str):
            try:
                parsed = json.loads(raw_payload)
            except (json.JSONDecodeError, ValueError):
                return event_type, {}
            return (
                event_type,
                parsed if isinstance(parsed, dict) else {},
            )
        # Unrecognized payload type — fall through to validator as empty.
        return event_type, {}
    # Bare payload — assume escalated.
    return "wicked.steer.escalated", event


def _emit_applied_event(
    decision: Dict[str, Any],
    original_payload: Dict[str, Any],
    *,
    bus_cmd: Optional[List[str]] = None,
) -> bool:
    """Emit ``wicked.steer.applied`` to the bus. Fail-open.

    Builds a payload that satisfies ``validate_payload(APPLIED_EVENT_TYPE, ...)``
    by reusing the original detector/signal/threshold/session metadata and
    stuffing the decision record into ``evidence`` (the catch-all dict).

    Returns True on a successful subprocess exit, False otherwise. The
    subscriber NEVER raises out of this — bus emit failures are observed via
    stderr only.
    """
    if bus_cmd is None:
        bus_cmd = _resolve_bus_command()
    if bus_cmd is None:
        sys.stderr.write(
            "warn: wicked-bus is not installed or unreachable; "
            "skipping wicked.steer.applied audit emit. "
            f"decision={decision['action_taken']} project={decision['project_slug']}\n"
        )
        return False

    # Build an audit payload that mirrors the original event structure but
    # adds the decision record under evidence. The schema validator accepts
    # any non-empty evidence dict, so this stays compliant.
    evidence: Dict[str, Any] = dict(original_payload.get("evidence") or {})
    evidence["action_taken"] = decision["action_taken"]
    evidence["previous_tier"] = decision["previous_tier"]
    evidence["new_tier"] = decision["new_tier"]
    evidence["reason"] = decision["reason"]
    evidence["decided_at"] = decision["decided_at"]
    evidence["subscriber"] = SUBSCRIBER_PLUGIN

    audit_payload = {
        "detector": original_payload.get("detector", "unknown"),
        "signal": original_payload.get(
            "signal", f"rigor-escalator decision: {decision['action_taken']}"
        ),
        "threshold": original_payload.get("threshold") or {"action": decision["action_taken"]},
        "recommended_action": original_payload.get(
            "recommended_action", decision.get("recommended_action") or "notify-only"
        ),
        "evidence": evidence,
        "session_id": original_payload.get("session_id", "rigor-escalator"),
        "project_slug": decision["project_slug"],
        "timestamp": decision["decided_at"],
    }

    # Defense-in-depth — refuse to emit a payload that would fail validation.
    errors, _warnings = validate_payload(APPLIED_EVENT_TYPE, audit_payload)
    if errors:
        sys.stderr.write(
            "warn: rigor-escalator built an invalid wicked.steer.applied payload; "
            f"dropping audit emit. errors={errors}\n"
        )
        return False

    cmd = list(bus_cmd) + [
        "emit",
        "--type", APPLIED_EVENT_TYPE,
        "--domain", APPLIED_EVENT_DOMAIN,
        "--subdomain", APPLIED_EVENT_SUBDOMAIN,
        "--payload", json.dumps(audit_payload, default=str, separators=(",", ":")),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_BUS_EMIT_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        sys.stderr.write(
            f"warn: wicked.steer.applied emit failed: {exc}\n"
        )
        return False
    if result.returncode != 0:
        sys.stderr.write(
            f"warn: wicked.steer.applied emit returned {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}\n"
        )
        return False
    return True


def _phase_manager():
    """Lazy import — avoids paying phase_manager's import cost in unit tests
    that mock the whole module out via ``sys.modules`` injection.

    Tests that need to exercise the persistence path inject a fake
    ``phase_manager`` module via ``apply_steering_event(... pm=fake)``.
    """
    from crew import phase_manager  # noqa: WPS433 (deliberate lazy import)
    return phase_manager


def apply_steering_event(
    event: Dict[str, Any],
    *,
    dry_run: bool = False,
    seen_event_ids: Optional[Set[Tuple[str, str]]] = None,
    action_map: Optional[Dict[str, Optional[str]]] = None,
    pm: Any = None,
    bus_cmd: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Apply a single steering event to the target project.

    Args:
        event: The event envelope (or bare payload — see ``_extract_payload``).
        dry_run: If True, no project state is mutated and no audit event is
            emitted. The decision record is still returned so callers can log
            what *would* have happened.
        seen_event_ids: Optional in-session idempotency set. The CLI passes a
            single shared set per process; tests typically pass ``None``.
        action_map: Override the default ``DEFAULT_ACTION_TO_TIER`` mapping.
            Useful for tests that want to assert custom action wiring without
            modifying the module-level dict.
        pm: Optional phase_manager module override (for tests). Defaults to
            the lazily-imported ``crew.phase_manager``.
        bus_cmd: Optional precomputed bus argv prefix (avoids re-probing
            wicked-bus on every event).

    Returns:
        A decision record dict with keys:
          * ``action_taken``: one of ``escalated``, ``redundant``, ``no-op``, ``error``
          * ``previous_tier``: tier before the decision (None if unknown / error)
          * ``new_tier``: tier after the decision (None when unchanged)
          * ``project_slug``: the project this decision targets
          * ``event_id``: stable id of the source event
          * ``reason``: short human-readable explanation
          * ``recommended_action``: the action from the source event (when known)
          * ``decided_at``: ISO8601 UTC timestamp of the decision

    The function NEVER raises — every failure is captured as
    ``action_taken="error"`` in the returned decision.
    """
    pm = pm or _phase_manager()
    actions = action_map or DEFAULT_ACTION_TO_TIER

    # ----- 1. Parse + validate ---------------------------------------------
    event_type, payload = _extract_payload(event)
    eid = _event_id(event)

    errors, warnings = validate_payload(event_type, payload)
    if event_type not in KNOWN_EVENT_TYPES or errors:
        for w in warnings:
            sys.stderr.write(f"warn: steering payload warning: {w}\n")
        for e in errors:
            sys.stderr.write(f"warn: steering payload error: {e}\n")
        decision = _new_decision(
            action_taken=ACTION_ERROR,
            previous_tier=None,
            new_tier=None,
            project_slug=str(payload.get("project_slug", "<unknown>")),
            event_id=eid,
            reason=f"invalid payload: {errors[:3]}" if errors else "unknown event_type",
        )
        if not dry_run:
            _emit_applied_event(decision, payload, bus_cmd=bus_cmd)
        return decision

    # event_type is escalated|advised|applied; we only mutate on escalated.
    # The bus filter already restricts to escalated, but a programmatic caller
    # could pass advised/applied — handle gracefully as no-op.
    if event_type != "wicked.steer.escalated":
        decision = _new_decision(
            action_taken=ACTION_NO_OP,
            previous_tier=None,
            new_tier=None,
            project_slug=str(payload.get("project_slug", "<unknown>")),
            event_id=eid,
            reason=f"event_type {event_type!r} is informational; subscriber only acts on escalated",
            recommended_action=str(payload.get("recommended_action", "")),
        )
        if not dry_run:
            _emit_applied_event(decision, payload, bus_cmd=bus_cmd)
        return decision

    project_slug = str(payload["project_slug"])
    recommended_action = str(payload.get("recommended_action", ""))

    # ----- 2. Idempotency --------------------------------------------------
    idem_key = (project_slug, eid)
    if seen_event_ids is not None and idem_key in seen_event_ids:
        decision = _new_decision(
            action_taken=ACTION_NO_OP,
            previous_tier=None,
            new_tier=None,
            project_slug=project_slug,
            event_id=eid,
            reason="duplicate event in this session (in-memory idempotency)",
            recommended_action=recommended_action,
        )
        # Don't re-emit audit on duplicates — that would create an infinite
        # echo if a downstream subscriber reflects applied events back.
        return decision

    # ----- 3. Resolve project ---------------------------------------------
    try:
        state = pm.load_project_state(project_slug)
    except Exception as exc:  # pragma: no cover — defensive only
        sys.stderr.write(f"warn: load_project_state({project_slug!r}) raised {exc!r}\n")
        state = None

    if state is None:
        decision = _new_decision(
            action_taken=ACTION_ERROR,
            previous_tier=None,
            new_tier=None,
            project_slug=project_slug,
            event_id=eid,
            reason=f"project {project_slug!r} not found",
            recommended_action=recommended_action,
        )
        if not dry_run:
            _emit_applied_event(decision, payload, bus_cmd=bus_cmd)
        return decision

    # ----- 4. Compute decision --------------------------------------------
    extras = getattr(state, "extras", None) or {}
    previous_tier = (extras.get("rigor_tier") or "standard").lower()
    target_tier = actions.get(recommended_action)

    if target_tier is None:
        # notify-only / regen-test-strategy / require-council-review — no
        # rigor change, but we still record the decision in history for
        # require-council-review and regen-test-strategy.
        update: Dict[str, Any] = {}
        decision_reason = f"action {recommended_action!r} does not change rigor tier"

        if recommended_action == "regen-test-strategy":
            decision_reason = (
                "regen-test-strategy queued — recorded in rigor_escalation_history"
            )
        elif recommended_action == "require-council-review":
            decision_reason = (
                "require-council-review recorded — next gate dispatch should run "
                "as council mode"
            )
            update["pending_council_upgrade"] = True

        decision = _new_decision(
            action_taken=ACTION_NO_OP,
            previous_tier=previous_tier,
            new_tier=previous_tier,
            project_slug=project_slug,
            event_id=eid,
            reason=decision_reason,
            recommended_action=recommended_action,
        )

        # For non-tier-changing actions we still want history + (optional)
        # pending_council_upgrade flag persisted, except for notify-only.
        if recommended_action != "notify-only" and not dry_run:
            _persist_history_only(pm, state, decision, payload, extra_extras=update)

        if not dry_run:
            _emit_applied_event(decision, payload, bus_cmd=bus_cmd)
        if seen_event_ids is not None:
            seen_event_ids.add(idem_key)
        return decision

    # target_tier is "minimal" | "standard" | "full". Apply the
    # never-de-escalate rule: only mutate when the new tier is STRICTLY
    # higher than the current tier.
    prev_rank = _TIER_RANK.get(previous_tier, 2)  # default to standard
    new_rank = _TIER_RANK.get(target_tier, prev_rank)

    if new_rank <= prev_rank:
        decision = _new_decision(
            action_taken=ACTION_REDUNDANT,
            previous_tier=previous_tier,
            new_tier=previous_tier,  # unchanged
            project_slug=project_slug,
            event_id=eid,
            reason=(
                f"never-de-escalate: project already at tier {previous_tier!r}; "
                f"recommended {target_tier!r} would not increase rigor"
            ),
            recommended_action=recommended_action,
        )
        # Still record for false-positive metrics & audit trail.
        if not dry_run:
            _persist_history_only(pm, state, decision, payload)
            _emit_applied_event(decision, payload, bus_cmd=bus_cmd)
        if seen_event_ids is not None:
            seen_event_ids.add(idem_key)
        return decision

    # Tier increase — escalate.
    decision = _new_decision(
        action_taken=ACTION_ESCALATED,
        previous_tier=previous_tier,
        new_tier=target_tier,
        project_slug=project_slug,
        event_id=eid,
        reason=f"rigor tier raised from {previous_tier!r} to {target_tier!r}",
        recommended_action=recommended_action,
    )

    if not dry_run:
        try:
            _persist_tier_change(pm, state, decision, payload)
        except Exception as exc:
            sys.stderr.write(
                f"warn: failed to persist rigor_tier change for {project_slug!r}: {exc!r}\n"
            )
            decision = _new_decision(
                action_taken=ACTION_ERROR,
                previous_tier=previous_tier,
                new_tier=None,
                project_slug=project_slug,
                event_id=eid,
                reason=f"persist failed: {exc!r}",
                recommended_action=recommended_action,
            )
        _emit_applied_event(decision, payload, bus_cmd=bus_cmd)

    if seen_event_ids is not None:
        seen_event_ids.add(idem_key)
    return decision


def _build_history_entry(
    decision: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Build one append-only history entry. Schema is intentionally flat."""
    return {
        "decided_at": decision["decided_at"],
        "event_id": decision["event_id"],
        "action_taken": decision["action_taken"],
        "previous_tier": decision["previous_tier"],
        "new_tier": decision["new_tier"],
        "recommended_action": decision["recommended_action"],
        "detector": payload.get("detector"),
        "signal": payload.get("signal"),
        "reason": decision["reason"],
    }


def _persist_history_only(
    pm: Any,
    state: Any,
    decision: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    extra_extras: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a history entry without touching ``rigor_tier``.

    Used for ``redundant``, ``no-op`` (regen + council), and audit-only
    branches. Idempotent: appending the same entry twice is harmless because
    the in-session idempotency check already gated us, and the (event_id,
    decided_at) pair is unique per call.
    """
    extras = dict(getattr(state, "extras", None) or {})
    history: List[Dict[str, Any]] = list(extras.get("rigor_escalation_history") or [])
    history.append(_build_history_entry(decision, payload))
    update: Dict[str, Any] = {"rigor_escalation_history": history}
    if extra_extras:
        update.update(extra_extras)
    pm.update_project(state, update)


def _persist_tier_change(
    pm: Any,
    state: Any,
    decision: Dict[str, Any],
    payload: Dict[str, Any],
) -> None:
    """Persist a rigor_tier change + history append in a single update_project call."""
    extras = dict(getattr(state, "extras", None) or {})
    history: List[Dict[str, Any]] = list(extras.get("rigor_escalation_history") or [])
    history.append(_build_history_entry(decision, payload))
    pm.update_project(
        state,
        {
            "rigor_tier": decision["new_tier"],
            "rigor_escalation_history": history,
        },
    )


# ---------------------------------------------------------------------------
# CLI subscriber loop
# ---------------------------------------------------------------------------

def _build_subscribe_cmd(bus_cmd: List[str], cursor: Optional[str]) -> List[str]:
    """Build the ``wicked-bus subscribe`` argv. Mirrors steering_tail.py."""
    cmd = list(bus_cmd) + [
        "subscribe",
        "--plugin", SUBSCRIBER_PLUGIN,
        "--filter", BUS_FILTER,
    ]
    if cursor:
        cmd += ["--cursor-id", cursor]
    return cmd


def _stream_loop(
    bus_cmd: List[str],
    *,
    cursor: Optional[str],
    dry_run: bool,
    seen_event_ids: Set[Tuple[str, str]],
) -> int:
    """Stream events from wicked-bus and dispatch each to apply_steering_event.

    Returns the subscribe child's returncode (or 0 on clean SIGINT).
    """
    cmd = _build_subscribe_cmd(bus_cmd, cursor)

    def _on_sigint(_signum, _frame):  # noqa: ARG001 — signal API
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _on_sigint)

    try:
        # Stream stderr straight through so the user sees subscribe errors live.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write(
            f"error: failed to launch wicked-bus subscribe: {' '.join(cmd)!r}\n"
        )
        return 1

    # Track whether SIGINT was received so we can return 0 on graceful exit
    # while still letting `finally` own all subprocess cleanup. PR #683 had a
    # bot finding flagging redundant cleanup between this except block and
    # the finally block — consolidated here.
    graceful_exit = False
    try:
        assert proc.stdout is not None  # type: ignore[unreachable]
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                sys.stderr.write(f"warn: skipping non-JSON line: {line!r}\n")
                continue
            if not isinstance(event, dict):
                continue
            decision = apply_steering_event(
                event,
                dry_run=dry_run,
                seen_event_ids=seen_event_ids,
                bus_cmd=bus_cmd,
            )
            sys.stdout.write(
                json.dumps(decision, default=str, separators=(",", ":")) + "\n"
            )
            sys.stdout.flush()
    except KeyboardInterrupt:
        graceful_exit = True
    finally:
        # Single cleanup path — terminate-then-kill ladder with bounded waits.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass  # intentional: last-resort cleanup; caller observes exit via returncode

    if graceful_exit:
        return 0
    return proc.returncode if proc.returncode is not None else 0


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rigor_escalator",
        description=(
            "Subscribe to wicked.steer.escalated events and mutate the active "
            "crew project's rigor_tier. Emits wicked.steer.applied for every "
            "decision. SIGINT (Ctrl-C) for clean exit."
        ),
    )
    parser.add_argument(
        "--from-cursor",
        default=None,
        help=(
            "Resume from a known cursor id. Optional — without this the bus "
            "registers a fresh subscription and tails from latest."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and log decisions but do NOT mutate project state and "
            "do NOT emit wicked.steer.applied audit events."
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)

    bus_cmd = _resolve_bus_command()
    if bus_cmd is None:
        sys.stderr.write(
            "error: wicked-bus is not installed. "
            "Install via 'npm install -g wicked-bus' or ensure 'npx' is on PATH.\n"
        )
        return 1

    seen: Set[Tuple[str, str]] = set()
    sys.stderr.write(
        f"rigor-escalator: subscribed to {BUS_FILTER!r} "
        f"(dry_run={args.dry_run}, cursor={args.from_cursor or '<latest>'})\n"
    )
    return _stream_loop(
        bus_cmd,
        cursor=args.from_cursor,
        dry_run=args.dry_run,
        seen_event_ids=seen,
    )


__all__ = [
    "SUBSCRIBER_PLUGIN",
    "BUS_FILTER",
    "APPLIED_EVENT_TYPE",
    "APPLIED_EVENT_DOMAIN",
    "APPLIED_EVENT_SUBDOMAIN",
    "DEFAULT_ACTION_TO_TIER",
    "ACTION_ESCALATED",
    "ACTION_REDUNDANT",
    "ACTION_NO_OP",
    "ACTION_ERROR",
    "apply_steering_event",
    "main",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
