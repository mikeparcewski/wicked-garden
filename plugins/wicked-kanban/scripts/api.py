#!/usr/bin/env python3
"""Minimal data API for wicked-workbench integration.

Provides HTTP endpoints for workbench to fetch kanban data.
No frontend, just data endpoints.

Usage:
    uv run python scripts/api.py [--port 18888]
"""
import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))
from kanban import get_store


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

        # Health check
        if path == '/health':
            self._send_json({'status': 'ok', 'service': 'wicked-kanban'})
            return

        # List projects
        if path == '/api/projects':
            projects = store.list_projects()
            self._send_json({'projects': projects})
            return

        # Get project
        if path.startswith('/api/projects/') and path.count('/') == 3:
            project_id = path.split('/')[-1]
            project = store.get_project(project_id)
            if project:
                self._send_json(project)
            else:
                self._send_error('Project not found', 404)
            return

        # List tasks
        if path.startswith('/api/projects/') and path.endswith('/tasks'):
            parts = path.split('/')
            project_id = parts[3]
            swimlane = query.get('swimlane', [None])[0]
            initiative_id = query.get('initiative', [None])[0]
            tasks = store.list_tasks(project_id, swimlane=swimlane, initiative_id=initiative_id)
            self._send_json({'tasks': tasks})
            return

        # Get task
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

        # List initiatives
        if path.startswith('/api/projects/') and path.endswith('/initiatives'):
            parts = path.split('/')
            project_id = parts[3]
            initiatives = store.list_initiatives(project_id)
            self._send_json({'initiatives': initiatives})
            return

        # Get initiative
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

        # List swimlanes
        if path.startswith('/api/projects/') and path.endswith('/swimlanes'):
            parts = path.split('/')
            project_id = parts[3]
            swimlanes = store.get_swimlanes(project_id)
            self._send_json({'swimlanes': swimlanes})
            return

        # Activity log
        if path.startswith('/api/projects/') and path.endswith('/activity'):
            parts = path.split('/')
            project_id = parts[3]
            date = query.get('date', [None])[0]
            limit = int(query.get('limit', [50])[0])
            activity = store.get_activity(project_id, date=date, limit=limit)
            self._send_json({'activity': activity})
            return

        # Task stats
        if path.startswith('/api/projects/') and path.endswith('/stats'):
            parts = path.split('/')
            project_id = parts[3]
            tasks = store.list_tasks(project_id)
            stats = {
                'total': len(tasks),
                'by_swimlane': {},
                'by_priority': {},
                'blocked': 0
            }
            for task in tasks:
                swimlane = task.get('swimlane', 'unknown')
                priority = task.get('priority', 'P2')
                stats['by_swimlane'][swimlane] = stats['by_swimlane'].get(swimlane, 0) + 1
                stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                if task.get('is_blocked'):
                    stats['blocked'] += 1
            self._send_json(stats)
            return

        # Search
        if path == '/api/search':
            query_str = query.get('q', [''])[0]
            project_id = query.get('project', [None])[0]
            results = store.search_tasks(query_str, project_id=project_id)
            self._send_json({'results': results})
            return

        # Active context
        if path == '/api/context':
            ctx = store.get_active_context()
            self._send_json(ctx)
            return

        self._send_error('Not found', 404)

    def do_POST(self):
        """Handle POST requests (for MCP-style tool calls)."""
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._get_body()
        store = get_store()

        # MCP-style tool endpoint
        if path == '/api/mcp/call':
            tool = body.get('tool')
            params = body.get('params', {})

            if tool == 'list_projects':
                projects = store.list_projects()
                self._send_json({'result': projects})
                return

            if tool == 'get_project':
                project = store.get_project(params.get('project_id'))
                self._send_json({'result': project})
                return

            if tool == 'list_tasks':
                tasks = store.list_tasks(
                    params.get('project_id'),
                    swimlane=params.get('swimlane'),
                    initiative_id=params.get('initiative_id')
                )
                self._send_json({'result': tasks})
                return

            if tool == 'get_task':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                self._send_json({'result': task})
                return

            if tool == 'list_initiatives':
                initiatives = store.list_initiatives(params.get('project_id'))
                self._send_json({'result': initiatives})
                return

            if tool == 'get_initiative':
                initiative = store.get_initiative(params.get('project_id'), params.get('initiative_id'))
                self._send_json({'result': initiative})
                return

            if tool == 'list_swimlanes':
                swimlanes = store.get_swimlanes(params.get('project_id'))
                self._send_json({'result': swimlanes})
                return

            if tool == 'get_task_stats':
                tasks = store.list_tasks(params.get('project_id'))
                stats = {
                    'total': len(tasks),
                    'by_swimlane': {},
                    'by_priority': {},
                    'blocked': 0
                }
                for task in tasks:
                    swimlane = task.get('swimlane', 'unknown')
                    priority = task.get('priority', 'P2')
                    stats['by_swimlane'][swimlane] = stats['by_swimlane'].get(swimlane, 0) + 1
                    stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                    if task.get('is_blocked'):
                        stats['blocked'] += 1
                self._send_json({'result': stats})
                return

            if tool == 'list_comments':
                # Comments are stored in task
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                comments = task.get('comments', []) if task else []
                self._send_json({'result': comments})
                return

            if tool == 'list_commits':
                # Commits are stored in task
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                commits = task.get('commits', []) if task else []
                self._send_json({'result': commits})
                return

            if tool == 'list_artifacts':
                # Artifacts are stored in task
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                artifacts = task.get('artifacts', []) if task else []
                self._send_json({'result': artifacts})
                return

            if tool == 'get_dependencies':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                deps = task.get('depends_on', []) if task else []
                self._send_json({'result': deps})
                return

            if tool == 'get_traceability':
                task = store.get_task(params.get('project_id'), params.get('task_id'))
                trace = task.get('traceability', []) if task else []
                self._send_json({'result': trace})
                return

            self._send_error(f'Unknown tool: {tool}', 400)
            return

        self._send_error('Not found', 404)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    parser = argparse.ArgumentParser(description='Wicked Kanban Data API')
    parser.add_argument('--port', '-p', type=int, default=18888, help='Port to listen on')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    args = parser.parse_args()

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


if __name__ == '__main__':
    main()
