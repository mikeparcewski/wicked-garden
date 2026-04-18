#!/usr/bin/env python3
"""
qe/_bus_consumers.py — Bus event consumers for the qe domain.

Poll-on-invoke pattern: called at command startup before primary logic.
Each consumer checks the idempotency ledger before acting.
All consumers fail-open — errors are logged, never raised.

Consumer: qe:scenario-scaffold
  Subscribes to wicked.phase.transitioned where phase_from == "build"
  and phase_to ∈ {"test-strategy", "review"}. On match, writes a minimal
  scenario scaffold markdown file under scripts/qe/scenarios/{project_id}/
  so the QE test-strategist has a deterministic starting point.

  The scaffold is intentionally skeletal — authorship is the human/agent's
  job. Idempotent: if the scaffold file already exists, it is not rewritten.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure scripts/ is on path so _bus can be imported directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-qe.bus-consumers")

# Phase transitions we care about. Build → {test-strategy | review} covers both
# phase plans that include a dedicated test-strategy phase and plans that route
# directly to review (low-complexity projects that skip test-strategy).
_TRIGGER_PHASE_FROM = "build"
_TRIGGER_PHASE_TO = frozenset({"test-strategy", "review"})

# Project id must sanitize to a filesystem-safe slug before being used in paths.
_PROJECT_ID_ALLOWED = re.compile(r"[^a-zA-Z0-9_-]")
_PROJECT_ID_MAX_LEN = 64

# Scaffold root — sibling of scripts/qe/, keeps generated artifacts out of the
# marketplace scenarios/ tree which ships as distributable fixtures.
_SCAFFOLD_ROOT = Path(__file__).resolve().parent / "scenarios"


def process_pending_events() -> List[str]:
    """Poll bus for pending phase transitions and scaffold scenarios on match.

    Called at QE command startup (poll-on-invoke). Returns list of actions
    taken. Empty list if bus unavailable, no matching events, or scaffolds
    already exist (idempotent).
    """
    actions: List[str] = []
    try:
        from _bus import poll_pending, ack_events, is_processed, mark_processed

        events = poll_pending(event_type_prefix="wicked.phase.transitioned")
        if not events:
            return actions

        max_event_id = 0
        for event in events:
            event_id = event.get("event_id", 0)
            event_type = event.get("event_type", "")
            payload = event.get("payload", {}) or {}
            metadata = event.get("metadata", {}) or {}
            chain_id = metadata.get("chain_id") or payload.get("chain_id") or ""

            if event_id > max_event_id:
                max_event_id = event_id

            if event_type != "wicked.phase.transitioned":
                continue

            phase_from = payload.get("phase_from")
            phase_to = payload.get("phase_to")
            if phase_from != _TRIGGER_PHASE_FROM or phase_to not in _TRIGGER_PHASE_TO:
                continue

            # Idempotency — (event_type, chain_id) matches the crew consumer
            # shape. Fall back to a composite key when chain_id is absent so
            # we still dedupe on replay.
            idem_key = chain_id or f"{payload.get('project_id', '')}:{phase_from}:{phase_to}"
            if not idem_key:
                continue
            if is_processed(event_type, idem_key):
                continue

            action = _try_scaffold_scenarios(payload, chain_id)
            # Mark processed even when the scaffold was a no-op (file already
            # existed or project_id missing) — replaying the same event should
            # not keep firing.
            mark_processed(event_type, idem_key)
            if action:
                actions.append(action)

        if max_event_id > 0:
            ack_events(max_event_id)

    except Exception as e:
        logger.debug(f"QE bus consumer error (non-blocking): {e}")

    return actions


def _try_scaffold_scenarios(payload: Dict[str, Any], chain_id: str) -> str:
    """Write a scenario scaffold for the project, if not already present.

    Returns a human-readable action string on success, empty string on no-op.
    """
    project_id_raw = payload.get("project_id") or ""
    project_id = _sanitize_project_id(project_id_raw)
    if not project_id:
        logger.debug("Scaffold skipped: missing or unsafe project_id")
        return ""

    try:
        project_dir = _SCAFFOLD_ROOT / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        scaffold_path = project_dir / "scenarios-scaffold.md"
        if scaffold_path.exists():
            # Idempotent — never overwrite a scaffold a human may have edited.
            return ""

        content = _render_scaffold(project_id, chain_id)
        # Write atomically via a temp file in the same directory so a partially
        # written scaffold is never visible to a concurrent reader.
        tmp_path = scaffold_path.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(scaffold_path)

        # Log a plugin-relative path when possible; fall back to absolute for
        # any redirected scaffold root (e.g. tests).
        plugin_root = Path(__file__).resolve().parents[2]
        try:
            display_path = scaffold_path.relative_to(plugin_root)
        except ValueError:
            display_path = scaffold_path
        action = f"Scaffolded QE scenarios for {project_id} at {display_path}"
        logger.info(action)
        return action

    except Exception as e:
        logger.debug(f"Scaffold error for {project_id} (non-blocking): {e}")
        return ""


def _sanitize_project_id(project_id: str) -> Optional[str]:
    """Reduce project_id to a filesystem-safe slug or None.

    Path traversal guard: anything outside [a-zA-Z0-9_-] becomes '-', empty
    and oversized inputs are rejected.
    """
    if not isinstance(project_id, str):
        return None
    cleaned = _PROJECT_ID_ALLOWED.sub("-", project_id).strip("-")
    if not cleaned:
        return None
    return cleaned[:_PROJECT_ID_MAX_LEN]


def _render_scaffold(project_id: str, chain_id: str) -> str:
    """Produce the minimal scaffold markdown — headers only, no test content."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # JSON-encode values so any embedded quote/backslash survives frontmatter.
    fm_project = json.dumps(project_id)
    fm_chain = json.dumps(chain_id or "")
    fm_generated = json.dumps(generated_at)
    return (
        "---\n"
        f"project_id: {fm_project}\n"
        f"chain_id: {fm_chain}\n"
        f"generated_at: {fm_generated}\n"
        "status: \"scaffold\"\n"
        "---\n"
        "\n"
        f"# QE Scenario Scaffold — {project_id}\n"
        "\n"
        "Auto-generated on `build` phase completion. Fill in each section below\n"
        "with concrete scenarios before advancing the test or review phase.\n"
        "\n"
        "## Happy Path\n"
        "\n"
        "_Author: describe the nominal, expected-outcome scenarios here._\n"
        "\n"
        "## Edge Cases\n"
        "\n"
        "_Author: describe boundary, empty, max, and limit scenarios here._\n"
        "\n"
        "## Error Conditions\n"
        "\n"
        "_Author: describe invalid input, dependency failures, and error paths here._\n"
    )
