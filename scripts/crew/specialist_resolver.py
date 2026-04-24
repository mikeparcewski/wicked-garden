#!/usr/bin/env python3
"""Specialist name resolver for the wicked-garden plugin (Issue #573).

Three naming systems used to collide for the same concept:

1. ``.claude-plugin/specialist.json`` lists 8 **domains**
   (``engineering``, ``platform``, ``product``, ``qe``, ``data``,
   ``delivery``, ``jam``, ``agentic``).
2. The facilitator rubric (``skills/propose-process/SKILL.md`` Step 4)
   picks bare **role** names like ``requirements-analyst`` or
   ``solution-architect``.
3. Actual subagents are keyed ``wicked-garden:{domain}:{role}`` — for
   example ``wicked-garden:product:requirements-analyst``.

This module is the single source of truth that bridges the three. It
walks ``agents/**/*.md``, parses the YAML-like frontmatter by simple
line scanning (stdlib only — hooks can import it), and returns lookup
maps keyed by both bare role and full subagent_type.

Public API:
    build_resolver(plugin_root: Path) -> dict
    resolve_role(role_name: str, resolver: dict) -> tuple[str, str] | tuple[None, None]

The builder is cached per ``plugin_root`` string so repeated calls from
hooks or scripts do not re-walk the agent tree.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Optional, Tuple

# The canonical subagent_type prefix used throughout the plugin. Callers
# may pass either a bare role (``requirements-analyst``) or the full
# prefixed form — the resolver handles both.
_SUBAGENT_PREFIX = "wicked-garden:"

# Frontmatter fences: a leading ``---`` starts the YAML-like block and a
# trailing ``---`` closes it. We stop at the second fence so nothing in
# the agent body can accidentally masquerade as frontmatter.
_FRONTMATTER_FENCE = "---"

# Only these two keys are consumed. We deliberately do not pull in a YAML
# library — hooks are stdlib-only, and the frontmatter in this repo is
# always a flat, top-level ``key: value`` pattern for these two fields.
_RE_NAME = re.compile(r"^name:\s*(.+?)\s*$")
_RE_SUBAGENT_TYPE = re.compile(r"^subagent_type:\s*(.+?)\s*$")


def _parse_agent_frontmatter(path: Path) -> dict:
    """Return ``{"name": ..., "subagent_type": ...}`` for an agent file.

    Missing keys are omitted from the returned dict (callers treat that
    as "skip this file"). Unreadable files return ``{}``.

    This is NOT a general YAML parser. It scans line-by-line between the
    first two ``---`` fences, matching only the two keys we care about.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return {}

    result: dict = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == _FRONTMATTER_FENCE:
            break
        name_match = _RE_NAME.match(line)
        if name_match and "name" not in result:
            result["name"] = name_match.group(1).strip()
            continue
        subagent_match = _RE_SUBAGENT_TYPE.match(line)
        if subagent_match and "subagent_type" not in result:
            result["subagent_type"] = subagent_match.group(1).strip()
            continue
    return result


def _load_domains(plugin_root: Path) -> list:
    """Return the list of specialist-domain names from specialist.json.

    Returns an empty list on any error so the resolver stays usable even
    if the manifest is briefly malformed during development.
    """
    manifest = plugin_root / ".claude-plugin" / "specialist.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names = []
    for entry in data.get("specialists", []):
        if isinstance(entry, dict) and entry.get("name"):
            names.append(entry["name"])
    return names


@functools.lru_cache(maxsize=32)
def _build_resolver_cached(plugin_root_str: str) -> dict:
    """Cached worker — keyed on the stringified plugin root."""
    plugin_root = Path(plugin_root_str)
    agents_dir = plugin_root / "agents"

    role_to_subagent: dict = {}
    role_to_domain: dict = {}
    subagent_to_role: dict = {}
    warnings: list = []

    if agents_dir.is_dir():
        # Sort for deterministic collision resolution: earlier (alphabetical
        # by path) wins, later entries become warnings. ``rglob`` order is
        # filesystem-dependent on some platforms, so we sort explicitly.
        for agent_path in sorted(agents_dir.rglob("*.md")):
            meta = _parse_agent_frontmatter(agent_path)
            name = meta.get("name")
            subagent_type = meta.get("subagent_type")
            if not name or not subagent_type:
                continue
            # The domain is the middle segment of wicked-garden:{domain}:{role}
            # — fall back to the parent directory name if the subagent_type
            # is malformed (keeps lookup working even for drifted files).
            if subagent_type.startswith(_SUBAGENT_PREFIX):
                tail = subagent_type[len(_SUBAGENT_PREFIX):]
                parts = tail.split(":", 1)
                domain = parts[0] if len(parts) == 2 else agent_path.parent.name
            else:
                domain = agent_path.parent.name

            if name in role_to_subagent:
                existing = role_to_subagent[name]
                if existing != subagent_type:
                    warnings.append(
                        f"role collision: '{name}' maps to both "
                        f"'{existing}' and '{subagent_type}' — keeping first"
                    )
                # Do not overwrite — first match wins.
                continue

            role_to_subagent[name] = subagent_type
            role_to_domain[name] = domain
            subagent_to_role[subagent_type] = name

    return {
        "role_to_subagent": role_to_subagent,
        "role_to_domain": role_to_domain,
        "subagent_to_role": subagent_to_role,
        "domains": _load_domains(plugin_root),
        "warnings": warnings,
    }


def build_resolver(plugin_root: Path) -> dict:
    """Build the resolver by walking ``agents/**/*.md`` under ``plugin_root``.

    Returns a dict with:

    * ``role_to_subagent`` — bare role -> full ``wicked-garden:{domain}:{role}``
    * ``role_to_domain`` — bare role -> domain (e.g. ``product``)
    * ``subagent_to_role`` — full subagent_type -> bare role (reverse map)
    * ``domains`` — list of specialist-domain names from ``specialist.json``
    * ``warnings`` — list of human-readable strings for collisions

    The result is cached per plugin_root string, so subsequent calls from
    the same process are O(1).
    """
    return _build_resolver_cached(str(plugin_root))


def resolve_role(
    role_name: str, resolver: dict
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(domain, subagent_type)`` for a role, or ``(None, None)``.

    Accepts either a bare role (``requirements-analyst``) or an already-
    qualified subagent_type (``wicked-garden:product:requirements-analyst``)
    — idempotent for the latter.

    Unknown roles return ``(None, None)`` without raising. Callers that
    want close-match suggestions should drive ``difflib.get_close_matches``
    off ``resolver["role_to_subagent"].keys()``.
    """
    if not role_name or not isinstance(role_name, str):
        return None, None
    role_name = role_name.strip()
    if not role_name:
        return None, None

    # Full subagent_type path: look up the bare role via the reverse map
    # and then use the forward maps for the domain. This keeps the return
    # shape consistent regardless of which form the caller passed in.
    if role_name.startswith(_SUBAGENT_PREFIX):
        bare = resolver.get("subagent_to_role", {}).get(role_name)
        if bare is None:
            return None, None
        domain = resolver.get("role_to_domain", {}).get(bare)
        if domain is None:
            return None, None
        return domain, role_name

    subagent_type = resolver.get("role_to_subagent", {}).get(role_name)
    if subagent_type is None:
        return None, None
    domain = resolver.get("role_to_domain", {}).get(role_name)
    if domain is None:
        return None, None
    return domain, subagent_type


def clear_cache() -> None:
    """Drop the module-level cache. Useful for tests that mutate agents/."""
    _build_resolver_cached.cache_clear()
