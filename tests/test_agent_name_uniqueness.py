"""
Regression suite: no two agent files share the same basename across domains.

Audit finding: #533 / #534 — duplicate basenames (e.g. facilitator exists in both
jam/ and crew/) created routing ambiguity. The brainstorm-facilitator rename (#534)
resolved the jam/crew collision. This suite guards against future recurrences.

Note: the check is on basename (stem) — `facilitator` in crew/ and `facilitator`
in jam/ would be a collision. Having the same name in different domains is the
problem because agent discovery tools may resolve by name without domain context.
"""
from pathlib import Path
from collections import defaultdict
import pytest

REPO = Path(__file__).parent.parent
AGENTS_DIR = REPO / "agents"


def test_agent_basenames_are_unique_across_domains():
    """No two agent files in different domains share the same stem."""
    stem_to_paths: dict[str, list[Path]] = defaultdict(list)
    for md_file in sorted(AGENTS_DIR.rglob("*.md")):
        stem_to_paths[md_file.stem].append(md_file)

    duplicates = {
        stem: paths
        for stem, paths in stem_to_paths.items()
        if len(paths) > 1
    }

    if duplicates:
        lines = []
        for stem, paths in sorted(duplicates.items()):
            rel_paths = [str(p.relative_to(REPO)) for p in paths]
            lines.append(f"  '{stem}': {rel_paths}")
        detail = "\n".join(lines)
        pytest.fail(
            f"Agent basename collisions detected across domains "
            f"(causes routing ambiguity):\n{detail}"
        )
