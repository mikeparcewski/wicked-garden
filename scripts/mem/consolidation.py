"""
Memory Consolidation Engine — 3-tier auto-consolidation.

Promotes memories across tiers:
  working  -> episodic  (session end: drop transient, merge similar)
  episodic -> semantic  (cross-session patterns, high access, high importance)

Also provides deduplication using word-overlap Jaccard similarity,
reusing the pattern from jam/consensus.py.

Stdlib-only. Cross-platform.
"""

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Resolve siblings from scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mem.memory import (
    Memory,
    MemoryStatus,
    MemoryStore,
    MemoryTier,
    MemoryType,
    _log,
)


# ---------------------------------------------------------------------------
# Jaccard similarity (mirrors jam/consensus.py _similarity pattern)
# ---------------------------------------------------------------------------

_MIN_WORD_LEN = 4


def _jaccard_similarity(text_a: str, text_b: str, min_word_len: int = _MIN_WORD_LEN) -> float:
    """Word-overlap Jaccard similarity between two strings.

    Extracts words of length >= min_word_len, lowercased, then computes
    |intersection| / |union|.  Matches the pattern in jam/consensus.py.
    """
    wa = {w for w in re.findall(r"[a-z0-9]+", text_a.lower()) if len(w) >= min_word_len}
    wb = {w for w in re.findall(r"[a-z0-9]+", text_b.lower()) if len(w) >= min_word_len}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


_SIMILARITY_THRESHOLD = 0.35


# ---------------------------------------------------------------------------
# Working -> Episodic consolidation
# ---------------------------------------------------------------------------

def consolidate_working(store: MemoryStore) -> Dict[str, int]:
    """Promote working-tier memories to episodic tier.

    - Drops transient items: access_count <= 1 AND older than the session TTL
      (default 1 day for working memories).
    - Merges similar remaining items using Jaccard similarity.
    - Promotes surviving items to episodic tier.

    Returns {promoted: int, dropped: int, merged: int}.
    """
    promoted = 0
    dropped = 0
    merged = 0

    now = datetime.now(timezone.utc)

    # Gather all active working-tier memories
    all_records = store._sm.list("memories")
    working_memories: List[Memory] = []
    for record in all_records:
        mem = store._dict_to_memory(record)
        if (
            mem
            and mem.tier == MemoryTier.WORKING.value
            and mem.status == MemoryStatus.ACTIVE.value
        ):
            working_memories.append(mem)

    if not working_memories:
        return {"promoted": promoted, "dropped": dropped, "merged": merged}

    # Separate transient vs retainable
    retainable: List[Memory] = []
    for mem in working_memories:
        ttl = mem.ttl_days if mem.ttl_days is not None else 1
        created = datetime.fromisoformat(mem.created.replace("Z", "+00:00"))
        age_days = (now - created).total_seconds() / 86400

        if mem.access_count <= 1 and age_days > ttl:
            # Drop transient — archive it
            store._sm.update("memories", mem.id, {"status": MemoryStatus.ARCHIVED.value})
            dropped += 1
        else:
            retainable.append(mem)

    # Cluster similar retainable memories using Jaccard
    clusters: List[List[Memory]] = []
    for mem in retainable:
        placed = False
        for cluster in clusters:
            representative = cluster[0]
            sim = _jaccard_similarity(
                representative.title + " " + representative.content,
                mem.title + " " + mem.content,
            )
            if sim > _SIMILARITY_THRESHOLD:
                cluster.append(mem)
                placed = True
                break
        if not placed:
            clusters.append([mem])

    # Process each cluster
    for cluster in clusters:
        if len(cluster) == 1:
            # Single item — just promote
            mem = cluster[0]
            store._sm.update("memories", mem.id, {"tier": MemoryTier.EPISODIC.value})
            promoted += 1
        else:
            # Merge: pick the one with highest importance/access_count as survivor
            cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
            survivor = cluster[0]

            # Merge content from others into survivor
            extra_content = []
            for other in cluster[1:]:
                extra_content.append(other.content)
                # Archive the merged-away memories
                store._sm.update("memories", other.id, {
                    "status": MemoryStatus.ARCHIVED.value,
                    "tier": MemoryTier.EPISODIC.value,
                })
                merged += 1

            # Update survivor with merged content and promote
            merged_content = survivor.content
            for ec in extra_content:
                if ec and ec not in merged_content:
                    merged_content += "\n---\n" + ec
            store._sm.update("memories", survivor.id, {
                "tier": MemoryTier.EPISODIC.value,
                "content": merged_content,
            })
            promoted += 1

    _log("mem", "verbose", "consolidation.working",
         detail={"promoted": promoted, "dropped": dropped, "merged": merged})
    return {"promoted": promoted, "dropped": dropped, "merged": merged}


# ---------------------------------------------------------------------------
# Episodic -> Semantic consolidation
# ---------------------------------------------------------------------------

def consolidate_episodic(store: MemoryStore) -> Dict[str, int]:
    """Promote episodic-tier memories to semantic tier.

    Promotion criteria (any one triggers promotion):
    - Memory appears across 3+ distinct sessions (by session_id diversity)
    - access_count >= 10
    - importance >= 8

    Similar promoted memories are merged into a single semantic entry.
    Originals are archived for audit trail.

    Returns {promoted: int, merged: int, archived: int}.
    """
    promoted = 0
    merged_count = 0
    archived = 0

    all_records = store._sm.list("memories")
    episodic_memories: List[Memory] = []
    for record in all_records:
        mem = store._dict_to_memory(record)
        if (
            mem
            and mem.tier == MemoryTier.EPISODIC.value
            and mem.status == MemoryStatus.ACTIVE.value
        ):
            episodic_memories.append(mem)

    if not episodic_memories:
        return {"promoted": promoted, "merged": merged_count, "archived": archived}

    # Count session_id diversity across all episodic memories for cross-session detection.
    # Group by content similarity to find recurring patterns.
    content_clusters: List[List[Memory]] = []
    for mem in episodic_memories:
        placed = False
        for cluster in content_clusters:
            representative = cluster[0]
            sim = _jaccard_similarity(
                representative.title + " " + representative.content,
                mem.title + " " + mem.content,
            )
            if sim > _SIMILARITY_THRESHOLD:
                cluster.append(mem)
                placed = True
                break
        if not placed:
            content_clusters.append([mem])

    # Identify promotion candidates
    candidates: List[List[Memory]] = []
    for cluster in content_clusters:
        # Check session diversity
        session_ids = {m.session_id for m in cluster if m.session_id}
        session_diverse = len(session_ids) >= 3

        # Check individual promotion triggers
        any_high_access = any(m.access_count >= 10 for m in cluster)
        any_high_importance = any(m.importance >= 8 for m in cluster)

        if session_diverse or any_high_access or any_high_importance:
            candidates.append(cluster)

    # Process candidates
    for cluster in candidates:
        # Sort by importance then access_count descending
        cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        survivor = cluster[0]

        if len(cluster) > 1:
            # Merge content from duplicates
            extra_content = []
            for other in cluster[1:]:
                if other.content and other.content not in survivor.content:
                    extra_content.append(other.content)
                # Archive originals
                store._sm.update("memories", other.id, {
                    "status": MemoryStatus.ARCHIVED.value,
                })
                archived += 1
                merged_count += 1

            merged_content = survivor.content
            for ec in extra_content:
                merged_content += "\n---\n" + ec

            store._sm.update("memories", survivor.id, {
                "tier": MemoryTier.SEMANTIC.value,
                "content": merged_content,
            })
        else:
            store._sm.update("memories", survivor.id, {
                "tier": MemoryTier.SEMANTIC.value,
            })
        promoted += 1

    _log("mem", "verbose", "consolidation.episodic",
         detail={"promoted": promoted, "merged": merged_count, "archived": archived})
    return {"promoted": promoted, "merged": merged_count, "archived": archived}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(store: MemoryStore, tier: Optional[str] = None) -> Dict[str, int]:
    """Find and merge near-duplicate memories within a tier (or all tiers).

    Uses word-overlap Jaccard similarity at threshold 0.35.
    Keeps the memory with higher importance/access_count, archives the rest.

    Returns {merged: int, archived: int}.
    """
    merged = 0
    archived = 0

    all_records = store._sm.list("memories")
    memories: List[Memory] = []
    for record in all_records:
        mem = store._dict_to_memory(record)
        if not mem or mem.status != MemoryStatus.ACTIVE.value:
            continue
        if tier and mem.tier != tier:
            continue
        memories.append(mem)

    if not memories:
        return {"merged": merged, "archived": archived}

    # Cluster by similarity
    clusters: List[List[Memory]] = []
    for mem in memories:
        placed = False
        for cluster in clusters:
            representative = cluster[0]
            sim = _jaccard_similarity(
                representative.title + " " + representative.content,
                mem.title + " " + mem.content,
            )
            if sim > _SIMILARITY_THRESHOLD:
                cluster.append(mem)
                placed = True
                break
        if not placed:
            clusters.append([mem])

    # Process clusters with duplicates
    for cluster in clusters:
        if len(cluster) <= 1:
            continue

        cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        # Keep first (highest score), archive the rest
        for dup in cluster[1:]:
            store._sm.update("memories", dup.id, {
                "status": MemoryStatus.ARCHIVED.value,
            })
            merged += 1
            archived += 1

    _log("mem", "verbose", "consolidation.dedup",
         detail={"merged": merged, "archived": archived, "tier": tier})
    return {"merged": merged, "archived": archived}


# ---------------------------------------------------------------------------
# Consolidated runner
# ---------------------------------------------------------------------------

def consolidate_all(store: MemoryStore) -> Dict:
    """Run both consolidation passes and deduplication.

    Returns combined stats from all three operations.
    """
    working_stats = consolidate_working(store)
    episodic_stats = consolidate_episodic(store)
    dedup_stats = deduplicate(store)

    result = {
        "working_to_episodic": working_stats,
        "episodic_to_semantic": episodic_stats,
        "deduplication": dedup_stats,
    }

    _log("mem", "normal", "consolidation.all", detail=result)
    return result
