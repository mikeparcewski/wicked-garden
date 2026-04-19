#!/usr/bin/env python3
"""
Convergence Lifecycle — artifact integration-state tracking with stall detection.

Each code artifact inside a crew project has a convergence lifecycle that tracks
how far it has progressed toward being *actually wired into the production path*.
This is distinct from the ``artifact_state.py`` deliverable lifecycle
(DRAFT/IN_REVIEW/APPROVED/IMPLEMENTED/VERIFIED/CLOSED), which tracks review
status of deliverable documents.

Convergence states
------------------
    Designed     — architecture/design note exists for the artifact
    Built        — implementation file exists and compiles
    Wired        — implementation is invoked from the production code path
    Tested       — implementation is covered by at least one test
    Integrated   — implementation participates in an end-to-end flow
    Verified     — implementation passed review and is shipping

Transitions are strictly forward. Each transition records an append-only
JSONL entry under ``{project_dir}/phases/{phase}/convergence-log.jsonl``.

Every transition requires an evidence envelope with these non-empty fields:
    verifier     — agent, test name, or reviewer authoring the transition
    phase        — crew phase under which the transition occurred
    artifact_ref — file path, symbol, or ID of the artifact
    description  — >= 10 character human-readable justification

Stall detection
---------------
Pre-``Integrated`` states carry an aging budget (in sessions). An artifact
stuck in the same state across >= ``STALL_SESSION_THRESHOLD`` sessions is
flagged as a gate finding for the review phase.

CLI
---
    convergence.py record --project P --artifact A --to Built \\
        --verifier agent --phase build --ref src/foo.py --desc "..." --session-id S1
    convergence.py status --project P [--artifact A]
    convergence.py stall --project P [--threshold 3]
    convergence.py verify-gate --project P

Stdlib-only. Cross-platform. Fail-open on missing logs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Resolve helpers from parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

STATES: Tuple[str, ...] = (
    "Designed",
    "Built",
    "Wired",
    "Tested",
    "Integrated",
    "Verified",
)

# Forward-only transitions.
VALID_TRANSITIONS: Dict[str, frozenset] = {
    "Designed":   frozenset({"Built"}),
    "Built":      frozenset({"Wired"}),
    "Wired":      frozenset({"Tested"}),
    "Tested":     frozenset({"Integrated"}),
    "Integrated": frozenset({"Verified"}),
    "Verified":   frozenset(),
}

# Telomere-style per-state session budgets. A transition out of the state
# must occur within this many sessions or the artifact is flagged as stale.
AGING_BUDGET_SESSIONS: Dict[str, int] = {
    "Designed":   2,
    "Built":      2,
    "Wired":      2,
    "Tested":     2,
    "Integrated": 1,
}

# Pre-Integrated states considered "not done yet" by the review gate.
PRE_INTEGRATED_STATES: frozenset = frozenset({"Designed", "Built", "Wired", "Tested"})

# Default stall threshold. Can be overridden per-call.
STALL_SESSION_THRESHOLD: int = 3

# Minimum description length to avoid trivially-empty evidence.
_MIN_DESCRIPTION_LEN: int = 10

# Required evidence fields for every transition.
_REQUIRED_EVIDENCE_FIELDS: Tuple[str, ...] = (
    "verifier",
    "phase",
    "artifact_ref",
    "description",
)

_LOG_FILENAME: str = "convergence-log.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_state(state: str) -> str:
    """Return the canonical form of ``state`` or raise ValueError."""
    if state not in STATES:
        raise ValueError(
            "Invalid convergence state '{}'. Valid states: {}".format(
                state, ", ".join(STATES),
            )
        )
    return state


def _validate_transition(from_state: Optional[str], to_state: str) -> None:
    """Raise ValueError if the transition is not allowed."""
    to_state = _validate_state(to_state)

    if from_state is None:
        # First transition must land in Designed (the initial state).
        if to_state != "Designed":
            raise ValueError(
                "First convergence transition must be to 'Designed', got '{}'".format(
                    to_state,
                )
            )
        return

    from_state = _validate_state(from_state)
    allowed = VALID_TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        allowed_list = ", ".join(sorted(allowed)) if allowed else "(none — terminal)"
        raise ValueError(
            "Invalid convergence transition: {} -> {}. Allowed from {}: {}".format(
                from_state, to_state, from_state, allowed_list,
            )
        )


def _validate_evidence(evidence: Dict[str, Any]) -> None:
    """Raise ValueError if evidence is missing required fields or too thin."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dict with required fields")
    missing: List[str] = []
    for field in _REQUIRED_EVIDENCE_FIELDS:
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    if missing:
        raise ValueError(
            "Missing or empty evidence fields: {}. Required: {}".format(
                ", ".join(missing), ", ".join(_REQUIRED_EVIDENCE_FIELDS),
            )
        )
    desc = evidence["description"].strip()
    if len(desc) < _MIN_DESCRIPTION_LEN:
        raise ValueError(
            "evidence.description must be >= {} characters (got {})".format(
                _MIN_DESCRIPTION_LEN, len(desc),
            )
        )


def _log_path(project_dir: Path, phase: str) -> Path:
    """Path to the convergence-log.jsonl for a given phase."""
    return project_dir / "phases" / phase / _LOG_FILENAME


def _iter_all_log_paths(project_dir: Path) -> List[Path]:
    """Return all convergence-log.jsonl files across every phase directory."""
    phases_dir = project_dir / "phases"
    if not phases_dir.is_dir():
        return []
    return sorted(phases_dir.glob("*/" + _LOG_FILENAME))


def _read_log(log_path: Path) -> List[Dict[str, Any]]:
    """Read a single convergence log file. Returns [] if missing or malformed."""
    if not log_path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            # Tolerate partial corruption — skip the bad line, keep going.
            continue
    return out


def read_all_entries(project_dir: Path) -> List[Dict[str, Any]]:
    """Return every convergence log entry in the project, time-ordered."""
    entries: List[Dict[str, Any]] = []
    for path in _iter_all_log_paths(project_dir):
        entries.extend(_read_log(path))
    entries.sort(key=lambda e: e.get("timestamp", ""))
    return entries


def _append_log(log_path: Path, entry: Dict[str, Any]) -> None:
    """Atomic-ish append of a single JSONL record."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_transition(
    project_dir: Path,
    artifact_id: str,
    to_state: str,
    evidence: Dict[str, Any],
    session_id: Optional[str] = None,
    *,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a convergence transition for an artifact.

    Validates the transition is legal given the artifact's current state,
    validates the evidence envelope, then appends a JSONL record under
    ``{project_dir}/phases/{evidence.phase}/convergence-log.jsonl``.

    Returns:
        The written log entry.

    Raises:
        ValueError: invalid state, illegal transition, missing evidence fields.
    """
    if not artifact_id or not isinstance(artifact_id, str):
        raise ValueError("artifact_id must be a non-empty string")

    _validate_state(to_state)
    _validate_evidence(evidence)

    current = current_state(project_dir, artifact_id)
    _validate_transition(current, to_state)

    phase = evidence["phase"].strip()
    effective_session_id = (session_id or os.environ.get("CLAUDE_SESSION_ID") or "").strip()
    entry: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "from_state": current,
        "to_state": to_state,
        "timestamp": timestamp or _now(),
        "session_id": effective_session_id,
        "phase": phase,
        "evidence": {
            "verifier": evidence["verifier"].strip(),
            "phase": phase,
            "artifact_ref": evidence["artifact_ref"].strip(),
            "description": evidence["description"].strip(),
        },
    }

    _append_log(_log_path(project_dir, phase), entry)
    return entry


def current_state(project_dir: Path, artifact_id: str) -> Optional[str]:
    """Return the most-recent state for ``artifact_id``, or None if unknown."""
    latest: Optional[Dict[str, Any]] = None
    for entry in read_all_entries(project_dir):
        if entry.get("artifact_id") != artifact_id:
            continue
        latest = entry
    if latest is None:
        return None
    return latest.get("to_state")


def artifact_history(project_dir: Path, artifact_id: str) -> List[Dict[str, Any]]:
    """Return the ordered transition history for a single artifact."""
    return [
        entry for entry in read_all_entries(project_dir)
        if entry.get("artifact_id") == artifact_id
    ]


def _collect_sessions_ordered(entries: Iterable[Dict[str, Any]]) -> List[str]:
    """Return unique session ids in first-seen order from entries."""
    seen: Dict[str, None] = {}
    for entry in entries:
        sid = entry.get("session_id") or ""
        if not sid:
            continue
        if sid not in seen:
            seen[sid] = None
    return list(seen.keys())


def sessions_in_state(
    project_dir: Path,
    artifact_id: str,
    *,
    current_session_id: Optional[str] = None,
) -> int:
    """Return the number of distinct sessions the artifact has been in its current state.

    The count includes the session of the landing transition and every later
    session where the project has logged *any* activity (across all artifacts)
    without this artifact advancing.

    Args:
        project_dir:         Project root directory.
        artifact_id:         Artifact to inspect.
        current_session_id:  Optional — if supplied, count it as an active
                             session even if no log entries exist for it yet.

    Returns:
        0 if the artifact is unknown, else >= 1.
    """
    history = artifact_history(project_dir, artifact_id)
    if not history:
        return 0

    # Find the most recent landing transition.
    landing = history[-1]
    landing_ts = landing.get("timestamp", "")
    landing_sid = (landing.get("session_id") or "").strip()

    # Collect every project-wide session seen at-or-after the landing timestamp.
    all_entries = read_all_entries(project_dir)
    sessions_after: List[str] = []
    seen: set = set()

    if landing_sid and landing_sid not in seen:
        sessions_after.append(landing_sid)
        seen.add(landing_sid)

    for entry in all_entries:
        ts = entry.get("timestamp", "")
        if ts < landing_ts:
            continue
        sid = (entry.get("session_id") or "").strip()
        if not sid or sid in seen:
            continue
        sessions_after.append(sid)
        seen.add(sid)

    # If the caller supplied a live session id that hasn't appeared in any log
    # entry yet, count it as an active session in the current state.
    if current_session_id:
        live = current_session_id.strip()
        if live and live not in seen:
            sessions_after.append(live)

    return max(1, len(sessions_after))


def aging_budget_used(
    project_dir: Path,
    artifact_id: str,
    *,
    current_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return aging-budget info for the artifact's current state.

    Returns:
        Dict with keys:
            state              — current state (or None)
            sessions_in_state  — int
            budget             — int or None (None for terminal/unbudgeted)
            over_budget        — bool (True if sessions_in_state > budget)
    """
    state = current_state(project_dir, artifact_id)
    if state is None:
        return {
            "state": None,
            "sessions_in_state": 0,
            "budget": None,
            "over_budget": False,
        }
    sessions = sessions_in_state(
        project_dir, artifact_id, current_session_id=current_session_id,
    )
    budget = AGING_BUDGET_SESSIONS.get(state)
    over = budget is not None and sessions > budget
    return {
        "state": state,
        "sessions_in_state": sessions,
        "budget": budget,
        "over_budget": over,
    }


def project_status(
    project_dir: Path,
    *,
    current_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a per-artifact status view across the whole project.

    Returns:
        Dict with:
            artifacts: list of {id, state, sessions_in_state, budget,
                                over_budget, last_transition_at, last_phase}
            counts:    dict state -> int
            total:     int (unique artifacts observed)
    """
    entries = read_all_entries(project_dir)
    by_artifact: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        aid = entry.get("artifact_id", "")
        if not aid:
            continue
        by_artifact.setdefault(aid, []).append(entry)

    artifacts: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {s: 0 for s in STATES}

    for aid, hist in sorted(by_artifact.items()):
        last = hist[-1]
        state = last.get("to_state")
        if state in counts:
            counts[state] += 1
        aging = aging_budget_used(
            project_dir, aid, current_session_id=current_session_id,
        )
        artifacts.append({
            "id": aid,
            "state": state,
            "sessions_in_state": aging["sessions_in_state"],
            "budget": aging["budget"],
            "over_budget": aging["over_budget"],
            "last_transition_at": last.get("timestamp"),
            "last_phase": last.get("phase"),
        })

    return {
        "artifacts": artifacts,
        "counts": counts,
        "total": len(by_artifact),
    }


def detect_stalls(
    project_dir: Path,
    *,
    threshold: int = STALL_SESSION_THRESHOLD,
    current_session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return artifacts stuck in a pre-Integrated state for >= ``threshold`` sessions.

    An artifact is considered stalled if:
        - current state is in PRE_INTEGRATED_STATES, AND
        - sessions_in_state >= threshold

    Each entry contains: artifact_id, state, sessions_in_state, threshold,
    last_transition_at, last_phase, and a human-readable message.
    """
    if threshold < 1:
        raise ValueError("threshold must be >= 1")

    status = project_status(project_dir, current_session_id=current_session_id)
    stalls: List[Dict[str, Any]] = []
    for record in status["artifacts"]:
        state = record.get("state")
        if state not in PRE_INTEGRATED_STATES:
            continue
        sessions = record.get("sessions_in_state", 0)
        if sessions < threshold:
            continue
        stalls.append({
            "artifact_id": record["id"],
            "state": state,
            "sessions_in_state": sessions,
            "threshold": threshold,
            "last_transition_at": record.get("last_transition_at"),
            "last_phase": record.get("last_phase"),
            "message": (
                "Artifact '{}' stuck in '{}' for {} sessions (threshold {}). "
                "Needs attention before review phase."
            ).format(record["id"], state, sessions, threshold),
        })
    return stalls


# ---------------------------------------------------------------------------
# Gate integration — review phase
# ---------------------------------------------------------------------------

# Gate verdicts (mirror existing conventions elsewhere in the codebase).
_GATE_APPROVE = "APPROVE"
_GATE_CONDITIONAL = "CONDITIONAL"
_GATE_REJECT = "REJECT"


def evaluate_review_gate(
    project_dir: Path,
    *,
    threshold: int = STALL_SESSION_THRESHOLD,
    current_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate the ``convergence-verify`` gate for the review phase.

    Rules:
        - If no convergence log exists anywhere under the project, fail-open
          with APPROVE verdict and a note explaining the empty state.
        - If any artifact is still in a pre-Integrated state, the gate returns
          REJECT with findings for every such artifact.
        - Stalled artifacts (sessions_in_state >= threshold) are surfaced as
          explicit stall findings, even if the artifact has since reached
          Tested+, to preserve the audit trail.
        - Over-budget artifacts (sessions > aging budget for their state)
          are surfaced as CONDITIONAL findings when the verdict would
          otherwise be APPROVE.
        - ``CREW_GATE_ENFORCEMENT=legacy`` forces APPROVE regardless of findings.

    Returns:
        Dict with keys:
            gate:      "convergence-verify"
            result:    APPROVE | CONDITIONAL | REJECT
            findings:  list of {kind, artifact_id, state, message}
            summary:   dict (counts + totals)
            legacy_bypass: bool
    """
    legacy_bypass = os.environ.get("CREW_GATE_ENFORCEMENT", "").lower() == "legacy"

    log_paths = _iter_all_log_paths(project_dir)
    if not log_paths:
        # No log — fail-open per graceful-degradation policy.
        return {
            "gate": "convergence-verify",
            "result": _GATE_APPROVE,
            "findings": [],
            "summary": {
                "note": "No convergence log found — skipping gate.",
                "total_artifacts": 0,
            },
            "legacy_bypass": legacy_bypass,
        }

    status = project_status(project_dir, current_session_id=current_session_id)
    findings: List[Dict[str, Any]] = []

    for record in status["artifacts"]:
        aid = record["id"]
        state = record.get("state")
        if state in PRE_INTEGRATED_STATES:
            findings.append({
                "kind": "pre-integrated",
                "artifact_id": aid,
                "state": state,
                "message": (
                    "Artifact '{}' is in '{}' — must reach at least 'Tested' "
                    "(ideally 'Integrated') before review."
                ).format(aid, state),
            })

    for stall in detect_stalls(
        project_dir,
        threshold=threshold,
        current_session_id=current_session_id,
    ):
        findings.append({
            "kind": "stall",
            "artifact_id": stall["artifact_id"],
            "state": stall["state"],
            "message": stall["message"],
        })

    for record in status["artifacts"]:
        if not record.get("over_budget"):
            continue
        # Over-budget but already past pre-Integrated (otherwise recorded above).
        if record.get("state") in PRE_INTEGRATED_STATES:
            continue
        findings.append({
            "kind": "over-budget",
            "artifact_id": record["id"],
            "state": record.get("state"),
            "message": (
                "Artifact '{}' exceeded aging budget for state '{}' "
                "({} sessions vs budget {})."
            ).format(
                record["id"],
                record.get("state"),
                record.get("sessions_in_state"),
                record.get("budget"),
            ),
        })

    if not findings:
        result = _GATE_APPROVE
    elif any(f["kind"] in ("pre-integrated", "stall") for f in findings):
        result = _GATE_REJECT
    else:
        result = _GATE_CONDITIONAL

    if legacy_bypass:
        result = _GATE_APPROVE

    return {
        "gate": "convergence-verify",
        "result": result,
        "findings": findings,
        "summary": {
            "total_artifacts": status["total"],
            "counts": status["counts"],
            "threshold": threshold,
        },
        "legacy_bypass": legacy_bypass,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_project_dir(project_name: str) -> Path:
    """Resolve the on-disk project directory via phase_manager's safe path logic.

    Import is done lazily so ``convergence.py`` can be imported for tests
    that pass a project_dir directly, without bringing in phase_manager's
    DomainStore side effects.
    """
    # Lazy import — avoids pulling DomainStore when callers pass their own path.
    from phase_manager import get_project_dir
    return get_project_dir(project_name)


def _cmd_record(args: argparse.Namespace) -> Dict[str, Any]:
    project_dir = _resolve_project_dir(args.project)
    evidence = {
        "verifier": args.verifier,
        "phase": args.phase,
        "artifact_ref": args.ref,
        "description": args.desc,
    }
    return record_transition(
        project_dir,
        artifact_id=args.artifact,
        to_state=args.to_state,
        evidence=evidence,
        session_id=args.session_id,
    )


def _cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    project_dir = _resolve_project_dir(args.project)
    if args.artifact:
        aging = aging_budget_used(
            project_dir, args.artifact, current_session_id=args.session_id,
        )
        history = artifact_history(project_dir, args.artifact)
        return {
            "artifact_id": args.artifact,
            "current_state": aging["state"],
            "sessions_in_state": aging["sessions_in_state"],
            "budget": aging["budget"],
            "over_budget": aging["over_budget"],
            "history": history,
        }
    return project_status(project_dir, current_session_id=args.session_id)


def _cmd_stall(args: argparse.Namespace) -> Dict[str, Any]:
    project_dir = _resolve_project_dir(args.project)
    stalls = detect_stalls(
        project_dir,
        threshold=args.threshold,
        current_session_id=args.session_id,
    )
    return {"threshold": args.threshold, "stalls": stalls, "count": len(stalls)}


def _cmd_verify_gate(args: argparse.Namespace) -> Dict[str, Any]:
    project_dir = _resolve_project_dir(args.project)
    return evaluate_review_gate(
        project_dir,
        threshold=args.threshold,
        current_session_id=args.session_id,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="convergence.py",
        description="Artifact convergence lifecycle for wicked-crew.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Record a state transition")
    rec.add_argument("--project", required=True, help="Crew project name")
    rec.add_argument("--artifact", required=True, help="Artifact identifier")
    rec.add_argument("--to", dest="to_state", required=True,
                     choices=list(STATES), help="Target state")
    rec.add_argument("--verifier", required=True, help="Agent / reviewer name")
    rec.add_argument("--phase", required=True, help="Crew phase")
    rec.add_argument("--ref", required=True, help="Artifact ref (path / symbol)")
    rec.add_argument("--desc", required=True, help="Transition description (>= 10 chars)")
    rec.add_argument("--session-id", default=None, help="Override session id (else env)")

    st = sub.add_parser("status", help="Show convergence status for project or artifact")
    st.add_argument("--project", required=True, help="Crew project name")
    st.add_argument("--artifact", default=None, help="Optional artifact id")
    st.add_argument("--session-id", default=None, help="Override session id (else env)")

    sl = sub.add_parser("stall", help="List stalled artifacts")
    sl.add_argument("--project", required=True, help="Crew project name")
    sl.add_argument("--threshold", type=int, default=STALL_SESSION_THRESHOLD,
                    help="Minimum sessions-in-state to qualify as stall")
    sl.add_argument("--session-id", default=None, help="Override session id (else env)")

    vg = sub.add_parser("verify-gate", help="Evaluate convergence-verify review gate")
    vg.add_argument("--project", required=True, help="Crew project name")
    vg.add_argument("--threshold", type=int, default=STALL_SESSION_THRESHOLD,
                    help="Stall threshold (sessions)")
    vg.add_argument("--session-id", default=None, help="Override session id (else env)")

    return parser


_CLI_DISPATCH = {
    "record": _cmd_record,
    "status": _cmd_status,
    "stall": _cmd_stall,
    "verify-gate": _cmd_verify_gate,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = _CLI_DISPATCH.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    try:
        result = handler(args)
    except ValueError as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}, indent=2) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
