---
description: Show available patch commands and usage
---

# /wicked-garden:patch:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-patch Help

Structural code transformations — rename symbols, add/remove fields, and propagate changes across the entire codebase.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:patch:rename` | Rename a field/symbol across all usages |
| `/wicked-garden:patch:add-field` | Add a field to an entity and propagate to affected files |
| `/wicked-garden:patch:remove` | Remove a field and all its usages |
| `/wicked-garden:patch:plan` | Preview what would be affected without generating patches |
| `/wicked-garden:patch:apply` | Apply patches from a saved JSON file |
| `/wicked-garden:patch:new-generator` | Create a new language generator with scaffolding and tests |
| `/wicked-garden:patch:help` | This help message |

## Quick Start

```
/wicked-garden:patch:plan
/wicked-garden:patch:rename
/wicked-garden:patch:add-field
```

## Workflow

1. **Plan** — see what files and symbols would be affected
2. **Generate** — use rename, add-field, or remove to create patches
3. **Apply** — apply saved patches from a JSON file

## Examples

### Rename a Symbol
```
/wicked-garden:patch:rename
```

### Add a Field
```
/wicked-garden:patch:add-field
```

### Preview Impact
```
/wicked-garden:patch:plan
```

### Extend Language Support
```
/wicked-garden:patch:new-generator
```

## Integration

- **wicked-search**: Symbol lookup and blast radius analysis
- **wicked-engineering**: Architecture-aware refactoring
- **wicked-qe**: Test updates after structural changes
```
