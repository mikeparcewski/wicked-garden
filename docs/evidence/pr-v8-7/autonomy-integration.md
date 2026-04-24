# Autonomy-Mode Integration — Worked Examples

**Issue #595 Stream 5**: Uses PR-6's autonomy module.

## Mode: `ask`

**Behavior**: Log intent, return `deferred_ask`, do NOT invoke subprocess.

```python
record = dispatch_for_phase(
    conn=conn,
    project_id="my-project",
    phase="test-strategy",
    skill="wicked-testing:plan",
    autonomy_mode_str="ask",
)
```

**Result**:
- `subprocess.run` is NOT called
- `record.verdict == "deferred_ask"`
- `record.notes` contains "ask mode" and "confirmation" — explains what would have fired
- Test: `TestAutonomyIntegration::test_ask_mode_defers_dispatch`
- Test: `TestAutonomyIntegration::test_ask_mode_notes_explain_deferral`

**Why**: `ask` mode = conservative default. The facilitator announces the dispatch
intent in the notes field so the user can explicitly confirm before it fires.

## Mode: `balanced`

**Behavior**: Test dispatch is non-blocking in `auto` env (evidence gathering is not
an irreversible action). Respects `WG_HITL_TEST_DISPATCH` env override.

```python
record = dispatch_for_phase(
    conn=conn,
    project_id="my-project",
    phase="test-strategy",
    skill="wicked-testing:plan",
    autonomy_mode_str="balanced",
)
# WG_HITL_TEST_DISPATCH not set → defaults to "auto" → proceed
```

**Result**:
- `subprocess.run` IS called (wicked-testing:plan invoked)
- `record.verdict == "ok"` (or "error" if subprocess fails)

**Override behaviors**:
- `WG_HITL_TEST_DISPATCH=pause` → deferred_ask (even in balanced mode)
- `WG_HITL_TEST_DISPATCH=off`  → proceed (same as full)

**Tests**:
- `TestAutonomyIntegration::test_balanced_mode_auto_dispatches_for_test_dispatch`
- `TestAutonomyIntegration::test_balanced_mode_env_override_pause`
- `TestAutonomyIntegration::test_balanced_mode_env_override_off_dispatches`

## Mode: `full`

**Behavior**: Auto-dispatch without pause. Subprocess is invoked immediately.

```python
record = dispatch_for_phase(
    conn=conn,
    project_id="my-project",
    phase="test-strategy",
    skill="wicked-testing:plan",
    autonomy_mode_str="full",
)
```

**Result**:
- `subprocess.run` IS called (wicked-testing:plan invoked)
- `record.verdict == "ok"` (or "error" if subprocess fails)
- Evidence path extracted from stdout if wicked-testing emits `evidence: /path`

**Test**: `TestAutonomyIntegration::test_full_mode_auto_dispatches`

## Implementation Note

The autonomy check in `_should_pause_test_dispatch()` imports `crew.autonomy` lazily
(graceful degradation if crew scripts are not on sys.path). The fallback behavior is
conservative (pause=True) to avoid unintentional auto-dispatch.
