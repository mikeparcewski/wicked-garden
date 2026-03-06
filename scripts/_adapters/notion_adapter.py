#!/usr/bin/env python3
"""
notion_adapter.py — Notion MCP adapter stub for DomainStore.

All methods return None so DomainStore falls through to local JSON.
Real Notion MCP integration will be added once the MCP-from-Python
invocation approach is determined.
"""
from __future__ import annotations

from _adapters import ExternalToolAdapter, _register


@_register
class NotionAdapter(ExternalToolAdapter):
    """Stub adapter for the Notion knowledge-management MCP tool."""

    tool_name = "notion"
