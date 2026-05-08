# migrate — expand / backfill / cutover / contract

For shape changes that require both forward and rollback proof. Schema
migrations, data backfills, breaking API rollouts. Uses the standard
**expand-contract** pattern: add the new shape, make both work, switch
readers, switch writers, remove the old shape.

## Phase shape

| Phase    | Goal                                                  |
|----------|-------------------------------------------------------|
| plan     | Document the shape change. Define rollback contract.  |
| expand   | Add the new shape. **Do not remove the old shape.**   |
| backfill | Populate the new shape from the old. Idempotent.      |
| cutover  | Switch readers/writers. **Hard gate** — staged.       |
| contract | Remove the old shape. Only after cutover has soaked.  |

## Produces

- **Shape change**: the new schema / API / data layout.
- **Rollback proof**: an executable rollback path. Tested in staging
  before cutover.

## HITL

`hard:cutover-gate` — cutover is a hard gate. Don't cutover without
explicit user approval AND a green pre-cutover checklist (rollback
tested, backfill complete, dual-read working).

## How to run

### plan

1. Document the shape change at `docs/migrations/{N}-{slug}.md`. The
   doc names:
   - The OLD shape, the NEW shape.
   - The rollback contract: how to undo, who pulls the trigger, how
     long the rollback window is.
   - The expand-contract phase boundaries: when each step happens.
2. Use `wicked-garden:engineering:migration-engineer` for the canonical
   playbook.
3. **If the shape change is reversible HIGH (e.g. a column add), this
   archetype is overkill.** Drop back to `build`.

### expand

1. Add the new shape alongside the old. **Both must work.**
2. New writes go to BOTH shapes (dual-write). New reads still come from
   the old shape.
3. Land + deploy expand. Don't combine with backfill.

### backfill

1. Populate the new shape from the old. The backfill must be
   **idempotent** — a half-completed backfill that gets restarted
   should converge to the same end state as a clean run.
2. Run in batches; rate-limit against the production DB.
3. Verify completeness: the row count + checksum + spot-check sample
   match the old shape.

### cutover

1. **Pre-cutover checklist**:
   - Rollback path executed in staging. (`✓` or block.)
   - Backfill complete + verified.
   - Dual-write running cleanly for at least 24h.
   - Monitoring + alerts updated to surface new shape's anomalies.
2. **Cutover staged**: switch readers first, watch for 1h, then switch
   writers. Don't switch both at once.
3. The cutover gate is HARD — explicit user "go" before each switch.
4. If anything looks off post-cutover: **rollback first, debug second.**

### contract

1. Wait for cutover to soak (24–72h, longer for data shape).
2. Stop the dual-write. Only the new shape is being written.
3. After another soak, drop the old shape.
4. Land the contract change with a docs update — the migration is now
   complete.

## When to stop

Migrate is done when the old shape is removed AND the contract phase
has soaked. Hand off to `review` for a post-migration audit when the
change touched compliance or revenue surface.

## Anti-patterns

- **Don't combine expand with backfill.** Each phase is a separate
  ship. Combining them removes the ability to roll back to a clean
  intermediate state.
- **Don't switch readers and writers simultaneously.** Stage them.
- **Don't contract before soaking.** "We've cutover; let's clean up
  the old shape" is how you discover at 3am that one consumer never
  switched.
- **Don't skip rollback testing.** A rollback path you haven't
  exercised is not a rollback path.
