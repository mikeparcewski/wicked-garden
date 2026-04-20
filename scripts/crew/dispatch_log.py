"""Dispatch-log orphan detection + HMAC authentication for gate-result
ingestion (#471, AC-7 + #500).

Framing shift (#500): this module now promotes the original orphan
detection (CH-04) to **authentication** when the session supplies an
HMAC secret. Two layered contracts live here:

1. **Orphan detection** (CH-04, pre-#500): every gate-result must have a
   matching dispatch-log entry. An attacker who can write the gate-result
   but not the dispatch entry is caught.

2. **HMAC authentication** (#500): appended dispatch records carry an
   ``hmac`` field = ``hmac-sha256(secret, record_json)``. On load,
   ``check_orphan`` verifies the HMAC on matching entries; a mismatch
   raises :class:`DispatchLogTamperError`. Legacy entries (pre-#500,
   no ``hmac`` field) downgrade to orphan-detection only with a
   one-time-per-session stderr WARN.

Secret management: session-scoped. Stored in
``SessionState.dispatch_log_hmac_secret`` (``scripts/_session.py``).
Auto-generated on first use via ``secrets.token_hex(32)``. NEVER logged,
NEVER included in audit records.

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

import hashlib
import hmac
import json
import os
import secrets
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
# Legacy-entry warning: emit at most once per process (#500).
_LEGACY_HMAC_WARNED: bool = False


# ---------------------------------------------------------------------------
# #500 — HMAC signing (session-scoped authentication)
# ---------------------------------------------------------------------------


class DispatchLogTamperError(GateResultAuthorizationError):
    """Raised by ``check_orphan`` on HMAC mismatch for a non-legacy entry.

    Subclasses :class:`GateResultAuthorizationError` so existing
    ``except GateResultAuthorizationError:`` paths still catch it while
    callers that want to distinguish forgery from orphan-missing can
    match the subclass explicitly.
    """


# The secret used for HMAC computation. Process-local, never serialized
# to disk outside the session-state JSON (which already lives in a
# per-session temp file). Tests may set this via ``set_hmac_secret`` to
# produce deterministic fixtures; production callers leave it None and
# the first ``append`` call auto-generates a secret (or reads the
# SessionState-supplied one).
_HMAC_SECRET: Optional[str] = None


def set_hmac_secret(secret: Optional[str]) -> None:
    """Install an explicit HMAC secret for the current process.

    Passing ``None`` clears the secret; the next append will auto-generate
    one (or the caller may re-install a value from SessionState).

    Test-only entry-point in spirit, but also used by the
    phase_manager dispatcher to propagate the SessionState value.
    """
    global _HMAC_SECRET
    _HMAC_SECRET = secret


def _current_hmac_secret() -> str:
    """Resolve the active HMAC secret, generating one on first use.

    Resolution order:
      1. Explicit value set via :func:`set_hmac_secret`
      2. SessionState.dispatch_log_hmac_secret (if loadable)
      3. Auto-generated via ``secrets.token_hex(32)`` — which is then
         written back to SessionState so subsequent reads see the same
         secret.

    Never returns the empty string. Never raises.
    """
    global _HMAC_SECRET
    if _HMAC_SECRET:
        return _HMAC_SECRET

    # Try SessionState — tolerated failure (e.g., temp-dir unwritable
    # in tests). SessionState import is deferred to avoid a hard
    # dependency at module import time.
    try:
        from _session import SessionState  # type: ignore
        state = SessionState.load()
        persisted = getattr(state, "dispatch_log_hmac_secret", "") or ""
        if persisted:
            _HMAC_SECRET = persisted
            return _HMAC_SECRET
        generated = secrets.token_hex(32)
        try:
            state.update(dispatch_log_hmac_secret=generated)
        except Exception:  # pragma: no cover — defensive
            pass  # fail open — SessionState write failure, cache in-process only
        _HMAC_SECRET = generated
        return _HMAC_SECRET
    except Exception:
        # SessionState module unavailable (e.g., early-boot or isolated
        # test harness) — auto-generate an in-process secret.
        _HMAC_SECRET = secrets.token_hex(32)
        return _HMAC_SECRET


def _canonical_record_bytes(record: Dict[str, Any]) -> bytes:
    """Deterministic JSON encoding of a dispatch record for HMAC input.

    Uses ``sort_keys=True`` + no whitespace so verifier and signer
    produce identical bytes regardless of dict insertion order. The
    ``hmac`` field (if present) MUST be stripped before hashing so
    attaching the MAC does not alter the signed payload.
    """
    copy = {k: v for k, v in record.items() if k != "hmac"}
    return json.dumps(copy, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _compute_hmac(record: Dict[str, Any], secret: str) -> str:
    """Return hex-encoded HMAC-SHA256 of the record under ``secret``."""
    return hmac.new(
        secret.encode("utf-8"),
        _canonical_record_bytes(record),
        hashlib.sha256,
    ).hexdigest()


def _warn_legacy_entry_once() -> None:
    """Emit the one-time-per-process legacy-entry WARN."""
    global _LEGACY_HMAC_WARNED
    if _LEGACY_HMAC_WARNED:
        return
    _LEGACY_HMAC_WARNED = True
    sys.stderr.write(
        "[wicked-garden:gate-result] legacy dispatch-log entry "
        "(no HMAC); downgrading to orphan-detection only. Subsequent "
        "legacy entries in this session will be silent.\n"
    )


def _reset_state_for_tests() -> None:
    """Test-only helper — wipes process-local latches + secret so the
    next call path observes pristine state. NEVER called from production.
    """
    global _HMAC_SECRET, _LEGACY_HMAC_WARNED, _STRICT_FLIP_ANNOUNCED
    _HMAC_SECRET = None
    _LEGACY_HMAC_WARNED = False
    _STRICT_FLIP_ANNOUNCED = False
    _DEPRECATION_EMITTED.clear()


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
        "is needed.\n"
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
    CH-04 — orphan *detection*).

    #500: the appended record is signed via HMAC-SHA256 over the
    canonical record bytes under the session-scoped secret. The
    secret is resolved via :func:`_current_hmac_secret` (auto-generated
    on first use). The ``hmac`` hex string is stored alongside the
    record; verifier strips it before re-computing the MAC.
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

    # #500 — compute + attach HMAC. Signing failure must NOT prevent
    # append: the orphan check still catches a gate-result with no
    # matching entry, and a missing-hmac path is caught by the
    # legacy-fallback WARN on load. Fail-open per AC-7 design.
    try:
        secret = _current_hmac_secret()
        record["hmac"] = _compute_hmac(record, secret)
    except Exception as exc:  # pragma: no cover — defensive
        sys.stderr.write(
            "[wicked-garden:gate-result] dispatch-log HMAC signing failed "
            f"(phase={phase}, reviewer={reviewer}): {exc}. Entry appended "
            "without HMAC; verifier will downgrade to orphan-detection.\n"
        )

    # #505 — rotate BEFORE writing each record. Cheap stat() check;
    # failure is non-fatal (rotate_if_needed is fail-open). Lazy import
    # so dispatch still works if log_retention is missing.
    try:
        from log_retention import rotate_if_needed  # type: ignore
        rotate_if_needed(path)
    except ImportError:  # pragma: no cover — defensive
        pass  # fail-open: rotation module unavailable, append continues unbounded

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
# HMAC verification helper (#500)
# ---------------------------------------------------------------------------


def _verify_hmac_or_raise(
    entry: Dict[str, Any],
    *,
    reviewer: str,
) -> None:
    """Verify the HMAC on a matched dispatch entry.

    Policy:
      - Entry has ``hmac`` field: recompute under the session secret.
        Mismatch raises :class:`DispatchLogTamperError`. Constant-time
        compare via ``hmac.compare_digest``.
      - Entry has no ``hmac`` field (legacy, pre-#500): emit one-time
        stderr WARN and return — orphan-detection-only fallback.

    Never logs the secret. Never embeds the stored / computed MAC in
    the raised error beyond the standard "dispatch-log-hmac-mismatch"
    tag — a motivated attacker already has disk access, so leaking
    the hex is low-value but unnecessary.
    """
    stored = entry.get("hmac")
    if not isinstance(stored, str) or not stored:
        _warn_legacy_entry_once()
        return

    try:
        secret = _current_hmac_secret()
        expected = _compute_hmac(entry, secret)
    except Exception as exc:  # pragma: no cover — defensive
        # Secret resolution failed mid-verify: fail-CLOSED for a signed
        # entry (unlike append which fails open). A forger who blocked
        # secret resolution could otherwise bypass. This is the only
        # place we bias toward reject on infrastructure failure.
        raise DispatchLogTamperError(
            "dispatch-log-hmac-verify-infra-failure",
            offending_field="reviewer",
            offending_value_excerpt=reviewer[:256],
        ) from exc

    if not hmac.compare_digest(stored, expected):
        raise DispatchLogTamperError(
            "dispatch-log-hmac-mismatch",
            offending_field="reviewer",
            offending_value_excerpt=reviewer[:256],
        )


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

    matched_entries = [e for e in entries if _match(e)]
    if matched_entries:
        # #500 — authenticate the matched entry. Pick the most recent
        # (same tiebreak as read_latest) so legacy duplicates don't
        # shadow a signed record.
        try:
            matched = max(matched_entries,
                          key=lambda e: e.get("dispatched_at", ""))
        except (TypeError, ValueError):
            matched = matched_entries[-1]
        _verify_hmac_or_raise(matched, reviewer=reviewer)
        return  # matched + HMAC-ok (or legacy downgrade) — verified.

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
    "DispatchLogTamperError",
    "append",
    "check_orphan",
    "read_entries",
    "read_latest",
    "set_hmac_secret",
]
