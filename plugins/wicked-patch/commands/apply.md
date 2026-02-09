---
description: Apply patches from a saved JSON file
---

# /wicked-patch:apply

Apply patches from a saved JSON file.

## Arguments

- `patches_file` (required): Path to patches JSON file
- `--dry-run`: Show what would be done without applying

## Instructions

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && python3 patch.py apply "<patches_file>" [--dry-run]
```

## Workflow

```bash
# 1. Generate patches and save
/wicked-patch:add-field SYMBOL --name foo --type String -o patches.json

# 2. Review the patches
cat patches.json

# 3. Dry-run to verify
/wicked-patch:apply patches.json --dry-run

# 4. Apply for real
/wicked-patch:apply patches.json
```

## Patches File Format

```json
{
  "change_type": "add_field",
  "target": "User.java::User",
  "files_affected": ["User.java", "migration.sql"],
  "patch_count": 3,
  "generated_at": "2024-01-15T10:30:00",
  "patches": [
    {
      "file": "User.java",
      "line_start": 45,
      "line_end": 44,
      "old": "",
      "new": "    private String email;",
      "description": "Add field 'email'"
    }
  ]
}
```
