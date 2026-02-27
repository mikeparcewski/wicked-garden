---
description: Show available workbench commands and usage
---

# /wicked-garden:workbench:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-workbench Help

Dashboard server for visualizing kanban boards, search results, delivery reports, and plugin data.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:workbench:workbench [action]` | Launch or manage the dashboard server |
| `/wicked-garden:workbench:help` | This help message |

## Quick Start

```
/wicked-garden:workbench:workbench start
/wicked-garden:workbench:workbench open
/wicked-garden:workbench:workbench status
```

## Actions

| Action | Description |
|--------|-------------|
| `start` | Start the dashboard server |
| `stop` | Stop the dashboard server |
| `status` | Check if the server is running |
| `open` | Open the dashboard in a browser |

## Integration

- **wicked-kanban**: Board and task visualization
- **wicked-search**: Code intelligence dashboards
- **wicked-delivery**: Delivery report rendering
- **wicked-observability**: Health and trace visualization
```
