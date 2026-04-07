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
  - Writes to: wicked-brain via brain API (chunk files + FTS5 index)
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


# Fact types eligible for promotion to wicked-mem
PROMOTABLE_TYPES = {"decision", "discovery"}

# Minimum content length for promotion
MIN_CONTENT_LENGTH = 15


def _brain_api(action, params=None, timeout=3):
    """Call brain API. Returns parsed JSON or None."""
    try:
        import urllib.request
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))
        payload = json.dumps({"action": action, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _write_brain_memory(title, content, tier="episodic", tags=None, mem_type="episodic", importance=5):
    """Write a memory chunk to brain. Returns chunk_id or None."""
    try:
        import uuid
        mem_id = str(uuid.uuid4())
        chunk_id = f"memories/{tier}/mem-{mem_id}"
        chunk_path = Path.home() / ".wicked-brain" / f"{chunk_id}.md"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        tags_list = tags or []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        lines = ["---"]
        lines.append("source: wicked-mem")
        lines.append(f"memory_type: {mem_type}")
        lines.append(f"memory_tier: {tier}")
        lines.append(f"title: {title}")
        lines.append(f"importance: {importance}")
        lines.append("contains:")
        for t in tags_list:
            lines.append(f"  - {t}")
        lines.append(f'indexed_at: "{now}"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(content)

        chunk_path.write_text("\n".join(lines), encoding="utf-8")

        # Index in brain FTS5
        search_text = f"{title} {content} {' '.join(tags_list)}"
        _brain_api("index", {"id": f"{chunk_id}.md", "path": f"{chunk_id}.md", "content": search_text, "brain_id": "wicked-brain"})
        return chunk_id
    except Exception:
        return None


def _run_mem_store(title: str, content: str, mem_type: str = "episodic") -> bool:
    """Store a memory via brain API (write chunk + index).

    Returns True on success, False on failure.
    """
    try:
        chunk_id = _write_brain_memory(
            title=title,
            content=content,
            tier=mem_type if mem_type in ("episodic", "semantic", "working") else "episodic",
            tags=[],
            mem_type=mem_type,
            importance=5,
        )
        return chunk_id is not None
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
                pass  # fail open: treat as empty promoted set
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
