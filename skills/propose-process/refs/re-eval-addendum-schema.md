# Re-Evaluation Addendum JSONL Schema (D2, D8)

This file is the authoritative human-readable description of the re-eval addendum
format. The machine validator is `scripts/crew/validate_reeval_addendum.py`.

---

## Storage

Each phase writes to a single append-only file:

```
phases/{phase}/reeval-log.jsonl
```

Each line is one complete JSON object (one re-eval invocation). Lines are never
overwritten or deleted — this is an audit log. `validate_reeval_addendum.py`
validates each line independently.

---

## Required keys per record

| Key | Type | Description |
|-----|------|-------------|
| `chain_id` | string | Dotted chain ID (e.g. `"v6-reliable-autonomy.design"`) |
| `triggered_at` | string | ISO 8601 UTC (e.g. `"2026-04-18T17:30:00Z"`) |
| `trigger` | string | `"phase-end"` or `"task-completion"` |
| `prior_rigor_tier` | string | `"minimal"`, `"standard"`, or `"full"` |
| `new_rigor_tier` | string | `"minimal"`, `"standard"`, or `"full"` (may equal prior) |
| `mutations` | array | All mutations the re-eval proposed (see below) |
| `mutations_applied` | array | Subset of `mutations` that were auto-applied |
| `mutations_deferred` | array | Subset awaiting user confirmation (D7) |
| `validator_version` | string | Schema version (e.g. `"1.0.0"`) |

**Optional keys:**

| Key | Type | Description |
|-----|------|-------------|
| `factor_deltas` | object | Map of factor-name → `{old_reading, new_reading}` for changed factors only |

---

## Mutation object schema

Each item in `mutations`, `mutations_applied`, `mutations_deferred`:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `op` | string | yes | `"prune"`, `"augment"`, or `"re_tier"` |
| `task_id` | string | for prune + augment | Task ID affected |
| `new_rigor_tier` | string | for re_tier only | Target tier after mutation |
| `why` | string | yes | One-sentence required rationale |

---

## Subset constraint

`mutations_applied` and `mutations_deferred` must both be subsets of `mutations`.
`validate_reeval_addendum.py` enforces this via JSON-equality comparison.

---

## Real example record

Scenario: design phase ended, two factors disproven (compliance_scope moved
HIGH→LOW, state_complexity moved MEDIUM→LOW), rigor re-tiered from full to
standard, 1 task augmented, 1 task pruned.

```json
{"chain_id":"v6-reliable-autonomy.design","triggered_at":"2026-04-18T18:45:00Z","trigger":"phase-end","prior_rigor_tier":"full","new_rigor_tier":"standard","factor_deltas":{"compliance_scope":{"old_reading":"HIGH","new_reading":"LOW"},"state_complexity":{"old_reading":"MEDIUM","new_reading":"LOW"}},"mutations":[{"op":"re_tier","new_rigor_tier":"standard","why":"2 HIGH/MEDIUM factors disproven by design ADR; no factor moved up; tier was rubric-set not user-overridden"},{"op":"augment","task_id":"t5b","why":"Design ADR revealed need for schema migration script not in original plan"},{"op":"prune","task_id":"t4c","why":"ADR confirms auth scaffolding already exists in codebase; original premise invalidated"}],"mutations_applied":[{"op":"re_tier","new_rigor_tier":"standard","why":"2 HIGH/MEDIUM factors disproven by design ADR; no factor moved up; tier was rubric-set not user-overridden"},{"op":"augment","task_id":"t5b","why":"Design ADR revealed need for schema migration script not in original plan"},{"op":"prune","task_id":"t4c","why":"ADR confirms auth scaffolding already exists in codebase; original premise invalidated"}],"mutations_deferred":[],"validator_version":"1.0.0"}
```

---

## Validation

```bash
# Validate a JSONL file (all lines)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/validate_reeval_addendum.py" \
  phases/design/reeval-log.jsonl

# Validate a single record from stdin
echo '{"chain_id":"..."}' | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/validate_reeval_addendum.py" --stdin

# Run built-in self-test
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/validate_reeval_addendum.py" --selftest
```

Exit 0 = valid. Exit 1 = error message on stderr.

---

## How `phase_manager.py` reads the log

`_run_checkpoint_reanalysis` reads the last line of the JSONL file via the
Python equivalent of `tail -1` + `json.loads`. The `triggered_at` field from
the last record becomes the new `last_reeval_ts` stored in session state.

`approve_phase` calls `_check_addendum_freshness` which confirms that the last
record's `triggered_at` is newer than the phase's start timestamp. If not,
approve is blocked with "re-evaluation required" — unless `--skip-reeval --reason`
is passed, which writes an entry to `phases/{phase}/skip-reeval-log.json` for
retrospective audit at the `final-audit` gate.
