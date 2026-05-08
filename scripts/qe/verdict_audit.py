#!/usr/bin/env python3
"""verdict_audit.py — Append-only audit log of review-archetype verdicts.

Every verdict the ``review`` archetype emits gets a one-line JSONL
record in ``{project_dir}/audit/verdicts.jsonl``. The log is the
forensic record of who said what, when. No HMAC, no orphan detection
— this is steering-not-blocking territory. The log is for *replay*,
not for refusing advancement.

Restored in v11 from the deleted v6 ``gate_ingest_audit.py`` +
``dispatch_log.py``, slimmed (~600 LOC → ~140 LOC). HMAC signing was
the v6 dispatch-log's defense against rogue reviewer self-authorisation
in the universal pipeline. v11's review archetype has its own banned-
reviewer enforcement at the validation layer (verdict_schema.py); the
audit log just records what happened.

Stdlib-only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Append-only log writer
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _audit_log_path(project_dir: Path) -> Path:
    """{project_dir}/audit/verdicts.jsonl"""
    return Path(project_dir) / "audit" / "verdicts.jsonl"


def append_verdict(
    project_dir: Path,
    *,
    verdict: Dict[str, Any],
    archetype: Optional[str] = None,
    phase: Optional[str] = None,
    source_path: Optional[str] = None,
) -> Path:
    """Append a verdict record to the audit log.

    The record carries:
      - recorded_at (ISO-8601 UTC, when the audit was written)
      - archetype (e.g. 'review', 'build', 'migrate')
      - phase (the archetype phase that produced the verdict)
      - source_path (path to the verdict.json this audits, if any)
      - verdict_field, reviewer, score (canonical fields from the verdict)
      - raw (the entire verdict dict, for replay fidelity)

    Returns the path to the audit log file.
    Fail-open: on any I/O error, prints to stderr and returns the path
    that was *attempted* but does not raise.
    """
    project_dir = Path(project_dir)
    log_path = _audit_log_path(project_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "recorded_at": _utc_now(),
        "archetype": archetype,
        "phase": phase,
        "source_path": source_path,
        "verdict": verdict.get("verdict"),
        "reviewer": verdict.get("reviewer"),
        "score": verdict.get("score"),
        "raw": verdict,
    }

    line = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    try:
        # Atomic append: open in text-append mode with line buffering.
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        import sys
        print(
            f"[verdict-audit] WARN: append failed for {log_path}: {exc}",
            file=sys.stderr,
        )
    return log_path


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------

def read_verdicts(
    project_dir: Path,
    *,
    archetype: Optional[str] = None,
    phase: Optional[str] = None,
    verdict_filter: Optional[str] = None,
) -> list:
    """Load all audit records, optionally filtered by archetype / phase /
    verdict. Returns [] when the log is missing or unreadable."""
    project_dir = Path(project_dir)
    log_path = _audit_log_path(project_dir)
    if not log_path.exists():
        return []
    out = []
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if archetype and rec.get("archetype") != archetype:
                continue
            if phase and rec.get("phase") != phase:
                continue
            if verdict_filter and rec.get("verdict") != verdict_filter:
                continue
            out.append(rec)
    except OSError:
        return out
    return out


__all__ = ["append_verdict", "read_verdicts"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="v11 verdict audit log tool.")
    sub = parser.add_subparsers(dest="action", required=True)

    a = sub.add_parser("append", help="Append a verdict from a JSON file.")
    a.add_argument("project_dir")
    a.add_argument("--verdict-file", required=True)
    a.add_argument("--archetype", default=None)
    a.add_argument("--phase", default=None)

    r = sub.add_parser("read", help="Read all audit records (JSON output).")
    r.add_argument("project_dir")
    r.add_argument("--archetype", default=None)
    r.add_argument("--phase", default=None)
    r.add_argument("--verdict", default=None)

    args = parser.parse_args()

    if args.action == "append":
        with open(args.verdict_file, "r", encoding="utf-8") as fh:
            verdict = json.load(fh)
        path = append_verdict(
            Path(args.project_dir),
            verdict=verdict,
            archetype=args.archetype,
            phase=args.phase,
            source_path=args.verdict_file,
        )
        print(json.dumps({"ok": True, "path": str(path)}))
    elif args.action == "read":
        records = read_verdicts(
            Path(args.project_dir),
            archetype=args.archetype,
            phase=args.phase,
            verdict_filter=args.verdict,
        )
        print(json.dumps(records, indent=2, default=str))
