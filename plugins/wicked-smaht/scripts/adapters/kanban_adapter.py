"""
wicked-kanban adapter for wicked-smaht.

Queries active tasks, artifacts, and project tracking.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, discover_script, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-kanban for relevant tasks."""
    items = []

    kanban_script = discover_script("wicked-kanban", "kanban.py")
    if not kanban_script:
        return items

    # Discover active project IDs from kanban storage
    kanban_storage = Path.home() / ".something-wicked" / "wicked-kanban" / "projects"
    project_ids = []
    if project:
        project_ids = [project]
    elif kanban_storage.is_dir():
        project_ids = [p.name for p in kanban_storage.iterdir() if p.is_dir()][:5]
    if not project_ids:
        return items

    # Query each project (kanban list-tasks outputs JSON, requires project_id positional arg)
    all_stdout = []
    for pid in project_ids:
        cmd = [sys.executable, str(kanban_script), "list-tasks", pid]
        returncode, stdout, stderr = await run_subprocess(cmd, timeout=3.0)
        if returncode == 0 and stdout.strip():
            all_stdout.append(stdout.strip())

    # Merge results from all projects
    stdout = ""
    if all_stdout:
        # Each project returns a JSON array; merge into one
        import itertools
        merged = []
        for s in all_stdout:
            try:
                merged.extend(json.loads(s))
            except json.JSONDecodeError:
                pass
        stdout = json.dumps(merged)
        returncode = 0
    else:
        return items

    if stdout.strip():
        try:
            tasks = json.loads(stdout)
            if not isinstance(tasks, list):
                tasks = tasks.get("tasks", [])

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
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-kanban JSON parse failed: {e}", file=sys.stderr)

    return items
