#!/usr/bin/env python3
"""
_capability_resolver.py — Capability-based dynamic tool routing.

Resolves agent tool-capabilities declarations into concrete allowed-tools
lists by probing the environment for available MCP servers and CLI tools.

stdlib-only — no external dependencies. Runs during bootstrap.

Usage:
    from _capability_resolver import resolve_all_agents, discover_mcp_servers

    resolutions = resolve_all_agents(agents, config, mcp_servers)
    # resolutions: dict[str, list[str]]  # agent_name -> merged tool list
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from _capability_registry import CAPABILITY_REGISTRY, CapabilityDef, ToolOption


# ---------------------------------------------------------------------------
# Environment Probing
# ---------------------------------------------------------------------------


def probe_cli(binary: str) -> bool:
    """Check if a CLI binary is available via shutil.which().

    Returns True if the binary is found in PATH, False otherwise.
    Uses shutil.which() — no shell injection risk, no subprocess needed.
    """
    try:
        return shutil.which(binary) is not None
    except Exception:
        return False


def discover_mcp_servers() -> list[str]:
    """Scan plugin cache directories for installed MCP server names.

    Reuses the same directory traversal pattern as _probe_plugin_readiness()
    in bootstrap.py. Returns a list of server name strings.
    """
    cache_dirs: list[Path | None] = [
        Path.home() / ".claude" / "plugins" / "cache",
    ]
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        cache_dirs.append(Path(config_dir) / "plugins" / "cache")

    alt_config = Path.home() / "alt-configs" / ".claude" / "plugins" / "cache"
    if alt_config.exists():
        cache_dirs.append(alt_config)

    servers: list[str] = []
    seen_names: set[str] = set()
    for cache_dir in cache_dirs:
        if cache_dir is None or not cache_dir.exists():
            continue
        try:
            for org_dir in cache_dir.iterdir():
                if not org_dir.is_dir():
                    continue
                for plugin_dir in org_dir.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    # Read plugin.json for the server name
                    for pj_path in [
                        plugin_dir / ".claude-plugin" / "plugin.json",
                        plugin_dir / "plugin.json",
                    ]:
                        if pj_path.exists():
                            try:
                                name = json.loads(pj_path.read_text()).get(
                                    "name", plugin_dir.name
                                )
                            except Exception:
                                name = plugin_dir.name
                            if name not in seen_names:
                                seen_names.add(name)
                                servers.append(name)
                            break
        except Exception:
            continue

    return servers


def probe_environment(
    capabilities: set[str],
    mcp_servers: list[str] | None = None,
) -> dict[str, list[str]]:
    """Probe which tools are available for a set of capabilities.

    Runs detection checks (MCP pattern match, CLI probes) once per
    unique capability. Results are cached for the duration of the call.

    Args:
        capabilities: Set of capability names to probe.
        mcp_servers:  Known MCP server names (from plugin cache scan).

    Returns:
        Dict mapping capability_name -> list of available tool names.
    """
    if mcp_servers is None:
        mcp_servers = []

    mcp_pairs = [(s, s.lower()) for s in mcp_servers]  # (original, lower)
    result: dict[str, list[str]] = {}

    # Collect all CLI binaries to probe in parallel
    cli_probes: set[str] = set()  # unique binaries to probe
    for cap_name in capabilities:
        cap = CAPABILITY_REGISTRY.get(cap_name)
        if cap is None:
            continue
        for tool_opt in cap.tools:
            if tool_opt.detection.startswith("cli:"):
                binary = tool_opt.cli_binary or tool_opt.detection[4:]
                cli_probes.add(binary)

    # Parallel CLI probing with timeout protection
    cli_available: dict[str, bool] = {}
    if cli_probes:
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = {
                    pool.submit(probe_cli, binary): binary
                    for binary in cli_probes
                }
                for future in as_completed(futures, timeout=2.0):
                    binary = futures[future]
                    try:
                        cli_available[binary] = future.result(timeout=0.5)
                    except Exception:
                        cli_available[binary] = False
        except Exception:
            # Timeout or pool error — mark remaining as unavailable
            for binary in cli_probes:
                if binary not in cli_available:
                    cli_available[binary] = False

    # Resolve each capability
    for cap_name in capabilities:
        cap = CAPABILITY_REGISTRY.get(cap_name)
        if cap is None:
            result[cap_name] = []
            continue

        available: list[str] = []
        for tool_opt in cap.tools:
            if tool_opt.detection.startswith("mcp:"):
                pattern = tool_opt.detection[4:].lower()
                for original, lower in mcp_pairs:
                    if pattern in lower:
                        mcp_tool = f"mcp__{original}__*"
                        if tool_opt.name not in available:
                            available.append(tool_opt.name)
                        if mcp_tool not in available:
                            available.append(mcp_tool)
                        break

            elif tool_opt.detection.startswith("cli:"):
                binary = tool_opt.cli_binary or tool_opt.detection[4:]
                if cli_available.get(binary, False):
                    if tool_opt.name not in available:
                        available.append(tool_opt.name)

        result[cap_name] = available

    return result


# ---------------------------------------------------------------------------
# Resolution Engine
# ---------------------------------------------------------------------------


def resolve_agent(
    profile: Any,
    config: dict | None = None,
    mcp_servers: list[str] | None = None,
    *,
    _probe_cache: dict[str, list[str]] | None = None,
) -> list[str] | None:
    """Resolve tool-capabilities for a single agent.

    Args:
        profile:      AgentProfile instance.
        config:       Parsed config.json dict (for tool_preferences section).
        mcp_servers:  List of discovered MCP server name strings.
        _probe_cache: Pre-computed probe results (from resolve_all_agents).

    Returns:
        Merged tool list (deduplicated), or None if agent has no tool-capabilities.
    """
    meta = profile.metadata if hasattr(profile, "metadata") else {}
    tool_caps = meta.get("tool_capabilities", [])

    if not tool_caps:
        return None

    # Get probe results
    if _probe_cache is not None:
        probe_results = _probe_cache
    else:
        probe_results = probe_environment(set(tool_caps), mcp_servers)

    # Start with base allowed-tools
    base_tools = list(meta.get("allowed_tools_list", []))

    # Resolve each capability
    resolved_tools: list[str] = []
    preferences = (config or {}).get("tool_preferences", {})

    for cap_name in tool_caps:
        cap_def = CAPABILITY_REGISTRY.get(cap_name)
        if cap_def is None:
            print(
                f"[wicked-garden] WARNING: Unknown capability '{cap_name}' "
                f"in agent '{profile.name}'",
                file=sys.stderr,
            )
            continue

        available = list(probe_results.get(cap_name, []))

        # Apply user preference: move preferred tool to front
        pref = preferences.get(cap_name)
        if pref and available:
            # Find the preferred tool in available list
            matching = [t for t in available if pref.lower() in t.lower()]
            if matching:
                for m in reversed(matching):
                    available.remove(m)
                    available.insert(0, m)

        resolved_tools.extend(available)

        # Emit warning for required capabilities with no tools
        if cap_def.required and not available:
            hints = [
                t.install_hint for t in cap_def.tools if t.install_hint
            ]
            hint_str = " | ".join(hints) if hints else "No install hints available."
            print(
                f"[wicked-garden] WARNING: Agent '{profile.name}' declares "
                f"required capability '{cap_name}' but no tools are available. "
                f"Install one of: {hint_str}",
                file=sys.stderr,
            )

    # Merge: base_tools + resolved_tools, deduplicated, preserving order
    seen: set[str] = set()
    merged: list[str] = []
    for tool in base_tools + resolved_tools:
        if tool not in seen:
            seen.add(tool)
            merged.append(tool)

    return merged


def resolve_all_agents(
    agents: dict[str, Any],
    config: dict | None = None,
    mcp_servers: list[str] | None = None,
) -> dict[str, list[str]]:
    """Resolve tool-capabilities for all agents that declare them.

    Args:
        agents:      Dict of agent_name -> AgentProfile (from AgentLoader.all()).
        config:      Parsed config.json dict (for tool_preferences section).
        mcp_servers: List of discovered MCP server name strings.

    Returns:
        Dict mapping agent_name -> merged tool list (allowed-tools + resolved).
        Only includes agents that have tool-capabilities declared.
    """
    # 1. Collect all unique capability names
    unique_caps: set[str] = set()
    agents_with_caps: list[tuple[str, Any]] = []

    for name, profile in agents.items():
        meta = profile.metadata if hasattr(profile, "metadata") else {}
        tool_caps = meta.get("tool_capabilities", [])
        if tool_caps:
            unique_caps.update(tool_caps)
            agents_with_caps.append((name, profile))

    if not agents_with_caps:
        return {}

    # 2. Discover MCP servers if not provided
    if mcp_servers is None:
        mcp_servers = discover_mcp_servers()

    # 3. Probe environment once for all unique capabilities
    probe_results = probe_environment(unique_caps, mcp_servers)

    # 4. Resolve each agent
    resolutions: dict[str, list[str]] = {}
    for name, profile in agents_with_caps:
        result = resolve_agent(
            profile,
            config=config,
            mcp_servers=mcp_servers,
            _probe_cache=probe_results,
        )
        if result is not None:
            resolutions[name] = result

    return resolutions
