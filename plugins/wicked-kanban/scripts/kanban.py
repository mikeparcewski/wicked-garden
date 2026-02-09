"""
Wicked Kanban - Folder-based Storage

File structure:
    ~/.something-wicked/wicked-kanban/
    ├── config.json                 # Global config, repo mappings
    ├── active_context.json         # Current session state
    └── projects/
        └── {project-id}/
            ├── project.json        # Project metadata
            ├── swimlanes.json      # Swimlane definitions
            ├── tasks/
            │   ├── index.json      # Task ID → swimlane mapping
            │   └── {task-id}.json  # Individual tasks
            ├── initiatives/
            │   └── {id}.json
            └── activity/
                └── {date}.jsonl    # Daily activity log
"""

import json
import os
import uuid
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List, Dict


def generate_id() -> str:
    """Generate a short unique ID."""
    return str(uuid.uuid4())[:8]


def get_utc_timestamp() -> str:
    """Generate UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_date_str() -> str:
    """Get current date string for activity logs."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class KanbanStore:
    """Folder-based kanban storage with per-file operations."""

    DEFAULT_SWIMLANES = [
        {"id": "todo", "name": "To Do", "order": 0, "is_complete": False},
        {"id": "in_progress", "name": "In Progress", "order": 1, "is_complete": False},
        {"id": "done", "name": "Done", "order": 2, "is_complete": True},
    ]

    def __init__(self):
        self.base_path = Path(os.environ.get(
            'WICKED_KANBAN_DATA_DIR',
            str(Path.home() / '.something-wicked' / 'wicked-kanban')
        ))
        self.projects_path = self.base_path / 'projects'
        self._ensure_base_structure()

    def _ensure_base_structure(self):
        """Create base directory structure."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.projects_path.mkdir(exist_ok=True)

    # ==================== Path Helpers ====================

    def _project_dir(self, project_id: str) -> Path:
        return self.projects_path / project_id

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _swimlanes_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "swimlanes.json"

    def _tasks_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "tasks"

    def _task_file(self, project_id: str, task_id: str) -> Path:
        return self._tasks_dir(project_id) / f"{task_id}.json"

    def _task_index_file(self, project_id: str) -> Path:
        return self._tasks_dir(project_id) / "index.json"

    def _initiatives_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "initiatives"

    def _initiative_file(self, project_id: str, initiative_id: str) -> Path:
        return self._initiatives_dir(project_id) / f"{initiative_id}.json"

    def _activity_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "activity"

    def _activity_file(self, project_id: str, date_str: str = None) -> Path:
        if not date_str:
            date_str = get_date_str()
        return self._activity_dir(project_id) / f"{date_str}.jsonl"

    # ==================== File I/O ====================

    def _read_json(self, path: Path) -> Optional[Dict]:
        """Read JSON file, return None if not exists."""
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding='utf-8'))

    def _write_json(self, path: Path, data: Dict):
        """Write JSON file with directory creation."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _append_jsonl(self, path: Path, record: Dict):
        """Append to JSONL file (activity log)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(record) + '\n')
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # ==================== Activity Log ====================

    def _log_activity(self, project_id: str, activity_type: str, **kwargs):
        """Append activity to daily log."""
        record = {
            "ts": get_utc_timestamp(),
            "type": activity_type,
            **kwargs
        }
        self._append_jsonl(self._activity_file(project_id), record)

    # ==================== Task Index ====================

    def _load_index(self, project_id: str) -> Dict:
        """Load task index, create if missing."""
        index = self._read_json(self._task_index_file(project_id))
        if not index:
            index = {"by_swimlane": {}, "by_initiative": {}, "all": []}
        return index

    def _save_index(self, project_id: str, index: Dict):
        """Save task index."""
        self._write_json(self._task_index_file(project_id), index)

    def _index_add_task(self, project_id: str, task: Dict):
        """Add task to index."""
        index = self._load_index(project_id)
        task_id = task["id"]
        swimlane = task.get("swimlane", "todo")
        initiative = task.get("initiative_id")

        # Add to all
        if task_id not in index.get("all", []):
            index.setdefault("all", []).append(task_id)

        # Add to swimlane
        index.setdefault("by_swimlane", {}).setdefault(swimlane, [])
        if task_id not in index["by_swimlane"][swimlane]:
            index["by_swimlane"][swimlane].append(task_id)

        # Add to initiative
        if initiative:
            index.setdefault("by_initiative", {}).setdefault(initiative, [])
            if task_id not in index["by_initiative"][initiative]:
                index["by_initiative"][initiative].append(task_id)

        self._save_index(project_id, index)

    def _index_update_task(self, project_id: str, task_id: str,
                           old_swimlane: str, new_swimlane: str,
                           old_initiative: str = None, new_initiative: str = None):
        """Update task position in index."""
        index = self._load_index(project_id)

        # Update swimlane
        if old_swimlane != new_swimlane:
            if old_swimlane in index.get("by_swimlane", {}):
                if task_id in index["by_swimlane"][old_swimlane]:
                    index["by_swimlane"][old_swimlane].remove(task_id)
            index.setdefault("by_swimlane", {}).setdefault(new_swimlane, [])
            if task_id not in index["by_swimlane"][new_swimlane]:
                index["by_swimlane"][new_swimlane].append(task_id)

        # Update initiative
        if old_initiative != new_initiative:
            if old_initiative and old_initiative in index.get("by_initiative", {}):
                if task_id in index["by_initiative"][old_initiative]:
                    index["by_initiative"][old_initiative].remove(task_id)
            if new_initiative:
                index.setdefault("by_initiative", {}).setdefault(new_initiative, [])
                if task_id not in index["by_initiative"][new_initiative]:
                    index["by_initiative"][new_initiative].append(task_id)

        self._save_index(project_id, index)

    def _index_remove_task(self, project_id: str, task_id: str):
        """Remove task from index."""
        index = self._load_index(project_id)

        # Remove from all
        if task_id in index.get("all", []):
            index["all"].remove(task_id)

        # Remove from swimlanes
        for swimlane_tasks in index.get("by_swimlane", {}).values():
            if task_id in swimlane_tasks:
                swimlane_tasks.remove(task_id)

        # Remove from initiatives
        for initiative_tasks in index.get("by_initiative", {}).values():
            if task_id in initiative_tasks:
                initiative_tasks.remove(task_id)

        self._save_index(project_id, index)

    # ==================== Projects ====================

    def list_projects(self) -> List[Dict]:
        """List all projects (metadata only)."""
        projects = []
        for project_dir in self.projects_path.iterdir():
            if project_dir.is_dir():
                project = self._read_json(project_dir / "project.json")
                if project:
                    # Add task count from index
                    index = self._load_index(project["id"])
                    project["task_count"] = len(index.get("all", []))
                    projects.append(project)
        return sorted(projects, key=lambda p: p.get("created_at", ""), reverse=True)

    def get_project(self, project_id: str) -> Optional[Dict]:
        """Get project metadata."""
        return self._read_json(self._project_file(project_id))

    def create_project(self, name: str, description: str = None,
                       repo_path: str = None) -> Dict:
        """Create a new project with default structure."""
        project_id = generate_id()
        project_dir = self._project_dir(project_id)

        # Create directories
        project_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_dir(project_id).mkdir(exist_ok=True)
        self._initiatives_dir(project_id).mkdir(exist_ok=True)
        self._activity_dir(project_id).mkdir(exist_ok=True)

        # Project metadata
        project = {
            "id": project_id,
            "name": name,
            "description": description,
            "repo_path": repo_path,
            "created_at": get_utc_timestamp(),
            "created_by": "claude",
            "archived": False
        }
        self._write_json(self._project_file(project_id), project)

        # Default swimlanes
        self._write_json(self._swimlanes_file(project_id), self.DEFAULT_SWIMLANES)

        # Empty index
        self._save_index(project_id, {"by_swimlane": {}, "by_initiative": {}, "all": []})

        # Log activity
        self._log_activity(project_id, "project_created", project_name=name)

        return project

    def update_project(self, project_id: str, **updates) -> Optional[Dict]:
        """Update project metadata."""
        project = self.get_project(project_id)
        if not project:
            return None

        allowed = {'name', 'description', 'repo_path', 'archived'}
        for key, value in updates.items():
            if key in allowed:
                project[key] = value

        project["updated_at"] = get_utc_timestamp()
        self._write_json(self._project_file(project_id), project)
        self._log_activity(project_id, "project_updated", updates=list(updates.keys()))
        return project

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its contents."""
        project_dir = self._project_dir(project_id)
        if not project_dir.exists():
            return False

        import shutil
        shutil.rmtree(project_dir)
        return True

    # ==================== Swimlanes ====================

    def get_swimlanes(self, project_id: str) -> List[Dict]:
        """Get swimlanes for a project."""
        swimlanes = self._read_json(self._swimlanes_file(project_id))
        return swimlanes or []

    def create_swimlane(self, project_id: str, name: str, **kwargs) -> Optional[Dict]:
        """Create a new swimlane."""
        swimlanes = self.get_swimlanes(project_id)
        if not swimlanes and not self.get_project(project_id):
            return None

        max_order = max((s.get("order", 0) for s in swimlanes), default=-1)
        swimlane = {
            "id": kwargs.get("id") or generate_id(),
            "name": name,
            "order": kwargs.get("order", max_order + 1),
            "is_complete": kwargs.get("is_complete", False),
            "color": kwargs.get("color")
        }

        swimlanes.append(swimlane)
        swimlanes.sort(key=lambda s: s.get("order", 0))
        self._write_json(self._swimlanes_file(project_id), swimlanes)
        return swimlane

    def update_swimlane(self, project_id: str, swimlane_id: str, **updates) -> Optional[Dict]:
        """Update a swimlane."""
        swimlanes = self.get_swimlanes(project_id)

        for swimlane in swimlanes:
            if swimlane["id"] == swimlane_id:
                allowed = {'name', 'order', 'is_complete', 'color'}
                for key, value in updates.items():
                    if key in allowed:
                        swimlane[key] = value
                swimlanes.sort(key=lambda s: s.get("order", 0))
                self._write_json(self._swimlanes_file(project_id), swimlanes)
                return swimlane
        return None

    # ==================== Tasks ====================

    def get_task(self, project_id: str, task_id: str) -> Optional[Dict]:
        """Get a single task by ID."""
        return self._read_json(self._task_file(project_id, task_id))

    def list_tasks(self, project_id: str, swimlane: str = None,
                   initiative_id: str = None) -> List[Dict]:
        """List tasks, optionally filtered by swimlane or initiative."""
        index = self._load_index(project_id)

        if swimlane:
            task_ids = index.get("by_swimlane", {}).get(swimlane, [])
        elif initiative_id:
            task_ids = index.get("by_initiative", {}).get(initiative_id, [])
        else:
            task_ids = index.get("all", [])

        tasks = []
        for task_id in task_ids:
            task = self.get_task(project_id, task_id)
            if task:
                tasks.append(task)

        return sorted(tasks, key=lambda t: t.get("order", 0))

    def create_task(self, project_id: str, name: str, swimlane: str = "todo",
                    **kwargs) -> Optional[Dict]:
        """Create a new task."""
        if not self.get_project(project_id):
            return None

        # Get max order in swimlane
        existing = self.list_tasks(project_id, swimlane=swimlane)
        max_order = max((t.get("order", 0) for t in existing), default=-1)

        task_id = generate_id()
        task = {
            "id": task_id,
            "name": name,
            "swimlane": swimlane,
            "order": max_order + 1,
            "priority": kwargs.get("priority", "P2"),
            "description": kwargs.get("description"),
            "initiative_id": kwargs.get("initiative_id"),
            "assigned_to": kwargs.get("assigned_to"),
            "depends_on": kwargs.get("depends_on", []),
            "commits": [],
            "artifacts": [],
            "metadata": kwargs.get("metadata"),
            "created_at": get_utc_timestamp(),
            "created_by": kwargs.get("created_by", "claude"),
            "updated_at": get_utc_timestamp()
        }

        self._write_json(self._task_file(project_id, task_id), task)
        self._index_add_task(project_id, task)
        self._log_activity(project_id, "task_created", task_id=task_id, task_name=name)

        return task

    def update_task(self, project_id: str, task_id: str, **updates) -> Optional[Dict]:
        """Update a task."""
        task = self.get_task(project_id, task_id)
        if not task:
            return None

        old_swimlane = task.get("swimlane")
        old_initiative = task.get("initiative_id")

        allowed = {
            'name', 'description', 'swimlane', 'order', 'priority',
            'initiative_id', 'assigned_to', 'depends_on', 'metadata'
        }
        for key, value in updates.items():
            if key in allowed:
                task[key] = value

        task["updated_at"] = get_utc_timestamp()
        self._write_json(self._task_file(project_id, task_id), task)

        # Update index if swimlane or initiative changed
        new_swimlane = task.get("swimlane")
        new_initiative = task.get("initiative_id")
        if old_swimlane != new_swimlane or old_initiative != new_initiative:
            self._index_update_task(project_id, task_id,
                                    old_swimlane, new_swimlane,
                                    old_initiative, new_initiative)

        self._log_activity(project_id, "task_updated", task_id=task_id,
                           updates=list(updates.keys()))
        return task

    def delete_task(self, project_id: str, task_id: str) -> bool:
        """Delete a task."""
        task_path = self._task_file(project_id, task_id)
        if not task_path.exists():
            return False

        task_path.unlink()
        self._index_remove_task(project_id, task_id)
        self._log_activity(project_id, "task_deleted", task_id=task_id)
        return True

    def add_comment(self, project_id: str, task_id: str, content: str,
                    commenter: str = "claude") -> Optional[Dict]:
        """Add a comment to a task (stored in activity log + task)."""
        task = self.get_task(project_id, task_id)
        if not task:
            return None

        comment = {
            "id": generate_id(),
            "commenter": commenter,
            "timestamp": get_utc_timestamp(),
            "content": content
        }

        # Store in activity log
        self._log_activity(project_id, "comment", task_id=task_id,
                           comment_id=comment["id"], content=content, by=commenter)

        return comment

    def add_project_comment(self, project_id: str, content: str,
                            commenter: str = "claude") -> Optional[Dict]:
        """Add a comment at the project level (stored in activity log)."""
        project = self.get_project(project_id)
        if not project:
            return None

        comment = {
            "id": generate_id(),
            "commenter": commenter,
            "timestamp": get_utc_timestamp(),
            "content": content
        }

        # Store in activity log as project-level comment
        self._log_activity(project_id, "project_comment",
                           comment_id=comment["id"], content=content, by=commenter)

        return comment

    def add_commit(self, project_id: str, task_id: str, commit_hash: str,
                   message: str = None) -> bool:
        """Link a commit to a task."""
        task = self.get_task(project_id, task_id)
        if not task:
            return False

        commits = task.get("commits", [])
        if commit_hash not in commits:
            commits.append(commit_hash)
            task["commits"] = commits
            task["updated_at"] = get_utc_timestamp()
            self._write_json(self._task_file(project_id, task_id), task)

        self._log_activity(project_id, "commit_linked", task_id=task_id,
                           commit=commit_hash, message=message)
        return True

    def add_artifact(self, project_id: str, task_id: str, name: str,
                     artifact_type: str = "file", path: str = None,
                     url: str = None) -> Optional[Dict]:
        """Add an artifact to a task."""
        task = self.get_task(project_id, task_id)
        if not task:
            return None

        artifact = {
            "id": generate_id(),
            "name": name,
            "type": artifact_type,
            "path": path,
            "url": url,
            "created_at": get_utc_timestamp()
        }

        task.setdefault("artifacts", []).append(artifact)
        task["updated_at"] = get_utc_timestamp()
        self._write_json(self._task_file(project_id, task_id), task)

        self._log_activity(project_id, "artifact_added", task_id=task_id,
                           artifact_name=name, artifact_type=artifact_type)
        return artifact

    def get_task_blocking_status(self, project_id: str, task_id: str) -> Dict:
        """Check if a task is blocked by incomplete dependencies."""
        task = self.get_task(project_id, task_id)
        if not task:
            return {"is_blocked": False, "blocking_tasks": []}

        depends_on = task.get("depends_on", [])
        if not depends_on:
            return {"is_blocked": False, "blocking_tasks": []}

        swimlanes = self.get_swimlanes(project_id)
        complete_swimlanes = {s["id"] for s in swimlanes if s.get("is_complete")}

        blocking_tasks = []
        for dep_id in depends_on:
            dep_task = self.get_task(project_id, dep_id)
            if dep_task:
                if dep_task.get("swimlane") not in complete_swimlanes:
                    blocking_tasks.append({
                        "task_id": dep_id,
                        "task_name": dep_task.get("name"),
                        "swimlane": dep_task.get("swimlane"),
                        "priority": dep_task.get("priority")
                    })

        return {
            "is_blocked": len(blocking_tasks) > 0,
            "blocking_tasks": blocking_tasks
        }

    def get_task_with_status(self, project_id: str, task_id: str) -> Optional[Dict]:
        """Get task with blocking status computed."""
        task = self.get_task(project_id, task_id)
        if not task:
            return None

        status = self.get_task_blocking_status(project_id, task_id)
        task["is_blocked"] = status["is_blocked"]
        task["blocking_details"] = status["blocking_tasks"]
        return task

    # ==================== Initiatives ====================

    def list_initiatives(self, project_id: str) -> List[Dict]:
        """List all initiatives in a project."""
        initiatives_dir = self._initiatives_dir(project_id)
        if not initiatives_dir.exists():
            return []

        initiatives = []
        for f in initiatives_dir.glob("*.json"):
            initiative = self._read_json(f)
            if initiative:
                initiatives.append(initiative)
        return sorted(initiatives, key=lambda i: i.get("created_at", ""))

    def get_initiative(self, project_id: str, initiative_id: str) -> Optional[Dict]:
        """Get a single initiative."""
        return self._read_json(self._initiative_file(project_id, initiative_id))

    def create_initiative(self, project_id: str, name: str, **kwargs) -> Optional[Dict]:
        """Create a new initiative."""
        if not self.get_project(project_id):
            return None

        initiative_id = generate_id()
        initiative = {
            "id": initiative_id,
            "name": name,
            "goal": kwargs.get("goal"),
            "status": kwargs.get("status", "planning"),
            "start_date": kwargs.get("start_date"),
            "end_date": kwargs.get("end_date"),
            "created_at": get_utc_timestamp(),
            "created_by": kwargs.get("created_by", "claude")
        }

        self._write_json(self._initiative_file(project_id, initiative_id), initiative)
        self._log_activity(project_id, "initiative_created",
                           initiative_id=initiative_id, initiative_name=name)
        return initiative

    def update_initiative(self, project_id: str, initiative_id: str,
                          **updates) -> Optional[Dict]:
        """Update an initiative."""
        initiative = self.get_initiative(project_id, initiative_id)
        if not initiative:
            return None

        allowed = {'name', 'goal', 'status', 'start_date', 'end_date'}
        for key, value in updates.items():
            if key in allowed:
                initiative[key] = value

        initiative["updated_at"] = get_utc_timestamp()
        self._write_json(self._initiative_file(project_id, initiative_id), initiative)
        return initiative

    def delete_initiative(self, project_id: str, initiative_id: str) -> bool:
        """Delete an initiative."""
        path = self._initiative_file(project_id, initiative_id)
        if not path.exists():
            return False

        path.unlink()

        # Clear initiative_id from tasks
        index = self._load_index(project_id)
        task_ids = index.get("by_initiative", {}).get(initiative_id, [])
        for task_id in task_ids:
            task = self.get_task(project_id, task_id)
            if task:
                task["initiative_id"] = None
                self._write_json(self._task_file(project_id, task_id), task)

        # Update index
        if initiative_id in index.get("by_initiative", {}):
            del index["by_initiative"][initiative_id]
            self._save_index(project_id, index)

        return True

    # ==================== Search ====================

    def search(self, query: str, project_id: str = None,
               include_comments: bool = True) -> List[Dict]:
        """Search tasks by name/description and optionally comments."""
        query_lower = query.lower()
        results = []
        seen_tasks = set()

        projects = [self.get_project(project_id)] if project_id else self.list_projects()

        for project in projects:
            if not project:
                continue
            pid = project["id"]
            pname = project["name"]

            # Search task names and descriptions
            for task in self.list_tasks(pid):
                name = task.get("name", "").lower()
                desc = (task.get("description") or "").lower()
                if query_lower in name or query_lower in desc:
                    task_key = (pid, task["id"])
                    if task_key not in seen_tasks:
                        seen_tasks.add(task_key)
                        results.append({
                            "task_id": task["id"],
                            "task_name": task["name"],
                            "project_id": pid,
                            "project_name": pname,
                            "swimlane": task.get("swimlane"),
                            "priority": task.get("priority"),
                            "match_type": "task"
                        })

            # Search comments in activity log
            if include_comments:
                activity = self.get_activity(pid, limit=1000)
                for entry in activity:
                    if entry.get("type") == "comment":
                        content = (entry.get("content") or "").lower()
                        if query_lower in content:
                            task_id = entry.get("task_id")
                            task_key = (pid, task_id)
                            if task_key not in seen_tasks:
                                seen_tasks.add(task_key)
                                task = self.get_task(pid, task_id)
                                if task:
                                    results.append({
                                        "task_id": task_id,
                                        "task_name": task.get("name", "Unknown"),
                                        "project_id": pid,
                                        "project_name": pname,
                                        "swimlane": task.get("swimlane"),
                                        "priority": task.get("priority"),
                                        "match_type": "comment"
                                    })

        return results

    # ==================== Activity ====================

    def get_activity(self, project_id: str, date_str: str = None,
                     limit: int = 100) -> List[Dict]:
        """Get activity log entries."""
        if date_str:
            files = [self._activity_file(project_id, date_str)]
        else:
            activity_dir = self._activity_dir(project_id)
            files = sorted(activity_dir.glob("*.jsonl"), reverse=True)

        entries = []
        for f in files:
            if not f.exists():
                continue
            with open(f, 'r', encoding='utf-8') as file:
                for line in file:
                    if line.strip():
                        entries.append(json.loads(line))
                        if len(entries) >= limit:
                            return entries
        return entries

    # ==================== Config ====================

    def get_config(self) -> Dict:
        """Get global config."""
        config_path = self.base_path / "config.json"
        return self._read_json(config_path) or {}

    def save_config(self, config: Dict):
        """Save global config."""
        self._write_json(self.base_path / "config.json", config)

    def get_project_for_repo(self, repo_path: str) -> Optional[str]:
        """Get project ID for a repo path."""
        config = self.get_config()
        return config.get("repo_projects", {}).get(repo_path)

    def set_project_for_repo(self, repo_path: str, project_id: str):
        """Map a repo to a project."""
        config = self.get_config()
        config.setdefault("repo_projects", {})[repo_path] = project_id
        self.save_config(config)

    # ==================== Active Context ====================

    def get_active_context(self) -> Dict:
        """Get current session context."""
        ctx_path = self.base_path / "active_context.json"
        return self._read_json(ctx_path) or {}

    def set_active_context(self, **updates):
        """Update active session context."""
        ctx = self.get_active_context()
        ctx.update(updates)
        ctx["updated_at"] = get_utc_timestamp()
        self._write_json(self.base_path / "active_context.json", ctx)

    def get_active_task(self) -> Optional[Dict]:
        """Get the currently active task."""
        ctx = self.get_active_context()
        project_id = ctx.get("project_id")
        task_id = ctx.get("active_task_id")
        if project_id and task_id:
            return self.get_task(project_id, task_id)
        return None


# ==================== Module Interface ====================

_store: Optional[KanbanStore] = None


def get_store() -> KanbanStore:
    """Get or create the kanban store."""
    global _store
    if _store is None:
        _store = KanbanStore()
    return _store


# ==================== CLI ====================

def main():
    """CLI interface for kanban operations."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Wicked Kanban Operations")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # list-projects
    subparsers.add_parser('list-projects', help='List all projects')

    # get-project
    get_proj = subparsers.add_parser('get-project', help='Get project details')
    get_proj.add_argument('project_id', help='Project ID')

    # create-project
    create_proj = subparsers.add_parser('create-project', help='Create a project')
    create_proj.add_argument('name', help='Project name')
    create_proj.add_argument('--description', '-d', help='Description')
    create_proj.add_argument('--repo', help='Repository path')

    # list-tasks
    list_tasks = subparsers.add_parser('list-tasks', help='List tasks')
    list_tasks.add_argument('project_id', help='Project ID')
    list_tasks.add_argument('--swimlane', '-s', help='Filter by swimlane')
    list_tasks.add_argument('--initiative', '-i', help='Filter by initiative')

    # get-task
    get_task = subparsers.add_parser('get-task', help='Get task details')
    get_task.add_argument('project_id', help='Project ID')
    get_task.add_argument('task_id', help='Task ID')
    get_task.add_argument('--with-status', action='store_true',
                          help='Include blocking status')

    # create-task
    create_task = subparsers.add_parser('create-task', help='Create a task')
    create_task.add_argument('project_id', help='Project ID')
    create_task.add_argument('name', help='Task name')
    create_task.add_argument('--swimlane', '-s', default='todo', help='Swimlane (default: todo)')
    create_task.add_argument('--priority', '-p', default='P2', help='Priority (P0-P3)')
    create_task.add_argument('--description', '-d', help='Description')
    create_task.add_argument('--initiative', help='Initiative ID')
    create_task.add_argument('--depends', nargs='+', help='Task IDs this task depends on')

    # update-task
    update_task = subparsers.add_parser('update-task', help='Update a task')
    update_task.add_argument('project_id', help='Project ID')
    update_task.add_argument('task_id', help='Task ID')
    update_task.add_argument('--swimlane', help='New swimlane')
    update_task.add_argument('--priority', help='New priority')
    update_task.add_argument('--name', help='New name')
    update_task.add_argument('--description', help='New description')
    update_task.add_argument('--initiative', help='Initiative ID')
    update_task.add_argument('--depends', nargs='+', help='Task IDs this task depends on')
    update_task.add_argument('--add-depends', nargs='+', help='Add task IDs to depends_on')
    update_task.add_argument('--remove-depends', nargs='+', help='Remove task IDs from depends_on')

    # add-comment
    add_comment = subparsers.add_parser('add-comment', help='Add comment to task')
    add_comment.add_argument('project_id', help='Project ID')
    add_comment.add_argument('task_id', help='Task ID')
    add_comment.add_argument('content', help='Comment text')

    # add-project-comment
    add_proj_comment = subparsers.add_parser('add-project-comment', help='Add comment to project')
    add_proj_comment.add_argument('project_id', help='Project ID')
    add_proj_comment.add_argument('content', help='Comment text')

    # add-commit
    add_commit = subparsers.add_parser('add-commit', help='Link commit to task')
    add_commit.add_argument('project_id', help='Project ID')
    add_commit.add_argument('task_id', help='Task ID')
    add_commit.add_argument('hash', help='Commit hash')
    add_commit.add_argument('--message', '-m', help='Commit message')

    # search
    search_cmd = subparsers.add_parser('search', help='Search tasks')
    search_cmd.add_argument('query', help='Search query')
    search_cmd.add_argument('--project', help='Limit to project ID')

    # activity
    activity = subparsers.add_parser('activity', help='Get activity log')
    activity.add_argument('project_id', help='Project ID')
    activity.add_argument('--date', help='Filter by date (YYYY-MM-DD)')
    activity.add_argument('--limit', type=int, default=50, help='Max entries')

    # list-initiatives
    list_init = subparsers.add_parser('list-initiatives', help='List initiatives')
    list_init.add_argument('project_id', help='Project ID')

    # create-initiative
    create_init = subparsers.add_parser('create-initiative', help='Create initiative')
    create_init.add_argument('project_id', help='Project ID')
    create_init.add_argument('name', help='Initiative name')
    create_init.add_argument('--goal', help='Goal')
    create_init.add_argument('--status', default='planning', help='Status')
    create_init.add_argument('--start', help='Start date (YYYY-MM-DD)')
    create_init.add_argument('--end', help='End date (YYYY-MM-DD)')

    # update-initiative
    update_init = subparsers.add_parser('update-initiative', help='Update initiative')
    update_init.add_argument('project_id', help='Project ID')
    update_init.add_argument('initiative_id', help='Initiative ID')
    update_init.add_argument('--name', help='New name')
    update_init.add_argument('--goal', help='New goal')
    update_init.add_argument('--status', help='New status (planning, active, completed, archived)')
    update_init.add_argument('--start', help='Start date (YYYY-MM-DD)')
    update_init.add_argument('--end', help='End date (YYYY-MM-DD)')

    # add-artifact
    add_artifact = subparsers.add_parser('add-artifact', help='Add artifact to task')
    add_artifact.add_argument('project_id', help='Project ID')
    add_artifact.add_argument('task_id', help='Task ID')
    add_artifact.add_argument('name', help='Artifact name')
    add_artifact.add_argument('--type', '-t', default='file',
                              help='Artifact type (file, url, image, document)')
    add_artifact.add_argument('--path', help='File path')
    add_artifact.add_argument('--url', help='URL')

    # get-initiative
    get_init = subparsers.add_parser('get-initiative', help='Get initiative details')
    get_init.add_argument('project_id', help='Project ID')
    get_init.add_argument('initiative_id', help='Initiative ID')

    # delete-initiative
    delete_init = subparsers.add_parser('delete-initiative', help='Delete initiative')
    delete_init.add_argument('project_id', help='Project ID')
    delete_init.add_argument('initiative_id', help='Initiative ID')

    # delete-task
    delete_task = subparsers.add_parser('delete-task', help='Delete task')
    delete_task.add_argument('project_id', help='Project ID')
    delete_task.add_argument('task_id', help='Task ID')

    args = parser.parse_args()
    store = get_store()

    result = None

    if args.command == 'list-projects':
        result = store.list_projects()

    elif args.command == 'get-project':
        result = store.get_project(args.project_id)
        if not result:
            print(f"Project not found: {args.project_id}", file=sys.stderr)
            return 1

    elif args.command == 'create-project':
        result = store.create_project(args.name, args.description, args.repo)

    elif args.command == 'list-tasks':
        result = store.list_tasks(args.project_id, args.swimlane, args.initiative)

    elif args.command == 'get-task':
        if args.with_status:
            result = store.get_task_with_status(args.project_id, args.task_id)
        else:
            result = store.get_task(args.project_id, args.task_id)
        if not result:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            return 1

    elif args.command == 'create-task':
        depends_on = args.depends if args.depends else []
        result = store.create_task(
            args.project_id, args.name, args.swimlane,
            priority=args.priority, description=args.description,
            initiative_id=args.initiative, depends_on=depends_on
        )
        if not result:
            print("Failed to create task", file=sys.stderr)
            return 1

    elif args.command == 'update-task':
        updates = {}
        if args.swimlane:
            updates['swimlane'] = args.swimlane
        if args.priority:
            updates['priority'] = args.priority
        if args.name:
            updates['name'] = args.name
        if args.description:
            updates['description'] = args.description
        if args.initiative:
            updates['initiative_id'] = args.initiative
        if args.depends:
            updates['depends_on'] = args.depends

        # Handle add/remove depends_on
        if args.add_depends or args.remove_depends:
            task = store.get_task(args.project_id, args.task_id)
            if task:
                current_deps = set(task.get('depends_on', []))
                if args.add_depends:
                    current_deps.update(args.add_depends)
                if args.remove_depends:
                    current_deps.difference_update(args.remove_depends)
                updates['depends_on'] = list(current_deps)

        result = store.update_task(args.project_id, args.task_id, **updates)
        if not result:
            print("Failed to update task", file=sys.stderr)
            return 1

    elif args.command == 'add-comment':
        result = store.add_comment(args.project_id, args.task_id, args.content)
        if not result:
            print("Failed to add comment", file=sys.stderr)
            return 1

    elif args.command == 'add-project-comment':
        result = store.add_project_comment(args.project_id, args.content)
        if not result:
            print("Failed to add project comment", file=sys.stderr)
            return 1

    elif args.command == 'add-commit':
        if store.add_commit(args.project_id, args.task_id, args.hash, args.message):
            result = {"status": "ok", "commit": args.hash}
        else:
            print("Failed to link commit", file=sys.stderr)
            return 1

    elif args.command == 'search':
        result = store.search(args.query, args.project)

    elif args.command == 'activity':
        result = store.get_activity(args.project_id, args.date, args.limit)

    elif args.command == 'list-initiatives':
        result = store.list_initiatives(args.project_id)

    elif args.command == 'create-initiative':
        result = store.create_initiative(
            args.project_id, args.name,
            goal=args.goal, status=args.status,
            start_date=args.start, end_date=args.end
        )
        if not result:
            print("Failed to create initiative", file=sys.stderr)
            return 1

    elif args.command == 'update-initiative':
        updates = {}
        if args.name:
            updates['name'] = args.name
        if args.goal:
            updates['goal'] = args.goal
        if args.status:
            updates['status'] = args.status
        if args.start:
            updates['start_date'] = args.start
        if args.end:
            updates['end_date'] = args.end

        result = store.update_initiative(args.project_id, args.initiative_id, **updates)
        if not result:
            print("Failed to update initiative", file=sys.stderr)
            return 1

    elif args.command == 'get-initiative':
        result = store.get_initiative(args.project_id, args.initiative_id)
        if not result:
            print(f"Initiative not found: {args.initiative_id}", file=sys.stderr)
            return 1

    elif args.command == 'delete-initiative':
        if store.delete_initiative(args.project_id, args.initiative_id):
            result = {"status": "deleted", "initiative_id": args.initiative_id}
        else:
            print("Failed to delete initiative", file=sys.stderr)
            return 1

    elif args.command == 'add-artifact':
        result = store.add_artifact(
            args.project_id, args.task_id, args.name,
            artifact_type=args.type, path=args.path, url=args.url
        )
        if not result:
            print("Failed to add artifact", file=sys.stderr)
            return 1

    elif args.command == 'delete-task':
        if store.delete_task(args.project_id, args.task_id):
            result = {"status": "deleted", "task_id": args.task_id}
        else:
            print("Failed to delete task", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 0

    if result is not None:
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
