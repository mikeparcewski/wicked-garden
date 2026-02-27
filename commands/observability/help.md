---
description: Show available observability commands and usage
---

# /wicked-garden:observability:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-observability Help

Plugin health monitoring, contract assertions, and hook execution tracing for the wicked-garden ecosystem.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:observability:health` | Run health probes against all installed plugins |
| `/wicked-garden:observability:assert` | Run contract assertions against plugin subprocess outputs |
| `/wicked-garden:observability:traces` | Query hook execution traces for the current session |
| `/wicked-garden:observability:help` | This help message |

## Quick Start

```
/wicked-garden:observability:health
/wicked-garden:observability:traces
/wicked-garden:observability:assert
```

## Examples

### Health Check
```
/wicked-garden:observability:health
```

### Hook Traces
```
/wicked-garden:observability:traces
```

### Contract Assertions
```
/wicked-garden:observability:assert
```

## Integration

- **All plugins**: Health probes check every installed plugin
- **Hook system**: Traces capture hook execution timing and outcomes
- **wicked-workbench**: Dashboard visualization of health and traces
```
