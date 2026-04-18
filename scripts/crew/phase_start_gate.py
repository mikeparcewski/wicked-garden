#!/usr/bin/env python3
"""
Phase-start heuristic gate (AC-3, AC-10, D6).

Implements a lightweight check that fires before a phase's first specialist is
engaged.  It compares evidence-manifest mtimes and task completion counts
against the ``last_reeval_ts`` stored in session state.

Bias (D6): when ambiguous (e.g. mtime equals last_reeval_ts exactly), the
heuristic treats the situation as "change detected" — false-positive is the
safe default because under-re-eval is a correctness cost whereas over-re-eval
is only a latency cost.

Fail-open (AC-10): any exception, including a missing/unavailable
current_chain.py, returns {"ok": true} with a "fail-open" detail rather than
raising.  The phase is NEVER blocked by missing gate data.

Stdlib-only.  No external dependencies.
"""

import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Internal sentinels
# ---------------------------------------------------------------------------

_CHANGE_MESSAGE_TEMPLATE = (
    "Phase `{phase}` is starting. Material changes detected since last "
    "re-evaluation ({reason}). Invoke `wicked-garden:crew:propose-process` "
    "in `re-evaluate` mode with `current_chain` before engaging specialists. "
    "Do not proceed until re-eval completes."
)


class _MissingChainError(RuntimeError):
    """Raised when the chain snapshot is None or clearly absent."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(ts_str: str) -> "datetime | None":
    """Parse an ISO 8601 UTC timestamp string into an aware datetime.

    Returns None on any parse failure so callers can skip gracefully.
    """
    if not ts_str:
        return None
    try:
        # Normalise 'Z' suffix to '+00:00' for Python < 3.11 compatibility
        normalised = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _change_detected(chain_snapshot: dict, reason: str) -> dict:
    """Build a change-detected response dict."""
    phase = chain_snapshot.get("phase", "unknown") if chain_snapshot else "unknown"
    msg = _CHANGE_MESSAGE_TEMPLATE.format(phase=phase, reason=reason)
    return {"ok": True, "systemMessage": msg, "detail": reason}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check(state: dict, chain_snapshot: dict) -> dict:
    """Evaluate whether material changes occurred since the last full re-eval.

    Bias (D6): mtime >= last_reeval_ts is treated as change detected.
    Fail-open (AC-10): any exception → {"ok": true, "detail": "fail-open ..."}.

    Args:
        state: Dict with keys:
            - last_reeval_ts (str | None): ISO 8601 UTC of last full re-eval.
            - last_reeval_task_count (int): task completion count at last re-eval.
        chain_snapshot: Dict from current_chain.py with keys:
            - counts: {total, completed, in_progress, pending, blocked}
            - tasks: list of task dicts (each has id, status, updated_at, ...)
            - evidence_manifests: list of {path, mtime_iso} dicts
            - phase (str, optional): current phase name for directive text

    Returns:
        {"ok": True}                                       — no change, no-op
        {"ok": True, "systemMessage": str, "detail": str} — change detected
        {"ok": True, "detail": "fail-open ..."}            — error or missing data
    """
    try:
        if not chain_snapshot:
            raise _MissingChainError("chain_snapshot is None or empty")

        last_ts_str: "str | None" = state.get("last_reeval_ts") if state else None
        last_count: int = (state.get("last_reeval_task_count", 0) if state else 0) or 0

        # === Heuristic 1: task completion count increased since last re-eval ===
        counts = chain_snapshot.get("counts") or {}
        completed_now: int = counts.get("completed", 0) or 0
        if completed_now > last_count:
            return _change_detected(chain_snapshot, "task-count-increased")

        # === Heuristics 2 & 3: evidence or task mtime vs last_reeval_ts ===
        if last_ts_str is not None:
            last_ts = _parse_iso(last_ts_str)
            if last_ts is None:
                # Unparseable timestamp — treat as ambiguous → false-positive (D6)
                return _change_detected(chain_snapshot, "last-reeval-ts-unparseable")

            for manifest in chain_snapshot.get("evidence_manifests") or []:
                mtime_str = manifest.get("mtime_iso", "") if isinstance(manifest, dict) else ""
                mtime = _parse_iso(mtime_str)
                if mtime is None:
                    continue
                # D6: >= is change detected (equality is the ambiguous case)
                if mtime >= last_ts:
                    return _change_detected(chain_snapshot, "evidence-mtime-gte-last-reeval")

            for task in chain_snapshot.get("tasks") or []:
                updated_at_str = task.get("updated_at", "") if isinstance(task, dict) else ""
                updated_at = _parse_iso(updated_at_str)
                if updated_at is None:
                    continue
                if updated_at >= last_ts:
                    return _change_detected(chain_snapshot, "task-updated-gte-last-reeval")
        else:
            # No prior re-eval timestamp: any completed task is a change signal
            if completed_now > 0:
                return _change_detected(chain_snapshot, "no-prior-reeval-tasks-exist")

        # === No change detected ===
        print("[phase_start_gate] no change detected — no-op", file=sys.stderr)
        return {"ok": True}

    except _MissingChainError as exc:
        # AC-10: chain data unavailable → fail-open, never block
        print(f"[phase_start_gate] fail-open (missing chain): {exc}", file=sys.stderr)
        return {"ok": True, "detail": f"fail-open: {exc}"}

    except Exception as exc:  # noqa: BLE001 — intentional catch-all for hook safety
        print(f"[phase_start_gate] fail-open (unexpected error): {exc}", file=sys.stderr)
        return {"ok": True, "detail": f"fail-open error: {exc}"}
