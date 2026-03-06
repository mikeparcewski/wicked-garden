#!/usr/bin/env python3
"""
linear_adapter.py — Linear MCP adapter stub for DomainStore.

All methods return None so DomainStore falls through to local JSON.
Real Linear MCP integration will be added once the MCP-from-Python
invocation approach is determined.
"""
from __future__ import annotations

from _adapters import ExternalToolAdapter, _register


@_register
class LinearAdapter(ExternalToolAdapter):
    """Stub adapter for the Linear project-management MCP tool."""

    tool_name = "linear"
