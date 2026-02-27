---
description: Show available engineering commands and usage
---

# /wicked-garden:engineering:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-engineering Help

Senior engineering perspective — architecture analysis, code review, debugging, documentation, and implementation planning.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:engineering:arch [component]` | Architecture analysis and design recommendations |
| `/wicked-garden:engineering:debug <symptom>` | Systematic debugging with root cause analysis |
| `/wicked-garden:engineering:docs <file>` | Generate or improve documentation |
| `/wicked-garden:engineering:plan <change>` | Review changes and recommend implementation steps |
| `/wicked-garden:engineering:review [path]` | Code review for quality, patterns, and maintainability |
| `/wicked-garden:engineering:help` | This help message |

## Quick Start

```
/wicked-garden:engineering:review ./src
/wicked-garden:engineering:plan "migrate from REST to GraphQL"
/wicked-garden:engineering:debug "timeout errors in payment service"
```

## Examples

### Architecture
```
/wicked-garden:engineering:arch "auth module" --scope service
/wicked-garden:engineering:arch --scope system
```

### Code Review
```
/wicked-garden:engineering:review ./api --focus security
/wicked-garden:engineering:review ./lib --focus performance --scenarios
```

### Documentation
```
/wicked-garden:engineering:docs ./api --type api
/wicked-garden:engineering:docs ./README.md --type readme
```

## Integration

- **wicked-crew**: Specialist routing for engineering phases
- **wicked-qe**: Test strategy and quality gates
- **wicked-search**: Code symbol and blast radius analysis
- **wicked-platform**: Security and infrastructure concerns
```
