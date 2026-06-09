#!/usr/bin/env python3
"""inject_capability_edges.py — materialize agent→capability edges into the
codegraph symbol graph.

A wicked-garden agent declares the runtime capabilities it needs through a
``tool-capabilities:`` frontmatter list (e.g. ``security-scanning``,
``version-control``). Each capability is defined in ``scripts/_capability_registry.py``
(``CAPABILITY_REGISTRY``), which maps it to the concrete tools that satisfy it
(MCP servers / CLI binaries, probed at runtime). The link from an agent to the
capability it depends on is a *string in YAML* keyed against a Python registry —
there is no symbol reference from the agent's markdown into the registry module,
so neither grep nor a static call-graph can connect them.

This reads each agent's ``tool-capabilities`` list + the registry, and for every
capability that IS defined in the registry, INSERTs:
  - a synthetic node ``capability:<name>`` (kind ``capability``), and
  - an edge ``file:<agent.md>`` → ``capability:<name>`` with
    ``provenance='injected:capability'``,

so blast-radius/impact traversals over the capability node surface every agent
that depends on it (change/remove a capability or its backing tool → the agents
that declare it are in the blast radius). Capabilities NOT present in the registry
are skipped — the extractor never fabricates a node for an undefined capability.

Stdlib-only. Idempotent (re-run replaces injected edges + the synthetic nodes it
owns). Read-the-registry, not the LLM — deterministic.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

_REPO = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO / "agents"
_INJECTED_PROVENANCE = "injected:capability"
_CAPABILITY_NODE_KIND = "capability"

# scripts/ on sys.path so we can read the registry (the source of truth for which
# capability names are real). Mirrors the test harness's path insertion.
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# self-noding helpers live beside this script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _graph_nodes import ensure_file_node, ensure_virtual_node  # noqa: E402


def _registry_capabilities() -> Set[str]:
    """The set of capability names defined in CAPABILITY_REGISTRY.

    Imported lazily so a missing/!importable registry degrades to 'no known
    capabilities' (every cap skipped) rather than raising."""
    try:
        from _capability_registry import CAPABILITY_REGISTRY  # noqa: WPS433
    except Exception:  # noqa: BLE001 — registry absence must not crash the extractor
        return set()
    return set(CAPABILITY_REGISTRY.keys())


def _frontmatter(text: str) -> str:
    """Return the YAML frontmatter block (between the leading --- fences), or ''."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end > 0 else ""


def _declared_capabilities(fm: str) -> List[str]:
    """Capability names from a ``tool-capabilities:`` block list in frontmatter.

    Matches the block-list shape used across agents:
        tool-capabilities:
          - security-scanning
          - version-control
    """
    block = re.search(
        r"(?m)^tool-capabilities:\s*\n((?:[ \t]+-[ \t]*[a-z0-9_-]+[ \t]*\n?)+)", fm
    )
    if not block:
        return []
    return re.findall(r"-[ \t]*([a-z0-9_-]+)", block.group(1))


def _agent_capabilities() -> List[Tuple[str, str]]:
    """[(agent_relpath, capability_name), ...] for caps that exist in the registry.

    Deterministic ordering; one entry per (agent, distinct declared cap)."""
    known = _registry_capabilities()
    out: List[Tuple[str, str]] = []
    for md in sorted(_AGENTS_DIR.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        caps = _declared_capabilities(_frontmatter(text))
        if not caps:
            continue
        agent_rel = md.relative_to(_REPO).as_posix()
        seen: Set[str] = set()
        for cap in caps:
            if cap in seen or cap not in known:  # skip dupes + caps absent from registry
                continue
            seen.add(cap)
            out.append((agent_rel, cap))
    return out


def inject(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        # idempotent: clear prior injected capability edges, then the synthetic
        # capability nodes this extractor owns (no other edge should reference them).
        conn.execute("DELETE FROM edges WHERE provenance = ?", (_INJECTED_PROVENANCE,))
        conn.execute("DELETE FROM nodes WHERE kind = ?", (_CAPABILITY_NODE_KIND,))
        pairs = _agent_capabilities()
        added = 0
        caps_created: Set[str] = set()
        for agent_rel, cap in pairs:
            # self-node the agent .md (codegraph indexes code, not markdown — #916)
            src = ensure_file_node(conn, agent_rel)
            tgt = ensure_virtual_node(conn, f"capability:{cap}", _CAPABILITY_NODE_KIND, cap)
            caps_created.add(cap)
            conn.execute(
                "INSERT INTO edges (source, target, kind, metadata, provenance) "
                "VALUES (?, ?, ?, ?, ?)",
                (src, tgt, "references",
                 json.dumps({"injected": "capability", "capability": cap}),
                 _INJECTED_PROVENANCE),
            )
            added += 1
        conn.commit()
        # skipped stays 0: caps absent from the registry are dropped in
        # _agent_capabilities(), and we now create whatever node we need.
        return {"edges_added": added, "skipped": 0,
                "capabilities": len(caps_created), "pairs": len(pairs)}
    finally:
        conn.close()


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else _REPO / ".codegraph" / "codegraph.db"
    if not db.exists():
        print(json.dumps({"error": f"codegraph db not found at {db}; run `codegraph index` first"}))
        return 1
    print(json.dumps(inject(db), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
