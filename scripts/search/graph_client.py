"""Graph client module for wicked-search.

Consumer API for reading cached graph data from wicked-cache.
See docs/cache-schema.md for full specification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# Result Types
# ============================================================================

@dataclass
class FreshnessMetadata:
    """Freshness metadata from cache."""
    indexed_at: str
    workspace_hash: str
    file_count: int
    node_count: int
    edge_count: int


@dataclass
class SymbolDependency:
    """A single dependency relationship."""
    target_id: str
    type: str
    line: int


@dataclass
class SymbolDependent:
    """A single dependent relationship."""
    source_id: str
    type: str
    line: int


@dataclass
class SymbolDepsEntry:
    """Symbol with dependencies and dependents."""
    id: str
    name: str
    type: str
    file: str
    line_start: int
    line_end: int
    dependencies: List[SymbolDependency]
    dependents: List[SymbolDependent]


@dataclass
class SymbolDepsResult:
    """Result for symbol dependencies query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    symbols: List[SymbolDepsEntry]


@dataclass
class FileSymbol:
    """Symbol summary for file references."""
    id: str
    name: str
    type: str
    line_start: int
    line_end: int
    calls_out: int
    calls_in: int


@dataclass
class FileRef:
    """File with symbols."""
    path: str
    mtime: float
    size: int
    domain: str
    symbols: List[FileSymbol]
    imports: List[str]


@dataclass
class FileRefsResult:
    """Result for file references query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    files: List[FileRef]


@dataclass
class SymbolLocation:
    """Symbol location for definition lookup."""
    id: str
    qualified_name: str
    file: str
    line_start: int
    type: str


@dataclass
class CallChainEntry:
    """Single entry in a call chain."""
    id: str
    name: str
    file: str
    depth: int
    path: List[str]


@dataclass
class CallChain:
    """Call chain for a symbol."""
    root_id: str
    root_name: str
    root_file: str
    downstream: List[CallChainEntry]
    upstream: List[CallChainEntry]


@dataclass
class CallChainResult:
    """Result for call chain query."""
    version: str
    freshness: FreshnessMetadata
    filter: Dict
    chains: List[CallChain]


# ============================================================================
# Exceptions
# ============================================================================

class CacheStaleError(Exception):
    """Raised when cache is stale or missing."""
    pass


class VersionMismatchError(Exception):
    """Raised when cache version is incompatible."""
    pass


# ============================================================================
# Client
# ============================================================================

class GraphClient:
    """Consumer API for reading cached graph data."""

    REQUIRED_VERSION = "1.0.0"

    def __init__(
        self,
        workspace_path: str,
        cache = None
    ):
        """
        Initialize client.

        Args:
            workspace_path: Root path of workspace
            cache: Optional wicked-cache namespace (auto-created if None)
        """
        self.workspace_hash = self._hash_workspace(workspace_path)
        self.workspace_path = workspace_path

        # Import cache here to avoid circular dependency
        if cache is None:
            from cache import namespace
            self.cache = namespace("wicked-search")
        else:
            self.cache = cache

    def get_symbol_dependencies(
        self,
        filter: Optional[Dict] = None
    ) -> SymbolDepsResult:
        """
        Get symbol dependencies with optional filter.

        Args:
            filter: Optional filter parameters

        Returns:
            SymbolDepsResult with symbols and relationships

        Raises:
            CacheStaleError: If cache is stale or missing
            VersionMismatchError: If cache version is incompatible
        """
        # Build cache key
        key_parts = ["symbol_deps", self.workspace_hash]
        if filter:
            filter_hash = self._hash_filter(filter)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Fetch from cache
        data = self.cache.get(cache_key)
        if data is None:
            raise CacheStaleError(f"Cache miss for key: {cache_key}")

        # Validate version
        cached_version = data.get("version", "0.0.0")
        if not self._is_compatible(cached_version):
            raise VersionMismatchError(
                f"Cache version {cached_version} incompatible with {self.REQUIRED_VERSION}"
            )

        # Parse freshness metadata
        freshness_data = data.get("freshness", {})
        freshness = FreshnessMetadata(
            indexed_at=freshness_data.get("indexed_at", ""),
            workspace_hash=freshness_data.get("workspace_hash", ""),
            file_count=freshness_data.get("file_count", 0),
            node_count=freshness_data.get("node_count", 0),
            edge_count=freshness_data.get("edge_count", 0)
        )

        # Parse symbols
        symbols = []
        for sym_data in data.get("symbols", []):
            dependencies = [
                SymbolDependency(
                    target_id=dep["target_id"],
                    type=dep["type"],
                    line=dep["line"]
                )
                for dep in sym_data.get("dependencies", [])
            ]

            dependents = [
                SymbolDependent(
                    source_id=dep["source_id"],
                    type=dep["type"],
                    line=dep["line"]
                )
                for dep in sym_data.get("dependents", [])
            ]

            symbols.append(SymbolDepsEntry(
                id=sym_data["id"],
                name=sym_data["name"],
                type=sym_data["type"],
                file=sym_data["file"],
                line_start=sym_data["line_start"],
                line_end=sym_data["line_end"],
                dependencies=dependencies,
                dependents=dependents
            ))

        return SymbolDepsResult(
            version=data["version"],
            freshness=freshness,
            filter=data.get("filter", {}),
            symbols=symbols
        )

    def get_file_references(
        self,
        files: Optional[List[str]] = None
    ) -> FileRefsResult:
        """
        Get file references.

        Args:
            files: Optional list of file paths to include

        Returns:
            FileRefsResult with file-level symbol data

        Raises:
            CacheStaleError: If cache is stale or missing
            VersionMismatchError: If cache version is incompatible
        """
        # Build cache key
        filter_params = {"files": files} if files else None
        key_parts = ["file_refs", self.workspace_hash]
        if filter_params:
            filter_hash = self._hash_filter(filter_params)
            key_parts.append(filter_hash)
        cache_key = ":".join(key_parts)

        # Fetch from cache
        data = self.cache.get(cache_key)
        if data is None:
            raise CacheStaleError(f"Cache miss for key: {cache_key}")

        # Validate version
        cached_version = data.get("version", "0.0.0")
        if not self._is_compatible(cached_version):
            raise VersionMismatchError(
                f"Cache version {cached_version} incompatible with {self.REQUIRED_VERSION}"
            )

        # Parse freshness metadata
        freshness_data = data.get("freshness", {})
        freshness = FreshnessMetadata(
            indexed_at=freshness_data.get("indexed_at", ""),
            workspace_hash=freshness_data.get("workspace_hash", ""),
            file_count=freshness_data.get("file_count", 0),
            node_count=freshness_data.get("node_count", 0),
            edge_count=freshness_data.get("edge_count", 0)
        )

        # Parse files
        file_refs = []
        for file_data in data.get("files", []):
            symbols = [
                FileSymbol(
                    id=sym["id"],
                    name=sym["name"],
                    type=sym["type"],
                    line_start=sym["line_start"],
                    line_end=sym["line_end"],
                    calls_out=sym["calls_out"],
                    calls_in=sym["calls_in"]
                )
                for sym in file_data.get("symbols", [])
            ]

            file_refs.append(FileRef(
                path=file_data["path"],
                mtime=file_data["mtime"],
                size=file_data["size"],
                domain=file_data["domain"],
                symbols=symbols,
                imports=file_data.get("imports", [])
            ))

        return FileRefsResult(
            version=data["version"],
            freshness=freshness,
            filter=data.get("filter", {}),
            files=file_refs
        )

    def lookup_definition(
        self,
        name: Optional[str] = None,
        qualified_name: Optional[str] = None
    ) -> Optional[SymbolLocation]:
        """
        Lookup symbol definition location.

        Args:
            name: Simple name (may return multiple results)
            qualified_name: Fully qualified name (unique)

        Returns:
            SymbolLocation or None if not found

        Raises:
            CacheStaleError: If cache is stale or missing
            VersionMismatchError: If cache version is incompatible
        """
        if not name and not qualified_name:
            raise ValueError("Must provide either name or qualified_name")

        # Build cache key (no filter for def_lookup)
        cache_key = f"def_lookup:{self.workspace_hash}"

        # Fetch from cache
        data = self.cache.get(cache_key)
        if data is None:
            raise CacheStaleError(f"Cache miss for key: {cache_key}")

        # Validate version
        cached_version = data.get("version", "0.0.0")
        if not self._is_compatible(cached_version):
            raise VersionMismatchError(
                f"Cache version {cached_version} incompatible with {self.REQUIRED_VERSION}"
            )

        index = data.get("index", {})

        # Lookup by qualified name (preferred, unique)
        if qualified_name:
            qn_key = qualified_name.lower()
            by_qn = index.get("by_qualified_name", {})
            if qn_key in by_qn:
                loc = by_qn[qn_key]
                return SymbolLocation(
                    id=loc["id"],
                    qualified_name=qualified_name,
                    file=loc["file"],
                    line_start=loc["line_start"],
                    type=loc["type"]
                )
            return None

        # Lookup by name (may have multiple matches, return first)
        if name:
            name_key = name.lower()
            by_name = index.get("by_name", {})
            if name_key in by_name:
                matches = by_name[name_key]
                if matches:
                    first = matches[0]
                    return SymbolLocation(
                        id=first["id"],
                        qualified_name=first.get("qualified_name", ""),
                        file=first["file"],
                        line_start=first["line_start"],
                        type=first["type"]
                    )
            return None

        return None

    def get_call_chain(
        self,
        symbol_id: str,
        max_depth: int = 5,
        ref_types: Optional[List[str]] = None
    ) -> CallChainResult:
        """
        Get transitive call chain.

        Args:
            symbol_id: Root symbol ID
            max_depth: Max traversal depth
            ref_types: Reference types to follow

        Returns:
            CallChainResult with upstream/downstream chains

        Raises:
            CacheStaleError: If cache is stale or missing
            VersionMismatchError: If cache version is incompatible
        """
        # Build filter for cache key
        filter_params = {
            "max_depth": max_depth
        }
        if ref_types:
            filter_params["ref_types"] = ref_types

        # Build cache key
        filter_hash = self._hash_filter(filter_params)
        cache_key = f"call_chain:{self.workspace_hash}:{filter_hash}"

        # Fetch from cache
        data = self.cache.get(cache_key)
        if data is None:
            raise CacheStaleError(f"Cache miss for key: {cache_key}")

        # Validate version
        cached_version = data.get("version", "0.0.0")
        if not self._is_compatible(cached_version):
            raise VersionMismatchError(
                f"Cache version {cached_version} incompatible with {self.REQUIRED_VERSION}"
            )

        # Parse freshness metadata
        freshness_data = data.get("freshness", {})
        freshness = FreshnessMetadata(
            indexed_at=freshness_data.get("indexed_at", ""),
            workspace_hash=freshness_data.get("workspace_hash", ""),
            file_count=freshness_data.get("file_count", 0),
            node_count=freshness_data.get("node_count", 0),
            edge_count=freshness_data.get("edge_count", 0)
        )

        # Parse chains
        chains = []
        for chain_data in data.get("chains", []):
            # Only include chain if it matches the requested symbol
            if chain_data["root_id"] != symbol_id:
                continue

            downstream = [
                CallChainEntry(
                    id=entry["id"],
                    name=entry["name"],
                    file=entry["file"],
                    depth=entry["depth"],
                    path=entry["path"]
                )
                for entry in chain_data.get("downstream", [])
            ]

            upstream = [
                CallChainEntry(
                    id=entry["id"],
                    name=entry["name"],
                    file=entry["file"],
                    depth=entry["depth"],
                    path=entry["path"]
                )
                for entry in chain_data.get("upstream", [])
            ]

            chains.append(CallChain(
                root_id=chain_data["root_id"],
                root_name=chain_data["root_name"],
                root_file=chain_data["root_file"],
                downstream=downstream,
                upstream=upstream
            ))

        return CallChainResult(
            version=data["version"],
            freshness=freshness,
            filter=data.get("filter", {}),
            chains=chains
        )

    def is_fresh(self, max_age_seconds: int = 3600) -> bool:
        """
        Check if cache is fresh.

        Args:
            max_age_seconds: Max age in seconds (default 1 hour)

        Returns:
            True if cache is fresh
        """
        freshness = self.get_freshness()
        if freshness is None:
            return False

        # Check workspace hash
        if freshness.workspace_hash != self.workspace_hash:
            return False

        # Check age
        try:
            indexed_at = datetime.fromisoformat(
                freshness.indexed_at.replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - indexed_at).total_seconds()
            return age < max_age_seconds
        except Exception:
            return False

    def get_freshness(self) -> Optional[FreshnessMetadata]:
        """
        Get freshness metadata.

        Returns:
            FreshnessMetadata or None if cache is empty
        """
        # Check any cache key (use symbol_deps as canonical)
        cache_key = f"symbol_deps:{self.workspace_hash}"
        data = self.cache.get(cache_key)

        if data is None:
            return None

        freshness_data = data.get("freshness", {})
        return FreshnessMetadata(
            indexed_at=freshness_data.get("indexed_at", ""),
            workspace_hash=freshness_data.get("workspace_hash", ""),
            file_count=freshness_data.get("file_count", 0),
            node_count=freshness_data.get("node_count", 0),
            edge_count=freshness_data.get("edge_count", 0)
        )

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

    def _is_compatible(self, cached_version: str) -> bool:
        """Check if cached version is compatible with required version."""
        try:
            cached_major = int(cached_version.split('.')[0])
            required_major = int(self.REQUIRED_VERSION.split('.')[0])
            return cached_major == required_major
        except Exception:
            return False
