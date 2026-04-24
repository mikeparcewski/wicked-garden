# Council C1 / C2 Disposition — PR #613 Fix-up

## C1 (REQUIRED, addressed in this commit)

**Issue**: `daemon/projector.py::_rework_triggered` incremented `rework_iterations` but did not call `upsert_phase(state=PhaseState.ACTIVE)`. A phase stuck in REJECTED after a rework event could never advance — the `("rework", REJECTED) → ACTIVE` transition defined in `scripts/crew/phase_state.py::TRANSITIONS` was not being applied by the projector.

**Fix**: Added `upsert_phase(state=_STATE_ACTIVE)` call in `_rework_triggered` before the `rework_iterations` update. Two separate upserts keep the intent explicit and replay-safe: if the phase is already ACTIVE on replay, the COALESCE/upsert semantics are idempotent.

**Evidence**:
- `rework-bug-pre-fix.txt` — new parity test `test_rework_transitions_rejected_to_active` fails with `state='rejected'` before fix
- `rework-bug-post-fix.txt` — same test passes with `state='active'` after fix
- Updated `tests/daemon/fixtures/reject_then_rework/expected_phases.json` from `state='rejected'` to `state='active'` (the fixture was documenting the buggy behavior)

**Migration transaction wrap (also C1 scope)**:
`scripts/crew/phase_state_migration.py::run_migration` UPDATE loop wrapped in `with conn:` context manager. If any row UPDATE raises, the transaction rolls back atomically — the `_migrations` INSERT never commits, and re-running the migration resumes from scratch. Test: `TestMigrationRollbackOnRowError::test_migration_rollback_on_row_error`.

## C2 (DEFERRED — separate issue)

C2 (hardening) was explicitly out of scope for this fix-up per the council disposition. No C2 work was performed in this commit. A separate issue should be filed to track C2 hardening items.
