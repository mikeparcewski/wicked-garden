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

2. **Tier 1 — Try Control Plane first**

   If `--unarchive` flag is present:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" crew projects unarchive "${PROJECT_NAME}"
   ```

   Otherwise archive the project:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" crew projects archive "${PROJECT_NAME}"
   ```

   Check the result. If the command succeeds (exit code 0 and valid JSON response), skip to step 4.

3. **Tier 2 — Local fallback via phase_manager**

   If Tier 1 failed (non-zero exit code, HTML error response, connection refused, or any other failure), fall back to updating the project record directly through phase_manager:

   For **archive**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${PROJECT_NAME}" update \
     --data '{"archived": true, "archived_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}' \
     --json
   ```

   For **unarchive**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${PROJECT_NAME}" update \
     --data '{"archived": false, "archived_at": null}' \
     --json
   ```

4. Report the result to the user. Confirm what action was taken, the project name, and **which path was used** (Control Plane or local fallback). Example:

   ```markdown
   Project **{name}** archived successfully (via local fallback — Control Plane unavailable).
   ```

## Example Usage

```
/wicked-garden:crew:archive my-old-project
/wicked-garden:crew:archive my-old-project --unarchive
```
