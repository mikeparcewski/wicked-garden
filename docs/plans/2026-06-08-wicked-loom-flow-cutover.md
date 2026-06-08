# wicked-loom — FLOW Surface Cutover (mirror → loom-authoritative park verdict) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the garden `flow` surface from a **read-only parity mirror** (which only logs `wicked.loom.parity_mismatch` and never changes behavior) to **loom-authoritative for the hard-gate park DECISION** — `approve_phase`'s `ValueError` guard fires based on loom's compiled-flow verdict (`loom flow` park-at-hard-gate semantics, re-derived through `flow_compiler` + loom's `_is_hard`), with the in-process `_HARD_GATE_PHASES` map demoted to the fail-soft fallback. `ProjectState` stays the sole source of truth for storage and one-phase-at-a-time advancement. This is the **smallest valuable, low-risk increment** of "loom authoritative for the flow surface": loom now decides *where the human stops*, but garden still *owns the state machine*.

**Architecture:** Garden's `phase_manager.approve_phase` already advances ONE phase per CLI call against a DomainStore-backed `ProjectState`; loom's `flow run` executes a WHOLE flow-def in one `while` loop and tracks its own `flowstate`. These are different state models (see "The hard design problem" below). This increment does NOT reconcile the two storage models — it delegates only the **single load-bearing decision** the parity mirror already cross-checks: *is `(archetype, phase)` a hard gate that must park for a human?* Today `_is_hard_gate` answers from the in-process `_HARD_GATE_PHASES` dict. After this increment, `_loom_confirms_hard_gate` (loom's verdict, via the compiled flow-def — which is itself derived from the same catalog + map) is **authoritative when present**, and `_HARD_GATE_PHASES` is the fallback only when loom is unavailable/uncertain. The mirror's stderr + `wicked.loom.parity_mismatch` emit is retained but re-cast as a divergence *signal* on the authoritative path. The `ValueError` hard-gate guard, the `confirmed_by`/`confirmation_evidence` requirement, and fail-closed posture are **preserved verbatim** — only the *source* of the "is this a hard gate" boolean changes.

**Tech Stack:** Python 3.9+ (stdlib only — garden's hook discipline; loom is reached as a subprocess via `scripts/_loom.py`, never imported). `pytest` (`testpaths = ["tests"]`; `tests/conftest.py` puts `scripts/` at `sys.path[0]` and `scripts/crew/` last). Tests drive the decision via the existing seams — patch `_loom.use_loom` / `phase_manager._loom_confirms_hard_gate` and stub `save_project_state` — so **no test spawns a real loom or touches the network**. The loom CLI surface this increment relies on is already shelled by `scripts/_loom.py`; the decision is computed in-process from the compiled flow-def (`flow_compiler.compile_flow`), which mirrors loom's own `_is_hard` rule (`hitl.startswith("hard:")`) — the same rule loom's `flow.py` uses to park.

**Decisions locked for this plan (override in review):**
- **Scope = the hard-gate PARK DECISION only.** Loom becomes authoritative for the boolean "must `approve_phase` require human confirmation here?" — nothing else. `ProjectState` storage, one-phase advancement, `start_phase`/`complete_phase`/`skip_phase`/`is_complete`, the `next_phase` resolution from `phase_plan`, and every bus emit are **unchanged**.
- **Fail-soft + fail-closed, both.** When loom is available and answers, loom wins. When loom is unavailable/uncertain (`_loom_confirms_hard_gate` returns `None`), the in-process `_HARD_GATE_PHASES` map answers — the exact current behavior (fail-soft, rollback-safe). Crucially, **the guard never weakens**: a phase that is hard under *either* source still requires confirmation. The authoritative source can only ADD a park (loom says hard, in-process says not) — it can never SILENTLY SKIP a park that the in-process map demands. This is the fail-closed invariant for this surface: we never regress the `ValueError`.
- **`_HARD_GATE_PHASES` is NOT deleted.** It stays as the fallback (loom unavailable) AND as the floor (loom must not be able to remove a park the map asserts). Deleting it is the separate **flow contract phase** (out of scope; see below).
- **The parity-mismatch signal is retained.** The existing `wicked.loom.parity_mismatch` stderr + bus emit stays; on the authoritative path it now means "loom and the in-process floor disagree" — still surfaced for operator visibility, but the *resolved* decision (the OR of both) drives the guard.
- **One feature flag, reused: `WICKED_LOOM_CUTOVER`** ∈ `{auto, on, off}`, default `auto` (the existing `_loom.use_loom()` gate). `off` / `auto`-unresolvable → loom is not consulted → the in-process map is authoritative (today's behavior). Rollback is `WICKED_LOOM_CUTOVER=off` — a single env var, no code revert.
- **Target repo:** garden = `~/Projects/wicked-garden` (this plan edits it). loom = `~/Projects/wicked-loom` (consumed via `scripts/_loom.py`; NOT edited here; the conduct/0.2.0 `flow` surface is its deliverable).

**Source material read before Task 1 (grounding):**
- `scripts/crew/phase_manager.py` — `approve_phase` (335–470), the loom parity mirror (359–377), `_is_hard_gate` (327–332), `_HARD_GATE_PHASES` (315–324), `_loom_confirms_hard_gate` (72–88), the `ValueError` hard-gate guard (380–399), and the `ProjectState` model (133–215). Garden advances ONE phase at a time via `approve_phase` → `next_phase`.
- `scripts/crew/flow_compiler.py` — `compile_flow` (66–105): the §3.1 archetype→flow-def compiler (already built; imports `_HARD_GATE_PHASES` so the two engines agree by construction).
- `scripts/_loom.py` — `use_loom()` (160–176), `run_json()` (122–151), the `WICKED_LOOM_CUTOVER` flag (154–157).
- `~/Projects/wicked-loom/python/loom/flow.py` — `_advance` (52–103): loom runs the WHOLE flow-def, parks at the first `hard:*` phase. `_is_hard` (36–38) is `hitl.startswith("hard:")` — the exact rule `flow_compiler` reproduces.
- `~/Projects/wicked-loom/python/loom/flowstate.py` — loom's own per-flow JSON state (one file per `flow_id`): a DIFFERENT state model from garden's `ProjectState`.
- `docs/plans/2026-06-08-wicked-loom-cutover.md` Task 3 + `2026-06-08-wicked-loom-contract.md` — the established flag-gated + parity-contract-test + fail-soft shim pattern this plan extends; the contract phase that explicitly LEFT the flow mirror intact.
- `tests/crew/test_loom_flow_contract.py` — the existing flow parity contract (3 tests). This plan adds to it; it does not break it.

**Out of scope (DEFERRED — do NOT do in this plan):**
- The **flow CONTRACT phase** — deleting the in-process flow logic. `_HARD_GATE_PHASES` and `_is_hard_gate` STAY (as fallback + floor). This increment leaves the in-process decision path in place behind the authoritative-source switch, so rollback is `WICKED_LOOM_CUTOVER=off`. Deleting them is a later plan, run only after this is proven in production.
- **Full `ProjectState` → loom `flowstate` migration.** Garden keeps its DomainStore `ProjectState` and its one-phase-at-a-time advancement model. Loom's whole-flow `flow run`/`flowstate` model is NOT adopted as garden's storage. That state-model reconciliation is a much larger, much riskier increment — explicitly deferred (see "The hard design problem", Decision below).
- **Loom autonomously driving phase advancement** (`loom flow run` executing the whole flow-def, doing gate re-derivation itself, advancing phases without the agent in the loop). This would remove the agent from the per-phase loop and is the OPPOSITE of garden's agent-driven model. Not in scope; arguably never (see Honest Assessment).
- **Wiring the produces-gate verdict (`loom gate`) into `approve_phase`.** The gate surface is already loom-authoritative via `vault_gate.cross_check` (contract phase done). `approve_phase` does not call the gate today and this increment does not add that call — that is a separate "gate-on-approve" feature, not a flow-surface cutover.
- The broader **§6 inventory** the cutover/contract did not touch (`_integration_resolver`/`_capability_resolver`/`_capability_registry`, `bootstrap` compose split, `_bus` consumer/projector, `_event_*` trio). All future increments. LEAVE ALONE.

**Bulletproof standards:** R1–R6 (no dead code — the fallback map is live, not dead; no swallowed errors — loom errors surface as `None` → fall back to the floor, never a silent skip of a park) and T1–T6 (determinism, no sleep-based sync, isolation, single-assertion focus, descriptive names, provenance). The fail-closed invariant gets the strongest coverage: a test proving loom-says-not-hard can NEVER remove a park the in-process map demands.

---

## Honest assessment: full flow cutover vs. scoped-down (READ THIS FIRST)

**A full flow cutover — loom authoritative for phase advancement — is NOT advisable as one increment. Recommend the scoped-down increment in this plan.** Reasons, plainly:

1. **The two surfaces have incompatible execution models, not just incompatible storage.** Garden's `approve_phase` advances ONE phase per call: the agent does the phase's work, calls `approve`, gets the `next_phase`, does the next phase's work, calls `approve` again. The agent is in the loop at every step. Loom's `flow run` executes the WHOLE flow-def in a single `while` loop (`flow.py:_advance`), re-deriving gates itself and parking only at the first `hard:*` phase. Adopting loom's model means the agent is NOT in the per-phase loop — loom advances autonomously between hard gates. That is a fundamental behavioral change to how garden does work, not a storage swap.

2. **The cutover plan made the flow surface read-only ON PURPOSE.** The cutover (Task 3) and the contract phase both explicitly chose a read-only parity mirror for flow and explicitly LEFT it that way ("There is no in-process re-derivation body to delete here... LEAVE the mirror"). That signal is deliberate: flow is the riskiest surface — it is the crew state machine, the thing that gates a human in the loop on `migrate.cutover` / `incident.mitigate`. A storage/execution-model migration here, done in one shot with the gate guard live, is exactly the kind of big-bang the strangler pattern exists to avoid.

3. **Two state stores would have to be reconciled.** ProjectState (`current_phase` as a phase *name*, `phases` dict keyed by name, `phase_plan` list, `extras.approvals`) vs. loom flowstate (`current_phase` as an *index*, `gate_verdicts` keyed by name, `parked`/`parked_reason`, one JSON file per `flow_id`). A full cutover must either (a) mirror loom's flowstate INTO ProjectState on every call — doubling the write path and the failure surface — or (b) move ProjectState onto loom's flowstate, breaking every existing reader (`status`, the delivery/smaht commands, the migration script). Neither is a safe single step.

4. **The valuable, low-risk decision is already isolated.** The parity mirror already computes loom's verdict for exactly ONE decision: is this phase a hard gate? Promoting that single boolean from "logged-only" to "authoritative (with the in-process map as fallback + floor)" is a 1-decision change with a trivial rollback (`WICKED_LOOM_CUTOVER=off`) and a strong, testable invariant (the park can only be ADDED, never removed). It delivers the real value of "loom decides where the human stops" without touching the state machine.

**State-model mapping decision (the hard design problem, answered):** **Keep `ProjectState` authoritative; delegate only the gate/park DECISION to loom; do NOT mirror loom's flowstate into ProjectState, and do NOT run `loom flow run` at all in this increment.** Garden does NOT shell `loom flow run` here — it computes the park decision in-process from `flow_compiler.compile_flow(archetype)` (the §3.1 seam), which reproduces loom's `_is_hard` park rule (`hitl.startswith("hard:")`) by construction. This means: (a) no second state store is created or reconciled; (b) the decision is the SAME decision loom's `flow run` would make at that phase, so when a later increment does adopt `loom flow`, the park behavior is already proven identical; (c) zero new failure modes — the only new dependency is the compiled flow-def, which already exists and is already contract-tested against `_HARD_GATE_PHASES`. The full `loom flow run` execution and any flowstate mirroring are explicitly the NEXT increment, gated on this one being proven.

---

## File Structure

```
wicked-garden/
├── scripts/
│   └── crew/
│       └── phase_manager.py        # MODIFY — _is_hard_gate gains a loom-authoritative
│                                    #   source (resolve_hard_gate): loom verdict wins when
│                                    #   present, in-process map is fallback + floor. The
│                                    #   ValueError guard, ProjectState, advancement: UNCHANGED.
└── tests/
    └── crew/
        └── test_loom_flow_contract.py  # MODIFY (append) — authoritative-decision tests:
                                         #   loom-says-hard parks; loom-unavailable falls back to
                                         #   the map; loom-says-not-hard can NEVER remove a
                                         #   map-asserted park (the fail-closed floor); the
                                         #   ValueError + confirmation contract is preserved.
```

**Responsibilities (one per file, justifying the layout):**
- `scripts/crew/phase_manager.py` (modified) = keeps its DomainStore `ProjectState` authority and one-phase advancement. The only change is the *source* of the hard-gate boolean: a new `resolve_hard_gate(state, phase)` helper combines loom's verdict (authoritative when present) with the in-process map (fallback + floor), and `approve_phase`'s guard calls it instead of `_is_hard_gate` directly. `_is_hard_gate` and `_HARD_GATE_PHASES` remain — they are the fallback and the floor, not dead code.
- `tests/crew/test_loom_flow_contract.py` (modified) = extends the existing flow parity contract with the authoritative-decision behavior. The existing 3 tests (compiled-flow gate-phase parity, non-hard archetypes have no hard phase, `off` preserves the in-process `ValueError`) STAY GREEN — they still hold under the authoritative source.

Why no new file: this increment is one decision-source switch inside one function plus its helper. Adding a module would violate YAGNI. The compiler (`flow_compiler.py`) is already the loom-side decision derivation; `phase_manager` already imports the loom seam (`_loom`, `_loom_confirms_hard_gate`). The change lives where the decision is consumed.

**The decision-resolution rule this plan implements** (the heart of the increment):

```
resolve_hard_gate(state, phase):
    in_process = _is_hard_gate(state, phase)          # the floor (and fallback)
    loom = _loom_confirms_hard_gate(archetype, phase) # None when loom unavailable/uncertain
    if loom is None:
        return in_process                              # fail-soft: map is authoritative
    if loom != in_process:
        <emit wicked.loom.parity_mismatch>             # divergence signal (retained)
    return loom or in_process                          # loom authoritative, but can only ADD
                                                       # a park, never remove the floor's park
```

`loom or in_process` is the fail-closed floor: the park is required if EITHER source says hard. Loom-authoritative means loom can turn a non-park into a park; it can never turn the in-process map's park into a non-park. That is the invariant the strongest test pins.

---

## Task 1: Promote the flow surface to loom-authoritative for the hard-gate park decision

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/crew/phase_manager.py` (add `resolve_hard_gate`; rewire `approve_phase`'s mirror + guard. `_is_hard_gate`, `_HARD_GATE_PHASES`, `ProjectState`, advancement: unchanged.)
- Modify: `~/Projects/wicked-garden/tests/crew/test_loom_flow_contract.py` (append the authoritative-decision tests)

The current `approve_phase` runs a **read-only** parity mirror (lines 359–377): it computes `loom_says` and `in_proc_says`, logs a mismatch, but the guard at line 380 calls `_is_hard_gate(state, phase)` — purely the in-process map. This task makes loom authoritative by routing the guard through a new `resolve_hard_gate` that returns `loom or in_process` when loom answers (fail-closed floor), and `in_process` when loom is unavailable (fail-soft fallback). The mismatch signal is folded into `resolve_hard_gate`.

- [ ] **Step 1: Write the failing tests (append to `tests/crew/test_loom_flow_contract.py`)**

Append the following class to the existing file (keep the 3 existing tests + imports + `_EXPECTED_GATE_PHASES` intact). These tests patch `phase_manager._loom_confirms_hard_gate` (the loom-verdict seam) and stub `save_project_state` so they are hermetic — no real loom, no disk.

```python
class FlowAuthoritativeParkDecision(unittest.TestCase):
    """Flow surface cutover: loom is AUTHORITATIVE for the hard-gate park
    decision. loom-says-hard adds a park; loom-unavailable falls back to the
    in-process map; loom-says-not-hard can NEVER remove a map-asserted park
    (the fail-closed floor). The ValueError + confirmation contract is preserved.
    """

    def setUp(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        os.environ.pop("WICKED_LOOM_CUTOVER", None)

    def _migrate_state(self, phase="cutover"):
        return pm.ProjectState(
            name="m1", current_phase=phase,
            created_at=pm.get_utc_timestamp(),
            phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
            extras={"v11_archetype": "migrate"})

    def _build_state(self, phase="plan"):
        return pm.ProjectState(
            name="b1", current_phase=phase,
            created_at=pm.get_utc_timestamp(),
            phase_plan=["plan", "implement", "test", "review"],
            extras={"v11_archetype": "build"})

    def test_loom_authoritative_hard_gate_requires_confirmation(self):
        # loom says cutover is hard; in-process map ALSO says hard. Guard fires.
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_loom_adds_a_park_the_in_process_map_does_not_assert(self):
        # loom says build.review is hard (it is not in _HARD_GATE_PHASES). loom is
        # authoritative -> the guard fires even though the in-process map is silent.
        st = self._build_state("review")
        self.assertFalse(pm._is_hard_gate(st, "review"))  # floor: not hard
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "review")

    def test_loom_says_not_hard_CANNOT_remove_a_map_asserted_park(self):
        # THE FAIL-CLOSED FLOOR: loom says cutover is NOT hard, but the in-process
        # map asserts it IS. The park MUST still fire — loom can add, never remove.
        st = self._migrate_state("cutover")
        self.assertTrue(pm._is_hard_gate(st, "cutover"))  # floor: hard
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_loom_unavailable_falls_back_to_in_process_map(self):
        # loom returns None (unavailable/uncertain) -> the in-process map is
        # authoritative (fail-soft). cutover is hard in the map -> guard fires.
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=None), \
             patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def test_non_hard_phase_advances_when_both_sources_agree_not_hard(self):
        # build.plan is not hard in either source -> no guard, normal advance.
        st = self._build_state("plan")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False), \
             patch.object(pm, "save_project_state", lambda s: None):
            _, next_phase = pm.approve_phase(st, "plan")
        self.assertEqual(next_phase, "implement")

    def test_hard_gate_with_confirmation_advances(self):
        # The confirmation contract is preserved: confirmed_by + evidence -> advance.
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True), \
             patch.object(pm, "save_project_state", lambda s: None):
            state, next_phase = pm.approve_phase(
                st, "cutover", confirmed_by="oncall-jane",
                confirmation_evidence="https://dash/rollback-drill-42")
        self.assertEqual(next_phase, "contract")
        self.assertEqual(state.phases["cutover"].status, "approved")

    def test_resolve_hard_gate_returns_floor_when_loom_none(self):
        st = self._migrate_state("cutover")
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=None):
            self.assertTrue(pm.resolve_hard_gate(st, "cutover"))
            self.assertFalse(pm.resolve_hard_gate(st, "plan"))

    def test_resolve_hard_gate_is_or_of_both_sources(self):
        st = self._build_state("review")  # not hard in the map
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=True):
            self.assertTrue(pm.resolve_hard_gate(st, "review"))  # loom adds it
        with patch.object(pm, "_loom_confirms_hard_gate", return_value=False):
            self.assertFalse(pm.resolve_hard_gate(st, "review"))  # neither
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_flow_contract.py::FlowAuthoritativeParkDecision -v`
Expected: FAIL — `test_loom_adds_a_park_the_in_process_map_does_not_assert` raises no `ValueError` (the current guard reads only the in-process map, which is silent on `build.review`), and `test_resolve_hard_gate_*` error with `AttributeError: module 'phase_manager' has no attribute 'resolve_hard_gate'`. The floor/fallback tests may already pass against the current guard.

- [ ] **Step 3: Edit `phase_manager.py` — add `resolve_hard_gate`**

Insert this function immediately after `_is_hard_gate` (after line 332, before `approve_phase`). It folds the mismatch signal in and implements the fail-closed-floor rule:

```python
def resolve_hard_gate(state: ProjectState, phase: str) -> bool:
    """Authoritative hard-gate decision for ``(archetype, phase)`` (flow cutover).

    The flow surface is now loom-AUTHORITATIVE for *where the human stops*:
    loom's verdict (derived from the compiled flow-def, which reproduces loom's
    own ``hitl.startswith("hard:")`` park rule) decides whether this phase is a
    hard gate — WHEN loom is available. The in-process ``_HARD_GATE_PHASES`` map
    is two things at once:

      - the FALLBACK: when loom is unavailable/uncertain
        (``_loom_confirms_hard_gate`` returns None — off, auto-unresolvable, or
        a compile error), the map answers (fail-soft, rollback-safe).
      - the FLOOR: even when loom answers, the resolved decision is
        ``loom or in_process`` — loom may ADD a park the map omits, but can
        NEVER remove a park the map asserts. This is the fail-closed posture of
        the flow surface: we never silently skip a human-in-the-loop stop that
        the in-process doctrine demands. A loom that (wrongly) says "not hard"
        for migrate.cutover cannot disarm the cutover gate.

    A divergence (loom != in_process, with loom present) is surfaced as a
    ``wicked.loom.parity_mismatch`` signal — retained from the parity mirror —
    so operators see drift even though the resolved decision is the safe OR.
    """
    in_process = _is_hard_gate(state, phase)
    archetype = (state.extras or {}).get("v11_archetype")
    if not archetype:
        return in_process

    loom_says = _loom_confirms_hard_gate(archetype, phase)
    if loom_says is None:
        return in_process  # fail-soft: in-process map is authoritative

    if loom_says != in_process:
        print(f"[wicked-garden] loom/in-process hard-gate parity mismatch: "
              f"archetype={archetype} phase={phase} "
              f"loom={loom_says} in_process={in_process}", file=sys.stderr)
        _bus_emit_safe(
            "wicked.loom.parity_mismatch",
            {"project_id": state.name, "archetype": archetype,
             "phase": phase, "loom": loom_says, "in_process": in_process,
             "resolved": loom_says or in_process},
            chain_id=f"{state.name}.{archetype}.{phase}.parity",
        )
    # loom authoritative, but fail-closed floor: a park is required if EITHER
    # source says hard. loom can add a park; it can never remove the map's.
    return loom_says or in_process
```

- [ ] **Step 4: Edit `approve_phase` — replace the read-only mirror block with the authoritative call**

In `approve_phase`, DELETE the read-only parity-mirror block (lines 359–377, from `# --- loom cutover mirror (flow surface) ----` through the closing `# ----`), because its mismatch-signal responsibility now lives inside `resolve_hard_gate`. Then change the guard at line 380 from `_is_hard_gate(state, phase)` to `resolve_hard_gate(state, phase)`.

Replace this (the read-only mirror, lines 359–377):

```python
    # --- loom cutover mirror (flow surface) ----------------------------------
    # Cross-check loom's park decision against the in-process map. A DISAGREEMENT
    # is surfaced (stderr + bus emit) but does NOT change behavior — the
    # in-process guard below stays authoritative during cutover (rollback-safe).
    archetype_for_parity = (state.extras or {}).get("v11_archetype")
    if archetype_for_parity:
        loom_says = _loom_confirms_hard_gate(archetype_for_parity, phase)
        in_proc_says = _is_hard_gate(state, phase)
        if loom_says is not None and loom_says != in_proc_says:
            print(f"[wicked-garden] loom/in-process hard-gate parity mismatch: "
                  f"archetype={archetype_for_parity} phase={phase} "
                  f"loom={loom_says} in_process={in_proc_says}", file=sys.stderr)
            _bus_emit_safe(
                "wicked.loom.parity_mismatch",
                {"project_id": state.name, "archetype": archetype_for_parity,
                 "phase": phase, "loom": loom_says, "in_process": in_proc_says},
                chain_id=f"{state.name}.{archetype_for_parity}.{phase}.parity",
            )
    # -------------------------------------------------------------------------

    # Hard-gate guard: enforce explicit confirmation at runtime.
    if _is_hard_gate(state, phase):
```

with this (the authoritative path — mirror responsibility moved into the helper):

```python
    # --- loom cutover (flow surface): loom-AUTHORITATIVE park decision -------
    # resolve_hard_gate consults loom first (authoritative when available) and
    # falls back to the in-process map, with that map as the fail-closed floor
    # (loom can ADD a park, never remove one). It also emits the retained
    # wicked.loom.parity_mismatch signal on divergence. The ValueError guard,
    # confirmation requirement, ProjectState, and advancement are UNCHANGED.
    # -------------------------------------------------------------------------

    # Hard-gate guard: enforce explicit confirmation at runtime.
    if resolve_hard_gate(state, phase):
```

> Implementer note: this is the ONLY behavioral change. The `confirmed_by`/`confirmation_evidence` requirement (lines 381–399), the `approval_record`, the `next_phase` resolution from `phase_plan`, `save_project_state`, and every bus emit (`hard_gate_passed`, `advanced`, `completed`) stay exactly as they are. `_is_hard_gate` is still called — inside `resolve_hard_gate` — so it is not dead (R1). `_HARD_GATE_PHASES` is still the source for `_is_hard_gate` and for `flow_compiler` (the single source of truth the compiled flow-def is derived from), so it is not dead either. Do NOT touch `start_phase`/`complete_phase`/`skip_phase`/`is_complete` or the CLI.

- [ ] **Step 5: Run the tests to verify they pass (new + existing)**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_flow_contract.py -v`
Expected: PASS — the 8 new `FlowAuthoritativeParkDecision` tests AND the 3 existing tests (`test_compiled_flow_gate_phase_matches_in_process_map`, `test_non_hard_archetypes_compile_no_hard_phase`, `test_approve_phase_in_process_authority_unchanged_when_loom_off`). The `off` test still passes because `_loom_confirms_hard_gate` returns `None` under `off` (`_loom.use_loom()` is False), so `resolve_hard_gate` falls back to the in-process map — identical to today.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/crew/phase_manager.py tests/crew/test_loom_flow_contract.py
git commit -m "feat(loom-flow-cutover): loom-authoritative hard-gate park decision (in-process map is fallback + fail-closed floor)"
```

---

## Task 2: Full-suite green + rollback proof + handoff note

**Files:** none (verification only).

- [ ] **Step 1: Run the full garden suite**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/ -q`
Expected: PASS — no regressions. The cutover defaults to `auto`; in CI loom is unresolvable, so `_loom_confirms_hard_gate` returns `None` and `resolve_hard_gate` falls back to the in-process map — every existing test exercises the unchanged behavior. New count: the baseline was **506** collected; this plan adds **8** tests to `test_loom_flow_contract.py` → **514** collected. Report the exact `passed` total.

- [ ] **Step 2: Prove the fail-closed floor holds (the load-bearing invariant)**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_flow_contract.py -k "CANNOT_remove or unavailable_falls_back or in_process_authority_unchanged" -v`
Expected: PASS — loom-says-not-hard cannot remove a map-asserted park; loom-unavailable falls back to the map; `off` preserves the in-process `ValueError`. The `migrate.cutover` / `incident.mitigate` human-in-the-loop guarantee never regresses.

- [ ] **Step 3: Prove rollback works**

Run: `cd ~/Projects/wicked-garden && WICKED_LOOM_CUTOVER=off python3 -m pytest tests/crew/test_loom_flow_contract.py -q`
Expected: PASS — with the flag off, `_loom_confirms_hard_gate` returns `None`, `resolve_hard_gate` is purely the in-process map, and the flow surface behaves exactly as before the cutover. The increment is fully reversible by a single env var (no code revert).

- [ ] **Step 4: Confirm no dead code, no signature drift**

Run: `cd ~/Projects/wicked-garden && grep -n "_is_hard_gate\|_HARD_GATE_PHASES\|resolve_hard_gate" scripts/crew/phase_manager.py scripts/crew/flow_compiler.py`
Expected: `_is_hard_gate` is called inside `resolve_hard_gate` (live); `_HARD_GATE_PHASES` is read by `_is_hard_gate` and imported by `flow_compiler` (live); `resolve_hard_gate` is called by `approve_phase` (live). No orphan.

- [ ] **Step 5: Report (no autonomous push)**

Report to the operator: the flow surface is now loom-AUTHORITATIVE for the hard-gate park decision, behind the `WICKED_LOOM_CUTOVER` flag, with the in-process `_HARD_GATE_PHASES` map as the fail-soft fallback AND the fail-closed floor (loom can add a park, never remove one). `ProjectState`, one-phase advancement, and the `ValueError`/confirmation contract are unchanged. Rollback = `WICKED_LOOM_CUTOVER=off`. The flow CONTRACT phase (deleting the in-process map) and the full `ProjectState`→loom-`flowstate` migration are DEFERRED — run them only after this is proven in production. Do NOT run `npm publish`, `/wg-release`, or delete `_HARD_GATE_PHASES` / `_is_hard_gate` in this plan.

---

## Self-Review

**1. Spec coverage** — checked against the prompt's deliverables:

| Requirement | Where realized | Status |
|---|---|---|
| Honest assessment: full vs scoped-down, recommend smallest valuable low-risk increment | "Honest assessment" section — full cutover NOT advisable; recommend the park-decision-only increment | ✓ |
| State-model mapping decision (ProjectState authoritative? mirror loom's flowstate? delegate only the decision?) | "State-model mapping decision" — ProjectState stays authoritative; delegate ONLY the park decision; do NOT mirror flowstate; do NOT run `loom flow run`; compute the decision in-process from `flow_compiler` | ✓ |
| Flag-gated | `WICKED_LOOM_CUTOVER` reused via `_loom.use_loom()` inside `_loom_confirms_hard_gate`; `off` → fallback to in-process | ✓ |
| Parity-contract-test | Existing 3 tests retained + 8 added; `test_compiled_flow_gate_phase_matches_in_process_map` is the parity contract | ✓ |
| Fail-soft (in-process stays as fallback) | `resolve_hard_gate` returns `in_process` when `_loom_confirms_hard_gate` is `None` | ✓ |
| In-process NOT deleted (separate contract phase) | `_HARD_GATE_PHASES` + `_is_hard_gate` retained as fallback + floor; deletion explicitly out of scope | ✓ |
| Preserve hard-gate guarantee (ValueError on unapproved hard gate must not regress) | Guard unchanged except its boolean source; `test_loom_says_not_hard_CANNOT_remove_a_map_asserted_park` + `test_loom_unavailable_falls_back` + the existing `off` test pin it | ✓ |
| Fail-closed posture | `loom or in_process` floor — a park is required if EITHER says hard; loom can only ADD | ✓ |
| Out of scope stated: contract phase, full ProjectState→flowstate migration, broader §6 | "Out of scope" section enumerates all three explicitly | ✓ |
| Bite-sized TDD with complete code + exact pytest commands + expected output | Task 1 steps 1–6, Task 2 steps 1–5 | ✓ |
| Self-Review + Execution Handoff | this section + below | ✓ |

**2. Placeholder scan** — No `TBD`/`TODO`/"add error handling"/"similar to Task N". Every code step shows complete, runnable code (the full `resolve_hard_gate`, the exact old→new `approve_phase` block, all 8 test methods); every run step shows the exact `python3 -m pytest …` command + expected pass/fail with named tests. ✓

**3. Type consistency** —
- `resolve_hard_gate(state: ProjectState, phase: str) -> bool` — consumed by `approve_phase`'s guard (`if resolve_hard_gate(state, phase):`) and asserted directly in `test_resolve_hard_gate_*`. ✓
- `_loom_confirms_hard_gate(archetype: str, phase: str) -> Optional[bool]` — already exists (lines 72–88); `resolve_hard_gate` reads `None` (fallback) vs `True`/`False` (authoritative). Patched in tests via `patch.object(pm, "_loom_confirms_hard_gate", ...)`. ✓
- `_is_hard_gate(state: ProjectState, phase: str) -> bool` — already exists (327–332); called by `resolve_hard_gate` and directly in tests (`pm._is_hard_gate(st, "review")`). ✓
- `approve_phase(...) -> Tuple[ProjectState, Optional[str]]` — signature and return UNCHANGED; tests read `_, next_phase = pm.approve_phase(...)` and `state.phases[...].status`. ✓
- `_bus_emit_safe(event_type, payload, *, chain_id)` — reused verbatim inside `resolve_hard_gate` with the same kwargs as the deleted mirror. ✓

**One self-review note (no fix needed):** the existing read-only mirror emitted `wicked.loom.parity_mismatch` with payload keys `{project_id, archetype, phase, loom, in_process}`; `resolve_hard_gate` keeps those and ADDS `resolved` (the OR). This is additive — no downstream consumer breaks (the bus is fire-and-forget, schema-tolerant), and it makes the authoritative decision auditable. Retained intentionally.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-08-wicked-loom-flow-cutover.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`. This is a 2-task plan (1 implementation + 1 verification); a single subagent per task is appropriate.
2. **Inline Execution** — execute in this session with checkpoints. REQUIRED SUB-SKILL: `superpowers:executing-plans`.

Notes for the executor:
- Execution happens in **wicked-garden** (`~/Projects/wicked-garden`), editing `scripts/crew/phase_manager.py` and `tests/crew/test_loom_flow_contract.py` only. The in-process `_HARD_GATE_PHASES` map and `_is_hard_gate` are **left in place** as the fallback + floor — do NOT delete them; that is the flow contract phase.
- No prerequisite on a published loom: the decision is computed in-process from `flow_compiler.compile_flow` (already built and contract-tested). Garden does NOT shell `loom flow run` in this increment, so `wicked-loom@0.2.0` is not required for the tests (the existing `_loom.use_loom()` gate still governs whether loom's verdict is consulted at all — under `auto` in CI, loom is unresolvable → fallback).
- Rollback during transition is a single env var: `WICKED_LOOM_CUTOVER=off` returns the flow surface to the pure in-process decision. No code revert needed.
- The flow CONTRACT phase (deleting `_HARD_GATE_PHASES`/`_is_hard_gate`) and the full `ProjectState`→loom-`flowstate` migration (adopting loom's whole-flow execution model) are the **next** plans — run them only after this park-decision cutover is proven in production.

**Which approach?**
