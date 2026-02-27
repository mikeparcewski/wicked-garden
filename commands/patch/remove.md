---
description: Remove a field and all its usages from the codebase
---

# /wicked-garden:patch:remove

Remove a field and all its usages from the codebase.

## Arguments

- `symbol_id` (required): Target symbol ID
- `--field` (required): Field name to remove
- `--output`, `-o`: Save patches to file
- `--apply`: Apply patches immediately
- `--verbose`, `-v`: Show full diffs

## Instructions

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && python3 patch.py remove "<symbol_id>" --field "<field_name>" [--verbose]
```

## Examples

```bash
# Remove deprecated field
/wicked-garden:patch:remove "User.java::User" --field legacyStatus

# Preview removal
/wicked-garden:patch:remove "Entity.java::Entity" --field oldField --verbose
```

## Warning

This operation DELETES code. Always review patches before applying:

```bash
# Generate and save patches
/wicked-garden:patch:remove SYMBOL --field foo -o patches.json

# Review
cat patches.json

# Apply when confident
/wicked-garden:patch:apply patches.json
```
