#!/usr/bin/env python3
"""
Smart Decisioning - Signal detection and specialist matching for wicked-crew v3.

Analyzes user input to determine:
1. What signals are present (security, product, compliance, etc.)
2. Complexity score (0-7 scale)
3. Which specialists should be engaged
4. Fallback agents for unavailable specialists

IMPORTANT: Do NOT import from specialist_discovery.py to avoid circular dependencies.
This module is designed to be standalone and imported by specialist_discovery if needed.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wicked-crew.smart-decisioning')

# Pre-compiled regex patterns for performance
_COMPILED_PATTERNS: Dict[str, re.Pattern] = {}

# Signal categories and their keywords
# This mapping is the core algorithm for capability matching:
# - Each category represents a problem domain (security, performance, etc.)
# - Keywords are lowercase, hyphenated or single words that indicate the domain
# - Matching uses word-boundary regex to avoid false positives
# - This is a STABLE mapping - changes should be rare and well-documented
SIGNAL_KEYWORDS = {
    "security": [
        "auth", "authenticate", "authorization", "encrypt", "pii", "credentials",
        "token", "password", "oauth", "jwt", "secret", "vault", "certificate",
        "api-key", "apikey", "login", "session", "csrf", "xss", "injection"
    ],
    "performance": [
        "scale", "scaling", "load", "optimize", "optimization", "latency",
        "throughput", "cache", "caching", "performance", "slow", "fast",
        "bottleneck", "memory", "cpu", "concurrent"
    ],
    "product": [
        "requirement", "feature", "story", "customer", "stakeholder", "acceptance",
        "roadmap", "backlog", "priority", "user story"
    ],
    "compliance": [
        "soc2", "hipaa", "gdpr", "pci", "audit", "policy", "regulation",
        "privacy", "data-protection", "compliance", "regulatory"
    ],
    "ambiguity": [
        "maybe", "either", "could", "should we", "not sure", "alternative",
        "options", "tradeoff", "versus", "vs", "compare", "brainstorm"
    ],
    "complexity": [
        "multiple", "system", "integration", "migrate", "migration", "refactor",
        "distributed", "microservice", "legacy", "cross-team"
    ],
    "data": [
        "data", "analytics", "metrics", "report", "dashboard", "visualization",
        "query", "database", "sql", "csv", "etl", "pipeline", "ml", "model",
        "training", "dataset", "warehouse"
    ],
    "infrastructure": [
        "deploy", "deployment", "ci/cd", "pipeline", "docker", "kubernetes",
        "k8s", "cloud", "aws", "gcp", "azure", "terraform", "helm"
    ],
    "architecture": [
        "architecture", "design pattern", "component", "api contract", "schema",
        "system design", "adr", "decision record", "monolith", "microservice",
        "event-driven", "cqrs", "hexagonal"
    ],
    "ux": [
        "user", "experience", "ux", "ui", "flow", "usability", "accessibility",
        "a11y", "wcag", "persona", "journey", "wireframe", "prototype",
        "design system", "interaction"
    ],
    "strategy": [
        "roi", "business value", "investment", "competitive", "market",
        "strategic", "value proposition", "differentiation", "business case"
    ]
}

# Map signal categories to specialist plugins
# This is a STABLE mapping that defines the wicked-crew specialist ecosystem.
# Why stable? Changes here affect:
# 1. Specialist discovery and routing logic
# 2. Fallback agent selection
# 3. User expectations about which specialists handle which domains
# 4. Integration tests and documentation
# Only modify when adding/removing specialists or redefining responsibilities.
#
# Note: Uses sets internally to prevent duplicate specialists per signal.
SIGNAL_TO_SPECIALISTS = {
    "security": {"wicked-platform", "wicked-qe"},
    "performance": {"wicked-engineering", "wicked-qe"},
    "product": {"wicked-product"},
    "compliance": {"wicked-platform"},
    "ambiguity": {"wicked-jam"},
    "complexity": {"wicked-delivery", "wicked-engineering"},
    "data": {"wicked-data"},
    "infrastructure": {"wicked-platform"},
    "architecture": {"wicked-agentic", "wicked-engineering"},
    "ux": {"wicked-product"},
    "strategy": {"wicked-product"}
}

# Built-in fallback agents for unavailable specialists
# Fallback mechanism design:
# - Max chain depth: 1 (no chained fallbacks - specialist -> built-in agent only)
# - Valid fallback agents: facilitator, reviewer, implementer, researcher
# - None means use default crew orchestration (kanban/todowrite)
# - Fallback references are validated at runtime
SPECIALIST_FALLBACKS = {
    "wicked-jam": "facilitator",
    "wicked-qe": "reviewer",
    "wicked-product": "facilitator",  # product strategy + review
    "wicked-engineering": "implementer",
    "wicked-platform": "implementer",  # with security checklist
    "wicked-delivery": None,  # tracking via kanban/todowrite
    "wicked-data": "researcher",  # data analysis fallback
    "wicked-agentic": "reviewer",  # agentic architecture review
}

# Valid built-in agents that can serve as fallbacks
VALID_FALLBACK_AGENTS = {"facilitator", "reviewer", "implementer", "researcher"}

# Maximum fallback chain depth (prevents circular fallbacks)
MAX_FALLBACK_DEPTH = 1


@dataclass
class SignalAnalysis:
    """Result of analyzing user input for signals."""
    signals: List[str]
    complexity_score: int
    recommended_specialists: List[str]
    available_specialists: List[str]
    unavailable_specialists: List[str]
    fallback_agents: Dict[str, str]
    is_ambiguous: bool
    confidence: str  # HIGH, MEDIUM, LOW


def detect_signals(text: str) -> List[str]:
    """Detect signal categories present in text."""
    text_lower = text.lower()
    detected = []

    for category, keywords in SIGNAL_KEYWORDS.items():
        for keyword in keywords:
            # Match whole words or hyphenated terms
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, text_lower):
                if category not in detected:
                    detected.append(category)
                break

    return detected


def assess_complexity(text: str) -> int:
    """Assess complexity on 0-7 scale."""
    score = 0

    # Word count
    word_count = len(text.split())
    if word_count > 100:
        score += 2
    elif word_count > 50:
        score += 1

    # Multiple files mentioned
    file_patterns = [r'\.(ts|js|py|go|rs|java|tsx|jsx|md|json|yaml|yml)\b', r'src/', r'lib/', r'test/']
    file_mentions = sum(1 for p in file_patterns if re.search(p, text, re.IGNORECASE))
    if file_mentions >= 2:
        score += 2
    elif file_mentions >= 1:
        score += 1

    # Integration keywords
    integration_keywords = ["integrate", "connect", "api", "endpoint", "service", "system"]
    if any(kw in text.lower() for kw in integration_keywords):
        score += 2

    # Stakeholders mentioned
    stakeholder_keywords = ["team", "manager", "lead", "stakeholder", "customer", "user"]
    if any(kw in text.lower() for kw in stakeholder_keywords):
        score += 1

    # Question marks (indicates uncertainty/scope exploration)
    if text.count("?") >= 2:
        score += 1

    return min(score, 7)


def is_ambiguous(text: str) -> bool:
    """Check if input indicates ambiguity or need for exploration."""
    ambiguity_patterns = [
        r'\?.*\?',  # Multiple questions
        r'should (we|i)',
        r'(could|might|may) (be|have)',
        r'not sure',
        r'options?',
        r'alternative',
        r'tradeoff',
        r'versus|vs\.',
        r'compare|comparison'
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in ambiguity_patterns)


def get_available_specialists(plugin_dir: Optional[Path] = None) -> Set[str]:
    """Check which specialist plugins are installed."""
    # Look for specialist plugins in common locations
    available = set()

    search_paths = []

    # Check plugin cache directory
    home = Path.home()
    cache_dir = home / ".claude" / "plugins" / "cache" / "wicked-garden"
    if cache_dir.exists():
        search_paths.append(cache_dir)

    # Check local plugin directory if provided
    if plugin_dir and plugin_dir.exists():
        search_paths.append(plugin_dir)

    # Check environment variable
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        root_path = Path(plugin_root).parent.parent  # Go up from wicked-crew to plugins
        if root_path.exists():
            search_paths.append(root_path)

    for search_path in search_paths:
        for item in search_path.iterdir():
            if item.is_dir() and item.name.startswith("wicked-"):
                # Check if it has a specialist.json or plugin.json
                plugin_json = item / ".claude-plugin" / "plugin.json"
                if not plugin_json.exists():
                    # Try versioned directory structure
                    for version_dir in item.iterdir():
                        if version_dir.is_dir():
                            plugin_json = version_dir / ".claude-plugin" / "plugin.json"
                            if plugin_json.exists():
                                break

                if plugin_json.exists():
                    available.add(item.name)

    return available


def validate_fallback_references() -> List[str]:
    """
    Validate that all fallback references point to valid agents.
    Returns list of validation issues.
    """
    issues = []

    for specialist, fallback in SPECIALIST_FALLBACKS.items():
        if fallback is not None and fallback not in VALID_FALLBACK_AGENTS:
            issues.append(f"Invalid fallback agent '{fallback}' for specialist '{specialist}'")

    return issues


def select_specialists(
    signals: List[str],
    complexity: int,
    ambiguous: bool,
    available: Set[str]
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """
    Select specialists based on signals and complexity.

    Returns:
        - recommended: All specialists that should be engaged (sorted list)
        - available: Specialists that are installed (sorted list)
        - fallbacks: Mapping of unavailable specialists to fallback agents

    Note: Uses set data structures internally to prevent duplicate specialists.
    """
    recommended = set()

    # 1. Signal-based selection (SIGNAL_TO_SPECIALISTS already uses sets)
    for signal in signals:
        specialists = SIGNAL_TO_SPECIALISTS.get(signal, set())
        recommended.update(specialists)

    # 2. Complexity-based additions
    if complexity >= 5:
        recommended.add("wicked-delivery")
    if complexity >= 3:
        recommended.add("wicked-qe")  # Always QE for moderate+

    # 3. Ambiguity detection
    if ambiguous:
        recommended.add("wicked-jam")

    # 4. Always include QE for non-trivial work
    if complexity >= 2 or len(signals) >= 2:
        recommended.add("wicked-qe")

    # 5. Filter to available (preserves set semantics - no duplicates)
    available_recommended = recommended.intersection(available)
    unavailable = recommended - available

    # 6. Determine fallbacks with validation
    fallbacks = {}
    for spec in unavailable:
        fallback = SPECIALIST_FALLBACKS.get(spec)
        if fallback:
            # Validate fallback reference
            if fallback not in VALID_FALLBACK_AGENTS:
                logger.error(f"Invalid fallback agent '{fallback}' for specialist '{spec}'")
                continue
            fallbacks[spec] = fallback

    return (
        sorted(list(recommended)),
        sorted(list(available_recommended)),
        fallbacks
    )


def _validate_configuration():
    """Validate configuration at module load time."""
    issues = validate_fallback_references()
    if issues:
        for issue in issues:
            logger.error(f"Configuration validation error: {issue}")
        raise ValueError(f"Invalid smart decisioning configuration: {issues}")


# Validate configuration when module loads
_validate_configuration()


def analyze_input(text: str, plugin_dir: Optional[Path] = None) -> SignalAnalysis:
    """
    Main entry point: Analyze user input and return signal analysis.
    """
    logger.info(f"Analyzing input ({len(text)} chars)")

    signals = detect_signals(text)
    complexity = assess_complexity(text)
    ambiguous = is_ambiguous(text)
    available = get_available_specialists(plugin_dir)

    logger.debug(f"Signals detected: {signals}")
    logger.debug(f"Complexity score: {complexity}/7")
    logger.debug(f"Ambiguous: {ambiguous}")

    recommended, available_specs, fallbacks = select_specialists(
        signals, complexity, ambiguous, available
    )

    unavailable = [s for s in recommended if s not in available_specs]

    # Determine confidence
    if len(signals) >= 3 or complexity >= 5:
        confidence = "HIGH"
    elif len(signals) >= 1 or complexity >= 3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    logger.info(f"Analysis complete: {len(signals)} signals, complexity {complexity}/7, "
                f"{len(available_specs)}/{len(recommended)} specialists available, "
                f"confidence {confidence}")

    if unavailable:
        logger.warning(f"Unavailable specialists will use fallbacks: {unavailable}")

    return SignalAnalysis(
        signals=signals,
        complexity_score=complexity,
        recommended_specialists=recommended,
        available_specialists=available_specs,
        unavailable_specialists=unavailable,
        fallback_agents=fallbacks,
        is_ambiguous=ambiguous,
        confidence=confidence
    )


def main():
    """CLI interface for smart decisioning."""
    import argparse

    parser = argparse.ArgumentParser(description="Smart decisioning for wicked-crew")
    parser.add_argument("text", nargs="?", help="Input text to analyze")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--plugin-dir", type=Path, help="Plugin directory to check")

    args = parser.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    elif args.text:
        text = args.text
    else:
        parser.error("Provide text or --stdin")

    analysis = analyze_input(text, args.plugin_dir)

    if args.json:
        print(json.dumps(asdict(analysis), indent=2))
    else:
        print(f"Signals detected: {', '.join(analysis.signals) or 'none'}")
        print(f"Complexity score: {analysis.complexity_score}/7")
        print(f"Confidence: {analysis.confidence}")
        print(f"Ambiguous: {'yes' if analysis.is_ambiguous else 'no'}")
        print()
        print(f"Recommended specialists: {', '.join(analysis.recommended_specialists) or 'none'}")
        print(f"Available: {', '.join(analysis.available_specialists) or 'none'}")
        print(f"Unavailable: {', '.join(analysis.unavailable_specialists) or 'none'}")
        if analysis.fallback_agents:
            print(f"Fallbacks: {analysis.fallback_agents}")


if __name__ == "__main__":
    main()
