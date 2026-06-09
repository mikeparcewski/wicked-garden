#!/usr/bin/env python3
"""find_orphan_agents.py — find agent definitions that nothing actually dispatches to.

After the v12 rubric-wrapper collapse, many commands stopped dispatching to agents
(the rubric moved inline). Some agents are now dead: nothing reaches them. But a
naive grep over-keeps, because:

  - `.claude-plugin/components.json` is a *generated* manifest — it lists every agent
    that EXISTS, not every agent that's USED. An agent referenced only there is dead.
  - agents reference each other (an orchestrator dispatches to sub-agents). An agent
    referenced only by *other dead agents* is part of a dead island, still dead.

So "is this agent used?" is a reachability question, not a grep count. This tool:

  1. ROOTS — an agent is rooted if a *real* (non-generated, non-doc) file references it:
       commands/**, skills/**, scenarios/**, specialist_resolver.py, specialist.json,
       _capability_registry*, _bus_consumers.json, hooks.json.
     References counted by precise forms: ``<domain>:<name>``, ``subagent_type: <name>``,
     ``agent: <name>``, or the bare hyphen-token ``<name>`` (boundary-aware so
     ``architect`` does NOT match inside ``solution-architect``).
  2. REACH — an agent dispatched to by a *live* agent's file is also live (transitive).
  3. ORPHANS — everything not reachable from a root. These are removal candidates.

components.json and docs/** are EXCLUDED from rooting (they describe, they don't use).

Usage:
  python3 scripts/ci/find_orphan_agents.py           # human report
  python3 scripts/ci/find_orphan_agents.py --json    # {orphans:[...], live:{name:reason}}

Read-only. Stdlib-only. Deterministic.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_REPO = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO / "agents"

# dirs never worth scanning: live worktrees (full repo copies — would double-count),
# vcs/build junk, and test-run evidence (artifacts mention agent names in their output).
_EXCLUDE_PARTS = {".git", "__pycache__", ".codegraph", "node_modules",
                  ".claude", ".wicked-testing"}
# extensions worth scanning for references
_SCAN_EXT = {".md", ".py", ".json"}

# A reference ROOTS an agent only if it comes from a real usage surface. Everything
# else (tests/, CHANGELOG.md, docs/, README, the generated components.json, ci fixtures)
# DESCRIBES or ENUMERATES agents — it does not dispatch to them, so it must not root.
_ROOT_DIRS = ("commands", "skills", "scenarios")  # scenarios dispatch → would break if removed
_ROOT_FILES = {
    _REPO / "scripts" / "crew" / "specialist_resolver.py",
    _REPO / ".claude-plugin" / "specialist.json",
    _REPO / "scripts" / "_bus_consumers.json",
    _REPO / "hooks" / "hooks.json",
}


def _is_root_source(p: Path) -> bool:
    """True iff a reference from this file means the agent is actually reached
    (a command/skill/scenario dispatch, or a resolver/capability/bus registry)."""
    if _AGENTS_DIR in p.parents:
        return False  # agent→agent handled separately by reachability
    if any((_REPO / d) in p.parents for d in _ROOT_DIRS):
        return True
    if p in _ROOT_FILES or p.name.startswith("_capability_registry"):
        return True
    return False


def _all_agents() -> Dict[str, Path]:
    """{name: path} for every agents/<domain>/<name>.md."""
    return {p.stem: p for p in sorted(_AGENTS_DIR.glob("*/*.md"))}


def _domain_of(path: Path) -> str:
    return path.parent.name


def _ref_patterns(name: str, domain: str) -> re.Pattern:
    """Precise reference forms for an agent, combined into one regex."""
    n = re.escape(name)
    forms = [
        rf"{re.escape(domain)}:{n}",            # wicked-garden:<domain>:<name>
        rf"subagent_type\s*[:=]\s*[\"']?{n}",   # Task dispatch
        rf"agent\s*:\s*{n}\b",                  # SKILL.md frontmatter
        rf"(?<![\w-]){n}(?![\w-])",             # bare hyphen-token (boundary-aware)
    ]
    return re.compile("|".join(forms))


def _scan_files() -> List[Path]:
    out = []
    for p in _REPO.rglob("*"):
        if not p.is_file() or p.suffix not in _SCAN_EXT:
            continue
        if any(part in _EXCLUDE_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


def _is_agent_file(p: Path) -> bool:
    return _AGENTS_DIR in p.parents and p.suffix == ".md"


def analyze() -> Tuple[List[str], Dict[str, str]]:
    """Return (orphans, live) where live maps name -> one-line reason it's kept."""
    agents = _all_agents()
    files = _scan_files()
    file_text = {p: p.read_text(encoding="utf-8", errors="ignore") for p in files}
    pats = {name: _ref_patterns(name, _domain_of(path)) for name, path in agents.items()}

    # which files reference each agent (excluding the agent's own file)
    refs: Dict[str, List[Path]] = {name: [] for name in agents}
    for name, pat in pats.items():
        own = agents[name]
        for p in files:
            if p == own:
                continue
            if pat.search(file_text[p]):
                refs[name].append(p)

    # ROOT: referenced by a real usage surface (command/skill/scenario/registry)
    live: Dict[str, str] = {}
    for name, ref_paths in refs.items():
        roots = [p for p in ref_paths if _is_root_source(p)]
        if roots:
            rel = roots[0].relative_to(_REPO).as_posix()
            live[name] = f"rooted: {rel}" + (f" (+{len(roots)-1} more)" if len(roots) > 1 else "")

    # REACH: agent referenced by a live agent's file is live (transitive)
    changed = True
    while changed:
        changed = False
        for name, ref_paths in refs.items():
            if name in live:
                continue
            for p in ref_paths:
                if _is_agent_file(p) and p.stem in live:
                    live[name] = f"dispatched-by: {p.stem}"
                    changed = True
                    break

    orphans = sorted(n for n in agents if n not in live)
    return orphans, live


def main() -> int:
    orphans, live = analyze()
    if "--json" in sys.argv[1:]:
        print(json.dumps({"orphans": orphans, "live": live}, indent=2))
        return 0
    total = len(orphans) + len(live)
    print(f"# Orphan-agent analysis — {total} agents, {len(live)} live, {len(orphans)} orphaned\n")
    print(f"## ORPHANS ({len(orphans)}) — referenced by nothing real (removal candidates)")
    for n in orphans:
        print(f"  - {n}")
    print(f"\n## LIVE ({len(live)}) — why each is kept")
    for n in sorted(live):
        print(f"  - {n}: {live[n]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
