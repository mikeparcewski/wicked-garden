#!/usr/bin/env python3
"""Post-cutover reconciler — projection-vs-event drift detector.

Ships alongside ``scripts/crew/reconcile.py`` (v1) during the bus-cutover
window (#746).  v1 is deprecated when Site 5 lands and removed in release N+5.

See ``docs/v9/adr-reconcile-v2.md`` and ``docs/v9/bus-cutover-staging-plan.md``
§5 for the design contract this module implements.

Background
----------
After the bus cutover, ``wicked.gate.decided`` and companion events become the
source of truth.  On-disk artifacts (gate-result.json, dispatcher-report.md,
reviewer-report.md, etc.) are *projections* of those events, materialised by
the wicked-garden-daemon projector.  The drift question shifts from:

  "do the two task stores agree?" (reconcile.py / v1)

to:

  "does every event have its projection, and does every projection trace to
   an event?" (this module / v2)

Drift classes (§5 of the staging plan)
---------------------------------------
  projection-stale           — event ingested; projection not yet materialised
                                (projector lagging, crashed, or slow handler)
  event-without-projection   — event in event_log but no matching file on disk
                                (handler missing, raised, or targeted wrong path)
  projection-without-event   — file on disk but no event_log row corresponds
                                (direct-write bypassing the bus, or GC'd event
                                 whose projection file survived)

Hard constraints (mirror v1)
----------------------------
  - Stdlib only.
  - READ ONLY — never write to either store.
  - Fail-open — projector DB unavailable → return empty list, never raise.
  - Honor WG_DAEMON_DB env var for DB path resolution (same as synthetic_drift.py).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

# ---------------------------------------------------------------------------
# Drift type labels — module-level constants so test suites and downstream
# consumers reference them without string typos.
# ---------------------------------------------------------------------------

DRIFT_PROJECTION_STALE: str = "projection-stale"
DRIFT_EVENT_WITHOUT_PROJECTION: str = "event-without-projection"
DRIFT_PROJECTION_WITHOUT_EVENT: str = "projection-without-event"

# chain_id format: {slug}.{phase}[.{gate}] — minimum 2 dot-separated parts.
_MIN_CHAIN_ID_PARTS = 2

# Projector is considered lagging when pending-event backlog exceeds this count.
_LAG_EVENTS_THRESHOLD = 10

# ---------------------------------------------------------------------------
# Event types the projector is expected to materialise as on-disk artifacts.
# Maps event_type → (relative_projection_path_template, uses_phase_from_chain).
#
# For per-project + per-phase artifacts the template uses {slug} + {phase}.
# These are the primary bus-truth artifacts after cutover Site 3.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-event projection resolvers — function shape lets each event express
# CONDITIONAL file production based on payload, not just static mapping.
#
# Rationale (Site 5 / #746): ``wicked.gate.decided`` ALWAYS materialises
# gate-result.json but CONDITIONALLY materialises conditions-manifest.json
# (only when verdict is CONDITIONAL with a non-empty conditions list).
# A static ``Dict[str, FrozenSet[str]]`` cannot model this — it would
# either over-claim (drift on every APPROVE event missing the manifest)
# or under-claim (silent on the conditional case).  The resolver-function
# shape models the conditional production directly: each function inspects
# the payload and yields the paths the event is expected to produce, given
# the actual verdict.  See
# ``memory/workaround-vs-fix-stop-shaping-plans-around-bad-design.md`` for
# the structural-fix-vs-workaround rationale.
#
# Resolver signature:
#   (payload: Dict, phase: str, project_dir: Path) -> Iterable[Path]
# ---------------------------------------------------------------------------


def _resolve_gate_decided(
    payload: Dict[str, Any], phase: str, project_dir: Path,
) -> "list[Path]":
    """``wicked.gate.decided`` — gate-result.json always; conditions-manifest.json
    only on CONDITIONAL verdicts with a non-empty conditions list."""
    paths: "list[Path]" = [
        project_dir / "phases" / phase / "gate-result.json",
    ]
    data = payload.get("data") or {}
    verdict = data.get("result") or data.get("verdict")
    conditions = data.get("conditions") or []
    if verdict == "CONDITIONAL" and conditions:
        paths.append(
            project_dir / "phases" / phase / "conditions-manifest.json"
        )
    return paths


def _resolve_single_file(template: str):
    """Build a resolver for events that always produce exactly one file."""
    def _resolver(
        payload: Dict[str, Any], phase: str, project_dir: Path,
    ) -> "list[Path]":
        return [project_dir / template.replace("{phase}", phase)]
    _resolver.__name__ = f"_resolve_{template.replace('/', '_').replace('.', '_')}"
    return _resolver


_PROJECTION_RESOLVERS: Dict[str, Callable[[Dict[str, Any], str, Path], "list[Path]"]] = {
    # Phase gate decisions — payload-aware (gate-result.json + maybe manifest).
    "wicked.gate.decided": _resolve_gate_decided,
    # ``wicked.gate.blocked`` is a REJECT-state sentinel that does not
    # materialise a file (gate-result.json is already produced by the
    # preceding gate.decided emit).  Intentionally NOT in this dict so the
    # drift detector treats it as non-materialising.  Without this
    # exclusion, an event_log row with only gate.blocked + an on-disk
    # gate-result.json would silently pass projection-without-event
    # detection (false negative — Copilot finding on PR #782).
    # ``_gate_blocked`` stays registered in ``daemon/projector.py._HANDLERS``
    # for completeness; it just doesn't claim to produce a file.
    #
    # Dispatch log (Site 1)
    "wicked.dispatch.log_entry_appended": _resolve_single_file(
        "phases/{phase}/dispatch-log.jsonl"
    ),
    # Consensus artifacts (Site 2)
    "wicked.consensus.report_created": _resolve_single_file(
        "phases/{phase}/consensus-report.json"
    ),
    "wicked.consensus.evidence_recorded": _resolve_single_file(
        "phases/{phase}/consensus-evidence.json"
    ),
    # Reviewer report (Site 3) — both event types produce the same file.
    "wicked.consensus.gate_completed": _resolve_single_file(
        "phases/{phase}/reviewer-report.md"
    ),
    "wicked.consensus.gate_pending": _resolve_single_file(
        "phases/{phase}/reviewer-report.md"
    ),
    # Site 5 (PR #785) — condition verification flip.
    # ``wicked.condition.marked_cleared`` updates the manifest AND writes a
    # resolution sidecar.  Sidecar paths vary per condition_id and are
    # transient (the manifest is the source of truth; ``recover()``
    # re-derives sidecars on demand) so they are NOT tracked here.
    "wicked.condition.marked_cleared": _resolve_single_file(
        "phases/{phase}/conditions-manifest.json"
    ),
    # Site W1 (#787) — solo_mode inline-HITL evidence record.
    # ``wicked.crew.inline_review_context_recorded`` materialises the
    # markdown evidence file at phases/{phase}/inline-review-context.md.
    # Solo-mode also fires ``wicked.gate.decided`` for the same gate, which
    # the existing gate.decided resolver maps to gate-result.json (+
    # conditions-manifest.json on CONDITIONAL).  This is a SECOND, distinct
    # event because the inline-review-context.md is a different artifact
    # written from the same flow — separate file, separate semantics
    # (evidence/audit), so a separate event is the right shape (per
    # ``memory/workaround-vs-fix-stop-shaping-plans-around-bad-design.md``:
    # don't dodge the structural answer; new artifact = new event).
    "wicked.crew.inline_review_context_recorded": _resolve_single_file(
        "phases/{phase}/inline-review-context.md"
    ),
}


# Compatibility view: many call sites and tests refer to "the projection
# map" by event_type → file basenames.  This view derives the static set
# of basenames each event MAY produce (ignoring conditional production)
# from the resolvers above by calling each with an empty payload AND a
# CONDITIONAL+conditions stub.  Used by ``_handler_available_for_file``
# and similar discovery code that needs "could this event ever produce
# file F?" semantics.
def _all_possible_basenames_for(event_type: str) -> FrozenSet[str]:
    resolver = _PROJECTION_RESOLVERS.get(event_type)
    if resolver is None:
        return frozenset()
    # Stub payload that triggers any conditional branches in the resolver.
    stub_payload = {
        "data": {
            "result": "CONDITIONAL",
            "verdict": "CONDITIONAL",
            "conditions": [{"description": "stub"}],
        },
    }
    paths = resolver(stub_payload, "_stub_phase_", Path("/__stub_root__"))
    return frozenset(p.name for p in paths)

# ---------------------------------------------------------------------------
# Per-FILE projection flag mapping — used by _active_projection_names() to
# build the set of files that the drift detector should inspect.
#
# Finding #1 fix (PR #764): Site 2 ships with TWO independent flags —
# WG_BUS_AS_TRUTH_CONSENSUS_REPORT and WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE —
# each controlling its own projection file independently.  The previous
# single-token-per-site shape could not represent this correctly.
#
# Shape A: per-file flag granularity.  Each projection filename maps to its
# own WG_BUS_AS_TRUTH_<TOKEN> env var.  _active_projection_names() includes
# file F iff its flag token is literally "on".  No site-number integer key.
#
# The token is composed into WG_BUS_AS_TRUTH_{token} by
# _bus_as_truth_enabled() in scripts/_bus.py — same literal-"on" contract.
# ---------------------------------------------------------------------------

PROJECTION_FILE_FLAGS: Dict[str, str] = {
    "dispatch-log.jsonl":       "DISPATCH_LOG",        # Site 1
    "consensus-report.json":    "CONSENSUS_REPORT",    # Site 2 (flag A)
    "consensus-evidence.json":  "CONSENSUS_EVIDENCE",  # Site 2 (flag B — independent)
    "reviewer-report.md":       "REVIEWER_REPORT",     # Site 3
    "gate-result.json":         "GATE_RESULT",         # Site 4 — active (PR #782 + #780 default-ON)
    "conditions-manifest.json": "CONDITIONS_MANIFEST", # Site 5 — active (PR #785 default-ON)
    "inline-review-context.md": "INLINE_REVIEW_CONTEXT", # Site W1 (#787) — solo_mode evidence record
}

# ---------------------------------------------------------------------------
# Per-EVENT-TYPE handler-availability registry — records whether
# daemon/projector.py has a handler for each event type.
#
# Issue #769 Finding #2 (PR fold): restructured from per-FILE boolean to
# per-EVENT-TYPE boolean.  The per-file shape could not model multi-event-type
# files: reviewer-report.md is materialised by BOTH gate_completed AND
# gate_pending; gate-result.json (Site 4) will be materialised by gate.decided
# and possibly gate.blocked.  A per-file key cannot distinguish "handler for
# gate_completed exists but not gate_pending" — that distinction matters for
# the detector functions that filter individual events.
#
# Consumers:
#   _handler_available_for_file(name)   — used by _active_projection_names()
#   _detect_projection_stale()          — filters per-event directly
#   _detect_event_without_projection()  — filters per-event directly
#
# Values are set to True only AFTER verifying the handler exists in
# daemon/projector.py._HANDLERS.  Verification was done by reading
# daemon/projector.py (lines 924-952) for this PR:
#
#   wicked.dispatch.log_entry_appended  → _dispatch_log_appended  [line 944]  ✓ PRESENT
#   wicked.consensus.report_created     → _consensus_report_created [line 950] ✓ PRESENT
#   wicked.consensus.evidence_recorded  → _consensus_evidence_recorded [line 951] ✓ PRESENT
#   wicked.consensus.gate_completed     → _consensus_gate_completed (PR #773) ✓ PRESENT
#                                          (registry flip landed in PR #781 / this commit)
#   wicked.consensus.gate_pending       → _consensus_gate_pending (PR #773) ✓ PRESENT
#                                          (registry flip landed in PR #781 / this commit)
#   wicked.gate.decided                 → _gate_decided handles DB rows; disk projection
#                                          fans out to _gate_decided_disk (PR-1 / #778)  ✓ PRESENT
#                                          (emit at phase_manager.py:3931 carries the full
#                                          gate_result dict under payload["data"] — handler
#                                          materialises gate-result.json when flag-on)
#   wicked.gate.blocked                 → _gate_blocked (PR-1 / #778) — registered in
#                                          _HANDLERS for completeness but REMOVED from
#                                          _PROJECTION_RESOLVERS (above) because it doesn't
#                                          materialise a file.  Therefore not keyed in
#                                          this registry either.
#   wicked.condition.marked_cleared     → _condition_marked_cleared (Site 5 / this PR) ✓ PRESENT
#                                          (writes resolution sidecar + flips manifest entry
#                                          to verified=True; same atomic two-step ordering
#                                          as conditions_manifest.mark_cleared())
#
# Update this dict when a new handler lands in daemon/projector.py.
# Never mark True speculatively — read the file and verify first.
# ---------------------------------------------------------------------------

_PROJECTION_HANDLERS_AVAILABLE: Dict[str, bool] = {
    # Site 1 — _dispatch_log_appended landed in PR #751
    "wicked.dispatch.log_entry_appended": True,
    # Site 2 — _consensus_report_created / _consensus_evidence_recorded landed in PR #758
    "wicked.consensus.report_created":    True,
    "wicked.consensus.evidence_recorded": True,
    # Site 3 — _consensus_gate_completed + _consensus_gate_pending landed
    # in PR #773 (closing #768).  This registry was never updated at the
    # time, leaving reviewer-report.md silently excluded from the drift
    # detector even though Site 3 had shipped end-to-end with flag-on by
    # default in PR #777.  Discovered during PR #782 (Site 4) and fixed
    # here (#781).
    "wicked.consensus.gate_completed":    True,
    "wicked.consensus.gate_pending":      True,
    # Site 4 — _gate_decided_disk fan-out (from existing _gate_decided)
    # landed in PR-1 (#778) and the emit at phase_manager.py:3931 was
    # widened in the same PR to carry the full gate_result dict under
    # payload["data"].  The handler is therefore materialising when
    # WG_BUS_AS_TRUTH_GATE_RESULT=on; flipping the registry True here
    # tells the drift detector to scan gate-result.json.
    # ``wicked.gate.blocked`` is intentionally absent from this registry
    # because it was removed from _PROJECTION_RESOLVERS above — it doesn't
    # materialise a file and the detector doesn't gate on it.
    #
    # Site 5 (this PR) extends ``_gate_decided_disk`` to ALSO materialise
    # ``conditions-manifest.json`` when the verdict is CONDITIONAL and
    # ``data["conditions"]`` is non-empty.  Same registry entry — one
    # event, multiple files (the new _PROJECTION_RESOLVERS shape).
    "wicked.gate.decided":                True,
    # Site 5 (PR #785) — _condition_marked_cleared materialises the
    # verification flip on conditions-manifest.json + writes the resolution
    # sidecar.  Wired into conditions_manifest.mark_cleared() as a
    # bus emit; projector handler in daemon/projector.py replays the
    # same atomic two-step write order.
    "wicked.condition.marked_cleared":    True,
    # Site W1 (#787) — _inline_review_context_recorded materialises the
    # solo_mode evidence markdown at phases/{phase}/inline-review-context.md.
    # Wired into solo_mode.dispatch_human_inline() as a bus emit BEFORE the
    # legacy direct write; projector handler in daemon/projector.py
    # rebuilds the markdown deterministically from the event payload so the
    # projection and direct-write paths produce byte-identical output.
    "wicked.crew.inline_review_context_recorded": True,
    # Site 5 — no event handler mapping yet
    # (conditions-manifest.json has no event type in _PROJECTION_RESOLVERS)
}


def _handler_available_for_file(name: str) -> bool:
    """Return True iff ALL event types that materialise *name* have a handler.

    Resolves the event types that map to *name* by scanning _PROJECTION_RESOLVERS
    in reverse.  Returns True only when handlers exist for ALL mapping event
    types (conservative: if any event type lacks a handler the file is treated
    as unprojectable until ALL handlers land).

    A file with no event types in _PROJECTION_RESOLVERS (e.g. conditions-manifest.json
    at Site 5 before its event type is added) returns False — defaulting to
    safe exclusion.
    """
    event_types_for_file = [
        et for et in _PROJECTION_RESOLVERS
        if name in _all_possible_basenames_for(et)
    ]
    if not event_types_for_file:
        return False
    return all(
        _PROJECTION_HANDLERS_AVAILABLE.get(et, False)
        for et in event_types_for_file
    )

# ---------------------------------------------------------------------------
# Backwards-compatible view: SITE_PROJECTIONS exposes the same file sets that
# callers or tests may already reference by site number.  Read-only; the drift
# detector now uses PROJECTION_FILE_FLAGS directly.
# ---------------------------------------------------------------------------
SITE_PROJECTIONS: Dict[int, FrozenSet[str]] = {
    1: frozenset({"dispatch-log.jsonl"}),
    2: frozenset({"consensus-report.json", "consensus-evidence.json"}),
    3: frozenset({"reviewer-report.md"}),
    4: frozenset({"gate-result.json"}),
    5: frozenset({"conditions-manifest.json"}),
}


def _site_flag_on(site_num: int) -> bool:
    """Return True iff ALL WG_BUS_AS_TRUTH_* flags for *site_num* are enabled.

    Delegates to ``_flag_on()`` (which calls ``_bus_as_truth_enabled()``) so all
    flag resolution goes through a single predicate with normalization and
    default-map fall-through.  For sites with multiple independent flags (e.g.
    Site 2: CONSENSUS_REPORT and CONSENSUS_EVIDENCE), returns True only when
    EVERY file in that site's projection set has its flag on — conservative.

    Prefer ``_active_projection_names()`` for drift-detector logic; this
    helper is kept for callers that reason in terms of site numbers.

    Args:
        site_num: Cutover site number (1–5).  Unknown site numbers always
            return False — conservative default, never silent approval.
    """
    filenames = SITE_PROJECTIONS.get(site_num)
    if filenames is None:
        return False
    return all(
        _flag_on(PROJECTION_FILE_FLAGS[f])
        for f in filenames
        if f in PROJECTION_FILE_FLAGS
    )


def _flag_on(token: str) -> bool:
    """Return True iff the WG_BUS_AS_TRUTH_{token} flag is enabled.

    Delegates to ``_bus_as_truth_enabled()`` in ``scripts/_bus.py`` — single
    source of truth for flag resolution including normalization (.strip().lower())
    and default-map fall-through for shipped sites.

    Finding #2 fix (PR #777): prior implementation duplicated the predicate with
    its own ``os.environ.get(...) == "on"`` check, bypassing the canonical helper
    in ``_bus.py``.  This delegation ensures the flag flip propagates to the
    reconciler scan path.
    """
    from _bus import _bus_as_truth_enabled  # type: ignore[import]
    return _bus_as_truth_enabled(token)


def _active_projection_names() -> FrozenSet[str]:
    """Return the set of projection filenames that the drift detector should inspect.

    A file is included iff BOTH conditions hold:
      1. Its WG_BUS_AS_TRUTH_<TOKEN> flag is literally ``"on"`` (flag gate).
      2. ``_PROJECTION_HANDLERS_AVAILABLE[filename]`` is True (handler gate).

    The handler gate (Issue #769, extended in fold PR) eliminates
    false-confidence: enabling a flag before the corresponding projector handler
    lands in daemon/projector.py would add a file to the scan set that the
    projector can never materialise, causing every event to be flagged as
    ``event-without-projection`` even though no handler could have written the
    file.  ``_handler_available_for_file(name)`` resolves the per-event-type
    registry for all event types that materialise *name*; a file is included
    only when ALL its event types have handlers (conservative).

    Flag gate (pre-existing): skips files whose cutover site is still OFF,
    preventing false ``projection-without-event`` drift on legacy direct-write
    paths.  When all flags are OFF (the default release state), the returned
    set is empty and the detector fires no false-positives.

    Each file is individually gated by its own WG_BUS_AS_TRUTH_<TOKEN> flag
    (per-file granularity, Shape A).  This means Site 2's two files
    (consensus-report.json, consensus-evidence.json) can be enabled
    independently — flipping only WG_BUS_AS_TRUTH_CONSENSUS_REPORT does NOT
    include consensus-evidence.json in the scan set, and vice-versa.
    """
    return frozenset(
        name
        for name, token in PROJECTION_FILE_FLAGS.items()
        if _flag_on(token) and _handler_available_for_file(name)
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _projects_root() -> Path:
    """Return WG_LOCAL_ROOT/wicked-crew/projects — read-only, no mkdir."""
    base = (
        os.environ.get("WG_LOCAL_ROOT")
        or str(Path.home() / ".something-wicked" / "wicked-garden" / "local")
    )
    return Path(base) / "wicked-crew" / "projects"


def _daemon_db_path() -> Optional[Path]:
    """Resolve projector DB path.

    Priority:
      1. WG_DAEMON_DB env var
      2. default at ~/.something-wicked/wicked-garden-daemon/projections.db

    Returns None when the DB does not exist or lacks the event_log table.
    Caller treats None as "projector unavailable" and returns an empty list.
    """
    env = os.environ.get("WG_DAEMON_DB")
    if env:
        candidate = Path(env)
    else:
        candidate = (
            Path.home()
            / ".something-wicked"
            / "wicked-garden-daemon"
            / "projections.db"
        )

    if not candidate.is_file():
        return None

    # Verify event_log table exists — half-formed DBs must not pass.
    try:
        conn = sqlite3.connect(str(candidate))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_log'"
            ).fetchone()
            return candidate if row is not None else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _validate_explicit_db_path(candidate: Path) -> Optional[Path]:
    """Validate an explicitly-supplied DB path before opening it.

    Mirrors ``_daemon_db_path()``'s validation: checks file existence AND
    verifies the ``event_log`` table exists.  A wrong SQLite file (e.g. an
    empty DB or a different schema) must return None so the caller falls back
    to the documented empty-list "DB unavailable" result rather than silently
    reading the wrong data and faking drift.

    Returns the Path when valid, None otherwise.
    """
    if not candidate.is_file():
        return None

    try:
        conn = sqlite3.connect(str(candidate))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_log'"
            ).fetchone()
            return candidate if row is not None else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _open_db(path: Path) -> sqlite3.Connection:
    """Open projector DB read-only (best effort), WAL mode, no mutations."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Event-log readers
# ---------------------------------------------------------------------------

def _phase_from_chain_id(chain_id: Optional[str]) -> Optional[str]:
    """Extract the phase segment from a chain_id.

    chain_id format: ``{slug}.{phase}(.{gate})?``
    The phase is the second dot-separated segment.
    Returns None when the chain_id is absent, too short, or malformed.
    """
    if not isinstance(chain_id, str) or not chain_id:
        return None
    parts = chain_id.split(".", 2)
    if len(parts) < _MIN_CHAIN_ID_PARTS:
        return None
    phase = parts[1]
    # Reserved non-phase tokens that reconcile.py uses at the root level.
    if phase in ("root", ""):
        return None
    return phase


def _project_slug_from_chain_id(chain_id: Optional[str]) -> Optional[str]:
    """Extract the project slug (first dot-segment) from a chain_id."""
    if not isinstance(chain_id, str) or not chain_id:
        return None
    return chain_id.split(".", 1)[0] or None


def _query_events_for_project(
    conn: sqlite3.Connection, project_slug: str
) -> List[Dict[str, Any]]:
    """Return event_log rows whose chain_id starts with ``{project_slug}.``.

    Rows are ordered by event_id ascending.  Site 5 (#746) added
    ``payload_json`` to the SELECT so payload-aware projection resolvers
    can decide which files an event is expected to produce based on
    payload contents (e.g. ``wicked.gate.decided`` only requires
    conditions-manifest.json on CONDITIONAL verdicts).  Each returned
    row carries a parsed ``payload`` dict; rows with malformed JSON
    silently fall back to ``{}`` so a single bad event doesn't taint
    the rest of the scan.
    """
    # LIKE escape: project_slug may contain underscores which LIKE treats
    # as single-char wildcards.  Use ESCAPE clause to be safe.
    escaped = project_slug.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    try:
        rows = conn.execute(
            """
            SELECT event_id, event_type, chain_id, payload_json,
                   projection_status, error_message, ingested_at
            FROM   event_log
            WHERE  chain_id LIKE ? ESCAPE '\\'
            ORDER  BY event_id ASC
            """,
            (f"{escaped}.%",),
        ).fetchall()
    except sqlite3.Error:
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        raw = d.pop("payload_json", None)
        try:
            d["payload"] = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            d["payload"] = {}
        out.append(d)
    return out


def _event_log_head(conn: sqlite3.Connection) -> int:
    """Return the current MAX(event_id) in the event_log (0 when empty)."""
    try:
        row = conn.execute("SELECT MAX(event_id) FROM event_log").fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return 0


def _event_log_total(conn: sqlite3.Connection) -> int:
    """Return the total count of rows in event_log."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return 0


# ---------------------------------------------------------------------------
# Projection-file discovery
# ---------------------------------------------------------------------------

def _list_known_project_slugs() -> List[str]:
    """List every project directory under the projects root."""
    root = _projects_root()
    if not root.is_dir():
        return []
    try:
        return sorted(
            e.name
            for e in root.iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )
    except OSError:
        return []


def _materialize_projection_paths(
    project_dir: Path,
    event_type: str,
    chain_id: Optional[str],
    payload: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    """Return the expected on-disk paths for an event, given its payload.

    Per Site 5 (#746): an event may CONDITIONALLY produce files based on
    payload contents (e.g. ``wicked.gate.decided`` produces
    conditions-manifest.json only when verdict is CONDITIONAL with a
    non-empty conditions list).  The resolver function in
    ``_PROJECTION_RESOLVERS`` inspects the payload and yields the paths
    the event is expected to produce.

    Returns an empty list when the event type has no resolver, the
    chain_id doesn't carry a phase segment, or the payload doesn't
    trigger any conditional branches.

    The ``payload`` parameter defaults to ``None`` (treated as ``{}``) so
    legacy call sites that don't have the payload handy still get the
    "always-produces" subset of projections — the conditional branches
    just won't fire without payload data.
    """
    resolver = _PROJECTION_RESOLVERS.get(event_type)
    if resolver is None:
        return []

    phase = _phase_from_chain_id(chain_id)
    if phase is None:
        return []

    return list(resolver(payload or {}, phase, project_dir))


def _collect_projection_files(project_dir: Path) -> List[Path]:
    """Walk phases/ and return every file that could be a bus projection.

    Includes the known artifact filenames across all phases.  This is
    the exhaustive set for projection-without-event detection.

    Only files whose owning cutover site has its flag ON are included.
    ``_active_projection_names()`` builds the set dynamically from
    ``SITE_PROJECTIONS`` and ``_site_flag_on()`` — preventing false
    ``projection-without-event`` drift on legacy direct-write paths when
    a site's flag is still OFF (the default release state).

    Example: with all flags OFF (default), the returned set is empty and
    no ``projection-without-event`` findings are raised.  With Site 3 flag
    ON only, the set is ``{"reviewer-report.md"}`` and only that file is
    checked.

    Transition note: the previously hardcoded five-file set is replaced by
    the dynamic call below.  If you need to understand which files are
    currently active, inspect ``_active_projection_names()`` at runtime or
    check the ``SITE_PROJECTIONS`` constant above.  See also
    docs/v9/bus-cutover-staging-plan.md §Site-5 for ``conditions-manifest.json``.
    """
    projection_names = _active_projection_names()
    phases_dir = project_dir / "phases"
    if not phases_dir.is_dir():
        return []
    out: List[Path] = []
    # Race window: a phase directory may be removed between is_dir() and iterdir();
    # suppress OSError and return whatever partial list was collected so far.
    with contextlib.suppress(OSError):
        for phase_dir in sorted(phases_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            for name in projection_names:
                candidate = phase_dir / name
                if candidate.is_file():
                    out.append(candidate)
    return out


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def _detect_projection_stale(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Events in projection_status='pending' with no materialised file.

    'pending' means the projector ingested the event but has not yet
    written the projection file (lagging or slow handler).

    Handler-presence gate (Finding #1 / #769 fold): events whose event_type
    has no handler in ``_PROJECTION_HANDLERS_AVAILABLE`` are skipped — the
    projector can never materialise the file, so reporting drift makes no
    sense and would produce false positives when a flag is enabled before the
    handler lands.
    """
    drift: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("projection_status") != "pending":
            continue
        # Skip events whose handler has not yet landed in daemon/projector.py.
        if not _PROJECTION_HANDLERS_AVAILABLE.get(ev["event_type"], False):
            continue
        proj_paths = _materialize_projection_paths(
            project_dir, ev["event_type"], ev.get("chain_id"), ev.get("payload"),
        )
        for proj_path in proj_paths:
            if not proj_path.exists():
                # projection_last_applied_seq: the event_id at which the projector
                # last successfully processed an event.  This cursor is not yet
                # tracked in the daemon DB schema (no projector_state table /
                # sidecar).  Emit null per staging plan §5 schema compliance
                # until the cursor is wired in (PR #764 follow-up TODO in
                # _build_report_header).
                drift.append({
                    "type": DRIFT_PROJECTION_STALE,
                    "projection": str(proj_path.relative_to(project_dir)),
                    "event_seq": ev["event_id"],
                    "event_type": ev["event_type"],
                    "chain_id": ev.get("chain_id"),
                    "projection_last_applied_seq": None,  # cursor pending — see TODO
                    "lag_events": None,                   # derived from cursor
                    "reason": (
                        f"event_seq {ev['event_id']} ({ev['event_type']!r}) "
                        f"is pending but projection has not been materialised"
                    ),
                })
    return drift


def _detect_event_without_projection(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Events with no matching file on disk (handler missing/raised/wrong path).

    Covers both projection_status='error' (explicit handler failure) and
    projection_status='applied' where the file is unexpectedly absent
    (handler wrote elsewhere, or file was deleted post-projection).

    Handler-presence gate (Finding #1 / #769 fold): events whose event_type
    has no handler in ``_PROJECTION_HANDLERS_AVAILABLE`` are skipped — the
    projector can never materialise the file, so reporting drift makes no
    sense and would produce false positives when a flag is enabled before the
    handler lands.
    """
    drift: List[Dict[str, Any]] = []
    for ev in events:
        # Skip events whose handler has not yet landed in daemon/projector.py.
        if not _PROJECTION_HANDLERS_AVAILABLE.get(ev["event_type"], False):
            continue
        # Only check events we can map to projection paths.
        proj_paths = _materialize_projection_paths(
            project_dir, ev["event_type"], ev.get("chain_id"), ev.get("payload"),
        )
        for proj_path in proj_paths:
            # Projection absent on disk → drift regardless of projection_status.
            if not proj_path.exists():
                # Skip pending events — those are covered by projection_stale.
                if ev.get("projection_status") == "pending":
                    continue
                drift.append({
                    "type": DRIFT_EVENT_WITHOUT_PROJECTION,
                    "event_seq": ev["event_id"],
                    "event_type": ev["event_type"],
                    "chain_id": ev.get("chain_id"),
                    "expected_projection": str(proj_path.relative_to(project_dir)),
                    "projection_status": ev.get("projection_status"),
                    "error_message": ev.get("error_message"),
                    "reason": (
                        f"event_seq {ev['event_id']} ({ev['event_type']!r}) "
                        f"has no materialised projection at "
                        f"{proj_path.relative_to(project_dir)}"
                    ),
                })
    return drift


def _detect_projection_without_event(
    events: List[Dict[str, Any]],
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Projection files on disk with no corresponding event_log row.

    Post-cutover analogue of reconcile.py's orphan_native: the projection
    exists but the bus event that should have produced it is absent (GC'd,
    direct-write bypassing the bus, or lint was off).
    """
    # Build a set of expected-projection paths from the known events so we
    # can quickly test each on-disk file against it.  Per Site 5 (#746):
    # an event may produce multiple files, and may produce them
    # CONDITIONALLY based on payload (e.g. gate.decided produces
    # conditions-manifest.json only on CONDITIONAL verdicts).  Pass
    # ev["payload"] so the resolver can make those conditional decisions.
    event_projection_paths: set = set()
    for ev in events:
        for p in _materialize_projection_paths(
            project_dir, ev["event_type"], ev.get("chain_id"), ev.get("payload"),
        ):
            event_projection_paths.add(p.resolve())

    drift: List[Dict[str, Any]] = []
    for proj_path in _collect_projection_files(project_dir):
        if proj_path.resolve() not in event_projection_paths:
            drift.append({
                "type": DRIFT_PROJECTION_WITHOUT_EVENT,
                "projection": str(proj_path.relative_to(project_dir)),
                "reason": (
                    f"projection {proj_path.relative_to(project_dir)} "
                    f"has no corresponding event_log row (direct-write or GC'd event)"
                ),
            })
    return drift


# ---------------------------------------------------------------------------
# Projections materialised inventory
# ---------------------------------------------------------------------------

def _build_projections_materialised(project_dir: Path) -> Dict[str, Any]:
    """Inventory what projections currently exist on disk for a project."""
    phases_dir = project_dir / "phases"
    gate_result_phases: List[str] = []
    dispatch_log_phases: List[str] = []
    conditions_manifest_phases: List[str] = []
    reviewer_report_phases: List[str] = []
    consensus_report_phases: List[str] = []
    consensus_evidence_phases: List[str] = []

    process_plan = project_dir / "process-plan.json"

    if phases_dir.is_dir():
        # Race window: a phase directory may disappear between is_dir() and
        # iterdir(); suppress OSError and return the partial inventory collected.
        with contextlib.suppress(OSError):
            for phase_dir in sorted(phases_dir.iterdir()):
                if not phase_dir.is_dir():
                    continue
                name = phase_dir.name
                if (phase_dir / "gate-result.json").is_file():
                    gate_result_phases.append(name)
                if (phase_dir / "dispatch-log.jsonl").is_file():
                    dispatch_log_phases.append(name)
                if (phase_dir / "conditions-manifest.json").is_file():
                    conditions_manifest_phases.append(name)
                if (phase_dir / "reviewer-report.md").is_file():
                    reviewer_report_phases.append(name)
                if (phase_dir / "consensus-report.json").is_file():
                    consensus_report_phases.append(name)
                if (phase_dir / "consensus-evidence.json").is_file():
                    consensus_evidence_phases.append(name)

    return {
        "process_plan_json": str(process_plan) if process_plan.is_file() else None,
        "gate_result_files": gate_result_phases,
        "dispatch_log_files": dispatch_log_phases,
        "conditions_manifest_files": conditions_manifest_phases,
        "reviewer_report_files": reviewer_report_phases,
        "consensus_report_files": consensus_report_phases,
        "consensus_evidence_files": consensus_evidence_phases,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconcile_project(
    project_slug: str,
    *,
    conn: Optional["sqlite3.Connection"] = None,
    _daemon_conn: Optional["sqlite3.Connection"] = None,  # alias for internal use
    daemon_db_path: "Path | str | None" = None,
) -> Dict[str, Any]:
    """Run the post-cutover drift check for a single project.

    Args:
        project_slug: The project directory name (slug).
        conn: Optional pre-opened SQLite connection (for test injection).
              When None, opens and closes the DB internally.
        daemon_db_path: Optional path override for the projector DB.
              Honoured in single-project mode (mirrors ``reconcile_all``).
              When None, resolves via WG_DAEMON_DB env var or the default path.

    Returns a per-project result dict per the staging plan §5 schema.
    Errors are reported inside the result, not raised.
    """
    # Support both `conn` and `_daemon_conn` for backward compat with
    # internal callers that share a single connection across projects.
    effective_conn = conn or _daemon_conn

    project_dir = _projects_root() / project_slug
    errors: List[str] = []
    events: List[Dict[str, Any]] = []

    # Attempt to query the event log.
    owns_conn = False
    db_conn: Optional[sqlite3.Connection] = effective_conn
    if db_conn is None:
        # Resolve DB path: explicit override → env var / default path.
        if daemon_db_path is not None:
            resolved_path: Optional[Path] = _validate_explicit_db_path(
                Path(daemon_db_path)
            )
        else:
            resolved_path = _daemon_db_path()

        if resolved_path is not None:
            try:
                db_conn = _open_db(resolved_path)
                owns_conn = True
            except (sqlite3.Error, OSError) as exc:
                errors.append(f"could not open projector DB: {exc}")
        else:
            errors.append("projector DB unavailable (file missing or schema absent)")

    try:
        if db_conn is not None:
            events = _query_events_for_project(db_conn, project_slug)
    except sqlite3.Error as exc:
        errors.append(f"event_log query failed: {exc}")
    finally:
        if owns_conn and db_conn is not None:
            # Closing a read-only SQLite connection can raise sqlite3.Error in
            # degraded states (e.g. WAL checkpoint race); safe to suppress.
            with contextlib.suppress(sqlite3.Error):
                db_conn.close()

    drift: List[Dict[str, Any]] = []
    if project_dir.is_dir():
        drift.extend(_detect_projection_stale(events, project_dir))
        drift.extend(_detect_event_without_projection(events, project_dir))
        drift.extend(_detect_projection_without_event(events, project_dir))
    else:
        errors.append(f"project directory not found: {project_dir}")

    summary = {
        "total_drift_count": len(drift),
        "projection_stale_count": sum(
            1 for d in drift if d["type"] == DRIFT_PROJECTION_STALE
        ),
        "event_without_projection_count": sum(
            1 for d in drift if d["type"] == DRIFT_EVENT_WITHOUT_PROJECTION
        ),
        "projection_without_event_count": sum(
            1 for d in drift if d["type"] == DRIFT_PROJECTION_WITHOUT_EVENT
        ),
    }

    return {
        "project_slug": project_slug,
        "events_for_project": len(events),
        "projections_materialized": _build_projections_materialised(project_dir),
        "drift": drift,
        "summary": summary,
        "errors": errors,
    }


def reconcile_all(
    daemon_db_path: "Path | str | None" = None,
) -> List[Dict[str, Any]]:
    """Run the post-cutover drift check for every known project.

    Returns an empty list when the projector DB is unavailable — NEVER raises.
    Callers can distinguish "no drift found" from "DB unreachable" by checking
    whether the returned list contains entries with errors.

    Args:
        daemon_db_path: Optional path override for the projector DB.
            When None, resolves via WG_DAEMON_DB env var or the default path.

    Returns:
        List of per-project result dicts (staging plan §5 schema).
        Empty list when the projector DB is unreachable.
    """
    # Resolve DB path.  When an explicit path is supplied, run the same
    # _validate_explicit_db_path() check used by reconcile_project() so that
    # an empty/wrong-schema SQLite file returns [] (the "DB unavailable"
    # contract) instead of opening and silently reading nothing.
    if daemon_db_path is not None:
        resolved: Optional[Path] = _validate_explicit_db_path(Path(daemon_db_path))
    else:
        resolved = _daemon_db_path()

    if resolved is None:
        return []

    # Open one shared connection for the full scan — O(projects) rather than
    # O(projects * open_close_cost).
    try:
        shared_conn = _open_db(resolved)
    except (sqlite3.Error, OSError):
        return []

    try:
        slugs = _list_known_project_slugs()
        results: List[Dict[str, Any]] = []
        for slug in slugs:
            result = reconcile_project(slug, _daemon_conn=shared_conn)
            results.append(result)
        return results
    except Exception:  # pragma: no cover — unexpected; fail-open
        return []
    finally:
        # Closing a shared read-only connection may raise sqlite3.Error on WAL
        # checkpoint races; suppressing is safe — the scan results are already in
        # `results` and no mutation was performed.
        with contextlib.suppress(sqlite3.Error):
            shared_conn.close()


def _build_report_header(
    conn: Optional[sqlite3.Connection],
    command_invoked: str,
) -> Dict[str, Any]:
    """Build the §5 header block for the full report."""
    head_seq = 0
    total_seq = 0
    if conn is not None:
        # DB access failure here just means the header reports zeros for
        # head/total; the report is still valid and fail-open is correct.
        with contextlib.suppress(sqlite3.Error):
            head_seq = _event_log_head(conn)
            total_seq = _event_log_total(conn)

    # Lag math — Path A (follow-up issue filed for Path B cursor wiring).
    #
    # The correct lag formula is:
    #   head_seq - projection_last_applied_seq
    # where projection_last_applied_seq is the event_id the projector last
    # successfully processed.  That cursor is NOT currently tracked in the
    # daemon DB schema — there is no projector_state table or sidecar file.
    #
    # The previous formula (total_seq - head_seq) was permanently false:
    # MAX(event_id) >= COUNT(*) in any retained DB, so the condition
    # `total_seq > head_seq` could never be true and lag was always 0.
    #
    # Until the projector cursor is wired in, we emit null for lag_events
    # rather than a misleading zero.
    #
    # TODO: wire projection_last_applied_seq from the projector and replace
    # the null with the real lag.  Filed as follow-up issue #767.
    lag_events: Optional[int] = None  # cursor unavailable — see TODO above

    if conn is None:
        projector_health = "unreachable"
    else:
        # Cursor absent — consumer cannot act on the cursor either way.
        # Schema enum is {ok, lagging, unreachable}; "unknown" is not valid.
        projector_health = "unreachable"

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "command_invoked": command_invoked,
        "event_log_head_seq": head_seq,
        "event_log_total_seq": total_seq,
        "lag_events": lag_events,
        "projector_health": projector_health,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_text_report(result: Dict[str, Any]) -> str:
    """Render a single project reconcile-v2 result as a human-readable report."""
    lines: List[str] = []
    slug = result.get("project_slug", "<unknown>")
    summary = result.get("summary") or {}
    lines.append(f"Reconcile-v2 report — project: {slug}")
    lines.append("=" * len(lines[-1]))
    lines.append(f"  Events for project:  {result.get('events_for_project', 0)}")
    lines.append("")
    lines.append("Drift summary (post-cutover):")
    lines.append(f"  total:                       {summary.get('total_drift_count', 0)}")
    lines.append(f"  projection-stale:             {summary.get('projection_stale_count', 0)}")
    lines.append(f"  event-without-projection:     {summary.get('event_without_projection_count', 0)}")
    lines.append(f"  projection-without-event:     {summary.get('projection_without_event_count', 0)}")

    errors = result.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Errors (fail-open — partial report shown):")
        for err in errors:
            lines.append(f"  - {err}")

    drift = result.get("drift") or []
    if drift:
        lines.append("")
        lines.append("Drift entries:")
        for entry in drift:
            kind = entry.get("type", "?")
            reason = entry.get("reason", "")
            lines.append(f"  [{kind}] {reason}")
    else:
        lines.append("")
        lines.append("No post-cutover drift detected.")

    return "\n".join(lines) + "\n"


def render_text_report_all(results: List[Dict[str, Any]]) -> str:
    """Render multiple project results, one section per project."""
    if not results:
        return "No projects found (or projector DB unavailable).\n"
    chunks: List[str] = []
    grand_total = 0
    for r in results:
        grand_total += int((r.get("summary") or {}).get("total_drift_count", 0))
        chunks.append(render_text_report(r))
    chunks.append(
        f"--- Aggregate ---\nProjects scanned: {len(results)}\n"
        f"Total drift entries: {grand_total}\n"
    )
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# CLI (mirrors v1 surface so operator muscle-memory transfers)
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Post-cutover reconciler: projection-vs-event drift detector. "
            "Reads-only — never mutates the projector DB or on-disk artifacts. "
            "v1 (reconcile.py) handles pre-cutover drift; this module handles post-cutover."
        ),
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--project",
        dest="project",
        help="Reconcile a single project slug.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Reconcile every known project.",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of the text report.",
    )
    p.add_argument(
        "--daemon-db",
        dest="daemon_db",
        help="Override projector DB path (default: WG_DAEMON_DB or ~/.something-wicked/...).",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    daemon_db_override = Path(args.daemon_db) if args.daemon_db else None

    if args.all:
        results = reconcile_all(daemon_db_path=daemon_db_override)
        if args.as_json:
            # Wire _build_report_header per staging plan §5 JSON schema.
            # Open a transient connection to read event_log head/total; if
            # the DB is unavailable reconcile_all already returned [] and we
            # emit an "unreachable" header.
            _header_conn: Optional[sqlite3.Connection] = None
            if daemon_db_override is not None:
                _resolved = _validate_explicit_db_path(daemon_db_override)
            else:
                _resolved = _daemon_db_path()
            if _resolved is not None:
                try:
                    _header_conn = _open_db(_resolved)
                except (sqlite3.Error, OSError):
                    _header_conn = None
            try:
                header = _build_report_header(
                    _header_conn,
                    command_invoked=" ".join(
                        ["reconcile_v2"] + (sys.argv[1:] if argv is None else list(argv))
                    ),
                )
            finally:
                if _header_conn is not None:
                    # Read-only connection; close failure is benign.
                    with contextlib.suppress(sqlite3.Error):
                        _header_conn.close()
            payload = {"header": header, "results": results}
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        else:
            sys.stdout.write(render_text_report_all(results))
        return 0

    # Single-project mode — honour --daemon-db the same way --all does.
    result = reconcile_project(args.project, daemon_db_path=daemon_db_override)
    if args.as_json:
        # Wire _build_report_header for single-project JSON output too.
        _header_conn2: Optional[sqlite3.Connection] = None
        if daemon_db_override is not None:
            _resolved2 = _validate_explicit_db_path(daemon_db_override)
        else:
            _resolved2 = _daemon_db_path()
        if _resolved2 is not None:
            try:
                _header_conn2 = _open_db(_resolved2)
            except (sqlite3.Error, OSError):
                _header_conn2 = None
        try:
            header2 = _build_report_header(
                _header_conn2,
                command_invoked=" ".join(
                    ["reconcile_v2"] + (sys.argv[1:] if argv is None else list(argv))
                ),
            )
        finally:
            if _header_conn2 is not None:
                # Read-only connection; close failure is benign.
                with contextlib.suppress(sqlite3.Error):
                    _header_conn2.close()
        payload2 = {"header": header2, "results": [result]}
        sys.stdout.write(json.dumps(payload2, indent=2) + "\n")
    else:
        sys.stdout.write(render_text_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
