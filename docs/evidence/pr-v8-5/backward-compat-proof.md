# Backward Compatibility Proof — v8-PR-5

## Claim

Projects WITHOUT `acceptance-criteria.json` still verify via the canonical-token
fallback. No regression in existing projects mid-flight.

## How it works

`check_acceptance_criteria` checks for `phases/clarify/acceptance-criteria.json`:

```python
json_path = phases_dir / "clarify" / "acceptance-criteria.json"
if json_path.is_file():
    return _check_acs_structured(name, phases_dir, json_path)  # PRIMARY
return _check_acs_canonical_tokens(name, phases_dir)           # FALLBACK
```

When the JSON does not exist, `_check_acs_canonical_tokens` runs — this is
exactly the #598 implementation: canonical-token regex + set membership lookup.

## Test verification

```python
# TestBackwardCompatFallback::test_no_json_falls_back_to_canonical
# phases/clarify/ac.md: "- **AC-3**: User can log in"
# phases/build/impl.md: "Implements AC-3 login flow."
# result.status == "PASS"  ✓

# TestBackwardCompatFallback::test_fallback_source_label_is_canonical_token
# result.evidence contains "canonical-token"  ✓

# TestBackwardCompatFallback::test_fallback_unlinked_still_fails
# AC-3 in clarify, no AC-3 in deliverable → FAIL  ✓
```

All three pass without `acceptance-criteria.json` present.

## What does NOT change for existing projects

- All #598 tests (separator normalisation, parent-id fallback, 80% threshold, AC-3/AC-30
  distinctness) continue to pass — verified by `TestNormalisedMatch`, `TestParentIdFallbackLogic`,
  `TestCoverageThreshold`, `TestDataShapeMatching`.
- The fallback path is reached automatically when JSON is absent.
- No CLI flag, no configuration change required for existing projects.

## Migration path for new projects

When `load_acs()` is first called on a prose-only project:
1. Clarify markdown is parsed → structured records written to JSON.
2. Subsequent calls to `check_acceptance_criteria` use the primary path.
3. `satisfied_by` starts empty — build-phase artifact linking populates it.

This is automatic and transparent — no user action required.
