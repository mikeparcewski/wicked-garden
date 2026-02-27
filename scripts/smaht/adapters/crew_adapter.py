"""
wicked-crew adapter for wicked-smaht.

Queries project state, phase, outcomes, and constraints.
Uses direct import of crew.crew since all scripts are co-located.
"""

import sys
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

# Direct import of the crew module (co-located under scripts/crew/)
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from crew.crew import list_projects


def _get_active_projects() -> list:
    """Synchronous crew project list — called via run_in_thread for async."""
    try:
        data = list_projects(active_only=True)
        return data.get("projects", [])
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-crew for project state."""
    items = []

    projects = await run_in_thread(_get_active_projects)

    for proj in projects:
        if project and proj.get("name") != project:
            continue

        project_name = proj.get("name", "unknown")
        current_phase = proj.get("current_phase", "unknown")
        signals = proj.get("signals_detected", [])
        complexity = proj.get("complexity_score", 0)

        # High relevance for active projects in non-completed phases
        semantic_score = 0.8 if current_phase not in ("review", "done") else 0.4

        items.append(ContextItem(
            id=f"crew:{project_name}",
            source="crew",
            title=f"Project: {project_name} ({current_phase} phase)",
            summary=proj.get("outcome_summary", f"Phase: {current_phase}, Complexity: {complexity}/7"),
            excerpt=f"Signals: {', '.join(signals)}" if signals else "",
            age_days=0,
            metadata={
                "project": project_name,
                "phase": current_phase,
                "signals": signals,
                "complexity": complexity,
                "semantic_score": semantic_score,
            }
        ))

    return items
