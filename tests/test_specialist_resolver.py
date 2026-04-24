"""Tests for scripts/crew/specialist_resolver.py and its two call sites.

Issue #573: Three naming systems (domain / bare role / full subagent_type)
used to collide. The facilitator emits bare roles, the engagement tracker
expected the full form, and the mismatch silently dropped events.

These tests cover the seven acceptance behaviors from the issue:

1. ``build_resolver()`` covers every agent in ``agents/**/*.md``.
2. ``resolve_role("requirements-analyst")`` returns the product triple.
3. ``resolve_role(full_subagent_type)`` is idempotent.
4. Unknown roles return ``(None, None)`` without raising.
5. ``_parse_specialist_from_agent_type`` now accepts bare roles.
6. ``validate_plan`` rejects unknown picks and suggests close matches.
7. (meta) these tests exist — covered by pytest collection.

Every test docstring cites Issue #573 per T1-T6.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
# Hooks and scripts use different sys.path conventions; tests reach into
# both. conftest.py has already inserted scripts/ at position 0, so all
# we need here is the hooks directory for the subagent_lifecycle test.
_HOOKS_SCRIPTS = str(_REPO_ROOT / "hooks" / "scripts")
if _HOOKS_SCRIPTS not in sys.path:
    sys.path.append(_HOOKS_SCRIPTS)

from crew import specialist_resolver


@pytest.fixture(autouse=True)
def _clear_resolver_cache():
    """Drop the lru_cache between tests so agents/ edits are re-read.

    Issue #573: the resolver is cached per plugin_root string for
    production-path O(1) lookups. Tests that swap plugin_root (or rely
    on the real repo tree being walked fresh) must clear between cases.
    """
    specialist_resolver.clear_cache()
    yield
    specialist_resolver.clear_cache()


# ---------------------------------------------------------------------------
# Acceptance #1: build_resolver covers every agent file
# ---------------------------------------------------------------------------

def test_build_resolver_covers_every_agent_file():
    """Every agents/**/*.md with a subagent_type is in the map (Issue #573)."""
    resolver = specialist_resolver.build_resolver(_REPO_ROOT)

    agents_dir = _REPO_ROOT / "agents"
    expected_subagent_types: set = set()
    for md in agents_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        for line in text.splitlines()[1:]:
            if line.strip() == "---":
                break
            if line.startswith("subagent_type:"):
                expected_subagent_types.add(line.split(":", 1)[1].strip())
                break

    missing = expected_subagent_types - set(resolver["subagent_to_role"].keys())
    # Allow collisions (same bare role in two domains) to be absent from
    # the forward map, but every subagent_type must appear in reverse.
    # Any remaining missing entries would be a resolver defect.
    assert not missing, (
        f"resolver missing {len(missing)} subagent_type(s) from agents/: "
        f"{sorted(missing)[:5]}"
    )


# ---------------------------------------------------------------------------
# Acceptance #2: bare role resolves to the expected triple
# ---------------------------------------------------------------------------

def test_resolve_role_bare_returns_domain_and_subagent_type():
    """Bare role 'requirements-analyst' -> product triple (Issue #573)."""
    resolver = specialist_resolver.build_resolver(_REPO_ROOT)
    domain, subagent_type = specialist_resolver.resolve_role(
        "requirements-analyst", resolver
    )
    assert domain == "product"
    assert subagent_type == "wicked-garden:product:requirements-analyst"


# ---------------------------------------------------------------------------
# Acceptance #3: resolve_role is idempotent on full subagent_type
# ---------------------------------------------------------------------------

def test_resolve_role_idempotent_on_full_subagent_type():
    """Full subagent_type round-trips to the same tuple (Issue #573)."""
    resolver = specialist_resolver.build_resolver(_REPO_ROOT)
    first = specialist_resolver.resolve_role("requirements-analyst", resolver)
    second = specialist_resolver.resolve_role(
        "wicked-garden:product:requirements-analyst", resolver
    )
    assert first == second
    assert first == ("product", "wicked-garden:product:requirements-analyst")


# ---------------------------------------------------------------------------
# Acceptance #4: unknown roles return (None, None) without raising
# ---------------------------------------------------------------------------

def test_resolve_role_unknown_returns_none_none():
    """Unknown role name returns (None, None), never raises (Issue #573)."""
    resolver = specialist_resolver.build_resolver(_REPO_ROOT)
    assert specialist_resolver.resolve_role("does-not-exist", resolver) == (
        None,
        None,
    )


def test_resolve_role_empty_string_returns_none_none():
    """Empty / whitespace input returns (None, None) (Issue #573)."""
    resolver = specialist_resolver.build_resolver(_REPO_ROOT)
    assert specialist_resolver.resolve_role("", resolver) == (None, None)
    assert specialist_resolver.resolve_role("   ", resolver) == (None, None)


# ---------------------------------------------------------------------------
# Acceptance #5: hook parser accepts bare roles
# ---------------------------------------------------------------------------

def test_parse_specialist_accepts_bare_role():
    """Hook's _parse_specialist_from_agent_type accepts bare role (Issue #573)."""
    from subagent_lifecycle import (
        _load_specialist_domains,
        _parse_specialist_from_agent_type,
    )

    domains = _load_specialist_domains()
    assert "product" in domains, (
        "specialist.json must list 'product' as a domain for this test"
    )

    domain, agent_name = _parse_specialist_from_agent_type(
        "requirements-analyst", domains
    )
    assert domain == "product"
    assert agent_name == "requirements-analyst"


def test_parse_specialist_preserves_qualified_behavior():
    """Fully-qualified subagent_type still parses directly (Issue #573)."""
    from subagent_lifecycle import _parse_specialist_from_agent_type

    # Simulate the legacy path: the hook passes in its loaded domain set.
    domains = {"product", "engineering", "platform"}
    domain, agent_name = _parse_specialist_from_agent_type(
        "wicked-garden:product:requirements-analyst", domains
    )
    assert domain == "product"
    assert agent_name == "requirements-analyst"


def test_parse_specialist_rejects_unknown_bare_role():
    """Bare role with no agent file still returns (None, None) (Issue #573)."""
    from subagent_lifecycle import _parse_specialist_from_agent_type

    domains = {"product", "engineering", "platform"}
    assert _parse_specialist_from_agent_type("made-up-role", domains) == (
        None,
        None,
    )


# ---------------------------------------------------------------------------
# Acceptance #6: validate_plan rejects unknown picks with close-match hints
# ---------------------------------------------------------------------------

def _valid_plan_with_specialist(name: str) -> dict:
    """Return a minimal valid plan whose specialists list contains ``name``.

    Mirrors the self-test fixture in validate_plan.py but parameterized
    on the specialist name so tests can inject known-good and known-bad
    values.
    """
    return {
        "project_slug": "test-project",
        "summary": "A test plan.",
        "rigor_tier": "standard",
        "complexity": 3,
        "factors": {
            key: {"reading": "LOW", "why": "because reasons"}
            for key in (
                "reversibility",
                "blast_radius",
                "compliance_scope",
                "user_facing_impact",
                "novelty",
                "scope_effort",
                "state_complexity",
                "operational_risk",
                "coordination_cost",
            )
        },
        "specialists": [{"name": name, "why": "writes the code"}],
        "phases": [{"name": "build", "why": "do the work", "primary": [name]}],
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


def test_validate_plan_accepts_known_specialist():
    """A resolvable bare role produces zero violations (Issue #573)."""
    from crew import validate_plan

    plan = _valid_plan_with_specialist("backend-engineer")
    violations = validate_plan.validate(plan)
    assert violations == []


def test_validate_plan_rejects_unknown_specialist_with_suggestions():
    """Unknown pick surfaces close-match suggestions (Issue #573)."""
    from crew import validate_plan

    # Typo: missing 'r' in requirements
    plan = _valid_plan_with_specialist("equirements-analyst")
    violations = validate_plan.validate(plan)

    specialist_errors = [
        v for v in violations if v.startswith("specialists[0].name")
    ]
    assert specialist_errors, (
        f"expected specialists[0].name violation, got: {violations}"
    )
    joined = " ".join(specialist_errors)
    assert "unknown specialist" in joined
    assert "requirements-analyst" in joined, (
        f"expected 'requirements-analyst' in suggestions, got: {joined}"
    )


def test_validate_plan_expanded_form_drift_rejected():
    """Expanded-form drift (wrong domain) is caught (Issue #573)."""
    from crew import validate_plan

    plan = _valid_plan_with_specialist("backend-engineer")
    # Lie about the domain: backend-engineer lives in engineering, not platform.
    plan["specialists"][0]["domain"] = "platform"
    plan["specialists"][0]["subagent_type"] = (
        "wicked-garden:platform:backend-engineer"
    )

    violations = validate_plan.validate(plan)
    assert any(
        "does not match resolved domain" in v for v in violations
    ), f"expected domain-drift violation, got: {violations}"
    assert any(
        "does not match resolved subagent_type" in v for v in violations
    ), f"expected subagent_type-drift violation, got: {violations}"


def test_validate_plan_expanded_form_agreement_accepted():
    """Expanded-form that matches the resolver is accepted (Issue #573)."""
    from crew import validate_plan

    plan = _valid_plan_with_specialist("backend-engineer")
    plan["specialists"][0]["domain"] = "engineering"
    plan["specialists"][0]["subagent_type"] = (
        "wicked-garden:engineering:backend-engineer"
    )

    violations = validate_plan.validate(plan)
    assert violations == [], (
        f"expected no violations for matching expanded form, got: {violations}"
    )
