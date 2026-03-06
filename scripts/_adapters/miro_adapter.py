#!/usr/bin/env python3
"""
miro_adapter.py — Miro MCP adapter stub for DomainStore.

All methods return None so DomainStore falls through to local JSON.
Real Miro MCP integration will be added once the MCP-from-Python
invocation approach is determined.
"""
from __future__ import annotations

from _adapters import ExternalToolAdapter, _register


@_register
class MiroAdapter(ExternalToolAdapter):
    """Stub adapter for the Miro whiteboard/brainstorming MCP tool."""

    tool_name = "miro"
