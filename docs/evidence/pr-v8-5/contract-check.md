# Contract Check — v8-PR-5 vs. 10 PR-1 Decisions

PR-1 established 10 foundational architectural decisions for the v8 daemon.
This document verifies PR-5 respects each one.

## Decision #1: Daemon-first, skills-thin

PR-5 status: **COMPLIANT**
- `acceptance_criteria.py` is a stdlib-only script (no HTTP calls).
- CLI (`main()`) is a thin client over `load_acs` / `link_evidence`.
- Daemon (`db.py`, `projector.py`) holds the authoritative projection.

## Decision #2: Bus is the source of truth

PR-5 status: **COMPLIANT**
- `acceptance_criteria` and `ac_evidence` tables are populated exclusively from
  `wicked.ac.declared` and `wicked.ac.evidence_linked` bus events.
- No HTTP write paths exist for these tables.
- `link_evidence()` in the script layer writes to the project filesystem JSON —
  this is the clarify-phase artifact store, not the daemon projection.

## Decision #3: Phase state machine with no dead-end states

PR-5 status: **NOT APPLICABLE**
- No new phase states introduced.
- AC verification is a check within the review phase, not a state transition.

## Decision #4: One canonical name per specialist

PR-5 status: **NOT APPLICABLE**
- No specialist dispatch changes.

## Decision #5: Council as first-class primitive

PR-5 status: **NOT APPLICABLE**
- Council (PR-4) can reference structured ACs via `list_acs()` in a future PR.
  PR-5 delivers the data model; council integration is a follow-up.

## Decision #6: Read-only principle (no HTTP write paths)

PR-5 status: **COMPLIANT** — this is the critical one.

The PR-4 carve-out allowed POST /council as the only HTTP write path.
PR-5 introduces TWO new DB tables but does NOT add HTTP write paths:

| Table                  | Write source           | HTTP write? |
|------------------------|------------------------|-------------|
| `acceptance_criteria`  | `wicked.ac.declared` event   | NO |
| `ac_evidence`          | `wicked.ac.evidence_linked` event | NO |

The `link_evidence()` function in `scripts/crew/acceptance_criteria.py` writes
to the filesystem JSON (`phases/clarify/acceptance-criteria.json`) — the same
layer as phase deliverables. It does NOT call the daemon's HTTP API.

Evidence for this:
- `daemon/projector.py::_ac_declared` — uses `db.upsert_ac()` only
- `daemon/projector.py::_ac_evidence_linked` — uses `db.add_ac_evidence()` only
- No new endpoints added to `daemon/server.py`

## Decision #7: ACs as structured assertions (THIS PR)

PR-5 status: **IMPLEMENTS**
- `AcceptanceCriterion` dataclass: `{id, statement, satisfied_by, verification}`
- `satisfied_by` holds references (file paths, test IDs, issue refs, check names)
- No fuzzy matching, no substring heuristics in the primary path

## Decision #8: Single scoped autonomy flag

PR-5 status: **NOT APPLICABLE**
- No gate policy changes.

## Decision #9: wicked-testing auto-engaged

PR-5 status: **NOT APPLICABLE**

## Decision #10: Live progress surface

PR-5 status: **FOUNDATION**
- `ac_coverage_summary()` returns counts usable by a dashboard/TUI.
- `list_acs()` + `get_ac_evidence()` provide the query surface.

## Summary

PR-5 complies with all 10 PR-1 decisions. The critical constraint (Decision #6,
read-only principle) is upheld: AC data reaches the daemon exclusively through
bus events, not HTTP writes.
