#!/usr/bin/env python3
"""find_orphan_agents.py — find worker (context:fork) skills that nothing dispatches to.

Skills-only cutover: the former agents/{domain}/{name}.md workers are now
standalone context:fork skills at skills/{domain}-{role}/SKILL.md. This tool
keeps the same reachability question — "is this worker actually reached?" — but
asks it of the fork skills.

After the v12 rubric-wrapper collapse, some workers may be dead: nothing reaches
them. A naive grep over-keeps, because:

  - `.claude-plugin/components.json` is a *generated* manifest — it lists every
    fork skill that EXISTS, not every one that's USED. A worker referenced only
    there is dead.
  - workers reference each other (an orchestrator fork skill dispatches to
    sub-workers). A worker referenced only by *other dead workers* is part of a
    dead island, still dead.

So "is this worker used?" is a reachability question, not a grep count. This tool:

  1. ROOTS — a worker is rooted if a *real* (non-generated, non-doc) surface that
     is NOT another worker references it: a domain router skill or its refs, a
     scenario, or a registry (specialist_resolver.py, specialist.json,
     _capability_registry*, _bus_consumers.json, hooks.json).
     Reference forms counted: the dash skill name ``wicked-garden-{domain}-{role}``,
     the legacy colon ``wicked-garden:{domain}:{role}``, the ``subagent_type: …``
     dispatch, the skill directory name ``{domain}-{role}``, or the bare
     hyphen-token ``{role}`` (boundary-aware so ``architect`` does NOT match
     inside ``solution-architect``).
  2. REACH — a worker dispatched to by a *live* worker's file is also live
     (transitive).
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
_SKILLS_DIR = _REPO / "skills"

# dirs never worth scanning: live worktrees (full repo copies — would double-count),
# vcs/build junk, and test-run evidence (artifacts mention worker names in their output).
_EXCLUDE_PARTS = {".git", "__pycache__", ".codegraph", "node_modules",
                  ".claude", ".wicked-testing"}
# extensions worth scanning for references
_SCAN_EXT = {".md", ".py", ".json"}

# A reference ROOTS a worker only if it comes from a real usage surface that is
# NOT another worker skill. Everything else (tests/, CHANGELOG.md, docs/, README,
# the generated components.json, ci fixtures) DESCRIBES or ENUMERATES workers —
# it does not dispatch to them, so it must not root.
_ROOT_DIRS = ("skills", "scenarios")  # skills routers + scenario dispatch
_ROOT_FILES = {
    _REPO / "scripts" / "crew" / "specialist_resolver.py",
    _REPO / ".claude-plugin" / "specialist.json",
    _REPO / "scripts" / "_bus_consumers.json",
    _REPO / "hooks" / "hooks.json",
}

_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)
_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
_SUBAGENT_RE = re.compile(r"^subagent_type:\s*(.+?)\s*$", re.MULTILINE)
_KNOWN_DOMAINS = ("agentic", "crew", "data", "engineering", "jam", "mem",
                  "persona", "platform", "product", "qe", "search", "smaht")
_SKILL_PREFIX = "wicked-garden-"


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else ""


class Worker:
    """A context:fork worker skill and the identifier forms that reference it."""

    __slots__ = ("name", "role", "domain", "subagent_type", "dir", "skill_md")

    def __init__(self, name: str, role: str, domain: str, subagent_type: str,
                 worker_dir: Path, skill_md: Path) -> None:
        self.name = name
        self.role = role
        self.domain = domain
        self.subagent_type = subagent_type
        self.dir = worker_dir
        self.skill_md = skill_md


def _split_domain_role(name: str, dir_name: str, subagent_type: str) -> Tuple[str, str]:
    """Best-effort (domain, role) for a worker."""
    if subagent_type.startswith("wicked-garden:"):
        tail = subagent_type[len("wicked-garden:"):]
        parts = tail.split(":", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    tail = name[len(_SKILL_PREFIX):] if name.startswith(_SKILL_PREFIX) else dir_name
    for dom in _KNOWN_DOMAINS:
        if tail.startswith(dom + "-"):
            return dom, tail[len(dom) + 1:]
        if tail == dom:
            return dom, tail
    return "", tail


def _all_workers() -> Dict[str, Worker]:
    """{name: Worker} for every context:fork SKILL.md under skills/."""
    out: Dict[str, Worker] = {}
    if not _SKILLS_DIR.is_dir():
        return out
    for skill_md in sorted(_SKILLS_DIR.rglob("SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fm = _frontmatter(text)
        if not _FORK_RE.search(fm):
            continue
        nm = _NAME_RE.search(fm)
        name = nm.group(1).strip() if nm else skill_md.parent.name
        sm = _SUBAGENT_RE.search(fm)
        subagent_type = sm.group(1).strip() if sm else ""
        domain, role = _split_domain_role(name, skill_md.parent.name, subagent_type)
        out[name] = Worker(name, role, domain, subagent_type, skill_md.parent, skill_md)
    return out


def _ref_patterns(w: Worker) -> re.Pattern:
    """Precise reference forms for a worker, combined into one regex."""
    forms = [re.escape(w.name), re.escape(w.dir.name)]
    if w.subagent_type:
        forms.append(re.escape(w.subagent_type))
    if w.domain and w.role:
        forms.append(rf"{re.escape(w.domain)}:{re.escape(w.role)}")
    if w.role:
        forms.append(rf"subagent_type\s*[:=]\s*[\"']?{re.escape(w.role)}")
        forms.append(rf"(?<![\w-]){re.escape(w.role)}(?![\w-])")  # bare role, boundary-aware
    return re.compile("|".join(forms))


def _scan_files() -> List[Path]:
    out = []
    for p in _REPO.rglob("*"):
        if not p.is_file() or p.suffix not in _SCAN_EXT:
            continue
        # Exclude on the path RELATIVE to the repo root — otherwise, when this
        # runs from inside a git worktree (which lives at .claude/worktrees/…),
        # the worktree's own ".claude" prefix would exclude the entire repo,
        # making every worker look orphaned.
        rel = p.relative_to(_REPO)
        if any(part in _EXCLUDE_PARTS for part in rel.parts):
            continue
        out.append(p)
    return out


def analyze() -> Tuple[List[str], Dict[str, str]]:
    """Return (orphans, live) where live maps name -> one-line reason it's kept."""
    workers = _all_workers()
    worker_dirs = {w.dir for w in workers.values()}
    files = _scan_files()
    file_text = {p: p.read_text(encoding="utf-8", errors="ignore") for p in files}
    pats = {name: _ref_patterns(w) for name, w in workers.items()}

    def is_worker_file(p: Path) -> bool:
        return any(wd == p or wd in p.parents for wd in worker_dirs)

    def is_root_source(p: Path) -> bool:
        # A reference from inside a worker's own dir is worker→worker (handled
        # by reachability), never a root.
        if is_worker_file(p):
            return False
        if any((_REPO / d) in p.parents for d in _ROOT_DIRS):
            return True
        if p in _ROOT_FILES or p.name.startswith("_capability_registry"):
            return True
        return False

    # which files reference each worker (excluding the worker's own dir)
    refs: Dict[str, List[Path]] = {name: [] for name in workers}
    for name, pat in pats.items():
        own_dir = workers[name].dir
        for p in files:
            if own_dir == p or own_dir in p.parents:
                continue  # skip the worker's own files
            if pat.search(file_text[p]):
                refs[name].append(p)

    # ROOT: referenced by a real usage surface (router skill/scenario/registry)
    live: Dict[str, str] = {}
    for name, ref_paths in refs.items():
        roots = [p for p in ref_paths if is_root_source(p)]
        if roots:
            rel = roots[0].relative_to(_REPO).as_posix()
            live[name] = f"rooted: {rel}" + (f" (+{len(roots)-1} more)" if len(roots) > 1 else "")

    # REACH: worker referenced by a live worker's file is live (transitive)
    dir_to_name = {w.dir: n for n, w in workers.items()}

    def owning_worker(p: Path) -> str | None:
        for wd, n in dir_to_name.items():
            if wd == p or wd in p.parents:
                return n
        return None

    changed = True
    while changed:
        changed = False
        for name, ref_paths in refs.items():
            if name in live:
                continue
            for p in ref_paths:
                owner = owning_worker(p)
                if owner is not None and owner in live:
                    live[name] = f"dispatched-by: {owner}"
                    changed = True
                    break

    orphans = sorted(n for n in workers if n not in live)
    return orphans, live


def main() -> int:
    orphans, live = analyze()
    if "--json" in sys.argv[1:]:
        print(json.dumps({"orphans": orphans, "live": live}, indent=2))
        return 0
    total = len(orphans) + len(live)
    print(f"# Orphan fork-skill analysis — {total} workers, {len(live)} live, {len(orphans)} orphaned\n")
    print(f"## ORPHANS ({len(orphans)}) — referenced by nothing real (removal candidates)")
    for n in orphans:
        print(f"  - {n}")
    print(f"\n## LIVE ({len(live)}) — why each is kept")
    for n in sorted(live):
        print(f"  - {n}: {live[n]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
