"""Dispatch-log orphan detection for gate-result ingestion (#471, AC-7).

Framing (challenge-phase mutation CH-04): this module detects **orphan**
gate-results — files written without a matching dispatch record. It is
NOT authentication. An attacker with local disk write can forge both
the gate-result and the dispatch-log entry. HMAC-signed entries are
tracked as follow-up issue **#500**.

Runtime overrides (design-addendum-1 D-1 + D-6):

  - ``WG_GATE_RESULT_DISPATCH_CHECK=off``      force-skip orphan detection
  - ``WG_GATE_RESULT_STRICT_AFTER=YYYY-MM-DD`` flip date; default
    ``2026-06-18``. Before the date: orphan → warn + allow (graceful
    degrade). On or after: orphan → REJECT via
    :class:`GateResultAuthorizationError`.

The soft window exists so in-flight projects that started before the
rollout don't brick; the warning is emitted once per session per
``(project_dir, phase)`` tuple via :class:`_DeprecationBudget`.

Stdlib-only.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_SCRIPTS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gate_result_schema import GateResultAuthorizationError  # noqa: E402


# Default strict-after date (design-addendum-1 D-6). Exported so tests
# and docs reference a single source of truth.
DEFAULT_STRICT_AFTER: date = date(2026, 6, 18)

# Process-local session markers. Not threadsafe-strict but correct for
# the one-process-per-crew-run model we operate under.
_DEPRECATION_EMITTED: set = set()
_STRICT_FLIP_ANNOUNCED: bool = False


def _resolve_log_path(project_dir: Path, phase: str) -> Path:
    return Path(project_dir) / "phases" / phase / "dispatch-log.jsonl"


def _get_strict_after_date() -> date:
    raw = os.environ.get("WG_GATE_RESULT_STRICT_AFTER", "").strip()
    if not raw:
        return DEFAULT_STRICT_AFTER
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        sys.stderr.write(
            "[wicked-garden:gate-result] WG_GATE_RESULT_STRICT_AFTER "
            f"value {raw!r} is not YYYY-MM-DD; falling back to "
            f"{DEFAULT_STRICT_AFTER.isoformat()}.\n"
        )
        return DEFAULT_STRICT_AFTER


def _dispatch_check_disabled() -> bool:
    """Return True when ``WG_GATE_RESULT_DISPATCH_CHECK=off`` is set.

    Emits a stderr WARN on every invocation. Auto-expires at strict-after.
    """
    raw = os.environ.get("WG_GATE_RESULT_DISPATCH_CHECK", "")
    if raw.strip().lower() != "off":
        return False
    expires = _get_strict_after_date()
    today = datetime.now(timezone.utc).date()
    if today >= expires:
        sys.stderr.write(
            "[wicked-garden:gate-result] WG_GATE_RESULT_DISPATCH_CHECK=off "
            f"is EXPIRED (strict-after={expires.isoformat()}). Flag ignored; "
            "dispatch-log check remains ACTIVE.\n"
        )
        return False
    sys.stderr.write(
        "[wicked-garden:gate-result] WARN: dispatch-log check DISABLED via "
        "WG_GATE_RESULT_DISPATCH_CHECK=off. Orphan gate-results allowed; "
        f"auto-expires {expires.isoformat()}.\n"
    )
    return True


def _emit_deprecation_once(project_dir: Path, phase: str, *, reason: str) -> None:
    key = (str(project_dir), phase)
    if key in _DEPRECATION_EMITTED:
        return
    _DEPRECATION_EMITTED.add(key)
    sys.stderr.write(
        "[wicked-garden:gate-result] WARN: gate-result for phase "
        f"{phase!r} has no matching dispatch-log entry "
        f"({reason}). Accepting under the soft-deprecation window; "
        "the result will REJECT after "
        f"{_get_strict_after_date().isoformat()}. "
        "Run /wicked-garden:crew:migrate-gates to backfill.\n"
    )


def _emit_flip_announcement_once(flip_date: date) -> None:
    global _STRICT_FLIP_ANNOUNCED
    if _STRICT_FLIP_ANNOUNCED:
        return
    _STRICT_FLIP_ANNOUNCED = True
    sys.stderr.write(
        "[wicked-garden:gate-result] strict-dispatch mode is now ACTIVE as "
        f"of {flip_date.isoformat()}. Missing dispatch-log entries will "
        "REJECT gate-results. Override with "
        "WG_GATE_RESULT_STRICT_AFTER=<future-date> if production rollback "
        "is needed. See docs/threat-models/gate-result-ingestion.md §6 "
        "for owner handoff.\n"
    )


# ---------------------------------------------------------------------------
# Append point (called from phase_manager._dispatch_gate_reviewer helpers)
# ---------------------------------------------------------------------------


def append(
    project_dir: Path,
    phase: str,
    *,
    reviewer: str,
    gate: str,
    dispatch_id: str,
    dispatcher_agent: str = "wicked-garden:crew:phase-manager",
    expected_result_path: str = "gate-result.json",
    dispatched_at: Optional[str] = None,
) -> None:
    """Append one dispatch record. Appending happens BEFORE dispatcher
    invocation so an out-of-band gate-result written by a rogue
    reviewer fails the orphan check (closes the TOCTOU window per
    CH-04 — orphan *detection*, not authentication).
    """
    path = _resolve_log_path(Path(project_dir), phase)
    record: Dict[str, Any] = {
        "reviewer": reviewer,
        "phase": phase,
        "gate": gate,
        "dispatched_at": dispatched_at or datetime.now(timezone.utc).isoformat(),
        "dispatcher_agent": dispatcher_agent,
        "expected_result_path": expected_result_path,
        "dispatch_id": dispatch_id,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as exc:
        # Non-fatal: dispatch can still proceed; downstream orphan check
        # will warn on the missing record.
        sys.stderr.write(
            "[wicked-garden:gate-result] dispatch-log append failed "
            f"(phase={phase}, reviewer={reviewer}): {exc}.\n"
        )


def read_entries(project_dir: Path, phase: str) -> List[Dict[str, Any]]:
    """Read dispatch-log entries for a phase. Malformed lines are
    skipped with a stderr note; callers see only valid records.
    """
    path = _resolve_log_path(Path(project_dir), phase)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for lineno, line in enumerate(fp, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    sys.stderr.write(
                        "[wicked-garden:gate-result] dispatch-log line "
                        f"{lineno} in {path} is malformed ({exc}); skipped.\n"
                    )
                    continue
                if isinstance(entry, dict):
                    out.append(entry)
    except OSError as exc:
        sys.stderr.write(
            "[wicked-garden:gate-result] dispatch-log read failed "
            f"(path={path}): {exc}.\n"
        )
    return out


def read_latest(
    project_dir: Path, phase: str, gate: str
) -> Optional[Dict[str, Any]]:
    """Return the latest dispatch entry matching ``(phase, gate)``."""
    matches = [e for e in read_entries(project_dir, phase)
               if e.get("gate") == gate]
    if not matches:
        return None
    try:
        return max(matches, key=lambda e: e.get("dispatched_at", ""))
    except (TypeError, ValueError):
        return matches[-1]


# ---------------------------------------------------------------------------
# Orphan detection (called from gate_result_schema after schema pass)
# ---------------------------------------------------------------------------


def check_orphan(
    parsed: Dict[str, Any],
    project_dir: Path,
    phase: str,
) -> None:
    """Detect gate-results without a matching dispatch-log entry.

    Soft-window behavior:
      - before strict-after: emit warn-once per (project_dir, phase),
        write an audit entry, and RETURN (accept). The caller treats
        the result as valid but unverified.
      - on/after strict-after: raise
        :class:`GateResultAuthorizationError` so the caller rejects.

    Never authenticates (see CH-04). Matching entries share
    ``(reviewer, phase, gate)`` and have ``dispatched_at <= recorded_at``.
    """
    if _dispatch_check_disabled():
        return

    reviewer = parsed.get("reviewer") or ""
    recorded_at = parsed.get("recorded_at") or ""
    gate = parsed.get("gate") or ""

    entries = read_entries(Path(project_dir), phase)

    def _match(entry: Dict[str, Any]) -> bool:
        if entry.get("reviewer") != reviewer:
            return False
        if entry.get("phase") != phase:
            return False
        if gate and entry.get("gate") and entry.get("gate") != gate:
            return False
        entry_when = entry.get("dispatched_at") or ""
        # Lexicographic compare works on ISO-8601 with identical offset;
        # crew writes UTC always. Missing values fail the match.
        if not entry_when or not recorded_at:
            return False
        return entry_when <= recorded_at

    if any(_match(e) for e in entries):
        return  # matched — the result is verified-orphan-free.

    today = datetime.now(timezone.utc).date()
    flip_date = _get_strict_after_date()
    if today >= flip_date:
        _emit_flip_announcement_once(flip_date)
        raise GateResultAuthorizationError(
            "unauthorized-gate-result:no-dispatch-record",
            offending_field="reviewer",
            offending_value_excerpt=reviewer[:256],
        )

    # Soft window — warn once + let caller decide (normally: accept,
    # write audit entry with event=unauthorized_dispatch_accepted_legacy).
    _emit_deprecation_once(Path(project_dir), phase,
                           reason=f"reviewer={reviewer}")
    raise GateResultAuthorizationError(
        "unauthorized-gate-result:no-dispatch-record",
        offending_field="reviewer",
        offending_value_excerpt=reviewer[:256],
    )


__all__ = [
    "DEFAULT_STRICT_AFTER",
    "append",
    "read_entries",
    "read_latest",
    "check_orphan",
]
