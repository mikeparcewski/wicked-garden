---
description: Archive or unarchive a crew project
argument-hint: "<project-name> [--unarchive]"
---

# /wicked-garden:crew:archive

Archive a project to remove it from active listings. Archived projects are hidden from default `list projects` output but not deleted.

## Arguments

- `project-name` (required): The project name to archive/unarchive
- `--unarchive` (optional): Restore an archived project to active status

## Instructions

1. Parse the project name from arguments

2. Update the project record via phase_manager:

   For **archive**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py "${PROJECT_NAME}" update \
     --data '{"archived": true, "archived_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}' \
     --json
   ```

   For **unarchive**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py "${PROJECT_NAME}" update \
     --data '{"archived": false, "archived_at": null}' \
     --json
   ```

3. Report the result to the user. Confirm what action was taken and the project name.

   ```markdown
   Project **{name}** archived successfully.
   ```

## Example Usage

```
/wicked-garden:crew:archive my-old-project
/wicked-garden:crew:archive my-old-project --unarchive
```
