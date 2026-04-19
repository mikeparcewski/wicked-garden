---
description: Grant or revoke yolo (auto-approve) for a crew project
argument-hint: "<project-name> --approve | --revoke | --status"
---

# /wicked-garden:crew:yolo

Grant, revoke, or inspect **yolo auto-approval** for a crew project. When granted,
`phase_manager.approve_phase()` auto-advances on APPROVE verdicts without user
confirmation. CONDITIONAL and REJECT always surface to the user regardless.

**Full-rigor policy**: yolo is ALLOWED at full rigor with explicit `--approve`. A
scope-increase (augment OR re-tier-up) mutation in phase-end re-eval AUTO-REVOKES
yolo with an audit line — safety is one-way.

## Arguments

- `project-name` (required): crew project slug.
- `--approve`: grant yolo (writes `yolo_approved_by_user=true` to ProjectState).
- `--revoke`: user-initiated revoke (writes `yolo_approved_by_user=false`).
- `--status`: show current flag + last yolo-audit entry.

## Flow

1. Resolve the project via `phase_manager.py` (reject if archived).
2. Read `rigor_tier` from ProjectState extras.
3. If `rigor_tier == "full"` and `--approve`: print the full-rigor warning:

   ```
   YOLO @ full rigor is an explicit safety waiver. Auto-approve applies to APPROVE
   verdicts only; CONDITIONAL and REJECT still surface. A scope-increase mutation
   auto-revokes yolo. Confirmed by your --approve flag.
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
/wicked-garden:crew:yolo my-project --approve
# → "Yolo granted for my-project. To revoke: /wicked-garden:crew:yolo my-project --revoke"

/wicked-garden:crew:yolo my-project --status
# → "yolo_approved_by_user=true; granted_at=2026-04-19T..."
```

## Safety Notes

- Yolo NEVER bypasses CONDITIONAL or REJECT — only APPROVE.
- Yolo NEVER bypasses the banned-reviewer check.
- Scope-increase mutations (`op: augment` or `op: re_tier` with `new_rigor_tier: full`)
  auto-revoke yolo and emit a `yolo-audit.jsonl` entry.
