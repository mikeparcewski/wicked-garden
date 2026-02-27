---
description: Show available startah commands and usage
---

# /wicked-garden:startah:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-startah Help

Issue reporting for bugs, UX friction points, and unmet outcomes in the wicked-garden ecosystem.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:startah:report-issue` | File a GitHub issue for a bug, UX friction, or unmet outcome |
| `/wicked-garden:startah:help` | This help message |

## Quick Start

```
/wicked-garden:startah:report-issue bug
/wicked-garden:startah:report-issue ux-friction
/wicked-garden:startah:report-issue --list-unfiled
```

## Examples

### Report a Bug
```
/wicked-garden:startah:report-issue bug
```

### Report UX Friction
```
/wicked-garden:startah:report-issue ux-friction
```

### Report Unmet Outcome
```
/wicked-garden:startah:report-issue unmet-outcome
```

### List Unfiled Issues
```
/wicked-garden:startah:report-issue --list-unfiled
```

## Integration

- **wicked-mem**: Recalls context about known issues
- **wicked-kanban**: Links issues to project tasks
```
