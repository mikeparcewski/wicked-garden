#!/usr/bin/env python3
"""
Bus-grain subscriber: react to wicked.gate.decided events.

Issue #592 (v8 PR-8) — migrated from Claude-lifecycle pattern.

Grain: BUS-GRAIN — this handler fires on wicked.gate.decided events that may
have been emitted by a different session hours ago.  It does NOT use Claude's
prompt / tool lifecycle hooks because Claude cannot see cross-session bus events.

Handler contract:
  - Receives full event JSON on stdin.
  - Emits {"status": "ok"|"error", "message": str, "emit_events": list} on stdout.

Responsibilities:
  1. Validate the gate-decided event has required fields.
  2. Log the gate decision for observability.
  3. Optionally emit a follow-on wicked.hook.gate_decided_processed event
     (hook chaining example).

Always fails open — any unhandled exception returns {"status": "error", ...}.
"""

import json
import sys


def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.stdout.write(json.dumps({
            "status": "error",
            "message": f"Failed to parse event JSON: {exc}",
            "emit_events": [],
        }))
        return

    payload = event.get("payload", {})
    project_id = payload.get("project_id") or payload.get("project") or ""
    phase = payload.get("phase") or ""
    verdict = payload.get("result") or payload.get("verdict") or ""
    score = payload.get("score")

    if not project_id or not phase:
        sys.stdout.write(json.dumps({
            "status": "error",
            "message": f"gate.decided event missing project_id or phase: {payload!r}",
            "emit_events": [],
        }))
        return

    # Emit a processed event for hook chaining (optional — downstream subscribers
    # can react to this synthetic event).
    emit_events = [
        {
            "event_type": "wicked.hook.gate_decided_processed",
            "payload": {
                "project_id": project_id,
                "phase": phase,
                "verdict": verdict,
                "score": score,
                "source_event_id": event.get("event_id", 0),
            },
        }
    ]

    sys.stdout.write(json.dumps({
        "status": "ok",
        "message": f"gate.decided processed: project={project_id} phase={phase} verdict={verdict}",
        "emit_events": emit_events,
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — handler must never crash; always emit a result
        sys.stdout.write(json.dumps({
            "status": "error",
            "message": f"Unhandled exception in on_gate_decided: {exc}",
            "emit_events": [],
        }))
