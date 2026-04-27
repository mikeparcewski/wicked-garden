---
description: Diagnose drift between native TaskList and garden chain (read-only)
argument-hint: "[--project=<slug> | --all] [--json]"
---

# /wicked-garden:crew:reconcile

Walks the native TaskList store and the garden chain (process-plan.json + per-phase gate-result.json) and surfaces drift WITHOUT mutating either store.

> **Scope**: Pure diagnostic. Read-only by contract — guaranteed not to write to any task file or project artifact. If the two stores disagree, this command names the disagreements; it does not fix them.

This is the interim Option C from the issue #579 brainstorm (D3). Option A (TaskList as truth, garden chain as projection) is a larger refactor that will follow once drift patterns from real usage are visible.

## Drift types reported

| Type             | Meaning                                                                                                    |
|------------------|------------------------------------------------------------------------------------------------------------|
| `missing_native` | A plan task has no matching native task with the expected `chain_id`.                                      |
| `stale_status`   | A native task and its plan phase disagree on completion (e.g., phase APPROVED but native still pending).   |
| `orphan_native`  | A native task carries a `chain_id` whose project slug is not present under the projects root.              |
| `phase_drift`    | A phase's `gate-result.json` is APPROVE/CONDITIONAL but its gate-finding native task is still open. (#653) |

## Arguments

- `--project <slug>` — reconcile a single project by slug
- `--all` — reconcile every project under the projects root
- `--json` — emit machine-readable JSON instead of the text report

Exactly one of `--project` or `--all` is required.

## Instructions

### 1. Run reconcile

```bash
# Single project
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reconcile.py" \
  --project "$PROJECT" ${JSON:+--json}

# All projects
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reconcile.py" \
  --all ${JSON:+--json}
```

The script honors `CLAUDE_CONFIG_DIR` for the native task path (per the lesson from PR #678).

### 2. Render the report

Default output is a human-readable text report grouped by project. Each section shows:

- Counts: plan tasks vs native tasks vs phases-with-gate-result
- Drift summary (by type)
- Per-entry drift details: type, identifier, one-line reason
- Errors (when a store is unreachable; we still report what we can)

Example (text mode):

```
Reconcile report — project: my-project
======================================
  Plan tasks (process-plan.json):   12
  Native tasks (matching chain_id): 11
  Phases with gate-result.json:     3  (clarify, design, build)

Drift summary:
  total:          2
  missing_native: 1
  stale_status:   1
  orphan_native:  0
  phase_drift:    0

Drift entries:
  [missing_native] t7 — no native task with matching chain_id
  [stale_status] task-abc123 — phase 'design' verdict is 'APPROVE' but native task still 'in_progress'
```

If `--json`, the same data is emitted as a single dict (`--project`) or a list of dicts (`--all`).

### 3. What to do with the results

`reconcile` does not mutate either store, so any drift it surfaces is a signal — not an automatic fix. Common next steps:

- **`missing_native`** — a `TaskCreate` was lost or the plan emitted a task without `chain_id`. Re-run the facilitator phase or open an issue with the plan path.
- **`stale_status`** — usually fixed at the next `/wicked-garden:crew:approve` (PR #653 closes the WRITE side). Long-stale entries are worth investigating.
- **`orphan_native`** — the project was deleted or renamed; native tasks are dangling. Consider archiving the parent project or migrating chain ids.
- **`phase_drift`** — the gate completed before #653 landed; one approval cycle should clean it up.

## Examples

```bash
# Default: text report for one project
/wicked-garden:crew:reconcile --project=my-feature

# JSON for piping into another tool
/wicked-garden:crew:reconcile --project=my-feature --json

# Sweep every project
/wicked-garden:crew:reconcile --all
```

## Notes

- Stdlib only; no DomainStore writes.
- Fail-open: if `process-plan.json` is missing or unreadable, the report still lists native tasks the project owns and explains the gap.
- The drift entries this command surfaces in real usage will inform the design of Option A (the projection refactor).
