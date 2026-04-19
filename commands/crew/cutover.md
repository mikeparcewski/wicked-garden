---
description: Cut an in-flight crew project over to mode-3 dispatch
argument-hint: "<project-name> --to=mode-3"
---

# /wicked-garden:crew:cutover

**In-flight cutover** (CR-2 / AC-α11). Legacy crew projects (created before the mode-3
merge) default to `state.dispatch_mode = "v6-legacy"` and run on the pre-existing
dispatcher. This command opts a project into the new mode-3 phase-executor path.

**No silent upgrade.** Existing projects run to completion on legacy dispatch unless
the user explicitly invokes this command. Mode-3 semantics apply only from the next
phase forward after cutover; prior-phase re-eval bookends are NOT synthesized retroactively.

## Arguments

- `project-name` (required): crew project slug.
- `--to=mode-3` (required): target dispatch mode. Currently only `mode-3` is supported.

## Safe Cutover Window

The command validates the project is in a safe state before writing. Cutover is
**refused** when any of these hold:

- An in-flight phase dispatch exists (a phase-executor task is `in_progress`).
- Unresolved conditions exist on the current or prior phase's `conditions-manifest.json`.
- A mid-phase scope-increase is pending re-eval (phase-end re-eval has emitted an
  augment / re-tier-up mutation that has not been applied yet).

## Flow

1. Resolve the project via `phase_manager.py` (reject if archived).
2. Read `state.dispatch_mode` via `_detect_dispatch_mode()`. If already `mode-3`, print
   "already on mode-3" and exit.
3. Validate the safe cutover window. If any validation fails, surface the reason and
   exit non-zero.
4. Write:

   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
     scripts/crew/phase_manager.py "${PROJECT_NAME}" cutover --to mode-3
   ```

   This writes `state.dispatch_mode = "mode-3"` AND emits the one-time migration marker
   at `{project_dir}/phases/.cutover-to-mode-3.json`:

   ```json
   {"timestamp": "<ISO>",
    "prior_mode": "v6-legacy",
    "new_mode": "mode-3",
    "prior_phase_pointer": "<current_phase>",
    "user_ack": "explicit-cutover-command",
    "note": "Mode-3 semantics apply from the next phase forward."}
   ```

5. Print confirmation + next-steps:

   ```
   Project <name> cut over to mode-3. The next /wicked-garden:crew:execute will use
   the phase-executor path. Prior phases retain their legacy bookends.
   ```

## Example

```
/wicked-garden:crew:cutover my-legacy-project --to=mode-3
# → Project my-legacy-project cut over to mode-3.

/wicked-garden:crew:cutover fresh-project --to=mode-3
# → Already on mode-3 (new projects default to mode-3).
```

## Safety Notes

- Cutover is irreversible in-session. To revert, manually edit ProjectState (not
  recommended).
- The `.cutover-to-mode-3.json` marker is an append-only audit artifact.
- Prior phase re-eval bookends are NOT backfilled. Mode-3 starts clean from the
  current phase.
