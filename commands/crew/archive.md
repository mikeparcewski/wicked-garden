---
description: Archive or unarchive a crew project
argument-hint: <project-name> [--unarchive]
---

# /wicked-garden:crew:archive

Archive a project to remove it from active listings. Archived projects are hidden from default `list projects` output but not deleted.

## Arguments

- `project-name` (required): The project name to archive/unarchive
- `--unarchive` (optional): Restore an archived project to active status

## Instructions

1. Parse the project name from arguments

2. If `--unarchive` flag is present:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" unarchive projects "${PROJECT_NAME}"
   ```

3. Otherwise archive the project:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/api.py" archive projects "${PROJECT_NAME}"
   ```

4. Report the result to the user. Confirm what action was taken and the project name.

## Example Usage

```
/wicked-garden:crew:archive my-old-project
/wicked-garden:crew:archive my-old-project --unarchive
```
