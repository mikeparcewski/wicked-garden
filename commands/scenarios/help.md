---
description: Show available E2E scenario commands and usage
---

# /wicked-garden:scenarios:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-scenarios Help

E2E testing with markdown scenarios orchestrating lightweight CLI tools — curl, hurl, playwright, k6, trivy, semgrep, and more.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:scenarios:run` | Execute an E2E test scenario by orchestrating CLI tools |
| `/wicked-garden:scenarios:list` | List available scenarios with tool availability status |
| `/wicked-garden:scenarios:check` | Validate scenario file format and structure |
| `/wicked-garden:scenarios:report` | File GitHub issues from test failures with deduplication |
| `/wicked-garden:scenarios:setup` | Install required CLI tools for running scenarios |
| `/wicked-garden:scenarios:help` | This help message |

## Quick Start

```
/wicked-garden:scenarios:list
/wicked-garden:scenarios:run
/wicked-garden:scenarios:setup
```

## Workflow

1. **List** available scenarios and check tool readiness
2. **Setup** any missing CLI tools
3. **Check** scenario files for validity
4. **Run** scenarios to execute tests
5. **Report** failures as GitHub issues

## Examples

### List and Run
```
/wicked-garden:scenarios:list
/wicked-garden:scenarios:run
```

### Validate Scenarios
```
/wicked-garden:scenarios:check
```

### Report Failures
```
/wicked-garden:scenarios:report
```

## Supported Tools

| Tool | Use Case |
|------|----------|
| curl / hurl | HTTP API testing |
| playwright | Browser E2E testing |
| agent-browser | AI-driven browser testing |
| hey / k6 | Load and performance testing |
| trivy / semgrep | Security scanning |
| pa11y | Accessibility testing |

## Integration

- **wicked-qe**: Test planning and acceptance criteria
- **wicked-platform**: Security scenario execution
- **wicked-crew**: Specialist routing for test phases
```
