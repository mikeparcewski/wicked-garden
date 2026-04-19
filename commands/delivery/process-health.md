---
description: Surface process memory — kaizen status, unresolved action items, aging alerts
argument-hint: "[--project name] [--format text|json|both]"
---

# /wicked-garden:delivery:process-health

Render the persistent process memory for a crew project — kaizen backlog status, unresolved retrospective action items, and aging alerts for items unresolved across two or more sessions. Backs issue #447.

## Arguments

- `--project` (optional): Project name. Defaults to the active crew project.
- `--format` (optional): `text` (default), `json`, or `both` (json to stderr + text to stdout).

## Instructions

### 1. Resolve the target project

If `--project` is supplied, use it. Otherwise find the active crew project:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If neither resolves to a name, abort with an informative message — this command only operates inside a crew project.

### 2. Render the report

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/delivery/process_health.py --project "{project}" --format text
```

Forward the output verbatim. The report contains:

- Narrative block (if the facilitator has recorded one)
- Kaizen backlog totals and by-status breakdown
- Action-item totals and by-status breakdown
- Aging alerts table (items unresolved for ≥ 2 sessions)
- Recent gate-pass-rate samples
- Path to the `process-memory.md` companion artifact

### 3. Suggest follow-up actions

Based on the report, point the user at the right next move:

- Any aging alerts → suggest `/wicked-garden:crew:retro` or direct resolution via the CLI.
- Kaizen items in `proposed` status older than a week → suggest adopting or rejecting.
- Empty memory (no kaizen, no action items, no pass-rate samples) → suggest running a retro first.

## Examples

```bash
# Show process health for the active project
/wicked-garden:delivery:process-health

# Named project, JSON format
/wicked-garden:delivery:process-health --project my-feature --format json
```

## Related

- `/wicked-garden:crew:retro` writes retro findings into the process memory.
- `/wicked-garden:delivery:setup` configures thresholds this command surfaces.
- Uncertainty gate is evaluated via `scripts/delivery/process_memory.py uncertainty-gate` when a specialist proposes adding a new process gate.
