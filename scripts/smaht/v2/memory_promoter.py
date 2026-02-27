#!/usr/bin/env python3
"""
wicked-smaht v2: Memory Promotion Pipeline

Promotes high-value facts from session-local storage to wicked-mem
for cross-session persistence. Uses type-based filtering and
idempotent operations to avoid duplicate promotions.

Promotion criteria:
  - Fact type: decision, discovery (highest value for cross-session use)
  - Not already promoted (tracked via promoted_at timestamp)
  - Content length > 15 chars (filter noise)

Integration:
  - Reads from: facts.jsonl (local session facts)
  - Writes to: wicked-mem via direct MemoryStore import
  - Marks promoted facts with promoted_at timestamp
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# All domain scripts live under plugins/wicked-garden/scripts/
# memory_promoter.py is at scripts/smaht/v2/, so parents[2] = scripts/
_SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

# Also add the v2 directory for sibling imports
_V2_DIR = Path(__file__).resolve().parent
if str(_V2_DIR) not in sys.path:
    sys.path.insert(0, str(_V2_DIR))

from fact_extractor import Fact, FactExtractor
from mem.memory import MemoryStore, MemoryType, Importance


# Fact types eligible for promotion to wicked-mem
PROMOTABLE_TYPES = {"decision", "discovery"}

# Minimum content length for promotion
MIN_CONTENT_LENGTH = 15


def _run_mem_store(title: str, content: str, mem_type: str = "episodic") -> bool:
    """Store a memory via direct MemoryStore call.

    Returns True on success, False on failure.
    """
    try:
        store = MemoryStore()
        mt = MemoryType(mem_type) if mem_type in {m.value for m in MemoryType} else MemoryType.EPISODIC
        store.store(
            title=title,
            content=content,
            type=mt,
        )
        return True
    except Exception:
        return False


class MemoryPromoter:
    """Promotes session facts to wicked-mem for cross-session persistence."""

    def __init__(self, session_dir: Path, fact_extractor: FactExtractor):
        self.session_dir = session_dir
        self.fact_extractor = fact_extractor
        self.promoted_path = session_dir / "promoted.json"
        self._promoted_ids: set[str] = self._load_promoted()

    def _load_promoted(self) -> set[str]:
        """Load set of already-promoted fact IDs."""
        if self.promoted_path.exists():
            try:
                data = json.loads(self.promoted_path.read_text())
                return set(data.get("promoted_ids", []))
            except Exception:
                pass
        return set()

    def _save_promoted(self):
        """Save promoted fact IDs."""
        data = {
            "promoted_ids": sorted(self._promoted_ids),
            "last_promotion": datetime.now(timezone.utc).isoformat(),
        }
        self.promoted_path.write_text(json.dumps(data, indent=2))

    def get_candidates(self) -> list[Fact]:
        """Get facts eligible for promotion.

        Criteria:
        - Type is in PROMOTABLE_TYPES (decision, discovery)
        - Not already promoted
        - Content length > MIN_CONTENT_LENGTH
        """
        candidates = []
        for fact in self.fact_extractor.facts:
            if fact.type not in PROMOTABLE_TYPES:
                continue
            if fact.id in self._promoted_ids:
                continue
            if len(fact.content) < MIN_CONTENT_LENGTH:
                continue
            candidates.append(fact)
        return candidates

    def promote(self, dry_run: bool = False) -> dict:
        """Promote eligible facts to wicked-mem.

        Args:
            dry_run: If True, return candidates without promoting.

        Returns:
            Summary of promotion results.
        """
        candidates = self.get_candidates()

        if not candidates:
            return {
                "status": "no_candidates",
                "promoted": 0,
                "skipped": 0,
                "candidates": [],
            }

        if dry_run:
            return {
                "status": "dry_run",
                "promoted": 0,
                "candidates": [f.to_dict() for f in candidates],
            }

        promoted = 0
        failed = 0

        for fact in candidates:
            # Build memory title and content
            mem_type = "decision" if fact.type == "decision" else "episodic"
            title = f"[{fact.type}] {fact.content[:80]}"
            content = fact.content
            if fact.entities:
                content += f" (entities: {', '.join(fact.entities[:3])})"

            success = _run_mem_store(title, content, mem_type)
            if success:
                self._promoted_ids.add(fact.id)
                promoted += 1
            else:
                failed += 1

        self._save_promoted()

        return {
            "status": "completed",
            "promoted": promoted,
            "failed": failed,
            "total_candidates": len(candidates),
        }

    def get_promotion_state(self) -> dict:
        """Get current promotion state."""
        candidates = self.get_candidates()
        return {
            "total_facts": len(self.fact_extractor.facts),
            "promoted_count": len(self._promoted_ids),
            "pending_candidates": len(candidates),
            "promotable_types": sorted(PROMOTABLE_TYPES),
        }
