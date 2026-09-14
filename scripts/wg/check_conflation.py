#!/usr/bin/env python3
"""Router-vs-worker conflation heuristic for wg-check (#664).

Skills-only cutover: the former "skill vs sibling agent" conflation smell
(#652 Pattern A) becomes "domain ROUTER skill vs sibling WORKER
skill". The former agents/{domain}/ tree is gone — workers are now standalone
skills at skills/{domain}-{role}/SKILL.md declaring ``context: fork``.

For each domain router (skills/{domain}/SKILL.md — a depth-2, non-fork skill),
grep it and its sibling fork worker skills (skills/{domain}-*/SKILL.md) for
shared content classes. If 3+ classes overlap in BOTH files, warn that the
router likely duplicates rubric / persona / mechanics content that belongs in
the worker -- keep the router slim (navigation + entry-points, ~50-100 lines)
and let the fork worker own the orchestration prose.

The heuristic is intentionally cheap (no LLM, no diff): four regex probes per
file, domain-scoped pairing only. Acceptable false-positive rate; the warning
is informational, not blocking.

Background: PRs #666 (jam slim) and #670 (propose-process slim) showed the
pattern -- a SKILL.md owning rubric steps + persona pools + convergence
mechanics + transcript/bus emit instructions while a sibling worker encodes
the same content. The fix is the Pattern A migration: keep orchestration prose
in the worker, slim the router to navigation + entry-points.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# scripts/ is not always on sys.path (hooks import by path; CI runs from a subdir).
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1])
if _SCRIPTS_DIR not in sys.path:
    sys.path.append(_SCRIPTS_DIR)
from _skill_meta import skill_role_of  # noqa: E402

# Conflation content classes -- each is a regex probe. A class "matches" a file
# if the file contains the pattern at least once. If 3+ classes match BOTH the
# router SKILL.md and a sibling fork worker skill, warn (#664 / #652 Pattern A).
PROBES = {
    "persona-archetype-list": re.compile(
        r"(persona[\s-]?archetype|archetype[\s-]?pool|persona pool|focus group personas?)",
        re.IGNORECASE,
    ),
    "rubric-step-block": re.compile(
        r"(^|\n)(#{2,4}\s*)?step\s*[0-9]+\s*[-:—]",
        re.IGNORECASE,
    ),
    "convergence-or-round-mechanics": re.compile(
        r"(convergence (check|mode|signal)|round\s*[0-9]+|after each round|next round)",
        re.IGNORECASE,
    ),
    "transcript-event-bus-emit": re.compile(
        r"(save_transcript|store the full transcript|"
        r"emit (a|an) (event|synthesis event)|event log|bus emit|emit_event)",
        re.IGNORECASE,
    ),
}

THRESHOLD = 3  # classes shared between router and worker before warning

def probe(text: str) -> set[str]:
    return {name for name, rx in PROBES.items() if rx.search(text)}


def candidate_workers(skills_root: Path, domain: str) -> list[Path]:
    """Sibling worker skills for a domain router.

    Workers live at skills/{domain}-{role}/SKILL.md (top-level siblings of the
    router directory skills/{domain}/). Only files whose role is ``worker``
    (``_skill_meta.skill_role``: ``metadata.role: worker``, legacy ``context: fork``
    inferred) are returned.
    """
    out: list[Path] = []
    for md in sorted(skills_root.glob(f"{domain}-*/SKILL.md")):
        if skill_role_of(md) == "worker":
            out.append(md)
    return out


def main(repo_root: Path = Path(".")) -> int:
    skills_root = repo_root / "skills"
    if not skills_root.is_dir():
        return 0

    flagged = 0
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        try:
            parts = skill_md.relative_to(skills_root).parts
        except ValueError:
            continue
        # Only DOMAIN ROUTER skills: skills/{domain}/SKILL.md (depth 2).
        if len(parts) != 2:
            continue
        domain = parts[0]
        try:
            router_text = skill_md.read_text(errors="replace")
        except OSError:
            continue
        # Only a ROUTER is judged: a top-level worker, the floor and module stubs
        # are not routers (role via scripts/_skill_meta.skill_role).
        if skill_role_of(skill_md) != "router":
            continue
        router_classes = probe(router_text)
        if len(router_classes) < THRESHOLD:
            # Router doesn't have enough rubric/persona content to bother --
            # it's already slim or scoped to one concern.
            continue
        for worker_md in candidate_workers(skills_root, domain):
            try:
                worker_text = worker_md.read_text(errors="replace")
            except OSError:
                continue
            worker_classes = probe(worker_text)
            shared = router_classes & worker_classes
            if len(shared) >= THRESHOLD:
                flagged += 1
                rel_router = skill_md.relative_to(repo_root)
                rel_worker = worker_md.relative_to(repo_root)
                print(
                    f"WARNING: router-vs-worker conflation detected -- {rel_router} "
                    f"and {rel_worker} share {len(shared)} content classes "
                    f"({sorted(shared)}). See #652 Pattern A migration."
                )

    if flagged == 0:
        print("OK: no router-vs-worker conflation patterns detected (#664)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
