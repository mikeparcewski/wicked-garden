---
description: Grant or revoke auto-approve (APPROVE-verdict fast-lane) for a crew project
argument-hint: "<project-name> --approve --justification \"<text>\" | --revoke | --status"
---

# /wicked-garden:crew:auto-approve

Grant, revoke, or inspect **auto-approval** for a crew project. When granted,
`phase_manager.approve_phase()` auto-advances on APPROVE verdicts without user
confirmation. CONDITIONAL and REJECT always surface to the user regardless.

> **Renamed from `crew:yolo`** (v6.3.3). The alias `/wicked-garden:crew:yolo` still
> works — it redirects here. The `yolo` subcommand name in `phase_manager.py` is
> unchanged for backward compatibility.

## When to use this vs the others

| Command | What it does |
|---------|-------------|
| `crew:execute` | Run a **single phase** to completion |
| `crew:just-finish` | Run **ALL remaining phases** to completion |
| `crew:auto-approve` | Toggle the APPROVE-auto-advance flag (**no execution**) |

Use `crew:auto-approve --approve` before `crew:just-finish` or `crew:execute` to
eliminate manual confirmation on routine APPROVE verdicts. CONDITIONAL and REJECT
always pause regardless.

**Full-rigor policy**: auto-approve is ALLOWED at full rigor with explicit `--approve`,
subject to three guardrails (#470):

1. **Justification** — `--justification "<text>"` must be >= 40 characters.
2. **Cooldown** — after an auto-revoke (scope-increase trigger), a 5-minute
   cooldown blocks re-grant.
3. **Second-persona review** — a sentinel at
   `{project_dir}/phases/yolo-approval/second-persona-review.md` must exist
   with >= 100 bytes of non-whitespace content. Produce it via
   `/wicked-garden:persona:as <specialist> "review the project spec and
   confirm auto-approve is safe"` (any persona qualifies).

A scope-increase (augment OR re-tier-up) mutation in phase-end re-eval
AUTO-REVOKES auto-approve with an audit line — safety is one-way.

## Arguments

- `project-name` (required): crew project slug.
- `--approve`: grant auto-approve (writes `yolo_approved_by_user=true` to ProjectState).
- `--justification "<text>"`: required at full rigor (>= 40 chars). Captured
  in `yolo-audit.jsonl` under the grant record's `justification` field.
- `--revoke`: user-initiated revoke (writes `yolo_approved_by_user=false`).
- `--status`: show current flag + last yolo-audit entry.

## Flow

1. Resolve the project via `phase_manager.py` (reject if archived).
2. Read `rigor_tier` from ProjectState extras.
3. If `rigor_tier == "full"` and `--approve`: print the full-rigor warning:

   ```
   AUTO-APPROVE @ full rigor is an explicit safety waiver. Auto-approve applies to APPROVE
   verdicts only; CONDITIONAL and REJECT still surface. A scope-increase mutation
   auto-revokes this flag. Confirmed by your --approve flag.
   ```

4. Write the flag:

   ```bash
   # Grant
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
     scripts/crew/phase_manager.py "${PROJECT_NAME}" yolo --action approve

   # Revoke
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
     scripts/crew/phase_manager.py "${PROJECT_NAME}" yolo --action revoke

   # Status
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
     scripts/crew/phase_manager.py "${PROJECT_NAME}" yolo --action status
   ```

5. The `phase_manager.py yolo` action appends an audit line to
   `{project_dir}/yolo-audit.jsonl` of shape:

   ```json
   {"event": "granted|revoked|status",
    "timestamp": "<ISO>",
    "reason": "<text>",
    "scope": "project:<slug>",
    "prior_value": <bool>, "new_value": <bool>}
   ```

6. Print confirmation + the revoke command.

## Example

```
/wicked-garden:crew:auto-approve my-project --approve
# → "Auto-approve granted for my-project. To revoke: /wicked-garden:crew:auto-approve my-project --revoke"

/wicked-garden:crew:auto-approve my-project --status
# → "yolo_approved_by_user=true; granted_at=2026-04-19T..."
```

## Safety Notes

- Auto-approve NEVER bypasses CONDITIONAL or REJECT — only APPROVE.
- Auto-approve NEVER bypasses the banned-reviewer check.
- Scope-increase mutations (`op: augment` or `op: re_tier` with `new_rigor_tier: full`)
  auto-revoke and emit a `yolo-audit.jsonl` entry.
