#!/usr/bin/env python3
"""
wicked-smaht v2: Context Pressure Tracker

Tracks cumulative content size flowing through the conversation to detect
when the context window is approaching capacity. Uses content bytes as the
metric instead of turn count — a 4-turn scenario test with 100KB evidence
is far more pressure than a 50-turn chat with short messages.

Storage: /tmp/wicked-smaht-pressure-{session_id} (volatile, per-session)

Pressure levels:
  LOW:      0 - 200KB   (normal operation)
  MEDIUM:   200 - 400KB (advise compaction)
  HIGH:     400 - 600KB (strongly recommend compaction, rich recovery briefing)
  CRITICAL: 600KB+      (insist on compaction before proceeding)

These thresholds assume ~800KB total context window with ~200KB reserved
for system prompt, CLAUDE.md, tools, and safety margin.
"""

import json
import os
import tempfile
from enum import Enum
from pathlib import Path


class PressureLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Thresholds in bytes
PRESSURE_THRESHOLDS = {
    PressureLevel.LOW: 0,
    PressureLevel.MEDIUM: 200 * 1024,      # 200KB
    PressureLevel.HIGH: 400 * 1024,         # 400KB
    PressureLevel.CRITICAL: 600 * 1024,     # 600KB
}


class PressureTracker:
    """Track cumulative content size for a session."""

    def __init__(self, session_id: str = ""):
        if not session_id:
            session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        if not session_id:
            session_id = f"pid-{os.getppid()}"
        self._path = Path(tempfile.gettempdir()) / f"wicked-smaht-pressure-{session_id}"

    def _read_state(self) -> dict:
        """Read pressure state from disk."""
        try:
            data = json.loads(self._path.read_text())
            return {
                "cumulative_bytes": data.get("cumulative_bytes", 0),
                "turn_count": data.get("turn_count", 0),
                "last_compacted": data.get("last_compacted", False),
                "peak_bytes": data.get("peak_bytes", 0),
            }
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {
                "cumulative_bytes": 0,
                "turn_count": 0,
                "last_compacted": False,
                "peak_bytes": 0,
            }

    def _write_state(self, state: dict):
        """Write pressure state to disk atomically."""
        tmp = str(self._path) + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def add_content(self, byte_count: int):
        """Add content bytes to cumulative pressure."""
        state = self._read_state()
        state["cumulative_bytes"] += byte_count
        if state["cumulative_bytes"] > state["peak_bytes"]:
            state["peak_bytes"] = state["cumulative_bytes"]
        self._write_state(state)

    def increment_turn(self, prompt_bytes: int = 0, briefing_bytes: int = 0):
        """Record a new turn with its content contribution."""
        state = self._read_state()
        state["turn_count"] += 1
        state["cumulative_bytes"] += prompt_bytes + briefing_bytes
        state["last_compacted"] = False  # clear compaction flag on new turn
        if state["cumulative_bytes"] > state["peak_bytes"]:
            state["peak_bytes"] = state["cumulative_bytes"]
        self._write_state(state)

    def mark_compacted(self):
        """Mark that compaction just occurred. Next prompt_submit detects this."""
        state = self._read_state()
        state["last_compacted"] = True
        # After compaction, reduce cumulative by ~70% (compaction summarizes)
        state["cumulative_bytes"] = int(state["cumulative_bytes"] * 0.3)
        self._write_state(state)

    def was_just_compacted(self) -> bool:
        """Check if compaction occurred since last turn."""
        state = self._read_state()
        return state.get("last_compacted", False)

    def get_level(self) -> PressureLevel:
        """Get current pressure level."""
        cumulative = self._read_state()["cumulative_bytes"]
        if cumulative >= PRESSURE_THRESHOLDS[PressureLevel.CRITICAL]:
            return PressureLevel.CRITICAL
        if cumulative >= PRESSURE_THRESHOLDS[PressureLevel.HIGH]:
            return PressureLevel.HIGH
        if cumulative >= PRESSURE_THRESHOLDS[PressureLevel.MEDIUM]:
            return PressureLevel.MEDIUM
        return PressureLevel.LOW

    def get_pressure_kb(self) -> int:
        """Get cumulative pressure in KB."""
        return self._read_state()["cumulative_bytes"] // 1024

    def get_turn_count(self) -> int:
        """Get turn count from pressure tracker."""
        return self._read_state()["turn_count"]

    def get_state_summary(self) -> dict:
        """Get full state for diagnostics."""
        state = self._read_state()
        level = self.get_level()
        return {
            "cumulative_kb": state["cumulative_bytes"] // 1024,
            "peak_kb": state["peak_bytes"] // 1024,
            "turn_count": state["turn_count"],
            "level": level.value,
            "last_compacted": state["last_compacted"],
        }

    def reset(self):
        """Reset pressure tracker (called on session start)."""
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass
