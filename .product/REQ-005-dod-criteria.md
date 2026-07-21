---
name: REQ-005-dod-criteria
title: wicked-garden — Definition of Done Criteria
status: partially-verified
version: 0.8
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
- [x] **L1-012** — Event names in all bus emissions follow the 4-segment format `wicked.<domain>.<noun>.<past-tense-verb>`. Evidence: `BUS_EVENT_MAP` in `scripts/_bus.py` contains 52 events (verified at runtime: `python3 -c "import sys; sys.path.insert(0,'scripts'); from _bus import BUS_EVENT_MAP; print(len(BUS_EVENT_MAP))"` → 52). All 52 are 4-segment. Two events were renamed from non-conforming noun forms to past-tense verbs in this PR: `wicked.garden.guard.findings` → `wicked.garden.guard.surfaced`; `wicked.garden.modernize.stack_gap` → `wicked.garden.modernize.gap_emitted`. One new event added: `wicked.garden.sentinel.unverified_task_done` (existing call site in `hooks/scripts/task_completed.py:299` was missing from map). Two orphaned entries (`rollout.decided`, `experiment.concluded`) removed from `_validate_registry.py`. (2026-07-21, v0.4)

---

## Level 2 — Functional Correctness

These criteria verify that the core capabilities work as designed. They are verified by unit tests (`tests/`), integration tests, and manual scenario runs. Failure at this level means the feature behaves incorrectly.

**Evidence gate:**
- [x] **L2-001** — `gate_satisfied()` returns green when wicked-loom and wicked-vault are present and evidence matches. Evidence: `tests/qe/test_loom_gate_contract.py::GateLoomAuthoritative::test_loom_pass_is_the_only_path` PASSED (2026-07-21).
- [x] **L2-002** — `gate_satisfied()` returns `gate: "unavailable"` (not green) when loom is absent or `WICKED_LOOM_CUTOVER=off`. Evidence: `test_gate_satisfied_fails_closed_when_loom_absent` and `test_off_disables_loom_fails_closed` PASSED (2026-07-21).
- [x] **L2-003** — `gate_satisfied()` fails closed when loom is unresolvable (returns `gate: "unavailable"`). Evidence: `test_gate_satisfied_fails_closed_when_loom_absent` PASSED — mocks `resolve_loom=None`, confirms gate returns ERROR/unavailable. Note: `WICKED_VAULT_BIN=""` is the kill-switch for the concrete vault probe (`vault_available()`) but does NOT kill-switch `gate_satisfied()` when loom is active (loom resolves vault independently). The gate's fail-closed posture when loom is absent is what the test verifies (2026-07-21, v0.4).
- [x] **L2-004** — Hard-gate attestation rejects evidence recorded under `created_by_source='env-user'` (vault `>= 0.4.0`). Evidence (2026-07-21, vault 0.9.0): (1) `wicked-vault record --scope l2-004-test --phase verify ... --artifact test-artifact.txt` (no `--actor`) → artifact ID `019F85F5DD2A62E049B179068641`, `created_by_source='env-user'`. (2) `wicked-vault inspect` confirms `created_by: michael.parcewski, source: env-user`. (3) `wicked-vault attest ... --evaluator test-evaluator` (no `--allow-weak-worker-identity`) → exit 1, error: `"attest refused (G10/D4): the artifact was recorded under a weak/ambient worker identity (created_by_source='env-user'), so 'evaluator != created_by' is not a trustworthy independence signal."` Vault fails-closed exactly as specified. vault 0.9.0 satisfies the `>= 0.4.0` floor.
- [x] **L2-005** — Evidence recorded under an explicit `--actor` (e.g., `garden-prove`) passes the attestation gate. Evidence: `tests/qe/test_prove.py::AttestationForwardingTests::test_with_attestations_forwarded_to_gate` PASSED (2026-07-21).

**Archetype detection:**
- [x] **L2-006** — The `UserPromptSubmit` hook fires and injects a `<wg archetype="X" score="Y" />` system-reminder for representative prompts in each of the ten work-shape categories. Evidence: `tests/crew/test_archetypes_v11.py` — 31 passed covering all 10 archetypes (2026-07-21).
- [x] **L2-007** — Multi-archetype detection returns a set (not a single match) for prompts that span multiple work-shapes (e.g., "add a column and deploy it" → `build + migrate`). Evidence: multi-archetype tests in `test_archetypes_v11.py` PASSED (2026-07-21).
- [x] **L2-008** — The detector does not return archetype hits below a configurable score threshold (no false-positive classifications). Evidence: threshold tests in `test_archetypes_v11.py` PASSED (2026-07-21).

**Compiler:**
- [x] **L2-009** — `compile.py` Phase 0 detection identifies the ecosystem, test/lint/build commands, and claims documents for a representative set of repo types (Node, Python, Rust). Evidence: `tests/crew/test_flow_compiler.py` PASSED; `tests/compiler/test_compile.py` 19 passed (2026-07-21).
- [x] **L2-010a** — The emitted `gate.py` contains only Python stdlib imports (no third-party packages). Evidence: AST stdlib-only enforcement in `tests/compiler/test_compile.py` — 19 passed, statically asserts no non-stdlib imports in the emitted gate (2026-07-21).
- [x] **L2-010b** — The emitted `gate.py` runs to completion in a clean environment with `wicked-vault` resolved via `npx` (end-to-end emitted gate execution). Evidence (2026-07-21): Created a test repo at `/tmp/l2-010b-test-repo` with `package.json` (`"test": "echo 'tests pass' && exit 0"`). `compile.py /tmp/l2-010b-test-repo` emitted `gate.py` + `contract.json` (auto-detected `npm test`). `python3 .wicked/gate.py` ran to completion: `{"gate": "vault-cross-check", "overall": "PASS", "claims": [{"claim_id": "tests-pass", "hash_ok": true, "verifier_status": "pass", "result": "PASS", "detail": "exit_code=0"}]}`. vault resolved via npx (no wicked-garden installation required in the test repo).
- [x] **L2-011** — With `--trigger hook`, a git pre-push hook is installed that executes the emitted gate on push. Evidence (2026-07-21): `compile.py /tmp/l2-010b-test-repo --trigger hook` → `{"trigger": "pre-push-hook", "status": "created", "path": "/tmp/l2-010b-test-repo/.git/hooks/pre-push"}`. Hook content: runs `python3 "$_root/.wicked/gate.py"` and blocks push on non-zero exit. Inspected and confirmed correct.
- [x] **L2-012** — With `--trigger ci`, a GitHub Actions workflow file is written that executes the emitted gate. Evidence (2026-07-21): `compile.py /tmp/l2-010b-test-repo --trigger ci` → `{"trigger": "ci-workflow", "status": "created", "path": "/tmp/l2-010b-test-repo/.github/workflows/wicked-gate.yml"}`. Workflow: `on: [push, pull_request]`, job `gate` runs `python3 .wicked/gate.py` on `ubuntu-latest` after `actions/checkout@v4` + `setup-node@v4`. Inspected and confirmed correct.

**wicked-patch:**
- [x] **L2-013** — `rename` applies consistently across all files referencing the target symbol. Evidence (partial): `scripts/engineering/patch/tests/test_propagation_plan.py` — 5 tests (`PropagationMultiFilePlanTests`): (1) RENAME_FIELD plan includes all 3 files (user.py + serializers.py + factories.py); (2) unrelated file excluded; (3) all referencing symbols in `all_affected`; (4) `files_affected` == union of symbol file_paths; (5) total file count correct. 10/10 tests pass in isolation; 26/26 patch tests pass overall (PR #1009, 2026-07-21). Remaining gap: the sub-claim about injected codegraph edges (bus/dispatch edges via wicked-estate) is NOT covered — `PropagationEngine` queries wicked-brain's HTTP API in production, and that integration path is unverified. The unit-level rename propagation through the SQLite symbol graph is verified; the wicked-estate edge injection path is an open gap.
- [x] **L2-014** — The `patch plan` step shows the complete affected file set before applying changes. Evidence: `scripts/engineering/patch/tests/test_propagation_plan.py` — 5 tests (`PropagationPlanCompletenessTests`): (1) plan available before `generate_patches` (no circular dependency); (2) source file full path in `format_plan` output; (3) all impact symbol names in output; (4) `Total: N symbols in M files` footer matches `len(plan.files_affected)`; (5) source symbol name shown. 10/10 pass (PR #1009, 2026-07-21).
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
- [x] **L3-001** — The wicked-garden self-test acceptance scenario (`.wicked-testing/scenarios/garden-self-test.md`) passes the wicked-testing acceptance pipeline. Verdict: PASS. Note: this verifies the bootstrap invariants scenario only, not the full `scenarios/` product-scenario tree (those are run via `/wg-test`, not the wicked-testing acceptance pipeline).
  <!-- evidence: `.wicked-testing/scenarios/garden-self-test.md` — 4 assertions (A1: npm test 972 passed; A2: BUS_EVENT_MAP 52 events all 4-segment; A3: gate fails closed with WICKED_LOOM_CUTOVER=off; A4: _SENTINEL_EVENTS has all 3 required entries). Reviewer (acceptance-test-reviewer, revision 3) issued PASS for all 4 assertions. Overall verdict PASS written to `.wicked-testing/evidence/garden-l3-20260721/verdict.json`. (2026-07-21) -->
- [ ] **L3-002** — The acceptance gate verdict is recorded as an EvidenceRecord in wicked-vault under an explicit actor (`WICKED_VAULT_ACTOR`). The verdict is re-derivable (not self-asserted).
  <!-- status: open — wicked-vault not installed in test environment; verdict.json is readable JSON evidence but is not recorded via vault's EvidenceRecord API under an explicit actor. Requires vault >= 0.4.0 installed and WICKED_VAULT_ACTOR set. -->
- [x] **L3-003** — The evaluator agent (wicked-testing's judge) is not the agent that ran the test scenarios (structural separation, not convention).
  <!-- evidence: executor = claude-code-main-session (ran all 4 scenario steps, wrote step-outputs.json). reviewer = acceptance-test-reviewer (independent subagent, no shared context with executor — cold-read evidence only). Structural separation confirmed in verdict.json. (2026-07-21) -->

**Adversarial review:**
- [x] **L3-004** — An adversarial review has been run on all changed skills and scripts. The reviewer is not the author. Findings are addressed or explicitly accepted with rationale. Evidence: `.product/reviews/adversarial-review-v12.28.1.md` — initial verdict FAIL (C-001: misleading evidence; H-001: wrong event count; H-002: 2 events non-conforming; H-003: misleading evidence citation). All blocking findings addressed in this PR (see L3-006). (2026-07-21)
- [x] **L3-005** — The adversarial review checked: frontmatter accuracy (description matches actual behavior), refs content correctness (rubrics are valid), gate semantics (no vacuous-pass paths), cross-platform paths, and naming compliance. Evidence: `adversarial-review-v12.28.1.md` — gate logic confirmed correct (fail-closed paths verified), triple-fallback hooks confirmed, AST stdlib check confirmed, event naming compliance verified (2 events renamed), evidence chain checked (2026-07-21).
- [x] **L3-006** — Review findings are recorded (not silently discarded). At least one reviewer finding was actioned or accepted with documented rationale. Evidence: C-001 resolved (L2-013/014 unchecked, evidence scoped down to 12 actual conformance tests); H-001 resolved (L1-012 count corrected, now 52 after adding `unverified_task_done`); H-002 resolved (2 events renamed to past-tense verbs); H-003 resolved (L2-003 evidence reworded). M-001/M-002/M-003/M-004 also addressed. Review record: `.product/reviews/adversarial-review-v12.28.1.md`.

**Release published:**
- [x] **L3-007** — `plugin.json` and `marketplace.json` version are bumped (semver, appropriate bump level for the change).
  <!-- evidence: PR #1010 (chore/garden-release-12.29.1) merged to main. plugin.json, marketplace.json, package.json, package-lock.json all bumped to 12.29.1. Patch bump for new propagation tests (L2-013/014 via PR #1009) + docstring fixes + package.json sync from 12.28.1. Prior: PR #1007 bumped plugin.json/marketplace.json to 12.29.0 (minor: sentinel event, two event renames, npm test script). (2026-07-21) -->
- [x] **L3-008** — `components.json` regenerated and committed with the version bump.
  <!-- evidence: `python3 scripts/ci/sync_components.py` → "components.json: in sync" — no diff from current skill tree. components.json verified current in PR #1010. (2026-07-21) -->
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
| 0.4 | 2026-07-21 | mike.parcewski@gmail.com | Bot review follow-up fixes: `modernize.md` event name updated to `gap_emitted`; `unverified_task_done` added to `_SENTINEL_EVENTS` frozenset (call site in `task_completed.py` was silently broken); `wicked.garden.sentinel.unverified_task_done` added to `BUS_EVENT_MAP` and `_validate_registry.py` `_AUDIT_MARKER_EVENTS` — bus catalog regenerated (51→52 events). L1-012 count updated to 52. 972 tests still pass. |
| 0.5 | 2026-07-21 | mike.parcewski@gmail.com | L2-013 and L2-014 checked off (partial): `test_propagation_plan.py` adds 10 tests across `PropagationMultiFilePlanTests` (L2-013) and `PropagationPlanCompletenessTests` (L2-014). Remaining gap: injected codegraph edge path (bus/dispatch edges via wicked-estate HTTP API) is not covered — production codegraph integration is unverified; SQLite symbol-graph propagation is verified. 26 patch tests pass total (PR #1009). |
| 0.6 | 2026-07-21 | mike.parcewski@gmail.com | Updated L3-007/008 evidence to reflect 12.29.1 release (PR #1010): version synced across package.json/plugin.json/marketplace.json/package-lock.json; CHANGELOG entries added for both 12.29.0 (missing) and 12.29.1. |
| 0.7 | 2026-07-21 | mike.parcewski@gmail.com | L2-004 checked off: hard-gate attestation rejects env-user artifacts end-to-end. vault 0.9.0 (`npx wicked-vault`) — `record` without `--actor` sets `created_by_source='env-user'`; subsequent `attest` exits 1 with error G10/D4 (fail-closed, no --allow-weak-worker-identity). |
| 0.8 | 2026-07-21 | mike.parcewski@gmail.com | L2-010b, L2-011, L2-012 checked off: compiler end-to-end verified. `compile.py /tmp/l2-010b-test-repo` (package.json with `npm test`) emitted gate.py + contract.json; `python3 .wicked/gate.py` → PASS (vault resolved via npx, no garden install required). `--trigger hook` → pre-push hook created at `.git/hooks/pre-push` (runs gate.py, blocks on non-zero). `--trigger ci` → `.github/workflows/wicked-gate.yml` created (on push+PR, gate job runs gate.py). |
