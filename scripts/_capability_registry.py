#!/usr/bin/env python3
"""
_capability_registry.py — Registry of capability definitions for dynamic tool routing.

Maps capability names to CapabilityDef entries. Each entry defines the tools
that satisfy the capability, how to detect them, and fallback behavior.

stdlib-only — no external dependencies.

Usage:
    from _capability_registry import CAPABILITY_REGISTRY, CapabilityDef, ToolOption
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolOption:
    """A concrete tool that can satisfy a capability."""

    name: str  # Tool name as it appears in allowed-tools
    detection: str  # "always" | "mcp:{pattern}" | "cli:{binary}"
    mcp_pattern: str = ""  # Substring match against MCP server names
    cli_binary: str = ""  # Binary name for shutil.which() probe
    priority: int = 100  # Lower = preferred (user prefs override)
    install_hint: str = ""  # Shown when required capability is missing


@dataclass
class CapabilityDef:
    """Definition of a single capability in the registry."""

    name: str  # kebab-case capability name
    description: str  # Human-readable purpose
    tools: list[ToolOption] = field(default_factory=list)  # Ordered tool options
    required: bool = False  # If True, warn when no tool available
    fallback_tools: list[str] = field(default_factory=list)  # Always-available tools


# ---------------------------------------------------------------------------
# Complete Registry (12 capabilities)
# ---------------------------------------------------------------------------

CAPABILITY_REGISTRY: dict[str, CapabilityDef] = {
    "code-search": CapabilityDef(
        name="code-search",
        description="Search and navigate codebases — symbol lookup, pattern matching, file discovery.",
        tools=[
            ToolOption(name="Grep", detection="always", priority=10),
            ToolOption(name="Glob", detection="always", priority=10),
            ToolOption(
                name="mcp__semgrep-plugin__semgrep",
                detection="mcp:semgrep",
                mcp_pattern="semgrep",
                priority=50,
                install_hint="Install the Semgrep Claude Code plugin for advanced code search.",
            ),
        ],
        fallback_tools=["Grep", "Glob"],
    ),
    "code-edit": CapabilityDef(
        name="code-edit",
        description="Read, write, and edit source files.",
        tools=[
            ToolOption(name="Read", detection="always", priority=10),
            ToolOption(name="Write", detection="always", priority=10),
            ToolOption(name="Edit", detection="always", priority=10),
        ],
        fallback_tools=["Read", "Write", "Edit"],
    ),
    "code-execution": CapabilityDef(
        name="code-execution",
        description="Execute shell commands and scripts.",
        tools=[
            ToolOption(name="Bash", detection="always", priority=10),
        ],
        fallback_tools=["Bash"],
    ),
    "web-access": CapabilityDef(
        name="web-access",
        description="Fetch web pages and search the internet.",
        tools=[
            ToolOption(name="WebFetch", detection="always", priority=10),
            ToolOption(name="WebSearch", detection="always", priority=10),
        ],
        fallback_tools=["WebFetch", "WebSearch"],
    ),
    "project-management": CapabilityDef(
        name="project-management",
        description="Track tasks, issues, and project work across tools like Jira, Linear, and GitHub Issues.",
        tools=[
            ToolOption(
                name="mcp__jira__*",
                detection="mcp:jira",
                mcp_pattern="jira",
                priority=50,
                install_hint="Configure a Jira MCP server for project management integration.",
            ),
            ToolOption(
                name="mcp__linear__*",
                detection="mcp:linear",
                mcp_pattern="linear",
                priority=50,
                install_hint="Configure a Linear MCP server for project management integration.",
            ),
            ToolOption(
                name="mcp__github__*",
                detection="mcp:github",
                mcp_pattern="github",
                priority=60,
                install_hint="Configure the GitHub MCP server for issue tracking.",
            ),
        ],
        # Strategy gate: add kanban and search as fallbacks
        fallback_tools=["Bash", "Grep"],
    ),
    "security-scanning": CapabilityDef(
        name="security-scanning",
        description="Scan code for vulnerabilities, secrets, and security issues.",
        tools=[
            ToolOption(
                name="mcp__semgrep-plugin__semgrep",
                detection="mcp:semgrep",
                mcp_pattern="semgrep",
                priority=30,
                install_hint="pip install semgrep && semgrep login",
            ),
            ToolOption(
                name="snyk",
                detection="cli:snyk",
                cli_binary="snyk",
                priority=50,
                install_hint="npm install -g snyk && snyk auth",
            ),
            ToolOption(
                name="trivy",
                detection="cli:trivy",
                cli_binary="trivy",
                priority=50,
                install_hint="brew install aquasecurity/trivy/trivy",
            ),
        ],
        # Fallback: Grep + Bash for manual pattern-based security checks
        fallback_tools=["Grep", "Bash"],
    ),
    "error-tracking": CapabilityDef(
        name="error-tracking",
        description="Monitor errors, exceptions, and system health via Sentry, Datadog, or log search.",
        tools=[
            ToolOption(
                name="mcp__sentry__*",
                detection="mcp:sentry",
                mcp_pattern="sentry",
                priority=40,
                install_hint="Configure a Sentry MCP server for error tracking.",
            ),
            ToolOption(
                name="mcp__datadog__*",
                detection="mcp:datadog",
                mcp_pattern="datadog",
                priority=40,
                install_hint="Configure a Datadog MCP server for error tracking.",
            ),
        ],
        # Strategy gate: search fallback for log-based error tracking
        fallback_tools=["Grep", "Bash"],
    ),
    "documentation": CapabilityDef(
        name="documentation",
        description="Access and manage documentation in Confluence, Notion, or local search.",
        tools=[
            ToolOption(
                name="mcp__confluence__*",
                detection="mcp:confluence",
                mcp_pattern="confluence",
                priority=40,
                install_hint="Configure a Confluence MCP server for documentation access.",
            ),
            ToolOption(
                name="mcp__notion__*",
                detection="mcp:notion",
                mcp_pattern="notion",
                priority=40,
                install_hint="Configure a Notion MCP server for documentation access.",
            ),
        ],
        # Strategy gate: search fallback for local doc search
        fallback_tools=["Grep", "Glob"],
    ),
    "version-control": CapabilityDef(
        name="version-control",
        description="Interact with version control systems — commits, PRs, branches.",
        tools=[
            ToolOption(
                name="gh",
                detection="cli:gh",
                cli_binary="gh",
                priority=30,
                install_hint="brew install gh && gh auth login",
            ),
            ToolOption(
                name="glab",
                detection="cli:glab",
                cli_binary="glab",
                priority=40,
                install_hint="brew install glab && glab auth login",
            ),
            ToolOption(
                name="mcp__github__*",
                detection="mcp:github",
                mcp_pattern="github",
                priority=50,
            ),
            ToolOption(
                name="mcp__gitlab__*",
                detection="mcp:gitlab",
                mcp_pattern="gitlab",
                priority=50,
            ),
        ],
        # Fallback: Bash for git commands (always available)
        fallback_tools=["Bash"],
    ),
    "ci-cd": CapabilityDef(
        name="ci-cd",
        description="Interact with CI/CD pipelines — GitHub Actions, GitLab CI, CircleCI.",
        tools=[
            ToolOption(
                name="mcp__github__*",
                detection="mcp:github",
                mcp_pattern="github",
                priority=40,
            ),
            ToolOption(
                name="mcp__gitlab__*",
                detection="mcp:gitlab",
                mcp_pattern="gitlab",
                priority=40,
            ),
            ToolOption(
                name="circleci",
                detection="cli:circleci",
                cli_binary="circleci",
                priority=60,
                install_hint="brew install circleci",
            ),
        ],
        # Fallback: Bash for reading CI config files and gh/glab CLI
        fallback_tools=["Bash", "Grep"],
    ),
    "subagent-dispatch": CapabilityDef(
        name="subagent-dispatch",
        description="Dispatch work to subagents via the Task tool.",
        tools=[
            ToolOption(name="Task", detection="always", priority=10),
        ],
        fallback_tools=["Task"],
    ),
    "data-query": CapabilityDef(
        name="data-query",
        description="Query databases and data stores — DuckDB, PostgreSQL, data MCP servers.",
        tools=[
            ToolOption(
                name="mcp__duckdb__*",
                detection="mcp:duckdb",
                mcp_pattern="duckdb",
                priority=40,
                install_hint="Configure a DuckDB MCP server for data querying.",
            ),
            ToolOption(
                name="duckdb",
                detection="cli:duckdb",
                cli_binary="duckdb",
                priority=50,
                install_hint="brew install duckdb",
            ),
            ToolOption(
                name="psql",
                detection="cli:psql",
                cli_binary="psql",
                priority=60,
                install_hint="brew install postgresql",
            ),
        ],
        # Fallback: Bash for running query commands
        fallback_tools=["Bash"],
    ),
}
