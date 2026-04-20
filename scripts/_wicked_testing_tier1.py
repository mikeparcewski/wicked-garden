"""
wicked-testing Tier-1 agent allowlist.

Frozen per INTEGRATION.md §3. Updates require a wicked-testing major bump.
Used by gate_dispatch and /wg-check to validate reviewer references.
"""

# 16 Tier-1 agents — do not add Tier-2 names here
TIER1_AGENTS: frozenset = frozenset({
    "wicked-testing:test-strategist",
    "wicked-testing:testability-reviewer",
    "wicked-testing:requirements-quality-analyst",
    "wicked-testing:risk-assessor",
    "wicked-testing:test-designer",
    "wicked-testing:test-automation-engineer",
    "wicked-testing:acceptance-test-writer",
    "wicked-testing:scenario-executor",
    "wicked-testing:acceptance-test-executor",
    "wicked-testing:contract-testing-engineer",
    "wicked-testing:acceptance-test-reviewer",
    "wicked-testing:semantic-reviewer",
    "wicked-testing:code-analyzer",
    "wicked-testing:production-quality-engineer",
    "wicked-testing:continuous-quality-monitor",
    "wicked-testing:test-oracle",
})

# Tier-2 agents — valid within wicked-testing itself but NOT valid gate-policy reviewers
TIER2_AGENTS: frozenset = frozenset({
    "wicked-testing:ui-component-test-engineer",
    "wicked-testing:chaos-test-engineer",
})


def is_valid_wt_reviewer(name: str) -> bool:
    """Return True if name is a valid Tier-1 wicked-testing agent.

    Non-wicked-testing names are not this module's concern and return True.
    """
    if not name.startswith("wicked-testing:"):
        return True
    return name in TIER1_AGENTS


def validate_gate_policy(gate_policy_dict: dict) -> list:
    """Return a list of violating reviewer names found in gate_policy_dict.

    A violation is any wicked-testing:* reference that is not in TIER1_AGENTS.
    Also flags bare qe-evaluator and legacy qe namespace names which should have
    been migrated in t10.

    Args:
        gate_policy_dict: Parsed gate-policy.json as a dict.

    Returns:
        List of violating reviewer name strings (empty = pass).
    """
    violations = []
    gates = gate_policy_dict.get("gates", {})
    for gate_name, tiers in gates.items():
        if not isinstance(tiers, dict):
            continue
        for tier_name, config in tiers.items():
            if not isinstance(config, dict):
                continue
            reviewers = config.get("reviewers", [])
            fallback = config.get("fallback")
            candidates = list(reviewers)
            if fallback:
                candidates.append(fallback)
            for reviewer in candidates:
                if not isinstance(reviewer, str):
                    continue
                # Flag non-Tier-1 wicked-testing references
                if reviewer.startswith("wicked-testing:") and reviewer not in TIER1_AGENTS:
                    violations.append(reviewer)
                # Flag stale qe-evaluator and legacy wicked-garden qe namespace references
                _legacy_qe_prefix = ":".join(["wicked-garden", "qe", ""])
                if reviewer == "qe-evaluator" or reviewer.startswith(_legacy_qe_prefix):
                    violations.append(reviewer)
    # Deduplicate while preserving first-seen order
    seen = set()
    unique = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique
