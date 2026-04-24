"""daemon/test_dispatch.py — Auto-dispatch to wicked-testing on test phases.

Issue #595 (v8 PR-7).

ARCHITECTURAL NOTE — mutation carve-out from PR-1 decision #6
--------------------------------------------------------------
PR-1 established the daemon as read-only (events projected from the bus).
PR-4 added council sessions as the first explicit write path (POST /council).
PR-7 adds a second explicit write path: test_dispatches.

Test dispatches are *originated* by the daemon when it detects a phase that
requires test-strategy or test activity.  There is no bus event to project from;
the daemon queries the phase plan and decides whether to dispatch.  This is a
deliberate, documented carve-out.  The read-only principle still applies to all
projection tables (projects, phases, tasks, cursor, event_log).

PLUGIN CONTRACT (v9/drop-in-plugin-contract.md)
--------------------------------------------------------------
- We dispatch TO wicked-testing; we do NOT re-implement its logic.
- We call wicked-testing's canonical skills (plan/authoring/execution/review).
- We honour the verdict shape it returns — we do not translate or recast it.
- wicked-testing not being installed is NOT a crash condition (graceful degradation).

Public API
----------
detect_test_phases(phases_list) -> list[str]
    Return phase names that require wicked-testing dispatch.

build_dispatch_plan(project_id, phases_list, phase_catalog) -> TestDispatchPlan
    Build the full dispatch plan for a project given its current phases.

dispatch_for_phase(conn, project_id, phase, skill, autonomy_mode, *, db_path) -> DispatchRecord
    Execute or log one wicked-testing skill dispatch for a phase.  Persists
    the result to test_dispatches.  Respects autonomy mode.

run_test_dispatches(conn, project_id, phases_list, phase_catalog,
                    autonomy_mode, *, db_path, skill_filter) -> list[DispatchRecord]
    Full orchestration: detect → build plan → dispatch each skill → return records.

DispatchRecord is a plain dataclass — JSON-serialisable via dataclasses.asdict.
TestDispatchPlan is a plain dataclass — JSON-serialisable via dataclasses.asdict.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants (R3: no magic values)
# ---------------------------------------------------------------------------

#: Phase names (or name substrings) that trigger wicked-testing dispatch.
_TEST_PHASE_KEYWORDS: frozenset[str] = frozenset({"test-strategy", "test", "qe"})

#: Specialists that indicate a test-related phase.
_TEST_SPECIALISTS: frozenset[str] = frozenset({"qe"})

#: Skill → phase-keyword mapping.  Defines which wicked-testing skills fire
#: for which phase types (in priority order within a phase).
_PHASE_SKILL_MAP: dict[str, list[str]] = {
    "test-strategy": ["wicked-testing:plan"],
    "test":          ["wicked-testing:authoring", "wicked-testing:execution"],
    "qe":            ["wicked-testing:review"],
    # Fallback for any test-related phase that doesn't match the above exactly
    "__test_phase__":["wicked-testing:plan"],
}

#: Skill names that wicked-testing exposes (canonical per plugin contract).
_ALL_WICKED_TESTING_SKILLS: frozenset[str] = frozenset({
    "wicked-testing:plan",
    "wicked-testing:authoring",
    "wicked-testing:execution",
    "wicked-testing:review",
})

#: Verdict written when wicked-testing is not installed.
_VERDICT_SKIPPED_UNAVAILABLE: str = "skipped_unavailable"

#: Verdict written when dispatch is deferred (ask mode, waiting for confirm).
_VERDICT_DEFERRED_ASK: str = "deferred_ask"

#: Verdict written when dispatch completes successfully.
_VERDICT_OK: str = "ok"

#: Verdict written when dispatch invocation failed (subprocess error / timeout).
_VERDICT_ERROR: str = "error"

#: Timeout in seconds for a wicked-testing skill subprocess invocation.
#: Per R5: all I/O must have timeouts.
_DISPATCH_TIMEOUT_S: int = 300

#: Idempotency window: re-dispatching the same (project, phase, skill) within
#: this many seconds is a no-op (avoids spamming wicked-testing).
_IDEMPOTENCY_WINDOW_S: int = 300

#: Maximum number of test_dispatches rows returned in a single list query.
#: Per R5: no unbounded reads.
_MAX_LIST_DISPATCHES: int = 500

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# sys.path: scripts/ must be importable for autonomy + probe
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SkillPlan:
    """One wicked-testing skill planned for dispatch."""
    phase: str
    skill: str
    reason: str


@dataclass
class TestDispatchPlan:
    """Full dispatch plan for a project — built by build_dispatch_plan."""
    project_id: str
    skills: list[SkillPlan] = field(default_factory=list)
    test_phases_detected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "test_phases_detected": list(self.test_phases_detected),
            "skills": [asdict(s) for s in self.skills],
        }


@dataclass
class DispatchRecord:
    """One test dispatch execution result — persisted as a test_dispatches row."""
    dispatch_id: str
    session_id: str
    project_id: str
    phase: str
    skill: str
    verdict: str            # ok | error | skipped_unavailable | deferred_ask
    evidence_path: str | None
    latency_ms: int
    emitted_at: int
    notes: str              # Human-readable detail (log excerpt, degradation reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "phase": self.phase,
            "skill": self.skill,
            "verdict": self.verdict,
            "evidence_path": self.evidence_path,
            "latency_ms": self.latency_ms,
            "emitted_at": self.emitted_at,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Phase detection (Stream 1)
# ---------------------------------------------------------------------------

def detect_test_phases(phases_list: list[dict[str, Any]]) -> list[str]:
    """Return phase names from phases_list that require wicked-testing dispatch.

    Detection rules (applied to each phase dict from db.list_phases / phases.json):
    1. Phase name exactly matches a key in _TEST_PHASE_KEYWORDS.
    2. Phase name contains a keyword as a substring.
    3. Phase ``specialists`` list contains a QE specialist name.
    4. Phase ``activities`` list contains a test-related keyword.

    The probe is intentionally conservative — missing fields are treated as empty
    rather than raising, so a partial phase record from the DB does not crash
    detection.
    """
    detected: list[str] = []
    for phase_row in phases_list:
        phase_name: str = phase_row.get("phase") or phase_row.get("name") or ""
        if not phase_name:
            continue

        # Rule 1 + 2: name match
        name_lower = phase_name.lower()
        name_matched = any(kw in name_lower for kw in _TEST_PHASE_KEYWORDS)

        # Rule 3: specialists contain qe
        specialists = phase_row.get("specialists") or []
        if isinstance(specialists, str):
            specialists = [s.strip() for s in specialists.split(",")]
        specialist_matched = bool(set(specialists) & _TEST_SPECIALISTS)

        # Rule 4: activities list contains a keyword
        activities = phase_row.get("activities") or []
        if isinstance(activities, str):
            activities = [a.strip() for a in activities.split(",")]
        activity_matched = any(
            any(kw in act.lower() for kw in _TEST_PHASE_KEYWORDS)
            for act in activities
        )

        if name_matched or specialist_matched or activity_matched:
            detected.append(phase_name)

    return detected


def _skills_for_phase(phase_name: str) -> list[str]:
    """Return the ordered list of wicked-testing skills for a given phase name.

    Uses exact match first, then substring/pattern fallback.
    """
    if phase_name in _PHASE_SKILL_MAP:
        return list(_PHASE_SKILL_MAP[phase_name])

    # Substring match — catches e.g. "test-strategy-lite"
    for key, skills in _PHASE_SKILL_MAP.items():
        if key == "__test_phase__":
            continue
        if key in phase_name.lower() or phase_name.lower() in key:
            return list(skills)

    return list(_PHASE_SKILL_MAP["__test_phase__"])


def build_dispatch_plan(
    project_id: str,
    phases_list: list[dict[str, Any]],
    phase_catalog: dict[str, Any] | None = None,
) -> TestDispatchPlan:
    """Build the full dispatch plan for a project.

    Parameters
    ----------
    project_id:
        Identifies the project; stored on each SkillPlan.
    phases_list:
        Phase rows from db.list_phases (runtime phase state) or from
        phases.json catalog (planning-time).  May contain dicts with
        varying shapes — detection is defensive.
    phase_catalog:
        Optional phases.json catalog dict (``{"phases": {...}}``) used to
        enrich phases_list with specialist/activities info when absent from
        the DB rows.

    Returns
    -------
    TestDispatchPlan
        Contains ``test_phases_detected`` + one SkillPlan per (phase, skill) pair.
    """
    # Enrich phases_list with catalog metadata when available
    enriched: list[dict[str, Any]] = []
    catalog_phases: dict[str, Any] = {}
    if phase_catalog:
        catalog_phases = phase_catalog.get("phases", {})

    for row in phases_list:
        phase_name = row.get("phase") or row.get("name") or ""
        if phase_name and phase_name in catalog_phases:
            merged = dict(catalog_phases[phase_name])
            merged.update(row)  # DB row values take precedence
            enriched.append(merged)
        else:
            enriched.append(row)

    test_phases = detect_test_phases(enriched)
    plan = TestDispatchPlan(
        project_id=project_id,
        test_phases_detected=list(test_phases),
    )

    for phase_name in test_phases:
        skills = _skills_for_phase(phase_name)
        for skill in skills:
            plan.skills.append(SkillPlan(
                phase=phase_name,
                skill=skill,
                reason=f"phase '{phase_name}' requires {skill}",
            ))

    return plan


# ---------------------------------------------------------------------------
# wicked-testing availability probe (Stream 3)
# ---------------------------------------------------------------------------

def _is_wicked_testing_available() -> bool:
    """Return True if wicked-testing is accessible via npx.

    Uses the existing ``_wicked_testing_probe.probe()`` infrastructure so
    detection is consistent with bootstrap.  Falls back to a simple shutil
    check when the probe module is unavailable.

    Never raises (R2: no bare panics in production paths).
    """
    try:
        from _wicked_testing_probe import probe  # type: ignore[import]
        result = probe()
        return result.get("status") == "ok"
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("test_dispatch: probe() raised %s — falling back to shutil", exc)

    # Fallback: shutil check for npx (weak but always available)
    import shutil
    return shutil.which("npx") is not None


# ---------------------------------------------------------------------------
# Idempotency guard (Stream 7 requirement)
# ---------------------------------------------------------------------------

def _is_duplicate_dispatch(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
    skill: str,
    window_s: int = _IDEMPOTENCY_WINDOW_S,
) -> bool:
    """Return True if a non-error dispatch for (project, phase, skill) exists
    within the idempotency window.

    Avoids spamming wicked-testing when the same phase is processed multiple
    times in a short session.
    """
    cutoff = int(time.time()) - window_s
    row = conn.execute(
        """
        SELECT dispatch_id FROM test_dispatches
        WHERE project_id = ?
          AND phase = ?
          AND skill = ?
          AND verdict NOT IN (?, ?)
          AND emitted_at >= ?
        LIMIT 1
        """,
        (project_id, phase, skill, _VERDICT_ERROR, _VERDICT_DEFERRED_ASK, cutoff),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Autonomy-mode HITL integration (Stream 5)
# ---------------------------------------------------------------------------

def _should_pause_test_dispatch(
    phase: str,
    skill: str,
    autonomy_mode_str: str,
) -> bool:
    """Return True when the autonomy mode requires a pause before dispatching.

    Mapping:
        ask      → always pause (log intent, wait for user confirmation)
        balanced → consult hitl_judge rule WG_HITL_TEST_DISPATCH
        full     → never pause (auto-dispatch)

    Importing autonomy lazily so the module stays usable when crew scripts
    are not on sys.path.
    """
    try:
        from crew.autonomy import AutonomyMode, get_mode  # type: ignore[import]

        mode = get_mode(cli_arg=autonomy_mode_str if autonomy_mode_str else None)

        if mode == AutonomyMode.ASK:
            return True

        if mode == AutonomyMode.FULL:
            return False

        # balanced — check env override first, then auto
        import os
        override = os.environ.get("WG_HITL_TEST_DISPATCH", "auto").lower()
        if override == "pause":
            return True
        if override == "off":
            return False
        # auto: balanced proceeds unless complexity is above threshold
        # (conservative: balanced always proceeds for test dispatch — test
        # strategy is about gathering evidence, not an irreversible action)
        return False

    except ImportError:
        logger.debug("test_dispatch: autonomy module not importable — defaulting to pause")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("test_dispatch: autonomy check raised %s — defaulting to pause", exc)
        return True


# ---------------------------------------------------------------------------
# Single-skill dispatch (Stream 2)
# ---------------------------------------------------------------------------

def dispatch_for_phase(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
    skill: str,
    autonomy_mode_str: str = "ask",
    *,
    session_id: str | None = None,
) -> DispatchRecord:
    """Execute or defer one wicked-testing skill dispatch.

    Decision flow:
    1. Check idempotency window — no-op if already dispatched recently.
    2. Check wicked-testing availability — graceful degradation if missing.
    3. Check autonomy mode — defer in ask mode.
    4. Execute the Skill invocation (subprocess).
    5. Persist the result to test_dispatches.

    Parameters
    ----------
    conn:
        Open daemon DB connection.  dispatch_for_phase writes test_dispatches
        rows (explicit mutation carve-out per module docstring).
    project_id:
        Project context.
    phase:
        Phase name the skill is dispatched for.
    skill:
        Canonical wicked-testing skill name (e.g. ``wicked-testing:plan``).
    autonomy_mode_str:
        String value of the resolved autonomy mode (``ask|balanced|full``).
    session_id:
        Optional caller-provided session ID; auto-generated when absent.

    Returns
    -------
    DispatchRecord
        Result of the dispatch attempt, already persisted to test_dispatches.
    """
    resolved_session_id = session_id or str(uuid.uuid4())
    dispatch_id = str(uuid.uuid4())
    start = time.monotonic()

    # 1. Idempotency guard
    if _is_duplicate_dispatch(conn, project_id, phase, skill):
        logger.debug(
            "test_dispatch: idempotency guard — skipping duplicate dispatch "
            "for project=%s phase=%s skill=%s", project_id, phase, skill,
        )
        record = DispatchRecord(
            dispatch_id=dispatch_id,
            session_id=resolved_session_id,
            project_id=project_id,
            phase=phase,
            skill=skill,
            verdict="no_op_duplicate",
            evidence_path=None,
            latency_ms=0,
            emitted_at=int(time.time()),
            notes="idempotency guard: already dispatched within window",
        )
        _persist_dispatch(conn, record)
        return record

    # 2. Availability probe (Stream 3 — graceful degradation)
    if not _is_wicked_testing_available():
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "test_dispatch: wicked-testing not available — "
            "recording skipped_unavailable for phase=%s skill=%s "
            "(evidence gap: no test evidence for this phase gate)",
            phase, skill,
        )
        record = DispatchRecord(
            dispatch_id=dispatch_id,
            session_id=resolved_session_id,
            project_id=project_id,
            phase=phase,
            skill=skill,
            verdict=_VERDICT_SKIPPED_UNAVAILABLE,
            evidence_path=None,
            latency_ms=latency_ms,
            emitted_at=int(time.time()),
            notes=(
                "wicked-testing not installed or not accessible via npx. "
                "Phase proceeds with flagged evidence gap. "
                "Install wicked-testing to enable auto-dispatch."
            ),
        )
        _persist_dispatch(conn, record)
        return record

    # 3. Autonomy-mode gate (Stream 5)
    if _should_pause_test_dispatch(phase, skill, autonomy_mode_str):
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "test_dispatch: ask mode — deferring dispatch of %s for phase=%s "
            "(user confirmation required before auto-dispatch fires)",
            skill, phase,
        )
        record = DispatchRecord(
            dispatch_id=dispatch_id,
            session_id=resolved_session_id,
            project_id=project_id,
            phase=phase,
            skill=skill,
            verdict=_VERDICT_DEFERRED_ASK,
            evidence_path=None,
            latency_ms=latency_ms,
            emitted_at=int(time.time()),
            notes=(
                f"ask mode: auto-dispatch would fire /{skill} for phase '{phase}'. "
                "Awaiting explicit user confirmation before proceeding."
            ),
        )
        _persist_dispatch(conn, record)
        return record

    # 4. Execute the skill invocation (Stream 2 — reuse PR-4 subprocess pattern)
    evidence_path, verdict, notes = _invoke_skill(skill, project_id, phase)
    latency_ms = int((time.monotonic() - start) * 1000)

    record = DispatchRecord(
        dispatch_id=dispatch_id,
        session_id=resolved_session_id,
        project_id=project_id,
        phase=phase,
        skill=skill,
        verdict=verdict,
        evidence_path=evidence_path,
        latency_ms=latency_ms,
        emitted_at=int(time.time()),
        notes=notes,
    )

    # 5. Persist
    _persist_dispatch(conn, record)
    return record


# ---------------------------------------------------------------------------
# Skill invocation (Stream 2 — subprocess, reusing PR-4 machinery pattern)
# ---------------------------------------------------------------------------

_SKILL_ARGV: dict[str, Any] = {
    "wicked-testing:plan":      lambda topic, phase: ["npx", "wicked-testing", "plan",      "--topic", topic, "--phase", phase],
    "wicked-testing:authoring": lambda topic, phase: ["npx", "wicked-testing", "authoring", "--topic", topic, "--phase", phase],
    "wicked-testing:execution": lambda topic, phase: ["npx", "wicked-testing", "execution", "--topic", topic, "--phase", phase],
    "wicked-testing:review":    lambda topic, phase: ["npx", "wicked-testing", "review",    "--topic", topic, "--phase", phase],
}


def _invoke_skill(
    skill: str,
    project_id: str,
    phase: str,
    timeout_s: int = _DISPATCH_TIMEOUT_S,
) -> tuple[str | None, str, str]:
    """Invoke a wicked-testing skill subprocess.

    Returns (evidence_path, verdict, notes).  Never raises (R2: no bare panics).
    Timeout is enforced on every invocation (R5: all I/O must have timeouts).
    """
    argv_factory = _SKILL_ARGV.get(skill)
    if argv_factory is None:
        logger.error("test_dispatch: no argv recipe for skill %r", skill)
        return None, _VERDICT_ERROR, f"no argv recipe configured for {skill}"

    argv = argv_factory(project_id, phase)
    logger.info("test_dispatch: invoking %s for project=%s phase=%s", skill, project_id, phase)

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,  # R5: timeout on every subprocess call
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "test_dispatch: %s exceeded timeout %ds for project=%s phase=%s",
            skill, timeout_s, project_id, phase,
        )
        return None, _VERDICT_ERROR, f"{skill} exceeded timeout of {timeout_s}s"
    except Exception as exc:  # noqa: BLE001 — subprocess errors must not crash dispatch
        logger.error(
            "test_dispatch: unexpected error invoking %s: %s", skill, exc, exc_info=True,
        )
        return None, _VERDICT_ERROR, f"unexpected error: {exc}"

    if result.returncode != 0:
        stderr_excerpt = (result.stderr or "")[:200]
        logger.warning(
            "test_dispatch: %s exited %d for project=%s (stderr: %s)",
            skill, result.returncode, project_id, stderr_excerpt,
        )
        return None, _VERDICT_ERROR, f"exited {result.returncode}: {stderr_excerpt}"

    # Extract evidence path from stdout if wicked-testing emitted one.
    evidence_path = _extract_evidence_path(result.stdout or "")
    notes = (result.stdout or "")[:500]

    logger.info(
        "test_dispatch: %s completed ok for project=%s phase=%s evidence=%s",
        skill, project_id, phase, evidence_path,
    )
    return evidence_path, _VERDICT_OK, notes


def _extract_evidence_path(stdout: str) -> str | None:
    """Extract an evidence file path from wicked-testing stdout.

    wicked-testing emits a line like ``evidence: path/to/evidence.json``.
    Returns the path string or None when absent.
    """
    import re
    match = re.search(r"^evidence:\s*(.+)$", stdout, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# DB persistence (Stream 2)
# ---------------------------------------------------------------------------

def _persist_dispatch(conn: sqlite3.Connection, record: DispatchRecord) -> None:
    """Insert a test_dispatches row.  Caller must have already called init_schema."""
    conn.execute(
        """
        INSERT OR IGNORE INTO test_dispatches
            (dispatch_id, session_id, project_id, phase, skill,
             verdict, evidence_path, latency_ms, emitted_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.dispatch_id,
            record.session_id,
            record.project_id,
            record.phase,
            record.skill,
            record.verdict,
            record.evidence_path,
            record.latency_ms,
            record.emitted_at,
            record.notes,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Full orchestration (Stream 2 + 5)
# ---------------------------------------------------------------------------

def run_test_dispatches(
    conn: sqlite3.Connection,
    project_id: str,
    phases_list: list[dict[str, Any]],
    phase_catalog: dict[str, Any] | None = None,
    autonomy_mode_str: str = "ask",
    *,
    session_id: str | None = None,
    skill_filter: list[str] | None = None,
) -> list[DispatchRecord]:
    """Orchestrate the full detect → plan → dispatch loop.

    Parameters
    ----------
    conn:
        Open daemon DB connection with test_dispatches table created.
    project_id:
        Project identifier.
    phases_list:
        Phase rows from db.list_phases or a catalog subset.
    phase_catalog:
        Optional phases.json catalog for enrichment.
    autonomy_mode_str:
        Resolved autonomy mode (``ask|balanced|full``).
    session_id:
        Optional caller session ID for audit correlation.
    skill_filter:
        If provided, only dispatch skills in this list.  Used by the
        HTTP endpoint to dispatch a specific subset.

    Returns
    -------
    list[DispatchRecord]
        One record per (phase, skill) pair in the plan.
    """
    plan = build_dispatch_plan(project_id, phases_list, phase_catalog)

    records: list[DispatchRecord] = []
    for skill_plan in plan.skills:
        if skill_filter and skill_plan.skill not in skill_filter:
            continue
        record = dispatch_for_phase(
            conn=conn,
            project_id=project_id,
            phase=skill_plan.phase,
            skill=skill_plan.skill,
            autonomy_mode_str=autonomy_mode_str,
            session_id=session_id,
        )
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# DB read helpers (Stream 6 — for HTTP endpoints)
# ---------------------------------------------------------------------------

def list_test_dispatches(
    conn: sqlite3.Connection,
    project_id: str | None = None,
    since: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return test_dispatches rows ordered by emitted_at DESC.

    ``project_id`` filters to a single project when provided.
    ``since`` is an epoch lower bound on ``emitted_at`` (inclusive).
    ``limit`` is capped at _MAX_LIST_DISPATCHES (R5: no unbounded reads).
    """
    limit = min(limit, _MAX_LIST_DISPATCHES)
    if project_id is not None:
        rows = conn.execute(
            """
            SELECT * FROM test_dispatches
            WHERE project_id = ? AND emitted_at >= ?
            ORDER BY emitted_at DESC
            LIMIT ?
            """,
            (project_id, since, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM test_dispatches
            WHERE emitted_at >= ?
            ORDER BY emitted_at DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]
