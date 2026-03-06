#!/usr/bin/env python3
"""
_adapters/__init__.py — External tool adapter base class and factory.

ExternalToolAdapter is the interface DomainStore uses to delegate CRUD
operations to external MCP tools (Linear, Jira, Notion, Miro, etc.).

All stub implementations return None — DomainStore interprets None as
"not handled; fall through to local JSON". Real implementations will be
wired once the MCP-from-Python invocation approach is determined.

Usage:
    from _adapters import ExternalToolAdapter, from_tool_name

    adapter = from_tool_name("linear")   # → LinearAdapter instance
    adapter = from_tool_name("unknown")  # → ExternalToolAdapter (base no-op)
    adapter = from_tool_name(None)       # → None
"""
from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ExternalToolAdapter:
    """No-op base adapter.  All methods return None so DomainStore falls back
    to local JSON automatically.

    Subclasses override individual methods as real MCP bindings are added.
    """

    # The tool name this adapter handles (set on subclasses)
    tool_name: str = "base"

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list(self, source: str, **params: Any) -> Optional[list]:
        """List records.  Returns None → DomainStore uses local JSON."""
        return None

    def get(self, source: str, id: str) -> Optional[dict]:
        """Fetch a single record by ID.  Returns None → fall through."""
        return None

    def search(self, source: str, q: str, **params: Any) -> Optional[list]:
        """Search records.  Returns None → fall through."""
        return None

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, source: str, payload: dict) -> Optional[dict]:
        """Create a record.  Returns None → DomainStore writes locally."""
        return None

    def update(self, source: str, id: str, diff: dict) -> Optional[dict]:
        """Patch a record.  Returns None → fall through."""
        return None

    def delete(self, source: str, id: str) -> Optional[bool]:
        """Delete a record.  Returns None → fall through."""
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Registry: tool name (lowercase) → adapter class
_REGISTRY: dict[str, type[ExternalToolAdapter]] = {}


def _register(cls: type[ExternalToolAdapter]) -> type[ExternalToolAdapter]:
    """Decorator that registers an adapter class in _REGISTRY."""
    _REGISTRY[cls.tool_name.lower()] = cls
    return cls


def from_tool_name(tool_name: Optional[str]) -> Optional[ExternalToolAdapter]:
    """Return an adapter instance for *tool_name*, or None.

    Args:
        tool_name: Tool name returned by resolve_tool(), e.g. "linear",
                   "jira", "notion", "miro".  None or "local" returns None
                   so the caller can skip the external path entirely.

    Returns:
        An ExternalToolAdapter instance, or None when no tool is configured.

    Lookup order:
        1. Exact match in _REGISTRY (lazy-loaded on first call).
        2. Falls back to the base no-op ExternalToolAdapter so callers
           never have to guard against unknown tool names — the base adapter
           returns None on every operation and local JSON is used.
    """
    if not tool_name or tool_name == "local":
        return None

    # Lazy-load concrete adapters to avoid import cost when local-only
    _ensure_adapters_loaded()

    key = tool_name.lower()
    cls = _REGISTRY.get(key)
    if cls is not None:
        return cls()

    # Unknown tool — return base no-op so operations fall through to local
    return ExternalToolAdapter()


# ---------------------------------------------------------------------------
# Lazy loader
# ---------------------------------------------------------------------------

_adapters_loaded = False


def _ensure_adapters_loaded() -> None:
    """Import all concrete adapter modules so they register themselves.

    Uses spec_from_file_location so this works whether _adapters is imported
    as a proper package or simply has its parent directory on sys.path.
    """
    global _adapters_loaded
    if _adapters_loaded:
        return
    _adapters_loaded = True

    import importlib.util
    import os
    import sys as _sys

    _pkg_dir = os.path.dirname(__file__)
    # Ensure the _adapters package itself is registered in sys.modules so
    # that absolute imports like "from _adapters import ..." inside each
    # adapter module resolve correctly.
    _pkg_key = "_adapters"
    import types as _types
    if _pkg_key not in _sys.modules:
        _sys.modules[_pkg_key] = _sys.modules.get(__name__, _types.ModuleType(_pkg_key))

    for filename in sorted(os.listdir(_pkg_dir)):
        if not filename.endswith("_adapter.py") or filename.startswith("_"):
            continue
        module_name = filename[:-3]  # strip .py
        full_key = f"_adapters.{module_name}"
        if full_key in _sys.modules:
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                full_key,
                os.path.join(_pkg_dir, filename),
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                _sys.modules[full_key] = mod
                spec.loader.exec_module(mod)  # type: ignore[arg-type]
        except Exception:
            pass  # Adapter unavailable — continue with base no-op
