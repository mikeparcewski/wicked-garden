# wicked-workbench

A live web dashboard that turns natural-language requests into visual views of your wicked-garden data — tasks, memories, project phases, and code symbols — without writing a line of UI code.

## Quick Start

```bash
# 1. Install
claude plugin install wicked-workbench@wicked-garden

# 2. Start the server
/wicked-workbench:workbench start

# 3. Ask Claude to build a dashboard
"Show my high priority blocked tasks with decision context"
```

## Workflows

### Build a sprint health board

You ask: "Create a sprint board showing blocked tasks and recent decisions"

Claude fetches available data sources, generates an A2UI layout, and posts it to the workbench renderer:

```bash
# What happens automatically:
GET  http://localhost:18889/api/v1/data/plugins
# → {plugins: 7, sources: 24}

GET  http://localhost:18889/api/v1/data/wicked-kanban/tasks/list
# → [{id: "42", title: "Fix auth", status: "blocked", priority: "high"}, ...]

GET  "http://localhost:18889/api/v1/data/wicked-mem/memories/search?query=decisions"
# → [{type: "decision", content: "Chose JWT over sessions", ...}, ...]

POST http://localhost:18889/api/render
# → Dashboard rendered at http://localhost:18889
```

Open http://localhost:18889 to see the result.

### Check project phase progress

```bash
/wicked-workbench:workbench status
```

```
## Wicked Workbench

Status: Running
URL: http://localhost:18889

Data Sources: 7 plugins, 24 sources

Query data via the gateway: GET /api/v1/data/{plugin}/{source}/{verb}
Generate dashboards by asking Claude Code to create A2UI views.
```

Then ask: "Show current crew project phases with signal summary" — Claude queries `/api/v1/data/wicked-crew/phases/list` and renders a phase tracker component.

### Query the data gateway directly

Every plugin that declares a `wicked.json` becomes a REST endpoint:

```bash
# Tasks
curl http://localhost:18889/api/v1/data/wicked-kanban/tasks/list

# Memories
curl "http://localhost:18889/api/v1/data/wicked-mem/memories/search?query=architecture"

# Code symbols
curl http://localhost:18889/api/v1/data/wicked-search/symbols/list

# Project phases
curl http://localhost:18889/api/v1/data/wicked-crew/phases/list
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-workbench:workbench start` | Start the dashboard server at http://localhost:18889 | `/wicked-workbench:workbench start` |
| `/wicked-workbench:workbench stop` | Stop the server | `/wicked-workbench:workbench stop` |
| `/wicked-workbench:workbench status` | Check running status and list connected data sources | `/wicked-workbench:workbench status` |
| `/wicked-workbench:workbench open` | Open dashboard in the default browser | `/wicked-workbench:workbench open` |

## How It Works

1. On startup, workbench discovers all installed plugins that declare data sources in `wicked.json`
2. Each source becomes a route: `GET /api/v1/data/{plugin}/{source}/{verb}`
3. When you ask Claude for a dashboard, it queries the gateway for live data
4. Claude generates an A2UI component layout (JSON) describing the view
5. Workbench renders the layout at http://localhost:18889

More installed plugins means more data sources, which means richer dashboard components available to Claude.

## Skills

| Skill | What It Does |
|-------|-------------|
| `dashboard` | Generate A2UI dashboard layouts from natural language; includes component mapping and data gateway query patterns |

## Configuration

| Setting | Default | Environment Variable |
|---------|---------|---------------------|
| Port | 18889 | `WICKED_WORKBENCH_PORT` |
| Host | 127.0.0.1 | `WICKED_WORKBENCH_HOST` |
| Database | SQLite (auto-created) | `DATABASE_URL` |

Optional OAuth for multi-user deployments: set `GOOGLE_CLIENT_ID` or `GITHUB_CLIENT_ID` plus their secrets.

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-kanban | Task boards, swimlanes, blocked task views, sprint tracking | No task data available to dashboard |
| wicked-mem | Memory panels, decision logs, session history views | No memory data available to dashboard |
| wicked-crew | Project phase tracking, specialist engagement, workflow dashboards | No project data available to dashboard |
| wicked-search | Code symbol graphs, lineage visualization, coverage views, hotspot maps | No code data available to dashboard |
| wicked-delivery | Sprint burndown, metrics panels, velocity tracking | No delivery tracking data |
| wicked-smaht | Context assembly visualization | No context data |
| wicked-jam | Decision logs, brainstorming session outputs | No jam data |
| wicked-data | Data profiling results, quality metrics panels | No data insights |
| wicked-engineering | Code health, architecture diagram data | No engineering metrics |
| wicked-platform | Pipeline status, security scan results | No platform metrics |
| wicked-product | Roadmap views, UX audit panels, feedback summaries | No product data |

## License

MIT
