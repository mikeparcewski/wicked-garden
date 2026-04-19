"""Append-only audit log for gate-result ingestion (#471, AC-8).

Records every ``GateResultSchemaError`` / authorization rejection with
content-hashed excerpts — **never** raw offending values. The audit
log must not itself become a re-injection vector for tools that tail it
for observability.

Record schema (design §4.2):
    {
      "event": "schema_violation" | "sanitization_violation" |
               "unauthorized_dispatch" |
               "unauthorized_dispatch_accepted_legacy" |
               "malformed_json",
      "phase": str,
      "gate": str | null,
      "reason": str,
      "offending_field": str | null,
      "violation_snippet_hash": "sha256:<hex>",
      "file_sha256": "sha256:<hex>",
      "rejected_at": ISO-8601 UTC,
    }

Write failures are swallowed to stderr (AC-8 / design §4.4) — an audit
I/O bug must never gate ``_load_gate_result`` closed.

Stdlib-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_SCRIPTS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gate_result_constants import AUDIT_SNIPPET_HASH_MAX_BYTES  # noqa: E402


# B-2: a defense-in-depth cap on how much of the caller-provided ``reason``
# string we serialize onto disk. Upstream (``gate_result_schema``) is
# already supposed to hash-prefix any attacker-controlled content before it
# reaches this module — but the audit log is read by LLM-observability tools
# and must not become a re-injection vector if a future caller regresses
# and passes a raw-content reason. The cap is conservative — enough room
# for a diagnostic tag + hash suffix, not enough for any meaningful
# prompt-injection payload.
_REASON_MAX_CHARS: int = 256


def _sanitize_reason(reason: Optional[str]) -> Optional[str]:
    """Truncate ``reason`` to a safe cap so a caller-side regression cannot
    smuggle adversarial content onto the audit log. Returns ``None`` for
    falsy input so existing JSON null shape is preserved.
    """
    if reason is None:
        return None
    if not isinstance(reason, str):
        return repr(reason)[:_REASON_MAX_CHARS]
    return reason[:_REASON_MAX_CHARS]


VALID_EVENT_TYPES: frozenset = frozenset({
    "schema_violation",
    "sanitization_violation",
    "unauthorized_dispatch",
    "unauthorized_dispatch_accepted_legacy",
    "malformed_json",
})


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_audit_path(project_dir: Path, phase: str) -> Path:
    return Path(project_dir) / "phases" / phase / "gate-ingest-audit.jsonl"


def append_audit_entry(
    project_dir: Path,
    phase: str,
    *,
    event: str,
    reason: str,
    offending_field: Optional[str] = None,
    offending_value: Any = None,
    raw_bytes: Optional[bytes] = None,
    gate: Optional[str] = None,
) -> None:
    """Append one record to the gate-ingest audit log.

    Never raises. On I/O failure a stderr warning fires and the caller
    continues (design §4.4).
    """
    if event not in VALID_EVENT_TYPES:
        # Unknown event — still log, but tag the shape for forensic review.
        event = f"unknown:{event}"

    # Hash the offending value (never the value itself) — audit-log
    # readers could tail this for observability and would otherwise
    # ingest attacker content.
    snippet_hash = "sha256:" + "0" * 64
    if offending_value is not None:
        try:
            text = offending_value if isinstance(offending_value, str) \
                else repr(offending_value)
            hashed = text.encode("utf-8", errors="replace")[
                :AUDIT_SNIPPET_HASH_MAX_BYTES
            ]
            snippet_hash = _sha256(hashed)
        except Exception:  # pragma: no cover — defensive
            pass  # fail open: hash unavailable leaves the zero-hash placeholder

    file_sha = "sha256:" + "0" * 64
    if raw_bytes is not None:
        try:
            file_sha = _sha256(raw_bytes)
        except Exception:  # pragma: no cover
            pass  # fail open: hash unavailable leaves the zero-hash placeholder

    record: Dict[str, Any] = {
        "event": event,
        "phase": phase,
        "gate": gate,
        # B-2: pass reason through the sanitizer — belt-and-suspenders cap
        # in case a caller regresses and hands us raw adversarial content.
        "reason": _sanitize_reason(reason),
        "offending_field": offending_field,
        "violation_snippet_hash": snippet_hash,
        "file_sha256": file_sha,
        "rejected_at": _utc_now_iso(),
    }

    audit_path = _resolve_audit_path(Path(project_dir), phase)

    # #505 — rotate BEFORE writing each record. Cheap stat() check; a
    # rotation failure is non-fatal (rotate_if_needed is fail-open).
    # Lazy import: audit-log must not break if log_retention is missing
    # (e.g., partial plugin install).
    try:
        from log_retention import rotate_if_needed  # type: ignore
        rotate_if_needed(audit_path)
    except ImportError:  # pragma: no cover — defensive
        pass  # fail-open: rotation module unavailable, append continues unbounded

    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as exc:
        sys.stderr.write(
            "[wicked-garden:gate-result] audit-log write failed "
            f"(phase={phase}, path={audit_path}): {exc}. Reject still "
            "propagates; the security decision is NOT bypassed by an "
            "audit-log I/O failure (design §4.4).\n"
        )


__all__ = [
    "VALID_EVENT_TYPES",
    "append_audit_entry",
]
