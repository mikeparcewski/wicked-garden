#!/usr/bin/env python3
"""Skill-as-agent conflation heuristic for wg-check (#664).

For each skill (skills/**/SKILL.md), look for sibling agents in agents/{domain}/
and grep both files for shared content classes. If 3+ classes overlap in BOTH
files, warn that the skill and the agent likely duplicate rubric / persona /
mechanics content -- the Pattern A migration smell from #652.

The heuristic is intentionally cheap (no LLM, no diff): four regex probes per
file, domain-scoped pairing only. Acceptable false-positive rate; the warning
is informational, not blocking.

Background: PRs #666 (jam slim) and #670 (propose-process slim) showed the
pattern -- a SKILL.md owning rubric steps + persona pools + convergence
mechanics + transcript/bus emit instructions while a sibling agent in the same
domain encodes the same content. The fix is the Pattern A migration: keep
orchestration prose in the agent, slim the skill to navigation + entry-points
(~50-100 lines).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Conflation content classes -- each is a regex probe. A class "matches" a file
# if the file contains the pattern at least once. If 3+ classes match BOTH the
# SKILL.md and a sibling agent in the same domain, warn (#664 / #652 Pattern A).
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

THRESHOLD = 3  # classes shared between skill and agent before warning


def probe(text: str) -> set[str]:
    return {name for name, rx in PROBES.items() if rx.search(text)}


def candidate_agents(agents_root: Path, domain: str, skill_name: str) -> list[Path]:
    """Find agents in the same domain that look like siblings of this skill."""
    domain_dir = agents_root / domain
    if not domain_dir.is_dir():
        return []
    out: list[Path] = []
    sk = skill_name.lower().replace("_", "-")
    for md in sorted(domain_dir.glob("*.md")):
        stem = md.stem.lower()
        if stem == sk or sk in stem or stem in sk:
            out.append(md)
            continue
        if sk in ("skill", domain) and stem.endswith(
            ("-facilitator", "-orchestrator", "-coordinator")
        ):
            out.append(md)
    # Single-skill domains (no name match): fall back to ALL agents in the domain.
    if not out:
        for md in sorted(domain_dir.glob("*.md")):
            out.append(md)
    return out


def main(repo_root: Path = Path(".")) -> int:
    skills_root = repo_root / "skills"
    agents_root = repo_root / "agents"
    if not skills_root.is_dir() or not agents_root.is_dir():
        return 0

    flagged = 0
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        try:
            parts = skill_md.relative_to(skills_root).parts
        except ValueError:
            continue
        if not parts:
            continue
        domain = parts[0]
        # multi-skill: skills/{domain}/{skill}/SKILL.md
        # single-skill: skills/{domain}/SKILL.md
        skill_name = parts[1] if len(parts) >= 3 else domain
        try:
            skill_text = skill_md.read_text(errors="replace")
        except OSError:
            continue
        skill_classes = probe(skill_text)
        if len(skill_classes) < THRESHOLD:
            # SKILL.md doesn't have enough rubric/persona content to bother --
            # it's already slim or scoped to one concern.
            continue
        for agent_md in candidate_agents(agents_root, domain, skill_name):
            try:
                agent_text = agent_md.read_text(errors="replace")
            except OSError:
                continue
            agent_classes = probe(agent_text)
            shared = skill_classes & agent_classes
            if len(shared) >= THRESHOLD:
                flagged += 1
                rel_skill = skill_md.relative_to(repo_root)
                rel_agent = agent_md.relative_to(repo_root)
                print(
                    f"WARNING: skill-as-agent conflation detected -- {rel_skill} "
                    f"and {rel_agent} share {len(shared)} content classes "
                    f"({sorted(shared)}). See #652 Pattern A migration."
                )

    if flagged == 0:
        print("OK: no skill-as-agent conflation patterns detected (#664)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
