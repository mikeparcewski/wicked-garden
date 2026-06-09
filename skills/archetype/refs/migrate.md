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

The cutover gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the rollback drill is re-run and the
shape-change post-condition re-checked, never trusting a self-asserted
"rolled back fine". This is the original evidence-vault use case — for a
migration the load-bearing honesty move is **no cutover without a
re-derivable rollback proof**. wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden:setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather than
self-asserting a PASS. Because `cutover` is a HARD gate, the gate also
demands an **independent attestation**: an evaluator who is **not** the
migrator confirms the rollback proof and shape change are adequate
(recorded via `wicked-vault:analyze-evidence`), and the gate fails closed
on a self-grade.

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
3. Declare the re-derivable contract early so the cutover gate has a bar
   to check against. If a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`):
   `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase migrate --spec contract.json`.
   `required_evidence` must pin both claim_ids:
   - `rollback-proof` → `exit_code_eq:0` on the rollback-drill command —
     the rollback was actually exercised and succeeded, not asserted.
   - `shape-change` → a deterministic post-condition: `exit_code_eq:0`
     on a migration-applied verification, or `jq_pred` over a captured
     schema-state JSON.
   Skip silently if no vault.
4. **If the shape change is reversible HIGH (e.g. a column add), this
   archetype is overkill.** Drop back to `build`.

### expand

1. Add the new shape alongside the old. **Both must work.**
2. New writes go to BOTH shapes (dual-write). New reads still come from
   the old shape.
3. Land + deploy expand. Don't combine with backfill.
4. Record the **shape-change** as re-derivable evidence (vault present):
   `wicked-vault record --scope <scope> --phase migrate --claim shape-change
   --kind schema-state --source "<migration-applied verification>"
   --criteria "<the post-condition>" --verifier exit_code_eq:0 --run`. The
   `--run` captures the real exit code now and the gate re-runs it later —
   a claim you can't re-derive is not evidence.

### backfill

1. Populate the new shape from the old. The backfill must be
   **idempotent** — a half-completed backfill that gets restarted
   should converge to the same end state as a clean run.
2. Run in batches; rate-limit against the production DB.
3. Verify completeness: the row count + checksum + spot-check sample
   match the old shape.
4. **Exercise the rollback drill and record it as re-derivable evidence —
   this must exist and re-derive BEFORE cutover** (vault present):
   `wicked-vault record --scope <scope> --phase migrate --claim rollback-proof
   --kind rollback-drill --source "<the rollback-drill command>"
   --criteria "rollback exercised and succeeded" --verifier exit_code_eq:0 --run`.
   The `--run` captures the drill's real exit code now; the gate re-runs
   it at cutover. A rollback path you can't re-derive is not a rollback
   path. No vault → fall back to `evidence_tracker.py claim`.

### cutover

1. **Pre-cutover checklist**:
   - Rollback path executed in staging. (`✓` or block.)
   - Backfill complete + verified.
   - Dual-write running cleanly for at least 24h.
   - Monitoring + alerts updated to surface new shape's anomalies.
2. **Gate before any switch** — don't self-assert the checklist. Run the
   produces-gate WITH judgment:
   `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase migrate --with-attestations`
   (exit 0 = satisfied). This re-derives the rollback drill and the
   shape-change post-condition over the declared contract, and requires
   the independent attestation (evaluator ≠ migrator, via
   `wicked-vault:analyze-evidence`). A REJECT means the rollback proof or
   shape change doesn't clear its contract — fix the work, not the claim.
   An `unavailable` verdict means the required vault isn't installed — run
   `/wicked-garden:setup`. **No cutover on a fail-closed verdict.**
3. **Cutover staged**: switch readers first, watch for 1h, then switch
   writers. Don't switch both at once.
4. The cutover gate is HARD — explicit user "go" before each switch.
5. If anything looks off post-cutover: **rollback first, debug second.**

### contract

1. Wait for cutover to soak (24–72h, longer for data shape).
2. Stop the dual-write. Only the new shape is being written.
3. After another soak, drop the old shape.
4. Land the contract change with a docs update — the migration is now
   complete.

## When to stop

Cutover may only proceed when the produces-gate is satisfied — check it,
don't self-assert it:
`scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase migrate --with-attestations`
(exit 0 = satisfied). This is a re-derived PASS over the declared contract
plus the independent attestation; a missing vault is `gate: "unavailable"`
/ `satisfied: false`, never a claim-only pass.

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
