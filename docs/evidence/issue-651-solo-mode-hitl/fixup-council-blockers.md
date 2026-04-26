# Fix-up Evidence: PR #662 Council Blockers

**PR**: https://github.com/mikeparcewski/wicked-garden/pull/662
**Date**: 2026-04-25
**Council verdict before fix-up**: 4-0 unanimous CONDITIONAL — 3 blockers

---

## Blocker 1: Mid-project rigor bypass (CRITICAL) — FIXED

**Root cause**: `_dispatch_human_inline` in `scripts/crew/phase_manager.py` delegated
directly to `solo_mode.dispatch_human_inline` without first checking the live
`rigor_tier` from state. If a project started `standard` + `solo_mode=true` and a
checkpoint re-evaluation upgraded rigor to `full`, the next gate dispatch still ran
inline, violating the "full-rigor always uses council" invariant.

**Fix** (`scripts/crew/phase_manager.py`, `_dispatch_human_inline`):
Added a live rigor check at the top of the function, before the `solo_mode` import.
When `state.extras["rigor_tier"] == "full"`:
- Falls back to `_dispatch_council` with the same reviewers from `gate_policy_entry`
- Annotates result with `original_mode: "human-inline"` and `mode_fallback_reason: "rigor-upgraded-to-full"`
- Logs a WARNING (not silent)

**New test class**: `TestDispatchHumanInlineRigorUpgradeFallback`
- `test_full_rigor_at_dispatch_falls_back_to_council`: verifies council is called once,
  result carries both annotation fields with correct values
- `test_standard_rigor_does_not_trigger_council_fallback`: verifies standard rigor takes
  the normal interactive path (council NOT called)
- `test_no_state_does_not_trigger_council_fallback`: verifies `state=None` defaults to
  standard (no false bypass)

---

## Blocker 2: Vacuous CONDITIONAL gate (HIGH) — FIXED

**Root cause**: `_parse_human_response` in `scripts/crew/solo_mode.py` accepted bare
`CONDITIONAL` (no colon, no text) and `CONDITIONAL:` (colon with no following text),
producing `conditions_text = ""`. `_write_conditions_manifest` fell through to the
`or "(no conditions text provided)"` default, creating a pending condition with no
actionable content. AC-4.4 auto-resolution in the next phase could auto-satisfy this
(treating it as APPROVE) or stall indefinitely.

**Fix** (`scripts/crew/solo_mode.py`, `_parse_human_response`):
- If `CONDITIONAL` has no colon: return `None` (trigger re-prompt)
- If `CONDITIONAL:` has empty text after the colon: return `None` (trigger re-prompt)
- Both cases now behave identically to fully ambiguous input

The `_write_conditions_manifest` fallback `or "(no conditions text provided)"` is now
dead code for the inline-review path (but kept as a defensive last resort for the
max-reprompt fallback which sets an explicit non-empty `conditions_text`).

**New test class**: `TestBareConditionalReprompts`
- `test_bare_conditional_no_colon_triggers_reprompt`: bare `CONDITIONAL` → re-prompt fires,
  second `APPROVE` accepted
- `test_bare_conditional_with_colon_but_no_text_triggers_reprompt`: `CONDITIONAL:` → same
- `test_bare_conditional_twice_defaults_to_conditional_with_text`: after max reprompts the
  fallback CONDITIONAL manifest description is non-empty and does not contain the
  vacuous placeholder
- `test_conditional_with_text_still_accepted`: `CONDITIONAL: <text>` still parses correctly

---

## Blocker 3: Orphan-check test invalid (MEDIUM) — FIXED

**Root cause**: `test_orphan_check_passes_with_prior_dispatch_entry` set
`WG_GATE_RESULT_DISPATCH_CHECK=off`, which caused `check_orphan` to return at line 460
(the first line of the function body) before reading any entries. The test asserted a
positive outcome but exercised nothing about the orphan-check path it claimed to cover.

**Fix** (`tests/crew/test_solo_mode_hitl.py`):
Removed the `patch.dict(os.environ, {"WG_GATE_RESULT_DISPATCH_CHECK": "off"})` override.
Added `set_hmac_secret(test_secret)` / `set_hmac_secret(None)` around the test body to
pin a deterministic HMAC secret (avoiding SessionState I/O while ensuring `append` and
`check_orphan` share the same secret). The test now exercises the real matching path:
- `append` writes a signed dispatch-log entry
- `check_orphan` reads entries, finds the matching (reviewer, phase, gate, dispatched_at)
  record, HMAC-verifies it successfully, and returns without raising

**No deeper issue found**: the orphan-check path was working correctly; only the test was
masking it with the env override.

---

## Test results

```
tests/crew/test_solo_mode_hitl.py: 46 passed (was 39)
Full suite (tests/):               1748 passed / 5 pre-existing failures / 3 deselected
Pre-existing failures (unchanged):
  - test_command_aliases.py::TestCrewYoloAliasStub (3 tests)
  - test_command_cross_links.py::TestCrewAliasRedirect::test_yolo_mentions_auto_approve
  - test_stub_audit.py::TestStubAudit::test_no_bare_pass_in_scripts_overall
```

---

## Files changed

- `scripts/crew/phase_manager.py` — blocker 1: rigor guard in `_dispatch_human_inline`
- `scripts/crew/solo_mode.py` — blocker 2: tighten `_parse_human_response` CONDITIONAL branch
- `tests/crew/test_solo_mode_hitl.py` — blocker 3: remove env override; add 7 new tests
