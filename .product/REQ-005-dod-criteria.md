---
name: REQ-005-dod-criteria
title: wicked-garden — Definition of Done Criteria
status: partially-verified
version: 0.3
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-005 — Definition of Done Criteria

Three levels of done apply to wicked-garden. Level 1 is structural correctness. Level 2 is functional correctness. Level 3 is independently verified quality. A capability is not done until it reaches the level appropriate for its risk and scope — new skills that ship to the marketplace require all three levels.

---

## Level 1 — Plugin Structure and CI Green

These criteria are mechanical. They are verified by `/wg-check` and the `validate.yml` CI workflow. Failure at this level means the work is structurally incomplete.

- [x] **L1-001** — All skills have valid YAML frontmatter (name, description, required fields present, no syntax errors). Evidence: `Plugin Validation` CI check (`validate.yml`) — `SUCCESS` on the docs/garden-dod-l1-evidence branch and on main HEAD. The CI runs `scripts/ci/validate.py` which enforces frontmatter schema on every SKILL.md (2026-07-21).
- [x] **L1-002** — All skill names follow the naming convention: `wicked-garden-{domain}` for domain router skills, `wicked-garden-{domain}-{role}` for fork workers. Kebab-case, max 64 chars. Evidence: `validate.yml` CI `Plugin Validation` check: success on main (2026-07-21).
- [x] **L1-003** — Fork worker skills carry `context: fork` in frontmatter. Evidence: `validate.yml` CI `Plugin Validation` check: success on main (2026-07-21).
- [x] **L1-004** — Slim body contract is met: Pattern A ≤ 8 lines, Pattern B ≤ 30 lines, Pattern C ≤ 35 lines. No skill body exceeds its pattern ceiling. Evidence: `validate.yml` CI `Plugin Validation` check: success on main (2026-07-21).
- [x] **L1-005** — `components.json` is in sync with the current skill tree (`scripts/ci/sync_components.py` produces no diff). Evidence: `python3 scripts/ci/sync_components.py --check` → "components.json: in sync" (exit 0, 2026-07-21).
- [x] **L1-006** — All hook scripts have no third-party package imports (no pip-installable dependencies; repo-local `scripts/` modules are allowed). Hook registration entries in `hooks/hooks.json` are consistent with the scripts in `hooks/scripts/`. Evidence: hooks.json uses `invoke.py` dispatcher pattern; all scripts loaded via `invoke.py <name>` — structurally consistent. `v11 Test Suite` CI: success on main.
- [x] **L1-007** — The compiler's emitted `gate.py` passes the AST-enforced stdlib-only check (`tests/compiler/test_compile.py`). Evidence: `python3 -m pytest tests/compiler/test_compile.py -q` → 19 passed, 4 skipped (exit 0, 2026-07-21).
- [x] **L1-008** — No hardcoded `/tmp` paths (use `tempfile.gettempdir()`). No bare `python3` without `|| python` fallback in hook commands. Evidence: (a) grep scan of `hooks/scripts/` and `scripts/` — `/tmp` occurrences are in comments/docstrings only, not executable paths; (b) all hook commands in `hooks/hooks.json` use the triple-fallback pattern `python3 "..." || python "..." || py -3 "..."` — Windows, macOS, and Linux all covered (2026-07-21).
- [x] **L1-009** — All Python scripts in `scripts/` and `hooks/scripts/` pass Python syntax check (`python3 -m py_compile`). Evidence: `python3 -m compileall scripts/ hooks/scripts/ -q` → exit 0 (covers all Python files recursively; 2026-07-21).
- [x] **L1-010** — `validate.yml` CI workflow is green on the PR branch. Evidence: `validate` and `test` CI checks (`validate.yml`, `test.yml`) on the docs/garden-dod-l1-evidence branch — both `SUCCESS` (same evidence as L1-002 through L1-004; CI runs on every push to this branch, 2026-07-21).
- [x] **L1-011** — `plugin.json` version matches `marketplace.json` version. Evidence: both `12.28.1` (2026-07-21).
- [x] **L1-012** — Event names in all bus emissions follow the 4-segment format `wicked.<domain>.<noun>.<past-tense-verb>`. Evidence: `BUS_EVENT_MAP` in `scripts/_bus.py` contains 51 events (verified at runtime: `python3 -c "from _bus import BUS_EVENT_MAP; print(len(BUS_EVENT_MAP))"` → 51). All 51 are 4-segment. Two events were renamed from non-conforming noun forms to past-tense verbs in this PR: `wicked.garden.guard.findings` → `wicked.garden.guard.surfaced`; `wicked.garden.modernize.stack_gap` → `wicked.garden.modernize.gap_emitted`. Two orphaned entries (`rollout.decided`, `experiment.concluded`) removed from `_validate_registry.py`. (2026-07-21, v0.3)

---

## Level 2 — Functional Correctness

These criteria verify that the core capabilities work as designed. They are verified by unit tests (`tests/`), integration tests, and manual scenario runs. Failure at this level means the feature behaves incorrectly.

**Evidence gate:**
- [x] **L2-001** — `gate_satisfied()` returns green when wicked-loom and wicked-vault are present and evidence matches. Evidence: `tests/qe/test_loom_gate_contract.py::GateLoomAuthoritative::test_loom_pass_is_the_only_path` PASSED (2026-07-21).
- [x] **L2-002** — `gate_satisfied()` returns `gate: "unavailable"` (not green) when loom is absent or `WICKED_LOOM_CUTOVER=off`. Evidence: `test_gate_satisfied_fails_closed_when_loom_absent` and `test_off_disables_loom_fails_closed` PASSED (2026-07-21).
- [x] **L2-003** — `gate_satisfied()` fails closed when loom is unresolvable (returns `gate: "unavailable"`). Evidence: `test_gate_satisfied_fails_closed_when_loom_absent` PASSED — mocks `resolve_loom=None`, confirms gate returns ERROR/unavailable. Note: `WICKED_VAULT_BIN=""` is the kill-switch for the concrete vault probe (`vault_available()`) but does NOT kill-switch `gate_satisfied()` when loom is active (loom resolves vault independently). The gate's fail-closed posture when loom is absent is what the test verifies (2026-07-21, v0.3).
- [ ] **L2-004** — Hard-gate attestation rejects evidence recorded under `created_by_source='env-user'` (vault `>= 0.4.0`). Requires vault `>= 0.4.0` installed; not yet run end-to-end.
- [x] **L2-005** — Evidence recorded under an explicit `--actor` (e.g., `garden-prove`) passes the attestation gate. Evidence: `tests/qe/test_prove.py::AttestationForwardingTests::test_with_attestations_forwarded_to_gate` PASSED (2026-07-21).

**Archetype detection:**
- [x] **L2-006** — The `UserPromptSubmit` hook fires and injects a `<wg archetype="X" score="Y" />` system-reminder for representative prompts in each of the ten work-shape categories. Evidence: `tests/crew/test_archetypes_v11.py` — 31 passed covering all 10 archetypes (2026-07-21).
- [x] **L2-007** — Multi-archetype detection returns a set (not a single match) for prompts that span multiple work-shapes (e.g., "add a column and deploy it" → `build + migrate`). Evidence: multi-archetype tests in `test_archetypes_v11.py` PASSED (2026-07-21).
- [x] **L2-008** — The detector does not return archetype hits below a configurable score threshold (no false-positive classifications). Evidence: threshold tests in `test_archetypes_v11.py` PASSED (2026-07-21).

**Compiler:**
- [x] **L2-009** — `compile.py` Phase 0 detection identifies the ecosystem, test/lint/build commands, and claims documents for a representative set of repo types (Node, Python, Rust). Evidence: `tests/crew/test_flow_compiler.py` PASSED; `tests/compiler/test_compile.py` 19 passed (2026-07-21).
- [x] **L2-010a** — The emitted `gate.py` contains only Python stdlib imports (no third-party packages). Evidence: AST stdlib-only enforcement in `tests/compiler/test_compile.py` — 19 passed, statically asserts no non-stdlib imports in the emitted gate (2026-07-21).
- [ ] **L2-010b** — The emitted `gate.py` runs to completion in a clean environment with `wicked-vault` resolved via `npx` (end-to-end emitted gate execution). Requires integration test against a real repo with live npx resolution; not yet run end-to-end (tracked as an open gap alongside L2-011/012).
- [ ] **L2-011** — With `--trigger hook`, a git pre-push hook is installed that executes the emitted gate on push. Requires integration test against a real repo; not yet run end-to-end.
- [ ] **L2-012** — With `--trigger ci`, a GitHub Actions workflow file is written that executes the emitted gate. Requires integration test against a real repo; not yet run end-to-end.

**wicked-patch:**
- [ ] **L2-013** — `rename` applies consistently across all files referencing the target symbol, including those connected via injected codegraph edges. Note: the `-k patch` filter collects 228 tests matching "patch" as a substring across the whole suite (including semver tests, loom pin tests, etc.) — those are not wicked-patch tests. The actual wicked-patch conformance tests are 12 tests in `scripts/engineering/patch/tests/test_conformance.py`, which verify language generator output (L2-015) only. Multi-file rename propagation and plan completeness (L2-013/014) have NO dedicated test coverage. The specific sub-claim about "injected codegraph edges" (bus/dispatch edges in wicked-estate) is also unverified: `PropagationEngine` queries wicked-brain's HTTP API, not wicked-estate. Open gap pending integration test.
- [ ] **L2-014** — The `patch plan` step shows the complete affected file set before applying changes. Note: the 12 conformance tests (`scripts/engineering/patch/tests/test_conformance.py`) verify language generator syntactic correctness only — plan completeness across multi-file renames is not covered. Open gap pending integration test.
- [x] **L2-015** — Language generators produce syntactically valid output for each supported language (Python, TypeScript, Java, Go, SQL, Rust). Evidence: `scripts/engineering/patch/tests/test_conformance.py` — 12 tests covering Python, TypeScript, Java, JSP, SQL, Go, C#, Ruby, Kotlin, Rust, PHP, Perl generators PASSED (2026-07-21). These are the actual wicked-patch conformance tests (not the broader `-k patch` filter).

**Council:**
- [x] **L2-016** — The `council` action dispatches to at least one external LLM CLI and returns a synthesized verdict. Evidence: 11 council tests PASSED (2026-07-21; `python3 -m pytest tests/ -k council`).
- [x] **L2-017** — Each council participant evaluates in an isolated context (no shared state with the invoking session). Evidence: isolation tests included in the 11 PASSED council tests (2026-07-21).

**Cross-platform:**
- [x] **L2-018** — All hook scripts execute without error on macOS and Linux (Git Bash / WSL paths verified for Windows compatibility). Evidence: 64 cross-platform tests PASSED (2026-07-21); L1-008 confirmed no hardcoded `/tmp` in scripts.
- [x] **L2-019** — Storage paths resolve correctly on all three platforms (no `/tmp` hardcode failures, no `~` expansion failures). Evidence: path resolution tests included in 64 cross-platform PASSED tests (2026-07-21).

---

## Level 3 — Independent Verification (Marketplace Ready)

These criteria require independent evaluation — the evaluator is not the agent or person that produced the work. Failure at this level means the capability has not been independently verified and is not ready to ship to the marketplace.

**wicked-testing acceptance gate:**
- [ ] **L3-001** — All scenarios in `scenarios/` pass the wicked-testing acceptance pipeline. Verdict: PASS. No scenario with verdict FAIL or SKIP (where SKIP is a substitute for a real result, not a legitimately out-of-scope check). MANUAL-ONLY is a distinct verdict from SKIP.
- [ ] **L3-002** — The acceptance gate verdict is recorded as an EvidenceRecord in wicked-vault under an explicit actor (`WICKED_VAULT_ACTOR`). The verdict is re-derivable (not self-asserted).
- [ ] **L3-003** — The evaluator agent (wicked-testing's judge) is not the agent that ran the test scenarios (structural separation, not convention).

**Adversarial review:**
- [x] **L3-004** — An adversarial review has been run on all changed skills and scripts. The reviewer is not the author. Findings are addressed or explicitly accepted with rationale. Evidence: `.product/reviews/adversarial-review-v12.28.1.md` — initial verdict FAIL (C-001: misleading evidence; H-001: wrong event count; H-002: 2 events non-conforming; H-003: misleading evidence citation). All blocking findings addressed in this PR (see L3-006). (2026-07-21)
- [x] **L3-005** — The adversarial review checked: frontmatter accuracy (description matches actual behavior), refs content correctness (rubrics are valid), gate semantics (no vacuous-pass paths), cross-platform paths, and naming compliance. Evidence: `adversarial-review-v12.28.1.md` — gate logic confirmed correct (fail-closed paths verified), triple-fallback hooks confirmed, AST stdlib check confirmed, event naming compliance verified (2 events renamed), evidence chain checked (2026-07-21).
- [x] **L3-006** — Review findings are recorded (not silently discarded). At least one reviewer finding was actioned or accepted with documented rationale. Evidence: C-001 resolved (L2-013/014 unchecked, evidence scoped down to 12 actual conformance tests); H-001 resolved (L1-012 count corrected to 51); H-002 resolved (2 events renamed to past-tense verbs); H-003 resolved (L2-003 evidence reworded). M-001/M-002/M-003/M-004 also addressed. Review record: `.product/reviews/adversarial-review-v12.28.1.md`.

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

---

## Revision History

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.1 | 2026-07-21 | mike.parcewski@gmail.com | Initial draft — all L1/L2/L3 items unchecked |
| 0.2 | 2026-07-21 | mike.parcewski@gmail.com | Evidence pass: all 12 L1 criteria checked off (CI green, syntax checks, components sync, version match). L2-001/002/003/005/006/007/008/009/010/013/014/015/016/017/018/019 verified via 972-test suite (972 passed, 17 skipped). L2-004/011/012 require end-to-end integration tests. All L3 items remain open (require acceptance pipeline + adversarial review). |
| 0.3 | 2026-07-21 | mike.parcewski@gmail.com | Adversarial review findings addressed (initial verdict FAIL → resolving to PASS): C-001 — L2-013/014 unchecked (evidence was misleading; 228 tests ≠ wicked-patch tests; scoped to 12 actual conformance tests; multi-file graph traversal gap noted); H-001 — L1-012 event count corrected to 51; H-002 — two events renamed (`guard.findings` → `guard.surfaced`, `modernize.stack_gap` → `modernize.gap_emitted`); H-003 — L2-003 evidence reworded to reflect what test actually proves (loom absent, not VAULT_BIN=""); M-001 — `npm test` script added to package.json; M-002 — `matcher: "*"` added to TaskCompleted hook; M-003 — `_SENTINEL_EVENTS` frozenset guard added; M-004 — orphaned rollout/experiment events removed from `_validate_registry.py`. L3-004/005/006 checked (adversarial review run, findings recorded and actioned). 972 tests still pass. |
