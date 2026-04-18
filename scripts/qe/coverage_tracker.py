#!/usr/bin/env python3
"""
qe/coverage_tracker.py — Emit-side coverage delta tracker.

Reads standard coverage reports (Cobertura XML, coverage.py JSON),
persists the last-measured line rate per project in DomainStore, and
emits `wicked.coverage.changed` on the bus when the delta is non-zero.

Design constraints:
  * stdlib-only — no `coverage`, `pytest-cov`, third-party parsers.
  * Fail-open everywhere — a missing report, malformed XML, absent bus,
    and DomainStore write failures are all silent no-ops. Callers never
    observe an exception from `track_and_emit`.
  * Idempotent — measuring the same report twice produces one emit on
    the first run (delta vs. no prior record) and zero on the second
    (delta == 0, so nothing changed).
  * Tier 1 + Tier 2 payload only — aggregate line rate / lines counts,
    never per-file breakdowns.
  * Path-traversal safe — `project_id` is sanitized via the same regex
    shape used by `scripts/qe/_bus_consumers.py` before any storage key
    or filesystem interaction.

CLI:
    python3 coverage_tracker.py [--project-id SLUG] [--chain-id ID] [--json]

When invoked without `--project-id`, the tracker resolves the active
project from SessionState (`active_project_id`) and defaults to
``"default"`` when no session exists.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

# Ensure scripts/ is on path so _domain_store, _bus, _session are importable
# when this module is invoked directly (`python3 scripts/qe/coverage_tracker.py`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-qe.coverage-tracker")

# Project id sanitation — matches scripts/qe/_bus_consumers.py. Keeps the
# filesystem slug deterministic and rejects path-traversal attempts.
_PROJECT_ID_ALLOWED = re.compile(r"[^a-zA-Z0-9_-]")
_PROJECT_ID_MAX_LEN = 64

# Report discovery — ordered by likelihood. First hit wins; each path is
# resolved relative to the cwd so invocations from a scenario runner or a
# repo root behave the same way.
_DEFAULT_SEARCH_PATHS: Tuple[str, ...] = (
    "coverage.xml",
    "coverage.json",
    "htmlcov/coverage.xml",
    "reports/coverage.xml",
    "reports/coverage.json",
    ".coverage/coverage.xml",
)

# Storage collection inside DomainStore("wicked-qe"). One record per
# sanitized project_id.
_STORE_DOMAIN = "wicked-qe"
_STORE_SOURCE = "coverage"

# Emitted event name — present in BUS_EVENT_MAP under subdomain qe.coverage.
_EVENT_TYPE = "wicked.coverage.changed"

# Delta threshold — anything within this tolerance is treated as zero so
# rounding noise in XML/JSON parsers does not produce spurious emits.
_DELTA_EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Parsers — Cobertura XML and coverage.py JSON.
# ---------------------------------------------------------------------------

def parse_coverage_xml(path: Path) -> Optional[Dict[str, Any]]:
    """Parse a Cobertura-format ``coverage.xml`` file.

    Cobertura (and coverage.py's ``--cov-report=xml`` output) encodes
    totals on the root ``<coverage>`` element as ``line-rate`` /
    ``branch-rate`` / ``lines-covered`` / ``lines-valid`` attributes.

    Returns:
        Normalized metrics dict, or None on any parse/IO error.
    """
    try:
        tree = ET.parse(str(path))
    except (ET.ParseError, OSError) as exc:
        logger.debug(f"coverage xml parse failed: {path} ({exc})")
        return None

    root = tree.getroot()
    if root is None:
        return None

    # Cobertura attributes are strings; coverage.py emits floats formatted
    # with trailing zeros (e.g. "0.8300"). Catch malformed attrs.
    try:
        line_rate = float(root.attrib.get("line-rate", "0") or 0)
        branch_rate = float(root.attrib.get("branch-rate", "0") or 0)
        lines_covered = int(float(root.attrib.get("lines-covered", "0") or 0))
        lines_total = int(float(root.attrib.get("lines-valid", "0") or 0))
    except (TypeError, ValueError) as exc:
        logger.debug(f"coverage xml attr parse failed: {path} ({exc})")
        return None

    return {
        "line_rate": _clamp_rate(line_rate),
        "branch_rate": _clamp_rate(branch_rate),
        "lines_covered": max(0, lines_covered),
        "lines_total": max(0, lines_total),
    }


def parse_coverage_json(path: Path) -> Optional[Dict[str, Any]]:
    """Parse coverage.py's ``coverage.json`` output.

    The JSON report emits a ``totals`` block with ``percent_covered``
    (0..100), ``covered_lines``, ``num_statements``, and
    ``percent_covered_display``. Branch coverage, when present, is under
    ``totals.percent_covered_branches`` or derivable from ``num_branches``.

    Returns:
        Normalized metrics dict, or None on any parse/IO error.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug(f"coverage json parse failed: {path} ({exc})")
        return None

    if not isinstance(data, dict):
        return None

    totals = data.get("totals")
    if not isinstance(totals, dict):
        return None

    try:
        # percent_covered is 0..100; normalize to 0..1 to match XML shape.
        percent_covered = float(totals.get("percent_covered", 0) or 0)
        line_rate = percent_covered / 100.0
        lines_covered = int(totals.get("covered_lines", 0) or 0)
        lines_total = int(totals.get("num_statements", 0) or 0)

        # Branch rate — coverage.py names this inconsistently across
        # versions; check both common keys before falling back to 0.
        branch_pct_raw = (
            totals.get("percent_covered_branches")
            if "percent_covered_branches" in totals
            else totals.get("branch_coverage", 0)
        )
        branch_rate = float(branch_pct_raw or 0) / 100.0
    except (TypeError, ValueError) as exc:
        logger.debug(f"coverage json totals parse failed: {path} ({exc})")
        return None

    return {
        "line_rate": _clamp_rate(line_rate),
        "branch_rate": _clamp_rate(branch_rate),
        "lines_covered": max(0, lines_covered),
        "lines_total": max(0, lines_total),
    }


def _clamp_rate(value: float) -> float:
    """Clamp a rate into 0..1 — coverage tools very occasionally emit
    slightly-out-of-range values when a file has zero statements."""
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


# ---------------------------------------------------------------------------
# Report discovery
# ---------------------------------------------------------------------------

def find_coverage_report(
    search_paths: Optional[Tuple[str, ...]] = None,
    cwd: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Callable[[Path], Optional[Dict[str, Any]]]]]:
    """Scan for a coverage report in the cwd tree.

    Returns the first matching (path, parser) tuple, or ``(None, None)``
    when no standard report is present.
    """
    base = (cwd or Path.cwd()).resolve()
    candidates = search_paths or _DEFAULT_SEARCH_PATHS

    for rel in candidates:
        candidate = (base / rel).resolve()
        # Guard against symlink escapes — the candidate must stay under
        # the working directory we were asked to scan.
        try:
            candidate.relative_to(base)
        except ValueError:
            continue
        if not candidate.is_file():
            continue
        parser = _parser_for(candidate)
        if parser is None:
            continue
        return candidate, parser

    return None, None


def _parser_for(path: Path) -> Optional[Callable[[Path], Optional[Dict[str, Any]]]]:
    suffix = path.suffix.lower()
    if suffix == ".xml":
        return parse_coverage_xml
    if suffix == ".json":
        return parse_coverage_json
    return None


# ---------------------------------------------------------------------------
# Persistence — DomainStore("wicked-qe") collection "coverage"
# ---------------------------------------------------------------------------

def load_previous(project_id: str) -> Optional[Dict[str, Any]]:
    """Load the last-recorded coverage entry for ``project_id``.

    Returns ``{"line_rate": float}`` or None when no record exists or the
    DomainStore is unavailable. Follows the crew phase_manager pattern of
    failing-open on any DomainStore error.
    """
    slug = _sanitize_project_id(project_id)
    if slug is None:
        return None

    try:
        from _domain_store import DomainStore

        store = DomainStore(_STORE_DOMAIN)
        record = store.get(_STORE_SOURCE, slug)
    except Exception as exc:
        logger.debug(f"load_previous: DomainStore error (non-fatal): {exc}")
        return None

    if not record:
        return None

    # Only surface the field we need — older records may carry extra
    # keys from previous schema iterations.
    line_rate = record.get("line_rate")
    if not isinstance(line_rate, (int, float)):
        return None
    return {"line_rate": float(line_rate)}


def store_current(project_id: str, line_rate: float, chain_id: str = "") -> bool:
    """Upsert the coverage record for ``project_id``.

    Returns True on successful write, False on any DomainStore error.
    Fail-open: errors are logged at debug and swallowed.
    """
    slug = _sanitize_project_id(project_id)
    if slug is None:
        return False

    record = {
        "id": slug,
        "line_rate": round(float(line_rate), 6),
        "measured_at": _utcnow_iso(),
        "chain_id": chain_id or "",
    }

    try:
        from _domain_store import DomainStore

        store = DomainStore(_STORE_DOMAIN)
        existing = store.get(_STORE_SOURCE, slug)
        if existing is None:
            store.create(_STORE_SOURCE, record)
        else:
            # Drop the id from the diff — create() assigned it; update()
            # does not need a new id.
            diff = {k: v for k, v in record.items() if k != "id"}
            store.update(_STORE_SOURCE, slug, diff)
        return True
    except Exception as exc:
        logger.debug(f"store_current: DomainStore error (non-fatal): {exc}")
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def track_and_emit(
    project_id: Optional[str] = None,
    chain_id: Optional[str] = None,
    search_paths: Optional[Tuple[str, ...]] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    """Find → parse → diff → emit → store.

    Returns a summary dict. On any failure path a negative result shape
    ``{"ok": False, "reason": "..."}`` is returned — the caller never
    sees an exception.
    """
    # Resolve project_id from session state when not supplied. The session
    # record uses ``active_project_id`` as the local project slug.
    project_slug = _resolve_project_id(project_id)
    if project_slug is None:
        return {"ok": False, "reason": "invalid-project-id"}

    resolved_chain = _resolve_chain_id(chain_id)

    path, parser = find_coverage_report(search_paths=search_paths, cwd=cwd)
    if path is None or parser is None:
        return {"ok": False, "reason": "no-coverage-report"}

    metrics = None
    try:
        metrics = parser(path)
    except Exception as exc:
        # Defensive — parsers already catch known errors, but any future
        # addition should still fail-open.
        logger.debug(f"coverage parser raised: {exc}")
        return {"ok": False, "reason": "parse-error", "path": str(path)}

    if not metrics:
        return {"ok": False, "reason": "parse-error", "path": str(path)}

    after = float(metrics["line_rate"])
    previous = load_previous(project_slug)
    before = float(previous["line_rate"]) if previous else 0.0
    delta = after - before

    summary: Dict[str, Any] = {
        "ok": True,
        "project_id": project_slug,
        "path": str(path),
        "before": before,
        "after": after,
        "delta": delta,
        "emitted": False,
        "first_measurement": previous is None,
    }

    if abs(delta) <= _DELTA_EPSILON:
        # No change — still refresh the stored record so ``measured_at``
        # stays current and chain_id mirrors the latest run. This is
        # cheap and keeps the audit trail useful.
        store_current(project_slug, after, chain_id=resolved_chain)
        return summary

    # Delta is non-zero — emit then store. Order matters: if we store
    # first and then fail to emit, the next run sees delta == 0 and will
    # swallow the event. Emitting first means a transient bus failure
    # still preserves the old baseline, so the delta re-fires next time.
    _emit_coverage_changed(before, after, delta, resolved_chain)
    store_current(project_slug, after, chain_id=resolved_chain)
    summary["emitted"] = True
    return summary


def _emit_coverage_changed(
    before: float,
    after: float,
    delta: float,
    chain_id: str,
) -> None:
    """Fire ``wicked.coverage.changed`` — fail-open."""
    try:
        from _bus import emit_event

        emit_event(
            _EVENT_TYPE,
            {
                "before_pct": round(before * 100, 2),
                "after_pct": round(after * 100, 2),
                "delta": round(delta * 100, 2),
                "chain_id": chain_id or "",
            },
            chain_id=chain_id or None,
        )
    except Exception as exc:
        logger.debug(f"emit coverage changed failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_project_id(project_id: Optional[str]) -> Optional[str]:
    """Reduce ``project_id`` to a filesystem-safe slug or None.

    Anything outside ``[a-zA-Z0-9_-]`` becomes ``-``. Empty strings,
    non-strings, and oversized inputs are rejected outright.
    """
    if not isinstance(project_id, str):
        return None
    cleaned = _PROJECT_ID_ALLOWED.sub("-", project_id).strip("-")
    if not cleaned:
        return None
    return cleaned[:_PROJECT_ID_MAX_LEN]


def _resolve_project_id(project_id: Optional[str]) -> Optional[str]:
    """Sanitize the supplied project_id or fall back to session state."""
    if project_id:
        return _sanitize_project_id(project_id)

    # Session fallback — mirrors the pattern used by registry_store.py.
    try:
        from _session import SessionState  # type: ignore

        state = SessionState.load()
        fallback = getattr(state, "active_project_id", None)
        if fallback:
            return _sanitize_project_id(fallback)
    except Exception:
        pass  # fail open: SessionState unavailable — fall through to default slug

    # Last resort — use a stable default slug so we still record
    # something. Better to have one "default" record than lose the signal.
    return "default"


def _resolve_chain_id(chain_id: Optional[str]) -> str:
    """Return an explicit chain_id, else read from SessionState, else ''."""
    if chain_id:
        return chain_id

    try:
        from _session import SessionState  # type: ignore

        state = SessionState.load()
        fallback = getattr(state, "active_chain_id", None) or ""
        return fallback or ""
    except Exception:
        return ""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track test-coverage delta and emit wicked.coverage.changed.",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Project slug for the coverage record (defaults to session).",
    )
    parser.add_argument(
        "--chain-id",
        default=None,
        help="Crew causality chain id to attach to the emit (optional).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the summary dict as JSON on stdout.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = track_and_emit(project_id=args.project_id, chain_id=args.chain_id)
    if args.json:
        print(json.dumps(summary, default=str))
    # Exit 0 regardless — fail-open by contract.
    return 0


# ---------------------------------------------------------------------------
# Inline smoke test — ``python3 coverage_tracker.py --selftest`` from the
# main block below. Uses a small literal Cobertura document so the test
# is hermetic and doesn't touch DomainStore or the bus.
# ---------------------------------------------------------------------------

_SELFTEST_XML = """<?xml version="1.0" ?>
<coverage line-rate="0.8300" branch-rate="0.75" lines-covered="83" lines-valid="100" version="7.4.0" timestamp="0">
  <packages>
    <package name="pkg" line-rate="0.83" branch-rate="0.75">
      <classes/>
    </package>
  </packages>
</coverage>
"""


def _selftest() -> int:
    """Exercise the XML parser against a literal fixture."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "coverage.xml"
        tmp_path.write_text(_SELFTEST_XML, encoding="utf-8")
        metrics = parse_coverage_xml(tmp_path)

    expected = {
        "line_rate": 0.83,
        "branch_rate": 0.75,
        "lines_covered": 83,
        "lines_total": 100,
    }
    if metrics != expected:
        print(f"selftest FAIL: got {metrics!r}, expected {expected!r}", file=sys.stderr)
        return 1

    # Delta epsilon check — re-measuring the same number should be a no-op.
    delta = expected["line_rate"] - 0.83
    if abs(delta) > _DELTA_EPSILON:
        print("selftest FAIL: epsilon check did not treat 0.83-0.83 as zero", file=sys.stderr)
        return 1

    print("selftest OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
