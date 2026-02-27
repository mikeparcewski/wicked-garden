#!/usr/bin/env python3
"""
Smart Decisioning - Signal detection and specialist matching for wicked-crew v3.

Analyzes user input to determine:
1. What signals are present (security, product, compliance, etc.)
2. Risk dimensions: impact (0-3), reversibility (0-3), novelty (0-3)
3. Complexity score (0-7 scale, derived from dimensions)
4. Which specialists should be engaged
5. Fallback agents for unavailable specialists

IMPORTANT: Do NOT import from specialist_discovery.py to avoid circular dependencies.
This module is designed to be standalone and imported by specialist_discovery if needed.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wicked-crew.smart-decisioning')

# ---------------------------------------------------------------------------
# Signal categories and their keywords
# ---------------------------------------------------------------------------
# This mapping is the core algorithm for capability matching:
# - Each category represents a problem domain (security, performance, etc.)
# - Keywords are lowercase; keywords ending with * are stem-matched
# - Matching uses word-boundary regex to avoid false positives
# - This is a STABLE mapping - changes should be rare and well-documented
SIGNAL_KEYWORDS = {
    "security": [
        "auth*", "encrypt*", "pii", "credential*",
        "token*", "password", "oauth", "jwt", "secret*", "vault", "certific*",
        "login", "session", "csrf", "xss", "inject*",
        "security", "permiss*", "rbac",
    ],
    "performance": [
        "scal*", "load", "optimi*", "latency",
        "throughput", "cache", "caching", "performance", "slow", "fast",
        "bottleneck", "memory", "cpu", "concurren*", "benchmark*",
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
        "distributed", "microservice", "legacy", "cross-team",
        "downstream", "cascading", "cross-cutting", "foundational", "core module",
        "affects all",
    ],
    "data": [
        "data", "analytics", "metrics", "report*", "dashboard", "visuali*",
        "query", "database", "sql", "csv", "etl", "pipeline", "ml", "model",
        "training", "dataset", "warehouse", "schema", "ontology",
    ],
    "infrastructure": [
        "deploy", "deployment", "ci/cd", "pipeline", "docker", "kubernetes",
        "k8s", "cloud", "aws", "gcp", "azure", "terraform", "helm",
        "hook binding", "event handler", "event listener",
        "middleware config", "build system", "makefile", "configuration-as-code",
    ],
    "architecture": [
        "architecture", "design pattern", "component", "api contract", "schema",
        "system design", "adr", "decision record", "monolith", "microservice",
        "event-driven", "cqrs", "hexagonal",
        "algorithm", "orchestrat*", "dispatcher", "resolver", "parser", "engine",
        "scoring", "routing logic", "decision logic", "phase selection",
        "signal detection",
    ],
    "ux": [
        "user", "experience", "ux", "ui", "flow", "usability", "accessibility",
        "a11y", "wcag", "persona", "journey", "wireframe", "prototype",
        "design system", "interaction"
    ],
    "strategy": [
        "roi", "business value", "investment", "competitive", "market",
        "strategic", "value proposition", "differentiation", "business case"
    ],
    "reversibility": [
        "migrat*", "schema", "breaking change", "deprecat*", "backward incompatible",
        "drop table", "drop column", "remove api", "rename api",
        "data transform*", "restructur*", "irreversible",
        "feature flag", "toggle", "rollback", "canary", "blue-green",
    ],
    "novelty": [
        "first time", "new pattern", "prototype", "proof of concept", "poc",
        "greenfield", "from scratch", "never done", "unfamiliar",
        "research", "spike", "experiment*", "evaluat*",
    ],
}

# ---------------------------------------------------------------------------
# Map signal categories to specialist plugins
# ---------------------------------------------------------------------------
# This is a STABLE mapping that defines the wicked-crew specialist ecosystem.
# Uses sets internally to prevent duplicate specialists per signal.
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
    "strategy": {"wicked-product"},
    "reversibility": {"wicked-platform", "wicked-delivery"},
    "novelty": {"wicked-jam", "wicked-engineering"},
}

# Built-in fallback agents for unavailable specialists
SPECIALIST_FALLBACKS = {
    "wicked-jam": "facilitator",
    "wicked-qe": "reviewer",
    "wicked-product": "facilitator",
    "wicked-engineering": "implementer",
    "wicked-platform": "implementer",
    "wicked-delivery": None,
    "wicked-data": "researcher",
    "wicked-agentic": "reviewer",
}

# Valid built-in agents that can serve as fallbacks
VALID_FALLBACK_AGENTS = {"facilitator", "reviewer", "implementer", "researcher"}

# Maximum fallback chain depth (prevents circular fallbacks)
MAX_FALLBACK_DEPTH = 1

# ---------------------------------------------------------------------------
# File Role Patterns (5-tier taxonomy for impact scoring)
# ---------------------------------------------------------------------------
FILE_ROLE_PATTERNS = [
    # --- TIER 1: Behavior-defining (weight 2.0) ---
    (r'\b(?:commands?|handlers?|controllers?|routes?|middleware|interceptors?)/\S+', 2.0),
    (r'\b(?:hooks?|triggers?|listeners?|subscribers?)/\S+', 2.0),
    (r'\.github/workflows/', 2.0),
    (r'\bgitlab-ci', 2.0),
    (r'\bJenkinsfile\b', 2.0),
    (r'\.(?:tf|hcl)\b', 2.0),
    (r'\b(?:Dockerfile|docker-compose)\b', 2.0),
    (r'\bhooks\.json\b', 2.0),
    (r'\b(?:routes|pipeline|workflow|dispatch)\.(?:json|ya?ml)\b', 2.0),
    (r'\bMakefile\b', 2.0),

    # --- TIER 2: Source code (weight 1.5) ---
    (r'\b(?:src|lib|app|pkg|internal|core)/\S+', 1.5),
    (r'\bscripts?/\S+', 1.5),
    (r'\bagents?/\S+', 1.5),
    (r'\bskills?/\S+\.md\b', 1.5),
    (r'\bSKILL\.md\b', 1.5),

    # --- TIER 3: Generic code files (weight 1.0) ---
    (r'\.(?:py|ts|js|go|rs|java|rb|tsx|jsx|c|cpp|cs|swift|kt)\b', 1.0),

    # --- TIER 4: Test code (weight 1.0) ---
    (r'\b(?:tests?|spec|__tests__|e2e|cypress|playwright)/\S+', 1.0),

    # --- TIER 5: Low-impact (weight 0.5 or 0.0) ---
    (r'\bREADME\b', 0.5),
    (r'\bCHANGELOG\b', 0.5),
    (r'\bLICENSE\b', 0.0),
    (r'\b(?:docs?|examples?|samples?)/\S+', 0.5),
    (r'\.md\b', 0.5),
    (r'\.(?:json|ya?ml)\b', 0.5),
]

MAX_FILE_IMPACT = 3

# ---------------------------------------------------------------------------
# Reversibility signals (opposing signal sets)
# ---------------------------------------------------------------------------

# High irreversibility indicators (push reversibility score UP)
IRREVERSIBILITY_SIGNALS = [
    # Data changes (hardest to reverse)
    ("migrat*", 3, "data migration"),
    ("schema change", 3, "schema change"),
    ("schema migrat*", 3, "schema migration"),
    ("drop table", 3, "destructive DDL"),
    ("drop column", 3, "destructive DDL"),
    ("data transform*", 2, "data transformation"),

    # Breaking changes (hard to reverse once consumers adapt)
    ("breaking change", 3, "breaking change"),
    ("deprecat*", 2, "deprecation"),
    ("remove api", 3, "API removal"),
    ("rename api", 2, "API rename"),
    ("backward incompatible", 3, "backward incompatible"),

    # State changes (side effects persist)
    ("delete", 1, "deletion"),
    ("remove", 1, "removal"),
    ("rename", 1, "rename"),
    ("restructur*", 2, "restructuring"),

    # External dependencies
    ("third party", 1, "third-party dependency"),
    ("external api", 2, "external API"),
    ("vendor", 1, "vendor dependency"),
]

# Reversibility mitigators (push reversibility score DOWN)
REVERSIBILITY_SIGNALS = [
    ("feature flag", -2, "feature-flagged"),
    ("feature toggle", -2, "feature-flagged"),
    ("toggle", -1, "toggle available"),
    ("rollback", -1, "rollback mentioned"),
    ("revert", -1, "revert mentioned"),
    ("canary", -1, "canary deployment"),
    ("blue-green", -1, "blue-green deployment"),
    ("experiment", -1, "experimental"),
]

# ---------------------------------------------------------------------------
# Novelty signals
# ---------------------------------------------------------------------------
NOVELTY_SIGNALS = [
    ("first time", 2, "first-time work"),
    ("new pattern", 2, "new pattern"),
    ("prototype", 2, "prototype"),
    ("proof of concept", 2, "proof of concept"),
    ("poc", 2, "proof of concept"),
    ("experiment*", 1, "experimental"),
    ("greenfield", 2, "greenfield"),
    ("from scratch", 2, "built from scratch"),
    ("never done", 2, "never done before"),
    ("unfamiliar", 1, "unfamiliar territory"),
    ("research", 1, "research needed"),
    ("spike", 1, "exploration spike"),
    ("evaluat*", 1, "evaluation"),
]

# ---------------------------------------------------------------------------
# Project Archetype Detection
# ---------------------------------------------------------------------------
# Archetypes represent the TYPE of project/app being changed.
# Different archetypes have different scoring levers:
# - Content-heavy: messaging consistency matters, not tech complexity
# - UI-heavy: design/UX consistency matters, needs design review + testing
# - API/Backend: integration surface and contract stability matter
# - Infrastructure/Framework: core execution path changes have broad impact
# - Data Pipeline: data quality, lineage, and downstream effects matter
#
# The archetype adjusts impact scoring and injects relevant signals so that
# scoring reflects what actually matters for the project type.

ARCHETYPE_KEYWORDS = {
    "content-heavy": [
        "content", "copy", "messaging", "blog", "cms", "landing page",
        "marketing", "seo", "editorial", "article", "headline", "brand",
        "tone", "voice", "paragraph", "section copy", "fact*",
        "consistency", "wording",
    ],
    "ui-heavy": [
        "component", "design system", "css", "layout", "responsive",
        "animation", "theme", "style", "visual", "frontend", "react",
        "vue", "angular", "dashboard", "widget", "button", "form",
        "modal", "sidebar", "navigation", "menu", "look and feel",
        "differentiation",
    ],
    "api-backend": [
        "api", "rest", "graphql", "endpoint", "service", "server",
        "backend", "database", "query", "orm", "grpc", "websocket",
        "microservice", "gateway", "proxy", "contract",
    ],
    "infrastructure-framework": [
        "plugin", "framework", "build system", "ci/cd",
        "scaffold", "hook", "middleware", "engine", "core",
        "execution", "scoring", "routing", "dispatch", "orchestrat*",
        "phase", "workflow", "configuration", "tooling", "cli",
        "command", "agent", "prompt engineering", "behavior",
        "core path", "execution path", "foundational",
    ],
    "data-pipeline": [
        "etl", "pipeline", "data flow", "transform", "warehouse",
        "lake", "batch", "stream", "ingest", "extract", "load",
        "lineage", "dbt", "airflow", "spark",
    ],
    "mobile-app": [
        "ios", "android", "mobile", "react native", "flutter",
        "swift", "kotlin", "app store", "play store", "push notification",
        "offline", "gesture",
    ],
    "ml-ai": [
        "model", "training", "inference", "embedding", "vector",
        "llm", "fine-tune", "prompt", "rag", "evaluation", "benchmark",
        "dataset", "feature engineering", "hyperparameter",
    ],
    "compliance-regulated": [
        "hipaa", "soc2", "gdpr", "pci", "audit", "compliance",
        "regulation", "phi", "pii", "data protection", "retention",
        "consent", "privacy",
    ],
    "monorepo-platform": [
        "monorepo", "workspace", "package", "shared", "library",
        "dependency", "nx", "turborepo", "lerna", "cross-package",
        "internal package", "versioning",
    ],
    "real-time": [
        "websocket", "real-time", "realtime", "streaming", "push",
        "event-driven", "pubsub", "message queue", "kafka", "rabbitmq",
        "socket", "live update",
    ],
}

# How each archetype adjusts scoring:
# - impact_bonus: added to impact score before composite (core path changes are high-impact)
# - inject_signals: signals auto-added if not already present (with moderate confidence)
# - min_complexity: floor for complexity score (prevents underscoring important changes)
# - description: human-readable explanation of why this archetype matters
#
# NOTE: This is a FALLBACK set. Commands should do dynamic archetype analysis
# (querying memories, reading AGENTS.md/CLAUDE.md/agent.md, using blast-radius) and pass
# results via --archetype-hints. These static definitions activate when no
# external hints are available or when keyword detection finds matches.
# External hints use the same adjustment format and can define NEW archetypes
# beyond this set.
ARCHETYPE_ADJUSTMENTS = {
    "content-heavy": {
        "impact_bonus": 1,
        "inject_signals": {"product": 0.3},
        "min_complexity": 2,
        "description": "Content-heavy: messaging consistency and factual accuracy matter",
    },
    "ui-heavy": {
        "impact_bonus": 1,
        "inject_signals": {"ux": 0.3},
        "min_complexity": 2,
        "description": "UI-heavy: design consistency and user experience require review",
    },
    "api-backend": {
        "impact_bonus": 1,
        "inject_signals": {},
        "min_complexity": 2,
        "description": "API/Backend: integration surface and contract stability matter",
    },
    "infrastructure-framework": {
        "impact_bonus": 2,
        "inject_signals": {"architecture": 0.3},
        "min_complexity": 3,
        "description": "Infrastructure/Framework: core execution path changes have broad impact",
    },
    "data-pipeline": {
        "impact_bonus": 1,
        "inject_signals": {"data": 0.3},
        "min_complexity": 2,
        "description": "Data pipeline: data quality, lineage, and downstream effects matter",
    },
    "mobile-app": {
        "impact_bonus": 1,
        "inject_signals": {"ux": 0.3},
        "min_complexity": 2,
        "description": "Mobile app: platform constraints, UX patterns, and release cycles matter",
    },
    "ml-ai": {
        "impact_bonus": 1,
        "inject_signals": {"data": 0.3},
        "min_complexity": 3,
        "description": "ML/AI: model quality, training data, and evaluation rigor matter",
    },
    "compliance-regulated": {
        "impact_bonus": 2,
        "inject_signals": {"compliance": 0.5, "security": 0.3},
        "min_complexity": 3,
        "description": "Compliance/Regulated: audit trails, policy adherence, and risk documentation matter",
    },
    "monorepo-platform": {
        "impact_bonus": 2,
        "inject_signals": {"architecture": 0.3},
        "min_complexity": 3,
        "description": "Monorepo/Platform: cross-package impact, shared dependencies, and versioning matter",
    },
    "real-time": {
        "impact_bonus": 1,
        "inject_signals": {"performance": 0.3},
        "min_complexity": 2,
        "description": "Real-time: latency, concurrency, and state synchronization matter",
    },
}

# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------


def _make_pattern(keyword: str) -> str:
    """Create regex pattern from keyword, supporting stem matching.

    Keywords ending with * match as prefix stems (e.g., "migrat*" matches
    "migrate", "migration", "migrating").
    """
    if keyword.endswith("*"):
        return rf'\b{re.escape(keyword[:-1])}\w*'
    else:
        return rf'\b{re.escape(keyword)}\b'


# ---------------------------------------------------------------------------
# Pre-compiled patterns (module load time for performance)
# ---------------------------------------------------------------------------
_COMPILED_FILE_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), weight)
    for pattern, weight in FILE_ROLE_PATTERNS
]

_COMPILED_SIGNAL_PATTERNS: Dict[str, List[Tuple[re.Pattern, str]]] = {}
for _cat, _keywords in SIGNAL_KEYWORDS.items():
    _COMPILED_SIGNAL_PATTERNS[_cat] = [
        (re.compile(_make_pattern(kw)), kw)
        for kw in _keywords
    ]

_COMPILED_IRREVERSIBILITY = [
    (re.compile(_make_pattern(kw)), weight, label)
    for kw, weight, label in IRREVERSIBILITY_SIGNALS
]

_COMPILED_MITIGATORS = [
    (re.compile(_make_pattern(kw)), weight, label)
    for kw, weight, label in REVERSIBILITY_SIGNALS
]

_COMPILED_NOVELTY = [
    (re.compile(_make_pattern(kw)), weight, label)
    for kw, weight, label in NOVELTY_SIGNALS
]

_COMPILED_ARCHETYPE_PATTERNS: Dict[str, List[re.Pattern]] = {}
for _arch, _keywords in ARCHETYPE_KEYWORDS.items():
    _COMPILED_ARCHETYPE_PATTERNS[_arch] = [
        re.compile(_make_pattern(kw), re.IGNORECASE)
        for kw in _keywords
    ]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RiskDimensions:
    """Independent risk dimensions computed from text analysis.

    Each dimension is 0-3. They drive different workflow decisions:
    - impact: gate strictness (fast-pass vs full gate)
    - reversibility: rollback planning, gate type selection
    - novelty: specialist engagement, design phase inclusion
    """
    impact: int = 0
    reversibility: int = 0
    novelty: int = 0
    explanation: List[str] = field(default_factory=list)


@dataclass
class RoutingInfo:
    """How and why a specialist was selected."""
    tier: str           # REQUIRED, RECOMMENDED, OPTIONAL
    reason: str         # Human-readable explanation
    signals: List[str]  # Which signals triggered this


@dataclass
class AnalysisOverrides:
    """User-configurable overrides for signal analysis."""
    complexity_override: Optional[int] = None
    skip_signals: List[str] = field(default_factory=list)
    force_signals: List[str] = field(default_factory=list)
    skip_injection: bool = False
    signal_threshold: float = 0.1
    component_overrides: Dict[str, int] = field(default_factory=dict)


@dataclass
class ContextualVariables:
    """Optional context that modifies scoring."""
    urgency: str = "medium"         # low, medium, high, critical
    team_size: int = 1
    customer_type: str = "internal"  # internal, external, enterprise


URGENCY_MODIFIERS = {"low": -1, "medium": 0, "high": 1, "critical": 2}
CUSTOMER_SIGNAL_INJECTION = {"enterprise": ["compliance"], "external": ["security"]}


@dataclass
class SignalAnalysis:
    """Result of analyzing user input for signals."""
    signals: List[str]                              # Categories above threshold
    signal_confidences: Dict[str, float]            # Raw confidence per category
    complexity_score: int                           # 0-7 composite
    complexity_breakdown: Dict[str, int]            # Component values
    risk_dimensions: RiskDimensions
    recommended_specialists: List[str]
    available_specialists: List[str]
    unavailable_specialists: List[str]
    specialist_routing: Dict[str, RoutingInfo]      # Tier + reason per specialist
    fallback_agents: Dict[str, str]
    is_ambiguous: bool
    confidence: str                                 # HIGH, MEDIUM, LOW
    archetypes: Dict[str, float] = field(default_factory=dict)  # Detected project archetypes
    primary_archetype: Optional[str] = field(default=None)      # Highest-confidence archetype
    archetype_adjustments_applied: Dict = field(default_factory=dict)  # What adjustments were made
    flags: Dict[str, bool] = field(default_factory=dict)
    overrides_applied: Dict = field(default_factory=dict)
    memory_payload: Optional[Dict] = field(default=None)  # For caller to store via /wicked-mem:store


# ---------------------------------------------------------------------------
# Core scoring functions
# ---------------------------------------------------------------------------


def detect_signals(text: str, threshold: float = 0.1) -> Dict[str, float]:
    """Detect signal categories with confidence scores.

    Confidence = matched_keywords / total_keywords_in_category.
    Returns only categories at or above threshold.

    This replaces the old binary detection. Categories above threshold
    are considered "detected" — the confidence value indicates strength.
    """
    text_lower = text.lower()
    confidences: Dict[str, float] = {}

    for category, patterns in _COMPILED_SIGNAL_PATTERNS.items():
        if not patterns:
            continue
        matches = sum(1 for compiled, _ in patterns if compiled.search(text_lower))
        confidence = matches / len(patterns)
        if confidence >= threshold:
            confidences[category] = round(confidence, 3)

    # Merge with semantic detection if available (V2-2)
    try:
        from signal_library import get_library
        lib = get_library()
        semantic = lib.detect(text)
        for cat, score in semantic.items():
            if score >= threshold:
                confidences[cat] = max(confidences.get(cat, 0.0), round(score, 3))
    except (ImportError, Exception):
        pass  # ChromaDB not available — keyword-only mode

    return confidences


def assess_file_impact(text: str) -> int:
    """Score file mentions by functional role instead of flat counting.

    Returns 0-3 (capped to prevent file mentions from dominating).
    Uses pre-compiled patterns from _COMPILED_FILE_PATTERNS.
    First-match-wins ordering with span-overlap dedup.
    Adjacent spans (end == start) are treated as overlapping to prevent
    double-counting parts of the same file reference (e.g., "CHANGELOG.md"
    matching both CHANGELOG and .md patterns).
    """
    text_lower = text.lower()
    max_weight = 0.0
    match_count = 0
    matched_spans = []

    for compiled_pattern, weight in _COMPILED_FILE_PATTERNS:
        for match in compiled_pattern.finditer(text_lower):
            start, end = match.span()
            # Skip if this span overlaps or is adjacent to a previous match
            if any(s <= start <= e or s <= end <= e for s, e in matched_spans):
                continue

            matched_spans.append((start, end))
            max_weight = max(max_weight, weight)
            match_count += 1

    if match_count == 0:
        return 0

    # Score based on highest-impact file + breadth bonus
    base = int(max_weight)

    # Breadth bonus: multiple distinct file mentions add +1
    breadth_bonus = 1 if match_count >= 3 else 0

    return min(base + breadth_bonus, MAX_FILE_IMPACT)


def assess_impact(text: str) -> Tuple[int, List[str]]:
    """Compute impact dimension from text.

    Returns (score 0-3, list of explanation strings).
    Combines file role analysis with integration surface detection.
    Integration keywords contribute +2 (matching old scorer behavior).
    """
    score = 0
    reasons = []

    # File role impact (0-3, from assess_file_impact)
    file_impact = assess_file_impact(text)
    score += file_impact
    if file_impact >= 2:
        reasons.append(f"behavior-defining files mentioned (impact={file_impact})")
    elif file_impact >= 1:
        reasons.append(f"source code files mentioned (impact={file_impact})")

    # Integration surface (+2, matching old scorer's contribution)
    integration_keywords = ["integrate", "connect", "api", "endpoint", "service", "system"]
    text_lower = text.lower()
    matched_integration = [kw for kw in integration_keywords if kw in text_lower]
    if matched_integration:
        score += 2
        reasons.append(f"integration surface: {', '.join(matched_integration[:3])}")

    return (min(score, 3), reasons)


def assess_reversibility(text: str) -> Tuple[int, List[str]]:
    """Compute reversibility dimension from text.

    0 = trivially reversible, 3 = very hard to undo.
    Returns (score 0-3, list of explanation strings).
    """
    score = 0
    reasons = []
    text_lower = text.lower()

    for compiled, weight, label in _COMPILED_IRREVERSIBILITY:
        if compiled.search(text_lower):
            score += weight
            reasons.append(f"+{weight} {label}")

    for compiled, weight, label in _COMPILED_MITIGATORS:
        if compiled.search(text_lower):
            score += weight  # weight is negative
            reasons.append(f"{weight} {label}")

    return (max(0, min(score, 3)), reasons)


def assess_novelty(text: str, signals: List[str], is_ambiguous: bool) -> Tuple[int, List[str]]:
    """Compute novelty dimension from text, detected signals, and ambiguity.

    0 = routine/familiar, 3 = highly novel/uncertain.
    Returns (score 0-3, list of explanation strings).

    DEPENDENCY: Must be called AFTER detect_signals() since it uses the
    signal count for cross-domain scoring.
    """
    score = 0
    reasons = []
    text_lower = text.lower()

    # 1. Explicit novelty keywords (break on first match)
    for compiled, weight, label in _COMPILED_NOVELTY:
        if compiled.search(text_lower):
            score += weight
            reasons.append(f"+{weight} {label}")
            break

    # 2. Cross-domain indicator: multiple signal categories = broader scope
    if len(signals) >= 3:
        score += 2
        reasons.append(f"+2 cross-domain ({len(signals)} signal categories)")
    elif len(signals) >= 2:
        score += 1
        reasons.append(f"+1 multi-domain ({len(signals)} signal categories)")

    # 3. Ambiguity as novelty proxy
    if is_ambiguous:
        score += 1
        reasons.append("+1 ambiguity detected (uncertain scope)")

    return (min(score, 3), reasons)


def detect_archetype(text: str) -> Dict[str, float]:
    """Detect project archetype from text description.

    Returns dict of archetype -> confidence (0.0-1.0).
    Multiple archetypes can be detected simultaneously.
    Confidence is based on keyword density relative to archetype threshold.
    """
    text_lower = text.lower()
    results: Dict[str, float] = {}

    for archetype, patterns in _COMPILED_ARCHETYPE_PATTERNS.items():
        if not patterns:
            continue
        matches = sum(1 for p in patterns if p.search(text_lower))
        if matches > 0:
            # Confidence scales with match density; 30% of keywords = 1.0
            confidence = min(matches / max(len(patterns) * 0.3, 1), 1.0)
            results[archetype] = round(confidence, 3)

    return results


STAKEHOLDER_KEYWORDS = ["team", "manager", "lead", "stakeholder", "customer", "user"]


def compute_composite(
    impact: int, reversibility: int, novelty: int, text: str,
    component_overrides: Optional[Dict[str, int]] = None
) -> Tuple[int, Dict[str, int]]:
    """Derive 0-7 composite from risk dimensions + text factors.

    Returns (score, breakdown) where breakdown is a dict of component values.

    Factors:
    - impact (0-3): base score from file role + integration surface
    - risk_premium (0-2): multiplicative model — both reversibility AND novelty
      must be elevated for high premium. Eliminates the degenerate equilibrium
      where rev=3 and rev=2 produced identical outcomes under the old formula.
    - scope (0-2): word count indicator
    - coordination (0-1): stakeholder mentions
    """
    # Multiplicative risk premium: rev*nov*0.22 → capped at 2
    # 3*3*0.22=1.98→2, 2*2*0.22=0.88→1, 3*0*0.22=0→0 (degeneracy fix)
    risk_premium = min(round(reversibility * novelty * 0.22), 2)

    # Scope: word count
    word_count = len(text.split())
    scope = 2 if word_count > 100 else (1 if word_count > 50 else 0)

    # Coordination: stakeholder mentions
    coordination = 1 if any(kw in text.lower() for kw in STAKEHOLDER_KEYWORDS) else 0

    breakdown = {
        "impact": impact,
        "risk_premium": risk_premium,
        "scope": scope,
        "coordination": coordination,
    }

    # Apply per-component overrides (V2-4: editable complexity)
    if component_overrides:
        for key, value in component_overrides.items():
            if key in breakdown:
                breakdown[key] = value

    total = min(sum(breakdown.values()), 7)
    return total, breakdown


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


# ---------------------------------------------------------------------------
# Specialist discovery and selection
# ---------------------------------------------------------------------------


def get_available_specialists(plugin_dir: Optional[Path] = None) -> Set[str]:
    """Check which specialist plugins are installed."""
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
    signal_confidences: Dict[str, float],
    complexity: int,
    ambiguous: bool,
    available: Set[str]
) -> Tuple[List[str], List[str], Dict[str, str], Dict[str, RoutingInfo]]:
    """
    Select specialists based on signal confidences and complexity.

    Returns:
        - recommended: All specialists that should be engaged (sorted list)
        - available: Specialists that are installed (sorted list)
        - fallbacks: Mapping of unavailable specialists to fallback agents
        - routing: RoutingInfo per specialist (tier, reason, signals)
    """
    routing: Dict[str, RoutingInfo] = {}
    signals = list(signal_confidences.keys())

    # 1. Signal-based selection with tier assignment
    for signal, confidence in signal_confidences.items():
        specialists = SIGNAL_TO_SPECIALISTS.get(signal, set())
        tier = "REQUIRED" if confidence >= 0.3 else "RECOMMENDED"
        for spec in specialists:
            if spec not in routing:
                routing[spec] = RoutingInfo(tier=tier, reason=f"signal:{signal}", signals=[signal])
            else:
                # Upgrade tier if stronger signal found
                if tier == "REQUIRED" and routing[spec].tier != "REQUIRED":
                    routing[spec].tier = "REQUIRED"
                routing[spec].signals.append(signal)

    # 2. Complexity-based additions
    if complexity >= 5 and "wicked-delivery" not in routing:
        routing["wicked-delivery"] = RoutingInfo(
            tier="RECOMMENDED", reason=f"complexity:{complexity}>=5", signals=[])
    if complexity >= 3 and "wicked-qe" not in routing:
        routing["wicked-qe"] = RoutingInfo(
            tier="RECOMMENDED", reason=f"complexity:{complexity}>=3", signals=[])

    # 3. Ambiguity detection
    if ambiguous and "wicked-jam" not in routing:
        routing["wicked-jam"] = RoutingInfo(
            tier="RECOMMENDED", reason="ambiguity detected", signals=["ambiguity"])

    # 4. Always include QE for non-trivial work
    if (complexity >= 2 or len(signals) >= 2) and "wicked-qe" not in routing:
        routing["wicked-qe"] = RoutingInfo(
            tier="RECOMMENDED", reason="non-trivial work", signals=[])

    recommended = set(routing.keys())

    # 5. Filter to available
    available_recommended = recommended.intersection(available)
    unavailable = recommended - available

    # 6. Determine fallbacks with validation
    fallbacks = {}
    for spec in unavailable:
        fallback = SPECIALIST_FALLBACKS.get(spec)
        if fallback:
            if fallback not in VALID_FALLBACK_AGENTS:
                logger.error(f"Invalid fallback agent '{fallback}' for specialist '{spec}'")
                continue
            fallbacks[spec] = fallback

    return (
        sorted(list(recommended)),
        sorted(list(available_recommended)),
        fallbacks,
        routing,
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _apply_context(
    signal_confidences: Dict[str, float],
    complexity: int,
    context: Optional[ContextualVariables],
) -> Tuple[Dict[str, float], int]:
    """Apply contextual variable modifiers to signals and complexity."""
    if not context:
        return signal_confidences, complexity

    # Urgency affects complexity
    complexity = max(0, min(complexity + URGENCY_MODIFIERS.get(context.urgency, 0), 7))

    # Team size affects coordination
    if context.team_size > 5:
        complexity = min(complexity + 1, 7)

    # Customer type injects signals
    for signal in CUSTOMER_SIGNAL_INJECTION.get(context.customer_type, []):
        if signal not in signal_confidences:
            signal_confidences[signal] = 0.5  # Moderate confidence from context

    return signal_confidences, complexity


def _log_decision(analysis: 'SignalAnalysis', input_length: int) -> None:
    """Log decision to JSONL audit trail and build memory_payload for significant decisions.

    Every call writes to the JSONL file (fast, local audit trail).
    Significant decisions get a memory_payload attached to the SignalAnalysis
    for the CALLER (a Claude command) to store via /wicked-mem:store using
    Claude's native tool system — scripts never call other plugins directly.
    """
    try:
        log_dir = Path.home() / ".something-wicked" / "wicked-crew" / "decisions"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_length": input_length,
            "signals": analysis.signal_confidences,
            "risk_dimensions": {
                "impact": analysis.risk_dimensions.impact,
                "reversibility": analysis.risk_dimensions.reversibility,
                "novelty": analysis.risk_dimensions.novelty,
            },
            "complexity_score": analysis.complexity_score,
            "complexity_breakdown": analysis.complexity_breakdown,
            "specialists_selected": [
                {"name": name, "tier": info.tier, "reason": info.reason}
                for name, info in analysis.specialist_routing.items()
            ],
            "overrides_applied": analysis.overrides_applied,
            "confidence": analysis.confidence,
        }

        # Always write JSONL audit trail
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Build memory_payload for significant decisions (caller stores via tool system)
        is_significant = (
            analysis.complexity_score >= 4
            or len(analysis.signals) >= 3
            or analysis.overrides_applied
            or analysis.risk_dimensions.reversibility >= 2
        )

        if is_significant:
            reasoning_parts = []
            if analysis.signal_confidences:
                top_signals = sorted(analysis.signal_confidences.items(), key=lambda x: -x[1])[:3]
                reasoning_parts.append(
                    f"Signals: {', '.join(f'{s}={c:.0%}' for s, c in top_signals)}"
                )
            reasoning_parts.append(
                f"Complexity {analysis.complexity_score}/7 "
                f"(impact={analysis.complexity_breakdown.get('impact', 0)}, "
                f"risk={analysis.complexity_breakdown.get('risk_premium', 0)}, "
                f"scope={analysis.complexity_breakdown.get('scope', 0)}, "
                f"coord={analysis.complexity_breakdown.get('coordination', 0)})"
            )
            if analysis.risk_dimensions.explanation:
                reasoning_parts.append(
                    f"Risk: {'; '.join(analysis.risk_dimensions.explanation[:2])}"
                )
            if analysis.specialist_routing:
                required = [n for n, r in analysis.specialist_routing.items() if r.tier == "REQUIRED"]
                recommended = [n for n, r in analysis.specialist_routing.items() if r.tier == "RECOMMENDED"]
                if required:
                    reasoning_parts.append(f"Required: {', '.join(required)}")
                if recommended:
                    reasoning_parts.append(f"Recommended: {', '.join(recommended)}")
            if analysis.overrides_applied:
                reasoning_parts.append(f"Overrides: {analysis.overrides_applied}")

            analysis.memory_payload = {
                "title": f"Signal analysis: {len(analysis.signals)} signals, complexity {analysis.complexity_score}",
                "content": " | ".join(reasoning_parts),
                "type": "decision",
                "tags": "crew,smart-decisioning,signal-analysis",
                "importance": "medium" if analysis.complexity_score < 5 else "high",
            }

    except Exception:
        pass  # Best-effort logging, never block analysis


def analyze_input(
    text: str,
    plugin_dir: Optional[Path] = None,
    overrides: Optional[AnalysisOverrides] = None,
    context: Optional[ContextualVariables] = None,
    archetype_hints: Optional[Dict] = None,
) -> SignalAnalysis:
    """
    Main entry point: Analyze user input and return signal analysis.

    ORDERING: detect_signals runs BEFORE assess_novelty because novelty
    uses the signal count for cross-domain scoring.
    """
    logger.info(f"Analyzing input ({len(text)} chars)")

    effective_overrides = overrides or AnalysisOverrides()
    overrides_applied: Dict = {}

    # Signal detection with confidence scoring
    signal_confidences = detect_signals(text, threshold=effective_overrides.signal_threshold)

    # Apply skip/force overrides
    if effective_overrides.skip_signals:
        for sig in effective_overrides.skip_signals:
            signal_confidences.pop(sig, None)
        overrides_applied["skip_signals"] = effective_overrides.skip_signals

    if effective_overrides.force_signals:
        for sig in effective_overrides.force_signals:
            if sig not in signal_confidences:
                signal_confidences[sig] = 1.0  # Forced = max confidence
        overrides_applied["force_signals"] = effective_overrides.force_signals

    signals = list(signal_confidences.keys())
    ambiguous = is_ambiguous(text)
    available = get_available_specialists(plugin_dir)

    # Archetype detection - understand the TYPE of project/app
    #
    # TWO SOURCES (merged):
    # 1. External archetype_hints from command-layer dynamic analysis (preferred)
    #    - Commands use subagents, memories, AGENTS.md/CLAUDE.md, blast-radius, etc.
    #    - Can define NEW archetypes not in ARCHETYPE_ADJUSTMENTS
    #    - Format: {"archetype-name": {"confidence": 0.8, "impact_bonus": 2,
    #      "inject_signals": {"security": 0.3}, "min_complexity": 3,
    #      "description": "why this matters"}}
    # 2. Static keyword detection (fallback when no hints provided)
    #
    # HOLISTIC: Apply adjustments from ALL detected archetypes using maximum values.
    archetypes: Dict[str, float] = {}
    archetype_adj_applied: Dict = {}

    # Local copy of adjustments to avoid mutating the global dict
    effective_adjustments = dict(ARCHETYPE_ADJUSTMENTS)

    # Merge external hints (command-layer dynamic analysis)
    if archetype_hints:
        for arch_name, hint_data in archetype_hints.items():
            # Validate hint schema
            if not isinstance(hint_data, dict):
                logger.warning(f"Invalid hint for {arch_name}: not a dict, skipping")
                continue
            confidence = hint_data.get("confidence", 0.7)
            if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
                logger.warning(f"Invalid confidence for {arch_name}: {confidence}, clamping")
                confidence = max(0.0, min(float(confidence) if isinstance(confidence, (int, float)) else 0.7, 1.0))
            archetypes[arch_name] = confidence
            # Register custom adjustments in local copy (not global)
            if arch_name not in effective_adjustments:
                effective_adjustments[arch_name] = {
                    "impact_bonus": min(int(hint_data.get("impact_bonus", 1)), 3),
                    "inject_signals": hint_data.get("inject_signals", {}),
                    "min_complexity": min(int(hint_data.get("min_complexity", 2)), 7),
                    "description": hint_data.get("description", f"Dynamic: {arch_name}"),
                }
            archetype_adj_applied[f"hint:{arch_name}"] = confidence

    # Keyword-based detection (fallback, always runs to augment hints)
    keyword_archetypes = detect_archetype(text)
    for arch, conf in keyword_archetypes.items():
        if arch not in archetypes or conf > archetypes[arch]:
            archetypes[arch] = conf

    primary_archetype = max(archetypes, key=archetypes.get) if archetypes else None

    # Apply signal injections from ALL detected archetypes
    for arch in archetypes:
        adj = effective_adjustments.get(arch, {})
        for sig, conf in adj.get("inject_signals", {}).items():
            if sig not in signal_confidences:
                signal_confidences[sig] = conf
                archetype_adj_applied[f"injected_signal:{sig}"] = conf
    if archetypes:
        signals = list(signal_confidences.keys())  # Refresh after injection

    # Compute risk dimensions
    impact, impact_reasons = assess_impact(text)
    reversibility, rev_reasons = assess_reversibility(text)
    novelty, nov_reasons = assess_novelty(text, signals, ambiguous)

    # Apply MAXIMUM impact bonus from ALL detected archetypes
    # Core infrastructure/framework changes have broad impact even without file references
    if archetypes:
        max_bonus = 0
        max_bonus_arch = None
        for arch in archetypes:
            adj = effective_adjustments.get(arch, {})
            bonus = adj.get("impact_bonus", 0)
            if bonus > max_bonus:
                max_bonus = bonus
                max_bonus_arch = arch
        if max_bonus > 0 and max_bonus_arch:
            adj = effective_adjustments.get(max_bonus_arch, {})
            old_impact = impact
            impact = min(impact + max_bonus, 3)
            if impact > old_impact:
                impact_reasons.append(
                    f"archetype:{max_bonus_arch} +{max_bonus} "
                    f"({adj.get('description', 'type-specific adjustment')})"
                )
                archetype_adj_applied["impact_bonus"] = max_bonus
                archetype_adj_applied["impact_bonus_from"] = max_bonus_arch

    # Build explanation
    explanation = []
    if impact_reasons:
        explanation.append(f"Impact ({impact}/3): {'; '.join(impact_reasons)}")
    if rev_reasons:
        explanation.append(f"Reversibility ({reversibility}/3): {'; '.join(rev_reasons)}")
    if nov_reasons:
        explanation.append(f"Novelty ({novelty}/3): {'; '.join(nov_reasons)}")

    risk_dims = RiskDimensions(
        impact=impact,
        reversibility=reversibility,
        novelty=novelty,
        explanation=explanation,
    )

    # Composite score with editable breakdown
    complexity, breakdown = compute_composite(
        impact, reversibility, novelty, text,
        component_overrides=effective_overrides.component_overrides or None,
    )

    # Apply MAXIMUM minimum complexity floor from ALL detected archetypes
    if archetypes:
        max_min_complexity = 0
        for arch in archetypes:
            adj = effective_adjustments.get(arch, {})
            max_min_complexity = max(max_min_complexity, adj.get("min_complexity", 0))
        if complexity < max_min_complexity:
            archetype_adj_applied["min_complexity_applied"] = {
                "from": complexity, "to": max_min_complexity
            }
            complexity = max_min_complexity

    if effective_overrides.component_overrides:
        overrides_applied["component_overrides"] = effective_overrides.component_overrides

    # Apply complexity override
    if effective_overrides.complexity_override is not None:
        overrides_applied["complexity_override"] = effective_overrides.complexity_override
        complexity = max(0, min(effective_overrides.complexity_override, 7))

    # Apply contextual variables
    signal_confidences, complexity = _apply_context(signal_confidences, complexity, context)
    signals = list(signal_confidences.keys())  # Refresh after context injection

    # Dimension-driven flags
    flags: Dict[str, bool] = {}
    if risk_dims.reversibility >= 2:
        flags["needs_rollback_plan"] = True
    if effective_overrides.skip_injection:
        flags["skip_injection"] = True
        overrides_applied["skip_injection"] = True

    logger.debug(f"Signals detected: {signals} (confidences: {signal_confidences})")
    logger.debug(f"Risk dimensions: impact={impact}, reversibility={reversibility}, novelty={novelty}")
    logger.debug(f"Complexity score: {complexity}/7 (breakdown: {breakdown})")
    logger.debug(f"Ambiguous: {ambiguous}")

    recommended, available_specs, fallbacks, routing = select_specialists(
        signal_confidences, complexity, ambiguous, available
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

    if overrides_applied:
        logger.info(f"Overrides applied: {overrides_applied}")

    analysis = SignalAnalysis(
        signals=signals,
        signal_confidences=signal_confidences,
        complexity_score=complexity,
        complexity_breakdown=breakdown,
        risk_dimensions=risk_dims,
        recommended_specialists=recommended,
        available_specialists=available_specs,
        unavailable_specialists=unavailable,
        specialist_routing=routing,
        fallback_agents=fallbacks,
        is_ambiguous=ambiguous,
        confidence=confidence,
        archetypes=archetypes,
        primary_archetype=primary_archetype,
        archetype_adjustments_applied=archetype_adj_applied,
        flags=flags,
        overrides_applied=overrides_applied,
    )

    # Decision observability logging (best-effort)
    _log_decision(analysis, len(text))

    return analysis


def main():
    """CLI interface for smart decisioning."""
    import argparse

    parser = argparse.ArgumentParser(description="Smart decisioning for wicked-crew")
    parser.add_argument("text", nargs="?", help="Input text to analyze")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--plugin-dir", type=Path, help="Plugin directory to check")
    parser.add_argument("--signal-threshold", type=float, default=0.1,
                        help="Signal confidence threshold (default: 0.1)")
    parser.add_argument("--show-breakdown", action="store_true",
                        help="Show complexity breakdown table")
    parser.add_argument("--urgency", choices=["low", "medium", "high", "critical"],
                        default="medium", help="Urgency context")
    parser.add_argument("--team-size", type=int, default=1, help="Team size context")
    parser.add_argument("--customer-type", choices=["internal", "external", "enterprise"],
                        default="internal", help="Customer type context")
    parser.add_argument("--archetype-hints", type=str, default=None,
                        help="JSON dict of archetype hints from dynamic analysis. "
                             "Format: {\"archetype-name\": {\"confidence\": 0.8, "
                             "\"impact_bonus\": 2, \"inject_signals\": {}, "
                             "\"min_complexity\": 3, \"description\": \"why\"}}")

    args = parser.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    elif args.text is not None:
        text = args.text
    else:
        parser.error("Provide text or --stdin")

    overrides = AnalysisOverrides(signal_threshold=args.signal_threshold)
    context = ContextualVariables(
        urgency=args.urgency,
        team_size=args.team_size,
        customer_type=args.customer_type,
    )

    # Parse archetype hints from command layer
    hints = None
    if args.archetype_hints:
        try:
            hints = json.loads(args.archetype_hints)
        except json.JSONDecodeError:
            logger.warning(f"Invalid archetype hints JSON, ignoring: {args.archetype_hints}")

    analysis = analyze_input(text, args.plugin_dir, overrides=overrides, context=context,
                             archetype_hints=hints)

    if args.json:
        # Convert RoutingInfo objects to dicts for JSON serialization
        data = asdict(analysis)
        print(json.dumps(data, indent=2))
    else:
        print(f"Signals detected: {', '.join(analysis.signals) or 'none'}")
        if analysis.signal_confidences:
            for cat, conf in sorted(analysis.signal_confidences.items(), key=lambda x: -x[1]):
                print(f"  {cat}: {conf:.1%}")
        print(f"\nComplexity score: {analysis.complexity_score}/7")

        if args.show_breakdown or True:  # Always show breakdown now
            print(f"  Breakdown:")
            for comp, val in analysis.complexity_breakdown.items():
                print(f"    {comp}: {val}")

        print(f"Confidence: {analysis.confidence}")
        print(f"Ambiguous: {'yes' if analysis.is_ambiguous else 'no'}")
        print()
        dims = analysis.risk_dimensions
        print(f"Risk Dimensions:")
        print(f"  Impact:        {dims.impact}/3")
        print(f"  Reversibility: {dims.reversibility}/3")
        print(f"  Novelty:       {dims.novelty}/3")
        if dims.explanation:
            print(f"  Explanation:")
            for exp in dims.explanation:
                print(f"    - {exp}")
        if analysis.archetypes:
            print()
            print(f"Project Archetypes:")
            for arch, conf in sorted(analysis.archetypes.items(), key=lambda x: -x[1]):
                primary = " (primary)" if arch == analysis.primary_archetype else ""
                adj = ARCHETYPE_ADJUSTMENTS.get(arch, {})
                desc = adj.get("description", "")
                print(f"  {arch}: {conf:.1%}{primary}")
                if desc and arch == analysis.primary_archetype:
                    print(f"    {desc}")
            if analysis.archetype_adjustments_applied:
                print(f"  Adjustments applied: {analysis.archetype_adjustments_applied}")
        if analysis.flags:
            print()
            print(f"Flags:")
            for flag_name, flag_value in analysis.flags.items():
                print(f"  {flag_name}: {flag_value}")
        print()
        print(f"Specialist Routing:")
        for name in analysis.recommended_specialists:
            info = analysis.specialist_routing.get(name)
            avail = "installed" if name in analysis.available_specialists else "NOT INSTALLED"
            if info:
                print(f"  [{info.tier}] {name} ({avail}) — {info.reason}")
            else:
                print(f"  [?] {name} ({avail})")
        if analysis.fallback_agents:
            print(f"\nFallbacks: {analysis.fallback_agents}")
        if analysis.overrides_applied:
            print(f"\nOverrides: {analysis.overrides_applied}")


if __name__ == "__main__":
    main()
