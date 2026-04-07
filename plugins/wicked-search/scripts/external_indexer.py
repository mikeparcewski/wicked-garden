#!/usr/bin/env python3
"""
external_indexer.py — Index content from external plugin sources (MCP tools).

Allows wicked-search to ingest content from Confluence, Jira, Notion, or any
MCP-compatible plugin and make it searchable alongside local code and docs.

Source config is persisted as JSON. Indexed content is stored in the wicked-search
SQLite index with source attribution metadata.

Commands:
  list [--config PATH] [--json]
  add --name X --plugin Y --command Z [--args '{}'] [--content-type T]
      [--refresh-interval N] [--config PATH] [--json]
  remove --name X [--config PATH] [--json]
  refresh [--force] [--dry-run] [--config PATH] [--json]
  index-content --name X --content TEXT --doc-id ID [--config PATH] [--json]

Usage examples:
  external_indexer.py list --json
  external_indexer.py add --name "confluence-eng" --plugin "mcp-confluence" \
      --command "get_space_pages" --args '{"space_key": "ENG"}' --json
  external_indexer.py remove --name "confluence-eng" --json
  external_indexer.py refresh --dry-run --json
  external_indexer.py index-content --name "confluence-eng" \
      --content "# Intro..." --doc-id "ENG-001" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Shared imports
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from _logger import log as _ops_log
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False

    def _ops_log(domain, level, event, ok=True, ms=None, detail=None):  # type: ignore
        pass  # intentional: ops logger unavailable — no-op fallback


def _log(level: str, event: str, ok: bool = True, ms: float | None = None, detail: dict | None = None) -> None:
    _ops_log("search", level, event, ok=ok, ms=ms, detail=detail)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ExternalSourceConfig:
    """Configuration for a single external content source."""

    name: str
    """Unique identifier, e.g. 'confluence-engineering'."""

    plugin: str
    """MCP plugin name, e.g. 'mcp-confluence'.  Ignored for http sources."""

    fetch_command: str
    """MCP tool command to invoke, e.g. 'get_space_pages'.  Ignored for http sources."""

    fetch_args: Dict = field(default_factory=dict)
    """Arguments passed to the fetch command.  Ignored for http sources."""

    content_type: str = "document"
    """Content type: 'document', 'code', or 'ticket'."""

    refresh_interval_minutes: int = 60
    """How often to re-fetch content (minutes)."""

    enabled: bool = True
    """Whether this source is active."""

    last_fetched: Optional[str] = None
    """ISO-8601 timestamp of last successful fetch."""

    source_type: str = "mcp"
    """Source type: 'mcp' (agent-orchestrated) or 'http' (direct HTTP fetch)."""

    auth_env_var: Optional[str] = None
    """Name of the environment variable that holds the Bearer token.
    Only the variable *name* is stored here — the value is read at fetch time."""

    fetch_url_template: Optional[str] = None
    """URL to fetch for 'http' source types."""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExternalSourceConfig":
        return cls(
            name=data["name"],
            plugin=data["plugin"],
            fetch_command=data["fetch_command"],
            fetch_args=data.get("fetch_args", {}),
            content_type=data.get("content_type", "document"),
            refresh_interval_minutes=data.get("refresh_interval_minutes", 60),
            enabled=data.get("enabled", True),
            last_fetched=data.get("last_fetched"),
            source_type=data.get("source_type", "mcp"),
            auth_env_var=data.get("auth_env_var"),
            fetch_url_template=data.get("fetch_url_template"),
        )

    def is_stale(self) -> bool:
        """Return True if last_fetched is None or past refresh_interval_minutes."""
        if not self.last_fetched:
            return True
        try:
            last = datetime.fromisoformat(self.last_fetched.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_minutes = (now - last).total_seconds() / 60
            return age_minutes >= self.refresh_interval_minutes
        except (ValueError, TypeError):
            return True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY_SCHEMA_VERSION = "1.0"


class ExternalSourceRegistry:
    """Manages a JSON-persisted registry of external source configurations."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._sources: Dict[str, ExternalSourceConfig] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_config(self, path: Optional[str] = None) -> None:
        """Load configuration from a JSON file."""
        target = Path(path) if path else self.config_path
        if not target.exists():
            self._sources = {}
            self._loaded = True
            return

        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            sources_list = data.get("sources", [])
            self._sources = {
                s["name"]: ExternalSourceConfig.from_dict(s) for s in sources_list
            }
            self._loaded = True
        except (OSError, json.JSONDecodeError, KeyError) as e:
            _log("normal", "external_indexer.config.load_error", ok=False, detail={"error": str(e)})
            self._sources = {}
            self._loaded = True

    def save_config(self, path: Optional[str] = None) -> None:
        """Save configuration to a JSON file."""
        target = Path(path) if path else self.config_path
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": _REGISTRY_SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [s.to_dict() for s in self._sources.values()],
        }

        tmp_path = target.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.rename(target)
        except OSError as e:
            _log("normal", "external_indexer.config.save_error", ok=False, detail={"error": str(e)})
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass  # fail open: cleanup failure non-fatal
            raise

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_config()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_source(self, config: ExternalSourceConfig) -> None:
        """Add or replace a source by name."""
        self._ensure_loaded()
        self._sources[config.name] = config
        self.save_config()
        _log("verbose", "external_indexer.source.added", detail={"name": config.name})

    def remove_source(self, name: str) -> bool:
        """Remove a source by name. Returns True if it existed."""
        self._ensure_loaded()
        existed = name in self._sources
        if existed:
            del self._sources[name]
            self.save_config()
            _log("verbose", "external_indexer.source.removed", detail={"name": name})
        return existed

    def list_sources(self) -> List[ExternalSourceConfig]:
        """Return all configured sources."""
        self._ensure_loaded()
        return list(self._sources.values())

    def get_source(self, name: str) -> Optional[ExternalSourceConfig]:
        """Return a source by name, or None."""
        self._ensure_loaded()
        return self._sources.get(name)

    def update_last_fetched(self, name: str, timestamp: str) -> None:
        """Update last_fetched timestamp for a source."""
        self._ensure_loaded()
        if name in self._sources:
            self._sources[name].last_fetched = timestamp
            self.save_config()


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

class ExternalIndexer:
    """Fetches content from external sources and indexes it into wicked-search."""

    def __init__(self, registry: ExternalSourceRegistry, index_dir: Optional[str] = None):
        self.registry = registry
        self._index_dir = index_dir  # Optional override for testing

    def _get_index_dir(self) -> Path:
        """Resolve the wicked-search index directory."""
        if self._index_dir:
            return Path(self._index_dir)
        home = Path.home()
        return home / ".something-wicked" / "wicked-search"

    def _get_external_index_path(self) -> Path:
        """Path to the external sources JSONL index."""
        index_dir = self._get_index_dir()
        external_dir = index_dir / "external"
        external_dir.mkdir(parents=True, exist_ok=True)
        return external_dir / "index.jsonl"

    def _fetch_http(self, source: ExternalSourceConfig) -> Optional[str]:
        """Fetch content via HTTP GET.

        The Bearer token is read from os.environ inside this call only —
        the value is never assigned to a module-level variable or logged.

        Args:
            source: ExternalSourceConfig with source_type == 'http'.

        Returns:
            Response body as a string, or None on error / missing URL.
        """
        import urllib.request

        url = source.fetch_url_template
        if not url:
            _log("warning", "external_indexer.http_fetch.no_url", ok=False,
                 detail={"source": source.name})
            return None

        req = urllib.request.Request(url)
        if source.auth_env_var:
            token = os.environ.get(source.auth_env_var)  # scoped here, never logged
            if token:
                req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            _log("warning", "external_indexer.http_fetch.failed", ok=False,
                 detail={"source": source.name, "error": str(e)})
            return None

    def fetch_content(self, source: ExternalSourceConfig) -> Optional[str]:
        """Fetch content from an external source via MCP tool invocation pattern.

        In practice, the actual MCP call is made by the Claude Code agent (Task tool).
        This method provides the invocation descriptor that the agent uses, and can
        optionally invoke a local script if the plugin exposes a CLI.

        For now, returns None (content must be passed in via index_content).
        The refresh command reports which sources need fetching so the agent can
        orchestrate the actual MCP calls.

        Args:
            source: The source configuration to fetch from.

        Returns:
            Content string if available via local mechanism, else None.
        """
        _log(
            "verbose",
            "external_indexer.fetch.attempted",
            detail={"name": source.name, "plugin": source.plugin},
        )
        # MCP tool invocation requires the agent layer — not directly callable
        # from a script. Return None and let the agent handle fetch + index_content.
        return None

    def index_content(
        self,
        source: ExternalSourceConfig,
        content: str,
        doc_id: str,
    ) -> int:
        """Store fetched content in the search index with source attribution.

        Creates GraphNode-compatible JSONL entries in the external index file.
        Each entry includes source attribution metadata so search results can
        indicate where the content originated.

        Args:
            source: The source configuration (for attribution).
            content: The text content to index.
            doc_id: A unique identifier for this document within the source.

        Returns:
            Number of nodes indexed (typically 1 per document, more if chunked).
        """
        import hashlib

        t0 = time.monotonic()
        index_path = self._get_external_index_path()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build a node ID from source name + doc_id
        node_id_raw = f"external::{source.name}::{doc_id}"
        node_id = hashlib.sha256(node_id_raw.encode()).hexdigest()[:16]
        node_id = f"external::{source.name}::{node_id}"

        # Source attribution metadata — included on every external node
        attribution = {
            "source": "external",
            "source_name": source.name,
            "source_plugin": source.plugin,
            "last_fetched": now_iso,
            "content_type": source.content_type,
            "doc_id": doc_id,
        }

        # Build a GraphNode-compatible record (domain="doc", type="doc_page")
        # Uses the same schema as models.GraphNode so unified_search can load it.
        node = {
            "id": node_id,
            "name": doc_id,
            "type": "doc_page",
            "file": f"external://{source.plugin}/{doc_id}",
            "line_start": 1,
            "line_end": max(1, len(content.splitlines())),
            "calls": [],
            "imports": [],
            "bases": [],
            "imported_names": [],
            "dependents": [],
            "content": content,
            "domain": "doc",
            "metadata": attribution,
        }

        # Load existing index, remove any prior entry for this doc_id
        existing_nodes: List[dict] = []
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing = json.loads(line)
                        # Skip prior entry for this same doc
                        if existing.get("id") == node_id:
                            continue
                        existing_nodes.append(existing)
                    except json.JSONDecodeError:
                        continue

        existing_nodes.append(node)

        # Atomic write
        tmp_path = index_path.with_suffix(".jsonl.tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for n in existing_nodes:
                fh.write(json.dumps(n) + "\n")
        tmp_path.rename(index_path)

        # Update last_fetched on the source
        self.registry.update_last_fetched(source.name, now_iso)

        elapsed_ms = (time.monotonic() - t0) * 1000
        _log(
            "verbose",
            "external_indexer.content.indexed",
            ms=elapsed_ms,
            detail={"name": source.name, "doc_id": doc_id, "chars": len(content)},
        )

        return 1

    def refresh_stale(
        self,
        sources: Optional[List[ExternalSourceConfig]] = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> List[dict]:
        """Identify and optionally refresh stale sources.

        Since actual MCP fetching requires the agent layer, this method
        identifies which sources need refreshing and returns a descriptor
        list. When not dry_run, it logs the intent (the agent orchestrates
        the actual fetch via `index_content`).

        Args:
            sources: Sources to check (default: all enabled sources).
            force: Treat all sources as stale regardless of last_fetched.
            dry_run: Only report what would be refreshed, without side effects.

        Returns:
            List of dicts describing each source that needs refreshing:
            [{"name": "...", "plugin": "...", "stale": True, "last_fetched": "..."}]
        """
        if sources is None:
            sources = [s for s in self.registry.list_sources() if s.enabled]

        stale_sources = []
        for source in sources:
            is_stale = force or source.is_stale()
            if not is_stale:
                continue

            if source.source_type == "http":
                # HTTP sources are fetched directly here — no agent layer needed.
                entry: dict = {
                    "name": source.name,
                    "source_type": "http",
                    "fetch_url_template": source.fetch_url_template,
                    "last_fetched": source.last_fetched,
                    "stale": True,
                }
                if not dry_run:
                    content = self._fetch_http(source)
                    if content is not None:
                        doc_id = source.fetch_url_template or source.name
                        nodes = self.index_content(source, content, doc_id)
                        entry["indexed"] = True
                        entry["nodes_indexed"] = nodes
                    else:
                        entry["indexed"] = False
                        entry["error"] = "http_fetch returned None"
                stale_sources.append(entry)
            else:
                # MCP sources require the agent layer — report them for agent orchestration.
                stale_sources.append({
                    "name": source.name,
                    "source_type": "mcp",
                    "plugin": source.plugin,
                    "fetch_command": source.fetch_command,
                    "fetch_args": source.fetch_args,
                    "last_fetched": source.last_fetched,
                    "stale": True,
                })

        if not dry_run:
            _log(
                "verbose",
                "external_indexer.refresh.started",
                detail={"stale_count": len(stale_sources), "force": force},
            )

        return stale_sources


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="wicked-search external source indexer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", metavar="PATH",
        help="Path to sources config JSON (default: ~/.something-wicked/wicked-search/external-sources.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- list --
    list_p = sub.add_parser("list", help="List configured sources")
    list_p.add_argument("--json", action="store_true", dest="json_output")

    # -- add --
    add_p = sub.add_parser("add", help="Add a new external source")
    add_p.add_argument("--name", required=True, metavar="NAME")
    add_p.add_argument("--source-type", dest="source_type", default="mcp",
                       choices=["mcp", "http"],
                       help="Source type: mcp (agent-orchestrated) or http (default: mcp)")
    add_p.add_argument("--plugin", default="", metavar="PLUGIN",
                       help="MCP plugin name (required for mcp source type)")
    add_p.add_argument("--command", dest="fetch_command", default="", metavar="CMD",
                       help="MCP tool command (required for mcp source type)")
    add_p.add_argument("--args", dest="fetch_args", default="{}", metavar="JSON",
                       help="JSON object of fetch arguments (default: {})")
    add_p.add_argument("--fetch-url", dest="fetch_url_template", default=None, metavar="URL",
                       help="URL to fetch (required for http source type)")
    add_p.add_argument("--auth-env-var", dest="auth_env_var", default=None, metavar="ENV_VAR",
                       help="Name of env var holding Bearer token (http source type)")
    add_p.add_argument("--content-type", default="document", metavar="TYPE",
                       help="Content type: document, code, ticket (default: document)")
    add_p.add_argument("--refresh-interval", type=int, default=60, metavar="MINUTES",
                       help="Refresh interval in minutes (default: 60)")
    add_p.add_argument("--json", action="store_true", dest="json_output")

    # -- remove --
    rm_p = sub.add_parser("remove", help="Remove an external source")
    rm_p.add_argument("--name", required=True, metavar="NAME")
    rm_p.add_argument("--json", action="store_true", dest="json_output")

    # -- refresh --
    ref_p = sub.add_parser("refresh", help="Refresh stale external sources")
    ref_p.add_argument("--force", action="store_true", help="Force refresh all sources")
    ref_p.add_argument("--dry-run", action="store_true", help="Report what would be refreshed")
    ref_p.add_argument("--json", action="store_true", dest="json_output")

    # -- index-content --
    idx_p = sub.add_parser("index-content", help="Index content for a named source")
    idx_p.add_argument("--name", required=True, metavar="NAME")
    content_group = idx_p.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--content", metavar="TEXT",
                               help="Content string (limited by shell arg length)")
    content_group.add_argument("--content-file", metavar="PATH",
                               help="Path to file containing content (for large documents)")
    content_group.add_argument("--content-stdin", action="store_true",
                               help="Read content from stdin (for piped input)")
    idx_p.add_argument("--doc-id", required=True, metavar="ID")
    idx_p.add_argument("--json", action="store_true", dest="json_output")

    return parser.parse_args()


def _default_config_path() -> str:
    """Resolve default config path via resolve_path.py, falling back to DomainStore convention."""
    try:
        import subprocess as _sp
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
        result = _sp.run(
            ["python3", os.path.join(plugin_root, "scripts", "resolve_path.py"), "search"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return str(Path(result.stdout.strip()) / "external-sources.json")
    except Exception:
        pass  # fail open: falls back to DomainStore path
    # Fallback — use DomainStore path resolution
    import sys as _sys
    _scripts = str(Path(__file__).resolve().parents[1])
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)
    from _domain_store import get_local_path
    return str(get_local_path("wicked-search") / "external-sources.json")


def _make_registry(args: argparse.Namespace) -> ExternalSourceRegistry:
    config_path = args.config or _default_config_path()
    registry = ExternalSourceRegistry(config_path)
    registry.load_config()
    return registry


def cmd_list(args: argparse.Namespace) -> int:
    registry = _make_registry(args)
    sources = registry.list_sources()

    result = {
        "sources": [s.to_dict() for s in sources],
        "count": len(sources),
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if not sources:
            print("No external sources configured.")
        else:
            print(f"External sources ({len(sources)}):")
            for s in sources:
                status = "enabled" if s.enabled else "disabled"
                fetched = s.last_fetched or "never"
                print(f"  {s.name}")
                print(f"    source_type: {s.source_type}")
                if s.source_type == "http":
                    print(f"    url:      {s.fetch_url_template or '(not set)'}")
                    if s.auth_env_var:
                        print(f"    auth_env: {s.auth_env_var}")
                else:
                    print(f"    plugin:   {s.plugin}")
                    print(f"    command:  {s.fetch_command}")
                print(f"    type:     {s.content_type}")
                print(f"    refresh:  every {s.refresh_interval_minutes}m")
                print(f"    status:   {status}")
                print(f"    fetched:  {fetched}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    try:
        fetch_args = json.loads(args.fetch_args)
    except json.JSONDecodeError as e:
        print(f"Error: --args must be valid JSON: {e}", file=sys.stderr)
        return 1

    source_type = args.source_type

    # Validate required fields per source type
    if source_type == "mcp":
        if not args.plugin:
            print("Error: --plugin is required for mcp source type", file=sys.stderr)
            return 1
        if not args.fetch_command:
            print("Error: --command is required for mcp source type", file=sys.stderr)
            return 1
    elif source_type == "http":
        if not args.fetch_url_template:
            print("Error: --fetch-url is required for http source type", file=sys.stderr)
            return 1

    config = ExternalSourceConfig(
        name=args.name,
        plugin=args.plugin,
        fetch_command=args.fetch_command,
        fetch_args=fetch_args,
        content_type=args.content_type,
        refresh_interval_minutes=args.refresh_interval,
        source_type=source_type,
        auth_env_var=args.auth_env_var,
        fetch_url_template=args.fetch_url_template,
    )

    registry = _make_registry(args)
    registry.add_source(config)

    result = {"ok": True, "name": args.name, "action": "added", "source_type": source_type}
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Added external source: {args.name} (type: {source_type})")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    registry = _make_registry(args)
    existed = registry.remove_source(args.name)

    if not existed:
        result = {"ok": False, "error": f"Source not found: {args.name}"}
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: source not found: {args.name}", file=sys.stderr)
        return 1

    result = {"ok": True, "removed": args.name}
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Removed external source: {args.name}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    registry = _make_registry(args)
    indexer = ExternalIndexer(registry)

    stale = indexer.refresh_stale(force=args.force, dry_run=args.dry_run)

    result = {
        "stale_sources": stale,
        "stale_count": len(stale),
        "dry_run": args.dry_run,
        "force": args.force,
    }
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if not stale:
            print("All sources are up to date.")
        else:
            action = "Would refresh" if args.dry_run else "Needs refresh"
            print(f"{action} {len(stale)} source(s):")
            mcp_stale = []
            for s in stale:
                fetched = s["last_fetched"] or "never"
                stype = s.get("source_type", "mcp")
                if stype == "http":
                    indexed_flag = ""
                    if "indexed" in s:
                        indexed_flag = " [indexed]" if s["indexed"] else " [fetch failed]"
                    print(f"  {s['name']} (http, last fetched: {fetched}){indexed_flag}")
                else:
                    mcp_stale.append(s)
                    print(f"  {s['name']} (mcp, last fetched: {fetched})")
            if mcp_stale and not args.dry_run:
                print("\nNote: Use the /wicked-garden:search:sources command to")
                print("have the agent orchestrate actual MCP content fetching.")
    return 0


def cmd_index_content(args: argparse.Namespace) -> int:
    registry = _make_registry(args)
    source = registry.get_source(args.name)

    if source is None:
        result = {"ok": False, "error": f"Source not found: {args.name}"}
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: source not found: {args.name}", file=sys.stderr)
        return 1

    # Resolve content from whichever input method was provided
    if args.content:
        content = args.content
    elif args.content_file:
        try:
            with open(args.content_file) as f:
                content = f.read()
        except OSError as e:
            result = {"ok": False, "error": f"Cannot read content file: {e}"}
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.content_stdin:
        content = sys.stdin.read()
    else:
        result = {"ok": False, "error": "No content provided (use --content, --content-file, or --content-stdin)"}
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print("Error: no content provided", file=sys.stderr)
        return 1

    indexer = ExternalIndexer(registry)
    nodes_indexed = indexer.index_content(source, content, args.doc_id)

    result = {
        "ok": True,
        "nodes_indexed": nodes_indexed,
        "source_name": args.name,
        "doc_id": args.doc_id,
    }
    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Indexed {nodes_indexed} node(s) from source '{args.name}' (doc: {args.doc_id})")
    return 0


def main() -> int:
    args = _parse_args()

    try:
        if args.command == "list":
            return cmd_list(args)
        elif args.command == "add":
            return cmd_add(args)
        elif args.command == "remove":
            return cmd_remove(args)
        elif args.command == "refresh":
            return cmd_refresh(args)
        elif args.command == "index-content":
            return cmd_index_content(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        _log("normal", "external_indexer.cli.error", ok=False, detail={"error": str(e)})
        if os.environ.get("WICKED_DEBUG"):
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
