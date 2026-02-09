"""
wicked-kanban adapter for wicked-smaht.

Queries active tasks, artifacts, and project tracking.
"""

import json
import sys
from datetime import datetime, timezone
from typing import List

from . import ContextItem, discover_script, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-kanban for relevant tasks."""
    items = []

    kanban_script = discover_script("wicked-kanban", "kanban.py")
    if not kanban_script:
        return items

    # Query via CLI using async subprocess
    cmd = [sys.executable, str(kanban_script), "list-tasks", "--json"]
    if project:
        cmd.extend(["--project", project])

    returncode, stdout, stderr = await run_subprocess(cmd, timeout=5.0)

    if returncode == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            tasks = data.get("tasks", [])

            now = datetime.now(timezone.utc)
            prompt_lower = prompt.lower()

            for task in tasks:
                title = task.get("title", "")
                description = task.get("description", "")
                status = task.get("status", "")

                # Skip completed tasks unless explicitly searching
                if status == "done" and "completed" not in prompt_lower:
                    continue

                # Calculate age
                created = task.get("created", "")
                age_days = 0
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age_days = (now - created_dt).days
                    except Exception:
                        pass

                # Simple relevance scoring
                title_lower = title.lower()
                desc_lower = description.lower()
                semantic_score = 0.3
                for word in prompt_lower.split():
                    if len(word) > 3:
                        if word in title_lower:
                            semantic_score += 0.3
                        if word in desc_lower:
                            semantic_score += 0.1
                semantic_score = min(semantic_score, 1.0)

                # Boost in-progress tasks
                if status in ("in_progress", "doing"):
                    semantic_score = min(semantic_score + 0.2, 1.0)

                items.append(ContextItem(
                    id=task.get("id", ""),
                    source="kanban",
                    title=f"[{status}] {title}",
                    summary=description[:200] if description else title,
                    excerpt=description,
                    age_days=age_days,
                    metadata={
                        "status": status,
                        "project": task.get("project", ""),
                        "priority": task.get("priority", ""),
                        "semantic_score": semantic_score,
                    }
                ))
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-kanban JSON parse failed: {e}", file=sys.stderr)
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-kanban query failed: {stderr}", file=sys.stderr)

    return items
