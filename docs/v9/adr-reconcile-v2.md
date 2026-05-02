# ADR: Post-cutover reconciler — `reconcile_v2.py` co-existence

**Status**: Accepted (subject to Site 3 implementation feedback)
**Date**: 2026-05-02
**Decided by**: Pre-Site-3 design jam on issue #750
**Supersedes**: nothing
**Superseded by**: nothing

## Context

`scripts/crew/reconcile.py` is today's drift detector. It compares two
on-disk stores — the wicked-crew `process-plan.json` tree and the native
`tasks/` session tree — and reports drift classes (`missing_native`,
`stale_status`, `orphan_native`, `phase_drift`). It is a **store-vs-store**
comparison.

The bus cutover (#746) inverts this. After Site 3 lands the
`reviewer-report.md` cutover, the `wicked.gate.decided` event becomes the
source of truth and the on-disk artifacts become *projections* of those
events (per `docs/v9/bus-cutover-staging-plan.md` §5). The drift question
shifts from "do the two stores agree?" to "does every event have its
projection, and does every projection trace to an event?" That is a
**projection-vs-event** comparison — a fundamentally different shape.

The staging plan §5 spells out the new JSON output schema and the three
post-cutover drift classes (`projection-stale`, `event-without-projection`,
`projection-without-event`). It does NOT pin the Python entry-point
contract, which leaves Site 3's implementer guessing at:

- whether to grow `reconcile.py` with a `--post-cutover` flag, or ship a
  new module
- what `reconcile_all()` should return when the projector DB is missing
- how the test suite should select between v1 and v2 detectors during
  the cutover window when both must keep working

The pre-merge council on PR #749 (synthetic-drift suite) deferred this
decision to the Site 3 PR by filing #750. The pre-Site-3 design jam on
#750 reopened it because Site 3 cannot start without an answer.

## Options considered

- **(a) Extend `reconcile.py` with a `--post-cutover` flag.** REJECTED.
  The two reconcilers compare different things — one walks the tasks
  store, the other walks the projector DB. Sharing a module would force
  every detector function to grow `if cutover_complete:` branches that
  ossify under test. The cutover window is finite (~5 releases); the
  flag would outlive its purpose.
- **(b) New module `scripts/crew/reconcile_v2.py` co-existing during
  the cutover window. v1 deprecated when Site 5 lands; removed in
  release N+5.** ACCEPTED.
- **(c) Replace `reconcile.py` in place at Site 3.** REJECTED. The
  staging plan keeps Sites 1-4 running with v1 detectors live (Sites
  4-5 still hold pre-cutover artifacts). A rollback at any of those
  sites would have to re-implement v1 from git history, which is the
  exact "no rollback path" foot-gun the staging plan was written to
  avoid.

## Decision

Ship `scripts/crew/reconcile_v2.py` alongside `scripts/crew/reconcile.py`.
Both run during the cutover window; tests can import either explicitly.
v1 is deprecated when Site 5 lands and removed in release N+5 (one full
release at the new shape under flag-default-on, mirroring the JSON
schema bump in staging plan §5 lines 515-519).

## API contract (subject to Site 3 implementer pushback)

```python
def reconcile_all(daemon_db_path: Path | str | None = None) -> List[dict]:
    """Returns the post-cutover drift report per staging plan §5 schema.

    Result list shape:
        [
          {
            "project_slug": "...",
            "events_for_project": int,
            "projections_materialized": {...},
            "drift": [
              {"type": "projection-stale", ...},
              {"type": "event-without-projection", ...},
              {"type": "projection-without-event", ...}
            ],
            "summary": {...}
          },
          ...
        ]

    Empty list when daemon_db_path is None or projector DB unavailable —
    NEVER raises. Caller distinguishes "no projects" from "couldn't read"
    by inspecting the per-project entries (an empty top-level list means
    the projector was unreachable; a list with entries means projects
    were scanned and zero drifted).
    """
```

CLI surface:

- `--all` and `--project <slug>` flags supported (mirror v1 surface so
  existing operator muscle-memory transfers)
- `--post-cutover` flag NOT introduced (separate module instead — see
  Decision)
- `--json` output schema bumps a major version per staging plan §5 line
  516; v1's `--json` schema stays untouched until v1 is removed

## Consequences

- Tests can import `reconcile` (v1) or `reconcile_v2` explicitly — no
  `if cutover_complete:` branches in production OR test code
- Site 5's deprecation PR is a clean module removal, not an in-place
  refactor with mixed-shape diffs
- The synthetic-drift suite's three post-cutover test classes
  (`ProjectionStaleTests`, `EventWithoutProjectionTests`,
  `ProjectionWithoutEventTests`) will import `reconcile_v2` once Site
  3 ships it; until then they assert fixture state only (the deferral
  documented in #750)
- Until Site 3 lands `reconcile_v2`, the meta-test in
  `tests/crew/test_synthetic_drift.py::TestPostCutoverContract` treats
  the import of `reconcile_v2` as the contract; the test passes
  trivially today and tightens automatically the moment the module is
  importable

## Honest caveats

- The `reconcile_all()` signature above is a **strong default**, NOT a
  contract. The Site 3 implementer can push back — the post-cutover
  detector logic may want different ergonomics (e.g. a streaming
  iterator instead of a list, or a `Result[T, E]` shape instead of
  empty-list-as-unavailable). Pushback is normal; this ADR exists to
  give Site 3 a target, not to lock it in.
- Treating the empty list as the "projector unavailable" signal is one
  option. Raising a typed exception (`ProjectorUnavailable`) might be
  cleaner. Decide at Site 3 with concrete usage data.
- The deprecation window (release N+5) is calibrated to the staging
  plan's existing schedule — if Site 3-5 slips, the window slips with
  it. Re-baseline at Site 5 implementation.

## References

- Issue #750 (this ADR's home — defers detector assertions to Site 3)
- Issue #746 (the umbrella step-3 cutover this enables)
- Issue #749 (the synthetic-drift suite that surfaces the gap)
- `docs/v9/bus-cutover-staging-plan.md` §5 (the JSON schema this ADR
  provides a Python wrapping for)
- `scripts/crew/reconcile.py` (the v1 module this ADR co-exists with)
- `scripts/crew/synthetic_drift.py` (the fixture builder; see
  `_DAEMON_DB_BEARING` for the canonical post-cutover class set)
- Pre-Site-3 design jam on #750 (the conversation this decision came
  out of)
