---
name: gate-benchmark-rebaseline
description: |
  Re-baseline procedure for the AC-11 gate-result benchmark lane
  (`tests/crew/test_gate_result_benchmark.py`). The benchmark enforces a
  2× p95 SLO on `gate-result.json` ingestion. When a deliberate perf change
  lands on main (validator hardening, cache tuning, schema expansion), the
  baseline needs updating. Never re-baseline to silence a regression.

  Use when: "re-baseline AC-11 benchmark", "gate-result benchmark regression",
  "p95 benchmark baseline out of date", "update benchmark_baseline.json",
  "benchmark.yml failure", "gate-result p95 exceeds 2x baseline",
  "rebaseline procedure", or `AC-11` baseline drift.
---

# Gate-Result Benchmark Re-baseline

Operational procedure for updating `tests/crew/benchmark_baseline.json` after a legitimate perf change on `main`.

## When to re-baseline

Re-baseline **only** when a deliberate perf change lands on `main`. Examples:

- Validator hardening (added / removed checks in `gate_result_schema.py`)
- Cache eviction tuning (changes to memoization in `phase_manager.py::_load_gate_result`)
- Schema expansion (new required fields in `gate-result.json`)
- Sanitizer pattern changes (`content_sanitizer.py`)

**Do not re-baseline to silence a regression.** If the benchmark fails on a PR that didn't intend perf work, treat it as a real regression and find the cause.

## How the lane works

- **Workflow**: `.github/workflows/benchmark.yml`
- **Trigger**: PRs touching `scripts/crew/phase_manager.py`, `gate_result_schema.py`, `content_sanitizer.py`, `dispatch_log.py`, or the benchmark test/baseline themselves. Other PRs skip the lane to keep default CI cost flat.
- **Test**: `tests/crew/test_gate_result_benchmark.py::test_load_gate_result_p95_within_2x_baseline`
- **Marker**: `benchmark` — opt-in. Local `uv run pytest` deselects it (see `pyproject.toml` `addopts = "-m 'not benchmark'"`).
- **Explicit invocation**: `uv run pytest -m benchmark`
- **Fixtures**: 50 deterministic `gate-result.json` files cycling through 1 KB / 4 KB / 16 KB / 60 KB (bounded by `MAX_SUMMARY_BYTES`). Each round clears the memoization cache so the full validate + sanitize + cache-insert path is measured. Cache-hit timing is **not** part of the SLO.
- **Baseline**: `tests/crew/benchmark_baseline.json` — `p95_ns` in nanoseconds.
- **Assertion**: `p95_current ≤ slo_multiplier × p95_baseline` (default `slo_multiplier = 2.0`). The workflow comments the delta on every triggered PR.
- **Missing-baseline behavior**: if `benchmark_baseline.json` is deleted or malformed, the test soft-skips with a directive to record one. The SLO is not enforced until a valid baseline is present — so a re-baseline PR can merge without a circular dependency.

## Re-baseline procedure

1. **Check out the target main commit.**

   ```bash
   git checkout main && git pull
   ```

2. **Run the benchmark three times.** The SLO is against p95, and CI noise varies — taking the highest of three local runs adds margin.

   ```bash
   uv run pytest -m benchmark tests/crew/test_gate_result_benchmark.py -s
   uv run pytest -m benchmark tests/crew/test_gate_result_benchmark.py -s
   uv run pytest -m benchmark tests/crew/test_gate_result_benchmark.py -s
   ```

3. **Record the highest `p95_current` reading** from the three runs.

4. **Update `tests/crew/benchmark_baseline.json`:**

   | Field | New value |
   |-------|-----------|
   | `p95_ns` | The highest `p95_current` from step 3, rounded **up** |
   | `recorded_on` | Today's date (`YYYY-MM-DD`) |
   | `recorded_from_commit` | Short SHA of the target main commit |
   | `slo_multiplier` | Leave at `2.0` unless the AC-11 contract changes |
   | `rebaseline_procedure` | Leave at `wicked-garden:platform:gate-benchmark-rebaseline` |

5. **Commit the baseline update in a dedicated PR.** Title convention:

   ```
   chore(benchmark): re-baseline AC-11 after {change-summary}
   ```

6. **The benchmark workflow runs on the PR and must pass** (p95 should be well under 2× the new baseline since you just measured it).

## Pre-flip dependency (semantic-gate condition)

Strict mode for gate-result ingestion (`WG_GATE_RESULT_STRICT_AFTER`, default `2026-06-18`) **requires** the AC-11 benchmark lane to be active in CI. Rationale: once strict-mode activates, a silent 2×+ perf regression would push every `approve_phase` call over the SLO without a guard.

If the benchmark lane is broken or disabled on `main`:

- **Before the flip date**: push `WG_GATE_RESULT_STRICT_AFTER` out (env var or default-constant update). Do not let strict-mode activate without benchmark enforcement.
- **After the flip date**: fix the benchmark lane before touching the ingestion path.

## Env-var rollback (preferred over revert)

For production rollback of a specific ingestion check, prefer env-var soft-disable over git-revert:

| Variable | Effect |
|----------|--------|
| `WG_GATE_RESULT_SCHEMA_VALIDATION=off` | Skip schema validator |
| `WG_GATE_RESULT_CONTENT_SANITIZATION=off` | Skip content sanitizer |
| `WG_GATE_RESULT_DISPATCH_CHECK=off` | Skip dispatch-log orphan check |

All flags auto-expire at `WG_GATE_RESULT_STRICT_AFTER`.

## References

- Test: `tests/crew/test_gate_result_benchmark.py`
- Baseline: `tests/crew/benchmark_baseline.json`
- Workflow: `.github/workflows/benchmark.yml`
- Ingestion path: `scripts/crew/phase_manager.py::_load_gate_result`
- Schema: `scripts/crew/gate_result_schema.py`
- Sanitizer: `scripts/crew/content_sanitizer.py`
- Dispatch log: `scripts/crew/dispatch_log.py`
