#!/usr/bin/env python3
"""
_domain_store.py — DomainStore: per-domain local JSON storage with integration-discovery routing.

Replaces StorageManager as the standard storage interface for domain scripts.
Local JSON is the canonical store. External tools (Linear MCP, Jira MCP, Notion MCP, etc.)
are resolved via integration-discovery and used when configured and authenticated.

Storage paths (unchanged from StorageManager):
    Local:  ~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json

CRUD API is identical to StorageManager — callers can swap the import with no other
changes required.

Usage:
    from _domain_store import DomainStore

    ds = DomainStore("wicked-mem")
    items = ds.list("memories", project="my-project")
    item  = ds.get("memories", "abc123")
    new   = ds.create("memories", {"title": "...", "content": "..."})
    ds.update("memories", "abc123", {"title": "new title"})
    ds.delete("memories", "abc123")

    # For truly ephemeral files (caches, temp session state) only:
    from _domain_store import get_local_path
    cache_dir = get_local_path("wicked-smaht", "cache", "context7")

hook_mode=True:
    When True, skips integration-discovery entirely and operates local-only.
    Use this from hook scripts to stay within the 5s timing budget.

_skip_discovery=True:
    When True, skips integration-discovery. Used internally by the integration
    resolver when it writes preferences via MemoryStore to avoid circular init.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (shared with _storage.py — same local JSON location)
# ---------------------------------------------------------------------------

try:
    from _paths import get_project_root
    _LOCAL_ROOT = get_project_root()
except ImportError:
    _LOCAL_ROOT = Path.home() / ".something-wicked" / "wicked-garden" / "local"

# ---------------------------------------------------------------------------
# Domain MCP Pattern Registry
#
# Maps domain names to keyword patterns that identify compatible MCP servers.
# Used by integration-discovery to find external tools for each domain.
# Matching is case-insensitive substring search.
# Domains not listed here skip discovery and go directly to local JSON.
# ---------------------------------------------------------------------------

DOMAIN_MCP_PATTERNS: dict[str, list[str]] = {
    "wicked-kanban": [
        "jira", "linear", "asana", "github", "gitlab",
        "trello", "monday", "clickup", "rally", "ado",
        "azure-devops", "project", "issue",
    ],
    "wicked-mem": [
        "notion", "confluence", "obsidian", "memory",
        "knowledge", "wiki", "coda",
    ],
    "wicked-jam": [
        "miro", "figjam", "mural", "whiteboard",
        "figma", "brainstorm",
    ],
    "wicked-crew": ["jira", "linear", "github", "rally", "ado", "azure-devops", "project"],
    "wicked-search": ["elasticsearch", "algolia", "typesense", "search"],
    # wicked-smaht, wicked-qe, wicked-patch: local-only (no MCP patterns)
}


# ---------------------------------------------------------------------------
# Public path helpers — delegate to _paths.py
# ---------------------------------------------------------------------------


def get_local_path(domain: str, *subpath: str) -> Path:
    """Delegate to _paths.get_local_path — see _paths.py for docs.

    Returns a directory path under the wicked-garden local root,
    creating it if it does not exist.

    Example:
        get_local_path("wicked-crew", "projects")
        # → ~/.something-wicked/wicked-garden/local/wicked-crew/projects/
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from _paths import get_local_path as _glp
        return _glp(domain, *subpath)
    except ImportError:
        # Inline fallback if _paths.py is not present
        p = _LOCAL_ROOT / domain
        for part in subpath:
            p = p / part
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_local_file(domain: str, *subpath: str) -> Path:
    """Delegate to _paths.get_local_file — see _paths.py for docs.

    Returns a file path under the wicked-garden local root.
    Parent directories are created automatically. Does not create the file.

    Example:
        get_local_file("wicked-search", "unified_search.db")
        # → ~/.something-wicked/wicked-garden/local/wicked-search/unified_search.db
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from _paths import get_local_file as _glf
        return _glf(domain, *subpath)
    except ImportError:
        # Inline fallback if _paths.py is not present
        p = _LOCAL_ROOT / domain
        for part in subpath:
            p = p / part
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


# ---------------------------------------------------------------------------
# DomainStore
# ---------------------------------------------------------------------------


class DomainStore:
    """Per-domain local JSON storage with integration-discovery routing.

    Initialization (once per domain per script invocation):
        1. Load cached tool selection from SessionState.integration_tools[domain]
        2. If no cache: run _init_routing() to discover + resolve external tool
        3. Store result back to SessionState for the session lifetime

    CRUD API (same surface as StorageManager):
        list(source, **params)       -> list[dict]
        get(source, id)              -> dict | None
        create(source, payload)      -> dict
        update(source, id, diff)     -> dict | None
        delete(source, id)           -> bool
        search(source, q, **params)  -> list[dict]  (delegates to list with q in params)

    Routing:
        - If an external tool is resolved: delegate to ExternalToolAdapter first,
          fall back to local JSON on None return.
        - hook_mode=True or _skip_discovery=True: local JSON only, no discovery.
        - Domains not in DOMAIN_MCP_PATTERNS: local JSON only.
    """

    def __init__(
        self,
        domain: str,
        *,
        hook_mode: bool = False,
        _skip_discovery: bool = False,
    ) -> None:
        """
        Args:
            domain:          Plugin domain, e.g. "wicked-mem", "wicked-kanban".
            hook_mode:       Pass True from hook scripts. Skips integration-discovery
                             to stay within the 5s hook timing budget.
            _skip_discovery: Internal flag. Pass True from integration resolver when
                             creating a MemoryStore to prevent circular initialization.
        """
        self._domain = domain
        self._hook_mode = hook_mode
        self._skip_discovery = _skip_discovery
        self._external: Any | None = None  # ExternalToolAdapter, wired in Task 1.4
        self._init_routing()

    # ------------------------------------------------------------------
    # Routing initialization
    # ------------------------------------------------------------------

    def _init_routing(self) -> None:
        """Load or discover the external tool for this domain.

        1. Skip entirely when hook_mode or _skip_discovery is True.
        2. Check SessionState.integration_tools[domain] cache first (<5ms).
        3. If cache miss: call resolve_tool() — runs discovery.
        4. Cache the result in SessionState for the session lifetime.
        5. If resolved tool != "local" and != None: instantiate adapter via
           from_tool_name() and assign to self._external.

        Imports are lazy (inside this method) to avoid circular imports at
        module load time. Any import failure causes silent local-only fallback.
        """
        # hooks and circular-init callers always go local
        if self._hook_mode or self._skip_discovery:
            return

        # Domains not in the pattern registry skip discovery entirely
        if self._domain not in DOMAIN_MCP_PATTERNS:
            return

        tool_name: str | None = None

        # ── Step 1: check session cache ──────────────────────────────────────
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from _session import SessionState

            state = SessionState.load()
            cached = (state.integration_tools or {}).get(self._domain)
            if cached is not None:
                # Cache hit — use the stored value directly
                tool_name = cached if cached != "local" else None
            else:
                # ── Step 2: cache miss — run discovery ───────────────────────
                tool_name = self._discover_tool()

                # ── Step 3: cache in SessionState ────────────────────────────
                tools = dict(state.integration_tools or {})
                tools[self._domain] = tool_name if tool_name else "local"
                state.update(integration_tools=tools)
        except Exception:
            # SessionState unavailable (e.g. no TMPDIR, corrupted file) —
            # run discovery without caching; fail open on any error.
            try:
                tool_name = self._discover_tool()
            except Exception:
                tool_name = None

        # ── Step 4: instantiate adapter ──────────────────────────────────────
        if tool_name and tool_name != "local":
            try:
                from _adapters import from_tool_name

                self._external = from_tool_name(tool_name)
            except Exception:
                self._external = None  # import failure → local only

    def _discover_tool(self) -> str | None:
        """Run integration-resolver discovery for this domain.

        Returns the tool name string or None for local-only. Imported lazily
        to avoid circular imports (_integration_resolver imports _domain_store).
        """
        try:
            from _integration_resolver import resolve_tool

            return resolve_tool(self._domain, hook_mode=False)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list(self, source: str, **params) -> list[dict]:
        """List records for a source, with optional filter params.

        Returns:
            List of record dicts. Empty list on any error.

        Delegates to external tool first (when resolved); falls back to local JSON.
        """
        if self._external is not None:
            try:
                result = self._external.list(source, **params)
                if result is not None:
                    return result
            except Exception:
                pass  # fall through to local

        return self._local_list(source, params)

    def search(self, source: str, q: str, **params) -> list[dict]:
        """Search records — delegates to list() with q in params.

        Falls back to local token-based search (title, content, summary, description).

        Args:
            source: Source name (e.g. "memories")
            q:      Search query string
            **params: Additional filter params (type, project, etc.)
        """
        return self.list(source, q=q, **params)

    def get(self, source: str, id: str) -> dict | None:
        """Fetch a single record by ID.

        Returns:
            Record dict, or None if not found.
        """
        if self._external is not None:
            try:
                result = self._external.get(source, id)
                if result is not None:
                    return result
            except Exception:
                pass  # fall through to local

        return self._local_get(source, id)

    # ------------------------------------------------------------------
    # Event emission (fire-and-forget)
    # ------------------------------------------------------------------

    def _emit_event(self, action: str, source: str, record_id: str | None = None,
                    payload: dict | None = None, tags: list[str] | None = None) -> None:
        """Emit an event to the unified event log. Never raises.

        Emits only safe metadata (id, timestamps, action) — not the full record
        payload, to avoid replicating sensitive data into the FTS-indexed event log.
        Callers needing full payload in events should call EventStore.append() directly.
        """
        try:
            from _event_store import EventStore
            EventStore.ensure_schema()

            # Auto-resolve project_id from session state
            project_id = None
            try:
                from _session import SessionState
                state = SessionState.load()
                project_id = getattr(state, "active_project", None)
            except Exception:
                pass

            # Emit safe metadata only — strip sensitive fields from payload
            safe_payload = None
            if payload is not None:
                safe_payload = {
                    k: v for k, v in payload.items()
                    if k in ("id", "name", "title", "type", "status", "phase",
                             "created_at", "updated_at", "deleted_at", "tags",
                             "complexity_score", "signals_detected")
                }

            EventStore.append(
                domain=self._domain,
                action=f"{source}.{action}",
                source=source,
                record_id=record_id,
                payload=safe_payload if safe_payload else None,
                project_id=project_id,
                tags=tags,
            )
        except Exception:
            pass  # fire-and-forget — never break domain operations

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, source: str, payload: dict) -> dict | None:
        """Create a new record.

        Returns:
            Created record dict, or None on failure.

        When an external tool is resolved, delegates to it first. On success,
        also writes to local JSON (external tool is the ID authority when used).
        Falls back to local JSON with auto-generated UUID on any failure.
        """
        record = dict(payload)
        record.setdefault("created_at", _now())
        record.setdefault("updated_at", _now())

        if self._external is not None:
            try:
                result = self._external.create(source, record)
                if result is not None:
                    # Use external-tool-assigned ID as canonical ID
                    if result.get("id"):
                        record["id"] = result["id"]
                    elif "id" not in record:
                        record["id"] = str(uuid.uuid4())
                    self._local_write(source, record["id"], record)
                    self._emit_event("created", source, record["id"], record)
                    return record
            except Exception:
                pass  # fall through to local

        # Local path: generate UUID and write
        if "id" not in record:
            record["id"] = str(uuid.uuid4())
        self._local_write(source, record["id"], record)
        self._emit_event("created", source, record["id"], record)
        return record

    def update(self, source: str, id: str, diff: dict) -> dict | None:
        """Patch an existing record with the fields in diff.

        Returns:
            Updated record dict, or None if not found.
        """
        if self._external is not None:
            try:
                result = self._external.update(source, id, diff)
                if result is not None:
                    # Also update local copy
                    existing = self._local_get(source, id)
                    if existing:
                        existing.update(diff)
                        existing["updated_at"] = _now()
                        self._local_write(source, id, existing)
                    return result
            except Exception:
                pass  # fall through to local

        # Local path: read-modify-write
        existing = self._local_get(source, id)
        if existing is None:
            return None

        existing.update(diff)
        existing["updated_at"] = _now()
        self._local_write(source, id, existing)
        self._emit_event("updated", source, id, diff)
        return existing

    def delete(self, source: str, id: str) -> bool:
        """Delete a record (soft-delete: sets deleted=True locally).

        Returns:
            True if the record was found and removed/marked deleted.
        """
        if self._external is not None:
            try:
                result = self._external.delete(source, id)
                if result is not None:
                    # Also soft-delete locally
                    existing = self._local_get(source, id)
                    if existing:
                        existing["deleted"] = True
                        existing["deleted_at"] = _now()
                        self._local_write(source, id, existing)
                    return bool(result)
            except Exception:
                pass  # fall through to local

        # Local path: soft-delete
        existing = self._local_get(source, id)
        if existing is None:
            return False

        existing["deleted"] = True
        existing["deleted_at"] = _now()
        self._local_write(source, id, existing)
        self._emit_event("deleted", source, id)
        return True

    # ------------------------------------------------------------------
    # Private: local file operations
    # (adapted from StorageManager._local_* methods, _storage.py lines 590-651)
    # ------------------------------------------------------------------

    def _local_dir(self, source: str) -> Path:
        return _LOCAL_ROOT / self._domain / source

    def _local_file(self, source: str, id: str) -> Path:
        return self._local_dir(source) / f"{id}.json"

    def _local_list(self, source: str, params: dict) -> list[dict]:
        """Scan local JSON files and return non-deleted records matching params."""
        source_dir = self._local_dir(source)
        if not source_dir.exists():
            return []

        records: list[dict] = []
        for json_file in sorted(source_dir.glob("*.json")):
            try:
                record = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            # Skip soft-deleted records
            if record.get("deleted"):
                continue

            # Apply simple equality filters from params
            if not _matches_params(record, params):
                continue

            records.append(record)

        return records

    def _local_get(self, source: str, id: str) -> dict | None:
        """Read a single local JSON file by ID."""
        path = self._local_file(source, id)

        if path.exists():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("deleted"):
                    return None
                return record
            except (json.JSONDecodeError, OSError):
                return None

        return None

    def _local_write(self, source: str, id: str, record: dict) -> None:
        """Atomically write a record to its local JSON file."""
        path = self._local_file(source, id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            print(
                f"[wicked-garden] Local write failed for {source}/{id}: {exc}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matches_params(record: dict, params: dict) -> bool:
    """Filter for local list queries.

    Supports exact equality for most fields plus substring search for the
    special ``q`` parameter (searches across title, content, summary,
    description).

    Copied from _storage.py to avoid import dependency.
    """
    for key, value in params.items():
        if key == "q":
            # Token-based search across text fields (all tokens must match)
            text_fields = [
                str(record.get(f, ""))
                for f in ("title", "content", "summary", "description")
            ]
            # Include tags (may be a list)
            tags_val = record.get("tags", [])
            if isinstance(tags_val, list):
                text_fields.append(" ".join(str(t) for t in tags_val))
            elif tags_val:
                text_fields.append(str(tags_val))
            # Include search_tags if present
            search_tags_val = record.get("search_tags", "")
            if search_tags_val:
                text_fields.append(str(search_tags_val))
            searchable = " ".join(text_fields).lower()
            tokens = str(value).lower().split()
            if not all(tok in searchable for tok in tokens):
                return False
        elif record.get(key) != value:
            return False
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
