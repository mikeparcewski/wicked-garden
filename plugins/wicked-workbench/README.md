# wicked-workbench

Turn any question into a live dashboard. "Show blocked tasks" becomes a visual board in your browser - no frontend code needed.

> **EXPERIMENTAL**: Renders structured JSON with component hierarchy. Full styled rendering coming soon.

## Quick Start

```bash
# Install
pip install wicked-workbench

# Start the server
/workbench
# or: wicked-workbench

# Open http://localhost:18889

# Then just ask Claude:
"Show my high priority tasks in a dashboard"
"Create a sprint health board"
"Display data quality metrics"
```

## How It Works

```
You ask a question
  → Claude reads component catalogs from your installed plugins
  → Generates an A2UI dashboard definition
  → Workbench renders it + fetches live data
  → You see it at http://localhost:18889
```

Your dashboards are only limited by which plugins you have installed. More plugins = more dashboard components available.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/workbench` | Start the workbench server | `/workbench` |

## Available Components by Plugin

| Plugin | Dashboard Components |
|--------|---------------------|
| wicked-kanban | Task boards, swimlanes, dependency graphs |
| wicked-mem | Memory panels, decision logs |
| wicked-data | Data profiling, quality metrics |
| wicked-engineering | Code health, architecture diagrams |
| wicked-delivery | Sprint boards, burndown charts |
| wicked-product | Roadmaps, UX audits, feedback panels |
| wicked-platform | Pipeline status, security scans |

## Configuration

| Setting | Default | Environment Variable |
|---------|---------|---------------------|
| Port | 18889 | `WICKED_WORKBENCH_PORT` |
| Host | 127.0.0.1 | `WICKED_WORKBENCH_HOST` |
| Database | SQLite (auto-created) | `DATABASE_URL` |

Optional OAuth for multi-user: set `GOOGLE_CLIENT_ID`/`GITHUB_CLIENT_ID` + secrets.

## License

MIT
