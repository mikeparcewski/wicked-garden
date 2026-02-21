"""
Wicked Memory - Natural Memory System

Extends the cache infrastructure with cognitive memory types:
- Episodic: What happened, what we learned
- Procedural: How to do things, patterns
- Decision: Choices made and rationale
- Preference: User/agent preferences
- Working: Current session context

Storage Structure:
    ~/.something-wicked/wicked-mem/
    ├── config.yaml
    ├── core/                    # Global memories
    │   ├── preferences/
    │   ├── learnings/
    │   └── agents/
    └── projects/               # Project-specific
        └── {project}/
            ├── episodic/
            ├── procedural/
            ├── decisions/
            └── working/
"""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict


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
    """Memory importance levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Scope(Enum):
    """Memory scope."""
    PROJECT = "project"
    GLOBAL = "global"


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
    context: str  # When is this relevant
    outcome: Optional[str] = None

    # Authorship
    author: str = "claude"  # user, claude, or agent
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    shared_with: List[str] = field(default_factory=lambda: ["all"])

    # Lifecycle
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    accessed: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    access_count: int = 0
    accessed_by: List[str] = field(default_factory=list)
    ttl_days: Optional[int] = None
    importance: str = "medium"  # Importance value
    status: str = "active"  # MemoryStatus value

    # Search & Linking
    tags: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)

    # Scope
    scope: str = "project"  # Scope value
    project: Optional[str] = None

    # Source
    source: str = "manual"  # auto, manual, hook
    session_id: Optional[str] = None


def generate_id() -> str:
    """Generate a unique memory ID."""
    return f"mem_{uuid.uuid4().hex[:12]}"


class MemoryStore:
    """Core memory storage and operations."""

    def __init__(self, project: Optional[str] = None):
        """
        Initialize memory store.

        Args:
            project: Project name for project-scoped memories.
                    If None, will try to detect from current directory.
        """
        self.project = project or self._detect_project()
        self.base_path = Path.home() / ".something-wicked" / "wicked-mem"
        self._ensure_structure()

    def _detect_project(self) -> Optional[str]:
        """Detect project name from current directory."""
        cwd = Path.cwd()
        # Look for common project indicators
        if (cwd / ".git").exists():
            return cwd.name
        if (cwd / "package.json").exists():
            return cwd.name
        if (cwd / "pyproject.toml").exists():
            return cwd.name
        return None

    def _ensure_structure(self):
        """Create directory structure if needed."""
        # Core directories
        (self.base_path / "core" / "preferences").mkdir(parents=True, exist_ok=True)
        (self.base_path / "core" / "learnings").mkdir(parents=True, exist_ok=True)
        (self.base_path / "core" / "agents").mkdir(parents=True, exist_ok=True)

        # Project directories
        if self.project:
            project_path = self.base_path / "projects" / self.project
            for subdir in ["episodic", "procedural", "decisions", "working"]:
                (project_path / subdir).mkdir(parents=True, exist_ok=True)

    def _get_path(self, memory: Memory) -> Path:
        """Get file path for a memory."""
        scope = Scope(memory.scope)
        mem_type = MemoryType(memory.type)

        if scope == Scope.GLOBAL:
            if mem_type == MemoryType.PREFERENCE:
                return self.base_path / "core" / "preferences" / f"{memory.id}.md"
            else:
                return self.base_path / "core" / "learnings" / f"{memory.id}.md"
        else:
            # Project scope
            project = memory.project or self.project or "default"
            type_dir = {
                MemoryType.EPISODIC: "episodic",
                MemoryType.PROCEDURAL: "procedural",
                MemoryType.DECISION: "decisions",
                MemoryType.PREFERENCE: "preferences",
                MemoryType.WORKING: "working",
            }.get(mem_type, "episodic")

            return self.base_path / "projects" / project / type_dir / f"{memory.id}.md"

    def _to_markdown(self, memory: Memory) -> str:
        """Convert memory to markdown with frontmatter."""
        # Build frontmatter
        fm = {
            "id": memory.id,
            "type": memory.type,
            "created": memory.created,
            "accessed": memory.accessed,
            "access_count": memory.access_count,
            "accessed_by": memory.accessed_by,
            "author": memory.author,
            "importance": memory.importance,
            "status": memory.status,
            "tags": memory.tags,
            "scope": memory.scope,
            "source": memory.source,
        }

        # Optional fields
        if memory.agent_id:
            fm["agent_id"] = memory.agent_id
        if memory.agent_type:
            fm["agent_type"] = memory.agent_type
        if memory.shared_with != ["all"]:
            fm["shared_with"] = memory.shared_with
        if memory.ttl_days:
            fm["ttl_days"] = memory.ttl_days
        if memory.related:
            fm["related"] = memory.related
        if memory.project:
            fm["project"] = memory.project
        if memory.session_id:
            fm["session_id"] = memory.session_id

        # Build markdown
        lines = ["---"]
        for key, value in fm.items():
            if isinstance(value, list):
                lines.append(f"{key}: {json.dumps(value)}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {memory.title}")
        lines.append("")
        lines.append("## Summary")
        lines.append(memory.summary)
        lines.append("")
        lines.append("## Content")
        lines.append(memory.content)
        lines.append("")
        lines.append("## Context")
        lines.append(memory.context)

        if memory.outcome:
            lines.append("")
            lines.append("## Outcome")
            lines.append(memory.outcome)

        return "\n".join(lines)

    def _from_markdown(self, path: Path) -> Optional[Memory]:
        """Parse memory from markdown file."""
        if not path.exists():
            return None

        content = path.read_text(encoding="utf-8")

        # Parse frontmatter
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        fm_text = parts[1].strip()
        body = parts[2].strip()

        # Parse frontmatter (simple YAML-like)
        fm = {}
        for line in fm_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                # Try to parse JSON values (lists)
                if value.startswith("["):
                    try:
                        value = json.loads(value)
                    except:
                        pass
                fm[key] = value

        # Parse body sections
        sections = {}
        current_section = None
        current_content = []

        for line in body.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = line[3:].strip().lower()
                current_content = []
            elif line.startswith("# "):
                fm["title"] = line[2:].strip()
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        # Convert access_count to int
        access_count = fm.get("access_count", 0)
        if isinstance(access_count, str):
            access_count = int(access_count)

        # Convert ttl_days to int if present
        ttl_days = fm.get("ttl_days")
        if isinstance(ttl_days, str):
            ttl_days = int(ttl_days)

        # Build Memory object
        return Memory(
            id=fm.get("id", generate_id()),
            type=fm.get("type", "episodic"),
            title=fm.get("title", "Untitled"),
            summary=sections.get("summary", ""),
            content=sections.get("content", ""),
            context=sections.get("context", ""),
            outcome=sections.get("outcome"),
            author=fm.get("author", "claude"),
            agent_id=fm.get("agent_id"),
            agent_type=fm.get("agent_type"),
            shared_with=fm.get("shared_with", ["all"]),
            created=fm.get("created", datetime.now(timezone.utc).isoformat() + "Z"),
            accessed=fm.get("accessed", datetime.now(timezone.utc).isoformat() + "Z"),
            access_count=access_count,
            accessed_by=fm.get("accessed_by", []),
            ttl_days=ttl_days,
            importance=fm.get("importance", "medium"),
            status=fm.get("status", "active"),
            tags=fm.get("tags", []),
            related=fm.get("related", []),
            scope=fm.get("scope", "project"),
            project=fm.get("project"),
            source=fm.get("source", "manual"),
            session_id=fm.get("session_id"),
        )

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
        scope: Scope = Scope.PROJECT,
        author: str = "claude",
        agent_id: Optional[str] = None,
        source: str = "manual",
        session_id: Optional[str] = None,
    ) -> Memory:
        """
        Store a new memory.

        Returns:
            The created Memory object
        """
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
            scope=scope.value,
            project=self.project if scope == Scope.PROJECT else None,
            tags=tags or [],
            ttl_days=DEFAULT_TTLS.get(type),
            source=source,
            session_id=session_id,
        )

        path = self._get_path(memory)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._to_markdown(memory), encoding="utf-8")

        return memory

    def recall(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        limit: int = 10,
        include_archived: bool = False,
        all_projects: bool = False,
    ) -> List[Memory]:
        """
        Recall memories matching criteria.

        Uses ripgrep for pattern matching.

        Args:
            query: Text to search for in memory content
            tags: Filter by tags (any match)
            type: Filter by memory type
            scope: Filter by scope (PROJECT or GLOBAL)
            limit: Max results to return
            include_archived: Include archived memories
            all_projects: Search ALL projects, not just current (like kanban search)
        """
        memories = []
        seen_ids = set()  # Deduplication like kanban

        # Determine search paths
        search_paths = []
        if scope == Scope.GLOBAL or scope is None:
            search_paths.append(self.base_path / "core")

        if scope == Scope.PROJECT or scope is None:
            projects_path = self.base_path / "projects"
            if all_projects and projects_path.exists():
                # Search ALL projects (like kanban does)
                for project_dir in projects_path.iterdir():
                    if project_dir.is_dir():
                        search_paths.append(project_dir)
            elif self.project:
                # Just current project
                search_paths.append(projects_path / self.project)

        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Use ripgrep if we have a query
            if query:
                matches = self._ripgrep_search(query, search_path)
                for match_path in matches:
                    memory = self._from_markdown(Path(match_path))
                    if memory and memory.id not in seen_ids:
                        seen_ids.add(memory.id)
                        memories.append(memory)
            else:
                # List all memories in path
                for md_file in search_path.rglob("*.md"):
                    memory = self._from_markdown(md_file)
                    if memory and memory.id not in seen_ids:
                        seen_ids.add(memory.id)
                        memories.append(memory)

        # Filter by type
        if type:
            memories = [m for m in memories if m.type == type.value]

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

    def search(self, pattern: str, path: Optional[str] = None) -> List[Memory]:
        """
        Ripgrep-based pattern search across memories.

        Args:
            pattern: Regex pattern (e.g., "auth.*error")
            path: Optional subdirectory to search
        """
        search_path = self.base_path
        if path:
            search_path = self.base_path / path

        matches = self._ripgrep_search(pattern, search_path)
        memories = []

        for match_path in matches:
            memory = self._from_markdown(Path(match_path))
            if memory and memory.status == MemoryStatus.ACTIVE.value:
                self._update_access(memory)
                memories.append(memory)

        return memories

    def search_all(
        self,
        query: str,
        include_archived: bool = False,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search ALL memories across ALL projects with enriched results.

        Like kanban's search, this searches everywhere and returns
        structured results with project context and match type.

        Args:
            query: Search query (case-insensitive)
            include_archived: Include archived memories
            limit: Max results

        Returns:
            List of dicts with: id, title, type, project, match_type, tags, importance
        """
        results = []
        seen_ids = set()
        query_lower = query.lower()

        # Search all paths
        search_paths = [self.base_path / "core"]
        projects_path = self.base_path / "projects"
        if projects_path.exists():
            for project_dir in projects_path.iterdir():
                if project_dir.is_dir():
                    search_paths.append(project_dir)

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for md_file in search_path.rglob("*.md"):
                memory = self._from_markdown(md_file)
                if not memory or memory.id in seen_ids:
                    continue

                if not include_archived and memory.status != MemoryStatus.ACTIVE.value:
                    continue

                # Determine match type (where the query matched)
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

            if len(results) >= limit:
                break

        # Sort by importance (high first) then access count
        importance_order = {"high": 0, "medium": 1, "low": 2}
        results.sort(key=lambda r: (importance_order.get(r["importance"], 1), -r["access_count"]))

        return results[:limit]

    def forget(self, memory_id: str, hard: bool = False) -> bool:
        """
        Archive (soft) or delete (hard) a memory.
        """
        memory = self.get(memory_id)
        if not memory:
            return False

        path = self._get_path(memory)

        if hard:
            path.unlink(missing_ok=True)
        else:
            memory.status = MemoryStatus.ARCHIVED.value
            path.write_text(self._to_markdown(memory), encoding="utf-8")

        return True

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        # Search all paths for the memory
        for md_file in self.base_path.rglob(f"{memory_id}.md"):
            memory = self._from_markdown(md_file)
            if memory:
                return memory
        return None

    def link(self, source_id: str, target_id: str) -> bool:
        """Link two related memories."""
        source = self.get(source_id)
        target = self.get(target_id)

        if not source or not target:
            return False

        if target_id not in source.related:
            source.related.append(target_id)
            path = self._get_path(source)
            path.write_text(self._to_markdown(source), encoding="utf-8")

        if source_id not in target.related:
            target.related.append(source_id)
            path = self._get_path(target)
            path.write_text(self._to_markdown(target), encoding="utf-8")

        return True

    # ==================== Decay Management ====================

    def run_decay(self) -> Dict[str, int]:
        """
        Run decay process.

        Returns counts of archived and deleted memories.
        """
        archived = 0
        deleted = 0

        for md_file in self.base_path.rglob("*.md"):
            memory = self._from_markdown(md_file)
            if not memory:
                continue

            # Check if should decay
            if memory.status == MemoryStatus.ACTIVE.value:
                if self._should_archive(memory):
                    memory.status = MemoryStatus.ARCHIVED.value
                    md_file.write_text(self._to_markdown(memory), encoding="utf-8")
                    archived += 1

            elif memory.status == MemoryStatus.DECAYED.value:
                # Check if should delete (7 days after decay)
                decayed_at = datetime.fromisoformat(memory.accessed.replace("Z", "+00:00"))
                if datetime.now(decayed_at.tzinfo) - decayed_at > timedelta(days=7):
                    md_file.unlink()
                    deleted += 1

            elif memory.status == MemoryStatus.ARCHIVED.value:
                # Check if should mark as decayed (30 days after archive without access)
                accessed_at = datetime.fromisoformat(memory.accessed.replace("Z", "+00:00"))
                if datetime.now(accessed_at.tzinfo) - accessed_at > timedelta(days=30):
                    memory.status = MemoryStatus.DECAYED.value
                    md_file.write_text(self._to_markdown(memory), encoding="utf-8")

        return {"archived": archived, "deleted": deleted}

    def _should_archive(self, memory: Memory) -> bool:
        """Check if memory should be archived based on TTL and access."""
        if memory.ttl_days is None:
            return False  # Permanent

        # Calculate effective TTL with access boost
        importance_mult = {"low": 0.5, "medium": 1.0, "high": 2.0}.get(memory.importance, 1.0)
        access_boost = 1 + (memory.access_count * 0.1)
        effective_ttl = memory.ttl_days * importance_mult * access_boost

        created_at = datetime.fromisoformat(memory.created.replace("Z", "+00:00"))
        age_days = (datetime.now(created_at.tzinfo) - created_at).days

        return age_days > effective_ttl

    def _update_access(self, memory: Memory):
        """Update access timestamp and count."""
        memory.accessed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        memory.access_count += 1

        path = self._get_path(memory)
        if path.exists():
            path.write_text(self._to_markdown(memory), encoding="utf-8")

    # ==================== Search Helpers ====================

    def _ripgrep_search(self, pattern: str, search_path: Path) -> List[str]:
        """Search using ripgrep, with Python fallback."""
        try:
            result = subprocess.run(
                [
                    "rg",
                    "-l",              # Files only
                    "-i",              # Case insensitive
                    "--type", "md",    # Markdown files
                    pattern,
                    str(search_path)
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            # ripgrep found no matches
            if result.returncode == 1:
                return []
        except FileNotFoundError:
            # ripgrep not installed, fall back to Python search
            pass

        # Python fallback: simple case-insensitive search
        return self._python_search(pattern, search_path)

    def _python_search(self, pattern: str, search_path: Path) -> List[str]:
        """Fallback search using Python when ripgrep is not available."""
        import re
        matches = []
        pattern_lower = pattern.lower()

        # Handle regex patterns by compiling, or use simple contains for plain text
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            use_regex = True
        except re.error:
            use_regex = False

        for md_file in search_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if use_regex:
                    if regex.search(content):
                        matches.append(str(md_file))
                else:
                    if pattern_lower in content.lower():
                        matches.append(str(md_file))
            except (IOError, UnicodeDecodeError):
                continue

        return matches

    # ==================== Utility ====================

    def list_projects(self) -> List[str]:
        """List all projects with memories."""
        projects_path = self.base_path / "projects"
        if not projects_path.exists():
            return []
        return [p.name for p in projects_path.iterdir() if p.is_dir()]

    def stats(self) -> Dict:
        """Get memory statistics."""
        stats = {
            "total": 0,
            "by_type": {},
            "by_status": {},
            "by_scope": {"project": 0, "global": 0},
            "by_tag": {},
        }

        for md_file in self.base_path.rglob("*.md"):
            memory = self._from_markdown(md_file)
            if not memory:
                continue

            stats["total"] += 1
            stats["by_type"][memory.type] = stats["by_type"].get(memory.type, 0) + 1
            stats["by_status"][memory.status] = stats["by_status"].get(memory.status, 0) + 1
            stats["by_scope"][memory.scope] = stats["by_scope"].get(memory.scope, 0) + 1
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
    parser.add_argument("--importance", choices=["low", "medium", "high"], help="Importance level")
    parser.add_argument("--summary", help="Memory summary")
    parser.add_argument("--all-projects", action="store_true", help="Search ALL projects (like kanban)")

    args = parser.parse_args()

    ms = MemoryStore(args.project)

    if args.operation == "store":
        if not args.title or not args.content:
            print("Error: --title and --content required")
            return 1

        mem_type = MemoryType(args.type or "episodic")
        tags = args.tags.split(",") if args.tags else []
        importance = Importance(args.importance) if args.importance else Importance.MEDIUM

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
        # Get all memories grouped by type
        from datetime import datetime, timezone, timedelta

        all_memories = []
        for md_file in ms.base_path.rglob("*.md"):
            memory = ms._from_markdown(md_file)
            if memory and memory.status == MemoryStatus.ACTIVE.value:
                # Filter by project if specified
                if args.project and memory.project != args.project:
                    continue
                # Filter by type if specified
                if args.type and memory.type != args.type:
                    continue
                all_memories.append(memory)

        # Calculate age for each memory
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

        # Group by type
        by_type = {}
        for m in memories_data:
            t = m["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(m)

        # Sort each group by access count
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

        # Update fields
        if args.title:
            memory.title = args.title
        if args.summary:
            memory.summary = args.summary
        if args.tags:
            memory.tags = args.tags.split(",")
        if args.importance:
            memory.importance = args.importance

        # Save
        path = ms._get_path(memory)
        path.write_text(ms._to_markdown(memory), encoding="utf-8")
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
