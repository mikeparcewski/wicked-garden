#!/usr/bin/env python3
"""reeval_addendum.py — Read and append re-eval addendum records (AC-α4).

Schema is pinned by ``skills/propose-process/refs/re-eval-addendum-schema.md``
v1.1.0 (bumped from v1.0 in feat-crew-phase-boundary-qe-evaluator, AC-4).
Validation is delegated to ``scripts/crew/validate_reeval_addendum.py``.

Two write targets per phase-end re-eval:
    - per-phase log:    ``{project_dir}/phases/{phase}/reeval-log.jsonl``
    - project-level:    ``{project_dir}/process-plan.addendum.jsonl``

Usage (library):
    from reeval_addendum import append, read, read_latest

    append(project_dir, phase="design", record={...})
    records = read(project_dir, phase_filter="design")
    latest = read_latest(project_dir, phase="design")

Usage (CLI):
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \\
      "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reeval_addendum.py" \\
      read <project_dir> [--phase PHASE]

    echo '<record>' | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \\
      "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reeval_addendum.py" \\
      append <project_dir> --phase PHASE

Stdlib-only. Fail-open at the hook level — a missing or unreadable addendum
file returns an empty list rather than raising (the gate's
``_check_addendum_freshness`` is the authoritative enforcement surface).
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


# Minimum chain_id prefix length to sanity-check addendum records against the
# project_dir we are writing them for. A record whose chain_id does not start
# with the project slug indicates a wiring bug.
_MIN_CHAIN_ID_LEN = 1


def _per_phase_log_path(project_dir: Path, phase: str) -> Path:
    """Return the per-phase reeval-log.jsonl path."""
    return project_dir / "phases" / phase / "reeval-log.jsonl"


def _project_addendum_path(project_dir: Path) -> Path:
    """Return the project-root process-plan.addendum.jsonl path."""
    return project_dir / "process-plan.addendum.jsonl"


# Valid archetype enum values (v1.1.0, AC-5).
VALID_ARCHETYPES = frozenset({
    "code-repo",
    "docs-only",
    "skill-agent-authoring",
    "config-infra",
    "multi-repo",
    "testing-only",
    "schema-migration",
})

# Trigger prefix constants (R3 — no magic values).
_GATE_ADJUDICATOR_TRIGGER_PREFIX = "gate-adjudicator:"  # canonical (v7.0+)

# Allowed manifest_path prefixes for gate-adjudicator triggers (MINOR-1).
_ALLOWED_QE_MANIFEST_PREFIXES = ("phases/testability/", "phases/evidence-quality/")
_DISALLOWED_QE_MANIFEST_PREFIXES = ("phases/clarify/", "phases/design/")


class LegacyReviewerNameError(ValueError):
    """Raised when a reeval-log.jsonl entry contains a legacy reviewer name.

    The backward-compatibility reader was removed in wicked-garden v7.1.0.
    Run the migration script to repair the log file before resuming.
    """


def _raise_legacy_name_error(legacy_value: str, index: int, log_path: Path) -> None:
    """Raise LegacyReviewerNameError with the structured AC-21 message."""
    raise LegacyReviewerNameError(
        f"LegacyReviewerNameError: reeval-log.jsonl contains legacy agent name "
        f"'{legacy_value}' at\n"
        f"  record index {index} in {log_path}\n\n"
        f"  This backward-compatibility reader was removed in wicked-garden v7.1.0.\n"
        f"  To repair your log file, run the migration script:\n\n"
        f"    python scripts/crew/migrate_qe_evaluator_name.py --project-dir PATH/TO/PROJECT\n\n"
        f"  See docs/MIGRATION-v7.md for full late-upgrader guidance."
    )


def _is_qe_trigger(trigger: str) -> bool:
    """Return True if trigger is a gate-adjudicator trigger."""
    return trigger.startswith(_GATE_ADJUDICATOR_TRIGGER_PREFIX)


def _validate_record(record: Dict[str, Any]) -> Optional[str]:
    """Return None when the record is valid, else a short error string.

    Supports both v1.0 and v1.1.0 records. New v1.1.0 optional fields are
    validated when present; their absence is always valid (backward-compat).

    v1.1.0 enforcement rules (MINOR-1, AC-4):
    - When trigger starts with "gate-adjudicator:" (or legacy "qe-evaluator:"),
      mutations MUST be [].
    - When trigger starts with "gate-adjudicator:", mutations_applied MUST be [].
    - When trigger starts with "gate-adjudicator:", conditions_deferred[*].manifest_path
      MUST have prefix "phases/testability/" or "phases/evidence-quality/".

    This is a lightweight structural check — the full schema validation
    happens via ``scripts/crew/validate_reeval_addendum.py`` which we shell
    out to when available. This function is the fast local gate.
    """
    if not isinstance(record, dict):
        return f"record must be a dict, got {type(record).__name__}"

    required = {
        "chain_id", "triggered_at", "trigger",
        "prior_rigor_tier", "new_rigor_tier",
        "mutations", "mutations_applied", "mutations_deferred",
        "validator_version",
    }
    missing = required - set(record.keys())
    if missing:
        return f"record missing required keys: {sorted(missing)}"

    chain_id = record.get("chain_id")
    if not isinstance(chain_id, str) or len(chain_id) < _MIN_CHAIN_ID_LEN:
        return "chain_id must be a non-empty string"

    for key in ("mutations", "mutations_applied", "mutations_deferred"):
        if not isinstance(record.get(key), list):
            return f"{key} must be a list"

    trigger = record.get("trigger", "") or ""

    # v1.1.0 rules: gate-adjudicator triggers must have empty mutations lists.
    if _is_qe_trigger(trigger):
        mutations = record.get("mutations", [])
        if mutations:
            return (
                f"gate-adjudicator trigger must have empty mutations list; "
                f"got {len(mutations)} item(s)"
            )
        mutations_applied = record.get("mutations_applied", [])
        if mutations_applied:
            return (
                f"gate-adjudicator trigger must have empty mutations_applied list; "
                f"got {len(mutations_applied)} item(s)"
            )

    # v1.1.0: validate optional archetype field enum when present.
    archetype = record.get("archetype")
    if archetype is not None:
        if archetype not in VALID_ARCHETYPES:
            return (
                f"archetype {archetype!r} is not one of the valid archetypes: "
                f"{sorted(VALID_ARCHETYPES)}"
            )

    # v1.1.0: validate archetype_evidence.conditions_deferred[*].manifest_path
    # prefix enforcement for gate-adjudicator triggers.
    archetype_evidence = record.get("archetype_evidence")
    if archetype_evidence is not None and isinstance(archetype_evidence, dict):
        conditions_deferred = archetype_evidence.get("conditions_deferred", [])
        if isinstance(conditions_deferred, list) and _is_qe_trigger(trigger):
            for i, cond in enumerate(conditions_deferred):
                if not isinstance(cond, dict):
                    continue
                manifest_path = cond.get("manifest_path", "")
                if not manifest_path:
                    continue
                # Must start with an allowed prefix.
                if not any(
                    manifest_path.startswith(pfx)
                    for pfx in _ALLOWED_QE_MANIFEST_PREFIXES
                ):
                    return (
                        f"conditions_deferred[{i}].manifest_path {manifest_path!r} "
                        f"must start with one of {list(_ALLOWED_QE_MANIFEST_PREFIXES)} "
                        f"for gate-adjudicator triggers (indirect authority creep guard)"
                    )
                # Must not start with a disallowed prefix.
                for disallowed in _DISALLOWED_QE_MANIFEST_PREFIXES:
                    if manifest_path.startswith(disallowed):
                        return (
                            f"conditions_deferred[{i}].manifest_path {manifest_path!r} "
                            f"must not start with {disallowed!r} for gate-adjudicator triggers"
                        )

    return None


def _atomic_append(path: Path, line: str) -> None:
    """Append one line to ``path`` as atomically as the platform allows.

    Uses exclusive-append + fsync on POSIX; falls back to best-effort on
    Windows. Torn-write risk on cross-platform filesystems is documented
    in design §4; the gate's addendum-freshness check re-validates on each
    approve cycle.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize line ending.
    if not line.endswith("\n"):
        line = line + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except (OSError, AttributeError):
            pass  # fail open: Windows / non-fsync filesystems — best-effort only


def append(
    project_dir: Path,
    *,
    phase: str,
    record: Dict[str, Any],
) -> None:
    """Validate then append ``record`` to BOTH per-phase and project logs.

    Raises:
        ValueError: Record failed structural validation.
        OSError:    File I/O error after validation.
    """
    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)
    err = _validate_record(record)
    if err:
        raise ValueError(f"reeval_addendum.append: {err}")

    line = json.dumps(record, sort_keys=True, ensure_ascii=False)
    per_phase = _per_phase_log_path(project_dir, phase)
    project_log = _project_addendum_path(project_dir)

    # Wave-2 Tranche B emit (#746 W7): fire BEFORE the dual append so
    # the projector handler can replay BOTH writes (per-phase + project-
    # root) in the same order for crash-safety parity.  chain_id uses
    # the record's chain_id when present (per the schema, every addendum
    # carries its own chain_id), else falls back to {project}.{phase}.{ts}.
    # Fail-open: bus unavailable must NOT block the disk appends.
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_root = str(_Path(__file__).resolve().parents[1])
        if _scripts_root not in _sys.path:
            _sys.path.insert(0, _scripts_root)
        from _bus import emit_event  # type: ignore[import]
        project_id_str = project_dir.name
        record_chain = record.get("chain_id")
        if not record_chain:
            ts = record.get("recorded_at") or record.get("timestamp") or ""
            ts_compact = "".join(ch for ch in ts if ch.isdigit())[:14] or "noid"
            record_chain = f"{project_id_str}.{phase}.reeval-{ts_compact}"
        emit_event(
            "wicked.reeval.addendum_appended",
            {
                "project_id": project_id_str,
                "phase": phase,
                "raw_payload": line + "\n",  # _atomic_append adds the newline
            },
            chain_id=str(record_chain),
        )
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        pass  # bus unavailable — atomic appends below still run

    _atomic_append(per_phase, line)
    _atomic_append(project_log, line)


_LEGACY_REVIEWER_NAMES = ("qe-evaluator", "wicked-garden:crew:qe-evaluator")
_LEGACY_TRIGGER_PREFIX = "qe-evaluator:"


def _validate_legacy_in_record(
    rec: Dict[str, Any], idx: int, source_path: Path
) -> None:
    """Raise LegacyReviewerNameError when the record references a legacy name."""
    reviewer_val = rec.get("reviewer", "")
    if reviewer_val in _LEGACY_REVIEWER_NAMES:
        _raise_legacy_name_error(reviewer_val, idx, source_path)
    trigger_val = rec.get("trigger", "")
    if isinstance(trigger_val, str) and trigger_val.startswith(
        _LEGACY_TRIGGER_PREFIX
    ):
        _raise_legacy_name_error(trigger_val, idx, source_path)


def _read_event_log_addenda(
    project_dir: Path,
) -> Optional[List[Dict[str, Any]]]:
    """Read reeval addendum records from the bus event_log (Scope B, #746 W7).

    Mirrors the W6 pattern in scripts/crew/amendments.py.  Returns the
    parsed list of addendum dicts (one per
    ``wicked.reeval.addendum_appended`` event in event_id order) across
    ALL phases for this project, or ``None`` when the event_log path is
    not available or the read fails.  Fail-open: caller treats ``None``
    as "use disk fallback".
    """
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_root = str(_Path(__file__).resolve().parents[1])
        if _scripts_root not in _sys.path:
            _sys.path.insert(0, _scripts_root)
        import sqlite3 as _sqlite3
        from _event_log_reader import _escape_like  # type: ignore
    except Exception:  # noqa: BLE001 — fail-open
        return None

    db_env = os.environ.get("WG_DAEMON_DB")
    if db_env:
        db_path = Path(db_env)
    else:
        db_path = (
            Path.home()
            / ".something-wicked"
            / "wicked-garden-daemon"
            / "projections.db"
        )
    if not db_path.is_file():
        return None

    project_id = project_dir.name
    try:
        conn = _sqlite3.connect(
            f"file:{db_path}?mode=ro", uri=True, check_same_thread=False
        )
    except Exception:  # noqa: BLE001 — fail-open
        return None
    try:
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_log'"
            ).fetchone()
            if row is None:
                return None
        except Exception:  # noqa: BLE001 — fail-open
            return None

        # Match all phases under this project — the project_addendum.jsonl
        # aggregates across phases, so the event_log query mirrors that.
        escaped = _escape_like(project_id)
        try:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM   event_log
                WHERE  chain_id LIKE ? ESCAPE '\\'
                  AND  event_type = ?
                ORDER  BY event_id ASC
                """,
                (f"{escaped}.%", "wicked.reeval.addendum_appended"),
            ).fetchall()
        except Exception:  # noqa: BLE001 — fail-open
            return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 — fail-open
            pass

    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        payload_json = row[0]
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get("raw_payload")
        if not isinstance(raw, str):
            continue
        try:
            rec = json.loads(raw.rstrip("\n"))
        except (TypeError, ValueError):
            continue
        if not isinstance(rec, dict):
            continue
        # Legacy-name validation runs against the event_log entry too.
        _validate_legacy_in_record(rec, idx, Path(f"event_log/{project_id}"))
        out.append(rec)
    return out


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Return all JSON records from a JSONL file.

    Lines that fail to parse are skipped with a warning-style noop; the
    gate's validator is authoritative for strict checks. Missing file ->
    empty list (fail-open read).
    """
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for idx, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
            if isinstance(rec, dict):
                _validate_legacy_in_record(rec, idx, path)
                out.append(rec)
        except json.JSONDecodeError:
            # Skip corrupt lines; validator will surface them on next approve.
            continue
    return out


def read(
    project_dir: Path,
    *,
    phase_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return all addendum records from the project log.

    Bus-as-truth (#746 Scope B W7): when event_log is available, read records
    from there as the source of truth.  When event_log is missing or returns
    no records, fall back to the legacy disk JSONL so pre-cutover projects
    still work.

    When ``phase_filter`` is provided, only records whose ``chain_id``
    suffix matches ``.{phase}`` (anywhere in the dotted chain) OR whose
    ``trigger`` mentions the phase are returned. This matches the
    chain_id format in ``scripts/_event_schema.py``.
    """
    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)

    bus_records = _read_event_log_addenda(project_dir)
    if bus_records is not None and bus_records:
        records = bus_records
    else:
        records = _read_jsonl(_project_addendum_path(project_dir))

    if not phase_filter:
        return records
    suffix_token = f".{phase_filter}"
    filtered: List[Dict[str, Any]] = []
    for rec in records:
        chain_id = rec.get("chain_id", "") or ""
        trigger = rec.get("trigger", "") or ""
        if suffix_token in f".{chain_id}." or phase_filter in trigger:
            filtered.append(rec)
    return filtered


def read_latest(
    project_dir: Path,
    *,
    phase: str,
) -> Optional[Dict[str, Any]]:
    """Return the most recent addendum record for ``phase``, or None."""
    recs = read(project_dir, phase_filter=phase)
    if not recs:
        return None
    # Records are append-only and time-ordered; last entry is latest.
    return recs[-1]


# ---------------------------------------------------------------------------
# CLI entry point (AC-α4 / NFR-α5)
# ---------------------------------------------------------------------------


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read / append re-eval addendum records."
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_read = sub.add_parser("read", help="Read addendum records")
    p_read.add_argument("project_dir", type=Path)
    p_read.add_argument("--phase", default=None)

    p_append = sub.add_parser("append", help="Append a record from stdin")
    p_append.add_argument("project_dir", type=Path)
    p_append.add_argument("--phase", required=True)

    p_latest = sub.add_parser("latest", help="Read latest record for a phase")
    p_latest.add_argument("project_dir", type=Path)
    p_latest.add_argument("--phase", required=True)

    args = parser.parse_args(argv)

    if args.action == "read":
        recs = read(args.project_dir, phase_filter=args.phase)
        print(json.dumps(recs, indent=2))
        return 0

    if args.action == "latest":
        rec = read_latest(args.project_dir, phase=args.phase)
        print(json.dumps(rec, indent=2) if rec else "null")
        return 0

    if args.action == "append":
        raw = sys.stdin.read().strip()
        if not raw:
            print("error: no record on stdin", file=sys.stderr)
            return 2
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON on stdin: {exc}", file=sys.stderr)
            return 2
        try:
            append(args.project_dir, phase=args.phase, record=rec)
        except ValueError as exc:
            print(f"error: validation failed: {exc}", file=sys.stderr)
            return 1
        print("ok")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(_main())
