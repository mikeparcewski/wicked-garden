---
name: adopt-legacy
description: |
  Detect and transform legacy beta.3 project markers to v6.0 format (D5, AC-13 c).
  Handles three markers: missing phase_plan_mode, markdown re-eval addendums in
  process-plan.md (pre-D2 format), and references to the removed legacy gate-bypass
  env-var in project files. Safe to run on v6-native projects — no markers detected
  means no-op. Dry-run by default; --apply to write changes.

  Use when: upgrading a project from wicked-garden v6.0-beta.3 to v6.0; checking
  whether a project needs migration; transforming legacy artifacts before running
  crew:approve on a beta project.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# Adopt Legacy (beta.3 → v6.0 upgrade)

Inspects a crew project directory for three legacy markers and offers to transform
them in-place. All transformations are idempotent — running twice is a no-op if no
markers remain.

## Detected markers

| Marker | Detection | Transformation |
|--------|-----------|----------------|
| Missing `phase_plan_mode` | `project.json` lacks the key | Sets `phase_plan_mode = "facilitator"` |
| Markdown re-eval addendum | `## Re-evaluation YYYY-MM-DD` in `process-plan.md` | Serialises each block to `phases/{phase}/reeval-log.jsonl` (best-effort); replaces block with a migration comment |
| Legacy gate-bypass reference | Any `.md`/`.json` file contains the removed env-var string | Replaces with a commented removal note |

## Usage

```bash
# Preview changes (default — no writes)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/adopt_legacy.py" <project-dir>

# Apply transformations
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/adopt_legacy.py" <project-dir> --apply
```

Or invoke directly as a crew command:

```
/wicked-garden:crew:adopt-legacy <project-dir>
```

## Output example

```
[adopt-legacy] Scanning project: my-feature
[adopt-legacy] Mode: dry-run (pass --apply to write changes)
[adopt-legacy] Detected 3 legacy marker(s)
[adopt-legacy] Transformation 1/3:  [dry-run] would set phase_plan_mode = "facilitator" in project.json
[adopt-legacy] Transformation 2/3:  [dry-run] would migrate 2 markdown addendum(s) from process-plan.md → phases/unknown/reeval-log.jsonl
[adopt-legacy] Transformation 3/3:  [dry-run] would replace legacy gate-bypass reference in status.md
[adopt-legacy] Dry-run complete. Run with --apply to write changes.
```

## When to use

- You see `phase_manager.py` complaining about missing `phase_plan_mode`
- You have a beta.3 project with prose re-eval addendums in `process-plan.md`
- Any project file references the removed legacy bypass env-var

## Script location

`scripts/crew/adopt_legacy.py` — stdlib-only, no external dependencies.
