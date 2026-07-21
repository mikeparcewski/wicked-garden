---
name: REQ-005-dod-criteria
title: wicked-garden — Definition of Done Criteria
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-005 — Definition of Done Criteria

Three levels of done apply to wicked-garden. Level 1 is structural correctness. Level 2 is functional correctness. Level 3 is independently verified quality. A capability is not done until it reaches the level appropriate for its risk and scope — new skills that ship to the marketplace require all three levels.

---

## Level 1 — Plugin Structure and CI Green

These criteria are mechanical. They are verified by `/wg-check` and the `validate.yml` CI workflow. Failure at this level means the work is structurally incomplete.

- [ ] **L1-001** — All skills have valid YAML frontmatter (name, description, required fields present, no syntax errors).
- [ ] **L1-002** — All skill names follow the naming convention: `wicked-garden-{domain}` for domain router skills, `wicked-garden-{domain}-{role}` for fork workers. Kebab-case, max 64 chars.
- [ ] **L1-003** — Fork worker skills carry `context: fork` in frontmatter.
- [ ] **L1-004** — Slim body contract is met: Pattern A ≤ 8 lines, Pattern B ≤ 30 lines, Pattern C ≤ 35 lines. No skill body exceeds its pattern ceiling.
- [ ] **L1-005** — `components.json` is in sync with the current skill tree (`scripts/ci/sync_components.py` produces no diff).
- [ ] **L1-006** — All hook scripts are stdlib-only Python (no third-party imports). Hook registration entries in `hooks/hooks.json` are consistent with the scripts in `hooks/scripts/`.
- [ ] **L1-007** — The compiler's emitted `gate.py` passes the AST-enforced stdlib-only check (`tests/compiler/test_compile.py`).
- [ ] **L1-008** — No hardcoded `/tmp` paths (use `tempfile.gettempdir()`). No bare `python3` without `|| python` fallback in hook commands.
- [ ] **L1-009** — All Python scripts in `scripts/` and `hooks/scripts/` pass Python syntax check (`python3 -m py_compile`).
- [ ] **L1-010** — `validate.yml` CI workflow is green on the PR branch.
- [ ] **L1-011** — `plugin.json` version matches `marketplace.json` version.
- [ ] **L1-012** — Event names in all bus emissions follow the 4-segment format `wicked.<domain>.<noun>.<past-tense-verb>`.

---

## Level 2 — Functional Correctness

These criteria verify that the core capabilities work as designed. They are verified by unit tests (`tests/`), integration tests, and manual scenario runs. Failure at this level means the feature behaves incorrectly.

**Evidence gate:**
- [ ] **L2-001** — `gate_satisfied()` returns green when wicked-loom and wicked-vault are present and evidence matches.
- [ ] **L2-002** — `gate_satisfied()` returns `gate: "unavailable"` (not green) when loom is absent or `WICKED_LOOM_CUTOVER=off`.
- [ ] **L2-003** — `gate_satisfied()` fails closed when vault is unresolvable (`WICKED_VAULT_BIN=""`).
- [ ] **L2-004** — Hard-gate attestation rejects evidence recorded under `created_by_source='env-user'` (vault `>= 0.4.0`).
- [ ] **L2-005** — Evidence recorded under an explicit `--actor` (e.g., `garden-prove`) passes the attestation gate.

**Archetype detection:**
- [ ] **L2-006** — The `UserPromptSubmit` hook fires and injects a `<wg archetype="X" score="Y" />` system-reminder for representative prompts in each of the ten work-shape categories.
- [ ] **L2-007** — Multi-archetype detection returns a set (not a single match) for prompts that span multiple work-shapes (e.g., "add a column and deploy it" → `build + migrate`).
- [ ] **L2-008** — The detector does not return archetype hits below a configurable score threshold (no false-positive classifications).

**Compiler:**
- [ ] **L2-009** — `compile.py` Phase 0 detection identifies the ecosystem, test/lint/build commands, and claims documents for a representative set of repo types (Node, Python, Rust).
- [ ] **L2-010** — The emitted `gate.py` runs to completion in a clean environment with only Python stdlib and a resolvable `wicked-vault` via `npx`.
- [ ] **L2-011** — With `--trigger hook`, a git pre-push hook is installed that executes the emitted gate on push.
- [ ] **L2-012** — With `--trigger ci`, a GitHub Actions workflow file is written that executes the emitted gate.

**wicked-patch:**
- [ ] **L2-013** — `rename` applies consistently across all files referencing the target symbol, including those connected via injected codegraph edges.
- [ ] **L2-014** — The patch plan step (`patch-plan`) shows the complete affected file set before applying changes.
- [ ] **L2-015** — Language generators produce syntactically valid output for each supported language (Python, TypeScript, Java, Go, SQL, Rust).

**Council:**
- [ ] **L2-016** — The `council` action dispatches to at least one external LLM CLI and returns a synthesized verdict.
- [ ] **L2-017** — Each council participant evaluates in an isolated context (no shared state with the invoking session).

**Cross-platform:**
- [ ] **L2-018** — All hook scripts execute without error on macOS and Linux (Git Bash / WSL paths verified for Windows compatibility).
- [ ] **L2-019** — Storage paths resolve correctly on all three platforms (no `/tmp` hardcode failures, no `~` expansion failures).

---

## Level 3 — Independent Verification (Marketplace Ready)

These criteria require independent evaluation — the evaluator is not the agent or person that produced the work. Failure at this level means the capability has not been independently verified and is not ready to ship to the marketplace.

**wicked-testing acceptance gate:**
- [ ] **L3-001** — All scenarios in `scenarios/` pass the wicked-testing acceptance pipeline. Verdict: PASS. No scenario with verdict FAIL or SKIP (where SKIP is a substitute for a real result, not a legitimately out-of-scope check). MANUAL-ONLY is a distinct verdict from SKIP.
- [ ] **L3-002** — The acceptance gate verdict is recorded as an EvidenceRecord in wicked-vault under an explicit actor (`WICKED_VAULT_ACTOR`). The verdict is re-derivable (not self-asserted).
- [ ] **L3-003** — The evaluator agent (wicked-testing's judge) is not the agent that ran the test scenarios (structural separation, not convention).

**Adversarial review:**
- [ ] **L3-004** — An adversarial review has been run on all changed skills and scripts. The reviewer is not the author. Findings are addressed or explicitly accepted with rationale.
- [ ] **L3-005** — The adversarial review checked: frontmatter accuracy (description matches actual behavior), refs content correctness (rubrics are valid), gate semantics (no vacuous-pass paths), cross-platform paths, and naming compliance.
- [ ] **L3-006** — Review findings are recorded (not silently discarded). At least one reviewer finding was actioned or accepted with documented rationale.

**Release published:**
- [ ] **L3-007** — `plugin.json` and `marketplace.json` version are bumped (semver, appropriate bump level for the change).
- [ ] **L3-008** — `components.json` regenerated and committed with the version bump.
- [ ] **L3-009** — Release tagged in git and published to the marketplace registry.
- [ ] **L3-010** — `test.yml` CI workflow is green on the release tag (unit tests + E2E trust-spine tests + wicked-patch conformance tests all pass).

---

## DoD Application by Change Type

| Change Type | Required Levels |
|-------------|----------------|
| Frontmatter / rubric / ref update | L1 + L2 (gate and detection tests must still pass) |
| New action in an existing domain skill | L1 + L2 |
| New domain router skill | L1 + L2 + L3 |
| New fork worker skill | L1 + L2 |
| Hook script change | L1 + L2 (cross-platform verification required) |
| Evidence gate path change | L1 + L2 (all gate criteria) + L3 (adversarial review required) |
| Compiler change | L1 + L2 (AST check + emitted gate run) + L3 |
| Archetype definition change (archetypes.json) | L1 + L2 + L3 |
| Release | L1 + L2 + L3 (all criteria) |
