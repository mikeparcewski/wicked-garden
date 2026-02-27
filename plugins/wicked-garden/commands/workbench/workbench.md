---
description: Launch or manage the Wicked Workbench dashboard server
argument-hint: "[start|stop|status|open]"
---

# /wicked-garden:workbench-workbench

Launch or manage the Wicked Workbench dashboard.

## Arguments

- `start` (default): Start the workbench server
- `stop`: Stop the workbench server
- `status`: Check server status
- `open`: Open the dashboard in browser

## Instructions

### Start Server

```bash
if curl -s http://localhost:18889/health > /dev/null 2>&1; then
  echo "Workbench already running at http://localhost:18889"
else
  uvx --from wicked-workbench-server wicked-workbench &
  sleep 2
  echo "Workbench started at http://localhost:18889"
fi
```

### Stop Server

```bash
pkill -f "wicked-workbench-server" || echo "Workbench not running"
```

### Check Status

```bash
if curl -s http://localhost:18889/health > /dev/null 2>&1; then
  echo "Workbench running"
  curl -s http://localhost:18889/api/v1/data/plugins | jq '{plugins: .meta.total_plugins, sources: .meta.total_sources}'
else
  echo "Workbench not running"
fi
```

### Open Dashboard

```bash
open http://localhost:18889/
```

## Output

```markdown
## Wicked Workbench

**Status**: Running
**URL**: http://localhost:18889

**Data Sources**: 7 plugins, 24 sources

Query data via the gateway: GET /api/v1/data/{plugin}/{source}/{verb}
Generate dashboards by asking Claude Code to create A2UI views.
```

## Examples

```
/workbench                    # Start server (default)
/workbench start              # Start server explicitly
/workbench status             # Check if running
/workbench open               # Open in browser
```
