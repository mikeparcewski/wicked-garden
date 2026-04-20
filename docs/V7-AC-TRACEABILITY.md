# v7.0 Acceptance Criteria Traceability

Crew project: `wicked-testing-extraction-v7-0`. This file provides AC-N ↔ implementation/test traceability per the semantic-alignment gate. See `/Users/michael.parcewski/.something-wicked/wicked-garden/projects/wicked-garden-9aec5ffd/wicked-crew/projects/wicked-testing-extraction-v7-0/phases/review/gap-report.md` for the human semantic review (43/47 aligned, 3 remediated inline, AC-23 deferred to v7.0.1).

## SessionStart hard-block

- **AC-1** — probe runs once per session — `scripts/_wicked_testing_probe.py::probe`; tests: `tests/test_wicked_testing_probe.py::test_probe_runs_once_per_session`
- **AC-2** — missing → block notice exact text — `hooks/scripts/bootstrap.py::_probe_wicked_testing`; tests: `tests/test_wicked_testing_probe.py::test_missing_emits_block_notice`
- **AC-3** — out-of-range → block — `scripts/_wicked_testing_probe.py::is_version_in_range`; tests: `tests/test_wicked_testing_probe.py::test_out_of_range_blocks`
- **AC-4** — crew:start/execute/gate refuse — `scripts/crew/_prerequisites.py::crew_command_gate`; tests: `tests/test_prerequisites.py::test_gate_refuses_when_missing`
- **AC-5** — `WG_SKIP_WICKED_TESTING_CHECK=1` escape hatch — `scripts/_wicked_testing_probe.py` + `tests/test_wicked_testing_probe.py::test_skip_env_bypasses_probe`
- **AC-6** — present+in-range → silent — `tests/test_wicked_testing_probe.py::test_happy_path_silent`

## Version pin

- **AC-7** — `plugin.json:wicked_testing_version` — `.claude-plugin/plugin.json`
- **AC-8** — marketplace.json description — `.claude-plugin/marketplace.json`
- **AC-9** — `/wg-check` semver validation — `.claude/commands/wg-check.md` §1
- **AC-10** — README pin-update policy — `README.md` Requirements subsection

## Docs as required peer plugin

- **AC-11** — README Requirements section — `README.md`
- **AC-12** — README Installation step — `README.md`
- **AC-13** — `/wicked-garden:setup` blocking install — `commands/setup.md` Step 2.5
- **AC-14** — Troubleshooting bullets — `README.md` Troubleshooting
- **AC-15** — no duplication, links upstream WICKED-GARDEN.md — `README.md` + `docs/MIGRATION-v7.md`

## gate-policy.json Tier-1 + polyglot

- **AC-16** — no `wicked-garden:qe:` in `.claude-plugin/gate-policy.json` — verified by grep
- **AC-17** — `gate-adjudicator` fully qualified — `.claude-plugin/gate-policy.json`
- **AC-18** — polyglot panel — `phases/design/polyglot-gate-policy.md`; tests: `tests/crew/test_wicked_testing_bus.py`
- **AC-19** — `/wg-check` Tier-1 allowlist — `scripts/_wicked_testing_tier1.py::validate_gate_policy`
- **AC-20** — crew smoke — `scenarios/crew/v7-0-cross-plugin-smoke.md`

## specialist.json routing

- **AC-21** — QE entries reference `wicked-testing:*` — `.claude-plugin/specialist.json`
- **AC-22** — facilitator testability-routing fidelity — `tests/crew/test_specialist_qe_tier1.py`
- **AC-23** — facilitator belt-and-suspenders check — **DEFERRED to v7.0.1**; see `docs/MIGRATION-v7.md` follow-up comment

## phase_manager dispatch + bus

- **AC-24** — no `wicked-garden:qe:` in dispatch — verified by grep
- **AC-25** — `_wicked_testing_bus.py` subscribes to `wicked.verdict.recorded` — `scripts/crew/_wicked_testing_bus.py`
- **AC-26** — verdict mapping PASS/FAIL/N-A/SKIP — `scripts/crew/_wicked_testing_bus.py`; tests: `tests/crew/test_wicked_testing_bus.py`
- **AC-27** — bus-absent fallback — `scripts/crew/gate_dispatch.py::_collect_bus_verdicts`; tests: `tests/crew/test_wicked_testing_bus.py::test_bus_absent_fallback`
- **AC-28** — unit tests cover (a)(b)(c)(d) — `tests/crew/test_wicked_testing_bus.py` (31 tests)
- **AC-29** — smoke bus-present/absent — `scenarios/crew/v7-0-polyglot-gate.md`

## Command alias layer

- **AC-30** — 8 shims with deprecation notice — `commands/qe/{qe,qe-plan,scenarios,automate,run,acceptance,qe-review,report}.md`
- **AC-31** — aliases refuse when wicked-testing missing — shim files invoke prerequisite gate
- **AC-32** — `/wicked-garden:help` Deprecated section — `commands/help.md`
- **AC-33** — v7.1 removal tracked by #551-#553 — `CHANGELOG.md` Deprecated section

## gate-adjudicator rename (#556)

- **AC-34** — 134 refs renamed across 17 files — verified by grep audit
- **AC-35** — 4 `git mv` renames (preserves history) — verified on commit
- **AC-36** — backward-compat reader (both names) — `scripts/crew/reeval_addendum.py::normalize_reviewer_name`; tests: `tests/crew/test_migrate_qe_evaluator_name.py`
- **AC-37** — refusal string updated — `agents/crew/gate-adjudicator.md` §Step 0
- **AC-38** — migration script idempotent + `.bak` — `scripts/crew/migrate_qe_evaluator_name.py`; tests: `tests/crew/test_migrate_qe_evaluator_name.py`
- **AC-39** — setup.py auto-invoke migration — `commands/setup.md` Step 2.6
- **AC-40** — `/wg-check` + integration test green — `tests/integration/test_gate_adjudicator_lifecycle.py`

## CHANGELOG + migration pointer

- **AC-41** — v7.0.0 entry with 11 items — `CHANGELOG.md`
- **AC-42** — Upgrading to v7.0 section — `README.md` + `docs/MIGRATION-v7.md`
- **AC-43** — `/wicked-garden:setup` references migration guide — `commands/setup.md` Step 2.5

## Tier-1 constraint

- **AC-44** — only 16 Tier-1 `wicked-testing:*` names referenced — `scripts/_wicked_testing_tier1.py::TIER1_ALLOWLIST`
- **AC-45** — no Tier-2 names as dispatch targets — verified by `/wg-check` rule

## Polyglot gate resolution

- **AC-46** — BLEND aggregation across namespaces — `scripts/crew/gate_dispatch.py::aggregate_blend`
- **AC-47** — dual verdict delivery paths (bus + dispatch) — `scripts/crew/_wicked_testing_bus.py` + `scripts/crew/gate_dispatch.py::collect`

## User stories (clarify artifact)

- **US-1** — user invoking `/wicked-garden:crew:start` with wicked-testing missing — covered by AC-1..AC-6
- **US-2** — plugin maintainer upgrading v6.x→v7.0 — covered by AC-34..AC-43
- **US-3** — wicked-testing contributor changing a Tier-1 agent — covered by AC-16..AC-20, AC-44
- **US-4** — QE reviewer emitting a verdict at a v7.0 gate — covered by AC-24..AC-29, AC-46, AC-47
