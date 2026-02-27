---
description: Show available delivery management commands and usage
---

# /wicked-garden:delivery:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-delivery Help

Multi-perspective delivery reporting and metrics configuration for project tracking.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:delivery:report <file>` | Generate delivery reports from project data |
| `/wicked-garden:delivery:setup` | Configure cost model, commentary sensitivity, and sprint cadence |
| `/wicked-garden:delivery:help` | This help message |

## Quick Start

```
/wicked-garden:delivery:report sprint-data.csv
/wicked-garden:delivery:setup
```

## Examples

### Reports
```
/wicked-garden:delivery:report backlog.csv --personas "CTO,PM,Scrum Master"
/wicked-garden:delivery:report metrics.csv --all --output ./reports
```

### Configuration
```
/wicked-garden:delivery:setup
/wicked-garden:delivery:setup --reset
```

## Integration

- **wicked-crew**: Specialist routing for delivery phases
- **wicked-kanban**: Project and task data as report input
- **wicked-product**: Strategic alignment for delivery priorities
```
