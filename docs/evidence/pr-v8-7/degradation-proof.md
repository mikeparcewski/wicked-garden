# Graceful Degradation Proof — wicked-testing Not Installed

**Issue #595 non-goal**: "If wicked-testing is not available, the dispatch logs a
warning and the phase proceeds with a flagged evidence gap."

## Scenario

A project enters the `test-strategy` phase. wicked-testing is not installed
(npx returns FileNotFoundError / non-zero exit).

## Worked Example

```python
# _is_wicked_testing_available() returns False
# (npx wicked-testing --version → error or not found)

record = dispatch_for_phase(
    conn=conn,
    project_id="my-project",
    phase="test-strategy",
    skill="wicked-testing:plan",
    autonomy_mode_str="full",
)
```

## What Happens

1. `_is_wicked_testing_available()` probes via `_wicked_testing_probe.probe()`
   (or shutil.which as fallback) — returns `False`

2. `logger.warning(...)` is emitted:
   ```
   WARNING daemon.test_dispatch: wicked-testing not available —
   recording skipped_unavailable for phase=test-strategy skill=wicked-testing:plan
   (evidence gap: no test evidence for this phase gate)
   ```

3. A `DispatchRecord` is written to `test_dispatches` with:
   - `verdict = "skipped_unavailable"`
   - `evidence_path = None`
   - `notes = "wicked-testing not installed or not accessible via npx. Phase proceeds
     with flagged evidence gap. Install wicked-testing to enable auto-dispatch."`

4. The phase PROCEEDS — no crash, no exception. The `skipped_unavailable` verdict
   is recorded as the evidence-gap signal. A gate reviewer querying
   `GET /test-dispatches?project_id=my-project` sees the flagged row.

5. The gate adjudicator receives the flagged evidence gap and can downgrade its
   verdict accordingly (CONDITIONAL vs APPROVE).

## Test Coverage

- `TestGracefulDegradation::test_unavailable_writes_skipped_unavailable`
- `TestGracefulDegradation::test_unavailable_emits_warning`
- `TestGracefulDegradation::test_unavailable_phase_proceeds_with_gap_flag`
- `TestGracefulDegradation::test_run_dispatches_degrades_gracefully_when_unavailable`

## Key Design Decision

The daemon never crashes on wicked-testing absence. This is enforced by:
- `_is_wicked_testing_available()` returns `bool` (never raises)
- `dispatch_for_phase()` has explicit degradation branch before subprocess
- `_invoke_skill()` catches all subprocess exceptions (R2 compliance)
