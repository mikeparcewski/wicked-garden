#!/usr/bin/env python3
"""
wicked-smaht v2: Structured Fact Extraction

Extracts typed facts from conversation turns and stores them in facts.jsonl.
Each fact has a UUID, entity references, and a structured type.

Fact types:
  - decision: Choices made ("let's use X", "decided on Y")
  - discovery: Information learned ("found that X", "turns out Y")
  - artifact: Files/outputs created ("created X", "wrote Y")
  - problem_solved: Issues resolved ("fixed X", "resolved Y")
  - context: Background information ("the system uses X", "currently Y")

Storage:
~/.something-wicked/wicked-smaht/sessions/{session_id}/facts.jsonl
"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


FACT_TYPES = ("decision", "discovery", "artifact", "problem_solved", "context")


@dataclass
class Fact:
    """A structured fact extracted from conversation."""
    id: str
    type: str
    content: str
    entities: list[str] = field(default_factory=list)
    source: str = "user"  # "user" or "assistant"
    timestamp: str = ""
    turn_index: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


# --- Extraction patterns ---

_DECISION_PATTERNS = [
    (r"let's (?:go with|use|do) ([^.!?\n]{10,100})", "decision"),
    (r"decided (?:on|to) ([^.!?\n]{10,100})", "decision"),
    (r"chose ([^.!?\n]{10,100})", "decision"),
    (r"we(?:'ll| will) use ([^.!?\n]{10,100})", "decision"),
    (r"going (?:to|with) ([^.!?\n]{10,100})", "decision"),
    (r"switched to ([^.!?\n]{10,100})", "decision"),
]

_DISCOVERY_PATTERNS = [
    (r"(?:found|discovered) (?:that |out )([^.!?\n]{10,100})", "discovery"),
    (r"turns out ([^.!?\n]{10,100})", "discovery"),
    (r"(?:realized|noticed) (?:that )?([^.!?\n]{10,100})", "discovery"),
    (r"the (?:issue|problem|root cause) (?:is|was) ([^.!?\n]{10,100})", "discovery"),
]

_ARTIFACT_PATTERNS = [
    (r"(?:created|wrote|generated|built) ([^.!?\n]{5,80})", "artifact"),
    (r"(?:added|implemented) ([^.!?\n]{5,80})", "artifact"),
]

_PROBLEM_SOLVED_PATTERNS = [
    (r"(?:fixed|resolved|solved) ([^.!?\n]{10,100})", "problem_solved"),
    (r"(?:the fix|solution) (?:is|was) ([^.!?\n]{10,100})", "problem_solved"),
]

_CONTEXT_PATTERNS = [
    (r"the system (?:uses|has|runs) ([^.!?\n]{10,80})", "context"),
    (r"currently (?:using|running|on) ([^.!?\n]{10,80})", "context"),
    (r"our (?:stack|setup|architecture) (?:is|includes) ([^.!?\n]{10,80})", "context"),
]

ALL_PATTERNS = (
    _DECISION_PATTERNS
    + _DISCOVERY_PATTERNS
    + _ARTIFACT_PATTERNS
    + _PROBLEM_SOLVED_PATTERNS
    + _CONTEXT_PATTERNS
)


def _extract_entities(text: str) -> list[str]:
    """Extract entity references (files, technologies, services) from text."""
    entities = []

    # File paths/names
    files = re.findall(
        r'([a-zA-Z_][a-zA-Z0-9_/.-]*\.'
        r'(?:py|ts|js|tsx|jsx|json|yaml|yml|md|sql|java|go|rs|sh))\b',
        text
    )
    entities.extend(files[:5])

    # Technology names (capitalized or known)
    tech_names = [
        "Redis", "Postgres", "PostgreSQL", "MySQL", "MongoDB", "SQLite",
        "Docker", "Kubernetes", "AWS", "GCP", "Azure",
        "React", "Vue", "Angular", "FastAPI", "Django", "Flask", "Express",
        "JWT", "OAuth", "GraphQL", "REST", "gRPC",
        "Stripe", "Kafka", "RabbitMQ", "Elasticsearch",
    ]
    text_lower = text.lower()
    for tech in tech_names:
        if tech.lower() in text_lower and tech not in entities:
            entities.append(tech)

    return entities[:8]


class FactExtractor:
    """Extracts and stores structured facts from conversation turns."""

    MAX_FACTS = 100  # Per session

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.facts_path = session_dir / "facts.jsonl"
        self.facts: list[Fact] = self._load_facts()

    def _load_facts(self) -> list[Fact]:
        """Load facts from disk."""
        facts = []
        if self.facts_path.exists():
            try:
                for line in self.facts_path.read_text().strip().split("\n"):
                    if line:
                        data = json.loads(line)
                        facts.append(Fact(**data))
            except Exception:
                pass
        return facts

    def save(self):
        """Save facts to disk."""
        lines = [json.dumps(f.to_dict()) for f in self.facts[-self.MAX_FACTS:]]
        self.facts_path.write_text("\n".join(lines) + "\n" if lines else "")

    def extract_from_turn(self, user_msg: str, assistant_msg: str, turn_index: int = 0) -> list[Fact]:
        """Extract facts from a conversation turn."""
        new_facts = []

        # Extract from user message
        user_facts = self._extract_from_text(user_msg, "user", turn_index)
        new_facts.extend(user_facts)

        # Extract from assistant message
        assistant_facts = self._extract_from_text(assistant_msg, "assistant", turn_index)
        new_facts.extend(assistant_facts)

        # Deduplicate against existing facts
        existing_contents = {f.content.lower() for f in self.facts}
        unique_facts = []
        for fact in new_facts:
            if fact.content.lower() not in existing_contents:
                existing_contents.add(fact.content.lower())
                unique_facts.append(fact)

        self.facts.extend(unique_facts)

        # Trim to max
        if len(self.facts) > self.MAX_FACTS:
            self.facts = self.facts[-self.MAX_FACTS:]

        if unique_facts:
            self.save()

        return unique_facts

    def _extract_from_text(self, text: str, source: str, turn_index: int) -> list[Fact]:
        """Extract facts from a text block."""
        facts = []
        text_lower = text.lower()

        for pattern, fact_type in ALL_PATTERNS:
            matches = re.findall(pattern, text_lower)
            for match in matches[:2]:
                if isinstance(match, tuple):
                    match = " ".join(match)
                match = match.strip()
                if not match or len(match) < 5:
                    continue

                entities = _extract_entities(text)
                fact = Fact(
                    id=str(uuid.uuid4())[:8],
                    type=fact_type,
                    content=match,
                    entities=entities,
                    source=source,
                    turn_index=turn_index,
                )
                facts.append(fact)

        return facts[:5]  # Max 5 facts per text block

    def get_facts_by_type(self, fact_type: str) -> list[Fact]:
        """Get facts filtered by type."""
        return [f for f in self.facts if f.type == fact_type]

    def get_recent_facts(self, n: int = 10) -> list[Fact]:
        """Get the N most recent facts."""
        return self.facts[-n:]

    def get_promotable_facts(self) -> list[Fact]:
        """Get facts suitable for promotion to wicked-mem.

        Criteria: decisions and discoveries are the most valuable for
        cross-session persistence. Artifacts and problems solved are
        session-specific.
        """
        promotable_types = {"decision", "discovery"}
        return [f for f in self.facts if f.type in promotable_types]

    def to_summary(self) -> dict:
        """Generate a summary of extracted facts."""
        by_type = {}
        for fact in self.facts:
            by_type.setdefault(fact.type, []).append(fact.content)
        return {
            "total_facts": len(self.facts),
            "by_type": {t: len(fs) for t, fs in by_type.items()},
            "recent": [f.to_dict() for f in self.facts[-5:]],
        }
