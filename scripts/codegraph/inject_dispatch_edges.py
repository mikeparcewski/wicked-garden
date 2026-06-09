#!/usr/bin/env python3
"""inject_dispatch_edges.py — materialize command→agent DISPATCH edges into the
codegraph symbol graph.

A wicked-garden slash command dispatches work to a subagent by naming it through
``Task(subagent_type="wicked-garden:<domain>:<agent>")`` (and, where present, a
``subagent_type:`` frontmatter key). That ``subagent_type`` is a *string handle*
resolved by the Claude Code runtime — the command file never references the
agent's file or any symbol it defines. So neither grep ("who calls this agent?")
nor a static call-graph can link a command to the agent it drives: the dispatch
is invisible as a call.

This reads the command markdown, extracts each ``subagent_type`` handle, resolves
``wicked-garden:<domain>:<name>`` to ``agents/<domain>/<name>.md`` by the project's
naming convention (CLAUDE.md: ``wicked-garden:{domain}:{agent-name}`` ↔
``agents/{domain}/{agent-name}.md``), and INSERTs an edge
``file:<command.md>`` → ``file:<agent.md>`` with ``provenance='injected:dispatch'``
so blast-radius/impact traversals surface the command as a dependent of the agent
(change the agent → the commands that dispatch it are in the blast radius).

The same ``wicked-garden:X:Y`` shape also appears for *cross-references to other
commands/skills* (e.g. ``Load skill wicked-garden:agentic:agentic-patterns``).
Those resolve to no ``agents/...`` file, so the target node is absent and the edge
is skipped — only real command→agent dispatches are materialized.

Stdlib-only. Idempotent (re-run replaces injected edges). Read-the-registry
(here: the command/agent files on disk), not the LLM — deterministic.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# self-noding helper lives beside this script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _graph_nodes import ensure_file_node  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_COMMANDS_DIR = _REPO / "commands"
_AGENTS_DIR = _REPO / "agents"
_INJECTED_PROVENANCE = "injected:dispatch"

# subagent_type referenced as a Task(...) kwarg (subagent_type="..."/'...') OR as a
# YAML frontmatter key (subagent_type: ...). Capture the wicked-garden:domain:name handle.
_DISPATCH_RE = re.compile(
    r"""subagent_type\s*[:=]\s*["']?(wicked-garden:[a-z0-9_-]+:[a-z0-9_-]+)["']?"""
)


def _agent_relpath_for(handle: str) -> str | None:
    """Resolve a ``wicked-garden:<domain>:<name>`` handle to ``agents/<domain>/<name>.md``.

    Returns the repo-relative posix path iff that agent file exists on disk;
    None otherwise (the handle names a command/skill, not an agent)."""
    parts = handle.split(":")
    if len(parts) != 3:
        return None
    _, domain, name = parts
    if not domain or not name:
        return None
    candidate = _AGENTS_DIR / domain / f"{name}.md"
    if candidate.exists():
        return candidate.relative_to(_REPO).as_posix()
    return None


def _dispatches() -> List[Tuple[str, str, str]]:
    """[(command_relpath, agent_relpath, handle), ...].

    One entry per (command, distinct subagent_type handle) where the handle
    resolves to an existing agent file. Deterministic ordering."""
    out: List[Tuple[str, str, str]] = []
    for md in sorted(_COMMANDS_DIR.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        cmd_rel = md.relative_to(_REPO).as_posix()
        seen: Set[str] = set()
        for handle in _DISPATCH_RE.findall(text):
            if handle in seen:
                continue
            seen.add(handle)
            agent_rel = _agent_relpath_for(handle)
            if agent_rel is None:
                continue
            out.append((cmd_rel, agent_rel, handle))
    return out


def inject(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        # idempotent: clear prior injected dispatch edges
        conn.execute("DELETE FROM edges WHERE provenance = ?", (_INJECTED_PROVENANCE,))
        dispatches = _dispatches()
        added = 0
        for cmd_rel, agent_rel, handle in dispatches:
            # self-node the .md command + agent (codegraph indexes code, not markdown,
            # so these file nodes don't exist until we create them — issue #916)
            src = ensure_file_node(conn, cmd_rel)
            tgt = ensure_file_node(conn, agent_rel)
            conn.execute(
                "INSERT INTO edges (source, target, kind, metadata, provenance) "
                "VALUES (?, ?, ?, ?, ?)",
                (src, tgt, "references",
                 json.dumps({"injected": "dispatch", "subagent_type": handle}),
                 _INJECTED_PROVENANCE),
            )
            added += 1
        conn.commit()
        # skipped stays 0: _dispatches() already drops handles that don't resolve to
        # an agent file, and we now create whatever node we need.
        return {"edges_added": added, "skipped": 0, "dispatches": len(dispatches)}
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
