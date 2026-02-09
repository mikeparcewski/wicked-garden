# KanbanStore API Documentation

Complete API reference for the wicked-kanban storage layer.

## Overview

The `KanbanStore` class provides a file-based storage system for kanban boards with support for projects, tasks, initiatives, swimlanes, and activity tracking.

**Base Path**: `~/.something-wicked/wicked-kanban/` (configurable via `WICKED_KANBAN_DATA_DIR`)

**Storage Structure**:
```
~/.something-wicked/wicked-kanban/
├── config.json                 # Global config, repo mappings
├── active_context.json         # Current session state
└── projects/
    └── {project-id}/
        ├── project.json        # Project metadata
        ├── swimlanes.json      # Swimlane definitions
        ├── tasks/
        │   ├── index.json      # Task ID → swimlane/initiative mapping
        │   └── {task-id}.json  # Individual tasks
        ├── initiatives/
        │   └── {id}.json       # Initiative definitions
        └── activity/
            └── {date}.jsonl    # Daily activity logs
```

---

## Project Management

### `list_projects()`

List all projects with metadata and task counts.

**Returns**: `List[Dict]`
- Sorted by `created_at` (newest first)
- Each project includes:
  - `id` (str): Project ID
  - `name` (str): Project name
  - `description` (str|None): Project description
  - `repo_path` (str|None): Associated repository path
  - `created_at` (str): ISO 8601 timestamp
  - `created_by` (str): Creator identifier
  - `archived` (bool): Archive status
  - `task_count` (int): Number of tasks in project
  - `updated_at` (str|None): Last update timestamp

**CLI Example**:
```bash
python kanban.py list-projects
```

**Python Example**:
```python
from kanban import get_store

store = get_store()
projects = store.list_projects()
for project in projects:
    print(f"{project['name']}: {project['task_count']} tasks")
```

---

### `get_project(project_id: str)`

Retrieve a single project by ID.

**Parameters**:
- `project_id` (str): Unique project identifier

**Returns**: `Optional[Dict]`
- Project metadata (same structure as `list_projects`)
- `None` if project doesn't exist

**CLI Example**:
```bash
python kanban.py get-project abc12345
```

**Python Example**:
```python
project = store.get_project("abc12345")
if project:
    print(f"Project: {project['name']}")
else:
    print("Project not found")
```

---

### `create_project(name: str, description: str = None, repo_path: str = None)`

Create a new project with default structure.

**Parameters**:
- `name` (str, required): Project name
- `description` (str, optional): Project description
- `repo_path` (str, optional): Associated repository path

**Returns**: `Dict`
- Newly created project metadata
- Auto-generates:
  - 8-character project ID
  - Default swimlanes (To Do, In Progress, Done)
  - Empty task index
  - Activity log directory

**Side Effects**:
- Creates project directory structure
- Logs `project_created` activity event

**CLI Example**:
```bash
python kanban.py create-project "API Redesign" \
  --description "Redesign REST API" \
  --repo /path/to/repo
```

**Python Example**:
```python
project = store.create_project(
    name="API Redesign",
    description="Redesign REST API",
    repo_path="/Users/dev/my-project"
)
print(f"Created project {project['id']}")
```

---

### `update_project(project_id: str, **updates)`

Update project metadata.

**Parameters**:
- `project_id` (str, required): Project ID
- `**updates`: Keyword arguments for fields to update

**Allowed Update Fields**:
- `name` (str): New project name
- `description` (str): New description
- `repo_path` (str): New repository path
- `archived` (bool): Archive status

**Returns**: `Optional[Dict]`
- Updated project metadata
- `None` if project doesn't exist

**Side Effects**:
- Sets `updated_at` timestamp
- Logs `project_updated` activity event

**CLI Example**:
```bash
# Note: Not exposed in CLI, use Python API
```

**Python Example**:
```python
project = store.update_project(
    "abc12345",
    name="API Redesign v2",
    archived=True
)
```

---

### `delete_project(project_id: str)`

Permanently delete a project and all its contents.

**Parameters**:
- `project_id` (str): Project ID to delete

**Returns**: `bool`
- `True` if deleted successfully
- `False` if project doesn't exist

**Warning**: This operation is **irreversible** and deletes:
- All tasks
- All initiatives
- All activity logs
- All project metadata

**Python Example**:
```python
if store.delete_project("abc12345"):
    print("Project deleted")
else:
    print("Project not found")
```

---

## Task Management

### `list_tasks(project_id: str, swimlane: str = None, initiative_id: str = None)`

List tasks with optional filtering.

**Parameters**:
- `project_id` (str, required): Project ID
- `swimlane` (str, optional): Filter by swimlane ID
- `initiative_id` (str, optional): Filter by initiative ID

**Returns**: `List[Dict]`
- Sorted by `order` field
- Each task includes:
  - `id` (str): Task ID
  - `name` (str): Task name
  - `swimlane` (str): Current swimlane ID
  - `order` (int): Position within swimlane
  - `priority` (str): Priority level (P0-P3)
  - `description` (str|None): Task description
  - `initiative_id` (str|None): Associated initiative
  - `assigned_to` (str|None): Assignee
  - `depends_on` (List[str]): Task dependencies
  - `commits` (List[str]): Linked commit hashes
  - `artifacts` (List[Dict]): Attached artifacts
  - `metadata` (Dict|None): Custom metadata
  - `created_at` (str): ISO 8601 timestamp
  - `created_by` (str): Creator identifier
  - `updated_at` (str): Last update timestamp

**CLI Example**:
```bash
# All tasks in project
python kanban.py list-tasks abc12345

# Filter by swimlane
python kanban.py list-tasks abc12345 --swimlane todo

# Filter by initiative
python kanban.py list-tasks abc12345 --initiative xyz789
```

**Python Example**:
```python
# All tasks
tasks = store.list_tasks("abc12345")

# Only in-progress tasks
in_progress = store.list_tasks("abc12345", swimlane="in_progress")

# Tasks in specific initiative
initiative_tasks = store.list_tasks("abc12345", initiative_id="xyz789")
```

---

### `get_task(project_id: str, task_id: str)`

Retrieve a single task by ID.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID

**Returns**: `Optional[Dict]`
- Task data (same structure as `list_tasks`)
- `None` if task doesn't exist

**CLI Example**:
```bash
python kanban.py get-task abc12345 task001
```

**Python Example**:
```python
task = store.get_task("abc12345", "task001")
if task:
    print(f"Task: {task['name']} ({task['swimlane']})")
```

---

### `get_task_with_status(project_id: str, task_id: str)`

Retrieve a task with computed blocking status.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID

**Returns**: `Optional[Dict]`
- Task data with additional fields:
  - `is_blocked` (bool): Whether task is blocked by dependencies
  - `blocking_details` (List[Dict]): Details of blocking tasks
- `None` if task doesn't exist

**CLI Example**:
```bash
python kanban.py get-task abc12345 task001 --with-status
```

**Python Example**:
```python
task = store.get_task_with_status("abc12345", "task001")
if task['is_blocked']:
    print(f"Blocked by {len(task['blocking_details'])} tasks")
```

---

### `create_task(project_id: str, name: str, swimlane: str = "todo", **kwargs)`

Create a new task.

**Parameters**:
- `project_id` (str, required): Project ID
- `name` (str, required): Task name
- `swimlane` (str, optional): Initial swimlane (default: "todo")

**Optional Keyword Arguments**:
- `priority` (str): Priority level (default: "P2")
- `description` (str): Task description
- `initiative_id` (str): Initiative ID to associate with
- `assigned_to` (str): Assignee identifier
- `depends_on` (List[str]): List of task IDs this task depends on
- `metadata` (Dict): Custom metadata
- `created_by` (str): Creator identifier (default: "claude")

**Returns**: `Optional[Dict]`
- Newly created task
- `None` if project doesn't exist

**Side Effects**:
- Auto-generates 8-character task ID
- Assigns `order` based on existing tasks in swimlane
- Updates task index
- Logs `task_created` activity event

**CLI Example**:
```bash
python kanban.py create-task abc12345 "Fix login bug" \
  --swimlane todo \
  --priority P0 \
  --description "Users can't log in with SSO" \
  --initiative xyz789 \
  --depends task002 task003
```

**Python Example**:
```python
task = store.create_task(
    project_id="abc12345",
    name="Fix login bug",
    swimlane="todo",
    priority="P0",
    description="Users can't log in with SSO",
    initiative_id="xyz789",
    depends_on=["task002", "task003"]
)
print(f"Created task {task['id']}")
```

---

### `update_task(project_id: str, task_id: str, **updates)`

Update an existing task.

**Parameters**:
- `project_id` (str, required): Project ID
- `task_id` (str, required): Task ID
- `**updates`: Keyword arguments for fields to update

**Allowed Update Fields**:
- `name` (str): Task name
- `description` (str): Task description
- `swimlane` (str): Move to different swimlane
- `order` (int): Change position within swimlane
- `priority` (str): Priority level
- `initiative_id` (str): Associate with initiative
- `assigned_to` (str): Assignee
- `depends_on` (List[str]): Task dependencies
- `metadata` (Dict): Custom metadata

**Returns**: `Optional[Dict]`
- Updated task
- `None` if task doesn't exist

**Side Effects**:
- Updates `updated_at` timestamp
- Updates task index if swimlane or initiative changed
- Logs `task_updated` activity event

**CLI Example**:
```bash
# Move to different swimlane
python kanban.py update-task abc12345 task001 --swimlane in_progress

# Update priority and name
python kanban.py update-task abc12345 task001 \
  --priority P0 \
  --name "URGENT: Fix login bug"

# Add dependency
python kanban.py update-task abc12345 task001 --add-depends task002

# Remove dependency
python kanban.py update-task abc12345 task001 --remove-depends task003
```

**Python Example**:
```python
# Move task to in-progress
task = store.update_task(
    "abc12345", "task001",
    swimlane="in_progress",
    priority="P0"
)

# Update dependencies
task = store.update_task(
    "abc12345", "task001",
    depends_on=["task002", "task004"]
)
```

---

### `delete_task(project_id: str, task_id: str)`

Permanently delete a task.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID

**Returns**: `bool`
- `True` if deleted successfully
- `False` if task doesn't exist

**Side Effects**:
- Removes task from index
- Logs `task_deleted` activity event

**Warning**: This does **not** update tasks that depend on the deleted task.

**CLI Example**:
```bash
python kanban.py delete-task abc12345 task001
```

**Python Example**:
```python
if store.delete_task("abc12345", "task001"):
    print("Task deleted")
```

---

## Initiative Management

### `list_initiatives(project_id: str)`

List all initiatives in a project.

**Parameters**:
- `project_id` (str): Project ID

**Returns**: `List[Dict]`
- Sorted by `created_at` (oldest first)
- Each initiative includes:
  - `id` (str): Initiative ID
  - `name` (str): Initiative name
  - `goal` (str|None): Initiative goal
  - `status` (str): Status (planning, active, completed, archived)
  - `start_date` (str|None): Start date (YYYY-MM-DD)
  - `end_date` (str|None): End date (YYYY-MM-DD)
  - `created_at` (str): ISO 8601 timestamp
  - `created_by` (str): Creator identifier
  - `updated_at` (str|None): Last update timestamp

**CLI Example**:
```bash
python kanban.py list-initiatives abc12345
```

**Python Example**:
```python
initiatives = store.list_initiatives("abc12345")
for init in initiatives:
    print(f"{init['name']}: {init['status']}")
```

---

### `get_initiative(project_id: str, initiative_id: str)`

Retrieve a single initiative.

**Parameters**:
- `project_id` (str): Project ID
- `initiative_id` (str): Initiative ID

**Returns**: `Optional[Dict]`
- Initiative data (same structure as `list_initiatives`)
- `None` if initiative doesn't exist

**CLI Example**:
```bash
python kanban.py get-initiative abc12345 xyz789
```

**Python Example**:
```python
initiative = store.get_initiative("abc12345", "xyz789")
if initiative:
    print(f"Initiative: {initiative['name']}")
```

---

### `create_initiative(project_id: str, name: str, **kwargs)`

Create a new initiative.

**Parameters**:
- `project_id` (str, required): Project ID
- `name` (str, required): Initiative name

**Optional Keyword Arguments**:
- `goal` (str): Initiative goal/objective
- `status` (str): Status (default: "active")
- `start_date` (str): Start date in YYYY-MM-DD format
- `end_date` (str): End date in YYYY-MM-DD format
- `created_by` (str): Creator identifier (default: "claude")

**Returns**: `Optional[Dict]`
- Newly created initiative
- `None` if project doesn't exist

**Side Effects**:
- Auto-generates 8-character initiative ID
- Logs `initiative_created` activity event

**CLI Example**:
```bash
python kanban.py create-initiative abc12345 "Q1 Performance Sprint" \
  --goal "Reduce API latency by 50%" \
  --status planning \
  --start 2026-01-01 \
  --end 2026-03-31
```

**Python Example**:
```python
initiative = store.create_initiative(
    project_id="abc12345",
    name="Q1 Performance Sprint",
    goal="Reduce API latency by 50%",
    status="planning",
    start_date="2026-01-01",
    end_date="2026-03-31"
)
print(f"Created initiative {initiative['id']}")
```

---

### `update_initiative(project_id: str, initiative_id: str, **updates)`

Update an initiative.

**Parameters**:
- `project_id` (str, required): Project ID
- `initiative_id` (str, required): Initiative ID
- `**updates`: Keyword arguments for fields to update

**Allowed Update Fields**:
- `name` (str): Initiative name
- `goal` (str): Goal/objective
- `status` (str): Status (planning, active, completed, archived)
- `start_date` (str): Start date (YYYY-MM-DD)
- `end_date` (str): End date (YYYY-MM-DD)

**Returns**: `Optional[Dict]`
- Updated initiative
- `None` if initiative doesn't exist

**Side Effects**:
- Sets `updated_at` timestamp

**CLI Example**:
```bash
python kanban.py update-initiative abc12345 xyz789 \
  --status active \
  --start 2026-02-01
```

**Python Example**:
```python
initiative = store.update_initiative(
    "abc12345", "xyz789",
    status="active",
    start_date="2026-02-01"
)
```

---

### `delete_initiative(project_id: str, initiative_id: str)`

Delete an initiative and unlink associated tasks.

**Parameters**:
- `project_id` (str): Project ID
- `initiative_id` (str): Initiative ID

**Returns**: `bool`
- `True` if deleted successfully
- `False` if initiative doesn't exist

**Side Effects**:
- Sets `initiative_id = None` on all associated tasks
- Updates task index to remove initiative mapping

**CLI Example**:
```bash
python kanban.py delete-initiative abc12345 xyz789
```

**Python Example**:
```python
if store.delete_initiative("abc12345", "xyz789"):
    print("Initiative deleted and tasks unlinked")
```

---

## Activity & Comments

### `add_comment(project_id: str, task_id: str, content: str, commenter: str = "claude")`

Add a comment to a task.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID
- `content` (str): Comment text
- `commenter` (str, optional): Commenter identifier (default: "claude")

**Returns**: `Optional[Dict]`
- Comment object with:
  - `id` (str): Comment ID
  - `commenter` (str): Commenter identifier
  - `timestamp` (str): ISO 8601 timestamp
  - `content` (str): Comment text
- `None` if task doesn't exist

**Side Effects**:
- Logs `comment` activity event in daily JSONL log
- Comment is stored in activity log only (not duplicated in task file)

**CLI Example**:
```bash
python kanban.py add-comment abc12345 task001 "Waiting on design approval"
```

**Python Example**:
```python
comment = store.add_comment(
    "abc12345", "task001",
    content="Waiting on design approval",
    commenter="alice"
)
print(f"Added comment {comment['id']}")
```

---

### `add_commit(project_id: str, task_id: str, commit_hash: str, message: str = None)`

Link a git commit to a task.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID
- `commit_hash` (str): Git commit hash
- `message` (str, optional): Commit message for logging

**Returns**: `bool`
- `True` if linked successfully
- `False` if task doesn't exist

**Side Effects**:
- Appends to task's `commits` array (no duplicates)
- Updates task's `updated_at` timestamp
- Logs `commit_linked` activity event

**CLI Example**:
```bash
python kanban.py add-commit abc12345 task001 a1b2c3d4 \
  --message "Fix authentication flow"
```

**Python Example**:
```python
store.add_commit(
    "abc12345", "task001",
    commit_hash="a1b2c3d4e5f6",
    message="Fix authentication flow"
)
```

---

### `add_artifact(project_id: str, task_id: str, name: str, artifact_type: str = "file", path: str = None, url: str = None)`

Attach an artifact to a task.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID
- `name` (str): Artifact name/description
- `artifact_type` (str, optional): Type (file, url, image, document) - default: "file"
- `path` (str, optional): File system path
- `url` (str, optional): URL

**Returns**: `Optional[Dict]`
- Artifact object with:
  - `id` (str): Artifact ID
  - `name` (str): Artifact name
  - `type` (str): Artifact type
  - `path` (str|None): File path
  - `url` (str|None): URL
  - `created_at` (str): ISO 8601 timestamp
- `None` if task doesn't exist

**Side Effects**:
- Appends to task's `artifacts` array
- Updates task's `updated_at` timestamp
- Logs `artifact_added` activity event

**CLI Example**:
```bash
# File artifact
python kanban.py add-artifact abc12345 task001 "Design mockup" \
  --type image \
  --path /path/to/mockup.png

# URL artifact
python kanban.py add-artifact abc12345 task001 "Spec document" \
  --type document \
  --url https://docs.example.com/spec
```

**Python Example**:
```python
# Add file artifact
artifact = store.add_artifact(
    "abc12345", "task001",
    name="Design mockup",
    artifact_type="image",
    path="/path/to/mockup.png"
)

# Add URL artifact
artifact = store.add_artifact(
    "abc12345", "task001",
    name="Spec document",
    artifact_type="document",
    url="https://docs.example.com/spec"
)
```

---

### `get_activity(project_id: str, date_str: str = None, limit: int = 100)`

Retrieve activity log entries.

**Parameters**:
- `project_id` (str): Project ID
- `date_str` (str, optional): Filter by date (YYYY-MM-DD format)
- `limit` (int, optional): Maximum entries to return (default: 100)

**Returns**: `List[Dict]`
- Activity entries (newest first if no date specified)
- Each entry includes:
  - `ts` (str): ISO 8601 timestamp
  - `type` (str): Activity type (task_created, task_updated, comment, etc.)
  - Additional fields vary by type

**Activity Types**:
- `project_created`: `project_name`
- `project_updated`: `updates` (list of changed fields)
- `task_created`: `task_id`, `task_name`
- `task_updated`: `task_id`, `updates`
- `task_deleted`: `task_id`
- `comment`: `task_id`, `comment_id`, `content`, `by`
- `commit_linked`: `task_id`, `commit`, `message`
- `artifact_added`: `task_id`, `artifact_name`, `artifact_type`
- `initiative_created`: `initiative_id`, `initiative_name`

**CLI Example**:
```bash
# Recent activity (last 50 entries)
python kanban.py activity abc12345 --limit 50

# Specific date
python kanban.py activity abc12345 --date 2026-01-26
```

**Python Example**:
```python
# Recent activity
activity = store.get_activity("abc12345", limit=50)
for entry in activity:
    print(f"{entry['ts']}: {entry['type']}")

# Activity for specific date
activity = store.get_activity("abc12345", date_str="2026-01-26")
```

---

## Search

### `search(query: str, project_id: str = None, include_comments: bool = True)`

Search tasks by name, description, and optionally comments.

**Parameters**:
- `query` (str): Search query (case-insensitive)
- `project_id` (str, optional): Limit search to specific project
- `include_comments` (bool, optional): Search comment content (default: True)

**Returns**: `List[Dict]`
- Search results with:
  - `task_id` (str): Task ID
  - `task_name` (str): Task name
  - `project_id` (str): Project ID
  - `project_name` (str): Project name
  - `swimlane` (str): Current swimlane
  - `priority` (str): Priority level
  - `match_type` (str): "task" or "comment"

**Search Scope**:
- Task names (partial match)
- Task descriptions (partial match)
- Comment content (if `include_comments=True`)

**CLI Example**:
```bash
# Search all projects
python kanban.py search "authentication"

# Search specific project
python kanban.py search "authentication" --project abc12345
```

**Python Example**:
```python
# Search all projects
results = store.search("authentication")
for result in results:
    print(f"{result['task_name']} ({result['project_name']})")

# Search specific project, tasks only
results = store.search("auth", project_id="abc12345", include_comments=False)
```

---

## Dependencies

### `get_task_blocking_status(project_id: str, task_id: str)`

Check if a task is blocked by incomplete dependencies.

**Parameters**:
- `project_id` (str): Project ID
- `task_id` (str): Task ID

**Returns**: `Dict`
- Blocking status with:
  - `is_blocked` (bool): Whether task has incomplete dependencies
  - `blocking_tasks` (List[Dict]): List of incomplete dependency tasks

**Blocking Task Details**:
- `task_id` (str): Dependency task ID
- `task_name` (str): Dependency task name
- `swimlane` (str): Current swimlane
- `priority` (str): Priority level

**Logic**:
- A task is blocked if any task in its `depends_on` array is in a non-complete swimlane
- Swimlanes are considered "complete" if `is_complete=True` in swimlane definition
- Default "Done" swimlane is marked as complete

**Python Example**:
```python
status = store.get_task_blocking_status("abc12345", "task001")
if status['is_blocked']:
    print(f"Task blocked by {len(status['blocking_tasks'])} tasks:")
    for blocker in status['blocking_tasks']:
        print(f"  - {blocker['task_name']} ({blocker['swimlane']})")
else:
    print("Task ready to work on")
```

---

## Configuration

### `get_config()`

Get global configuration.

**Returns**: `Dict`
- Configuration object (empty dict if no config exists)
- May contain:
  - `repo_projects` (Dict[str, str]): Repository path → project ID mapping

**Python Example**:
```python
config = store.get_config()
print(f"Mapped repos: {config.get('repo_projects', {})}")
```

---

### `save_config(config: Dict)`

Save global configuration.

**Parameters**:
- `config` (Dict): Configuration object to save

**Python Example**:
```python
config = store.get_config()
config['custom_setting'] = 'value'
store.save_config(config)
```

---

### `get_project_for_repo(repo_path: str)`

Get project ID associated with a repository path.

**Parameters**:
- `repo_path` (str): Repository path

**Returns**: `Optional[str]`
- Project ID if mapping exists
- `None` if no mapping

**Python Example**:
```python
project_id = store.get_project_for_repo("/Users/dev/my-project")
if project_id:
    print(f"Repo mapped to project {project_id}")
```

---

### `set_project_for_repo(repo_path: str, project_id: str)`

Map a repository path to a project.

**Parameters**:
- `repo_path` (str): Repository path
- `project_id` (str): Project ID

**Side Effects**:
- Updates global config
- Creates/updates `repo_projects` mapping

**Python Example**:
```python
store.set_project_for_repo("/Users/dev/my-project", "abc12345")
```

---

## Session Context

### `get_active_context()`

Get current session context.

**Returns**: `Dict`
- Active context (empty dict if none)
- May contain:
  - `project_id` (str): Active project ID
  - `active_task_id` (str): Active task ID
  - `updated_at` (str): Last update timestamp

**Python Example**:
```python
ctx = store.get_active_context()
if ctx.get('project_id'):
    print(f"Active project: {ctx['project_id']}")
```

---

### `set_active_context(**updates)`

Update active session context.

**Parameters**:
- `**updates`: Keyword arguments for context fields

**Common Fields**:
- `project_id` (str): Set active project
- `active_task_id` (str): Set active task
- `session_name` (str): Session identifier

**Side Effects**:
- Updates `updated_at` timestamp automatically

**Python Example**:
```python
store.set_active_context(
    project_id="abc12345",
    active_task_id="task001",
    session_name="Authentication Sprint"
)
```

---

### `get_active_task()`

Get the currently active task with full details.

**Returns**: `Optional[Dict]`
- Task data if active task is set
- `None` if no active task or task doesn't exist

**Python Example**:
```python
task = store.get_active_task()
if task:
    print(f"Working on: {task['name']}")
else:
    print("No active task")
```

---

## Swimlane Management

### `get_swimlanes(project_id: str)`

Get all swimlanes for a project.

**Parameters**:
- `project_id` (str): Project ID

**Returns**: `List[Dict]`
- Swimlane definitions:
  - `id` (str): Swimlane ID
  - `name` (str): Display name
  - `order` (int): Display order
  - `is_complete` (bool): Whether tasks in this swimlane are considered complete
  - `color` (str|None): Display color

**Default Swimlanes**:
```python
[
    {"id": "todo", "name": "To Do", "order": 0, "is_complete": False},
    {"id": "in_progress", "name": "In Progress", "order": 1, "is_complete": False},
    {"id": "done", "name": "Done", "order": 2, "is_complete": True}
]
```

**Python Example**:
```python
swimlanes = store.get_swimlanes("abc12345")
for lane in swimlanes:
    print(f"{lane['name']}: {'complete' if lane['is_complete'] else 'active'}")
```

---

### `create_swimlane(project_id: str, name: str, **kwargs)`

Create a new swimlane.

**Parameters**:
- `project_id` (str): Project ID
- `name` (str): Swimlane name

**Optional Keyword Arguments**:
- `id` (str): Custom swimlane ID (auto-generated if not provided)
- `order` (int): Display order (appends to end if not provided)
- `is_complete` (bool): Completion status (default: False)
- `color` (str): Display color

**Returns**: `Optional[Dict]`
- Newly created swimlane
- `None` if project doesn't exist

**Python Example**:
```python
swimlane = store.create_swimlane(
    "abc12345",
    name="Review",
    order=2,
    is_complete=False,
    color="#FFA500"
)
```

---

### `update_swimlane(project_id: str, swimlane_id: str, **updates)`

Update a swimlane.

**Parameters**:
- `project_id` (str): Project ID
- `swimlane_id` (str): Swimlane ID
- `**updates`: Fields to update

**Allowed Update Fields**:
- `name` (str): Display name
- `order` (int): Display order
- `is_complete` (bool): Completion status
- `color` (str): Display color

**Returns**: `Optional[Dict]`
- Updated swimlane
- `None` if swimlane doesn't exist

**Side Effects**:
- Re-sorts swimlanes by order

**Python Example**:
```python
swimlane = store.update_swimlane(
    "abc12345", "review",
    name="Code Review",
    order=1
)
```

---

## Error Handling

All methods follow these error patterns:

**Not Found**: Returns `None`
```python
project = store.get_project("invalid")  # Returns None
task = store.get_task("abc", "invalid")  # Returns None
```

**Invalid Operations**: Returns `None` or `False`
```python
result = store.create_task("invalid_project", "Task")  # Returns None
success = store.delete_task("abc", "invalid")  # Returns False
```

**Exceptions**: File I/O errors may raise standard Python exceptions
- `OSError`: Permission issues, disk full, etc.
- `JSONDecodeError`: Corrupted data files

---

## Data Types

### Priority Levels
- `P0`: Critical/Urgent
- `P1`: High priority
- `P2`: Normal priority (default)
- `P3`: Low priority

### Initiative Status
- `planning`: Not yet started
- `active`: Currently in progress
- `completed`: Finished
- `archived`: Archived/inactive

### Common Timestamps
All timestamps use ISO 8601 format with UTC timezone:
```python
"2026-01-26T15:30:00Z"
```

Generated by `get_utc_timestamp()` helper.

---

## Concurrency

**File Locking**: Activity log writes use `fcntl.flock()` for safe concurrent appends.

**Index Updates**: Not atomic. Concurrent updates may cause race conditions. Designed for single-user CLI usage.

**Thread Safety**: Not thread-safe. Use external synchronization if needed.

---

## Performance Considerations

**Task Listing**: O(n) where n = number of tasks (reads each task file)

**Search**: O(n*m) where n = projects, m = tasks per project

**Activity Logs**: Stored as daily JSONL files for efficient sequential writes

**Index Optimization**: Task index provides O(1) lookups by swimlane/initiative without scanning all task files

---

## Module Interface

### `get_store()`

Get or create the singleton KanbanStore instance.

**Returns**: `KanbanStore`
- Singleton instance (created on first call)

**Python Example**:
```python
from kanban import get_store

store = get_store()
projects = store.list_projects()
```

---

## CLI Usage

The module provides a complete CLI interface when run directly:

```bash
python kanban.py <command> [arguments]
```

All CLI commands output JSON to stdout. Errors are printed to stderr and exit with code 1.

See command-specific sections above for CLI examples.

**General Pattern**:
```bash
python kanban.py <command> <required-args> [--optional-flags]
```

**Output Format**: JSON (pretty-printed with 2-space indent)

---

## Storage Layout

### Project Directory Structure
```
~/.something-wicked/wicked-kanban/projects/{project-id}/
├── project.json           # Project metadata
├── swimlanes.json         # Swimlane definitions
├── tasks/
│   ├── index.json         # Fast lookups
│   ├── {task-id}.json     # Task 1
│   └── {task-id}.json     # Task 2
├── initiatives/
│   └── {id}.json          # Initiative definitions
└── activity/
    ├── 2026-01-26.jsonl   # Today's activity
    └── 2026-01-25.jsonl   # Yesterday's activity
```

### Index Structure
```json
{
  "by_swimlane": {
    "todo": ["task001", "task002"],
    "in_progress": ["task003"]
  },
  "by_initiative": {
    "xyz789": ["task001", "task003"]
  },
  "all": ["task001", "task002", "task003"]
}
```

---

## Environment Variables

- `WICKED_KANBAN_DATA_DIR`: Override default data directory (default: `~/.something-wicked/wicked-kanban`)

**Example**:
```bash
export WICKED_KANBAN_DATA_DIR=/custom/path
python kanban.py list-projects
```
