#!/usr/bin/env python3
"""
crew/_bus_consumers.py — Bus event consumers for the crew domain.

Poll-on-invoke pattern: called at command startup before primary logic.
Each consumer checks the idempotency ledger before acting.
All consumers fail-open — errors are logged, never raised.
"""

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure scripts/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-crew.bus-consumers")


def process_pending_events() -> List[str]:
    """Poll bus for pending events and process them. Returns list of actions taken.

    Called at crew command startup (poll-on-invoke).
    Returns empty list if bus unavailable or no actionable events.
    """
    actions = []
    try:
        from _bus import poll_pending, ack_events, is_processed, mark_processed

        # Poll for gate events
        events = poll_pending(event_type_prefix="wicked.gate.")
        if not events:
            return actions

        max_event_id = 0
        for event in events:
            event_id = event.get("event_id", 0)
            event_type = event.get("event_type", "")
            payload = event.get("payload", {})
            metadata = event.get("metadata", {})
            chain_id = metadata.get("chain_id", "")

            if event_id > max_event_id:
                max_event_id = event_id

            # Consumer: gate APPROVE + low complexity → auto-advance
            #
            # Gate REJECT no longer creates a tracked task here — the reviewer
            # agent emits TaskCreate directly with metadata.event_type=gate-finding
            # and verdict=REJECT. The bus event remains for observability only.
            if event_type == "wicked.gate.decided":
                result = payload.get("result")
                if result == "APPROVE" and chain_id:
                    idem_key = f"auto-advance:{chain_id}"
                    if not is_processed("wicked.phase.auto_advanced", idem_key):
                        action = _try_auto_advance(payload, chain_id)
                        if action:
                            mark_processed("wicked.phase.auto_advanced", idem_key)
                            actions.append(action)

        # Ack up to the last event we saw
        if max_event_id > 0:
            ack_events(max_event_id)

    except Exception as e:
        logger.debug(f"Bus consumer error (non-blocking): {e}")

    return actions


def _try_auto_advance(payload: Dict[str, Any], chain_id: str) -> str:
    """Auto-advance phase if project has auto_advance=true and complexity ≤ 2.

    Option D from council review: bus consumer calls phase_manager approve
    (phase_manager remains single state writer). Emits audit event.

    Safety rails:
    - Disabled by default (auto_advance must be explicitly true)
    - Re-evaluates complexity at transition time
    - Any prior non-APPROVE result kills auto-advance for the project
    - Approver identity: "bus:auto-advance"
    """
    try:
        project_id = payload.get("project_id", "")
        phase = payload.get("phase", "")
        if not project_id or not phase:
            return ""

        # Load project state to check auto_advance flag
        from _domain_store import DomainStore
        ds = DomainStore("wicked-crew")
        projects = ds.list("projects")
        project = None
        for p in projects:
            if p.get("name") == project_id or p.get("id") == project_id:
                project = p
                break

        if not project:
            return ""

        # Check auto_advance flag (disabled by default)
        if not project.get("auto_advance", False):
            return ""

        # Check complexity ≤ 2
        complexity = project.get("complexity_score", 99)
        if complexity > 2:
            return ""

        # Check no prior non-APPROVE gate in this project
        phases_data = project.get("phases", {})
        for p_name, p_data in phases_data.items():
            if isinstance(p_data, dict):
                gate_result = p_data.get("gate_result")
                if gate_result and gate_result not in ("APPROVE", None):
                    logger.info(f"Auto-advance skipped: prior {gate_result} in phase {p_name}")
                    return ""

        # All checks pass — call phase_manager approve
        import subprocess
        from pathlib import Path
        scripts_dir = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(scripts_dir / "_run.py"),
                "scripts/crew/phase_manager.py",
                project_id, "approve",
                "--phase", phase,
                "--approver", "bus:auto-advance",
            ],
            capture_output=True, text=True, timeout=10,
            cwd=str(scripts_dir.parent),
        )

        if result.returncode != 0:
            logger.debug(f"Auto-advance failed: {result.stderr[:200]}")
            return ""

        # Emit audit event
        from _bus import emit_event
        emit_event("wicked.phase.auto_advanced", {
            "project_id": project_id,
            "phase": phase,
            "complexity_score": complexity,
            "gate_result": "APPROVE",
        }, chain_id=chain_id)

        action = f"Auto-advanced {project_id}/{phase} (complexity {complexity}, gate APPROVE)"
        logger.info(action)
        return action

    except Exception as e:
        logger.debug(f"Auto-advance error (non-blocking): {e}")
        return ""
