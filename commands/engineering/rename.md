---
description: Rename a field/symbol across all usages in the codebase
---

# /wicked-garden:engineering:rename

Rename a field/symbol across all usages in the codebase.

## Arguments

- `symbol_id` (required): Target symbol ID
- `--old` (required): Current field name
- `--new` (required): New field name
- `--output`, `-o`: Save patches to file
- `--apply`: Apply patches immediately
- `--verbose`, `-v`: Show full diffs

## Instructions

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" rename "<symbol_id>" --old "<old_name>" --new "<new_name>" [--verbose]
```

## Examples

```bash
# Rename field in entity
/wicked-garden:engineering:rename "User.java::User" --old status --new userStatus

# Save patches for review
/wicked-garden:engineering:rename "Order.java::Order" --old date --new orderDate -o patches.json
```

## What Gets Updated

- Field declarations
- Getter/setter method names
- Property references (`this.oldName` → `this.newName`)
- JSP EL expressions (`${entity.oldName}` → `${entity.newName}`)
- Form bindings (`path="oldName"` → `path="newName"`)
- TypeScript interfaces and type aliases
- SQL column names (generates ALTER TABLE RENAME COLUMN)
