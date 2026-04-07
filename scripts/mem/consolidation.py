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
from datetime import datetime, timezone
from typing import Dict, List, Optional

from mem.memory import (
    Memory,
    MemoryStatus,
    MemoryStore,
    MemoryTier,
    _log,
)


# ---------------------------------------------------------------------------
# Jaccard similarity (mirrors jam/consensus.py _similarity pattern)
# ---------------------------------------------------------------------------

_MIN_WORD_LEN = 4
_SIMILARITY_THRESHOLD = 0.35


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Word-overlap Jaccard similarity between two strings."""
    wa = {w for w in re.findall(r"[a-z0-9]+", text_a.lower()) if len(w) >= _MIN_WORD_LEN}
    wb = {w for w in re.findall(r"[a-z0-9]+", text_b.lower()) if len(w) >= _MIN_WORD_LEN}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_active(store: MemoryStore, tier: Optional[str] = None) -> List[Memory]:
    """Load active memories, optionally filtered by tier."""
    result: List[Memory] = []
    for record in store._sm.list("memories"):
        mem = store._dict_to_memory(record)
        if not mem or mem.status != MemoryStatus.ACTIVE.value:
            continue
        if tier and mem.tier != tier:
            continue
        result.append(mem)
    return result


def _cluster_by_similarity(memories: List[Memory]) -> List[List[Memory]]:
    """Group memories into clusters by Jaccard word-overlap similarity."""
    clusters: List[List[Memory]] = []
    for mem in memories:
        placed = False
        text = mem.title + " " + mem.content
        for cluster in clusters:
            rep = cluster[0]
            if _jaccard_similarity(rep.title + " " + rep.content, text) > _SIMILARITY_THRESHOLD:
                cluster.append(mem)
                placed = True
                break
        if not placed:
            clusters.append([mem])
    return clusters


# ---------------------------------------------------------------------------
# Working -> Episodic consolidation
# ---------------------------------------------------------------------------

def consolidate_working(store: MemoryStore) -> Dict[str, int]:
    """Promote working-tier memories to episodic tier.

    - Drops transient items: access_count <= 1 AND older than the session TTL.
    - Merges similar remaining items using Jaccard similarity.
    - Promotes surviving items to episodic tier.

    Returns {promoted: int, dropped: int, merged: int}.
    """
    promoted = 0
    dropped = 0
    merged = 0

    now = datetime.now(timezone.utc)
    working_memories = _fetch_active(store, MemoryTier.WORKING.value)

    if not working_memories:
        return {"promoted": promoted, "dropped": dropped, "merged": merged}

    # Separate transient vs retainable
    retainable: List[Memory] = []
    for mem in working_memories:
        ttl = mem.ttl_days if mem.ttl_days is not None else 1
        created = datetime.fromisoformat(mem.created.replace("Z", "+00:00"))
        age_days = (now - created).total_seconds() / 86400

        if mem.access_count <= 1 and age_days > ttl:
            store._sm.update("memories", mem.id, {"status": MemoryStatus.ARCHIVED.value})
            dropped += 1
        else:
            retainable.append(mem)

    # Cluster and process
    for cluster in _cluster_by_similarity(retainable):
        if len(cluster) == 1:
            store._sm.update("memories", cluster[0].id, {"tier": MemoryTier.EPISODIC.value})
            promoted += 1
        else:
            cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
            survivor = cluster[0]
            merged_content = survivor.content
            for other in cluster[1:]:
                if other.content and other.content not in merged_content:
                    merged_content += "\n---\n" + other.content
                store._sm.update("memories", other.id, {
                    "status": MemoryStatus.ARCHIVED.value,
                    "tier": MemoryTier.EPISODIC.value,
                })
                merged += 1
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

    Returns {promoted: int, merged: int, archived: int}.
    """
    promoted = 0
    merged_count = 0
    archived = 0

    episodic_memories = _fetch_active(store, MemoryTier.EPISODIC.value)
    if not episodic_memories:
        return {"promoted": promoted, "merged": merged_count, "archived": archived}

    # Identify promotion candidates from similarity clusters
    candidates: List[List[Memory]] = []
    for cluster in _cluster_by_similarity(episodic_memories):
        session_ids = {m.session_id for m in cluster if m.session_id}
        if (len(session_ids) >= 3
                or any(m.access_count >= 10 for m in cluster)
                or any(m.importance >= 8 for m in cluster)):
            candidates.append(cluster)

    for cluster in candidates:
        cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        survivor = cluster[0]

        if len(cluster) > 1:
            merged_content = survivor.content
            for other in cluster[1:]:
                if other.content and other.content not in survivor.content:
                    merged_content += "\n---\n" + other.content
                store._sm.update("memories", other.id, {
                    "status": MemoryStatus.ARCHIVED.value,
                })
                archived += 1
                merged_count += 1
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

    Keeps the memory with higher importance/access_count, archives the rest.

    Returns {merged: int, archived: int}.
    """
    merged = 0
    archived = 0

    memories = _fetch_active(store, tier)
    if not memories:
        return {"merged": merged, "archived": archived}

    for cluster in _cluster_by_similarity(memories):
        if len(cluster) <= 1:
            continue
        cluster.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
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

def _trigger_brain_compile():
    """Trigger brain:compile to synthesize wiki articles from chunks.

    This maps the wicked-mem consolidation (chunks→wiki) to the brain's
    compile pipeline. Fires async via the brain API — non-blocking.
    Fails silently if brain is unavailable.
    """
    try:
        import json
        import os
        import urllib.request
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=json.dumps({"action": "compile", "params": {}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # brain compile is best-effort


def _trigger_brain_lint():
    """Trigger brain:lint to auto-decay working-tier chunks with expired TTL.

    Maps wicked-mem working-tier decay to brain's lint pipeline.
    Fails silently if brain is unavailable.
    """
    try:
        import json
        import os
        import urllib.request
        port = int(os.environ.get("WICKED_BRAIN_PORT", "4242"))
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=json.dumps({"action": "lint", "params": {}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # brain lint is best-effort


def consolidate_all(store: MemoryStore) -> Dict:
    """Run both consolidation passes, deduplication, and brain sync.

    Returns combined stats from all operations.
    """
    working_stats = consolidate_working(store)
    episodic_stats = consolidate_episodic(store)
    dedup_stats = deduplicate(store)

    # Trigger brain compile + lint after consolidation
    # compile: synthesizes wiki articles from promoted chunks
    # lint: auto-decays expired working-tier brain chunks
    _trigger_brain_compile()
    _trigger_brain_lint()

    result = {
        "working_to_episodic": working_stats,
        "episodic_to_semantic": episodic_stats,
        "deduplication": dedup_stats,
    }

    _log("mem", "normal", "consolidation.all", detail=result)
    return result
