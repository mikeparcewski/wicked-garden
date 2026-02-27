"""
Delegation advisor adapter for wicked-smaht.

Analyzes prompts to suggest specialist delegation when domain-specific work is detected.
"""

import sys
from typing import List

from . import ContextItem


# Domain-to-specialist mapping for delegation hints
DOMAIN_HINTS = {
    "security": ("wicked-platform", "security-engineer", "Security review"),
    "architecture": ("wicked-engineering", "solution-architect", "Architecture analysis"),
    "test": ("wicked-qe", "test-strategist", "Test strategy"),
    "data": ("wicked-data", "data-analyst", "Data analysis"),
    "brainstorm": ("wicked-jam", "facilitator", "Brainstorming session"),
    "requirements": ("wicked-product", "requirements-analyst", "Requirements elicitation"),
    "agent": ("wicked-agentic", "architect", "Agentic system review"),
    "cost": ("wicked-delivery", "cost-optimizer", "Cost optimization"),
    "review": ("wicked-engineering", "senior-engineer", "Code review"),
    "debug": ("wicked-engineering", "debugger", "Debugging session"),
    "performance": ("wicked-platform", "performance-engineer", "Performance analysis"),
    "ux": ("wicked-product", "ux-researcher", "UX research"),
    "compliance": ("wicked-platform", "compliance-auditor", "Compliance review"),
}

# Keywords that suggest delegatable work
DOMAIN_KEYWORDS = {
    "security": ["security", "auth", "encrypt", "vulnerability", "owasp", "csrf", "xss", "secure", "authentication", "authorization"],
    "architecture": ["architecture", "design", "system design", "component", "api contract", "scalability", "microservice"],
    "test": ["test", "testing", "coverage", "scenario", "qa", "quality", "e2e", "integration test", "unit test"],
    "data": ["data", "analytics", "pipeline", "etl", "database", "query", "csv", "sql", "warehouse"],
    "brainstorm": ["brainstorm", "ideas", "explore", "alternatives", "perspectives", "ideation"],
    "requirements": ["requirements", "user story", "acceptance criteria", "stakeholder", "feature request"],
    "agent": ["agent", "agentic", "llm", "prompt", "guardrail", "tool use", "subagent"],
    "cost": ["cost", "budget", "cloud spend", "optimization", "right-sizing", "finops"],
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
        plugin, agent, desc = DOMAIN_HINTS[domain]
        hint_text = (
            f"{desc} detected — consider delegating to specialist:\n"
            f"Task(subagent_type=\"{plugin}:{agent}\", prompt=\"...\")"
        )

        items.append(ContextItem(
            id=f"delegation-{domain}",
            source="delegation",
            title=f"Delegation: {desc}",
            summary=f"Consider: {plugin}:{agent}",
            excerpt=hint_text,
            relevance=0.7,  # High relevance for actionable delegation advice
            age_days=0,
            metadata={
                "domain": domain,
                "plugin": plugin,
                "agent": agent,
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
