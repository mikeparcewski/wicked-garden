"""
Delegation advisor adapter for wicked-smaht.

Analyzes prompts to suggest specialist delegation when domain-specific work is detected.
"""

import sys
from typing import List

from . import ContextItem


# Domain-to-specialist mapping for delegation hints. The plugin is skills-only:
# each worker is a context:fork skill dispatched by name via Skill(...). Values
# are (target, description). A ``wicked-garden-*`` target is invoked with the
# Skill tool; a ``wicked-testing:*`` target is an external-plugin subagent
# dispatched via Task(subagent_type=...) (QE lives in wicked-testing).
DOMAIN_HINTS = {
    "security": ("wicked-garden-platform-security-engineer", "Security review"),
    "architecture": ("wicked-garden-engineering-solution-architect", "Architecture analysis"),
    "test": ("wicked-testing:test-strategist", "Test strategy"),
    "data": ("wicked-garden-data-engineer", "Data analysis"),
    "brainstorm": ("wicked-garden-jam-brainstorm-facilitator", "Brainstorming session"),
    "requirements": ("wicked-garden-product-requirements-analyst", "Requirements elicitation"),
    "agent": ("wicked-garden-agentic-architect", "Agentic system review"),

    "review": ("wicked-garden-crew-reviewer", "Code review"),
    "debug": ("wicked-garden-engineering-solution-architect", "Debugging / root-cause analysis"),
    "performance": ("wicked-garden-agentic-performance-analyst", "Performance analysis"),
    "ux": ("wicked-garden-product-ux-designer", "UX research"),
    "compliance": ("wicked-garden-platform-compliance-officer", "Compliance review"),
}


def _dispatch_hint(target: str) -> str:
    """Render the invocation string for a delegation target.

    Fork skills (``wicked-garden-*``) are invoked with the Skill tool;
    external-plugin subagents (``wicked-testing:*``) keep Task/subagent_type.
    """
    if target.startswith("wicked-garden-"):
        return f'Skill(skill="{target}", args="...")'
    return f'Task(subagent_type="{target}", prompt="...")'

# Keywords that suggest delegatable work
DOMAIN_KEYWORDS = {
    "security": ["security", "auth", "encrypt", "vulnerability", "owasp", "csrf", "xss", "secure", "authentication", "authorization"],
    "architecture": ["architecture", "design", "system design", "component", "api contract", "scalability", "microservice"],
    "test": ["test", "testing", "coverage", "scenario", "qa", "quality", "e2e", "integration test", "unit test"],
    "data": ["data", "analytics", "pipeline", "etl", "database", "query", "csv", "sql", "warehouse"],
    "brainstorm": ["brainstorm", "ideas", "explore", "alternatives", "perspectives", "ideation"],
    "requirements": ["requirements", "user story", "acceptance criteria", "stakeholder", "feature request"],
    "agent": ["agent", "agentic", "llm", "prompt", "guardrail", "tool use", "subagent"],
    "review": ["review", "code review", "pull request", "pr review", "peer review"],
    "debug": ["debug", "error", "bug", "stacktrace", "root cause", "investigate", "troubleshoot"],
    "performance": ["performance", "latency", "throughput", "bottleneck", "optimize", "profiling"],
    "ux": ["ux", "user experience", "usability", "user research", "user flow", "interaction"],
    "compliance": ["compliance", "audit", "regulatory", "gdpr", "hipaa", "sox", "policy"],
}


async def query(prompt: str, **kwargs) -> List[ContextItem]:
    """Return delegation hints for the given prompt."""
    prompt_lower = prompt.lower()
    items = []
    detected_domains = []

    # Detect all matching domains
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            detected_domains.append(domain)

    # Create delegation hints for each detected domain
    for domain in detected_domains:
        target, desc = DOMAIN_HINTS[domain]
        hint_text = (
            f"{desc} detected — consider delegating to specialist:\n"
            f"{_dispatch_hint(target)}"
        )

        items.append(ContextItem(
            id=f"delegation-{domain}",
            source="delegation",
            title=f"Delegation: {desc}",
            summary=f"Consider: {target}",
            excerpt=hint_text,
            relevance=0.7,  # High relevance for actionable delegation advice
            age_days=0,
            metadata={
                "domain": domain,
                "target": target,
                "type": "delegation_hint",
            }
        ))

    # Suggest parallel dispatch if multiple specialists applicable
    if len(detected_domains) > 1:
        parallel_hint = (
            f"{len(detected_domains)} specialist domains detected "
            f"({', '.join(detected_domains)}) — "
            f"use parallel Task dispatches for efficiency"
        )

        items.append(ContextItem(
            id="delegation-parallel",
            source="delegation",
            title="Parallel Delegation Opportunity",
            summary=f"{len(detected_domains)} specialists applicable",
            excerpt=parallel_hint,
            relevance=0.8,  # Higher relevance for efficiency pattern
            age_days=0,
            metadata={
                "domains": detected_domains,
                "type": "parallel_hint",
            }
        ))

    return items
