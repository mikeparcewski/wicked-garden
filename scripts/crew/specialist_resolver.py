#!/usr/bin/env python3
"""Specialist name resolver for the wicked-garden plugin (Issue #573).

Three naming systems used to collide for the same concept:

1. ``.claude-plugin/specialist.json`` lists the **domains**
   (``engineering``, ``platform``, ``product``, ``qe``, ``data``,
   ``jam``, ``agentic``).
2. The facilitator rubric (``skills/propose-process/SKILL.md`` Step 4)
   picks bare **role** names like ``requirements-analyst`` or
   ``solution-architect``.
3. Actual workers are **context:fork skills** named
   ``wicked-garden-{domain}-{role}`` — for example
   ``wicked-garden-product-requirements-analyst`` at
   ``skills/product-requirements-analyst/SKILL.md``. (Before the
   skills-only cutover these were agents keyed
   ``wicked-garden:{domain}:{role}``; some fork skills still carry that
   legacy ``subagent_type`` in frontmatter for compatibility.)

This module is the single source of truth that bridges the three. It
walks ``skills/**/SKILL.md``, keeps only files declaring
``context: fork``, parses the YAML-like frontmatter by simple line
scanning (stdlib only — hooks can import it), and returns lookup maps
keyed by bare role, dash-named skill, and legacy colon subagent_type.

Public API:
    build_resolver(plugin_root: Path) -> dict
    resolve_role(role_name: str, resolver: dict) -> tuple[str, str] | tuple[None, None]

``resolve_role`` returns ``(domain, skill_name)`` where ``skill_name``
is the dispatchable fork-skill name (``wicked-garden-{domain}-{role}``).

The builder is cached per ``plugin_root`` string so repeated calls from
hooks or scripts do not re-walk the skills tree.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Optional, Tuple

# Legacy colon prefix (pre-skills-only subagent_type namespace). Callers
# may still pass ``wicked-garden:{domain}:{role}`` identifiers from old
# payloads — the resolver maps them to the fork-skill name.
_SUBAGENT_PREFIX = "wicked-garden:"

# Canonical dash prefix of fork-skill names.
_SKILL_PREFIX = "wicked-garden-"

# Known plugin domains (mirrors .claude-plugin/components.json "domains").
# Used to split ``{domain}-{role}`` skill names deterministically.
_DOMAINS = ("agentic", "crew", "data", "engineering", "jam", "mem", "persona",
            "platform", "product", "qe", "search", "smaht")

# Frontmatter fences: a leading ``---`` starts the YAML-like block and a
# trailing ``---`` closes it. We stop at the second fence so nothing in
# the skill body can accidentally masquerade as frontmatter.
_FRONTMATTER_FENCE = "---"

# Only these three keys are consumed. We deliberately do not pull in a YAML
# library — hooks are stdlib-only, and the frontmatter in this repo is
# always a flat, top-level ``key: value`` pattern for these fields.
_RE_NAME = re.compile(r"^name:\s*(.+?)\s*$")
_RE_SUBAGENT_TYPE = re.compile(r"^subagent_type:\s*(.+?)\s*$")
_RE_CONTEXT = re.compile(r"^context:\s*(.+?)\s*$")


def _parse_skill_frontmatter(path: Path) -> dict:
    """Return ``{"name": ..., "subagent_type": ..., "context": ...}``.

    Missing keys are omitted from the returned dict (callers treat that
    as "skip this file"). Unreadable files return ``{}``.

    This is NOT a general YAML parser. It scans line-by-line between the
    first two ``---`` fences, matching only the keys we care about.
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
        context_match = _RE_CONTEXT.match(line)
        if context_match and "context" not in result:
            result["context"] = context_match.group(1).strip()
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


def _split_domain_role(skill_name: str, legacy_subagent_type: str) -> Tuple[str, str]:
    """Derive ``(domain, bare_role)`` for a fork skill.

    Preference order:
    1. Legacy ``subagent_type: wicked-garden:{domain}:{role}`` frontmatter
       (authoritative where present — kept for compatibility).
    2. The dash-named skill: ``wicked-garden-{domain}-{role}`` split against
       the known domain list.
    3. Fallback: no domain, whole tail is the role.
    """
    if legacy_subagent_type.startswith(_SUBAGENT_PREFIX):
        tail = legacy_subagent_type[len(_SUBAGENT_PREFIX):]
        parts = tail.split(":", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]

    tail = skill_name[len(_SKILL_PREFIX):] if skill_name.startswith(_SKILL_PREFIX) else skill_name
    for domain in _DOMAINS:
        if tail.startswith(domain + "-"):
            return domain, tail[len(domain) + 1:]
        if tail == domain:
            return domain, tail
    return "", tail


@functools.lru_cache(maxsize=32)
def _build_resolver_cached(plugin_root_str: str) -> dict:
    """Cached worker — keyed on the stringified plugin root."""
    plugin_root = Path(plugin_root_str)
    skills_dir = plugin_root / "skills"

    role_to_skill: dict = {}
    role_to_domain: dict = {}
    skill_to_role: dict = {}
    subagent_to_role: dict = {}
    warnings: list = []

    if skills_dir.is_dir():
        # Sort for deterministic collision resolution: earlier (alphabetical
        # by path) wins, later entries become warnings. ``rglob`` order is
        # filesystem-dependent on some platforms, so we sort explicitly.
        for skill_path in sorted(skills_dir.rglob("SKILL.md")):
            meta = _parse_skill_frontmatter(skill_path)
            if meta.get("context") != "fork":
                continue  # only fork-context skills are dispatchable workers
            skill_name = meta.get("name")
            if not skill_name:
                continue
            legacy_subagent_type = meta.get("subagent_type", "")
            domain, role = _split_domain_role(skill_name, legacy_subagent_type)
            if not role:
                continue

            if role in role_to_skill:
                existing = role_to_skill[role]
                if existing != skill_name:
                    warnings.append(
                        f"role collision: '{role}' maps to both "
                        f"'{existing}' and '{skill_name}' — keeping first"
                    )
                # Do not overwrite — first match wins.
                continue

            role_to_skill[role] = skill_name
            role_to_domain[role] = domain
            skill_to_role[skill_name] = role
            if legacy_subagent_type:
                subagent_to_role.setdefault(legacy_subagent_type, role)

    return {
        # role -> dispatchable fork-skill name (dash form). The key keeps
        # its historical name so existing consumers don't break; the value
        # space changed from colon subagent_type to skill names.
        "role_to_subagent": role_to_skill,
        "role_to_skill": role_to_skill,
        "role_to_domain": role_to_domain,
        "skill_to_role": skill_to_role,
        # legacy colon subagent_type -> role (only where a fork skill kept
        # the legacy frontmatter key), plus skill name -> role.
        "subagent_to_role": {**subagent_to_role, **skill_to_role},
        "domains": _load_domains(plugin_root),
        "warnings": warnings,
    }


def build_resolver(plugin_root: Path) -> dict:
    """Build the resolver by walking ``skills/**/SKILL.md`` under ``plugin_root``.

    Only skills declaring ``context: fork`` are indexed (they are the
    dispatchable workers — the former agents/). Returns a dict with:

    * ``role_to_skill`` — bare role -> fork-skill name
      (``wicked-garden-{domain}-{role}``)
    * ``role_to_subagent`` — alias of ``role_to_skill`` (historical key)
    * ``role_to_domain`` — bare role -> domain (e.g. ``product``)
    * ``skill_to_role`` — fork-skill name -> bare role (reverse map)
    * ``subagent_to_role`` — legacy ``wicked-garden:{domain}:{role}``
      identifiers AND skill names -> bare role
    * ``domains`` — list of specialist-domain names from ``specialist.json``
    * ``warnings`` — list of human-readable strings for collisions

    The result is cached per plugin_root string, so subsequent calls from
    the same process are O(1).
    """
    return _build_resolver_cached(str(plugin_root))


def resolve_role(
    role_name: str, resolver: dict
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(domain, skill_name)`` for a role, or ``(None, None)``.

    Accepts a bare role (``requirements-analyst``), a fork-skill name
    (``wicked-garden-product-requirements-analyst``), or a legacy colon
    subagent_type (``wicked-garden:product:requirements-analyst``) —
    all resolve to the dispatchable fork-skill name.

    Unknown roles return ``(None, None)`` without raising. Callers that
    want close-match suggestions should drive ``difflib.get_close_matches``
    off ``resolver["role_to_skill"].keys()``.
    """
    if not role_name or not isinstance(role_name, str):
        return None, None
    role_name = role_name.strip()
    if not role_name:
        return None, None

    # Qualified identifiers (legacy colon form or dash skill name): map
    # back to the bare role via the reverse map, then use the forward
    # maps so the return shape is consistent for every input form.
    if role_name.startswith(_SUBAGENT_PREFIX) or role_name.startswith(_SKILL_PREFIX):
        bare = resolver.get("subagent_to_role", {}).get(role_name)
        if bare is None:
            return None, None
        role_name = bare

    skill_name = resolver.get("role_to_skill", resolver.get("role_to_subagent", {})).get(role_name)
    if skill_name is None:
        return None, None
    domain = resolver.get("role_to_domain", {}).get(role_name)
    if domain is None:
        return None, None
    return domain, skill_name


def clear_cache() -> None:
    """Drop the module-level cache. Useful for tests that mutate skills/."""
    _build_resolver_cached.cache_clear()
