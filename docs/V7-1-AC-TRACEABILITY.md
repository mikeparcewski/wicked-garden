# v7.1 Acceptance Criteria Traceability

Crew project: `refactor-wicked-testing-cleanup-v7-1`. Scope: remove deprecated surfaces + deferred v7.0.1 items. Numbering here is independent of v7.0 (which lived in `docs/V7-AC-TRACEABILITY.md`).

## #558 AC-23 defense-in-depth facilitator check

- **AC-1** — `check_testability_gate()` exists — `scripts/crew/_prerequisites.py`; tests: `tests/crew/test_facilitator_wicked_testing_check.py`
- **AC-2** — missing probe key → fail-closed — same file; test: `test_facilitator_wicked_testing_check.py::test_probe_absent_raises`
- **AC-3** — structured error on missing wicked-testing — tests confirm actionable message

## #559 Scenario cleanup

- **AC-4** — `v7-0-missing-wicked-testing.md` targets `bootstrap.py` — verified in scenario file
- **AC-5** — `v7-0-reeval-backcompat.md` uses `--project-dir` flag — verified
- **AC-6** — `v7-0-cross-plugin-smoke.md` exclusion list widened — verified

## #551 agents/qe/ removal

- **AC-7** — `agents/qe/` deleted — `ls agents/qe/` returns not-found
- **AC-8** — zero `wicked-garden:qe:*` dispatch refs outside exempt list — verified by grep (exempt: CHANGELOG, MIGRATION-v7.md, test fixtures, scenario assertion files)
- **AC-9** — `scripts/qe/cli_discovery.py` deleted (CH-03 orphan cleanup) — verified

## #552 skills/qe/ + skills/acceptance-testing/ removal

- **AC-10** — `skills/qe/` deleted — verified
- **AC-11** — `skills/acceptance-testing/` deleted — verified
- **AC-12** — hook suggestions updated to `wicked-testing:*` Tier-1 skills — `hooks/scripts/bootstrap.py` + `post_tool.py`
- **AC-13** — `.claude-plugin/components.json` qe list cleared — verified

## #553 commands/qe/ removal

- **AC-14** — `commands/qe/` deleted (all 12 files) — verified
- **AC-15** — 4 non-aliased commands also deleted per design OQ-1 — verified
- **AC-16** — `/wicked-garden:help` Deprecated section removed — `commands/help.md`
- **AC-17** — `hooks/scripts/bootstrap.py` + `post_tool.py` suggestions use `wicked-testing:*` — verified
- **AC-18** — no orphan references post-deletion — verified by grep audit

## Backward-compat reader removal

- **AC-19** — `normalize_reviewer_name` deleted from `reeval_addendum.py` — verified
- **AC-20** — `_QE_EVALUATOR_TRIGGER_PREFIX` removed; `_REJECTED_LEGACY_TRIGGER_PREFIX` retained with clarifying comment — `validate_reeval_addendum.py`
- **AC-21** — `LegacyReviewerNameError` raised on legacy entries — `reeval_addendum.py`; tests: `test_reeval_addendum_schema.py`
- **AC-22** — SessionStart legacy-scan (CH-02) — `hooks/scripts/bootstrap.py::_scan_for_legacy_reeval_entries`; tests: `tests/crew/test_legacy_reeval_scan.py`

## CHANGELOG + version bump

- **AC-23** — `CHANGELOG.md` `[7.1.0]` entry present — verified
- **AC-24** — entry documents removals + AC-23 + scenario fixes + CH-01 404 pointer + migration guidance for v6.x upgraders — verified
- **AC-25** — pin policy unchanged at `^0.1.0` — `.claude-plugin/plugin.json`
- **AC-26** — `plugin.json:version == "7.1.0"` — verified; v7.0.0 tag retroactively applied at commit 0d3145d

## Invariants

- **AC-27** — test suite 1012+ passing via `uv run pytest tests/` — verified
- **AC-28** — grep audit clean (dispatch paths) — verified; scenarios/ legitimately retained as assertion fixtures
- **AC-29** — `/wg-check` passes — verified
- **AC-30** — `git revert` on v7.1 returns to v7.0 state; `v7.0.0` tag exists — verified

## User stories

- **US-1** — grace-period-ending user — covered by AC-14..AC-18 (removals complete) + AC-23/AC-24 (migration guidance in CHANGELOG)
- **US-2** — late-upgrader who skipped v7.0 migration — covered by AC-21 (LegacyReviewerNameError) + AC-22 (SessionStart scan) + AC-24 (CHANGELOG v6.x-direct guidance)
- **US-3** — plugin maintainer verifying no regressions — covered by AC-27..AC-30 invariants
- **US-4** — developer updating custom gate-policy.json — covered by AC-8 + AC-17 (no stale `wicked-garden:qe:*` references remain)
