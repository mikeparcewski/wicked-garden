# Issue #660 — Late Bot Review Findings — Fix Evidence

Generated: 2026-04-25

## Branch

fix/660-v8.2-late-bot-findings (from 5b56202 v8.3.0)

## Fixes Applied

### P1 — Substantive Bugs

**Fix 1 (PR #657): _sync_gate_finding_task closes tasks when gate_result is None**
- File: scripts/crew/phase_manager.py
- Change: Early return guard at top of _sync_gate_finding_task when gate_result is None.
  --override-gate path and non-gated phases no longer close pending gate-finding tasks.
- New test: test_sync_gate_result_none_does_not_close_pending_task
  (tests/crew/test_phase_manager.py)

**Fix 2 (PR #654): required_deliverables shape mismatch in phase-executor**
- File: agents/crew/phase-executor.md
- Change: Pseudocode updated to read d["file"] and d["min_bytes"] (actual phases.json keys)
  instead of wrong d["name"] and d["min_size"]. Backward-compat retained for legacy
  bare-string entries. Halt reason unified: deliverable-too-small renamed to
  executor-deliverable-too-small for consistent executor- prefix.
- Schema verified: phases.json uses {"file": ..., "min_bytes": ..., "frontmatter": [...]}
- New test: test_phase_spec_required_deliverables_keys_match_executor_pseudocode
  (tests/crew/test_phase_spec.py)

**Fix 3 (PR #658): telemetry happy-path reports tasks_observed: 0**
- File: scripts/delivery/telemetry.py
- Change: sample_window field renamed task_files_scanned → tasks_observed and now
  uses len(tasks) instead of len(task_files). len(task_files) was always 0 on the
  daemon-routed happy path, making the metric meaningless for daemon sessions.
- New test: test_tasks_observed_reflects_task_count_not_file_count
  (tests/delivery/test_telemetry.py)

### P3 — Cleanup

**Fix 4 (PR #659): pre-sweep audit log corruption**
- File: docs/evidence/issue-644-pii-sweep-v2/pre-sweep-FULL-grep.txt
- Changes:
  - Line 50: restored [^/]+ (was corrupted to ~/]+ by the sed pattern matching itself)
  - Lines 67-83: restored after-grep-old-surfaces.txt entries (17 lines of file paths
    collapsed to bare "." by the \. pattern)
  - Lines 88-103: restored before-grep-old-surfaces.txt entries (16 lines similarly
    collapsed)
- Method: re-grepped actual source files (which were not corrupted, only the audit log was)

### P4 — Polish

**Fix 5 (PR #646): test naming and comment accuracy**
- File: tests/crew/test_factor_questionnaire.py
- Changes:
  - Block comment updated to list all 6 test functions by exact name (was vague "two pin tests")
  - test_operational_risk_o5_weight_is_two: added docstring note documenting it as an
    intentional implementation pin (not behavior-coupled by accident)
  - test_operational_risk_o5_with_feature_flag_is_high: renamed to
    test_operational_risk_all_no_answers_is_high with clarified docstring. The old name
    implied o5=YES-with-flag; the body uses all-NO (safe/gated state).

**Fix 6 (PR #657): st_mtime equality flake risk in test_phase_manager.py**
- File: tests/crew/test_phase_manager.py
- Changes:
  - test_sync_skips_already_completed_tasks: replaced st_mtime equality with JSON content
    comparison (read file, compare dict equality)
  - test_sync_no_op_when_no_matching_task: same replacement

## Test Results

Baseline: 1748 pass / 5 pre-existing failures
After fixes: 1751 pass / 5 pre-existing failures
New tests added: 3

Pre-existing failures (unchanged):
- tests/test_command_aliases.py::TestCrewYoloAliasStub::test_yolo_md_exists
- tests/test_command_aliases.py::TestCrewYoloAliasStub::test_yolo_md_is_short_stub
- tests/test_command_aliases.py::TestCrewYoloAliasStub::test_yolo_stub_references_auto_approve
- tests/test_command_cross_links.py::TestCrewAliasRedirect::test_yolo_mentions_auto_approve
- tests/test_stub_audit.py::TestStubAudit::test_no_bare_pass_in_scripts_overall

## Schema Verification (Fix 2)

Verified phases.json required_deliverables shape before applying fix:
  ideate: [{"file": "brainstorm-summary.md", "min_bytes": 100, "frontmatter": []}]
  clarify: [{"file": "objective.md", ...}, {"file": "complexity.md", ...}, ...]
  design: [{"file": "architecture.md", "min_bytes": 200, ...}]

Keys are "file" and "min_bytes" — NOT "name" and "min_size" as the issue description
stated. Fix applied using correct keys from actual schema. Issue description's
suggested key names (name/min_size) were wrong; the actual schema was verified before
patching.
