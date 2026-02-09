"""
wicked-crew adapter for wicked-smaht.

Queries project state, phase, outcomes, and constraints.
"""

import json
import sys
from datetime import datetime, timezone
from typing import List

from . import ContextItem, discover_script, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-crew for project state."""
    items = []

    crew_script = discover_script("wicked-crew", "crew.py")
    if not crew_script:
        return items

    # Get active projects
    cmd = [sys.executable, str(crew_script), "list-projects", "--active", "--json"]
    returncode, stdout, stderr = await run_subprocess(cmd, timeout=5.0)

    if returncode == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            projects = data.get("projects", [])

            now = datetime.now(timezone.utc)

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
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-crew JSON parse failed: {e}", file=sys.stderr)
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-crew query failed: {stderr}", file=sys.stderr)

    return items
