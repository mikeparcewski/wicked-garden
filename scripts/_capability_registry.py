#!/usr/bin/env python3
"""
_capability_registry.py — Registry of capabilities that need runtime discovery.

Only lists capabilities where tools must be PROBED at runtime (MCP servers,
CLI binaries). Built-in Claude Code tools (Read, Write, Edit, Grep, Glob,
Bash, WebFetch, WebSearch, Task) are always available and known to the
model — they don't belong here.

stdlib-only — no external dependencies.

Usage:
    from _capability_registry import CAPABILITY_REGISTRY, CapabilityDef, ToolOption
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolOption:
    """A tool that requires runtime detection to confirm availability."""

    name: str  # Tool name as it appears in allowed-tools
    detection: str  # "mcp:{pattern}" | "cli:{binary}"
    mcp_pattern: str = ""  # Substring match against MCP server names
    cli_binary: str = ""  # Binary name for shutil.which() probe
    priority: int = 100  # Lower = preferred (user prefs override)
    install_hint: str = ""  # Shown when required capability is missing


@dataclass
class CapabilityDef:
    """A capability that requires runtime environment probing."""

    name: str  # kebab-case capability name
    description: str  # Human-readable purpose
    tools: list[ToolOption] = field(default_factory=list)  # Probeable tool options
    required: bool = False  # If True, warn when no tool available


# ---------------------------------------------------------------------------
# Registry — only capabilities that need runtime discovery
# ---------------------------------------------------------------------------

CAPABILITY_REGISTRY: dict[str, CapabilityDef] = {
    "project-management": CapabilityDef(
        name="project-management",
        description="Track tasks and issues via Jira, Linear, or GitHub Issues MCP servers.",
        tools=[
            ToolOption(
                name="mcp__jira__*",
                detection="mcp:jira",
                mcp_pattern="jira",
                priority=50,
                install_hint="Configure a Jira MCP server for project management.",
            ),
            ToolOption(
                name="mcp__linear__*",
                detection="mcp:linear",
                mcp_pattern="linear",
                priority=50,
                install_hint="Configure a Linear MCP server for project management.",
            ),
            ToolOption(
                name="mcp__github__*",
                detection="mcp:github",
                mcp_pattern="github",
                priority=60,
                install_hint="Configure the GitHub MCP server for issue tracking.",
            ),
        ],
    ),
    "security-scanning": CapabilityDef(
        name="security-scanning",
        description="Scan code for vulnerabilities via Semgrep, Snyk, or Trivy.",
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
    ),
    "error-tracking": CapabilityDef(
        name="error-tracking",
        description="Monitor errors and system health via Sentry or Datadog MCP servers.",
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
    ),
    "documentation": CapabilityDef(
        name="documentation",
        description="Access external documentation via Confluence or Notion MCP servers.",
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
    ),
    "version-control": CapabilityDef(
        name="version-control",
        description="GitHub/GitLab integration via CLI or MCP server.",
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
    ),
    "ci-cd": CapabilityDef(
        name="ci-cd",
        description="CI/CD pipeline interaction via GitHub Actions, GitLab CI, or CircleCI.",
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
    ),
    "data-query": CapabilityDef(
        name="data-query",
        description="Query databases via DuckDB, PostgreSQL, or data MCP servers.",
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
    ),
    "apm": CapabilityDef(
        name="apm",
        description="Application performance monitoring via Datadog, New Relic, or Grafana.",
        tools=[
            ToolOption(
                name="mcp__datadog__*",
                detection="mcp:datadog",
                mcp_pattern="datadog",
                priority=40,
                install_hint="Configure a Datadog MCP server for APM.",
            ),
            ToolOption(
                name="mcp__newrelic__*",
                detection="mcp:newrelic",
                mcp_pattern="newrelic",
                priority=45,
                install_hint="Configure a New Relic MCP server for APM.",
            ),
            ToolOption(
                name="mcp__grafana__*",
                detection="mcp:grafana",
                mcp_pattern="grafana",
                priority=50,
                install_hint="Configure a Grafana MCP server for APM dashboards.",
            ),
        ],
    ),
    "tracing": CapabilityDef(
        name="tracing",
        description="Distributed tracing via Honeycomb, Grafana Tempo, or Datadog.",
        tools=[
            ToolOption(
                name="mcp__honeycomb__*",
                detection="mcp:honeycomb",
                mcp_pattern="honeycomb",
                priority=40,
                install_hint="Configure a Honeycomb MCP server for distributed tracing.",
            ),
            ToolOption(
                name="mcp__grafana__*",
                detection="mcp:grafana",
                mcp_pattern="grafana",
                priority=50,
                install_hint="Configure a Grafana MCP server (Tempo) for tracing.",
            ),
            ToolOption(
                name="mcp__datadog__*",
                detection="mcp:datadog",
                mcp_pattern="datadog",
                priority=50,
                install_hint="Configure a Datadog MCP server for tracing.",
            ),
        ],
    ),
    "logging": CapabilityDef(
        name="logging",
        description="Log aggregation and search via Grafana Loki, Datadog, or Elasticsearch.",
        tools=[
            ToolOption(
                name="mcp__grafana__*",
                detection="mcp:grafana",
                mcp_pattern="grafana",
                priority=45,
                install_hint="Configure a Grafana MCP server (Loki) for log search.",
            ),
            ToolOption(
                name="mcp__datadog__*",
                detection="mcp:datadog",
                mcp_pattern="datadog",
                priority=45,
                install_hint="Configure a Datadog MCP server for log search.",
            ),
            ToolOption(
                name="mcp__elasticsearch__*",
                detection="mcp:elastic",
                mcp_pattern="elastic",
                priority=55,
                install_hint="Configure an Elasticsearch MCP server for log search.",
            ),
        ],
    ),
    "telemetry": CapabilityDef(
        name="telemetry",
        description="OpenTelemetry and metrics pipelines via Grafana, Prometheus, or OTel tooling.",
        tools=[
            ToolOption(
                name="mcp__grafana__*",
                detection="mcp:grafana",
                mcp_pattern="grafana",
                priority=45,
                install_hint="Configure a Grafana MCP server for metrics.",
            ),
            ToolOption(
                name="mcp__prometheus__*",
                detection="mcp:prometheus",
                mcp_pattern="prometheus",
                priority=50,
                install_hint="Configure a Prometheus MCP server for metrics.",
            ),
            ToolOption(
                name="otel",
                detection="cli:otel",
                cli_binary="otel",
                priority=70,
                install_hint="Install the OpenTelemetry CLI (otel).",
            ),
        ],
    ),
}
