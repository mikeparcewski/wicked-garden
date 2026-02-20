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
  - Writes to: wicked-mem via discover_script + subprocess
  - Marks promoted facts with promoted_at timestamp
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .fact_extractor import Fact, FactExtractor


# Fact types eligible for promotion to wicked-mem
PROMOTABLE_TYPES = {"decision", "discovery"}

# Minimum content length for promotion
MIN_CONTENT_LENGTH = 15


def _discover_mem_script() -> Optional[Path]:
    """Discover wicked-mem's memory.py script.

    Uses two-tier lookup:
    1. Cache path: ~/.claude/plugins/cache/wicked-garden/wicked-mem/{version}/scripts/memory.py
    2. Local sibling: ../wicked-mem/scripts/memory.py (for dev in monorepo)
    """
    # Check cache first
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / "wicked-mem"
    if cache_base.exists():
        versions = sorted(
            [v for v in cache_base.iterdir() if v.is_dir()],
            reverse=True,
        )
        for version_dir in versions:
            script = version_dir / "scripts" / "memory.py"
            if script.exists():
                return script

    # Check local sibling (monorepo dev)
    this_dir = Path(__file__).resolve().parent
    # scripts/v2 -> scripts -> wicked-smaht -> plugins -> wicked-mem
    plugin_root = this_dir.parent.parent
    sibling = plugin_root.parent / "wicked-mem" / "scripts" / "memory.py"
    if sibling.exists():
        return sibling

    return None


def _run_mem_store(script: Path, content: str, mem_type: str = "semantic") -> bool:
    """Store a memory via wicked-mem's memory.py script.

    Returns True on success, False on failure.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(script), "store", content, "--type", mem_type],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
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

        # Discover wicked-mem script
        mem_script = _discover_mem_script()
        if not mem_script:
            return {
                "status": "mem_not_available",
                "promoted": 0,
                "skipped": len(candidates),
                "reason": "wicked-mem not installed or memory.py not found",
            }

        promoted = 0
        failed = 0

        for fact in candidates:
            # Build memory content with context
            mem_type = "decision" if fact.type == "decision" else "semantic"
            content = fact.content
            if fact.entities:
                content += f" (entities: {', '.join(fact.entities[:3])})"

            success = _run_mem_store(mem_script, content, mem_type)
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
