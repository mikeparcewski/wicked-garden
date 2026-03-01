#!/usr/bin/env python3
"""
wicked-smaht v2: Multi-Lane Tracking

Tracks parallel work streams (lanes) within a session.
Each lane has a priority, status, and activity tracking.

Lanes allow context-switching between tasks without losing
the state of paused work. Priority decay moves stale lanes
to dormant status, and reactivation brings them back.

Storage:
~/.something-wicked/wicked-garden/local/wicked-smaht/sessions/{session_id}/lanes.jsonl
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


LANE_STATUSES = ("active", "paused", "dormant", "completed")
PRIORITIES = ("high", "medium", "low")

# After this many seconds of inactivity, a paused lane becomes dormant
DORMANCY_THRESHOLD_SECONDS = 600  # 10 minutes


@dataclass
class Lane:
    """A parallel work stream within a session."""
    lane_id: str
    description: str
    priority: str = "medium"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    last_active_at: str = ""
    topics: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    turn_count: int = 0

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.lane_id:
            self.lane_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.last_active_at:
            self.last_active_at = now

    def touch(self):
        """Mark lane as recently active."""
        now = datetime.now(timezone.utc).isoformat()
        self.updated_at = now
        self.last_active_at = now
        self.turn_count += 1

    def to_dict(self) -> dict:
        return asdict(self)


class LaneTracker:
    """Manages parallel work lanes within a session."""

    MAX_LANES = 10

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.lanes_path = session_dir / "lanes.jsonl"
        self.lanes: list[Lane] = self._load_lanes()

    def _load_lanes(self) -> list[Lane]:
        """Load lanes from disk."""
        lanes = []
        if self.lanes_path.exists():
            try:
                for line in self.lanes_path.read_text().strip().split("\n"):
                    if line:
                        data = json.loads(line)
                        lanes.append(Lane(**data))
            except Exception:
                pass
        return lanes

    def save(self):
        """Save lanes to disk."""
        lines = [json.dumps(lane.to_dict()) for lane in self.lanes]
        self.lanes_path.write_text("\n".join(lines) + "\n" if lines else "")

    def get_active_lane(self) -> Optional[Lane]:
        """Get the currently active lane (highest priority active lane)."""
        active = [l for l in self.lanes if l.status == "active"]
        if not active:
            return None
        # Sort by priority (high > medium > low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        active.sort(key=lambda l: priority_order.get(l.priority, 1))
        return active[0]

    def create_lane(self, description: str, priority: str = "medium") -> Lane:
        """Create a new lane and set it as active."""
        # Pause any currently active lanes
        for lane in self.lanes:
            if lane.status == "active":
                lane.status = "paused"

        lane = Lane(
            lane_id=str(uuid.uuid4())[:8],
            description=description,
            priority=priority if priority in PRIORITIES else "medium",
            status="active",
        )
        self.lanes.append(lane)

        # Trim to max
        if len(self.lanes) > self.MAX_LANES:
            # Remove oldest completed or dormant lanes first
            self.lanes = sorted(
                self.lanes,
                key=lambda l: (
                    l.status != "completed",
                    l.status != "dormant",
                    l.updated_at,
                ),
            )[-self.MAX_LANES:]

        self.save()
        return lane

    def switch_to_lane(self, lane_id: str) -> Optional[Lane]:
        """Switch to a different lane, pausing the current one."""
        target = None
        for lane in self.lanes:
            if lane.lane_id == lane_id:
                target = lane
            elif lane.status == "active":
                lane.status = "paused"

        if target:
            target.status = "active"
            target.touch()
            self.save()

        return target

    def update_active_lane(self, user_msg: str, assistant_msg: str):
        """Update the active lane with turn information."""
        active = self.get_active_lane()
        if not active:
            return

        active.touch()

        # Extract topics from user message
        import re
        text_lower = user_msg.lower()
        concepts = [
            "caching", "auth", "authentication", "database", "api",
            "testing", "debugging", "refactoring", "performance",
            "security", "deployment", "logging", "monitoring",
        ]
        for concept in concepts:
            if re.search(rf"\b{re.escape(concept)}\b", text_lower) and concept not in active.topics:
                active.topics.append(concept)
                if len(active.topics) > 10:
                    active.topics.pop(0)

        # Extract files
        files = re.findall(
            r'([a-zA-Z_][a-zA-Z0-9_/.-]*\.'
            r'(?:py|ts|js|tsx|jsx|json|yaml|yml|md|sql|java|go|rs))\b',
            user_msg + " " + assistant_msg,
        )
        for f in files[:5]:
            if isinstance(f, tuple):
                f = f[0]
            if f not in active.files:
                active.files.append(f)
                if len(active.files) > 20:
                    active.files.pop(0)

        self.save()

    def apply_priority_decay(self):
        """Move stale paused lanes to dormant status."""
        now = time.time()
        changed = False

        for lane in self.lanes:
            if lane.status != "paused":
                continue

            try:
                last_active = datetime.fromisoformat(lane.last_active_at).timestamp()
            except (ValueError, TypeError):
                continue

            if now - last_active > DORMANCY_THRESHOLD_SECONDS:
                lane.status = "dormant"
                changed = True

        if changed:
            self.save()

    def reactivate_lane(self, lane_id: str) -> Optional[Lane]:
        """Reactivate a dormant or paused lane."""
        return self.switch_to_lane(lane_id)

    def complete_lane(self, lane_id: str) -> Optional[Lane]:
        """Mark a lane as completed."""
        for lane in self.lanes:
            if lane.lane_id == lane_id:
                lane.status = "completed"
                lane.updated_at = datetime.now(timezone.utc).isoformat()
                self.save()
                return lane
        return None

    def detect_lane_switch(self, user_msg: str) -> Optional[str]:
        """Detect if the user is switching to a different task.

        Returns description of new task if a switch is detected, None otherwise.
        """
        import re
        user_lower = user_msg.lower()

        # Explicit switch patterns
        switch_patterns = [
            r"(?:let's switch to|back to|now let's|moving on to|switching to) ([^.!?\n]{10,100})",
            r"(?:actually|wait),? (?:let's|let me) ([^.!?\n]{10,100})",
            r"(?:put that on hold|park that|pause that)",
        ]

        for pattern in switch_patterns:
            matches = re.findall(pattern, user_lower)
            if matches:
                if isinstance(matches[0], str) and len(matches[0]) > 5:
                    return matches[0].strip()
                return None

        # Detect implicit switch: new task statement while active lane exists
        task_patterns = [
            r"(?:i(?:'m| am) (?:working on|trying to|building|fixing|implementing)) ([^.!?\n]{10,100})",
        ]
        active = self.get_active_lane()
        if active and active.turn_count > 2:
            for pattern in task_patterns:
                matches = re.findall(pattern, user_lower)
                if matches:
                    new_task = matches[0].strip()
                    # Only trigger switch if task seems different
                    if active.description.lower() not in new_task and new_task not in active.description.lower():
                        return new_task

        return None

    def get_state(self) -> dict:
        """Get lane state summary."""
        active = self.get_active_lane()
        return {
            "total_lanes": len(self.lanes),
            "active_lane": active.to_dict() if active else None,
            "paused_count": sum(1 for l in self.lanes if l.status == "paused"),
            "dormant_count": sum(1 for l in self.lanes if l.status == "dormant"),
            "completed_count": sum(1 for l in self.lanes if l.status == "completed"),
            "lanes": [l.to_dict() for l in self.lanes],
        }

    def to_markdown(self) -> str:
        """Format lane state as markdown for context injection."""
        active = self.get_active_lane()
        if not active and not self.lanes:
            return ""

        lines = []
        if active:
            lines.append(f"**Active lane**: {active.description}")
            if active.topics:
                lines.append(f"  Topics: {', '.join(active.topics[:5])}")

        paused = [l for l in self.lanes if l.status == "paused"]
        if paused:
            lines.append("**Paused lanes**: " + ", ".join(l.description[:40] for l in paused[:3]))

        dormant = [l for l in self.lanes if l.status == "dormant"]
        if dormant:
            lines.append(f"**Dormant lanes**: {len(dormant)}")

        return "\n".join(lines)
