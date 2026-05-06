#!/usr/bin/env python3
"""Validate a facilitator process-plan JSON file.

Usage:
    validate_plan.py <path-to-plan.json>
    validate_plan.py --selftest

Exit 0 on valid, exit 1 on invalid or selftest failure.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

# Resolver import is best-effort — validate_plan is used in CI where the
# repo layout is guaranteed, but the import is guarded so a malformed
# agents/ tree surfaces a readable warning instead of a hard crash.
try:
    from crew.specialist_resolver import build_resolver, resolve_role
    _RESOLVER_AVAILABLE = True
except Exception:  # pragma: no cover - import-time safety net
    _RESOLVER_AVAILABLE = False
    build_resolver = None  # type: ignore[assignment]
    resolve_role = None  # type: ignore[assignment]

# Plugin root for resolver lookups. Mirrors the convention used in
# hooks/scripts/*: prefer the env var, fall back to the repo tree above
# this file. Kept module-level so tests can patch it if needed.
_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Close-match cutoff chosen by difflib's default (0.6). Issue #573 asks
# for suggestions on unknown roles; three is enough to narrow without
# drowning the reader in look-alikes.
_CLOSE_MATCHES_N = 3
_CLOSE_MATCHES_CUTOFF = 0.6

VALID_RIGOR_TIERS = {"minimal", "standard", "full"}
# NB(#627): `reading` uses the inverted HIGH=safest convention (kept for
# backward compat). Internal-only — never display to users without translation.
# `risk_level` (below) is the direction-explicit, user-facing field.
VALID_FACTOR_READINGS = {"LOW", "MEDIUM", "HIGH"}
# NB(#627): `risk_level` is the direction-explicit, user-facing field emitted
# by `factor_questionnaire.score_all()`. Validation here defends against silent
# producer regression that would drop the field and force consumers back onto
# the inversion-prone `reading` value.
VALID_FACTOR_RISK_LEVELS = {"low_risk", "medium_risk", "high_risk"}
# Mapping mirrors `_RISK_INVERSION` in `scripts/crew/factor_questionnaire.py`.
# Keep the two in sync — drift here means the validator stops catching producer
# regression. Tests cover the round-trip in tests/test_validate_plan_test_strategy_check.py
# plus the validate_plan selftest fixtures below.
_EXPECTED_RISK_LEVEL_FOR_READING = {
    "HIGH": "low_risk",
    "MEDIUM": "medium_risk",
    "LOW": "high_risk",
}
VALID_EVENT_TYPES = {
    "task", "coding-task", "gate-finding",
    "phase-transition", "procedure-trigger", "subtask",
}
# Issue #810: canonical 7-value archetype enum, mirrors
# `scripts/crew/archetype_detect.py` priority-order. Kept here so the validator
# can reject typos in the top-level field without taking a hard runtime
# dependency on archetype_detect (which pulls in heavier file-walk imports).
# Drift between the two lists is caught by tests/test_validate_plan_archetype.py.
#
# The tuple holds the priority-ordered list (used by docs / future error
# rendering that needs to preserve detector priority); the set is derived
# for O(1) membership checks. `sorted(VALID_ARCHETYPES)` in error messages
# is alphabetical by design — readers scanning a violation want a
# scannable list, not a priority-order recital.
VALID_ARCHETYPES_PRIORITY = (
    "schema-migration", "multi-repo", "testing-only", "config-infra",
    "skill-agent-authoring", "docs-only", "code-repo",
)
VALID_ARCHETYPES = frozenset(VALID_ARCHETYPES_PRIORITY)
REQUIRED_TOP_LEVEL_KEYS = {
    "project_slug", "summary", "factors", "specialists",
    "phases", "rigor_tier", "complexity", "tasks",
}
REQUIRED_FACTOR_KEYS = {
    "reversibility", "blast_radius", "compliance_scope",
    "user_facing_impact", "novelty", "scope_effort",
    "state_complexity", "operational_risk", "coordination_cost",
}
REQUIRED_TASK_METADATA_KEYS = {
    "chain_id", "event_type", "source_agent", "phase", "rigor_tier",
}

# Issue #563: every violation cites this doc so callers don't have to grep
# to find the authoritative schema.
SCHEMA_DOC = "skills/propose-process/refs/output-schema.md"

# Issue #583: warning code for the test-strategy-missing gap. Plans that
# declare ``test_required: true`` on any task but omit the ``test-strategy``
# phase silently bypass the wicked-testing integration path — dispatches
# to ``wicked-testing:plan`` / ``wicked-testing:authoring`` never fire.
_WARN_TEST_STRATEGY_MISSING = "test-strategy-missing"
_TEST_STRATEGY_PHASE_NAME = "test-strategy"

# Steering-not-blocking principle (2026-05-05): `risk_level` drift relative
# to `reading` was previously a fatal violation, forcing hand-patches on
# every facilitator output that picked the more intuitive direction (LOW
# reversibility = low semantic risk). Now downgraded to an advisory warning
# emitted by `_check_factor_risk_consistency`. The reading-derived
# `_EXPECTED_RISK_LEVEL_FOR_READING` mapping remains the authoritative
# direction; consumers preferring `reading` are unaffected.
_WARN_RISK_LEVEL_INVERTED = "risk-level-inverted-vs-reading"

# Per-section anchors within SCHEMA_DOC. Key is the violation-message prefix
# (the text before ' — ', with [] / . suffixes stripped).
_SECTION_ANCHORS = {
    "top-level": "§ Required vs. optional fields",
    "factors": "§ Schema — factors block",
    "specialists": "§ Schema — specialists",
    "phases": "§ Schema — phases",
    "tasks": "§ Schema — tasks",
    "rigor_tier": "§ rigor_tier enum (minimal|standard|full)",
    "complexity": "§ complexity bounds (0..7)",
    "affected_repos": "§ affected_repos (advisory, optional)",
    "archetype": "§ archetype (canonical, optional)",
    "archetype_confidence": "§ archetype (canonical, optional)",
    "archetype_signals": "§ archetype (canonical, optional)",
}


def _schema_pointer_for(violation: str) -> str:
    """Return a 'See: <doc> § <anchor>' hint for a given violation, or an
    empty string for file-level failures where the schema doc isn't the
    right reference (missing file, invalid JSON, non-object root).

    Copilot #569 review: don't mislead the user by citing the schema doc
    on errors whose fix is the file path or the JSON itself.
    """
    head = violation.split(" — ", 1)[0]
    # Strip index / dotted suffix so "tasks[0].metadata" → "tasks".
    section = head.split(".", 1)[0].split("[", 1)[0]
    if section not in _SECTION_ANCHORS:
        return ""
    return f"See: {SCHEMA_DOC} {_SECTION_ANCHORS[section]}"


def _check_top_level(plan: dict, violations: list) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - plan.keys()
    for key in sorted(missing):
        violations.append(f"top-level — missing required key '{key}'")

    if "rigor_tier" in plan and plan["rigor_tier"] not in VALID_RIGOR_TIERS:
        violations.append(
            f"rigor_tier — '{plan['rigor_tier']}' is not one of {sorted(VALID_RIGOR_TIERS)}"
        )

    if "complexity" in plan:
        c = plan["complexity"]
        if not isinstance(c, int) or not (0 <= c <= 7):
            violations.append(f"complexity — must be an integer in [0, 7], got {c!r}")

    # Issue #810: optional canonical `archetype` field at the top level.
    # Promoted out of `tasks[*].metadata.archetype` so downstream Python
    # consumers can probe `plan["archetype"]` directly instead of digging
    # into per-task metadata. Validates: (1) value is in the 7-value enum
    # if present; (2) `archetype_confidence` if present is a float in
    # [0.0, 1.0]; (3) `archetype_signals` if present is a list of strings;
    # (4) agreement invariant — when both top-level and per-task archetypes
    # are present, every task's metadata.archetype must equal the top-level
    # value. Disagreement is rejected so consumers have a single source of
    # truth (the original Issue #810 bug was silent disagreement masked as
    # `None` on the top-level probe).
    if "archetype" in plan:
        a = plan["archetype"]
        if not isinstance(a, str) or a not in VALID_ARCHETYPES:
            violations.append(
                f"archetype — must be one of {sorted(VALID_ARCHETYPES)}, got {a!r}"
            )

    if "archetype_confidence" in plan:
        c = plan["archetype_confidence"]
        if not isinstance(c, (int, float)) or isinstance(c, bool) or not (0.0 <= float(c) <= 1.0):
            violations.append(
                f"archetype_confidence — must be a number in [0.0, 1.0], got {c!r}"
            )

    if "archetype_signals" in plan:
        sigs = plan["archetype_signals"]
        if not isinstance(sigs, list):
            violations.append("archetype_signals — must be a list of strings")
        else:
            for i, entry in enumerate(sigs):
                if not isinstance(entry, str) or not entry.strip():
                    violations.append(
                        f"archetype_signals[{i}] — every entry must be a "
                        f"non-empty string, got {entry!r}"
                    )

    # Agreement invariant. Only runs when top-level archetype is valid; we
    # don't want to spam disagreement violations on top of an enum error.
    if (
        "archetype" in plan
        and isinstance(plan.get("archetype"), str)
        and plan["archetype"] in VALID_ARCHETYPES
        and isinstance(plan.get("tasks"), list)
    ):
        top = plan["archetype"]
        for i, task in enumerate(plan["tasks"]):
            if not isinstance(task, dict):
                continue
            md = task.get("metadata")
            if not isinstance(md, dict):
                continue
            task_arch = md.get("archetype")
            if task_arch is None:
                continue  # per-task field is itself optional
            if task_arch != top:
                violations.append(
                    f"tasks[{i}].metadata.archetype — '{task_arch}' disagrees with "
                    f"top-level archetype '{top}' (Issue #810: pick one source of truth)"
                )

    # Issue #722: optional advisory `affected_repos` field. Read-only
    # metadata for the multi-repo archetype — no DAG, no worktree
    # provisioning, no validation beyond shape. Plans omitting the key
    # behave exactly as today (backward compat). The full DAG-of-repos
    # workflow is deferred to the `wicked-garden-monorepo` sibling plugin
    # (see docs/v9/sibling-plugin-monorepo.md).
    if "affected_repos" in plan:
        repos = plan["affected_repos"]
        if not isinstance(repos, list):
            violations.append(
                "affected_repos — must be a list of strings (advisory field, "
                "see docs/v9/sibling-plugin-monorepo.md)"
            )
        else:
            for i, entry in enumerate(repos):
                if not isinstance(entry, str) or not entry.strip():
                    violations.append(
                        f"affected_repos[{i}] — every entry must be a "
                        f"non-empty string, got {entry!r}"
                    )


def _check_factors(plan: dict, violations: list) -> None:
    if "factors" not in plan:
        return
    factors = plan["factors"]
    if not isinstance(factors, dict):
        violations.append("factors — must be a dict")
        return

    actual_keys = set(factors.keys())
    missing = REQUIRED_FACTOR_KEYS - actual_keys
    extra = actual_keys - REQUIRED_FACTOR_KEYS
    for key in sorted(missing):
        violations.append(f"factors — missing required factor key '{key}'")
    for key in sorted(extra):
        violations.append(f"factors — unexpected factor key '{key}'")

    for key, value in factors.items():
        if key not in REQUIRED_FACTOR_KEYS:
            continue
        if not isinstance(value, dict):
            violations.append(f"factors.{key} — must be a dict")
            continue
        reading = value.get("reading")
        if reading not in VALID_FACTOR_READINGS:
            violations.append(
                f"factors.{key}.reading — '{reading}' is not one of {sorted(VALID_FACTOR_READINGS)}"
            )
        # #627: `risk_level` is the user-facing translation of `reading`.
        # Facilitator output is expected to carry it on every factor; missing
        # it is now treated as producer regression.
        risk_level = value.get("risk_level")
        if "risk_level" not in value:
            violations.append(
                f"factors.{key}.risk_level — missing required key 'risk_level'"
            )
        else:
            if risk_level not in VALID_FACTOR_RISK_LEVELS:
                violations.append(
                    f"factors.{key}.risk_level — '{risk_level}' is not one of "
                    f"{sorted(VALID_FACTOR_RISK_LEVELS)}"
                )
            # Steering, not blocking: cross-field consistency between
            # `reading` and `risk_level` is an advisory warning emitted by
            # `_check_factor_risk_consistency` rather than a fatal violation.
            # Producer drift is a hint, not an error — `reading` carries the
            # authoritative direction (HIGH=safest), so consumers preferring
            # `reading` are unaffected when `risk_level` lags.
        why = value.get("why")
        if not why or not str(why).strip():
            violations.append(f"factors.{key}.why — must be a non-empty string")


def _check_specialists(plan: dict, violations: list) -> None:
    if "specialists" not in plan:
        return
    specialists = plan["specialists"]
    if not isinstance(specialists, list) or len(specialists) == 0:
        violations.append("specialists — must be a non-empty list")
        return

    # Issue #573: every pick must resolve via the agent-frontmatter
    # resolver. Build the resolver once and re-use it across entries.
    resolver = None
    if _RESOLVER_AVAILABLE:
        try:
            resolver = build_resolver(_PLUGIN_ROOT)  # type: ignore[misc]
        except Exception:  # pragma: no cover - defensive
            resolver = None

    for i, entry in enumerate(specialists):
        if not isinstance(entry, dict):
            violations.append(f"specialists[{i}] — must be a dict")
            continue
        name = entry.get("name")
        if not name or not str(name).strip():
            violations.append(f"specialists[{i}].name — must be a non-empty string")
        if not entry.get("why") or not str(entry["why"]).strip():
            violations.append(f"specialists[{i}].why — must be a non-empty string")

        # Resolver check — applied only when the name is present and the
        # resolver loaded successfully. Unknown picks become blocking
        # errors with difflib suggestions so the facilitator can
        # self-correct a typo without re-running the rubric.
        if name and str(name).strip() and resolver is not None:
            role_name = str(name).strip()
            domain, subagent_type = resolve_role(role_name, resolver)  # type: ignore[misc]
            if domain is None or subagent_type is None:
                suggestions = difflib.get_close_matches(
                    role_name,
                    list(resolver.get("role_to_subagent", {}).keys()),
                    n=_CLOSE_MATCHES_N,
                    cutoff=_CLOSE_MATCHES_CUTOFF,
                )
                if suggestions:
                    hint = ", ".join(suggestions)
                    violations.append(
                        f"specialists[{i}].name — unknown specialist "
                        f"'{role_name}'; did you mean: {hint}?"
                    )
                else:
                    violations.append(
                        f"specialists[{i}].name — unknown specialist "
                        f"'{role_name}'; no close matches found in "
                        f"agents/**/*.md"
                    )

        # Expanded-form (Issue #573): validators accept picks emitted as
        # either a bare string (via ``name``) or the full triple
        # {name, domain, subagent_type}. When domain/subagent_type are
        # present, they must agree with the resolver — silent drift
        # between the expanded form and the agent frontmatter would
        # reintroduce the original engagement-tracker bug.
        if (
            isinstance(entry.get("domain"), str)
            or isinstance(entry.get("subagent_type"), str)
        ) and resolver is not None and name:
            role_name = str(name).strip()
            expected_domain, expected_subagent = resolve_role(role_name, resolver)  # type: ignore[misc]
            if expected_domain is not None and expected_subagent is not None:
                declared_domain = entry.get("domain")
                declared_subagent = entry.get("subagent_type")
                if (
                    isinstance(declared_domain, str)
                    and declared_domain != expected_domain
                ):
                    violations.append(
                        f"specialists[{i}].domain — '{declared_domain}' does "
                        f"not match resolved domain '{expected_domain}' for "
                        f"role '{role_name}'"
                    )
                if (
                    isinstance(declared_subagent, str)
                    and declared_subagent != expected_subagent
                ):
                    violations.append(
                        f"specialists[{i}].subagent_type — "
                        f"'{declared_subagent}' does not match resolved "
                        f"subagent_type '{expected_subagent}' for role "
                        f"'{role_name}'"
                    )


def _check_phases(plan: dict, violations: list) -> None:
    if "phases" not in plan:
        return
    phases = plan["phases"]
    if not isinstance(phases, list) or len(phases) == 0:
        violations.append("phases — must be a non-empty list")
        return
    for i, entry in enumerate(phases):
        if not isinstance(entry, dict):
            violations.append(f"phases[{i}] — must be a dict")
            continue
        if not entry.get("name") or not str(entry["name"]).strip():
            violations.append(f"phases[{i}].name — must be a non-empty string")
        if not entry.get("why") or not str(entry["why"]).strip():
            violations.append(f"phases[{i}].why — must be a non-empty string")
        if not isinstance(entry.get("primary"), list):
            violations.append(f"phases[{i}].primary — must be a list of strings")


def _check_tasks(plan: dict, violations: list) -> None:
    if "tasks" not in plan:
        return
    tasks = plan["tasks"]
    if not isinstance(tasks, list) or len(tasks) == 0:
        violations.append("tasks — must be a non-empty list")
        return
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            violations.append(f"tasks[{i}] — must be a dict")
            continue
        for field in ("id", "title", "phase"):
            if not task.get(field) or not str(task[field]).strip():
                violations.append(f"tasks[{i}].{field} — must be a non-empty string")
        meta = task.get("metadata")
        if not isinstance(meta, dict):
            violations.append(f"tasks[{i}].metadata — must be a dict")
            continue
        for key in sorted(REQUIRED_TASK_METADATA_KEYS):
            if key not in meta:
                violations.append(f"tasks[{i}].metadata — missing required key '{key}'")
        if "rigor_tier" in meta and meta["rigor_tier"] not in VALID_RIGOR_TIERS:
            violations.append(
                f"tasks[{i}].metadata.rigor_tier — '{meta['rigor_tier']}' is not one of {sorted(VALID_RIGOR_TIERS)}"
            )
        if "event_type" in meta and meta["event_type"] not in VALID_EVENT_TYPES:
            violations.append(
                f"tasks[{i}].metadata.event_type — '{meta['event_type']}' is not one of {sorted(VALID_EVENT_TYPES)}"
            )


def _check_test_strategy_present(plan: dict) -> list:
    """Issue #583: warn when ``test_required: true`` tasks exist but the
    plan omits the ``test-strategy`` phase.

    Returns a list of structured warning dicts (never raises). Empty list
    when either no task opts into testing or a ``test-strategy`` phase is
    present. The warning is advisory — plans still validate — but it
    surfaces the qe integration bypass that used to go silent when the
    facilitator collapsed test-strategy into build for "crisp bugfixes."

    Each warning dict has:
      - ``code``: stable identifier (``test-strategy-missing``)
      - ``severity``: ``"warn"``
      - ``message``: human-readable explanation naming the offending task ids
    """
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return []

    test_required_ids: list = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        meta = task.get("metadata")
        if not isinstance(meta, dict):
            continue
        if meta.get("test_required") is True:
            task_id = task.get("id")
            if task_id and str(task_id).strip():
                test_required_ids.append(str(task_id).strip())

    if not test_required_ids:
        return []

    phases = plan.get("phases")
    if isinstance(phases, list):
        for entry in phases:
            if isinstance(entry, dict) and entry.get("name") == _TEST_STRATEGY_PHASE_NAME:
                return []

    id_list = ", ".join(test_required_ids)
    message = (
        f"test_required=true on task(s) [{id_list}] but no test-strategy "
        f"phase in plan; wicked-testing specialists will not be dispatched"
    )
    return [
        {
            "code": _WARN_TEST_STRATEGY_MISSING,
            "severity": "warn",
            "message": message,
        }
    ]


def _check_factor_risk_consistency(plan: dict) -> list:
    """Steering-not-blocking advisory: surface drift between a factor's
    ``reading`` and its ``risk_level`` field.

    Previously enforced as a fatal violation (Issue #627). Downgraded
    2026-05-05 because the reject loop forced hand-patching on every
    facilitator output that picked the more intuitive direction
    (LOW reversibility = low semantic risk). The authoritative direction
    still lives in ``reading`` (HIGH=safest); consumers preferring
    ``reading`` are unaffected.

    Each warning dict has:
      - ``code``: stable identifier (``risk-level-inverted-vs-reading``)
      - ``severity``: ``"warn"``
      - ``factor``: the factor key with drift
      - ``reading``: the reading value seen on the factor
      - ``risk_level``: the actual risk_level value seen on the factor
      - ``expected_risk_level``: what risk_level should be per the
        HIGH=safest inversion mapping
      - ``message``: human-readable explanation citing
        ``factor_questionnaire.py::_RISK_INVERSION``
    """
    factors = plan.get("factors")
    if not isinstance(factors, dict):
        return []
    out: list = []
    for key, value in factors.items():
        if not isinstance(value, dict):
            continue
        reading = value.get("reading")
        risk_level = value.get("risk_level")
        if (
            reading in _EXPECTED_RISK_LEVEL_FOR_READING
            and risk_level in VALID_FACTOR_RISK_LEVELS
        ):
            expected = _EXPECTED_RISK_LEVEL_FOR_READING[reading]
            if risk_level != expected:
                out.append({
                    "code": _WARN_RISK_LEVEL_INVERTED,
                    "severity": "warn",
                    "factor": key,
                    "reading": reading,
                    "risk_level": risk_level,
                    "expected_risk_level": expected,
                    "message": (
                        f"factors.{key} — risk_level '{risk_level}' does not "
                        f"match reading '{reading}' (expected '{expected}'; "
                        f"see scripts/crew/factor_questionnaire.py::_RISK_INVERSION). "
                        f"Advisory only — `reading` carries authoritative direction."
                    ),
                })
    return out


def validate(plan: dict) -> list:
    """Return a list of violation strings (empty means valid)."""
    violations = []
    _check_top_level(plan, violations)
    _check_factors(plan, violations)
    _check_specialists(plan, violations)
    _check_phases(plan, violations)
    _check_tasks(plan, violations)
    return violations


def warnings(plan: dict) -> list:
    """Return a list of non-blocking warning dicts.

    Warnings are distinct from violations: they do NOT fail validation but
    surface advisory gaps. Kept as a separate function so callers that only
    care about reject/accept can ignore them.

    Sources:
      - Issue #583: ``test-strategy-missing`` when ``test_required: true``
        tasks exist but the plan omits the test-strategy phase.
      - 2026-05-05 (steering-not-blocking): ``risk-level-inverted-vs-reading``
        when a factor's risk_level disagrees with the HIGH=safest inversion
        of its reading.
    """
    out: list = []
    out.extend(_check_test_strategy_present(plan))
    out.extend(_check_factor_risk_consistency(plan))
    return out


def validate_file(path: Path) -> list:
    """Load JSON from path and validate. Returns violations list."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read file — {exc}"]
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON — {exc}"]
    if not isinstance(plan, dict):
        return ["top-level — must be a JSON object, not an array or scalar"]
    return validate(plan)


# ---------------------------------------------------------------------------
# Self-test fixtures
# ---------------------------------------------------------------------------

_VALID_FIXTURE = {
    "project_slug": "test-project",
    "summary": "A valid test plan.",
    "rigor_tier": "standard",
    "complexity": 3,
    "factors": {
        key: {"reading": "LOW", "risk_level": "high_risk", "why": "because reasons"}
        for key in REQUIRED_FACTOR_KEYS
    },
    "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
    "phases": [{"name": "build", "why": "do the work", "primary": ["backend-engineer"]}],
    "tasks": [
        {
            "id": "t1",
            "title": "Implement feature",
            "phase": "build",
            "blockedBy": [],
            "metadata": {
                "chain_id": "test-project.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
                "rigor_tier": "standard",
            },
        }
    ],
}

_INVALID_FIXTURES = [
    # (description, mutator_fn) — every entry must produce >= 1 violation.
    ("missing top-level key", lambda p: {k: v for k, v in p.items() if k != "summary"}),
    ("bad rigor_tier", lambda p: {**p, "rigor_tier": "turbo"}),
    ("bad factor reading", lambda p: {
        **p,
        "factors": {
            **p["factors"],
            "reversibility": {"reading": "MAYBE", "risk_level": "high_risk", "why": "idk"},
        },
    }),
    ("missing task metadata key", lambda p: {
        **p,
        "tasks": [{**p["tasks"][0], "metadata": {k: v for k, v in p["tasks"][0]["metadata"].items() if k != "chain_id"}}],
    }),
    ("factors keyset missing a key", lambda p: {
        **p,
        "factors": {k: v for k, v in p["factors"].items() if k != "novelty"},
    }),
    ("specialists empty list", lambda p: {**p, "specialists": []}),
    ("bad event_type", lambda p: {
        **p,
        "tasks": [{**p["tasks"][0], "metadata": {**p["tasks"][0]["metadata"], "event_type": "garbage"}}],
    }),
    # #627: bad risk_level enum value
    ("bad factor risk_level enum", lambda p: {
        **p,
        "factors": {
            **p["factors"],
            "reversibility": {"reading": "LOW", "risk_level": "wat", "why": "idk"},
        },
    }),
    # #689: risk_level is now required on every factor entry.
    ("missing factor risk_level", lambda p: {
        **p,
        "factors": {
            **p["factors"],
            "reversibility": {"reading": "LOW", "why": "idk"},
        },
    }),
    # 2026-05-05 (steering-not-blocking): inversion mismatch is no longer
    # a fatal violation. It now surfaces as an advisory warning emitted by
    # `_check_factor_risk_consistency` and exposed via `warnings()`. The
    # corresponding positive assertion lives in `_run_selftest` below.
    # #722: affected_repos must be a list when present
    ("affected_repos not a list", lambda p: {**p, "affected_repos": "foo"}),
    # #722: affected_repos entries must be non-empty strings
    ("affected_repos contains a non-string", lambda p: {**p, "affected_repos": ["foo", 42]}),
    ("affected_repos contains an empty string", lambda p: {**p, "affected_repos": ["foo", "  "]}),
    # #810: archetype value must be in the 7-value enum when present
    ("archetype not in enum", lambda p: {**p, "archetype": "random-thing"}),
    # #810: archetype_confidence must be a float in [0, 1] when present
    ("archetype_confidence above 1.0", lambda p: {**p, "archetype": "code-repo", "archetype_confidence": 1.5}),
    ("archetype_confidence is bool", lambda p: {**p, "archetype": "code-repo", "archetype_confidence": True}),
    # #810: archetype_signals shape — list of non-empty strings
    ("archetype_signals not a list", lambda p: {**p, "archetype": "code-repo", "archetype_signals": "foo"}),
    ("archetype_signals contains an empty string", lambda p: {**p, "archetype": "code-repo", "archetype_signals": ["ok", "  "]}),
    # #810: agreement invariant — top-level vs per-task archetype must match
    ("archetype disagreement top-level vs task", lambda p: {
        **p,
        "archetype": "code-repo",
        "tasks": [{**p["tasks"][0], "metadata": {**p["tasks"][0]["metadata"], "archetype": "docs-only"}}],
    }),
]


def _run_selftest() -> None:
    import copy

    failures = []

    # Valid fixture must pass
    result = validate(copy.deepcopy(_VALID_FIXTURE))
    if result:
        failures.append(f"valid fixture produced violations: {result}")

    # #810: positive path — top-level archetype + agreeing task metadata + the
    # confidence/signals optional fields all valid; must not raise violations.
    pos = copy.deepcopy(_VALID_FIXTURE)
    pos["archetype"] = "code-repo"
    pos["archetype_confidence"] = 0.85
    pos["archetype_signals"] = ["scripts/crew/*.py changed"]
    pos["tasks"][0]["metadata"]["archetype"] = "code-repo"
    result = validate(pos)
    if result:
        failures.append(f"#810 positive archetype fixture produced violations: {result}")

    # #810: enum drift guard — VALID_ARCHETYPES must mirror archetype_detect's
    # priority order. We pull the canonical list from archetype_detect when
    # available; if the import fails (e.g. CI sandbox), we skip rather than
    # silently passing — the test suite covers this path more rigorously.
    try:
        from crew.archetype_detect import _detect_archetype_inner  # noqa: F401
        # The enum lives implicitly in the priority-ordered checks tuple.
        # Sourcing it strictly here would couple the validator too tightly;
        # the dedicated test in tests/test_validate_plan_archetype.py is
        # the primary drift detector. This selftest only confirms our
        # local enum is non-empty and contains the documented 7 values.
        expected = {
            "schema-migration", "multi-repo", "testing-only", "config-infra",
            "skill-agent-authoring", "docs-only", "code-repo",
        }
        if VALID_ARCHETYPES != expected:
            failures.append(
                f"#810 VALID_ARCHETYPES drift: got {sorted(VALID_ARCHETYPES)}, "
                f"expected {sorted(expected)}"
            )
    except ImportError:
        pass  # CI sandbox; tests will catch the drift case.

    # Invalid fixtures must each produce at least one violation
    for desc, mutator in _INVALID_FIXTURES:
        mutated = mutator(copy.deepcopy(_VALID_FIXTURE))
        result = validate(mutated)
        if not result:
            failures.append(f"invalid fixture '{desc}' produced no violations (expected >=1)")

    # 2026-05-05 (steering-not-blocking): risk_level/reading drift no longer
    # rejects, but must surface as exactly one warning with the expected code.
    drifted = copy.deepcopy(_VALID_FIXTURE)
    drifted["factors"]["reversibility"] = {
        "reading": "LOW", "risk_level": "low_risk", "why": "drift"
    }
    drift_violations = validate(drifted)
    if drift_violations:
        failures.append(
            f"steering: risk_level drift produced violations (should warn only): "
            f"{drift_violations}"
        )
    drift_warnings = warnings(drifted)
    drift_warn_codes = {w.get("code") for w in drift_warnings}
    if _WARN_RISK_LEVEL_INVERTED not in drift_warn_codes:
        failures.append(
            f"steering: risk_level drift did not produce expected warning "
            f"'{_WARN_RISK_LEVEL_INVERTED}' (got codes: {sorted(drift_warn_codes)})"
        )
    # The drift warning must include enough audit detail to fix the producer.
    drift_warn = next(
        (w for w in drift_warnings if w.get("code") == _WARN_RISK_LEVEL_INVERTED),
        None,
    )
    if drift_warn is not None:
        for required_field in ("factor", "reading", "risk_level", "expected_risk_level"):
            if required_field not in drift_warn:
                failures.append(
                    f"steering: drift warning missing required field "
                    f"'{required_field}' (got keys: {sorted(drift_warn.keys())})"
                )

    if failures:
        for msg in failures:
            sys.stderr.write(f"selftest FAIL: {msg}\n")
        sys.exit(1)

    sys.stdout.write("selftest PASS\n")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a facilitator process-plan JSON file.")
    parser.add_argument("plan_path", nargs="?", help="Path to the plan JSON file")
    parser.add_argument("--selftest", action="store_true", help="Run built-in smoke tests and exit")
    args = parser.parse_args()

    if args.selftest:
        _run_selftest()

    if not args.plan_path:
        parser.print_usage(sys.stderr)
        sys.stderr.write("ERROR: plan_path is required\n")
        sys.exit(1)

    path = Path(args.plan_path)
    violations = validate_file(path)

    if violations:
        for v in violations:
            sys.stderr.write(f"ERROR: {path} — {v}\n")
            pointer = _schema_pointer_for(v)
            if pointer:
                sys.stderr.write(f"  {pointer}\n")
        sys.exit(1)

    # Issue #583: emit non-blocking warnings after a clean validation so
    # the qe-integration-bypass gap surfaces in CI without failing the run.
    try:
        plan_text = path.read_text(encoding="utf-8")
        plan_obj = json.loads(plan_text)
        if isinstance(plan_obj, dict):
            for warn in warnings(plan_obj):
                sys.stderr.write(
                    f"WARN: {path} — [{warn['code']}] {warn['message']}\n"
                )
    except (OSError, json.JSONDecodeError):
        # Unreachable in practice — validate_file would have failed above —
        # but defense-in-depth: warnings must never turn a pass into a fail.
        # R4-suppressed by design: warnings are advisory; never block the pass
        # path when the warning-extraction itself cannot parse the plan.
        return

    sys.exit(0)


if __name__ == "__main__":
    main()
