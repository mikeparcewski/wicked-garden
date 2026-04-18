#!/usr/bin/env python3
"""
Swarm trigger detection — Quality Coalition crisis detector.

Analyzes a project's gate history for BLOCK/REJECT findings. If 3+ are
detected across recent gates, returns a swarm recommendation; otherwise
returns None.

Extracted from scripts/crew/smart_decisioning.py in Gate 4 Phase 2 of the
v6 rebuild (epic #428). Behavior is preserved verbatim from the original
function at smart_decisioning.py lines ~1771-1852 (issue #395).

Original owner module (smart_decisioning.py) is deleted in v6. A follow-up
may replace the in-memory gate-list input with a wicked-bus query over
`event_type=gate-finding` events; the public API here is stable so that
swap is internal.

Usage:
    from swarm_trigger import detect_swarm_trigger
    result = detect_swarm_trigger(gate_results)  # list[dict]
    if result:
        # result = {formation, coalition_specialists, priority,
        #           block_count, affected_phases, reason}
        ...

stdlib-only. Fails open — returns None on empty input, never raises
on malformed gate dicts (missing keys default to empty strings).
"""

from typing import List, Optional


# Domain keywords used to map gate block reasons to specialist domains.
# Kept in-module so this file is self-contained and stdlib-only.
_DOMAIN_KEYWORDS_FOR_SWARM = {
    "engineering": ["code", "implementation", "build", "compile", "syntax", "logic"],
    "qe": ["test", "coverage", "quality", "regression", "assertion", "validation"],
    "platform": ["deploy", "infra", "security", "pipeline", "ci/cd", "config"],
    "product": ["requirement", "acceptance", "criteria", "scope", "spec"],
    "data": ["data", "schema", "migration", "query", "etl"],
    "design": ["ui", "ux", "accessibility", "layout", "design"],
}


def detect_swarm_trigger(gate_results: List[dict]) -> Optional[dict]:
    """Detect whether accumulated gate failures warrant a swarm response.

    Analyzes a project's gate history for BLOCK/REJECT findings. If 3+ are
    detected across recent gates, returns a swarm recommendation. Otherwise
    returns None.

    Args:
        gate_results: List of gate result dicts, each with at minimum:
            - verdict: str ("PASS", "CONDITIONAL", "BLOCK", "REJECT")
            - phase: str (which phase the gate belongs to)
            - reason: str (human-readable explanation, optional)
            - domain: str (which domain area, optional)

    Returns:
        Swarm recommendation dict or None.
    """
    if not gate_results:
        return None

    # Count BLOCK/REJECT findings
    block_results = [
        g for g in gate_results
        if g.get("verdict", "").upper() in ("BLOCK", "REJECT")
    ]

    if len(block_results) < 3:
        return None

    # Determine which specialist domains are relevant based on gate reasons
    coalition_specialists: List[str] = []
    seen_specialists: set = set()
    affected_phases: List[str] = []

    for gate in block_results:
        phase = gate.get("phase", "unknown")
        if phase not in affected_phases:
            affected_phases.append(phase)

        # Check explicit domain field first
        domain = gate.get("domain", "")
        if domain and domain not in seen_specialists:
            seen_specialists.add(domain)
            coalition_specialists.append(domain)

        # Infer domains from reason text
        reason = (gate.get("reason") or "").lower()
        for specialist, keywords in _DOMAIN_KEYWORDS_FOR_SWARM.items():
            if specialist not in seen_specialists:
                if any(kw in reason for kw in keywords):
                    seen_specialists.add(specialist)
                    coalition_specialists.append(specialist)

    # Always include qe and engineering in a swarm — they're the baseline
    for base in ("qe", "engineering"):
        if base not in seen_specialists:
            coalition_specialists.append(base)

    phases_str = ", ".join(affected_phases[:5])
    return {
        "formation": "swarm",
        "coalition_specialists": coalition_specialists,
        "priority": "crisis",
        "block_count": len(block_results),
        "affected_phases": affected_phases,
        "reason": (
            f"Quality coalition triggered: {len(block_results)} BLOCK/REJECT "
            f"findings detected across gates ({phases_str}). "
            f"Concentrating {len(coalition_specialists)} specialists to resolve "
            f"before other work proceeds."
        ),
    }


if __name__ == "__main__":
    # Inline self-test: 3 BLOCK findings should trigger a swarm.
    sample = [
        {"verdict": "BLOCK", "phase": "build", "reason": "test coverage too low"},
        {"verdict": "REJECT", "phase": "review", "reason": "security scan failed"},
        {"verdict": "BLOCK", "phase": "build", "reason": "missing acceptance criteria"},
    ]
    result = detect_swarm_trigger(sample)
    assert result is not None, "expected swarm trigger on 3 blocks"
    assert result["block_count"] == 3
    assert "qe" in result["coalition_specialists"]
    assert "engineering" in result["coalition_specialists"]
    assert "product" in result["coalition_specialists"]  # via acceptance keyword
    assert "platform" in result["coalition_specialists"]  # via security keyword

    # 2 blocks should NOT trigger
    fewer = sample[:2]
    assert detect_swarm_trigger(fewer) is None

    # Empty should NOT trigger
    assert detect_swarm_trigger([]) is None

    print("swarm_trigger self-test: PASS")
