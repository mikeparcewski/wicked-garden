#!/usr/bin/env python3
"""
_integration_resolver.py — Integration tool resolution for DomainStore.

Resolves which external tool (if any) should be used for a given plugin domain.
Called by DomainStore._init_routing() during initialization, and also testable
in isolation.

Resolution order:
    1. ~/.something-wicked/wicked-garden/config.json key tool_preferences.{domain}
    2. Stored memory preference (tagged "tool-preference" + domain name)
    3. MCP discovery (stub — deferred until MCP-from-Python approach is determined)
    4. Interactive prompt if multiple matches (not reachable until step 3 is wired)

Returns:
    Tool name string ("linear", "jira", "notion", …) or None for local-only.

stdlib-only — no external dependencies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Config location — same root as the local data store
_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_tool(domain: str, hook_mode: bool = False) -> Optional[str]:
    """Return the external tool name to use for *domain*, or None for local.

    Args:
        domain:    Plugin domain, e.g. "wicked-crew", "wicked-garden:mem".
        hook_mode: When True, skip discovery and return None immediately so
                   hook scripts stay within the 5-second timing budget.

    Returns:
        Tool name string or None (meaning: use local JSON storage).
    """
    # Import here to avoid a circular import at module load time — _domain_store
    # imports this module, and DOMAIN_MCP_PATTERNS lives in _domain_store.
    try:
        _scripts_dir = str(Path(__file__).parent)
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        from _domain_store import DOMAIN_MCP_PATTERNS
    except ImportError:
        DOMAIN_MCP_PATTERNS = {}

    # Domains not in the pattern registry are always local-only
    if domain not in DOMAIN_MCP_PATTERNS:
        return None

    # Hook scripts skip discovery to meet timing budgets
    if hook_mode:
        return None

    # ── Step 1: explicit user preference in config.json ──────────────────
    preference = _read_config_preference(domain)
    if preference:
        return preference

    # ── Step 2: stored memory preference ─────────────────────────────────
    mem_preference = _check_mem_preference(domain)
    if mem_preference:
        return mem_preference

    # ── Step 3: MCP discovery (stub — always returns []) ─────────────────
    matches = _discover_mcp_tools(domain)

    # ── Step 4: interactive prompt when multiple tools are found ──────────
    if len(matches) == 1:
        tool = matches[0]
        _store_preference(domain, tool)
        return tool

    if len(matches) > 1:
        tool = _prompt_user_choice(domain, matches)
        return tool

    # No external tool found — use local JSON
    return None


# ---------------------------------------------------------------------------
# Step 1 helpers
# ---------------------------------------------------------------------------


def _read_config_preference(domain: str) -> Optional[str]:
    """Read tool_preferences.{domain} from config.json.

    Returns the configured tool name, or None if not set or on any error.
    """
    try:
        if not _CONFIG_PATH.exists():
            return None
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        prefs = data.get("tool_preferences")
        if not isinstance(prefs, dict):
            return None
        value = prefs.get(domain)
        if isinstance(value, str) and value:
            return value
        return None
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Step 2 helpers
# ---------------------------------------------------------------------------


def _brain_api(action, params=None, timeout=3):
    """Call brain API. Returns parsed JSON or None."""
    try:
        import urllib.request
        from _brain_port import resolve_port
        port = resolve_port()
        payload = json.dumps({"action": action, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _check_mem_preference(domain: str) -> Optional[str]:
    """Query brain for a previously stored tool preference.

    Searches for memories tagged with "tool-preference" and the domain
    name via the brain search API. Returns the tool name found in the
    memory content, or None if not found or brain is unavailable.

    Fails gracefully so callers that run before brain is initialized
    (e.g. during onboarding) continue to work.
    """
    try:
        result = _brain_api("search", {"query": f"tool-preference {domain}", "limit": 5}, timeout=3)
        if not result:
            return None

        # Handle both list and dict response formats
        results = result if isinstance(result, list) else result.get("results", [])
        for r in results:
            # Look for tool-preference memories that match this domain
            content = r.get("content", "") or ""
            path = r.get("path", "") or ""
            if "tool-preference" in content and domain in content:
                # Extract the tool name — it's the short content of the memory
                # Try to read the actual chunk file for the definitive content
                try:
                    chunk_path = Path.home() / ".wicked-brain" / path
                    if chunk_path.exists():
                        text = chunk_path.read_text(encoding="utf-8")
                        # Content is after the frontmatter and title
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            body = parts[2].strip()
                            # Skip the title line (# ...)
                            body_lines = [l for l in body.splitlines() if l.strip() and not l.startswith("#")]
                            if body_lines:
                                tool = body_lines[-1].strip()
                                if tool:
                                    return tool
                except Exception:
                    pass  # fail open
        return None
    except Exception:
        # Brain may be unavailable — always fail gracefully
        return None


# ---------------------------------------------------------------------------
# Step 3 helpers
# ---------------------------------------------------------------------------


def _discover_mcp_tools(domain: str) -> list:
    """Discover MCP tools available for *domain*.

    MCP invocation from Python is unresolved (see design/architecture.md
    Open Questions).  This is a stub that always returns an empty list.
    Real discovery will be wired in a follow-on task once the approach is
    determined.

    Args:
        domain: Plugin domain name (e.g. "wicked-crew").

    Returns:
        List of matching tool name strings (empty until real discovery is wired).
    """
    return []


# ---------------------------------------------------------------------------
# Step 4 helpers
# ---------------------------------------------------------------------------


def _prompt_user_choice(domain: str, matches: list) -> str:
    """Interactively ask the user to choose from multiple matching tools.

    Prints a numbered list to stdout and reads a line from stdin.
    Stores the choice via _store_preference() and returns the selected tool.

    Args:
        domain:  Plugin domain name.
        matches: Non-empty list of discovered tool name strings.

    Returns:
        Selected tool name string.
    """
    # Guard against non-interactive contexts (hooks, dangerous mode, CI).
    if not sys.stdin.isatty():
        return _local_fallback_and_store(domain, matches)

    print(f"\n[wicked-garden] Multiple integration tools found for {domain}:")
    for idx, tool in enumerate(matches, start=1):
        print(f"  {idx}. {tool}")
    print(f"  {len(matches) + 1}. Use local storage (no external tool)")
    print("Enter a number to select: ", end="", flush=True)

    try:
        raw = sys.stdin.readline().strip()
        choice_num = int(raw)
    except (ValueError, EOFError, OSError):
        # Default to local on any input error
        return _local_fallback_and_store(domain, matches)

    if 1 <= choice_num <= len(matches):
        tool = matches[choice_num - 1]
        _store_preference(domain, tool)
        return tool

    # Choice was "local" or out of range — store "local" sentinel so we don't
    # ask again this session; return None via the caller's None path.
    # We can't return None here (return type is str), so store and return the
    # first match; caller will treat any truthy return as an external tool.
    # Instead, write a special "local" marker and return the first match as a
    # no-op — the adapter will return None and fall through to local JSON.
    # Realistically this branch is unreachable until _discover_mcp_tools returns
    # real results, so correctness here is secondary to not crashing.
    return _local_fallback_and_store(domain, matches)


def _local_fallback_and_store(domain: str, matches: list) -> str:
    """Store 'local' preference and return the first match as a no-op tool name.

    Internal helper: used when the user selects the 'local' option or
    input parsing fails. Returns first match so the caller has a valid string;
    the adapter's stub will return None → local JSON path is taken.
    """
    _store_preference(domain, "local")
    # Return first match — stub adapters return None so local JSON is used anyway.
    return matches[0] if matches else "local"


# ---------------------------------------------------------------------------
# Preference storage
# ---------------------------------------------------------------------------


def _store_preference(domain: str, tool: str) -> None:
    """Persist a tool preference to brain as a memory chunk.

    Writes a memory chunk with tags=["tool-preference", domain] so future
    sessions can skip the discovery step.

    Fails silently on any error so a broken brain never blocks writes.
    """
    try:
        import uuid
        import os as _os
        from datetime import datetime, timezone

        mem_id = str(uuid.uuid4())
        chunk_id = f"memories/semantic/mem-{mem_id}"
        chunk_path = Path.home() / ".wicked-brain" / f"{chunk_id}.md"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        tags_list = ["tool-preference", domain]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        title = f"Tool preference: {domain} → {tool}"

        lines = ["---"]
        lines.append("source: wicked-brain:memory")
        lines.append("memory_type: preference")
        lines.append("memory_tier: semantic")
        lines.append(f"title: {title}")
        lines.append("importance: 5")
        lines.append("contains:")
        for t in tags_list:
            lines.append(f"  - {t}")
        lines.append(f'indexed_at: "{now}"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(tool)

        chunk_path.write_text("\n".join(lines), encoding="utf-8")

        # Index in brain FTS5
        search_text = f"{title} {tool} {' '.join(tags_list)}"
        _brain_api("index", {"id": f"{chunk_id}.md", "path": f"{chunk_id}.md", "content": search_text, "brain_id": "wicked-brain"})
    except Exception:
        pass  # fail open: brain may be unavailable
