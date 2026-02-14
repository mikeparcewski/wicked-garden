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
    """Compressed session summary — the "ticket rail" for the session.

    Beyond topics/decisions/preferences, tracks working state:
    current task, active constraints, file scope, and open questions.
    This is the L2 cache between the rolling turn buffer (L1) and
    long-term memory in wicked-mem (L3).
    """
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)
    # Working state fields (the "ticket rail")
    current_task: str = ""
    active_constraints: list[str] = field(default_factory=list)
    file_scope: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format as markdown."""
        lines = []

        if self.current_task:
            lines.append(f"**Current task**: {self.current_task}")
        if self.topics:
            lines.append("**Topics**: " + ", ".join(self.topics[:5]))
        if self.decisions:
            lines.append("**Decisions**: " + "; ".join(self.decisions[:3]))
        if self.active_constraints:
            lines.append("**Constraints**: " + "; ".join(self.active_constraints[:3]))
        if self.file_scope:
            lines.append("**Files**: " + ", ".join(self.file_scope[:8]))
        if self.preferences:
            lines.append("**Preferences**: " + ", ".join(self.preferences[:3]))
        if self.open_questions:
            lines.append("**Open questions**: " + "; ".join(self.open_questions[:3]))
        if self.open_threads:
            lines.append("**Open threads**: " + ", ".join(self.open_threads[:3]))

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
                # Filter to known fields only (schema drift safety)
                known = {f.name for f in SessionSummary.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in known}
                return SessionSummary(**filtered)
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
        fd, tmp_path = tempfile.mkstemp(dir=self.session_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except Exception:
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
            "current_task": self.summary.current_task,
            "active_constraints": self.summary.active_constraints,
            "file_scope": self.summary.file_scope,
            "open_questions": self.summary.open_questions,
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

        # Extract working state: files touched, constraints, questions
        self._update_file_scope(turn)
        self._update_constraints(turn)
        self._update_current_task(turn)
        self._update_open_questions(turn)

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

    def _update_file_scope(self, turn: Turn):
        """Track files mentioned or modified in this turn."""
        combined = turn.user + " " + turn.assistant
        # Match file paths and filenames
        files = re.findall(
            r'(?:^|[\s"\'`(])([a-zA-Z_][a-zA-Z0-9_/.-]*\.'
            r'(?:py|ts|js|tsx|jsx|md|json|yaml|yml|sh|sql|java|go|rs))\b',
            combined
        )
        # Also pick up paths from tool use (Read, Edit, Write patterns)
        paths = re.findall(r'file_path["\s:]+([^\s"]+)', combined)
        all_files = list(dict.fromkeys(files + paths))  # dedupe, preserve order
        for f in all_files:
            if f not in self.summary.file_scope:
                self.summary.file_scope.append(f)
        # Keep bounded — most recent files matter most
        if len(self.summary.file_scope) > 20:
            self.summary.file_scope = self.summary.file_scope[-20:]

    def _update_constraints(self, turn: Turn):
        """Extract constraints from conversation."""
        combined = (turn.user + " " + turn.assistant).lower()
        patterns = [
            r"(?:must|should|need to|has to|require[sd]?) ([^.!?]{10,80})",
            r"(?:don't|do not|never|avoid) ([^.!?]{10,80})",
            r"(?:constraint|requirement|rule):\s*([^.!?]{10,80})",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, combined)
            for match in matches[:2]:
                match = match.strip()
                if match and match not in self.summary.active_constraints:
                    self.summary.active_constraints.append(match)
        if len(self.summary.active_constraints) > 10:
            self.summary.active_constraints = self.summary.active_constraints[-10:]

    def _update_current_task(self, turn: Turn):
        """Track what the user is currently working on."""
        user_lower = turn.user.lower()
        # Explicit task statements
        patterns = [
            r"(?:i(?:'m| am) (?:working on|trying to|building|fixing|implementing)) ([^.!?]{10,100})",
            r"(?:let's|help me) ([^.!?]{10,100})",
            r"(?:task|goal|objective):\s*([^.!?]{10,100})",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, user_lower)
            if matches:
                self.summary.current_task = matches[0].strip()
                return
        # Also detect from crew task subjects
        if "TaskCreate" in turn.assistant or "TaskUpdate" in turn.assistant:
            task_match = re.search(r'subject["\s:]+([^"]+)', turn.assistant)
            if task_match:
                self.summary.current_task = task_match.group(1).strip()

    def _update_open_questions(self, turn: Turn):
        """Track recent questions from assistant. Keeps last 3 on substantive user response."""
        # Questions from the assistant that need user input
        questions = re.findall(r'([^.!]*\?)', turn.assistant)
        for q in questions[-2:]:
            q = q.strip()
            if len(q) > 15 and len(q) < 150:
                self.summary.open_questions.append(q)
        # Clear questions that were likely answered by user input
        if turn.user and self.summary.open_questions:
            # If user gave a substantive response, clear oldest question
            if len(turn.user) > 10:
                self.summary.open_questions = self.summary.open_questions[-3:]

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
        """Get full session state — the 'ticket rail' for context assembly."""
        return {
            "session_id": self.session_id,
            "turn_count": len(self.turn_buffer),
            "topics": self.summary.topics,
            "decisions": self.summary.decisions,
            "current_task": self.summary.current_task,
            "active_constraints": self.summary.active_constraints,
            "file_scope": self.summary.file_scope,
            "open_questions": self.summary.open_questions,
            "has_decisions": len(self.summary.decisions) > 0,
            "has_open_threads": len(self.summary.open_threads) > 0,
        }

    def persist_session_meta(self):
        """Persist session metadata for cross-session recall.

        Called on session end (Stop hook) to save a condensed session
        summary that future sessions can recall for continuity.
        """
        meta_path = self.session_dir / "session_meta.json"
        turn_count = len(self.turn_buffer)

        # Only persist if there was meaningful activity
        if turn_count == 0 and not self.summary.topics:
            return

        meta = {
            "session_id": self.session_id,
            "start_time": self.turn_buffer[0].timestamp if self.turn_buffer else datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "turn_count": turn_count,
            "key_topics": self.summary.topics[:5],
            "decisions_made": self.summary.decisions[:3],
            "current_task": self.summary.current_task,
            "files_touched": self.summary.file_scope[:10],
        }
        self._atomic_write(meta_path, json.dumps(meta, indent=2))

    @staticmethod
    def load_recent_sessions(max_sessions: int = 3) -> list[dict]:
        """Load condensed summaries from recent past sessions.

        Returns session metadata sorted by recency (newest first).
        Used by SessionStart hook for cross-session continuity.
        """
        sessions_dir = Path.home() / ".something-wicked" / "wicked-smaht" / "sessions"
        if not sessions_dir.exists():
            return []

        session_metas = []
        for session_path in sessions_dir.iterdir():
            if not session_path.is_dir():
                continue
            meta_path = session_path / "session_meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
                # Add mtime for sorting
                meta["_mtime"] = meta_path.stat().st_mtime
                session_metas.append(meta)
            except Exception:
                continue

        # Sort by modification time, newest first
        session_metas.sort(key=lambda x: x.get("_mtime", 0), reverse=True)

        # Remove internal sort key and return
        for meta in session_metas:
            meta.pop("_mtime", None)

        return session_metas[:max_sessions]


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
