#!/usr/bin/env python3
"""Wicked Kanban Data API — dual-mode: CLI verbs + HTTP server.

CLI mode (standard Plugin Data API):
    python3 api.py list tasks --limit 10 --project abc123
    python3 api.py get tasks <task-id> --project abc123
    python3 api.py search tasks --query "bug" --project abc123
    python3 api.py stats tasks --project abc123
    python3 api.py create tasks < payload.json
    python3 api.py update tasks <task-id> < payload.json
    python3 api.py delete tasks <task-id> --project abc123
    python3 api.py list projects
    python3 api.py list initiatives --project abc123
    python3 api.py list activity --project abc123 --limit 20

HTTP mode (legacy, backward-compatible):
    python3 api.py serve [--port 18888]
    python3 api.py [--port 18888]  # no verb = HTTP server
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from kanban import get_store


# ==================== Shared Helpers ====================

VALID_VERBS = {"list", "get", "search", "stats", "create", "update", "delete"}
VALID_SOURCES = {"projects", "tasks", "initiatives", "activity", "comments"}


def _meta(source, total, limit=100, offset=0):
    """Build standard meta block."""
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _error(message, code, **details):
    """Print error to stderr and exit."""
    err = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


def _paginate(items, limit, offset):
    """Apply pagination to a list."""
    return items[offset:offset + limit]


def _read_input():
    """Read JSON input from stdin for write operations."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _error("Invalid JSON input", "INVALID_INPUT")


def _validate_required(data, *fields):
    """Validate required fields are present in input data."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        _error("Validation failed", "VALIDATION_ERROR",
               fields={f: "required field missing" for f in missing})


# ==================== Read Handlers ====================


def cli_list(source, args):
    """Handle list verb."""
    store = get_store()

    if source == "comments":
        if not args.task_id:
            _error("--task-id required for comments", "MISSING_TASK_ID")
        if not args.project:
            _error("--project required for comments", "MISSING_PROJECT")

        task = store.get_task(args.project, args.task_id)
        if not task:
            _error("Task not found", "NOT_FOUND", resource="tasks", id=args.task_id)

        comments = task.get("comments", [])
        data = _paginate(comments, args.limit, args.offset)
        print(json.dumps({"data": data, "meta": _meta(source, len(comments), args.limit, args.offset)}, indent=2))

    elif source == "projects":
        projects = store.list_projects()
        data = _paginate(projects, args.limit, args.offset)
        print(json.dumps({"data": data, "meta": _meta(source, len(projects), args.limit, args.offset)}, indent=2))

    elif source == "tasks":
        swimlane = getattr(args, 'filter', None)
        if not args.project:
            # List tasks across all projects
            projects = store.list_projects()
            all_tasks = []
            for p in projects:
                pid = p.get("id") or p.get("name", "")
                tasks = store.list_tasks(pid, swimlane=swimlane)
                all_tasks.extend(tasks)
            tasks = all_tasks
        else:
            tasks = store.list_tasks(args.project, swimlane=swimlane)

        data = _paginate(tasks, args.limit, args.offset)
        print(json.dumps({"data": data, "meta": _meta(source, len(tasks), args.limit, args.offset)}, indent=2))

    elif source == "initiatives":
        if not args.project:
            _error("--project required for initiatives", "MISSING_PROJECT")
        initiatives = store.list_initiatives(args.project)
        data = _paginate(initiatives, args.limit, args.offset)
        print(json.dumps({"data": data, "meta": _meta(source, len(initiatives), args.limit, args.offset)}, indent=2))

    elif source == "activity":
        if not args.project:
            _error("--project required for activity", "MISSING_PROJECT")
        activity = store.get_activity(args.project, limit=args.limit)
        data = _paginate(activity, args.limit, args.offset)
        print(json.dumps({"data": data, "meta": _meta(source, len(activity), args.limit, args.offset)}, indent=2))


def cli_get(source, item_id, args):
    """Handle get verb."""
    store = get_store()

    if source == "projects":
        project = store.get_project(item_id)
        if not project:
            _error("Project not found", "NOT_FOUND", resource="projects", id=item_id)
        print(json.dumps({"data": project, "meta": _meta(source, 1)}, indent=2))

    elif source == "tasks":
        if not args.project:
            _error("--project required for task get", "MISSING_PROJECT")
        task = store.get_task(args.project, item_id)
        if not task:
            _error("Task not found", "NOT_FOUND", resource="tasks", id=item_id)
        print(json.dumps({"data": task, "meta": _meta(source, 1)}, indent=2))

    elif source == "initiatives":
        if not args.project:
            _error("--project required for initiative get", "MISSING_PROJECT")
        initiative = store.get_initiative(args.project, item_id)
        if not initiative:
            _error("Initiative not found", "NOT_FOUND", resource="initiatives", id=item_id)
        print(json.dumps({"data": initiative, "meta": _meta(source, 1)}, indent=2))

    else:
        _error(f"get not supported for source: {source}", "INVALID_VERB", source=source)


def cli_search(source, args):
    """Handle search verb."""
    store = get_store()

    if source != "tasks":
        _error(f"search not supported for source: {source}", "INVALID_VERB", source=source)

    if not args.query:
        _error("--query required for search", "MISSING_QUERY")

    results = store.search(args.query, project_id=args.project)
    data = _paginate(results, args.limit, args.offset)
    print(json.dumps({"data": data, "meta": _meta(source, len(results), args.limit, args.offset)}, indent=2))


def cli_stats(source, args):
    """Handle stats verb."""
    store = get_store()

    if source != "tasks":
        _error(f"stats not supported for source: {source}", "INVALID_VERB", source=source)

    if not args.project:
        # Stats across all projects
        projects = store.list_projects()
        all_tasks = []
        for p in projects:
            pid = p.get("id") or p.get("name", "")
            all_tasks.extend(store.list_tasks(pid))
    else:
        all_tasks = store.list_tasks(args.project)

    stats = {
        "total": len(all_tasks),
        "by_swimlane": {},
        "by_priority": {},
        "blocked": 0,
    }
    for task in all_tasks:
        swimlane = task.get("swimlane", "unknown")
        priority = task.get("priority", "P2")
        stats["by_swimlane"][swimlane] = stats["by_swimlane"].get(swimlane, 0) + 1
        stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
        if task.get("is_blocked"):
            stats["blocked"] += 1

    print(json.dumps({"data": stats, "meta": _meta(source, 1)}, indent=2))


# ==================== Write Handlers ====================


def cli_create(source, args):
    """Handle create verb — reads JSON from stdin."""
    store = get_store()
    data = _read_input()

    if source == "comments":
        task_id = data.get("task_id") or getattr(args, "task_id", None)
        project_id = data.get("project_id") or getattr(args, "project", None)

        if not task_id:
            _error("task_id required for comment creation", "MISSING_TASK_ID")
        if not project_id:
            _error("project_id required for comment creation", "MISSING_PROJECT")
        # Accept both "text" and "body" for the comment content (normalize to "text")
        comment_text = data.get("text") or data.get("body")
        if not comment_text:
            _error("'text' field required for comment creation", "MISSING_FIELD", field="text")

        task = store.get_task(project_id, task_id)
        if not task:
            _error("Task not found", "NOT_FOUND", resource="tasks", id=task_id)

        # Create comment object (matches existing stored format: text, author, created_at)
        comment = {
            "id": str(uuid.uuid4())[:8],
            "text": comment_text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "author": data.get("author", "system")
        }

        # Add to task's comments array via store methods (transaction-safe)
        if not isinstance(task.get("comments"), list):
            task["comments"] = []
        task["comments"].append(comment)
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        store._write_json(store._task_file(project_id, task_id), task)

        # Log activity
        store._log_activity(project_id, "comment_added", task_id=task_id, comment_id=comment["id"], text=comment_text)

        print(json.dumps({"data": comment, "meta": _meta(source, 1)}, indent=2))

    elif source == "projects":
        _validate_required(data, "name")
        result = store.create_project(
            name=data["name"],
            description=data.get("description", ""),
            repo_path=data.get("repo_path", ""),
        )
        if not result:
            _error("Failed to create project", "CREATE_FAILED", resource="projects")
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "tasks":
        project_id = data.get("project_id") or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for task creation", "MISSING_PROJECT")
        _validate_required(data, "name")
        result = store.create_task(
            project_id=project_id,
            name=data["name"],
            swimlane=data.get("swimlane", "todo"),
            priority=data.get("priority"),
            description=data.get("description"),
            initiative_id=data.get("initiative_id"),
            depends_on=data.get("depends_on"),
            metadata=data.get("metadata"),
        )
        if not result:
            _error("Failed to create task", "CREATE_FAILED", resource="tasks")
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "initiatives":
        project_id = data.get("project_id") or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for initiative creation", "MISSING_PROJECT")
        _validate_required(data, "name")
        result = store.create_initiative(
            project_id=project_id,
            name=data["name"],
            goal=data.get("goal"),
            status=data.get("status", "planning"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )
        if not result:
            _error("Failed to create initiative", "CREATE_FAILED", resource="initiatives")
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "activity":
        _error("create not supported for activity (auto-generated)", "UNSUPPORTED_VERB", source=source)


def cli_update(source, item_id, args):
    """Handle update verb — reads JSON from stdin."""
    store = get_store()
    data = _read_input()

    if source == "projects":
        result = store.update_project(item_id, **{
            k: v for k, v in data.items()
            if k in ("name", "description", "repo_path", "archived")
        })
        if not result:
            _error("Project not found", "NOT_FOUND", resource="projects", id=item_id)
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "tasks":
        project_id = data.pop("project_id", None) or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for task update", "MISSING_PROJECT")
        allowed = {"name", "description", "swimlane", "order", "priority",
                    "initiative_id", "assigned_to", "depends_on", "metadata"}
        updates = {k: v for k, v in data.items() if k in allowed}
        result = store.update_task(project_id, item_id, **updates)
        if not result:
            _error("Task not found", "NOT_FOUND", resource="tasks", id=item_id)
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "initiatives":
        project_id = data.pop("project_id", None) or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for initiative update", "MISSING_PROJECT")
        allowed = {"name", "goal", "status", "start_date", "end_date"}
        updates = {k: v for k, v in data.items() if k in allowed}
        result = store.update_initiative(project_id, item_id, **updates)
        if not result:
            _error("Initiative not found", "NOT_FOUND", resource="initiatives", id=item_id)
        print(json.dumps({"data": result, "meta": _meta(source, 1)}, indent=2))

    elif source == "activity":
        _error("update not supported for activity", "UNSUPPORTED_VERB", source=source)


def cli_delete(source, item_id, args):
    """Handle delete verb."""
    store = get_store()

    if source == "projects":
        result = store.delete_project(item_id)
        if not result:
            _error("Project not found", "NOT_FOUND", resource="projects", id=item_id)
        print(json.dumps({"data": {"deleted": True, "id": item_id}, "meta": _meta(source, 1)}, indent=2))

    elif source == "tasks":
        # Read project_id from stdin or args
        data = _read_input() if not sys.stdin.isatty() else {}
        project_id = data.get("project_id") or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for task deletion", "MISSING_PROJECT")
        result = store.delete_task(project_id, item_id)
        if not result:
            _error("Task not found", "NOT_FOUND", resource="tasks", id=item_id)
        print(json.dumps({"data": {"deleted": True, "id": item_id}, "meta": _meta(source, 1)}, indent=2))

    elif source == "initiatives":
        data = _read_input() if not sys.stdin.isatty() else {}
        project_id = data.get("project_id") or getattr(args, "project", None)
        if not project_id:
            _error("project_id required for initiative deletion", "MISSING_PROJECT")
        result = store.delete_initiative(project_id, item_id)
        if not result:
            _error("Initiative not found", "NOT_FOUND", resource="initiatives", id=item_id)
        print(json.dumps({"data": {"deleted": True, "id": item_id}, "meta": _meta(source, 1)}, indent=2))

    elif source == "activity":
        _error("delete not supported for activity", "UNSUPPORTED_VERB", source=source)


# ==================== CLI Router ====================


def run_cli(args):
    """Execute CLI mode."""
    verb = args.verb
    source = args.source

    if source not in VALID_SOURCES:
        _error(f"Unknown source: {source}", "INVALID_SOURCE",
               source=source, valid=list(VALID_SOURCES))

    if verb == "list":
        cli_list(source, args)
    elif verb == "get":
        if not args.id:
            _error("ID required for get verb", "MISSING_ID")
        cli_get(source, args.id, args)
    elif verb == "search":
        cli_search(source, args)
    elif verb == "stats":
        cli_stats(source, args)
    elif verb == "create":
        cli_create(source, args)
    elif verb == "update":
        if not args.id:
            _error("ID required for update verb", "MISSING_ID")
        cli_update(source, args.id, args)
    elif verb == "delete":
        if not args.id:
            _error("ID required for delete verb", "MISSING_ID")
        cli_delete(source, args.id, args)


# ==================== HTTP Mode (legacy, unchanged) ====================

class KanbanAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for kanban data API."""

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        response = json.dumps(data, indent=2)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(response.encode())

    def _send_error(self, message: str, status: int = 400):
        """Send error response."""
        self._send_json({'error': message}, status)

    def _get_body(self) -> dict:
        """Parse JSON body from request."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        store = get_store()

        if path == '/health':
            self._send_json({'status': 'ok', 'service': 'wicked-kanban'})
            return
        if path == '/api/projects':
            self._send_json({'projects': store.list_projects()})
            return
        if path.startswith('/api/projects/') and path.count('/') == 3:
            project_id = path.split('/')[-1]
            project = store.get_project(project_id)
            if project:
                self._send_json(project)
            else:
                self._send_error('Project not found', 404)
            return
        if path.startswith('/api/projects/') and path.endswith('/tasks'):
            parts = path.split('/')
            project_id = parts[3]
            swimlane = query.get('swimlane', [None])[0]
            initiative_id = query.get('initiative', [None])[0]
            tasks = store.list_tasks(project_id, swimlane=swimlane, initiative_id=initiative_id)
            self._send_json({'tasks': tasks})
            return
        if path.startswith('/api/projects/') and '/tasks/' in path:
            parts = path.split('/')
            project_id = parts[3]
            task_id = parts[5]
            task = store.get_task(project_id, task_id)
            if task:
                self._send_json(task)
            else:
                self._send_error('Task not found', 404)
            return
        if path.startswith('/api/projects/') and path.endswith('/initiatives'):
            parts = path.split('/')
            project_id = parts[3]
            self._send_json({'initiatives': store.list_initiatives(project_id)})
            return
        if path.startswith('/api/projects/') and '/initiatives/' in path:
            parts = path.split('/')
            project_id = parts[3]
            initiative_id = parts[5]
            initiative = store.get_initiative(project_id, initiative_id)
            if initiative:
                self._send_json(initiative)
            else:
                self._send_error('Initiative not found', 404)
            return
        if path.startswith('/api/projects/') and path.endswith('/swimlanes'):
            parts = path.split('/')
            project_id = parts[3]
            self._send_json({'swimlanes': store.get_swimlanes(project_id)})
            return
        if path.startswith('/api/projects/') and path.endswith('/activity'):
            parts = path.split('/')
            project_id = parts[3]
            date = query.get('date', [None])[0]
            limit = int(query.get('limit', [50])[0])
            self._send_json({'activity': store.get_activity(project_id, date=date, limit=limit)})
            return
        if path.startswith('/api/projects/') and path.endswith('/stats'):
            parts = path.split('/')
            project_id = parts[3]
            tasks = store.list_tasks(project_id)
            stats = {
                'total': len(tasks),
                'by_swimlane': {},
                'by_priority': {},
                'blocked': 0,
            }
            for task in tasks:
                sl = task.get('swimlane', 'unknown')
                pr = task.get('priority', 'P2')
                stats['by_swimlane'][sl] = stats['by_swimlane'].get(sl, 0) + 1
                stats['by_priority'][pr] = stats['by_priority'].get(pr, 0) + 1
                if task.get('is_blocked'):
                    stats['blocked'] += 1
            self._send_json(stats)
            return
        if path == '/api/search':
            query_str = query.get('q', [''])[0]
            project_id = query.get('project', [None])[0]
            results = store.search_tasks(query_str, project_id=project_id)
            self._send_json({'results': results})
            return
        if path == '/api/context':
            self._send_json(store.get_active_context())
            return

        self._send_error('Not found', 404)

    def do_POST(self):
        """Handle POST requests (for MCP-style tool calls)."""
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._get_body()
        store = get_store()

        if path == '/api/mcp/call':
            tool = body.get('tool')
            params = body.get('params', {})

            if tool == 'list_projects':
                self._send_json({'result': store.list_projects()})
                return
            if tool == 'get_project':
                self._send_json({'result': store.get_project(params.get('project_id'))})
                return
            if tool == 'list_tasks':
                tasks = store.list_tasks(params.get('project_id'),
                                         swimlane=params.get('swimlane'),
                                         initiative_id=params.get('initiative_id'))
                self._send_json({'result': tasks})
                return
            if tool == 'get_task':
                self._send_json({'result': store.get_task(params.get('project_id'), params.get('task_id'))})
                return
            if tool == 'list_initiatives':
                self._send_json({'result': store.list_initiatives(params.get('project_id'))})
                return
            if tool == 'get_initiative':
                self._send_json({'result': store.get_initiative(params.get('project_id'), params.get('initiative_id'))})
                return
            if tool == 'list_swimlanes':
                self._send_json({'result': store.get_swimlanes(params.get('project_id'))})
                return
            if tool == 'get_task_stats':
                tasks = store.list_tasks(params.get('project_id'))
                stats = {'total': len(tasks), 'by_swimlane': {}, 'by_priority': {}, 'blocked': 0}
                for task in tasks:
                    sl = task.get('swimlane', 'unknown')
                    pr = task.get('priority', 'P2')
                    stats['by_swimlane'][sl] = stats['by_swimlane'].get(sl, 0) + 1
                    stats['by_priority'][pr] = stats['by_priority'].get(pr, 0) + 1
                    if task.get('is_blocked'):
                        stats['blocked'] += 1
                self._send_json({'result': stats})
                return
            if tool == 'list_comments':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task.get('comments', []) if task else []})
                return
            if tool == 'list_commits':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task.get('commits', []) if task else []})
                return
            if tool == 'list_artifacts':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task.get('artifacts', []) if task else []})
                return
            if tool == 'get_dependencies':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task.get('depends_on', []) if task else []})
                return
            if tool == 'get_traceability':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task.get('traceability', []) if task else []})
                return

            self._send_error(f'Unknown tool: {tool}', 400)
            return

        self._send_error('Not found', 404)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_http(args):
    """Start HTTP server (legacy mode)."""
    port = int(os.environ.get('WICKED_KANBAN_PORT', args.port))
    host = args.host
    server = HTTPServer((host, port), KanbanAPIHandler)
    print(f"Wicked Kanban API running on http://{host}:{port}")
    print("Endpoints:")
    print("  GET  /health                          - Health check")
    print("  GET  /api/projects                    - List projects")
    print("  GET  /api/projects/{id}               - Get project")
    print("  GET  /api/projects/{id}/tasks         - List tasks")
    print("  GET  /api/projects/{id}/tasks/{tid}   - Get task")
    print("  GET  /api/projects/{id}/initiatives   - List initiatives")
    print("  GET  /api/projects/{id}/swimlanes     - List swimlanes")
    print("  GET  /api/projects/{id}/activity      - Activity log")
    print("  GET  /api/projects/{id}/stats         - Task stats")
    print("  GET  /api/search?q=query              - Search tasks")
    print("  GET  /api/context                     - Active context")
    print("  POST /api/mcp/call                    - MCP tool call")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


# ==================== Main ====================

def main():
    parser = argparse.ArgumentParser(
        description='Wicked Kanban Data API (CLI + HTTP)')

    subparsers = parser.add_subparsers(dest='verb')

    # CLI verbs (read + write)
    for verb in sorted(VALID_VERBS):
        sub = subparsers.add_parser(verb, help=f'{verb} data from kanban')
        sub.add_argument('source', help='Data source (projects, tasks, initiatives, activity, comments)')
        if verb in ('get', 'update', 'delete'):
            sub.add_argument('id', nargs='?', help='Resource ID')
        sub.add_argument('--limit', type=int, default=100, help='Limit results (default: 100)')
        sub.add_argument('--offset', type=int, default=0, help='Skip first N results')
        sub.add_argument('--project', help='Filter by project ID')
        sub.add_argument('--task-id', help='Task ID (for comments)')
        sub.add_argument('--query', help='Search query (for search verb)')
        sub.add_argument('--filter', help='Filter expression')

    # HTTP server mode
    serve = subparsers.add_parser('serve', help='Start HTTP server (legacy)')
    serve.add_argument('--port', '-p', type=int, default=18888, help='Port to listen on')
    serve.add_argument('--host', default='127.0.0.1', help='Host to bind to')

    args = parser.parse_args()

    if args.verb is None:
        # No verb = HTTP server (backward compatible)
        args.port = 18888
        args.host = '127.0.0.1'
        run_http(args)
    elif args.verb == 'serve':
        run_http(args)
    elif args.verb in VALID_VERBS:
        run_cli(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
