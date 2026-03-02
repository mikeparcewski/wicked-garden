"""
Wicked Memory - Natural Memory System

Extends the cache infrastructure with cognitive memory types:
- Episodic: What happened, what we learned
- Procedural: How to do things, patterns
- Decision: Choices made and rationale
- Preference: User/agent preferences
- Working: Current session context

All data flows through StorageManager("wicked-mem") which routes to the
Control Plane when available and falls back to local JSON files.

All memory types are stored in a single "memories" source with a "type"
field for filtering.  CP is the ID authority (#106) and stores provenance
fields plus a metadata JSON blob for display-only fields (#107).
"""

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager


class MemoryType(Enum):
    """Types of memories."""
    EPISODIC = "episodic"       # What happened
    PROCEDURAL = "procedural"   # How-to
    DECISION = "decision"       # Why we chose X
    PREFERENCE = "preference"   # User/agent preferences
    WORKING = "working"         # Current session context


class MemoryStatus(Enum):
    """Memory lifecycle states."""
    ACTIVE = "active"           # Live, surfaced in searches
    ARCHIVED = "archived"       # Exists but not auto-surfaced
    DECAYED = "decayed"         # Marked for cleanup


class Importance(Enum):
    """Memory importance levels. Values are integers for CP compatibility."""
    LOW = 2
    MEDIUM = 5
    HIGH = 8


_IMPORTANCE_FROM_STR = {"low": 2, "medium": 5, "high": 8, "critical": 9}


def _parse_importance(val) -> int:
    """Parse importance from int or legacy string format."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        return _IMPORTANCE_FROM_STR.get(val.lower(), 5)
    return 5


# Default TTLs by memory type (in days)
DEFAULT_TTLS = {
    MemoryType.EPISODIC: 90,
    MemoryType.PROCEDURAL: None,  # Permanent
    MemoryType.DECISION: None,    # Permanent
    MemoryType.PREFERENCE: None,  # Permanent
    MemoryType.WORKING: 1,
}


@dataclass
class Memory:
    """A single memory entry."""
    # Identity
    id: str
    type: str  # MemoryType value

    # Content
    title: str
    summary: str
    content: str

    # Metadata (stored in CP metadata JSON blob)
    context: str = ""           # When is this relevant
    outcome: Optional[str] = None
    related: List[str] = field(default_factory=list)

    # Provenance (CP columns)
    author: str = "claude"      # user, claude, or agent
    agent_id: Optional[str] = None
    source: str = "manual"      # auto, manual, hook

    # Lifecycle
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    accessed: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    access_count: int = 0
    ttl_days: Optional[int] = None
    importance: int = 5         # Importance value (2=low, 5=medium, 8=high)
    status: str = "active"      # MemoryStatus value

    # Search
    tags: List[str] = field(default_factory=list)

    # Scope (project=None means global)
    project: Optional[str] = None

    # Session
    session_id: Optional[str] = None


def generate_id() -> str:
    """Generate a unique memory ID (UUID)."""
    return str(uuid.uuid4())


class MemoryStore:
    """StorageManager-backed memory storage and operations."""

    def __init__(self, project: Optional[str] = None):
        self.project = project or self._detect_project()
        self._sm = StorageManager("wicked-mem")

    def _detect_project(self) -> Optional[str]:
        """Detect project name from current directory."""
        cwd = Path.cwd()
        if (cwd / ".git").exists():
            return cwd.name
        if (cwd / "package.json").exists():
            return cwd.name
        if (cwd / "pyproject.toml").exists():
            return cwd.name
        return None

    def _source_for_type(self, mem_type: str) -> str:
        """Return the CP source name. All types use a single 'memories' source."""
        return "memories"

    def _memory_to_dict(self, memory: Memory) -> Dict:
        """Convert Memory dataclass to a dict for CP storage.

        Packs context/outcome/related into a 'metadata' JSON blob
        (CP #107) and maps field names to CP schema.
        """
        d = {
            "id": memory.id,
            "type": memory.type,
            "title": memory.title,
            "summary": memory.summary,
            "content": memory.content,
            "author": memory.author,
            "agent_id": memory.agent_id,
            "source": memory.source,
            "importance": memory.importance,
            "status": memory.status,
            "tags": memory.tags,
            "project": memory.project,
            "session_id": memory.session_id,
            "ttl_days": memory.ttl_days,
            "accessed_at": memory.accessed,
            "access_count": memory.access_count,
            "metadata": {
                "context": memory.context,
                "outcome": memory.outcome,
                "related": memory.related,
            },
        }
        return d

    def _dict_to_memory(self, data: Dict) -> Optional[Memory]:
        """Convert a stored dict back to a Memory object.

        Handles both CP format (accessed_at, metadata blob) and
        legacy local format (accessed, flat fields).
        """
        if not data:
            return None
        access_count = data.get("access_count", 0)
        if isinstance(access_count, str):
            access_count = int(access_count)
        ttl_days = data.get("ttl_days")
        if isinstance(ttl_days, str):
            ttl_days = int(ttl_days)

        # Unpack metadata blob (CP #107) or fall back to flat fields
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        try:
            return Memory(
                id=data.get("id", generate_id()),
                type=data.get("type", "episodic"),
                title=data.get("title", "Untitled"),
                summary=data.get("summary", ""),
                content=data.get("content", ""),
                context=metadata.get("context", data.get("context", "")),
                outcome=metadata.get("outcome", data.get("outcome")),
                related=metadata.get("related", data.get("related", [])),
                author=data.get("author", "claude"),
                agent_id=data.get("agent_id"),
                source=data.get("source", "manual"),
                created=data.get("created_at", data.get("created", datetime.now(timezone.utc).isoformat() + "Z")),
                accessed=data.get("accessed_at", data.get("accessed", datetime.now(timezone.utc).isoformat() + "Z")),
                access_count=access_count,
                ttl_days=ttl_days,
                importance=_parse_importance(data.get("importance", 5)),
                status=data.get("status", "active"),
                tags=data.get("tags", []),
                project=data.get("project"),
                session_id=data.get("session_id"),
            )
        except Exception:
            return None

    # ==================== Core Operations ====================

    def store(
        self,
        title: str,
        content: str,
        type: MemoryType = MemoryType.EPISODIC,
        summary: Optional[str] = None,
        context: str = "",
        outcome: Optional[str] = None,
        tags: List[str] = None,
        importance: Importance = Importance.MEDIUM,
        author: str = "claude",
        agent_id: Optional[str] = None,
        source: str = "manual",
        session_id: Optional[str] = None,
    ) -> Memory:
        """Store a new memory."""
        memory = Memory(
            id=generate_id(),
            type=type.value,
            title=title,
            summary=summary or content[:200] + "..." if len(content) > 200 else content,
            content=content,
            context=context,
            outcome=outcome,
            author=author,
            agent_id=agent_id,
            importance=importance.value,
            project=self.project,
            tags=tags or [],
            ttl_days=DEFAULT_TTLS.get(type),
            source=source,
            session_id=session_id,
        )

        self._sm.create("memories", self._memory_to_dict(memory))
        return memory

    def recall(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        type: Optional[MemoryType] = None,
        limit: int = 10,
        include_archived: bool = False,
        all_projects: bool = False,
    ) -> List[Memory]:
        """Recall memories matching criteria."""
        params = {}
        if type:
            params["type"] = type.value
        if not all_projects and self.project:
            params["project"] = self.project

        memories = []
        seen_ids = set()

        # Use FTS5 search when query is present, list for tag/type-only filters
        if query:
            records = self._sm.search("memories", query, **params)
        else:
            records = self._sm.list("memories", **params)

        for record in records:
            memory = self._dict_to_memory(record)
            if memory and memory.id not in seen_ids:
                seen_ids.add(memory.id)
                memories.append(memory)

        # Filter by tags
        if tags:
            memories = [m for m in memories if all(t in m.tags for t in tags)]

        # Filter by status
        if not include_archived:
            memories = [m for m in memories if m.status == MemoryStatus.ACTIVE.value]

        # Sort by access count (most accessed first) and recency
        memories.sort(key=lambda m: (m.access_count, m.accessed), reverse=True)

        # Update access for returned memories
        for memory in memories[:limit]:
            self._update_access(memory)

        return memories[:limit]

    def search(self, pattern: str, path: Optional[str] = None,
               all_projects: bool = False) -> List[Memory]:
        """Search memories via StorageManager FTS5 search."""
        params = {}
        if not all_projects and self.project:
            params["project"] = self.project

        memories = []
        seen_ids: set = set()
        for record in self._sm.search("memories", pattern, **params):
            memory = self._dict_to_memory(record)
            if memory and memory.status == MemoryStatus.ACTIVE.value:
                if memory.id not in seen_ids:
                    seen_ids.add(memory.id)
                    self._update_access(memory)
                    memories.append(memory)

        return memories

    def search_all(
        self,
        query: str,
        include_archived: bool = False,
        limit: int = 50,
    ) -> List[Dict]:
        """Search ALL memories across ALL projects with enriched results."""
        results = []
        seen_ids = set()
        query_lower = query.lower()

        for record in self._sm.search("memories", query):
            memory = self._dict_to_memory(record)
            if not memory or memory.id in seen_ids:
                continue
            if not include_archived and memory.status != MemoryStatus.ACTIVE.value:
                continue

            # Determine match type
            match_type = None
            if query_lower in memory.title.lower():
                match_type = "title"
            elif any(query_lower in tag.lower() for tag in memory.tags):
                match_type = "tags"
            elif query_lower in memory.summary.lower():
                match_type = "summary"
            elif query_lower in memory.content.lower():
                match_type = "content"
            elif query_lower in memory.context.lower():
                match_type = "context"

            if match_type:
                seen_ids.add(memory.id)
                results.append({
                    "id": memory.id,
                    "title": memory.title,
                    "type": memory.type,
                    "project": memory.project or "global",
                    "match_type": match_type,
                    "tags": memory.tags,
                    "importance": memory.importance,
                    "summary": memory.summary[:100] + "..." if len(memory.summary) > 100 else memory.summary,
                    "access_count": memory.access_count,
                })
                if len(results) >= limit:
                    break

        # Sort by importance (higher = more important) then access count
        results.sort(key=lambda r: (-r["importance"], -r["access_count"]))
        return results[:limit]

    def forget(self, memory_id: str, hard: bool = False) -> bool:
        """Archive (soft) or delete (hard) a memory."""
        memory = self.get(memory_id)
        if not memory:
            return False

        if hard:
            self._sm.delete("memories", memory_id)
        else:
            self._sm.update("memories", memory_id, {"status": MemoryStatus.ARCHIVED.value})
        return True

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        record = self._sm.get("memories", memory_id)
        if record:
            return self._dict_to_memory(record)
        return None

    def link(self, source_id: str, target_id: str) -> bool:
        """Link two related memories."""
        source_mem = self.get(source_id)
        target_mem = self.get(target_id)

        if not source_mem or not target_mem:
            return False

        if target_id not in source_mem.related:
            source_mem.related.append(target_id)
            self._sm.update("memories", source_id, {
                "metadata": {"context": source_mem.context, "outcome": source_mem.outcome, "related": source_mem.related},
            })

        if source_id not in target_mem.related:
            target_mem.related.append(source_id)
            self._sm.update("memories", target_id, {
                "metadata": {"context": target_mem.context, "outcome": target_mem.outcome, "related": target_mem.related},
            })

        return True

    # ==================== Decay Management ====================

    def run_decay(self) -> Dict[str, int]:
        """Run decay process."""
        archived = 0
        deleted = 0

        for record in self._sm.list("memories"):
            memory = self._dict_to_memory(record)
            if not memory:
                continue

            if memory.status == MemoryStatus.ACTIVE.value:
                if self._should_archive(memory):
                    self._sm.update("memories", memory.id, {"status": MemoryStatus.ARCHIVED.value})
                    archived += 1

            elif memory.status == MemoryStatus.DECAYED.value:
                decayed_at = datetime.fromisoformat(memory.accessed.replace("Z", "+00:00"))
                if datetime.now(decayed_at.tzinfo) - decayed_at > timedelta(days=7):
                    self._sm.delete("memories", memory.id)
                    deleted += 1

            elif memory.status == MemoryStatus.ARCHIVED.value:
                accessed_at = datetime.fromisoformat(memory.accessed.replace("Z", "+00:00"))
                if datetime.now(accessed_at.tzinfo) - accessed_at > timedelta(days=30):
                    self._sm.update("memories", memory.id, {"status": MemoryStatus.DECAYED.value})

        return {"archived": archived, "deleted": deleted}

    def _should_archive(self, memory: Memory) -> bool:
        """Check if memory should be archived based on TTL and access."""
        if memory.ttl_days is None:
            return False

        importance_mult = max(0.5, memory.importance / 5.0)  # 2→0.5, 5→1.0, 8→1.6
        access_boost = 1 + (memory.access_count * 0.1)
        effective_ttl = memory.ttl_days * importance_mult * access_boost

        created_at = datetime.fromisoformat(memory.created.replace("Z", "+00:00"))
        age_days = (datetime.now(created_at.tzinfo) - created_at).days
        return age_days > effective_ttl

    def _update_access(self, memory: Memory):
        """Update access timestamp and count."""
        memory.accessed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        memory.access_count += 1
        self._sm.update("memories", memory.id, {
            "accessed_at": memory.accessed,
            "access_count": memory.access_count,
        })

    # ==================== Utility ====================

    def list_projects(self) -> List[str]:
        """List all projects with memories."""
        projects = set()
        for record in self._sm.list("memories"):
            proj = record.get("project")
            if proj:
                projects.add(proj)
        return sorted(projects)

    def stats(self) -> Dict:
        """Get memory statistics."""
        stats = {
            "total": 0,
            "by_type": {},
            "by_status": {},
            "by_tag": {},
        }

        for record in self._sm.list("memories"):
            memory = self._dict_to_memory(record)
            if not memory:
                continue
            stats["total"] += 1
            stats["by_type"][memory.type] = stats["by_type"].get(memory.type, 0) + 1
            stats["by_status"][memory.status] = stats["by_status"].get(memory.status, 0) + 1
            for tag in memory.tags:
                stats["by_tag"][tag] = stats["by_tag"].get(tag, 0) + 1

        return stats


# ==================== Convenience Functions ====================

_store: Optional[MemoryStore] = None


def get_store(project: Optional[str] = None) -> MemoryStore:
    """Get or create the memory store."""
    global _store
    if _store is None or (project and _store.project != project):
        _store = MemoryStore(project)
    return _store


def store(
    title: str,
    content: str,
    type: MemoryType = MemoryType.EPISODIC,
    **kwargs
) -> Memory:
    """Store a new memory (convenience function)."""
    return get_store().store(title, content, type, **kwargs)


def recall(
    query: Optional[str] = None,
    **kwargs
) -> List[Memory]:
    """Recall memories (convenience function)."""
    return get_store().recall(query, **kwargs)


def search(pattern: str, **kwargs) -> List[Memory]:
    """Search memories (convenience function)."""
    return get_store().search(pattern, **kwargs)


def forget(memory_id: str, hard: bool = False) -> bool:
    """Forget a memory (convenience function)."""
    return get_store().forget(memory_id, hard)


# ==================== CLI ====================

def main():
    """CLI interface for memory operations."""
    import argparse

    parser = argparse.ArgumentParser(description="Wicked Memory Operations")
    parser.add_argument("operation", choices=["store", "recall", "search", "search-all", "forget", "stats", "decay", "review", "get", "update", "archive", "delete"],
                       help="Operation to perform")
    parser.add_argument("--title", "-t", help="Memory title")
    parser.add_argument("--content", "-c", help="Memory content")
    parser.add_argument("--type", choices=["episodic", "procedural", "decision", "preference", "working"],
                       help="Memory type (default: episodic for store operation)")
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--pattern", "-p", help="Ripgrep pattern")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--id", help="Memory ID")
    parser.add_argument("--hard", action="store_true", help="Hard delete")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--limit", type=int, default=10, help="Result limit")
    parser.add_argument("--stale", action="store_true", help="Show only stale memories (30+ days)")
    parser.add_argument("--importance", choices=["low", "medium", "high"],
                        help="Importance level (low=2, medium=5, high=8)")
    parser.add_argument("--summary", help="Memory summary")
    parser.add_argument("--all-projects", action="store_true", help="Search ALL projects")

    args = parser.parse_args()

    ms = MemoryStore(args.project)

    if args.operation == "store":
        if not args.title or not args.content:
            print("Error: --title and --content required")
            return 1

        mem_type = MemoryType(args.type or "episodic")
        tags = args.tags.split(",") if args.tags else []
        _importance_map = {"low": Importance.LOW, "medium": Importance.MEDIUM, "high": Importance.HIGH}
        importance = _importance_map.get(args.importance, Importance.MEDIUM)

        memory = ms.store(
            title=args.title,
            content=args.content,
            type=mem_type,
            tags=tags,
            importance=importance,
            summary=args.summary,
        )
        print(f"Stored: {memory.id}")

    elif args.operation == "recall":
        tags = args.tags.split(",") if args.tags else None
        mem_type = MemoryType(args.type) if args.type else None
        memories = ms.recall(
            query=args.query,
            tags=tags,
            type=mem_type,
            limit=args.limit,
            all_projects=args.all_projects,
        )
        for m in memories:
            project_label = f" [{m.project}]" if m.project else ""
            print(f"[{m.id}] {m.type}{project_label}: {m.title}")
            print(f"  Tags: {', '.join(m.tags)}")
            print(f"  Summary: {m.summary[:100]}...")
            print()

    elif args.operation == "search-all":
        if not args.query:
            print("Error: --query required for search-all")
            return 1

        results = ms.search_all(args.query, limit=args.limit)
        print(json.dumps(results, indent=2))

    elif args.operation == "search":
        if not args.pattern:
            print("Error: --pattern required")
            return 1

        memories = ms.search(args.pattern)
        for m in memories:
            print(f"[{m.id}] {m.type}: {m.title}")

    elif args.operation == "forget":
        if not args.id:
            print("Error: --id required")
            return 1

        if ms.forget(args.id, hard=args.hard):
            print(f"Forgotten: {args.id}")
        else:
            print(f"Not found: {args.id}")
            return 1

    elif args.operation == "stats":
        stats = ms.stats()
        print(json.dumps(stats, indent=2))

    elif args.operation == "decay":
        result = ms.run_decay()
        print(f"Archived: {result['archived']}, Deleted: {result['deleted']}")

    elif args.operation == "review":
        from datetime import datetime, timezone, timedelta

        all_memories = ms.recall(
            type=MemoryType(args.type) if args.type else None,
            limit=1000,
            include_archived=False,
            all_projects=not args.project,
        )

        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(days=30)

        memories_data = []
        for m in all_memories:
            try:
                created = datetime.fromisoformat(m.created.replace("Z", "+00:00"))
                accessed = datetime.fromisoformat(m.accessed.replace("Z", "+00:00"))
                age_days = (now - created).days
                is_stale = accessed < stale_threshold

                if args.stale and not is_stale:
                    continue

                memories_data.append({
                    "id": m.id,
                    "type": m.type,
                    "title": m.title,
                    "summary": m.summary[:100],
                    "tags": m.tags,
                    "age_days": age_days,
                    "access_count": m.access_count,
                    "is_stale": is_stale,
                    "importance": m.importance
                })
            except:
                continue

        by_type = {}
        for m in memories_data:
            t = m["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(m)

        for t in by_type:
            by_type[t].sort(key=lambda x: x["access_count"], reverse=True)

        print(json.dumps({
            "project": args.project or ms.project,
            "total": len(memories_data),
            "by_type": by_type
        }, indent=2))

    elif args.operation == "get":
        if not args.id:
            print("Error: --id required")
            return 1

        memory = ms.get(args.id)
        if memory:
            print(json.dumps({
                "id": memory.id,
                "type": memory.type,
                "title": memory.title,
                "summary": memory.summary,
                "content": memory.content,
                "context": memory.context,
                "outcome": memory.outcome,
                "tags": memory.tags,
                "importance": memory.importance,
                "status": memory.status,
                "created": memory.created,
                "accessed": memory.accessed,
                "access_count": memory.access_count,
                "project": memory.project,
                "source": memory.source
            }, indent=2))
        else:
            print(f"Not found: {args.id}")
            return 1

    elif args.operation == "update":
        if not args.id:
            print("Error: --id required")
            return 1

        memory = ms.get(args.id)
        if not memory:
            print(f"Not found: {args.id}")
            return 1

        diff = {}
        if args.title:
            diff["title"] = args.title
        if args.summary:
            diff["summary"] = args.summary
        if args.tags:
            diff["tags"] = args.tags.split(",")
        if args.importance:
            diff["importance"] = _IMPORTANCE_FROM_STR.get(args.importance, 5)

        ms._sm.update("memories", args.id, diff)
        print(f"Updated: {args.id}")

    elif args.operation == "archive":
        if not args.id:
            print("Error: --id required")
            return 1

        if ms.forget(args.id, hard=False):
            print(f"Archived: {args.id}")
        else:
            print(f"Not found: {args.id}")
            return 1

    elif args.operation == "delete":
        if not args.id:
            print("Error: --id required")
            return 1

        if ms.forget(args.id, hard=True):
            print(f"Deleted: {args.id}")
        else:
            print(f"Not found: {args.id}")
            return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
