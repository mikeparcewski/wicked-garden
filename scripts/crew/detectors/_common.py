#!/usr/bin/env python3
"""
crew/detectors/_common.py — shared infrastructure for steering detectors.

Centralizes the bits every detector needs:

  * Bus binary resolution + reachability probe (mirrors ``sensitive_path.py``
    + ``steering_tail.py`` — same npx-status-probe-then-fall-back ladder).
  * Schema-validate-then-emit helper that drops invalid payloads with a stderr
    warning and returns a count of successfully emitted events.
  * Thread-pooled subprocess emit (``_EMIT_MAX_WORKERS=8`` — same value PR-2
    proved out, since wicked-bus has no batch flag).
  * ISO8601 timestamp formatter so detectors don't roll their own.
  * Standard CLI argument additions (``--session-id``, ``--project-slug``,
    ``--dry-run``) so every detector exposes the same surface.

Pure stdlib. Importable from any detector under ``scripts/crew/detectors/``.

Design rules:

  * Every payload that lands on the bus MUST have passed
    ``crew.steering_event_schema.validate_payload`` for the supplied
    ``event_type``.
  * Bus unreachable → fail-open. Log to stderr, return 0. Never raise out of
    ``emit_validated_payloads``.
  * Subprocess timeout / OSError → log + count as failure. Never raise.
  * Detectors that need extra CLI args extend the parser returned by
    ``build_standard_arg_parser`` rather than re-declaring the standard set.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

# Allow running detector files directly as scripts.
_REPO_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_REPO_SCRIPTS))

from crew.steering_event_schema import validate_payload  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Bus event domain — every wicked-garden detector emits under this domain.
EVENT_DOMAIN: str = "wicked-garden"

#: Reachability probe timeout. 5s mirrors ``sensitive_path.py`` and the
#: plugin-wide budget for status checks.
BUS_PROBE_TIMEOUT_SECONDS: float = 5.0

#: Per-event emit timeout. Network roundtrip + SQLite write — give 10s of
#: headroom over the 5s status probe.
BUS_EMIT_TIMEOUT_SECONDS: float = 10.0

#: Worker count for the parallel emit thread pool. ``wicked-bus emit`` takes
#: one event per call (no batch/stdin flag), so we collapse N serial spawns
#: into a small pool. 8 keeps SQLite write contention low.
EMIT_MAX_WORKERS: int = 8


# ---------------------------------------------------------------------------
# Bus resolution + reachability
# ---------------------------------------------------------------------------

def resolve_bus_command() -> Optional[List[str]]:
    """Return argv prefix for invoking wicked-bus, or ``None`` if unreachable.

    Mirrors the resolution ladder used by ``sensitive_path.py`` and
    ``steering_tail.py``:

      1. Direct ``wicked-bus`` binary on ``PATH`` — fastest path, no probe.
      2. ``npx wicked-bus`` — but only after ``npx wicked-bus status --json``
         exits 0. Without the probe, ``npx`` may hang downloading the package
         on first invocation.

    Returns ``None`` if neither is available — callers MUST treat this as
    "bus is unreachable" and fail-open (warn + skip emit, do not raise).
    """
    direct = shutil.which("wicked-bus")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx is None:
        return None
    try:
        result = subprocess.run(
            [npx, "wicked-bus", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=BUS_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return [npx, "wicked-bus"]


# ---------------------------------------------------------------------------
# Validate-then-emit
# ---------------------------------------------------------------------------

def emit_validated_payloads(
    payloads: Sequence[dict],
    *,
    event_type: str,
    subdomain: str,
    bus_cmd: Optional[Sequence[str]] = None,
) -> int:
    """Validate every payload then push the survivors to wicked-bus.

    Args:
        payloads: Detector-produced payloads. May be empty (fast no-op).
        event_type: Bus ``event_type`` (e.g. ``wicked.steer.escalated``).
            Must be present in
            ``crew.steering_event_schema.KNOWN_EVENT_TYPES`` — the validator
            enforces this and rejects unknown types as hard errors.
        subdomain: Bus subdomain — by convention
            ``crew.detector.<detector-name>``.
        bus_cmd: Optional pre-resolved argv prefix. Tests inject their own;
            production callers leave this ``None`` to use
            ``resolve_bus_command``.

    Returns:
        Count of payloads that were successfully emitted (subprocess exit
        code 0). Schema failures, bus unreachable, subprocess timeouts, and
        non-zero exits all count as 0 — the contract is "every counted event
        landed on the bus and passed validation".

    Never raises — even on schema failure or OSError. The contract is
    fail-open so a misbehaving detector can never break the calling crew
    workflow.
    """
    if not payloads:
        return 0

    if bus_cmd is None:
        bus_cmd = resolve_bus_command()
    if bus_cmd is None:
        sys.stderr.write(
            "warn: wicked-bus is not installed or unreachable; "
            f"dropping {len(payloads)} steering event(s). "
            "Install via 'npm install -g wicked-bus' to enable steering events.\n"
        )
        return 0

    # Re-validate every payload up front. Defense in depth — even if the
    # detector validated, hand-crafted callers might pass garbage.
    valid_payloads: List[dict] = []
    for payload in payloads:
        errors, _warnings = validate_payload(event_type, payload)
        if errors:
            sys.stderr.write(
                f"warn: dropping invalid steering event: {errors}\n"
            )
            continue
        valid_payloads.append(payload)

    if not valid_payloads:
        return 0

    workers = min(EMIT_MAX_WORKERS, len(valid_payloads))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda ev: _emit_single_event(bus_cmd, event_type, subdomain, ev),
            valid_payloads,
        ))
    return sum(1 for ok in results if ok)


def _emit_single_event(
    bus_cmd: Sequence[str],
    event_type: str,
    subdomain: str,
    event_record: dict,
) -> bool:
    """Spawn one ``wicked-bus emit`` subprocess. ``True`` iff exit 0.

    Logs to stderr on failure and returns ``False`` — never raises. Used by
    ``emit_validated_payloads`` under a thread pool.
    """
    cmd = list(bus_cmd) + [
        "emit",
        "--type", event_type,
        "--domain", EVENT_DOMAIN,
        "--subdomain", subdomain,
        "--payload", json.dumps(event_record, default=str, separators=(",", ":")),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BUS_EMIT_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        sys.stderr.write(
            f"warn: wicked-bus emit failed for steering event: {exc}\n"
        )
        return False
    if result.returncode != 0:
        sys.stderr.write(
            f"warn: wicked-bus emit returned {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}\n"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_iso8601(now: Optional[datetime] = None) -> str:
    """Return an ISO8601 ``YYYY-MM-DDTHH:MM:SSZ`` string in UTC.

    ``now`` is overridable for tests; production callers pass nothing and
    get ``datetime.now(timezone.utc)``.
    """
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_non_empty_string(value: object, field_name: str) -> str:
    """Raise ``ValueError`` if ``value`` is not a non-empty string.

    Centralizes the ``session_id`` / ``project_slug`` guard every detector
    needs at the start of ``detect_*``.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def build_standard_arg_parser(
    prog: str,
    description: str,
) -> argparse.ArgumentParser:
    """Return an argparse parser preloaded with the detector-standard args.

    Adds ``--session-id``, ``--project-slug``, and ``--dry-run``. Detectors
    add their signal-specific args on top of the returned parser.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--session-id",
        required=True,
        help="Session that produced the signal (required by schema).",
    )
    parser.add_argument(
        "--project-slug",
        required=True,
        help="Crew project slug (required by schema).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and print payloads to stdout but do NOT emit to "
            "wicked-bus."
        ),
    )
    return parser


__all__ = [
    "EVENT_DOMAIN",
    "BUS_PROBE_TIMEOUT_SECONDS",
    "BUS_EMIT_TIMEOUT_SECONDS",
    "EMIT_MAX_WORKERS",
    "resolve_bus_command",
    "emit_validated_payloads",
    "utc_iso8601",
    "require_non_empty_string",
    "build_standard_arg_parser",
]
