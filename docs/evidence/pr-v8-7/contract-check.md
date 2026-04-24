# Plugin Contract Check — v9 Drop-In Contract + PR-1 10 Decisions

## v9 Drop-In Plugin Contract (docs/v9/drop-in-plugin-contract.md)

| Rule | Status | Evidence |
|------|--------|----------|
| Don't duplicate wicked-testing value | PASS | No test logic in daemon/test_dispatch.py — dispatch-only |
| Dispatch via canonical skills | PASS | Uses wicked-testing:plan/authoring/execution/review |
| Honor verdict shape | PASS | verdict stored verbatim; no translation or recast |
| Plugin must degrade when peer absent | PASS | _is_wicked_testing_available() returns False gracefully |
| Don't modify peer plugin files | PASS | Zero changes to wicked-testing agents/skills/scripts |

## PR-1 Ten Decisions Compliance

### Decision #6 (daemon read-only for projection tables)

**Status**: RESPECTED with documented carve-out

All projection tables remain read-only:
- `projects` — read-only (not touched by test_dispatch.py)
- `phases` — read-only (read for phase list; not written)
- `tasks` — read-only (unchanged)
- `cursor` — read-only (unchanged)
- `event_log` — read-only (unchanged)
- `acceptance_criteria` — read-only (unchanged)
- `ac_evidence` — read-only (unchanged)

**Carve-out: `test_dispatches` table**

`test_dispatches` is NOT a projection table. The daemon *originates* these rows
when it decides to dispatch to wicked-testing — there is no bus event to project
from. This is the third explicit write path:

| Write path | PR | Table |
|------------|-----|-------|
| Event ingestion | PR-2 | event_log |
| Council orchestration | PR-4 | council_sessions, council_votes |
| Test dispatch | PR-7 | test_dispatches |

The carve-out is documented in three places:
1. `daemon/test_dispatch.py` module docstring — full rationale
2. `daemon/db.py` SQL comment at table creation
3. `daemon/server.py` handler docstring for POST /test-dispatch

### Decision #10 (bind to 127.0.0.1 by default)

**Status**: RESPECTED — new endpoints added to existing server; bind address unchanged.

## Coupling Assessment

**Assumed wicked-testing CLI interface**:
```
npx wicked-testing {plan|authoring|execution|review} --topic <project_id> --phase <phase>
stdout: optional "evidence: /path/to/evidence.json" line
exit 0: success
exit non-0: failure
```

This is a LOOSE contract. If wicked-testing changes its CLI interface:
- The `_SKILL_ARGV` dict in `daemon/test_dispatch.py` is the single point of change
- No other code needs to change
- The dispatch layer is intentionally thin — no argument interpretation

**Hidden coupling risk**: wicked-testing's `--version` probe format (the existing
`_wicked_testing_probe.py` dependency). This is pre-existing, not introduced by PR-7.
