#!/usr/bin/env python3
"""process_memory.py — persistent process memory + kaizen backlog (issue #447).

Purpose
-------
Process observations and improvement hypotheses evaporate between sessions.
This module gives every crew project three durable surfaces that survive
across sessions:

1. ``process-memory.md`` — a living narrative the facilitator reads at every
   session start (first-class context, not recall-on-demand). Stored in the
   crew project directory.
2. **Kaizen backlog** — hypothesis-driven process-improvement items with
   structured IDs, waste types, uncertainty classification, and status
   lifecycle (``proposed`` / ``trialing`` / ``adopted`` / ``rejected``).
3. **Action-item tracking** — retrospective action items get stable ``AI-NNN``
   IDs and are tracked across sessions; unresolved items ≥2 sessions old
   surface automatically at planning time.

All three surfaces live in a single JSON file per project so that the
facilitator can load them with one read:

    <project-dir>/process-memory.json

Additionally a human-readable ``process-memory.md`` companion is rendered on
every write so users and agents can browse without JSON parsing.

Uncertainty gate
----------------
``evaluate_uncertainty_gate()`` is the guardrail that prevents the team from
bolting on new process gates in response to common-cause variation. Any
proposed new gate must pass one of:

- The underlying drift is *actionable* (special-cause signal from
  ``scripts/delivery/drift.classify``), OR
- The author explicitly flags the uncertainty as ``epistemic`` (we don't
  know enough) rather than ``aleatoric`` (irreducible variation).

If ``scripts/delivery/drift`` isn't importable yet (PR #452 not merged), the
gate fails open — we do not block work because a sibling PR hasn't landed.
The fail-open branch is logged to stderr so reviewers know why the gate
behaved permissively.

Stdlib-only. No external dependencies. Safe to import from hook scripts.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Resolve crew project directory helper without creating a circular dep on
# phase_manager.py (which loads DomainStore, logging config, etc.).
_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT))

try:
    from _domain_store import get_local_path  # type: ignore
except Exception:  # pragma: no cover — fallback only triggers in broken envs
    def get_local_path(domain: str, *subpath: str) -> Path:  # type: ignore[misc]
        root = Path.home() / ".something-wicked" / "wicked-garden" / "local" / domain
        for part in subpath:
            root = root / part
        root.mkdir(parents=True, exist_ok=True)
        return root


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Lean Muda-derived waste taxonomy — kaizen items are classified by which
# type of process waste they aim to remove. Using the canonical 8-waste list
# makes retro observations easier to cluster over time.
WASTE_TYPES: tuple[str, ...] = (
    "defects",          # rework, bugs escaping review
    "overproduction",   # features nobody asked for, extra gates
    "waiting",          # blocked on review, handoff, toolchain
    "non-utilized-talent",  # specialists idle or misapplied
    "transportation",   # excessive context handoff between agents
    "inventory",        # WIP piling up in one phase
    "motion",           # switching tools / rereading the same docs
    "overprocessing",   # rigor above what the work warrants
)

# Uncertainty classification — borrowed from decision-theory literature.
# The distinction matters because adding process is only useful against
# *epistemic* uncertainty (we can learn our way out). Adding process
# against *aleatoric* uncertainty just adds overhead without removing risk.
UNCERTAINTY_TYPES: tuple[str, ...] = ("epistemic", "aleatoric")

# Kaizen lifecycle.
KAIZEN_STATUSES: tuple[str, ...] = ("proposed", "trialing", "adopted", "rejected")

# Action-item lifecycle.
AI_STATUSES: tuple[str, ...] = ("open", "in-progress", "resolved", "cancelled")

# Aging threshold — action items unresolved for 2+ sessions surface at
# planning. This is a deliberate choice: 1 session might just be the current
# work cycle; 2+ means the item is sticking.
AGING_SESSION_THRESHOLD = 2

# Process-memory JSON + markdown filenames (sit inside the crew project dir).
MEMORY_JSON_FILENAME = "process-memory.json"
MEMORY_MD_FILENAME = "process-memory.md"

# Regex for safe project slugs (mirrors phase_manager.is_safe_project_name).
_SAFE_PROJECT_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class KaizenItem:
    """A hypothesis-driven process-improvement item.

    Fields:
        id:              ``KZN-NNN`` stable identifier (assigned on creation).
        title:           One-line summary of the improvement hypothesis.
        hypothesis:      If-we-do-X-then-Y framing; the thing we'd test.
        waste_type:      Which Lean waste this aims to reduce.
        impact:          Rough impact rating (``low`` / ``medium`` / ``high``).
        effort:          Rough effort rating (``low`` / ``medium`` / ``high``).
        uncertainty:     ``epistemic`` or ``aleatoric``.
        status:          See ``KAIZEN_STATUSES``.
        source_session:  Session ID where this item was first proposed.
        evidence:        Free-text pointer to the retro / incident that
                         motivated the idea.
        decision_notes:  Populated when the uncertainty gate runs.
        created_at:      ISO timestamp.
        updated_at:      ISO timestamp.
    """

    id: str
    title: str
    hypothesis: str
    waste_type: str
    impact: str = "medium"
    effort: str = "medium"
    uncertainty: str = "epistemic"
    status: str = "proposed"
    source_session: str = ""
    evidence: str = ""
    decision_notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ActionItem:
    """A retrospective action item that needs tracking across sessions.

    Fields:
        id:              ``AI-NNN`` stable identifier (assigned on creation).
        title:           One-line summary.
        description:     Detail — why this item exists.
        owner:           Agent or specialist role expected to drive it.
        status:          See ``AI_STATUSES``.
        source_session:  Session where the AI originated.
        last_seen_session:  Session where the AI was last surfaced/updated.
        age_sessions:    Count of distinct sessions since creation.
        related_kaizen:  Optional KZN-id link.
        created_at:      ISO timestamp.
        updated_at:      ISO timestamp.
        resolved_at:     ISO timestamp (populated on resolution).
    """

    id: str
    title: str
    description: str = ""
    owner: str = ""
    status: str = "open"
    source_session: str = ""
    last_seen_session: str = ""
    age_sessions: int = 1
    related_kaizen: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_safe_project_name(name: str) -> bool:
    return bool(name) and bool(_SAFE_PROJECT_RE.match(name))


def _project_dir(project: str) -> Path:
    """Resolve the crew project directory with path-traversal protection.

    Mirrors phase_manager.get_project_dir but avoids importing it (phase
    manager pulls in DomainStore + logging; this module stays lean so hook
    scripts can import it).
    """
    if not _is_safe_project_name(project):
        raise ValueError(
            f"Invalid project name: {project!r}. Must be alphanumeric, "
            "hyphens, or underscores (max 64 chars)."
        )
    base = get_local_path("wicked-crew", "projects")
    project_dir = (base / project).resolve()
    # Defense-in-depth: reject any path that escapes the projects root.
    try:
        project_dir.relative_to(Path(base).resolve())
    except ValueError as exc:
        raise ValueError(f"Invalid project path (traversal blocked): {exc}")
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _memory_json_path(project: str) -> Path:
    return _project_dir(project) / MEMORY_JSON_FILENAME


def _memory_md_path(project: str) -> Path:
    return _project_dir(project) / MEMORY_MD_FILENAME


def _atomic_write(path: Path, text: str) -> None:
    """Write atomically: temp file + os.replace."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _empty_memory(project: str) -> dict:
    return {
        "schema_version": "1.0",
        "project": project,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        # Free-text narrative the facilitator writes at session-end retros.
        "narrative": "",
        # Session-pass-rate timeline — newest entry last. Consumed by drift
        # classifier when the uncertainty gate runs.
        "pass_rate_timeline": [],
        # Counters for ID assignment; never reused.
        "next_kaizen_seq": 1,
        "next_ai_seq": 1,
        "kaizen": [],
        "action_items": [],
    }


def load_memory(project: str) -> dict:
    """Load the project's process memory, creating an empty shell if absent.

    The shell contains the full schema with empty lists so downstream code
    doesn't need None-checks. This is the single read point the facilitator
    uses at session start.
    """
    path = _memory_json_path(project)
    if not path.exists():
        return _empty_memory(project)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Corrupted file — don't crash. Treat as empty; a subsequent save()
        # will overwrite it atomically.
        print(
            f"[process_memory] corrupted {path}, re-initializing",
            file=sys.stderr,
        )
        return _empty_memory(project)
    # Backfill missing fields so older files remain compatible.
    for key, default in _empty_memory(project).items():
        data.setdefault(key, default)
    return data


def save_memory(project: str, memory: dict) -> None:
    """Persist the memory dict + render the markdown companion."""
    memory["updated_at"] = _utc_now()
    _atomic_write(
        _memory_json_path(project),
        json.dumps(memory, indent=2, sort_keys=False),
    )
    _atomic_write(_memory_md_path(project), render_markdown(memory))


# ---------------------------------------------------------------------------
# Kaizen CRUD
# ---------------------------------------------------------------------------


def _next_kaizen_id(memory: dict) -> str:
    seq = int(memory.get("next_kaizen_seq", 1))
    memory["next_kaizen_seq"] = seq + 1
    return f"KZN-{seq:03d}"


def add_kaizen(
    project: str,
    *,
    title: str,
    hypothesis: str,
    waste_type: str,
    impact: str = "medium",
    effort: str = "medium",
    uncertainty: str = "epistemic",
    source_session: str = "",
    evidence: str = "",
) -> dict:
    """Append a kaizen item and return it.

    Validates taxonomies before writing so the backlog stays clean.
    """
    if waste_type not in WASTE_TYPES:
        raise ValueError(
            f"waste_type {waste_type!r} not in {WASTE_TYPES}"
        )
    if uncertainty not in UNCERTAINTY_TYPES:
        raise ValueError(
            f"uncertainty {uncertainty!r} not in {UNCERTAINTY_TYPES}"
        )
    memory = load_memory(project)
    now = _utc_now()
    item = KaizenItem(
        id=_next_kaizen_id(memory),
        title=title,
        hypothesis=hypothesis,
        waste_type=waste_type,
        impact=impact,
        effort=effort,
        uncertainty=uncertainty,
        status="proposed",
        source_session=source_session,
        evidence=evidence,
        created_at=now,
        updated_at=now,
    )
    memory["kaizen"].append(asdict(item))
    save_memory(project, memory)
    return asdict(item)


def update_kaizen(project: str, kaizen_id: str, **fields: Any) -> dict | None:
    """Update mutable fields on a kaizen item. Returns the updated item or None."""
    memory = load_memory(project)
    for item in memory["kaizen"]:
        if item["id"] == kaizen_id:
            # Guard lifecycle transitions — block unknown statuses.
            if "status" in fields and fields["status"] not in KAIZEN_STATUSES:
                raise ValueError(
                    f"status {fields['status']!r} not in {KAIZEN_STATUSES}"
                )
            if "waste_type" in fields and fields["waste_type"] not in WASTE_TYPES:
                raise ValueError(f"waste_type {fields['waste_type']!r} invalid")
            if "uncertainty" in fields and fields["uncertainty"] not in UNCERTAINTY_TYPES:
                raise ValueError(f"uncertainty {fields['uncertainty']!r} invalid")
            item.update(fields)
            item["updated_at"] = _utc_now()
            save_memory(project, memory)
            return dict(item)
    return None


def list_kaizen(project: str, *, status: str | None = None) -> list[dict]:
    """List kaizen items, optionally filtered by status."""
    memory = load_memory(project)
    items = memory["kaizen"]
    if status is not None:
        items = [i for i in items if i.get("status") == status]
    return list(items)


# ---------------------------------------------------------------------------
# Action-item CRUD + aging
# ---------------------------------------------------------------------------


def _next_ai_id(memory: dict) -> str:
    seq = int(memory.get("next_ai_seq", 1))
    memory["next_ai_seq"] = seq + 1
    return f"AI-{seq:03d}"


def add_action_item(
    project: str,
    *,
    title: str,
    description: str = "",
    owner: str = "",
    source_session: str = "",
    related_kaizen: str = "",
) -> dict:
    """Create a tracked retrospective action item."""
    memory = load_memory(project)
    now = _utc_now()
    ai = ActionItem(
        id=_next_ai_id(memory),
        title=title,
        description=description,
        owner=owner,
        status="open",
        source_session=source_session,
        last_seen_session=source_session,
        age_sessions=1,
        related_kaizen=related_kaizen,
        created_at=now,
        updated_at=now,
    )
    memory["action_items"].append(asdict(ai))
    save_memory(project, memory)
    return asdict(ai)


def touch_action_item(project: str, ai_id: str, session_id: str) -> dict | None:
    """Record that an AI was surfaced in ``session_id``.

    Increments ``age_sessions`` only when the session differs from the last
    one we saw — we count *distinct* sessions, not hook invocations.
    """
    memory = load_memory(project)
    for ai in memory["action_items"]:
        if ai["id"] == ai_id:
            if session_id and session_id != ai.get("last_seen_session"):
                ai["age_sessions"] = int(ai.get("age_sessions", 1)) + 1
                ai["last_seen_session"] = session_id
            ai["updated_at"] = _utc_now()
            save_memory(project, memory)
            return dict(ai)
    return None


def resolve_action_item(
    project: str, ai_id: str, *, status: str = "resolved"
) -> dict | None:
    """Mark an AI resolved (or cancelled). Sets resolved_at."""
    if status not in AI_STATUSES:
        raise ValueError(f"status {status!r} not in {AI_STATUSES}")
    memory = load_memory(project)
    for ai in memory["action_items"]:
        if ai["id"] == ai_id:
            ai["status"] = status
            ai["updated_at"] = _utc_now()
            if status in ("resolved", "cancelled"):
                ai["resolved_at"] = _utc_now()
            save_memory(project, memory)
            return dict(ai)
    return None


def list_action_items(
    project: str, *, status: str | None = None
) -> list[dict]:
    """List action items, optionally filtered by status."""
    memory = load_memory(project)
    items = memory["action_items"]
    if status is not None:
        items = [i for i in items if i.get("status") == status]
    return list(items)


def aging_action_items(
    project: str, *, threshold: int = AGING_SESSION_THRESHOLD
) -> list[dict]:
    """Return open/in-progress AIs whose age meets or exceeds the threshold.

    This is the call the facilitator makes at session start to surface
    items that are sticking across multiple sessions.
    """
    memory = load_memory(project)
    return [
        ai
        for ai in memory["action_items"]
        if ai.get("status") in ("open", "in-progress")
        and int(ai.get("age_sessions", 1)) >= threshold
    ]


# ---------------------------------------------------------------------------
# Pass-rate timeline
# ---------------------------------------------------------------------------


def record_pass_rate(
    project: str, pass_rate: float, *, session_id: str = ""
) -> dict:
    """Append a gate-pass-rate sample to the timeline.

    The timeline feeds ``drift.classify`` when the uncertainty gate runs.
    Keep the list bounded (newest 50) to avoid unbounded growth.
    """
    if not (0.0 <= pass_rate <= 1.0):
        raise ValueError(f"pass_rate must be in [0, 1], got {pass_rate}")
    memory = load_memory(project)
    entry = {
        "session_id": session_id,
        "pass_rate": float(pass_rate),
        "recorded_at": _utc_now(),
    }
    memory["pass_rate_timeline"].append(entry)
    # Bound the timeline — 50 samples is plenty for drift classification.
    memory["pass_rate_timeline"] = memory["pass_rate_timeline"][-50:]
    save_memory(project, memory)
    return entry


# ---------------------------------------------------------------------------
# Uncertainty gate
# ---------------------------------------------------------------------------


def _classify_drift(timeline: list[float]) -> dict | None:
    """Call scripts.delivery.drift.classify if importable; else return None.

    This is the fail-open path documented in the PR. The drift module
    lives in PR #452 (sibling). Until that merges, we skip the drift
    check entirely and let the uncertainty flag carry the decision.

    NOTE: The drift module is an expected dependency from PR #452.
    Until it merges, this helper fails open.
    """
    try:
        # Import lazily — the module may not exist yet in this branch.
        from delivery import drift as _drift  # type: ignore
    except Exception:
        # Surface once, via stderr, so reviewers see the fail-open decision.
        print(
            "[process_memory] delivery.drift not importable — "
            "fail-open on drift classification (PR #452 pending)",
            file=sys.stderr,
        )
        return None
    try:
        return _drift.classify(list(timeline))
    except Exception as exc:  # pragma: no cover — drift shouldn't raise
        print(
            f"[process_memory] drift.classify raised {exc!r}; fail-open",
            file=sys.stderr,
        )
        return None


def evaluate_uncertainty_gate(
    project: str,
    *,
    proposed_gate_name: str,
    uncertainty: str = "aleatoric",
    timeline: list[float] | None = None,
    session_id: str = "",
) -> dict:
    """Decide whether a proposed new process-gate should be allowed.

    A proposed new gate passes when either:

    - ``drift.classify(timeline)["is_actionable"]`` is True (special-cause
      or >=15% drop — a real signal that warrants more process), OR
    - ``uncertainty`` is ``"epistemic"`` — the author has explicitly
      acknowledged that the team is not confident in the cause and needs
      more process to learn.

    Both conditions are false only when the author is asking for more
    process to contain aleatoric (irreducible) variation without any
    special-cause signal. That's the case this gate is meant to block,
    because more process against aleatoric noise just creates overhead.

    Returns a decision dict that is ALSO recorded as a new kaizen item
    (``status="proposed"``) so the audit trail is durable.

    Fail-open semantics
    -------------------
    If ``drift.classify`` is not importable (PR #452 not merged), the
    gate treats the drift check as inconclusive and uses only the
    uncertainty flag. The decision payload notes ``drift_available=False``
    so downstream reviewers can see why the gate behaved permissively.
    """
    if uncertainty not in UNCERTAINTY_TYPES:
        raise ValueError(f"uncertainty {uncertainty!r} not in {UNCERTAINTY_TYPES}")

    memory = load_memory(project)
    if timeline is None:
        timeline = [
            float(s.get("pass_rate", 0.0))
            for s in memory.get("pass_rate_timeline", [])
        ]

    drift_result = _classify_drift(timeline) if timeline else None
    drift_available = drift_result is not None
    is_actionable = bool(drift_result.get("is_actionable")) if drift_result else False
    drift_zone = drift_result.get("zone") if drift_result else "unknown"

    # Decision: pass if EITHER actionable drift OR explicit epistemic flag.
    passed = is_actionable or uncertainty == "epistemic"

    if passed:
        if is_actionable:
            reason = (
                f"drift classifier flagged {drift_zone!r} zone as actionable — "
                "adding process is warranted by special-cause signal."
            )
        else:
            reason = (
                "author flagged uncertainty as epistemic — more process is a "
                "legitimate learning instrument."
            )
    else:
        reason = (
            "no special-cause drift detected and uncertainty is aleatoric — "
            "adding a new gate would add overhead without addressing root cause. "
            "Consider common-cause remediation (coaching, tooling) instead."
        )

    decision = {
        "proposed_gate_name": proposed_gate_name,
        "passed": passed,
        "reason": reason,
        "uncertainty": uncertainty,
        "drift_available": drift_available,
        "drift_zone": drift_zone,
        "drift_is_actionable": is_actionable,
        "timeline_length": len(timeline),
        "session_id": session_id,
        "evaluated_at": _utc_now(),
    }

    # Record the decision as a kaizen item so it's auditable.
    kaizen_title = f"Uncertainty gate: {proposed_gate_name} ({'PASS' if passed else 'BLOCK'})"
    kaizen_notes = json.dumps(decision, indent=2)
    # Choose waste_type heuristically: blocked gates are overproduction,
    # passed gates are defect prevention.
    waste_type = "defects" if passed else "overproduction"
    add_kaizen(
        project,
        title=kaizen_title,
        hypothesis=(
            f"Adding a '{proposed_gate_name}' gate will reduce process risk."
        ),
        waste_type=waste_type,
        impact="medium",
        effort="low",
        uncertainty=uncertainty,
        source_session=session_id,
        evidence=kaizen_notes,
    )
    # Find the just-added item and annotate decision_notes for quick recall.
    memory = load_memory(project)
    if memory["kaizen"]:
        memory["kaizen"][-1]["decision_notes"] = kaizen_notes
        # Auto-reject blocked proposals so they don't clutter "proposed".
        if not passed:
            memory["kaizen"][-1]["status"] = "rejected"
        save_memory(project, memory)

    return decision


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(memory: dict) -> str:
    """Render the process-memory.md companion document.

    This is the artifact facilitators, reviewers, and humans actually read.
    It's intentionally compact so it fits into first-class context at
    session start.
    """
    lines: list[str] = []
    lines.append(f"# Process Memory — {memory.get('project', 'unknown')}")
    lines.append("")
    lines.append(f"_Updated {memory.get('updated_at', '')}_")
    lines.append("")

    narrative = (memory.get("narrative") or "").strip()
    if narrative:
        lines.append("## Narrative")
        lines.append("")
        lines.append(narrative)
        lines.append("")

    # Aging action items go FIRST — this is what we want facilitators to
    # notice immediately when they open the file.
    aging = [
        ai
        for ai in memory.get("action_items", [])
        if ai.get("status") in ("open", "in-progress")
        and int(ai.get("age_sessions", 1)) >= AGING_SESSION_THRESHOLD
    ]
    if aging:
        lines.append(f"## Aging Action Items (>= {AGING_SESSION_THRESHOLD} sessions)")
        lines.append("")
        lines.append("| ID | Title | Owner | Age | Status |")
        lines.append("|----|-------|-------|-----|--------|")
        for ai in aging:
            lines.append(
                f"| {ai.get('id', '')} | {ai.get('title', '')} "
                f"| {ai.get('owner') or '—'} | {ai.get('age_sessions', 1)} "
                f"| {ai.get('status', '')} |"
            )
        lines.append("")

    # All action items (detail table) for completeness.
    items = memory.get("action_items") or []
    if items:
        lines.append("## All Action Items")
        lines.append("")
        lines.append("| ID | Title | Status | Age | Owner |")
        lines.append("|----|-------|--------|-----|-------|")
        for ai in items:
            lines.append(
                f"| {ai.get('id', '')} | {ai.get('title', '')} "
                f"| {ai.get('status', '')} | {ai.get('age_sessions', 1)} "
                f"| {ai.get('owner') or '—'} |"
            )
        lines.append("")

    kaizen = memory.get("kaizen") or []
    if kaizen:
        lines.append("## Kaizen Backlog")
        lines.append("")
        lines.append(
            "| ID | Title | Waste | Impact | Effort | Uncertainty | Status |"
        )
        lines.append(
            "|----|-------|-------|--------|--------|-------------|--------|"
        )
        for k in kaizen:
            lines.append(
                f"| {k.get('id', '')} | {k.get('title', '')} "
                f"| {k.get('waste_type', '')} | {k.get('impact', '')} "
                f"| {k.get('effort', '')} | {k.get('uncertainty', '')} "
                f"| {k.get('status', '')} |"
            )
        lines.append("")

    timeline = memory.get("pass_rate_timeline") or []
    if timeline:
        lines.append("## Gate Pass-Rate Timeline (recent)")
        lines.append("")
        for sample in timeline[-10:]:
            lines.append(
                f"- {sample.get('recorded_at', '')} — "
                f"{sample.get('pass_rate', 0.0):.2f} "
                f"(session {sample.get('session_id') or '—'})"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Facilitator context — the one-read-at-session-start surface
# ---------------------------------------------------------------------------


def facilitator_context(project: str) -> dict:
    """Return the compact dict the facilitator reads at session start.

    Fields are deliberately chosen so the caller can show them inline
    without further processing. Everything a planner needs to know about
    open process risk for this project, in one shot.
    """
    memory = load_memory(project)
    aging = [
        ai
        for ai in memory.get("action_items", [])
        if ai.get("status") in ("open", "in-progress")
        and int(ai.get("age_sessions", 1)) >= AGING_SESSION_THRESHOLD
    ]
    proposed_kaizen = [
        k for k in memory.get("kaizen", []) if k.get("status") == "proposed"
    ]
    trialing_kaizen = [
        k for k in memory.get("kaizen", []) if k.get("status") == "trialing"
    ]
    return {
        "project": project,
        "narrative": memory.get("narrative", ""),
        "aging_action_items": aging,
        "aging_count": len(aging),
        "open_action_items": len(
            [a for a in memory.get("action_items", []) if a.get("status") in ("open", "in-progress")]
        ),
        "proposed_kaizen": proposed_kaizen,
        "trialing_kaizen": trialing_kaizen,
        "kaizen_backlog_size": len(memory.get("kaizen", [])),
        "pass_rate_timeline_length": len(memory.get("pass_rate_timeline", [])),
        "markdown_path": str(_memory_md_path(project)),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Persistent process memory + kaizen backlog (issue #447)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # show
    p_show = sub.add_parser("show", help="Show facilitator context JSON.")
    p_show.add_argument("--project", required=True)

    # render
    p_render = sub.add_parser("render", help="Print process-memory.md content.")
    p_render.add_argument("--project", required=True)

    # kaizen-add
    p_kz = sub.add_parser("kaizen-add", help="Add a kaizen item.")
    p_kz.add_argument("--project", required=True)
    p_kz.add_argument("--title", required=True)
    p_kz.add_argument("--hypothesis", required=True)
    p_kz.add_argument("--waste-type", required=True, choices=WASTE_TYPES)
    p_kz.add_argument("--impact", default="medium")
    p_kz.add_argument("--effort", default="medium")
    p_kz.add_argument(
        "--uncertainty", default="epistemic", choices=UNCERTAINTY_TYPES
    )
    p_kz.add_argument("--session-id", default="")
    p_kz.add_argument("--evidence", default="")

    # ai-add
    p_ai = sub.add_parser("ai-add", help="Add an action item.")
    p_ai.add_argument("--project", required=True)
    p_ai.add_argument("--title", required=True)
    p_ai.add_argument("--description", default="")
    p_ai.add_argument("--owner", default="")
    p_ai.add_argument("--session-id", default="")

    # ai-touch
    p_touch = sub.add_parser(
        "ai-touch", help="Mark an AI as seen in a session (ages counter)."
    )
    p_touch.add_argument("--project", required=True)
    p_touch.add_argument("--id", required=True)
    p_touch.add_argument("--session-id", required=True)

    # ai-resolve
    p_res = sub.add_parser("ai-resolve", help="Resolve an action item.")
    p_res.add_argument("--project", required=True)
    p_res.add_argument("--id", required=True)
    p_res.add_argument(
        "--status", default="resolved", choices=AI_STATUSES
    )

    # aging
    p_age = sub.add_parser(
        "aging", help="List aging AIs (>= 2 sessions) as JSON."
    )
    p_age.add_argument("--project", required=True)
    p_age.add_argument(
        "--threshold", type=int, default=AGING_SESSION_THRESHOLD
    )

    # pass-rate
    p_pr = sub.add_parser(
        "record-pass-rate", help="Record a gate-pass-rate sample."
    )
    p_pr.add_argument("--project", required=True)
    p_pr.add_argument("--rate", type=float, required=True)
    p_pr.add_argument("--session-id", default="")

    # uncertainty-gate
    p_ug = sub.add_parser(
        "uncertainty-gate",
        help="Evaluate whether a proposed new gate should be added.",
    )
    p_ug.add_argument("--project", required=True)
    p_ug.add_argument("--proposed-gate-name", required=True)
    p_ug.add_argument(
        "--uncertainty", default="aleatoric", choices=UNCERTAINTY_TYPES
    )
    p_ug.add_argument("--session-id", default="")

    args = parser.parse_args()

    if args.cmd == "show":
        print(json.dumps(facilitator_context(args.project), indent=2))
        return 0

    if args.cmd == "render":
        memory = load_memory(args.project)
        sys.stdout.write(render_markdown(memory))
        return 0

    if args.cmd == "kaizen-add":
        item = add_kaizen(
            args.project,
            title=args.title,
            hypothesis=args.hypothesis,
            waste_type=args.waste_type,
            impact=args.impact,
            effort=args.effort,
            uncertainty=args.uncertainty,
            source_session=args.session_id,
            evidence=args.evidence,
        )
        print(json.dumps(item, indent=2))
        return 0

    if args.cmd == "ai-add":
        ai = add_action_item(
            args.project,
            title=args.title,
            description=args.description,
            owner=args.owner,
            source_session=args.session_id,
        )
        print(json.dumps(ai, indent=2))
        return 0

    if args.cmd == "ai-touch":
        ai = touch_action_item(args.project, args.id, args.session_id)
        print(json.dumps(ai, indent=2) if ai else json.dumps({"ok": False, "reason": "not found"}))
        return 0 if ai else 1

    if args.cmd == "ai-resolve":
        ai = resolve_action_item(args.project, args.id, status=args.status)
        print(json.dumps(ai, indent=2) if ai else json.dumps({"ok": False, "reason": "not found"}))
        return 0 if ai else 1

    if args.cmd == "aging":
        items = aging_action_items(args.project, threshold=args.threshold)
        print(json.dumps(items, indent=2))
        return 0

    if args.cmd == "record-pass-rate":
        entry = record_pass_rate(
            args.project, args.rate, session_id=args.session_id
        )
        print(json.dumps(entry, indent=2))
        return 0

    if args.cmd == "uncertainty-gate":
        decision = evaluate_uncertainty_gate(
            args.project,
            proposed_gate_name=args.proposed_gate_name,
            uncertainty=args.uncertainty,
            session_id=args.session_id,
        )
        print(json.dumps(decision, indent=2))
        return 0 if decision["passed"] else 2

    print(f"Unknown command: {args.cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
