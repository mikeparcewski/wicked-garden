# wicked-workbench

Web dashboard for your wicked-garden ecosystem. Browse all installed plugins and commands from a React UI, execute them with streaming results, and generate custom dashboards by asking Claude in plain English.

> **Early access**: Dashboard rendering uses structured component hierarchy. Visual polish is actively improving.

## Quick Start

```bash
# Install the plugin
claude plugin install wicked-workbench@wicked-garden

# Start the server
/workbench start

# Open http://localhost:18889

# Then ask Claude to build dashboards:
"Show my high priority tasks in a dashboard"
"Create a sprint health board"
```

## How It Works

1. Start the workbench server (`/workbench start`)
2. Ask Claude for a dashboard in plain English
3. Claude generates an A2UI component layout from your installed plugins
4. Workbench renders it with live data at http://localhost:18889

More installed plugins = more dashboard components available.

## Commands & Skills

| Component | What It Does | Example |
|-----------|-------------|---------|
| `/workbench` | Start, stop, or check the server | `/workbench start` |
| `dashboard` skill | Generate A2UI dashboards from natural language | "Create a sprint board" |

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
