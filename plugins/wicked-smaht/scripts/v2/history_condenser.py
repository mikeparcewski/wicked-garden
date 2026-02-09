#!/usr/bin/env python3
"""
wicked-smaht v2: History Condenser

Progressive compression of conversation history:
- Full history → Session summary (~500 tokens)
- + Turn window (last 3-5 turns)
- = 50-100x compression

Storage:
~/.something-wicked/wicked-smaht/sessions/{session_id}/
├── summary.json       # Session summary (persistent)
├── turns.jsonl        # Recent turns (rolling buffer)
└── condensed.md       # Last condensed output (cache)
"""

import json
import os
import re
import tempfile
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Turn:
    """A single conversation turn."""
    user: str
    assistant: str
    timestamp: str = ""
    tools_used: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class SessionSummary:
    """Compressed session summary."""
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format as markdown."""
        lines = []

        if self.topics:
            lines.append("**Topics**: " + ", ".join(self.topics[:5]))
        if self.decisions:
            lines.append("**Decisions**: " + "; ".join(self.decisions[:3]))
        if self.preferences:
            lines.append("**Preferences**: " + ", ".join(self.preferences[:3]))
        if self.open_threads:
            lines.append("**Open**: " + ", ".join(self.open_threads[:3]))

        return "\n".join(lines) if lines else "(No summary yet)"


class HistoryCondenser:
    """Manages condensed session history."""

    TURN_WINDOW_SIZE = 5
    MAX_TOPICS = 10
    MAX_DECISIONS = 5
    MAX_PREFERENCES = 5

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = Path.home() / ".something-wicked" / "wicked-smaht" / "sessions" / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.summary = self._load_summary()
        self.turn_buffer: deque[Turn] = deque(maxlen=self.TURN_WINDOW_SIZE)
        self._load_turns()

    def _load_summary(self) -> SessionSummary:
        """Load session summary from disk."""
        summary_path = self.session_dir / "summary.json"
        if summary_path.exists():
            try:
                data = json.loads(summary_path.read_text())
                return SessionSummary(**data)
            except Exception:
                pass
        return SessionSummary()

    def _load_turns(self):
        """Load recent turns from disk."""
        turns_path = self.session_dir / "turns.jsonl"
        if turns_path.exists():
            try:
                lines = turns_path.read_text().strip().split("\n")
                for line in lines[-self.TURN_WINDOW_SIZE:]:
                    if line:
                        data = json.loads(line)
                        self.turn_buffer.append(Turn(**data))
            except Exception:
                pass

    def _atomic_write(self, path: Path, content: str):
        """Write file atomically using temp file + rename."""
        # Write to temp file in same directory, then rename
        fd, tmp_path = tempfile.mkstemp(dir=self.session_dir, suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, path)
        except Exception:
            os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def save(self):
        """Save summary and turns to disk (atomic writes for thread safety)."""
        # Save summary
        summary_path = self.session_dir / "summary.json"
        summary_content = json.dumps({
            "topics": self.summary.topics,
            "decisions": self.summary.decisions,
            "preferences": self.summary.preferences,
            "open_threads": self.summary.open_threads,
        }, indent=2)
        self._atomic_write(summary_path, summary_content)

        # Save turns
        turns_path = self.session_dir / "turns.jsonl"
        lines = []
        for turn in self.turn_buffer:
            lines.append(json.dumps({
                "user": turn.user,
                "assistant": turn.assistant,
                "timestamp": turn.timestamp,
                "tools_used": turn.tools_used,
            }))
        self._atomic_write(turns_path, "\n".join(lines))

    def add_turn(self, user_msg: str, assistant_msg: str, tools_used: list[str] = None):
        """Add a turn and update summary."""
        turn = Turn(
            user=user_msg,
            assistant=assistant_msg,
            tools_used=tools_used or [],
        )
        self.turn_buffer.append(turn)
        self._update_summary(turn)
        self.save()

    def _update_summary(self, turn: Turn):
        """Update session summary with new turn."""
        # Extract topics from user message
        topics = self._extract_topics(turn.user)
        for topic in topics:
            if topic not in self.summary.topics:
                self.summary.topics.append(topic)
                if len(self.summary.topics) > self.MAX_TOPICS:
                    self.summary.topics.pop(0)

        # Extract decisions
        decisions = self._extract_decisions(turn)
        for decision in decisions:
            if decision not in self.summary.decisions:
                self.summary.decisions.append(decision)
                if len(self.summary.decisions) > self.MAX_DECISIONS:
                    self.summary.decisions.pop(0)

        # Extract preferences
        preferences = self._extract_preferences(turn.user)
        for pref in preferences:
            if pref not in self.summary.preferences:
                self.summary.preferences.append(pref)
                if len(self.summary.preferences) > self.MAX_PREFERENCES:
                    self.summary.preferences.pop(0)

    def _extract_topics(self, text: str) -> list[str]:
        """Extract topics from text."""
        topics = []

        # File/module mentions
        files = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*\.(py|ts|js|md))", text)
        for f in files:
            if isinstance(f, tuple):
                f = f[0]
            topics.append(f)

        # Concept keywords
        concepts = [
            "caching", "auth", "authentication", "database", "api",
            "testing", "debugging", "refactoring", "performance",
            "security", "deployment", "logging", "monitoring",
        ]
        text_lower = text.lower()
        for concept in concepts:
            if concept in text_lower and concept not in topics:
                topics.append(concept)

        return topics[:5]

    def _extract_decisions(self, turn: Turn) -> list[str]:
        """Extract decisions from turn."""
        decisions = []
        combined = turn.user + " " + turn.assistant
        combined_lower = combined.lower()

        # Decision patterns
        patterns = [
            r"let's (go with|use|do) ([^.!?]+)",
            r"decided on ([^.!?]+)",
            r"chose ([^.!?]+)",
            r"we'll use ([^.!?]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, combined_lower)
            for match in matches:
                if isinstance(match, tuple):
                    match = " ".join(match)
                if len(match) > 10 and len(match) < 100:
                    decisions.append(match.strip())

        return decisions[:2]

    def _extract_preferences(self, text: str) -> list[str]:
        """Extract user preferences from text."""
        preferences = []
        text_lower = text.lower()

        patterns = [
            r"i (prefer|like|want) ([^.!?]+)",
            r"keep it (simple|clean|minimal)",
            r"don't want ([^.!?]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if isinstance(match, tuple):
                    match = " ".join(match)
                if len(match) > 5 and len(match) < 50:
                    preferences.append(match.strip())

        return preferences[:2]

    def get_condensed_history(self) -> str:
        """Get condensed history for subagent input."""
        lines = ["## Session Context", ""]

        # Summary section
        lines.append("### Summary")
        lines.append(self.summary.to_markdown())
        lines.append("")

        # Recent turns
        if self.turn_buffer:
            lines.append("### Recent Turns")
            for i, turn in enumerate(self.turn_buffer):
                turn_num = i + 1
                condensed = self._condense_turn(turn)
                lines.append(f"**Turn {turn_num}**: {condensed}")
            lines.append("")

        return "\n".join(lines)

    def _condense_turn(self, turn: Turn) -> str:
        """Condense a single turn."""
        # User: keep more detail (first 100 chars)
        user_summary = turn.user[:100]
        if len(turn.user) > 100:
            user_summary += "..."

        # Assistant: heavily compress
        assistant_summary = self._summarize_assistant(turn.assistant)

        return f"User: {user_summary} → {assistant_summary}"

    def _summarize_assistant(self, msg: str) -> str:
        """Heavily compress assistant message."""
        msg_lower = msg.lower()

        if "```" in msg:
            return "Provided code"
        if "?" in msg and len(msg) < 200:
            return "Asked clarifying question"
        if "created" in msg_lower or "wrote" in msg_lower:
            return "Created/wrote content"
        if "fixed" in msg_lower or "resolved" in msg_lower:
            return "Fixed issue"
        if "found" in msg_lower or "searched" in msg_lower:
            return "Found/searched"

        # Default: first 50 chars
        summary = msg[:50].replace("\n", " ")
        if len(msg) > 50:
            summary += "..."
        return summary

    def get_last_turn(self) -> Optional[Turn]:
        """Get the last turn."""
        if self.turn_buffer:
            return self.turn_buffer[-1]
        return None

    def get_session_state(self) -> dict:
        """Get session state for router."""
        return {
            "session_id": self.session_id,
            "turn_count": len(self.turn_buffer),
            "topics": self.summary.topics,
            "has_decisions": len(self.summary.decisions) > 0,
            "has_open_threads": len(self.summary.open_threads) > 0,
        }


def main():
    """CLI for testing history condenser."""
    import sys

    session_id = sys.argv[1] if len(sys.argv) > 1 else "test-session"
    condenser = HistoryCondenser(session_id)

    if len(sys.argv) > 2:
        # Add a test turn
        condenser.add_turn(
            user_msg=sys.argv[2],
            assistant_msg="Test assistant response",
        )

    print(condenser.get_condensed_history())


if __name__ == "__main__":
    main()
