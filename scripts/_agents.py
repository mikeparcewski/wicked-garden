#!/usr/bin/env python3
"""
_agents.py — Dynamic fork-skill (worker) loader.

The plugin is skills-only: the former agents/{domain}/*.md worker definitions
now live as standalone skills at skills/<domain>-<role>/SKILL.md with
``context: fork`` frontmatter. This loader scans skills/**/SKILL.md and loads
every fork-context skill as an AgentProfile (name/domain/system_prompt/
capabilities), preserving the profile shape downstream consumers expect.

Usage:
    from _agents import AgentLoader

    loader = AgentLoader()
    loader.load_fork_skills(skills_dir)          # skills/ root
    profile = loader.get("wicked-garden-crew-implementer")
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# AgentProfile dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentProfile:
    """Normalized agent definition — common format for disk and CP sources.

    Fields:
        name:          Unique agent identifier (kebab-case).
        domain:        Domain namespace (e.g. "engineering", "platform").
        system_prompt: Full system prompt text.
        capabilities:  List of capability strings (e.g. ["code-review"]).
        traits:        List of trait strings (e.g. ["pragmatic", "concise"]).
        metadata:      Arbitrary key/value pairs; includes "source" and others.
    """

    name: str
    domain: str = ""
    system_prompt: str = ""
    capabilities: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "system_prompt": self.system_prompt,
            "capabilities": self.capabilities,
            "traits": self.traits,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# AgentLoader
# ---------------------------------------------------------------------------


class AgentLoader:
    """Load and retrieve worker (fork-skill) profiles from disk.

    Lifecycle (called once in bootstrap.py):
        loader = AgentLoader()
        loader.load_fork_skills(skills_dir)
        profile = loader.get("wicked-garden-crew-implementer")
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_fork_skills(self, skills_dir: Path) -> dict[str, AgentProfile]:
        """Scan skills_dir recursively for SKILL.md files declaring
        ``context: fork`` and load each as an AgentProfile.

        Each SKILL.md must have YAML frontmatter with at least a `name`
        field. Additional recognized frontmatter keys: domain, description,
        capabilities (list), traits (list), model, color, effort, max-turns,
        allowed-tools, tool-capabilities.

        The body of the SKILL.md (after frontmatter) becomes system_prompt.

        Args:
            skills_dir: Path to the skills/ directory (may contain subdirs).

        Returns:
            Dict mapping skill name -> AgentProfile. Also stored internally.
        """
        if not skills_dir.exists():
            return {}

        for md_file in sorted(skills_dir.rglob("SKILL.md")):
            profile = _parse_agent_md(md_file, fork_only=True)
            if profile is None:
                continue
            self._agents[profile.name] = profile

        return dict(self._agents)

    def load_disk_agents(self, agents_dir: Path) -> dict[str, AgentProfile]:
        """Deprecated compatibility alias for :meth:`load_fork_skills`.

        The agents/ directory no longer exists; workers are context:fork
        skills. Callers passing the old agents/ path get an empty dict
        (the dir is gone); callers passing skills/ get fork-skill profiles.
        """
        return self.load_fork_skills(agents_dir)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, name: str) -> AgentProfile | None:
        """Look up an agent by name.

        Args:
            name: Agent name (kebab-case, e.g. "senior-engineer").

        Returns:
            AgentProfile, or None if no agent with that name is loaded.
        """
        return self._agents.get(name)

    def all(self) -> dict[str, AgentProfile]:
        """Return a shallow copy of all loaded agents."""
        return dict(self._agents)

    def count(self) -> int:
        return len(self._agents)

    def serialize(self) -> list[dict]:
        """Serialize all agents to a JSON-safe list (for session state file)."""
        return [p.to_dict() for p in self._agents.values()]

    @classmethod
    def deserialize(cls, data: list[dict]) -> "AgentLoader":
        """Reconstruct an AgentLoader from a previously serialized list."""
        loader = cls()
        for rec in data:
            name = rec.get("name")
            if not name:
                continue
            loader._agents[name] = AgentProfile(
                name=name,
                domain=rec.get("domain", ""),
                system_prompt=rec.get("system_prompt", ""),
                capabilities=rec.get("capabilities") or [],
                traits=rec.get("traits") or [],
                metadata=rec.get("metadata") or {},
            )
        return loader


# ---------------------------------------------------------------------------
# Markdown frontmatter parser (stdlib-only, no PyYAML)
# ---------------------------------------------------------------------------

_FRONTMATTER_START = "---"
_FRONTMATTER_END = "---"


def _parse_agent_md(path: Path, fork_only: bool = False) -> AgentProfile | None:
    """Parse a worker SKILL.md (context: fork) into an AgentProfile.

    Format:
        ---
        name: wicked-garden-crew-implementer
        description: |
          Optional description
        context: fork                # required when fork_only=True
        domain: engineering          # optional
        capabilities:                # optional list
          - code-review
        traits:                      # optional list
          - pragmatic
        model: sonnet                # stored in metadata
        color: blue                  # stored in metadata
        ---

        # Skill Title

        System prompt body...

    Returns:
        AgentProfile, or None if the file lacks a valid name field or
        (when fork_only) does not declare ``context: fork``.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter, body = _split_frontmatter(raw)
    if frontmatter is None:
        if fork_only:
            # A worker must declare context: fork in frontmatter
            return None
        # No frontmatter — use filename as name, whole file as system_prompt
        name = path.stem
        domain = _infer_domain(path)
        return AgentProfile(
            name=name,
            domain=domain,
            system_prompt=raw.strip(),
            metadata={"source": "disk", "file": str(path)},
        )

    parsed = _parse_simple_yaml(frontmatter)
    if fork_only and parsed.get("context") != "fork":
        return None
    name = parsed.get("name") or (path.parent.name if path.name == "SKILL.md" else path.stem)
    if not name:
        return None

    domain = parsed.get("domain") or _infer_domain(path)

    # Build metadata from remaining frontmatter keys
    metadata_keys = {"model", "color", "version", "author", "allowed-tools",
                     "context", "subagent_type", "effort", "max-turns"}
    extra_meta = {k: v for k, v in parsed.items() if k in metadata_keys}
    extra_meta["source"] = "disk"
    extra_meta["file"] = str(path)

    # Extract tool-capabilities for capability-based dynamic tool routing
    tool_caps = _to_list(parsed.get("tool-capabilities"))
    if tool_caps:
        extra_meta["tool_capabilities"] = tool_caps

    # Parse allowed-tools into a list for the resolver
    allowed_tools_list = _to_list(parsed.get("allowed-tools"))
    if allowed_tools_list:
        extra_meta["allowed_tools_list"] = allowed_tools_list

    return AgentProfile(
        name=name,
        domain=domain,
        system_prompt=body.strip(),
        capabilities=_to_list(parsed.get("capabilities")),
        traits=_to_list(parsed.get("traits")),
        metadata=extra_meta,
    )


def _split_frontmatter(raw: str) -> tuple[str | None, str]:
    """Split raw markdown into (frontmatter, body).

    Returns (None, raw) if no YAML frontmatter block is found.
    """
    lines = raw.split("\n")
    if not lines or lines[0].strip() != _FRONTMATTER_START:
        return None, raw

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_END:
            end_idx = i
            break

    if end_idx is None:
        return None, raw

    frontmatter = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    return frontmatter, body


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML parser for Claude Code agent frontmatter.

    Handles the subset of YAML used in agent files:
        - key: scalar_value
        - key: |
            multi-line block (dedented)
        - key:
            - list_item_1
            - list_item_2

    Does NOT handle nested dicts, anchors, or other YAML features.
    """
    result: dict[str, Any] = {}
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip blank lines and comments
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        # Key: value or Key:
        if ":" not in line:
            i += 1
            continue

        key_part, _, value_part = line.partition(":")
        key = key_part.strip()
        value = value_part.strip()

        if not key:
            i += 1
            continue

        # Block scalar (|)
        if value == "|":
            block_lines: list[str] = []
            i += 1
            while i < len(lines):
                bl = lines[i]
                # Block ends when we hit a line at root indentation (no leading space)
                if bl and not bl.startswith(" ") and not bl.startswith("\t"):
                    break
                block_lines.append(bl)
                i += 1
            result[key] = "\n".join(line.rstrip() for line in block_lines).strip()
            continue

        # Inline list (next lines starting with "  -")
        if value == "":
            list_items: list[str] = []
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate.startswith("- "):
                    list_items.append(candidate[2:].strip())
                    j += 1
                elif candidate == "-":
                    list_items.append("")
                    j += 1
                else:
                    break
            if list_items:
                result[key] = list_items
                i = j
                continue

        # Plain scalar — strip surrounding quotes
        if value.startswith(('"', "'")):
            value = value[1:-1] if len(value) > 1 and value[-1] == value[0] else value
        result[key] = value
        i += 1

    return result


# Known plugin domains (mirrors .claude-plugin/components.json "domains")
_DOMAINS = ("agentic", "crew", "data", "engineering", "jam", "mem", "persona",
            "platform", "product", "qe", "search", "smaht")


def _infer_domain(path: Path) -> str:
    """Infer domain from a skills path.

    skills/<domain>/.../SKILL.md            -> <domain>
    skills/<domain>-<role>/SKILL.md         -> <domain>   (fork workers)
    Anything else                           -> the top-level skills/ segment.
    """
    parts = path.parts
    for idx, part in enumerate(parts):
        if part == "skills" and idx + 2 < len(parts):
            seg = parts[idx + 1]
            for d in _DOMAINS:
                if seg == d or seg.startswith(d + "-"):
                    return d
            return seg
    return ""


def _to_list(value: Any) -> list[str]:
    """Normalize a YAML value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        # Comma-separated or single value
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value.strip()] if value.strip() else []
    return []
