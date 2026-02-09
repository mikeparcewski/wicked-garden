#!/usr/bin/env python3
"""
wicked-smaht v2: Router

Decides whether to use fast path (pattern-based) or slow path (subagent).

Fast path criteria (ALL must be true):
- Short prompt (< 100 words)
- High confidence intent (> 0.7)
- Simple context needs (< 5 entities)
- Not novel topic

Slow path triggers (ANY triggers escalation):
- Low confidence (< 0.5)
- Competing intents
- High entity count (> 5)
- Requires history
- Planning/design request
- Novel topic
- Long prompt (> 200 words)
- Compound request
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    GENERAL = "general"
    DEBUGGING = "debugging"
    PLANNING = "planning"
    RESEARCH = "research"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"


class PathDecision(str, Enum):
    FAST = "fast"
    SLOW = "slow"


# Intent detection patterns
INTENT_PATTERNS = {
    IntentType.DEBUGGING: [
        r"\b(error|bug|fix|crash|exception|traceback|failing|broken|issue)\b",
        r"\b(debug|diagnose|investigate|troubleshoot)\b",
        r"(doesn't work|not working|fails?|failed)\b",
    ],
    IntentType.PLANNING: [
        r"\b(plan|design|architect|strategy|approach)\b",
        r"(should we|how should|let's think about|brainstorm)\b",
        r"\b(roadmap|milestone|phase|sprint)\b",
    ],
    IntentType.RESEARCH: [
        r"\b(what (is|does|are)|how (does|do|is)|explain|where|find|search|list)\b",
        r"\b(documentation|docs|reference|guide)\b",
        r"(tell me about|show me|describe|defined|available)\b",
        r"^(what|where|how|which|why|who)\b",  # Questions starting with W-words
    ],
    IntentType.IMPLEMENTATION: [
        r"\b(build|implement|create|add|write|make|code)\b",
        r"\b(feature|function|component|module)\b",
        r"(let's (add|build|create|write))\b",
    ],
    IntentType.REVIEW: [
        r"\b(review|check|verify|validate|approve)\b",
        r"\b(PR|pull request|merge|diff)\b",
        r"(look at|examine|inspect)\b",
    ],
}

# Entity extraction patterns
ENTITY_PATTERNS = {
    "files": r"([a-zA-Z_][a-zA-Z0-9_]*\.(py|ts|js|tsx|jsx|md|json|yaml|yml|sh|sql))\b",
    "symbols": r"\b([A-Z][a-zA-Z0-9]+(?:Service|Manager|Handler|Controller|Provider))\b",
    "paths": r"((?:src|plugins?|scripts?|tests?)/[^\s]+)",
}

# History reference patterns
HISTORY_PATTERNS = [
    r"(like we (discussed|talked about|mentioned))",
    r"(earlier|before|previously)",
    r"(as I said|as mentioned)",
    r"(the thing|that feature|that bug)",
]

# Compound request patterns
COMPOUND_PATTERNS = [
    r"\b(and also|and then|plus|as well as)\b",
    r"(first .+ then .+)",
    r"(\d+\.\s+.+\n\s*\d+\.)",  # Numbered list
]


@dataclass
class PromptAnalysis:
    """Analysis of a user prompt."""
    prompt: str
    word_count: int
    intent_type: IntentType
    confidence: float
    competing_intents: int
    entities: list[str] = field(default_factory=list)
    entity_count: int = 0
    requires_history: bool = False
    is_planning: bool = False
    is_novel: bool = False
    is_compound: bool = False


@dataclass
class RouterDecision:
    """Router's decision with reasoning."""
    path: PathDecision
    analysis: PromptAnalysis
    reason: str


class Router:
    """Decides fast vs slow path for context assembly."""

    def __init__(self, session_topics: list[str] = None):
        """
        Args:
            session_topics: Topics seen in this session (for novelty detection)
        """
        self.session_topics = set(session_topics or [])
        self.fast_path_cache: dict[str, bool] = {}

    def route(self, prompt: str) -> RouterDecision:
        """Route a prompt to fast or slow path."""
        analysis = self.analyze(prompt)

        # Check escalation triggers (slow path)
        if self._should_escalate(analysis):
            reason = self._get_escalation_reason(analysis)
            return RouterDecision(PathDecision.SLOW, analysis, reason)

        # Check fast path eligibility
        if self._use_fast_path(analysis):
            return RouterDecision(PathDecision.FAST, analysis, "High confidence, simple request")

        # Default to slow when uncertain
        return RouterDecision(PathDecision.SLOW, analysis, "Uncertain - defaulting to slow path")

    def analyze(self, prompt: str) -> PromptAnalysis:
        """Analyze a prompt for routing decision."""
        prompt_lower = prompt.lower()
        words = prompt.split()

        # Detect intent and confidence
        intent_type, confidence, competing = self._detect_intent(prompt_lower)

        # Extract entities
        entities = self._extract_entities(prompt)

        # Check various flags
        requires_history = self._references_history(prompt_lower)
        is_planning = intent_type == IntentType.PLANNING or self._is_planning_request(prompt_lower)
        is_novel = self._is_novel_topic(entities)
        is_compound = self._is_compound_request(prompt_lower)

        return PromptAnalysis(
            prompt=prompt,
            word_count=len(words),
            intent_type=intent_type,
            confidence=confidence,
            competing_intents=competing,
            entities=entities,
            entity_count=len(entities),
            requires_history=requires_history,
            is_planning=is_planning,
            is_novel=is_novel,
            is_compound=is_compound,
        )

    def _detect_intent(self, prompt_lower: str) -> tuple[IntentType, float, int]:
        """Detect intent type, confidence, and count of competing intents."""
        scores: dict[IntentType, float] = {}

        for intent_type, patterns in INTENT_PATTERNS.items():
            score = 0.0
            for pattern in patterns:
                matches = re.findall(pattern, prompt_lower, re.IGNORECASE)
                if matches:
                    score += 0.3 * len(matches)
            scores[intent_type] = min(score, 1.0)

        # Find best and count competing
        if not scores or all(s == 0 for s in scores.values()):
            return IntentType.GENERAL, 0.3, 0

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_type, best_score = sorted_scores[0]

        # Count intents with score > 0.5 * best (competing)
        competing = sum(1 for _, s in sorted_scores if s > best_score * 0.5 and s > 0.2) - 1

        # Calculate confidence
        if best_score < 0.3:
            return IntentType.GENERAL, 0.3, competing

        confidence = min(0.3 + best_score * 0.7, 1.0)
        return best_type, confidence, max(0, competing)

    def _extract_entities(self, prompt: str) -> list[str]:
        """Extract entities (files, symbols, paths) from prompt."""
        entities = []
        for pattern in ENTITY_PATTERNS.values():
            matches = re.findall(pattern, prompt)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match and match not in entities:
                    entities.append(match)
        return entities

    def _references_history(self, prompt_lower: str) -> bool:
        """Check if prompt references conversation history."""
        for pattern in HISTORY_PATTERNS:
            if re.search(pattern, prompt_lower):
                return True
        return False

    def _is_planning_request(self, prompt_lower: str) -> bool:
        """Check for planning/design indicators beyond intent patterns."""
        planning_words = ["trade-off", "tradeoff", "options", "alternatives", "pros and cons"]
        return any(w in prompt_lower for w in planning_words)

    def _is_novel_topic(self, entities: list[str]) -> bool:
        """Check if entities are novel (not seen in session).

        Note: Prompts without detectable entities cannot be flagged as novel,
        which is acceptable since the fast path is appropriate for general queries.
        Novel detection primarily guards against sudden topic shifts with explicit
        file/symbol references.
        """
        if not entities:
            return False
        # Novel if majority of entities are new
        new_count = sum(1 for e in entities if e not in self.session_topics)
        return new_count > len(entities) / 2

    def _is_compound_request(self, prompt_lower: str) -> bool:
        """Check for compound/multi-part requests."""
        for pattern in COMPOUND_PATTERNS:
            if re.search(pattern, prompt_lower):
                return True
        return False

    def _should_escalate(self, analysis: PromptAnalysis) -> bool:
        """Check if any escalation trigger fires."""
        return (
            analysis.confidence < 0.5 or
            analysis.competing_intents >= 1 or  # Escalate if ANY competing intent
            analysis.entity_count > 5 or
            analysis.requires_history or
            analysis.is_planning or
            analysis.is_novel or
            analysis.word_count > 200 or
            analysis.is_compound
        )

    def _use_fast_path(self, analysis: PromptAnalysis) -> bool:
        """Check if fast path is appropriate."""
        return (
            analysis.word_count < 100 and
            analysis.confidence > 0.7 and
            analysis.entity_count <= 5 and
            not analysis.is_novel
        )

    def _get_escalation_reason(self, analysis: PromptAnalysis) -> str:
        """Get human-readable reason for escalation."""
        reasons = []
        if analysis.confidence < 0.5:
            reasons.append(f"low confidence ({analysis.confidence:.2f})")
        if analysis.competing_intents >= 1:
            reasons.append(f"{analysis.competing_intents} competing intent(s)")
        if analysis.entity_count > 5:
            reasons.append(f"many entities ({analysis.entity_count})")
        if analysis.requires_history:
            reasons.append("references history")
        if analysis.is_planning:
            reasons.append("planning/design request")
        if analysis.is_novel:
            reasons.append("novel topic")
        if analysis.word_count > 200:
            reasons.append(f"long prompt ({analysis.word_count} words)")
        if analysis.is_compound:
            reasons.append("compound request")

        return "; ".join(reasons) if reasons else "uncertain"

    def update_session_topics(self, entities: list[str]):
        """Add entities to session topics for novelty tracking."""
        self.session_topics.update(entities)


def main():
    """CLI for testing router."""
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: router.py <prompt>")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    router = Router()
    decision = router.route(prompt)

    print(json.dumps({
        "path": decision.path.value,
        "reason": decision.reason,
        "analysis": {
            "intent": decision.analysis.intent_type.value,
            "confidence": decision.analysis.confidence,
            "word_count": decision.analysis.word_count,
            "entity_count": decision.analysis.entity_count,
            "entities": decision.analysis.entities,
            "requires_history": decision.analysis.requires_history,
            "is_planning": decision.analysis.is_planning,
            "is_novel": decision.analysis.is_novel,
            "is_compound": decision.analysis.is_compound,
        }
    }, indent=2))


if __name__ == "__main__":
    main()
