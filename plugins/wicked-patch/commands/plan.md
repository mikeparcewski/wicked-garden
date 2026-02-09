---
description: Show what would be affected by a change without generating patches
---

# /wicked-patch:plan

Show what would be affected by a change without generating patches.

## Arguments

- `symbol_id` (required): Symbol ID to analyze
- `--change`: Change type (`add_field`, `rename_field`, `remove_field`, `modify_field`)
- `--depth`: Max traversal depth (default: 5)
- `--json`: Output as JSON

## Instructions

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && python3 patch.py plan "<symbol_id>" --change "<change_type>" [--json]
```

## Examples

```bash
# Plan for adding a field
/wicked-patch:plan "User.java::User" --change add_field

# Plan for rename with JSON output
/wicked-patch:plan "Order.java::Order" --change rename_field --json
```

## Output

```
═══════════════════════════════════════════════════════════
PROPAGATION PLAN
═══════════════════════════════════════════════════════════

Source: User
  Type: entity
  File: /path/to/User.java
  Line: 22

Direct Impacts (3):
  • email (entity_field) @ User.java
  • name (entity_field) @ User.java
  • id (entity_field) @ User.java

Downstream Impacts (5):
  • USER_EMAIL (column) @ migration.sql
  • user-form.jsp (ui_binding) @ user-form.jsp
  ...

───────────────────────────────────────────────────────────
Total: 9 symbols in 4 files
═══════════════════════════════════════════════════════════
```
