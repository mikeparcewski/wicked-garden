#!/usr/bin/env python3
"""
jira_adapter.py — Jira MCP adapter stub for DomainStore.

All methods return None so DomainStore falls through to local JSON.
Real Jira MCP integration will be added once the MCP-from-Python
invocation approach is determined.
"""
from __future__ import annotations

from _adapters import ExternalToolAdapter, _register


@_register
class JiraAdapter(ExternalToolAdapter):
    """Stub adapter for the Jira project-management MCP tool."""

    tool_name = "jira"
