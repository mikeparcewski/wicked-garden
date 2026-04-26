# PR #657 Fix-up: Council Blocker Resolution

**PR**: https://github.com/mikeparcewski/wicked-garden/pull/657
**Branch**: fix/650-653-phase-manager-cluster
**Council verdict before fix-up**: 2-REJECT / 2-CONDITIONAL (HITL PAUSE)

## Changes Applied

### Fix 1 (iterdir first-match-wins → mtime sort)

`_sync_gate_finding_task` in `scripts/crew/phase_manager.py` previously
used `tasks_dir.iterdir()` and returned on the first matching task.
In rerun scenarios (phase REJECT'd then re-run), multiple gate-finding
tasks exist for the same phase/chain_id prefix.  Filesystem iteration
order is non-deterministic — the stale task could be picked, leaving the
active one in `in_progress` while the stale one gets incorrectly stamped
`completed`.

Fix: collect all matching in-progress gate-finding tasks into a list,
sort by `st_mtime` descending (one `stat()` call per matching file — cost
negligible), pick the most-recently-modified.  The 200-file bound is
preserved and now triggers a `logger.warning` when hit (see Fix 3).

### Fix 2 (min_score stamp on completed task)

`_event_schema.py` line 80 declares `required_at_completion`:
`["verdict", "min_score", "score"]`.  The original code only wrote
`verdict` and `score` — omitting `min_score` made every synced task
schema-invalid at completion.

Fix: extract `min_score` from `gate_result["min_score"]` (present in
both the in-memory merged result produced by `_blend_results` and in the
`_empty_verdict_stub`; absent in file-based `gate-result.json` loaded
from disk, in which case `min_score` stays `None` and is not written,
preserving prior behavior for callers that do not supply it).

### Fix 3 (log level: debug → warning on outer exception handler)

Changed the outer exception handler's `logger.debug` to `logger.warning`.
Fail-open + silent is the original bug's close cousin.  The bounded-scan
limit warning also uses `logger.warning` for the same reason.

## Test Evidence

Three new tests added to `TestSyncGateFindingTask` in
`tests/crew/test_phase_manager.py`:

| Test | Scenario |
|------|----------|
| `test_sync_rerun_picks_newest_task_by_mtime` | Two gate-finding tasks for same phase, stale (older mtime) + active (newer mtime). Sync stamps active; stale stays in_progress. |
| `test_sync_stamps_min_score_on_completed_task` | Single matching task. Completed metadata contains `min_score` with correct value. |
| `test_sync_warns_at_scan_limit` | 201 non-matching files exceeds 200-file bound. WARNING is emitted. |

## Test Results

```
Tests: 1699 passed / 11 pre-existing failures (unchanged)
New tests: +3 (all passing)
```

Pre-existing failures are unrelated (yolo stub content checks, bare-pass
audit) and present on the base branch before this fix-up.
