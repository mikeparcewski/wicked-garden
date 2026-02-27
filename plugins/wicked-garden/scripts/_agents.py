#!/usr/bin/env python3
"""
_agents.py — Dynamic agent loader.

Merges two sources of agent definitions:
    1. Disk agents: agents/{domain}/*.md files shipped with the plugin.
       Always available regardless of connectivity.
    2. Control plane agents: JSON records from GET /api/v1/data/wicked-agents/list.
       Overlay and extend disk agents; CP wins on any field conflict.

Merge strategy (CP wins):
    - system_prompt, capabilities, traits from CP replace disk values.
    - metadata is deep-merged; CP keys win on conflict.
    - Net-new CP agents (not on disk) are added to the merged set.

Usage:
    from _agents import AgentLoader

    loader = AgentLoader(agents_dir=Path("agents/"))
    loader.load_disk_agents(agents_dir)
    loader.overlay_cp_agents(cp_agents_list)
    profile = loader.get("senior-engineer")
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
    """Load, merge, and retrieve agent profiles.

    Lifecycle (called once in bootstrap.py):
        loader = AgentLoader()
        loader.load_disk_agents(agents_dir)     # always succeeds
        loader.overlay_cp_agents(cp_agents)     # may be [] if offline
        profile = loader.get("senior-engineer")
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_disk_agents(self, agents_dir: Path) -> dict[str, AgentProfile]:
        """Scan agents_dir recursively for *.md agent files and load them.

        Each markdown file must have YAML frontmatter with at least a `name`
        field. Additional recognized frontmatter keys: domain, description,
        capabilities (list), traits (list), model, color.

        The body of the markdown file (after frontmatter) becomes system_prompt.

        Args:
            agents_dir: Path to the agents/ directory (may contain subdirs).

        Returns:
            Dict mapping agent name -> AgentProfile. Also stored internally.
        """
        if not agents_dir.exists():
            return {}

        for md_file in sorted(agents_dir.rglob("*.md")):
            profile = _parse_agent_md(md_file)
            if profile is None:
                continue
            self._agents[profile.name] = profile

        return dict(self._agents)

    def overlay_cp_agents(self, cp_agents: list[dict]) -> None:
        """Merge control plane agent records over the current disk agents.

        CP records win on all named fields. metadata is deep-merged.

        Args:
            cp_agents: List of agent dicts from the control plane API.
                       May be empty (offline / no CP agents defined).
        """
        for cp_rec in cp_agents:
            name = cp_rec.get("name")
            if not name:
                continue

            if name in self._agents:
                # Overlay: CP fields win, metadata is deep-merged
                existing = self._agents[name]
                existing.system_prompt = cp_rec.get("system_prompt") or existing.system_prompt
                existing.capabilities = cp_rec.get("capabilities") or existing.capabilities
                existing.traits = cp_rec.get("traits") or existing.traits
                # Deep merge metadata
                merged_meta = dict(existing.metadata)
                merged_meta.update(cp_rec.get("metadata") or {})
                merged_meta["source"] = "control-plane"
                existing.metadata = merged_meta
                existing.domain = cp_rec.get("domain") or existing.domain
            else:
                # Net-new agent from CP
                self._agents[name] = AgentProfile(
                    name=name,
                    domain=cp_rec.get("domain", ""),
                    system_prompt=cp_rec.get("system_prompt", ""),
                    capabilities=cp_rec.get("capabilities") or [],
                    traits=cp_rec.get("traits") or [],
                    metadata={
                        **(cp_rec.get("metadata") or {}),
                        "source": "control-plane",
                    },
                )

    # ------------------------------------------------------------------
    # Convenience merge factory
    # ------------------------------------------------------------------

    def merge(
        self,
        disk: dict[str, AgentProfile],
        cp: list[dict],
    ) -> dict[str, AgentProfile]:
        """Convenience method: load disk agents dict + overlay CP, return merged.

        Intended for callers that pre-compute disk_agents and cp_agents
        independently and want a single merge call.

        Args:
            disk: Previously loaded disk agents (from load_disk_agents).
            cp:   CP agent list (may be empty).

        Returns:
            Merged dict. Internal state is also updated.
        """
        self._agents = dict(disk)
        self.overlay_cp_agents(cp)
        return dict(self._agents)

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
# CP fetch helper (used by bootstrap.py)
# ---------------------------------------------------------------------------


def fetch_cp_agents(domain: str = "wicked-agents", source: str = "agents") -> list[dict]:
    """Fetch agent records from the control plane.

    Returns an empty list if the CP is unavailable or returns no records.
    Designed to be called once per session in bootstrap.py.

    Args:
        domain: CP domain to query (default: "wicked-agents").
        source: Resource source within the domain (default: "agents").

    Returns:
        List of raw agent record dicts from the CP, or [] on any failure.
    """
    try:
        from _control_plane import get_client
        from _session import SessionState

        state = SessionState.load()
        if not state.cp_available or state.fallback_mode:
            return []

        cp = get_client(hook_mode=False)
        result = cp.request(domain, source, "list")
        if result is None:
            return []

        data = result.get("data", [])
        return data if isinstance(data, list) else []

    except Exception as exc:
        print(
            f"[wicked-garden] Failed to fetch CP agents: {exc}",
            file=sys.stderr,
        )
        return []


# ---------------------------------------------------------------------------
# Markdown frontmatter parser (stdlib-only, no PyYAML)
# ---------------------------------------------------------------------------

_FRONTMATTER_START = "---"
_FRONTMATTER_END = "---"


def _parse_agent_md(path: Path) -> AgentProfile | None:
    """Parse a Claude Code agent markdown file into an AgentProfile.

    Format:
        ---
        name: agent-name
        description: |
          Optional description
        domain: engineering          # optional
        capabilities:                # optional list
          - code-review
        traits:                      # optional list
          - pragmatic
        model: sonnet                # stored in metadata
        color: blue                  # stored in metadata
        ---

        # Agent Title

        System prompt body...

    Returns:
        AgentProfile, or None if the file lacks a valid name field.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter, body = _split_frontmatter(raw)
    if frontmatter is None:
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
    name = parsed.get("name") or path.stem
    if not name:
        return None

    domain = parsed.get("domain") or _infer_domain(path)

    # Build metadata from remaining frontmatter keys
    metadata_keys = {"model", "color", "version", "author"}
    extra_meta = {k: v for k, v in parsed.items() if k in metadata_keys}
    extra_meta["source"] = "disk"
    extra_meta["file"] = str(path)

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


def _infer_domain(path: Path) -> str:
    """Infer domain from path: agents/{domain}/agent.md -> domain."""
    parts = path.parts
    # Look for the 'agents' segment and take the next part as domain
    for idx, part in enumerate(parts):
        if part == "agents" and idx + 2 < len(parts):
            return parts[idx + 1]
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
