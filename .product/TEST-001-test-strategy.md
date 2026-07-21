---
name: TEST-001-test-strategy
title: wicked-garden — Test Strategy
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# TEST-001 — Test Strategy

## Overview

wicked-garden's test strategy has four layers: unit tests for script-level logic, integration tests for multi-component flows, scenario tests for end-to-end capability acceptance, and an adversarial review layer for quality gates that structural tests cannot cover. The wicked-testing acceptance pipeline enforces structural separation between the agent that runs tests and the agent that evaluates them.

The core principle is consistent with the product's evidence-gate stance: a FAIL that surfaces a real bug is worth more than a PASS that masked it. PASS counts inflated by SKIPped scenarios are not coverage. MANUAL-ONLY is a distinct verdict from SKIP.

---

## Test Layers

### Layer 1 — Unit Tests (`tests/`)

Unit tests cover the imperative Python scripts under `scripts/` and `hooks/scripts/`. They run via pytest and do not require wicked-vault, wicked-loom, or any peer to be installed (peers are mocked or stubbed).

**Scope:**
- `tests/compiler/` — compiler output tests, including `test_compile.py` (AST-enforced stdlib-only check on emitted `gate.py`).
- `tests/crew/` — archetype detection tests: representative prompts for each of the 10 archetypes, multi-archetype detection, below-threshold filtering.
- `tests/hooks/` — hook script output format tests (JSON shape, `ok` field, `reason` field on block).
- `tests/qe/` — gate semantics tests: green path, fail-closed on loom absent, fail-closed on vault absent, attestation rejection on `env-user` actor.
- `tests/domain/` — DomainStore path resolution, SessionState isolation.
- `tests/agents/` — agent lift evaluation results (`EVAL_RESULTS.md`; documents which fork workers showed measurable lift vs. inline execution).

Run: `pytest tests/ -v`

**Testing rules (T1–T6):**
- T1 — Determinism: no test output depends on execution order.
- T2 — No sleep-based sync: tests do not `time.sleep()` to wait for async operations.
- T3 — Isolation: each test uses its own temp directory; no shared mutable state.
- T4 — Single assertion focus: each test asserts one behavior.
- T5 — Descriptive names: test names describe the scenario (`test_gate_fails_closed_when_loom_absent`).
- T6 — Provenance: tests that exercise evidence paths record evidence under explicit actor identities.

**CI trigger**: `test.yml` workflow, push and pull_request to `main`.

---

### Layer 2 — Integration Tests

Integration tests verify multi-component flows where the components interact for real (no mocking of the peer interface).

**Scope:**
- Gate integration: `vault_gate.py` shelling real `wicked-loom gate` → real `wicked-vault cross-check`. Requires both peers installed in CI.
- Compiler integration: `compile.py` against representative repo fixtures; verifies emitted files exist and emitted `gate.py` runs to completion.
- Hook integration: fires `UserPromptSubmit` event with test prompts; verifies system-reminder injection in the hook's output JSON.
- wicked-patch integration: applies a patch against a small synthetic repo using the codegraph fixture; verifies all expected files changed and no unexpected files changed.

**CI trigger**: `test.yml` workflow, push and pull_request to `main`. Integration tests that require live peers are skipped in environments where peers are not installed — CI installs wicked-vault and wicked-loom via npm for gate integration tests to run.

---

### Layer 3 — Scenario Tests (`scenarios/`)

Scenario tests are end-to-end acceptance tests structured around the product's intended behaviors. Each scenario is an executable assertion of intended behavior — not a unit test of a function, but a test of a complete capability flow.

**Structure:**
- `scenarios/{domain}/` — organized by domain or capability.
- Each scenario file declares: description, preconditions, steps, expected outcome, verification method.
- Scenarios are executed by the wicked-testing acceptance pipeline (not by pytest directly).

Run: `/wicked-testing:acceptance-testing scenarios/<scenario>.md`

**wicked-testing acceptance gate (the 3-agent pipeline):**
1. **Writer agent** (wicked-testing): reads the scenario and runs the steps against a real or simulated environment.
2. **Executor agent** (separate context): executes the steps mechanically and records outputs.
3. **Evaluator agent** (independent context, not the executor): reads the recorded outputs and the scenario expectations, renders a verdict (PASS / FAIL / MANUAL-ONLY / SKIP).

The evaluator is **not** the agent that ran the tests. This is structural, not conventional. An evaluator that is also the executor produces a self-graded result, which is not an acceptable quality signal.

**Verdict definitions:**
- **PASS**: all assertions met, all preconditions valid, verifier re-ran successfully.
- **FAIL**: at least one assertion failed. The finding is surfaced; the scenario is not SKIPped to maintain the PASS rate.
- **MANUAL-ONLY**: the scenario requires human judgment that an automated evaluator cannot provide. This is a distinct verdict — not a synonym for SKIP.
- **SKIP**: the scenario is legitimately out of scope for this run (e.g., a platform-specific scenario on an incompatible platform). Not used to paper over FAIL.

**Evidence recording**: the wicked-testing acceptance gate records its verdict as an EvidenceRecord in wicked-vault under `WICKED_VAULT_ACTOR`. The gate is re-derivable; a cached status is not accepted.

**CI trigger**: Not run in CI on every push. Scenario tests require the wicked-testing acceptance pipeline, which is a pre-release gate (see Pre-release gate section below), not a per-push CI trigger.

---

### Layer 4 — Adversarial Review

Adversarial review is not automated testing — it is an independent human or agent review of the work product, focused on finding what structural tests cannot. It is required before Level 3 DoD (marketplace ship). Findings are committed to `.product/reviews/`.

**Scope of adversarial review:**
- **Frontmatter accuracy**: does the skill description match the actual behavior? Could the harness pick up the wrong skill based on trigger overlap?
- **Refs content correctness**: are rubrics and playbooks accurate? Do they reflect the current implementation?
- **Gate semantics**: is there any path through the gate that produces a vacuous pass? Any self-assertion that bypasses loom?
- **Cross-platform paths**: are there any `/tmp` hardcodes, bare `python3` calls without fallback, or Windows-incompatible shell constructs?
- **Naming compliance**: do all skill names follow the naming convention? Do all bus events follow the 4-segment format?
- **Multi-archetype handling**: does the archetype detector handle multi-archetype prompts correctly?

**Who reviews**: the reviewer is not the author of the work under review. For in-house contributions, a second contributor reviews. For external contributions (vendor PRs), an in-house reviewer reviews — the PR is not auto-merged.

**Vendor contribution protocol**: a vendor PR that bundles legitimate skill rewrites with frontmatter regressions or hook changes is rejected as a bundle. Legitimate wins are salvaged in-house. This policy exists because `five legitimate rewrites + three regressions = net regression`.

**Findings**: all findings are recorded, not silently discarded. Each finding is either actioned (fixed in a follow-up commit) or accepted with documented rationale. A review with no findings documented is suspect.

---

## CI Workflow Structure

### `validate.yml` — structural validation (push and pull_request to `main`)

Runs two scripts:
1. `python scripts/ci/validate.py` — structural checks: Python syntax (`py_compile`), SKILL.md frontmatter validation, `components.json` sync, hook registration consistency, compiler AST check, cross-platform path checks, event name format.
2. `python scripts/_validate_registry.py` — in-code allowlist validation.

### `test.yml` — functional tests (push and pull_request to `main`)

1. Installs wicked peers globally: `npm i -g wicked-vault wicked-loom wicked-testing` (required for trust-spine E2E tests).
2. Unit + E2E tests: `python -m pytest tests/ -q` with `WICKED_REQUIRE_E2E=1` — the trust-spine tests (`tests/e2e/`) MUST run, not skip.
3. wicked-patch conformance: `python -m pytest scripts/engineering/patch/tests/test_conformance.py -q`.
4. Phase manager smoke: `phase_manager.py ci-smoke` create/status/delete round-trip.

Scenario tests (`scenarios/`) and the wicked-testing acceptance pipeline are **not** run in CI — they are a pre-release gate (see Pre-release gate section).

### Pre-release gate

Before `/wg-release --bump <level>`:
1. `/wg-check --full` green.
2. `test.yml` green on the release branch.
3. Scenario verdict PASS in wicked-vault (re-derivable, not cached). Evidence committed to `.product/evidence/`.
4. Adversarial review finding log present in `.product/reviews/`.

---

## What Is NOT Covered

- **LLM judgment quality** — archetype classification accuracy is bounded by the model; tests verify the scoring mechanism, not the model's classification ability.
- **Council seat availability** — external CLI availability (Antigravity, Codex, local models) is not tested in CI; degraded-council behavior (fewer participants) is tested.
- **Cross-harness behavior** — Claude Code is the primary tested harness; Cursor, Codex, OpenCode are validated manually on releases.

---

## Defect Triage

| Severity | Examples | Response |
|----------|---------|---------|
| Critical | Evidence gate fails open; emitted `gate.py` imports wicked-garden (stdlib violation); parent-context skill body > 35 lines | Block release; fix before merge |
| High | Archetype detector returns wrong archetype for high-confidence prompts; hook script crashes on Windows; attestation accepts `env-user` actor | Fix before next release |
| Medium | Council seat returns malformed verdict; codegraph absent degrades non-gracefully; `components.json` drift not caught by CI | Fix in current sprint |
| Low | Slow test; cosmetic skill description issue; stale refs content | Backlog |

---

## Coverage Philosophy

**What is measured**: scenario coverage by capability domain (archetype detection, evidence gate, compiler, wicked-patch, council, each of the 9 skill domains). Not line coverage — line coverage on skill Markdown files is meaningless.

**What is not measured as coverage**: SKIP verdicts. A scenario that is SKIPped does not contribute to coverage. If a capability cannot be tested automatically, the scenario is MANUAL-ONLY (requires human execution during release), not SKIP.

**Honest metrics**: a 70% real PASS rate on 10 scenarios beats a 95% inflated PASS rate on 20 scenarios where 5 are SKIP. The metric reported is real PASSes over non-MANUAL non-SKIP scenarios.
