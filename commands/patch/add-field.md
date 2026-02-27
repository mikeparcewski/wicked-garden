---
description: Add a field to an entity/class and propagate to all affected files
---

# /wicked-garden:patch:add-field

Add a field to an entity/class and propagate to all affected files.

## Arguments

- `symbol_id` (required): Target symbol ID (e.g., `path/Entity.java::EntityName`)
- `--name` (required): Field name
- `--type` (required): Field type (String, Integer, Boolean, Date, etc.)
- `--column`: Database column name (defaults to SNAKE_CASE of name)
- `--label`: UI label for form fields
- `--required`: Mark field as non-nullable
- `--output`, `-o`: Save patches to JSON file
- `--apply`: Apply patches immediately
- `--verbose`, `-v`: Show full diffs

## Instructions

Run the patch CLI:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && python3 patch.py add-field "<symbol_id>" \
  --name "<name>" \
  --type "<type>" \
  [--column "<column>"] \
  [--required] \
  [--verbose]
```

## Examples

```bash
# Add email field to User entity
/wicked-garden:patch:add-field "User.java::User" --name email --type String --column USER_EMAIL

# Add required date field
/wicked-garden:patch:add-field "Order.java::Order" --name createdAt --type datetime --required

# Save patches for review
/wicked-garden:patch:add-field "Entity.java::Entity" --name foo --type String -o patches.json
```

## Output

Shows generated patches grouped by file:

```
═══════════════════════════════════════════════════════════
GENERATED PATCHES
═══════════════════════════════════════════════════════════

Change: add_field
Target: User.java::User
Files affected: 3
Patches: 5

PATCHES:

  User.java
    [45-44] Add field 'email' (String)
    [98-97] Add getter for 'email'
    [99-98] Add setter for 'email'

  user-form.jsp
    [67-66] Add form field for 'email'

  migration.sql
    [10-9] Add column 'EMAIL' to 'USERS'

═══════════════════════════════════════════════════════════
```
