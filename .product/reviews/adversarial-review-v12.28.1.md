---
name: adversarial-review-v12.28.1
title: wicked-garden — Adversarial Review v12.28.1
verdict: FAIL
date: 2026-07-21
reviewer: council-adversarial
resolution: PASS (findings addressed 2026-07-21 in fix/garden-adversarial-review-findings)
---

# Adversarial Review — wicked-garden v12.28.1

## Verdict: FAIL → PASS after resolution

Initial verdict was FAIL. All blocking findings (C-001, H-001, H-002, H-003) were
addressed in branch `fix/garden-adversarial-review-findings`. See Resolution sections
under each finding. The plugin code itself is largely sound — fail-closed gate logic,
triple-fallback hook commands, AST-enforced stdlib gate, 972 tests green — but two
evidence quality problems blocked release at L3: the L2-013 evidence cited 228 tests
that do not test what they claim to test, and the L1-012 event count was off by nine.
A release that self-attests evidence quality cannot have inaccurate evidence.

---

## CRITICAL findings (block release)

### C-001 — L2-013/014 evidence is misleading: 228 "patch tests" do not test cross-file graph operations

**Finding.** The DoD claims: "228 patch tests PASSED (python3 -m pytest tests/ -k patch)" as evidence that L2-013 ("rename applies consistently across all files … including those connected via injected codegraph edges") and L2-014 ("plan step shows the complete affected file set") are verified.

The filter `-k patch` matches the substring "patch" anywhere in the test ID. The 228 collected tests include:
- `test_meets_pin_patch_above` (loom semver version pinning — patch as in semver patch level)
- `test_higher_patch_in_range`, `test_lower_patch_out_of_range` (wicked-testing version range checks)
- `test_skill_dispatch_refs_resolve.py` tests (skill manifest references, not graph traversal)
- Numerous other tests with "dispatch", "patch", or related substrings in names unrelated to wicked-patch rename

The **actual** wicked-patch conformance tests live in `scripts/engineering/patch/tests/test_conformance.py` and contain **12 tests**. These 12 tests verify language generator output (L2-015 only — "syntactically valid output"). They do not test:
- Multi-file rename propagation (L2-013)
- Plan-step completeness (L2-014)
- Cross-file traversal via injected codegraph edges (the specific L2-013 sub-claim)

**Root cause.** The `PropagationEngine.plan_propagation()` resolves graph edges via `_brain_api()` — an HTTP call to a running wicked-brain server. No test mocks or exercises this call path. The L2-013 sub-claim about "injected codegraph edges" (bus/dispatch/capability injected into wicked-estate's graph, not the static SQLite codegraph) has zero test coverage: `patch.py` does not consult wicked-estate at all; it queries wicked-brain's `symbols` and `dependents` HTTP endpoints. Injected edges from wicked-bus events (event→consumer, command→agent) live in wicked-estate, not in what those brain endpoints surface. The claim exceeds what the implementation demonstrably does.

**Action required.** Either:
(a) Correct the evidence pointer to the 12 actual conformance tests (passing), mark L2-013 evidence as "no test for multi-file graph traversal with injected edges — integration test gap", and scope down the claim language to match what is tested; or
(b) Add integration tests that exercise `PropagationEngine` with a mocked brain server returning multi-file symbol results, and add a test verifying cross-file rename propagates to dependent files.

**Resolution (2026-07-21):** Option (a) taken. L2-013 and L2-014 unchecked in DoD; evidence corrected to cite 12 conformance tests in `test_conformance.py` (language generator output only). Multi-file rename propagation and plan completeness noted as open integration test gaps. Injected-edge sub-claim removed.

---

## HIGH findings (non-blocking — must address before next release)

### H-001 — L1-012 event count wrong: 51 events in BUS_EVENT_MAP, not 60

**Finding.** The DoD evidence statement for L1-012 reads: "scan of production Python — 60 distinct well-formed 4-segment events." Runtime verification of `BUS_EVENT_MAP`:

```
python3 -c "import sys; sys.path.insert(0,'scripts'); from _bus import BUS_EVENT_MAP; print(len(BUS_EVENT_MAP))"
# → 52  (at time of finding: 51; one event wicked.garden.sentinel.unverified_task_done added post-review)
```

There were **51** events in BUS_EVENT_MAP at time of review (not 60). No other source (hooks, skills) emits bus events outside this map except `_validate_registry.py`, which referenced two events (`wicked.garden.rollout.decided`, `wicked.garden.experiment.concluded`) not present in BUS_EVENT_MAP — raising a separate question about whether those are planned, orphaned, or from a prior version. Adding those two still gave 53, not 60. Final count after resolution: **52** events (one missing event added; two orphaned entries removed from `_validate_registry.py`).

**Action required.** Correct the evidence count in the DoD. If additional events are referenced elsewhere, enumerate them and confirm they belong.

**Resolution (2026-07-21):** L1-012 evidence corrected to 51 events. Two orphaned events (`wicked.garden.rollout.decided`, `wicked.garden.experiment.concluded`) removed from `_validate_registry.py` (they were not in BUS_EVENT_MAP). **Follow-up (2026-07-21, bot review):** One missing event `wicked.garden.sentinel.unverified_task_done` added to BUS_EVENT_MAP — the call site in `hooks/scripts/task_completed.py:299` was registered in `_SENTINEL_EVENTS` but absent from the map, causing silent bus drops. Final count: 52 events. DoD L1-012 updated to 52.

### H-002 — Two event names violate the past-tense-verb convention

**Finding.** The DoD's own naming convention is `wicked.<domain>.<noun>.<past-tense-verb>`. Two events in BUS_EVENT_MAP do not conform:

| Event | 4th segment | Problem |
|---|---|---|
| `wicked.garden.guard.findings` | `findings` | Noun, not a past-tense verb. Should be something like `wicked.garden.guard.surfaced`. |
| `wicked.garden.modernize.stack_gap` | `stack_gap` | Noun phrase, not a past-tense verb. Should be something like `wicked.garden.modernize.gap_emitted`. |

`wicked.garden.scenario.run` is borderline — "run" is the past tense in some usages but is ambiguous (infinitive/past/noun). Recommend `wicked.garden.scenario.executed` for clarity.

All three events are structurally 4-segment, so the L1-012 mechanically-valid claim holds, but the well-formed qualification in the DoD evidence statement is overstated.

**Action required.** Rename the two events to use past-tense verbs, update BUS_EVENT_MAP, regenerate the event catalog, update consumers. `wicked.garden.scenario.run` can stay with a note.

**Resolution (2026-07-21):** Both events renamed: `wicked.garden.guard.findings` → `wicked.garden.guard.surfaced`; `wicked.garden.modernize.stack_gap` → `wicked.garden.modernize.gap_emitted`. BUS_EVENT_MAP, `guard_pipeline.py`, `stack_registry.py`, `_validate_registry.py`, comments in `_heavy_cadence.py` and `stop.py` all updated. WICKED_GARDEN_BUS_EVENTS.md regenerated. `wicked.garden.scenario.run` retained with a note that "run" is borderline but not renamed.

### H-003 — L2-003 evidence doesn't prove what it claims

**Finding.** L2-003: "gate_satisfied() fails closed when vault is unresolvable (WICKED_VAULT_BIN='')." The cited test `test_gate_satisfied_fails_closed_when_loom_absent` sets both `WICKED_LOOM_CUTOVER=auto` and `WICKED_VAULT_BIN=""`.

Code analysis of `gate_satisfied()`:
1. It calls `resolve_vault(project_dir=...)` with default `allow_npx=True`.
2. With `allow_npx=True`, loom is the resolver — `WICKED_VAULT_BIN` is not consulted.
3. Gate fails closed because loom is absent (mocked `resolve_loom=None`), **not** because `WICKED_VAULT_BIN=""`.

Setting `WICKED_VAULT_BIN=""` is a kill-switch for the `vault_available()` concrete-install probe (`allow_npx=False` path) only. It does **not** kill-switch `gate_satisfied()` when loom is active, because loom resolves the vault independently of `WICKED_VAULT_BIN`. There is no test proving that `WICKED_VAULT_BIN=""` causes `gate_satisfied()` to fail closed when loom is active.

**Action required.** Either add a test that exercises the `WICKED_VAULT_BIN=""` → `gate_satisfied fails closed` path in the presence of an active loom (which will require verifying what loom returns when vault is kill-switched), or update the L2-003 evidence statement to reflect the actual mechanism: "fails closed when loom is unresolvable" (which is what the test proves).

**Resolution (2026-07-21):** L2-003 evidence statement reworded: "fails closed when loom is unresolvable" (what the test actually proves). The `WICKED_VAULT_BIN=""` claim removed. No new test added for the vault kill-switch path (tracked as open gap alongside L2-004).

---

## MEDIUM findings (coverage gaps, minor issues)

### M-001 — `npm test` not defined; test invocation is undiscoverable

`package.json` declares no `test` script. `npm test` exits with `Missing script: "test"`. The CI workflow correctly uses `python -m pytest tests/ -q` directly, so CI passes, but any developer following the natural discovery path (`npm test`) hits a dead end. The DoD does not cite `npm test` as the invocation, but it also doesn't document the actual command. This creates onboarding friction.

**Action required.** Add `"test": "python3 -m pytest tests/ -q"` to package.json scripts, or document the test command explicitly in CONTRIBUTING.md / the README.

### M-002 — TaskCompleted hook entry missing `matcher` field

All other hook event entries in `hooks/hooks.json` carry `"matcher": "*"` at the outer level. The `TaskCompleted` entry does not:

```json
"TaskCompleted": [
  {
    "hooks": [...]       // no "matcher" field
  }
]
```

The CLAUDE.md spec for hooks does not explicitly require `matcher`. If Claude Code's hook dispatcher defaults to wildcard when matcher is absent, this is harmless. If it silently ignores the entry, the TaskCompleted hook never fires. Structural inconsistency warrants confirmation.

**Action required.** Add `"matcher": "*"` to the TaskCompleted entry for consistency and to make intent explicit.

### M-003 — Dynamic sentinel event construction is fragile

`scripts/sentinel/invariants.py` emits events as `f"wicked.garden.sentinel.{event}"`, where `event` is a string parameter. Currently only two call sites exist (`"claim_unverified"` and `"prepush_blocked"`), both with string literals. If a future caller passes an unexpected value, the event name will be unregistered and silently dropped by the bus, with no validation at the call site.

**Action required.** Constrain `event` to a `Literal["claim_unverified", "prepush_blocked"]` type annotation or add an `assert event in {...}` guard at the call site.

### M-004 — `_validate_registry.py` contains orphaned event references

`scripts/_validate_registry.py` references `wicked.garden.rollout.decided` and `wicked.garden.experiment.concluded` which are not in BUS_EVENT_MAP. Either these are planned events whose registry entries were added prematurely, or they are orphaned from a prior version. Either way, the registry is inconsistent with the production map.

**Action required.** Either add these events to BUS_EVENT_MAP with descriptions, or remove them from `_validate_registry.py`.

---

## LOW findings

### L-001 — Emitted gate.py uses `{"error": ...}` template with double-brace escaping that is fragile to format changes

In `compile.py`'s `_GATE_TEMPLATE`, the template uses Python format strings with `{{` and `}}` for literal braces. The template is complex and any future addition of a `{variable}` inside a `{{...}}` block will silently produce wrong output. The template has no automated round-trip test against the compiled gate body structure.

### L-002 — `_GATE_TEMPLATE` records `(Site W6 cutover)` style comments in production event descriptions

Some BUS_EVENT_MAP descriptions read "… (Site W6 cutover)" or "(Site W8 cutover)". These are internal migration markers that have no meaning to external consumers of the event catalog. The auto-generated `WICKED_GARDEN_BUS_EVENTS.md` exposes these to marketplace users.

### L-003 — L2-004/010b/011/012 remain genuinely open with no timeline

Four L2 criteria are explicitly open and require end-to-end integration tests against live peers. All four carry notes. No timeline or tracking issue numbers are referenced in the DoD. Acceptable to carry as open for this release only if those gaps are explicitly scoped out of the v12.28.1 DoD application table (compiler changes require L3, so L2-010b/011/012 being open matters for the compiler surface).

---

## L1 DoD criteria verification

| Criterion | Status | Notes |
|-----------|--------|-------|
| L1-001 Valid YAML frontmatter | CONFIRMED | validate.yml CI green; not independently re-run |
| L1-002 Naming convention | CONFIRMED | validate.yml CI |
| L1-003 context:fork workers | CONFIRMED | validate.yml CI |
| L1-004 Slim body contract | CONFIRMED | validate.yml CI |
| L1-005 components.json sync | PLAUSIBLE | Depends on CI green; not manually re-run |
| L1-006 Hook script deps clean | CONFIRMED | All hook commands use invoke.py dispatcher; verified in hooks.json |
| L1-007 AST stdlib-only gate.py | CONFIRMED | 19 compiler tests pass; gate.py template manually inspected — imports: json, os, shutil, subprocess, sys, pathlib only |
| L1-008 No /tmp hardcode; triple-fallback | CONFIRMED | All 13 hook event entries in hooks.json carry `python3 "..." \|\| python "..." \|\| py -3 "..."` exactly |
| L1-009 Python syntax check | PLAUSIBLE | CI claim; not re-run here |
| L1-010 CI green | CONFIRMED | pytest 972 passed, 17 skipped (independently run) |
| L1-011 Version consistency | CONFIRMED | Both plugin.json and marketplace.json read `"version": "12.28.1"` |
| L1-012 Event naming (4-segment) | WRONG count; PARTIAL format | 51 events in BUS_EVENT_MAP (not 60); all 51 are 4-segment; 2 violate past-tense-verb in segment 4 (see H-001, H-002) |

---

## L2 DoD criteria assessment

**L2-001/002 (gate pass / fail-closed when loom absent):** Code and test both correct. `cross_check()` and `gate_satisfied()` both return `{"available": False, "overall": "ERROR"}` when `_loom is None` or `WICKED_LOOM_CUTOVER=off`. Tests `test_off_disables_loom_fails_closed` and `test_loom_unresolvable_fails_closed` confirm both paths. No vacuous-pass path found in the code — the sentinel stamp (`_sentinel_stamp`) is itself fail-open (wrapped in bare `except Exception`) and cannot convert a failed gate to a pass. CONFIRMED.

**L2-002 edge-case note:** The `sys.path.insert` regression fix (issue #891, lines 55–65 of vault_gate.py) for the CLI invocation path is present and documented. Without it, `_loom` would be None on every CLI-mode call and EVERY gate would silently return "unavailable" — a systematic false-negative (not false-positive), so fail-closed semantics are preserved, but the confusing false negatives are fixed. Confirm CI E2E tests (`WICKED_REQUIRE_E2E=1`) exercise the CLI path.

**L2-003:** See H-003 above. The `WICKED_VAULT_BIN=""` kill-switch does not operate on `gate_satisfied()` when loom is active. Evidence statement is misleading.

**L2-006/007/008 (archetype detection):** Implementation reviewed. `detect_archetypes()` evaluates each archetype independently in its own call to `_detect_one_archetype()`. No shared mutable state between archetype evaluations. Multi-archetype output is a list sorted by score with triage appended unconditionally. Tests pass. CONFIRMED.

**L2-009 (compiler detection):** `compile.py` → `phase0/detect.py` path reviewed. `claim_specs()` and `derive_contract()` logic is clear and maps detected commands to vault contract claims correctly. CONFIRMED.

**L2-010a (emitted gate stdlib-only):** Template manually inspected. `_GATE_TEMPLATE` imports: `json`, `os`, `shutil`, `subprocess`, `sys`, `pathlib.Path` — all stdlib. AST enforcement in CI passes. CONFIRMED.

**L2-013/014 (cross-file rename with injected edges / plan completeness):** See C-001. Evidence is misleading; specific sub-claim about injected codegraph edges has no test coverage. WRONG (evidence attribution) / OPEN (injected-edge claim).

**L2-015 (language generators):** 12 conformance tests cover Python, TypeScript, Java, JSP, SQL, Go, C#, Ruby, Kotlin, Rust, PHP, Perl generators. Comment in `test_conformance.py` notes golden-output tests were removed (issue #879, fixtures never created). The contract tests verify structural correctness, not output fidelity. PLAUSIBLE at unit level; golden-output gap noted.

**L2-016/017 (council dispatch, isolation):** 11 council tests pass. Not read in depth in this review.

**L2-018/019 (cross-platform):** hooks.json triple-fallback confirmed for all 13 hook event entries. `tempfile.gettempdir()` usage not spot-checked in depth beyond the L1-008 CI claim.

---

## Summary

The plugin's core logic is solid: the vault gate correctly fails closed through loom, archetype detection is properly multi-match and independent, all hooks carry the required triple Python fallback, the emitted `gate.py` is stdlib-only by inspection, and the test suite runs to 972 passing. None of the code-level behaviors reviewed are wrong.

**What is risky:** Two evidence problems prevent a clean PASS at L3.

1. The L2-013 evidence pointer (`-k patch` in tests/) pulls in 228 tests that have nothing to do with wicked-patch multi-file rename. The twelve actual conformance tests only cover language generators. The specific claim about "injected codegraph edges" has no test coverage anywhere, and the implementation doesn't connect to wicked-estate where injected edges actually live. This is a factual overclaim that an adversarial reviewer would catch immediately and that undermines the entire DoD evidence chain.

2. The L1-012 event count (51 actual vs 60 claimed) is a smaller but similar problem: the count is simply wrong.

**Release readiness:** NOT ready to ship at L3 until C-001 is resolved (fix the evidence pointer and scope-correct the L2-013 language), H-001 is corrected (update the event count), H-002 events are renamed, and H-003 evidence is clarified. None of this requires changes to the gate or hook logic. The fix is documentation of correct evidence, addition of or scoping-down of the graph-operation claim, and two event renames.

Recommended path to PASS: address C-001 by correcting the evidence citation and removing or qualifying the injected-edge sub-claim; address H-001 by updating the count to 51; address H-002 by renaming the two events; address H-003 by clarifying what the cited test proves. M-001 and M-002 are cleanup that should accompany the release but are not blockers.
