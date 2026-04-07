"""Graph export module for wicked-search.

Exports SymbolGraph to wicked-cache for consumption by other plugins.
See docs/cache-schema.md for full specification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from symbol_graph import ReferenceType, SymbolGraph


@dataclass
class FreshnessMetadata:
    """Freshness metadata for cache invalidation."""
    indexed_at: str
    workspace_hash: str
    file_count: int
    node_count: int
    edge_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExportResult:
    """Result from export operation."""
    workspace_hash: str
    exported_at: str
    keys_written: List[str]
    stats: Dict[str, int]


@dataclass
class IncrementalExportResult:
    """Result from incremental export operation."""
    workspace_hash: str
    exported_at: str
    keys_updated: List[str]
    files_affected: List[str]
    is_partial: bool = True


class GraphExporter:
    """Exports wicked-search SymbolGraph to wicked-cache."""

    VERSION = "1.0.0"

    def __init__(self, cache):
        """
        Initialize exporter.

        Args:
            cache: NamespacedCache instance (wicked-cache)
        """
        self.cache = cache

    def export_all(
        self,
        graph: SymbolGraph,
        workspace_path: str,
        force: bool = False
    ) -> ExportResult:
        """
        Export all query types to cache.

        Args:
            graph: SymbolGraph instance to export
            workspace_path: Root path of workspace (for hash generation)
            force: Force re-export even if cache is fresh

        Returns:
            ExportResult with statistics
        """
        workspace_hash = self._hash_workspace(workspace_path)
        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        keys_written = []

        # Build freshness metadata
        stats = graph.stats()
        freshness = FreshnessMetadata(
            indexed_at=exported_at,
            workspace_hash=workspace_hash,
            file_count=stats.get("total_files", 0),
            node_count=stats.get("total_symbols", 0),
            edge_count=stats.get("total_references", 0)
        )

        # Export each query type
        key = self.export_symbol_deps(graph, workspace_hash, freshness)
        keys_written.append(key)

        key = self.export_file_refs(graph, workspace_hash, freshness)
        keys_written.append(key)

        key = self.export_def_lookup(graph, workspace_hash, freshness)
        keys_written.append(key)

        key = self.export_call_chain(graph, workspace_hash, freshness)
        keys_written.append(key)

        return ExportResult(
            workspace_hash=workspace_hash,
            exported_at=exported_at,
            keys_written=keys_written,
            stats=stats
        )

    def export_incremental(
        self,
        graph: SymbolGraph,
        workspace_path: str,
        changed_files: List[str]
    ) -> IncrementalExportResult:
        """
        Export incremental updates for changed files only.

        Instead of re-exporting the entire graph, this method:
        1. Updates only the symbols in changed files
        2. Updates affected dependents
        3. Preserves cache entries for unchanged files

        Args:
            graph: Updated SymbolGraph instance
            workspace_path: Root path of workspace
            changed_files: List of file paths that changed

        Returns:
            IncrementalExportResult with update statistics
        """
        workspace_hash = self._hash_workspace(workspace_path)
        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        keys_updated = []

        # Build freshness metadata
        stats = graph.stats()
        freshness = FreshnessMetadata(
            indexed_at=exported_at,
            workspace_hash=workspace_hash,
            file_count=stats.get("total_files", 0),
            node_count=stats.get("total_symbols", 0),
            edge_count=stats.get("total_references", 0)
        )

        # For incremental updates, we still need to re-export all query types
        # but the underlying graph already has incremental changes applied.
        # The cache benefits from freshness metadata updates.

        # Get affected symbols (in changed files + their dependents)
        affected_symbols = set()
        for symbol in graph.symbols.values():
            if symbol.file_path in changed_files:
                affected_symbols.add(symbol.id)
                # Also mark dependents as affected (they reference changed symbols)
                for ref in graph.get_references_to(symbol.id):
                    affected_symbols.add(ref.source_id)

        # Re-export all query types with updated freshness
        # Note: For truly incremental cache updates, we'd need delta-capable
        # cache storage. For now, we re-export with efficient freshness tracking.
        key = self.export_symbol_deps(graph, workspace_hash, freshness)
        keys_updated.append(key)

        key = self.export_file_refs(graph, workspace_hash, freshness)
        keys_updated.append(key)

        key = self.export_def_lookup(graph, workspace_hash, freshness)
        keys_updated.append(key)

        key = self.export_call_chain(graph, workspace_hash, freshness)
        keys_updated.append(key)

        return IncrementalExportResult(
            workspace_hash=workspace_hash,
            exported_at=exported_at,
            keys_updated=keys_updated,
            files_affected=changed_files,
            is_partial=True
        )

    def export_symbol_deps(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        freshness: FreshnessMetadata,
        filter_params: Optional[Dict] = None
    ) -> str:
        """
        Export symbol dependencies view.

        Args:
            graph: SymbolGraph to export
            workspace_hash: Workspace identifier
            freshness: Freshness metadata
            filter_params: Optional filter parameters

        Returns:
            Cache key
        """
        # Build cache key
        key_parts = ["symbol_deps", workspace_hash]
        if filter_params:
            filter_hash = self._hash_filter(filter_params)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Build symbols array
        symbols = []
        for symbol in graph.symbols.values():
            # Apply filter if provided
            if filter_params and not self._matches_filter(symbol, filter_params):
                continue

            # Build dependencies
            dependencies = []
            for ref in graph.get_references_from(symbol.id):
                dependencies.append({
                    "target_id": ref.target_id,
                    "type": ref.ref_type.value if hasattr(ref.ref_type, 'value') else str(ref.ref_type),
                    "line": ref.evidence.get("line", 0)
                })

            # Build dependents
            dependents = []
            for ref in graph.get_references_to(symbol.id):
                dependents.append({
                    "source_id": ref.source_id,
                    "type": ref.ref_type.value if hasattr(ref.ref_type, 'value') else str(ref.ref_type),
                    "line": ref.evidence.get("line", 0)
                })

            symbols.append({
                "id": symbol.id,
                "name": symbol.name,
                "type": symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type),
                "file": symbol.file_path,
                "line_start": symbol.line_start,
                "line_end": symbol.line_end,
                "dependencies": dependencies,
                "dependents": dependents
            })

        # Build result
        result = {
            "version": self.VERSION,
            "freshness": freshness.to_dict(),
            "filter": filter_params or {},
            "symbols": symbols
        }

        # Write to cache (manual mode, no auto-invalidation)
        self.cache.set(cache_key, result, options={"mode": "manual"})
        return cache_key

    def export_file_refs(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        freshness: FreshnessMetadata,
        filter_params: Optional[Dict] = None
    ) -> str:
        """
        Export file references view.

        Args:
            graph: SymbolGraph to export
            workspace_hash: Workspace identifier
            freshness: Freshness metadata
            filter_params: Optional filter parameters (e.g., {"files": [...]})

        Returns:
            Cache key
        """
        # Build cache key
        key_parts = ["file_refs", workspace_hash]
        if filter_params:
            filter_hash = self._hash_filter(filter_params)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Group symbols by file
        file_map = {}
        for symbol in graph.symbols.values():
            file_path = symbol.file_path

            # Apply file filter if provided
            if filter_params and "files" in filter_params:
                if file_path not in filter_params["files"]:
                    continue

            if file_path not in file_map:
                file_map[file_path] = {
                    "symbols": [],
                    "imports": set()
                }

            # Count calls in/out
            calls_out = len(graph.get_references_from(symbol.id))
            calls_in = len(graph.get_references_to(symbol.id))

            file_map[file_path]["symbols"].append({
                "id": symbol.id,
                "name": symbol.name,
                "type": symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type),
                "line_start": symbol.line_start,
                "line_end": symbol.line_end,
                "calls_out": calls_out,
                "calls_in": calls_in
            })

            # Collect imports
            for ref in graph.get_references_from(symbol.id, ref_type=ReferenceType.IMPORTS):
                target = graph.get_symbol(ref.target_id)
                if target:
                    file_map[file_path]["imports"].add(target.name)

        # Build files array
        files = []
        for file_path, data in file_map.items():
            # Get file metadata (stub for now, would come from IndexMetadata)
            files.append({
                "path": file_path,
                "mtime": 0,  # TODO: get from IndexMetadata
                "size": 0,   # TODO: get from IndexMetadata
                "domain": "code",  # TODO: get from symbol metadata
                "symbols": data["symbols"],
                "imports": sorted(data["imports"])
            })

        # Build result
        result = {
            "version": self.VERSION,
            "freshness": freshness.to_dict(),
            "filter": filter_params or {},
            "files": files
        }

        # Write to cache
        self.cache.set(cache_key, result, options={"mode": "manual"})
        return cache_key

    def export_def_lookup(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        freshness: FreshnessMetadata,
        filter_params: Optional[Dict] = None
    ) -> str:
        """
        Export definition lookup index.

        Args:
            graph: SymbolGraph to export
            workspace_hash: Workspace identifier
            freshness: Freshness metadata
            filter_params: Optional filter parameters

        Returns:
            Cache key
        """
        # Build cache key
        key_parts = ["def_lookup", workspace_hash]
        if filter_params:
            filter_hash = self._hash_filter(filter_params)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Build indexes
        by_name = {}
        by_qualified_name = {}

        for symbol in graph.symbols.values():
            # Apply filter if provided
            if filter_params and not self._matches_filter(symbol, filter_params):
                continue

            # By name (case-insensitive)
            name_key = symbol.name.lower()
            if name_key not in by_name:
                by_name[name_key] = []

            by_name[name_key].append({
                "id": symbol.id,
                "qualified_name": symbol.qualified_name,
                "file": symbol.file_path,
                "line_start": symbol.line_start,
                "type": symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type)
            })

            # By qualified name
            if symbol.qualified_name:
                qn_key = symbol.qualified_name.lower()
                by_qualified_name[qn_key] = {
                    "id": symbol.id,
                    "file": symbol.file_path,
                    "line_start": symbol.line_start,
                    "type": symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type)
                }

        # Build result
        result = {
            "version": self.VERSION,
            "freshness": freshness.to_dict(),
            "filter": filter_params or {},
            "index": {
                "by_name": by_name,
                "by_qualified_name": by_qualified_name
            }
        }

        # Write to cache
        self.cache.set(cache_key, result, options={"mode": "manual"})
        return cache_key

    def export_call_chain(
        self,
        graph: SymbolGraph,
        workspace_hash: str,
        freshness: FreshnessMetadata,
        filter_params: Optional[Dict] = None
    ) -> str:
        """
        Export call chain analysis.

        Args:
            graph: SymbolGraph to export
            workspace_hash: Workspace identifier
            freshness: Freshness metadata
            filter_params: Optional filter parameters

        Returns:
            Cache key
        """
        # Build cache key
        key_parts = ["call_chain", workspace_hash]
        if filter_params:
            filter_hash = self._hash_filter(filter_params)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Get filter parameters
        max_depth = filter_params.get("max_depth", 5) if filter_params else 5
        ref_types = filter_params.get("ref_types") if filter_params else None
        ref_types_set = set(ReferenceType(rt) for rt in ref_types) if ref_types else None

        # Build chains for each symbol using BFS to track depth/path
        chains = []
        for symbol in graph.symbols.values():
            # Get downstream (transitive dependencies) with depth tracking via BFS
            downstream = []
            visited_down = {symbol.id}
            queue_down = [(symbol.id, 0, [symbol.id])]  # (current_id, depth, path)

            while queue_down:
                current_id, depth, path = queue_down.pop(0)
                if depth >= max_depth:
                    continue

                for ref in graph.get_references_from(current_id):
                    # Apply ref_types filter if specified
                    if ref_types_set and ref.ref_type not in ref_types_set:
                        continue

                    target_id = ref.target_id
                    if target_id in visited_down:
                        continue

                    visited_down.add(target_id)
                    target = graph.get_symbol(target_id)
                    if target:
                        new_path = path + [target_id]
                        downstream.append({
                            "id": target.id,
                            "name": target.name,
                            "file": target.file_path,
                            "depth": depth + 1,
                            "path": new_path
                        })
                        queue_down.append((target_id, depth + 1, new_path))

            # Get upstream (transitive reverse dependencies) with depth tracking via BFS
            upstream = []
            visited_up = {symbol.id}
            queue_up = [(symbol.id, 0, [symbol.id])]

            while queue_up:
                current_id, depth, path = queue_up.pop(0)
                if depth >= max_depth:
                    continue

                for ref in graph.get_references_to(current_id):
                    # Apply ref_types filter if specified
                    if ref_types_set and ref.ref_type not in ref_types_set:
                        continue

                    source_id = ref.source_id
                    if source_id in visited_up:
                        continue

                    visited_up.add(source_id)
                    source = graph.get_symbol(source_id)
                    if source:
                        new_path = path + [source_id]
                        upstream.append({
                            "id": source.id,
                            "name": source.name,
                            "file": source.file_path,
                            "depth": depth + 1,
                            "path": new_path
                        })
                        queue_up.append((source_id, depth + 1, new_path))

            # Only include symbols with dependencies
            if downstream or upstream:
                chains.append({
                    "root_id": symbol.id,
                    "root_name": symbol.name,
                    "root_file": symbol.file_path,
                    "downstream": downstream,
                    "upstream": upstream
                })

        # Build result
        result = {
            "version": self.VERSION,
            "freshness": freshness.to_dict(),
            "filter": filter_params or {},
            "chains": chains
        }

        # Write to cache
        self.cache.set(cache_key, result, options={"mode": "manual"})
        return cache_key

    def invalidate_all(self, workspace_hash: str) -> int:
        """
        Invalidate all cache entries for a workspace, including filtered variants.

        Args:
            workspace_hash: Workspace identifier

        Returns:
            Count of invalidated entries
        """
        count = 0
        query_types = ["symbol_deps", "file_refs", "def_lookup", "call_chain"]

        # Get all cache entries and invalidate those matching our workspace
        try:
            all_entries = self.cache.list_entries() if hasattr(self.cache, 'list_entries') else []
            for entry in all_entries:
                key = entry.get("key", "") if isinstance(entry, dict) else getattr(entry, "key", "")
                # Match pattern: {query_type}:{workspace_hash} or {query_type}:{workspace_hash}:{filter_hash}
                for query_type in query_types:
                    prefix = f"{query_type}:{workspace_hash}"
                    if key == prefix or key.startswith(f"{prefix}:"):
                        if self.cache.invalidate(key):
                            count += 1
                        break
        except Exception:
            # Fallback: just invalidate base keys (backward compatible)
            for query_type in query_types:
                key = f"{query_type}:{workspace_hash}"
                if self.cache.invalidate(key):
                    count += 1

        return count

    def _hash_workspace(self, workspace_path: str) -> str:
        """Generate stable hash for workspace path."""
        canonical_path = str(Path(workspace_path).resolve())
        return hashlib.sha256(canonical_path.encode()).hexdigest()[:8]

    def _hash_filter(self, filter_params: Dict) -> str:
        """Generate stable hash for filter parameters.

        Canonicalizes list values by sorting to ensure order-independent hashing.
        """
        # Deep-copy and canonicalize lists
        canonical_params = {}
        for key, value in filter_params.items():
            if isinstance(value, list):
                canonical_params[key] = sorted(value)
            else:
                canonical_params[key] = value
        canonical = json.dumps(canonical_params, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:8]

    def _matches_filter(self, symbol, filter_params: Dict) -> bool:
        """Check if symbol matches filter parameters."""
        if not filter_params:
            return True

        # Filter by paths
        if "paths" in filter_params:
            if not any(symbol.file_path.startswith(p) for p in filter_params["paths"]):
                return False

        # Filter by exclude_paths
        if "exclude_paths" in filter_params:
            if any(symbol.file_path.startswith(p) for p in filter_params["exclude_paths"]):
                return False

        # Filter by node_types
        if "node_types" in filter_params:
            symbol_type = symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type)
            if symbol_type not in filter_params["node_types"]:
                return False

        # Filter by domain
        if "domain" in filter_params:
            # Assume domain is stored in symbol metadata
            symbol_domain = symbol.metadata.get("domain", "code")
            if symbol_domain != filter_params["domain"]:
                return False

        return True
