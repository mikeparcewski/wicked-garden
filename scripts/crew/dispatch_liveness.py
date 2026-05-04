#!/usr/bin/env python3
"""dispatch_liveness.py — Theme 4 stuck-state audit for gate dispatch.

Cross-project memory synthesis flagged a class of bug where code defers
resolution to a "next responder" on conflict, but the underlying state is
**terminal** — last writer wins, the resource is exhausted, or the trigger
is purely external. The liveness audit scans for two forms of this:

1. **Stale dispatch-log entries** — entries appended via
   ``dispatch_log.append`` but never matched by a corresponding gate-result.
   When ``dispatched_at`` is older than a configurable threshold (default
   300 seconds for active sessions), the entry is "stuck" — there is no
   next event coming, the reviewer never delivered.

2. **CONDITIONAL gate-results with external-trigger conditions** — a gate
   that emits a CONDITIONAL verdict whose condition text says "wait for X"
   / "external" / "deferred" / "awaiting" but does NOT name a producer
   event. There is no path back to APPROVE because nothing knows what to
   listen for. These are gate-results that have already shipped, so the
   audit reports them as findings rather than rewriting the verdict.

The audit is non-destructive: it READS gate-result.json + dispatch-log
entries (via ``dispatch_log.read_entries`` so the bus-as-truth read path
applies) and emits findings to stdout (or JSON when ``--json`` is set).
Wired into the phase_manager liveness CLI surface so operators can run
``phase_manager.py <project> liveness`` to see stuck dispatches at a
glance, and into a standalone CLI here for cron-style polling.

Stdlib-only. Cross-platform.

Configuration
-------------
``WG_DISPATCH_LIVENESS_STALE_SECS`` (default ``300``):
    Threshold above which a dispatch-log entry without a matching
    gate-result is considered stuck. Five minutes covers a normal
    council-mode panel; longer windows belong in an operator-tunable
    setting, not a code constant.

``WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED`` (default ``warn``):
    ``warn`` (default) — surface external-trigger conditions without a
    producer_event field as findings only. ``strict`` — exit non-zero so
    CI/cron can pipeline-fail. ``off`` — disable the check.

Output shape
------------
Findings are dicts with::

    {
        "kind": "stale-dispatch" | "external-trigger-no-producer",
        "phase": str,
        "gate": str,
        "reviewer": str | None,
        "severity": "warn" | "block",
        "message": str,
        "evidence": dict,  # kind-specific
    }
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Resolve sibling crew imports from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-crew.dispatch-liveness")

# ---------------------------------------------------------------------------
# Tunables (env-driven so operators can adjust without a code change)
# ---------------------------------------------------------------------------

_DEFAULT_STALE_SECS = 300  # 5 minutes — covers a normal council panel
_VALID_PRODUCER_MODES = ("warn", "strict", "off")

# Keywords that mark a condition as deferring to an external actor. These
# are deliberately broad — the goal is to catch "next event will fix it"
# language. False positives are visible (operator reads the WARN), false
# negatives are silent (the bug we're fixing).
_EXTERNAL_TRIGGER_KEYWORDS: Tuple[str, ...] = (
    "wait for",
    "waiting for",
    "external",
    "deferred",
    "awaiting",
    "pending external",
    "after notification",
    "on receipt of",
    "next responder",
    "out-of-band",
    "out of band",
)


def _config_block() -> Dict[str, Any]:
    """Load the dispatch_liveness block from gate-policy.json. Fail-open.

    Theme 2 alignment: gate-policy.json is the canonical source for these
    knobs. We read it via _gate_policy.load_gate_policy so the divergence
    pattern (silent fallback to hardcoded values) is funneled through the
    instrumented loader. Missing/malformed config returns {} and the env-var
    + hardcoded defaults take over — every step logs.
    """
    try:
        from _gate_policy import load_gate_policy  # type: ignore[import]
    except ImportError as exc:
        logger.warning(
            "dispatch_liveness: _gate_policy unavailable (%s) — falling back "
            "to env-var + hardcoded defaults.", exc,
        )
        return {}
    try:
        policy = load_gate_policy()
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.warning(
            "dispatch_liveness: gate-policy.json unreadable (%s) — falling "
            "back to env-var + hardcoded defaults.", exc,
        )
        return {}
    block = policy.get("dispatch_liveness")
    if not isinstance(block, dict):
        return {}
    return block


def _stale_threshold_secs() -> int:
    """Resolve the stale-dispatch threshold.

    Resolution order (highest priority first):
      1. ``WG_DISPATCH_LIVENESS_STALE_SECS`` env-var
      2. ``gate-policy.json::dispatch_liveness.stale_dispatch_secs``
      3. ``_DEFAULT_STALE_SECS`` constant

    Theme 2 mirror: invalid values WARN and walk to the next priority — they
    do not silently flip the audit into "everything is stuck" or "nothing is
    stuck".
    """
    raw = os.environ.get("WG_DISPATCH_LIVENESS_STALE_SECS", "").strip()
    if raw:
        try:
            val = int(raw)
        except ValueError:
            logger.warning(
                "dispatch_liveness: invalid WG_DISPATCH_LIVENESS_STALE_SECS=%r "
                "— falling through to gate-policy.json + default.", raw,
            )
        else:
            if val < 0:
                logger.warning(
                    "dispatch_liveness: negative WG_DISPATCH_LIVENESS_STALE_SECS"
                    "=%r — falling through to gate-policy.json + default.", raw,
                )
            else:
                return val

    block = _config_block()
    if "stale_dispatch_secs" in block:
        candidate = block.get("stale_dispatch_secs")
        try:
            val = int(candidate)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            logger.warning(
                "dispatch_liveness: gate-policy.json dispatch_liveness."
                "stale_dispatch_secs=%r is not an int — using default %d.",
                candidate, _DEFAULT_STALE_SECS,
            )
            return _DEFAULT_STALE_SECS
        if val < 0:
            logger.warning(
                "dispatch_liveness: gate-policy.json dispatch_liveness."
                "stale_dispatch_secs=%r is negative — using default %d.",
                candidate, _DEFAULT_STALE_SECS,
            )
            return _DEFAULT_STALE_SECS
        return val

    return _DEFAULT_STALE_SECS


def _producer_mode() -> str:
    """Resolve the producer-event-required mode.

    Resolution order: env > gate-policy.json > 'warn'. Invalid values WARN
    and walk to the next priority.
    """
    raw = os.environ.get("WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED", "").strip().lower()
    if raw:
        if raw in _VALID_PRODUCER_MODES:
            return raw
        logger.warning(
            "dispatch_liveness: invalid WG_DISPATCH_LIVENESS_PRODUCER_REQUIRED"
            "=%r (valid: %s) — falling through to gate-policy.json + 'warn'.",
            raw, _VALID_PRODUCER_MODES,
        )

    block = _config_block()
    candidate = block.get("producer_event_required") if block else None
    if isinstance(candidate, str) and candidate.strip().lower() in _VALID_PRODUCER_MODES:
        return candidate.strip().lower()
    if candidate is not None:
        logger.warning(
            "dispatch_liveness: gate-policy.json dispatch_liveness."
            "producer_event_required=%r is not one of %s — using 'warn'.",
            candidate, _VALID_PRODUCER_MODES,
        )
    return "warn"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp; return None when malformed."""
    if not isinstance(ts, str) or not ts:
        return None
    # datetime.fromisoformat handles "+00:00" and naive forms but stumbles on
    # the trailing "Z" used by some emitters. Normalise it.
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _condition_text(condition: Any) -> str:
    """Extract the human-readable text from a condition (str or dict shape)."""
    if isinstance(condition, str):
        return condition
    if isinstance(condition, dict):
        for key in ("description", "text", "message", "finding"):
            val = condition.get(key)
            if isinstance(val, str) and val:
                return val
    return ""


def _condition_has_producer(condition: Any) -> bool:
    """True iff the condition declares the event/agent that will resolve it."""
    if not isinstance(condition, dict):
        return False
    # Accept any of these forms — gate authors don't all use the same key.
    for key in ("producer_event", "producer", "trigger_event", "resolves_on"):
        val = condition.get(key)
        if isinstance(val, str) and val.strip():
            return True
    return False


def _matches_external_trigger(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _EXTERNAL_TRIGGER_KEYWORDS)


# ---------------------------------------------------------------------------
# Audit: stale dispatch-log entries
# ---------------------------------------------------------------------------


def audit_phase_dispatches(
    project_dir: Path,
    phase: str,
    *,
    now: Optional[datetime] = None,
    stale_secs: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Find dispatch-log entries with no gate-result older than the threshold.

    Returns a list of findings; empty when everything is healthy. Reads
    dispatch-log via ``dispatch_log.read_entries`` so the bus-as-truth path
    applies (#746 — entries materialise from the event_log).

    A "matching gate-result" is detected by checking for the existence of
    ``phases/{phase}/gate-result.json``. The gate-result schema validator
    + orphan check live elsewhere — this audit is purely about LIVENESS,
    not authentication. If gate-result.json exists, we trust the existing
    orphan-detection layer to handle authorisation.
    """
    findings: List[Dict[str, Any]] = []
    threshold = stale_secs if stale_secs is not None else _stale_threshold_secs()
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        from dispatch_log import read_entries  # type: ignore[import]
    except ImportError as exc:
        logger.warning("dispatch_liveness: dispatch_log unavailable: %s", exc)
        return findings

    try:
        entries = read_entries(Path(project_dir), phase)
    except Exception as exc:  # noqa: BLE001 — fail-open audit
        logger.warning(
            "dispatch_liveness: read_entries failed for phase=%r: %s",
            phase, exc,
        )
        return findings

    gate_result_path = Path(project_dir) / "phases" / phase / "gate-result.json"
    gate_result_present = gate_result_path.exists()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        dispatched_at = _parse_iso(entry.get("dispatched_at", ""))
        if dispatched_at is None:
            # Malformed timestamps are an audit signal in their own right —
            # they break the orphan-window check. Surface as a finding.
            findings.append({
                "kind": "stale-dispatch",
                "phase": phase,
                "gate": entry.get("gate", ""),
                "reviewer": entry.get("reviewer"),
                "severity": "warn",
                "message": (
                    f"dispatch-log entry has unparseable dispatched_at="
                    f"{entry.get('dispatched_at')!r} — cannot determine age"
                ),
                "evidence": {
                    "dispatch_id": entry.get("dispatch_id"),
                    "dispatched_at": entry.get("dispatched_at"),
                },
            })
            continue
        age_secs = (now - dispatched_at).total_seconds()
        if age_secs < threshold:
            continue
        if gate_result_present:
            # The gate-result has already shipped; the orphan check + schema
            # validator own authentication. We only flag dispatches with NO
            # corresponding result.
            continue
        findings.append({
            "kind": "stale-dispatch",
            "phase": phase,
            "gate": entry.get("gate", ""),
            "reviewer": entry.get("reviewer"),
            "severity": "warn",
            "message": (
                f"dispatch-log entry for reviewer={entry.get('reviewer')!r} "
                f"is {int(age_secs)}s old (threshold {threshold}s) and has no "
                f"matching gate-result.json — the reviewer never delivered"
            ),
            "evidence": {
                "dispatch_id": entry.get("dispatch_id"),
                "dispatched_at": entry.get("dispatched_at"),
                "age_secs": int(age_secs),
                "threshold_secs": threshold,
            },
        })
    return findings


# ---------------------------------------------------------------------------
# Audit: CONDITIONAL gate-results with external-trigger conditions
# ---------------------------------------------------------------------------


def audit_conditional_externals(
    project_dir: Path,
    phase: str,
) -> List[Dict[str, Any]]:
    """Find CONDITIONAL gate-results that defer to external triggers w/o a producer.

    Reads ``phases/{phase}/gate-result.json``, walks its conditions list,
    and flags any condition whose text matches an external-trigger keyword
    AND that does NOT declare a producer_event / trigger_event / resolves_on
    field. These are gate verdicts with no return path — the operator
    cannot know what would clear the condition.

    This audit is read-only: the gate-result is NOT mutated. Findings are
    intended to be surfaced as warnings (default) or as a non-zero exit
    in strict mode for CI pipelines.
    """
    findings: List[Dict[str, Any]] = []
    mode = _producer_mode()
    if mode == "off":
        return findings

    gate_file = Path(project_dir) / "phases" / phase / "gate-result.json"
    if not gate_file.exists():
        return findings
    try:
        data = json.loads(gate_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # The schema validator owns reporting on malformed gate-result files;
        # liveness audit just skips and moves on.
        return findings
    if not isinstance(data, dict):
        return findings

    verdict = data.get("verdict") or data.get("result")
    if verdict != "CONDITIONAL":
        return findings

    conditions = data.get("conditions")
    if not isinstance(conditions, list):
        return findings

    severity = "block" if mode == "strict" else "warn"
    for idx, condition in enumerate(conditions):
        text = _condition_text(condition)
        if not text:
            continue
        if not _matches_external_trigger(text):
            continue
        if _condition_has_producer(condition):
            continue
        findings.append({
            "kind": "external-trigger-no-producer",
            "phase": phase,
            "gate": data.get("gate", ""),
            "reviewer": data.get("reviewer"),
            "severity": severity,
            "message": (
                f"CONDITIONAL condition[{idx}] references an external trigger "
                f"({_first_match(text)!r}) but does not declare a "
                "producer_event / trigger_event / resolves_on field — there "
                "is no path back to APPROVE"
            ),
            "evidence": {
                "condition_index": idx,
                "condition_text_excerpt": text[:200],
            },
        })
    return findings


def _first_match(text: str) -> str:
    lowered = text.lower()
    for kw in _EXTERNAL_TRIGGER_KEYWORDS:
        if kw in lowered:
            return kw
    return ""


# ---------------------------------------------------------------------------
# Phase / project drivers
# ---------------------------------------------------------------------------


def audit_phase(
    project_dir: Path,
    phase: str,
    *,
    now: Optional[datetime] = None,
    stale_secs: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run all liveness audits for a single phase. Concatenates findings."""
    out: List[Dict[str, Any]] = []
    out.extend(audit_phase_dispatches(
        project_dir, phase, now=now, stale_secs=stale_secs,
    ))
    out.extend(audit_conditional_externals(project_dir, phase))
    return out


def audit_project(
    project_dir: Path,
    *,
    now: Optional[datetime] = None,
    stale_secs: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run liveness audit across every phase directory in the project."""
    out: List[Dict[str, Any]] = []
    phases_dir = Path(project_dir) / "phases"
    if not phases_dir.is_dir():
        return out
    for phase_dir in sorted(phases_dir.iterdir()):
        if not phase_dir.is_dir():
            continue
        out.extend(audit_phase(
            project_dir, phase_dir.name, now=now, stale_secs=stale_secs,
        ))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_text(findings: Iterable[Dict[str, Any]]) -> str:
    findings_list = list(findings)
    if not findings_list:
        return "dispatch_liveness: no stuck dispatches or external-trigger conditions found."
    lines: List[str] = []
    for f in findings_list:
        lines.append(
            f"[{f['severity'].upper()}] {f['kind']} phase={f['phase']!r} "
            f"gate={f.get('gate', '')!r} reviewer={f.get('reviewer')!r}\n"
            f"  {f['message']}\n"
            f"  evidence={json.dumps(f.get('evidence', {}), separators=(',', ':'))}"
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a crew project for stuck gate dispatches and "
            "CONDITIONAL gate-results that defer to external triggers "
            "without naming the producer event."
        ),
    )
    parser.add_argument(
        "project_dir",
        help="Path to the crew project directory (e.g. ~/.something-wicked/wicked-garden/local/wicked-crew/projects/<name>)",
    )
    parser.add_argument(
        "--phase", default=None,
        help="Audit a single phase (default: every phase under phases/).",
    )
    parser.add_argument(
        "--stale-secs", type=int, default=None,
        help=f"Override stale threshold (default: env or {_DEFAULT_STALE_SECS}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON.")
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero when any blocking finding is reported.",
    )
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser()
    if not project_dir.exists():
        sys.stderr.write(f"dispatch_liveness: project_dir does not exist: {project_dir}\n")
        return 2

    if args.phase:
        findings = audit_phase(project_dir, args.phase, stale_secs=args.stale_secs)
    else:
        findings = audit_project(project_dir, stale_secs=args.stale_secs)

    if args.json:
        sys.stdout.write(json.dumps({"findings": findings}, indent=2) + "\n")
    else:
        sys.stdout.write(_format_text(findings) + "\n")

    if args.strict and any(f.get("severity") == "block" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
