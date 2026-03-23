---
description: Show available quality engineering commands and usage
---

# /wicked-garden:qe:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# qe Help

Quality engineering — test planning, scenario generation, code review, acceptance testing, and test automation.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:qe:qe <target>` | Quality review across requirements, design, architecture, code, and deployment |
| `/wicked-garden:qe:qe-plan <feature>` | Generate comprehensive test plan for a feature or change |
| `/wicked-garden:qe:qe-review <path>` | Review test quality, coverage, and best practices |
| `/wicked-garden:qe:scenarios <feature>` | Generate test scenarios — happy paths, edge cases, error conditions |
| `/wicked-garden:qe:acceptance <scenario>` | Evidence-gated acceptance testing (Write, Execute, Review pipeline) |
| `/wicked-garden:qe:automate <plan>` | Generate test code from scenarios or test plan |
| `/wicked-garden:qe:run <scenario>` | Execute an E2E test scenario by orchestrating CLI tools |
| `/wicked-garden:qe:list` | List available scenarios with tool availability status |
| `/wicked-garden:qe:check` | Validate scenario file format and structure |
| `/wicked-garden:qe:report` | File GitHub issues from test failures with deduplication |
| `/wicked-garden:qe:setup` | Install required CLI tools for running scenarios |
| `/wicked-garden:qe:help` | This help message |

## Quick Start

```
/wicked-garden:qe:scenarios "user registration flow"
/wicked-garden:qe:qe-plan "add payment processing"
/wicked-garden:qe:qe-review ./tests
```

## Examples

### Scenario Generation
```
/wicked-garden:qe:scenarios "checkout with discount codes"
/wicked-garden:qe:scenarios "file upload API"
```

### Test Planning
```
/wicked-garden:qe:qe-plan "OAuth2 integration" --scope e2e
/wicked-garden:qe:qe-plan "database migration" --scope all
```

### Quality Review
```
/wicked-garden:qe:qe ./api --focus code
/wicked-garden:qe:qe-review ./tests --focus flakiness
```

### Acceptance Testing
```
/wicked-garden:qe:acceptance ./scenarios --phase all
/wicked-garden:qe:acceptance ./test.md --phase execute --plan plan.md
```

### Test Automation
```
/wicked-garden:qe:automate ./scenarios --framework pytest --output ./tests
/wicked-garden:qe:automate plan.md --framework jest
```

## Integration

- **wicked-crew**: Specialist routing for test strategy and QE gate phases
- **engineering**: Code review with quality lens
- **product**: Acceptance criteria as test input
- **E2E scenarios**: Markdown-based test scenarios orchestrating CLI tools (curl, playwright, k6, trivy, etc.)
```
