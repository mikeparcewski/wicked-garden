"""
wicked-kanban adapter for wicked-smaht.

Queries active tasks, artifacts, and project tracking.
Uses direct import of kanban.kanban since all scripts are co-located.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

# Direct import of the kanban module (co-located under scripts/kanban/)
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from kanban.kanban import KanbanStore


def _get_tasks(project: str = None) -> list:
    """Synchronous kanban task list — called via run_in_thread for async."""
    try:
        store = KanbanStore()
        kanban_storage = Path.home() / ".something-wicked" / "wicked-kanban" / "projects"

        project_ids = []
        if project:
            project_ids = [project]
        elif kanban_storage.is_dir():
            project_ids = [p.name for p in kanban_storage.iterdir() if p.is_dir()][:5]

        if not project_ids:
            return []

        all_tasks = []
        for pid in project_ids:
            try:
                tasks = store.list_tasks(pid)
                if tasks:
                    all_tasks.extend(tasks)
            except Exception:
                continue

        return all_tasks
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-kanban for relevant tasks."""
    items = []

    tasks = await run_in_thread(_get_tasks, project)
    if not tasks:
        return items

    now = datetime.now(timezone.utc)
    prompt_lower = prompt.lower()

    for task in tasks:
        name = task.get("name", "")
        description = task.get("description", "") or ""
        swimlane = task.get("swimlane", "")

        # Skip completed tasks unless explicitly searching
        if swimlane == "done" and "completed" not in prompt_lower:
            continue

        # Calculate age
        created = task.get("created_at", "")
        age_days = 0
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_days = (now - created_dt).days
            except Exception:
                pass

        # Simple relevance scoring
        name_lower = name.lower()
        desc_lower = description.lower()
        semantic_score = 0.3
        for word in prompt_lower.split():
            if len(word) > 3:
                if word in name_lower:
                    semantic_score += 0.3
                if word in desc_lower:
                    semantic_score += 0.1
        semantic_score = min(semantic_score, 1.0)

        # Boost in-progress tasks
        if swimlane in ("doing", "in_progress"):
            semantic_score = min(semantic_score + 0.2, 1.0)

        items.append(ContextItem(
            id=task.get("id", ""),
            source="kanban",
            title=f"[{swimlane}] {name}",
            summary=description[:200] if description else name,
            excerpt=description,
            age_days=age_days,
            metadata={
                "status": swimlane,
                "project": task.get("initiative_id", ""),
                "priority": task.get("priority", ""),
                "semantic_score": semantic_score,
            }
        ))

    return items
