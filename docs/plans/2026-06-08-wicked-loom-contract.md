# wicked-loom — Contract Phase (garden-side strangler migration) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the strangler. The **cutover** (`docs/plans/2026-06-08-wicked-loom-cutover.md`) gave garden's `resolve` and `gate` surfaces a *loom-first head* that **falls back to an unchanged in-process body** when loom is unresolvable or errors. That fallback was the cutover's whole safety net — rollback was `WICKED_LOOM_CUTOVER=off`. The cutover is now proven; this **contract** phase deletes the now-redundant in-process re-derivation body so **loom is authoritative** for both shimmed surfaces. The in-process re-derivation code (the `_run` + JSON-parse body of `cross_check`; the `allow_npx=True` resolution ladder fallback in `resolve_vault`) is **removed**, not flag-flipped.

**Critical invariant (the whole point of the gate):** honest evidence is preserved verbatim. Removing the in-process fallback must NEVER open a vacuous-pass path. With loom unresolvable / erroring, the gate MUST fail **closed** (`available: False`, `gate: "unavailable"`, `satisfied: false`) — exactly as the in-process body did when the vault was unresolvable. We are deleting a *redundant re-derivation engine*, not a *fail-closed guard*. I2 (fail-closed) holds unchanged.

**Scope — the SHIMMED surfaces ONLY (`resolve` + `gate`):**
- **`cross_check` (gate):** remove the in-process `_run(...)` + JSON-parse re-derivation body that the loom head currently falls through to. loom `gate` becomes the sole re-derivation path. On any loom error/unresolvable → fail-closed `available: False` / `overall: "ERROR"`.
- **`resolve_vault` (resolve):** make loom authoritative for the `allow_npx=True` (run-the-vault) path — remove the redundant in-process npx-bearing ladder fallback. **KEEP** the in-process ladder for the `allow_npx=False` path because `vault_available()` calls `resolve_vault(allow_npx=False)` to detect a **concrete** install — loom's `resolve` would report the npx last-resort as resolvable and corrupt that "installed" signal (the cutover's `allow_npx` boundary, plan line 533). So `vault_available()` stays in-process and unbroken.
- **The flag `WICKED_LOOM_CUTOVER`:** kept as a documented **emergency disable**, not removed. There is no longer an in-process gate to "fall to", so `off`/`auto`-unresolvable now mean *the loom path is not taken → the surface is unavailable → the gate fails closed*. `off` is therefore a coarse "stop using loom" kill that **fails closed** (never a vacuous pass), parallel to `WICKED_VAULT_BIN=""`. Decision + justification below.

**Out of scope (DO NOT TOUCH — future increments, NOT shimmed by the cutover):**
- The **flow surface** (`phase_manager.approve_phase`'s loom *parity mirror* + `flow_compiler.py`). The cutover made this a **read-only parity mirror** — it never *replaced* an in-process path, it only cross-checks the park-at-hard-gate decision and emits a `wicked.loom.parity_mismatch` event. There is no in-process re-derivation body to delete here. `phase_manager`'s DomainStore `ProjectState` storage is the STAY surface (spec §6). LEAVE the mirror, `flow_compiler`, and all flow contract tests intact.
- The broader spec §6 inventory the cutover did NOT shim: `phase_manager` storage move to loom, deletion of `_integration_resolver.py` / `_capability_resolver.py` / `_capability_registry.py`, the `bootstrap.py` peer-detect → loom compose split, the `_bus.py` consumer/projector split, the `_event_*` trio. **All future increments. LEAVE ALONE.**
- The **compiler** (`scripts/compiler/**`) — self-contained, resolves the vault directly via npx, imports nothing from the garden (AST-enforced). Untouched.
- The **bootstrap loom peer-probe** (`_check_loom_dependency`) — its detection logic stays (compose is a future increment). Only its prose claim "garden falls back to its in-process runtime when loom is absent" is corrected (no longer true post-contract).

**Tech Stack:** Python 3.9+ (stdlib only — garden's hook discipline; loom is reached as a subprocess, never imported). `pytest` (`testpaths = ["tests"]`; `tests/conftest.py` puts `scripts/` on `sys.path[0]`). Tests inject the loom subprocess runner (mock `_loom._default_run` / patch `_loom.resolve_loom`) so **no test spawns a real loom or touches the network** — CI stays Python-only.

**Bulletproof standards:** R1–R6 (no dead code — the removed in-process body is dead once loom is authoritative; no swallowed errors — loom errors surface as fail-closed verdicts, never silent pass). T1–T6 (determinism, isolation, single-assertion focus, descriptive names, provenance). The fail-closed invariant gets the strongest coverage: a test proving loom-unresolvable → `unavailable`, never a pass.

---

## File Structure

```
wicked-garden/
├── scripts/
│   ├── _loom.py                 # MODIFY — docstrings only: use_loom()/cutover_mode()
│   │                            #   no longer describe an "in-process fallback"; off now
│   │                            #   = loom disabled = fail-closed for shimmed surfaces.
│   │                            #   (Logic unchanged — the flag semantics are unchanged;
│   │                            #    only the CALLERS stop having an in-process body.)
│   └── qe/
│       └── vault_gate.py        # MODIFY — DELETE the in-process re-derivation body of
│                                #   cross_check (the loom head becomes the whole function);
│                                #   DELETE the allow_npx=True in-process ladder fallback in
│                                #   resolve_vault (loom authoritative), KEEP the allow_npx=False
│                                #   ladder for vault_available(). _run() is deleted (dead).
├── hooks/scripts/
│   └── bootstrap.py             # MODIFY — prose only: _check_loom_dependency message no longer
│                                #   claims an in-process fallback (loom is now load-bearing).
├── docs/
│   └── required-peers.md        # MODIFY — loom row + load-bearing note: loom is the runtime,
│                                #   not a shim; the in-process fallback is gone post-contract.
└── tests/
    ├── conftest.py              # MODIFY — drop the WICKED_LOOM_CUTOVER=off autouse default for
    │                            #   the gate/resolve surfaces; tests now exercise the loom path
    │                            #   via injected/mocked runners. (Keep path ordering + bus reset.)
    ├── qe/
    │   ├── test_loom_gate_contract.py   # REPLACE — parity (loom==in-process) tests are MOOT
    │   │                                #   (no in-process to compare). Rewrite as loom-AUTHORITATIVE:
    │   │                                #   loom is the only re-derivation path; fail-closed when
    │   │                                #   loom absent/errors. KEEP a strong fail-closed test.
    │   └── test_vault_gate.py           # MODIFY — the in-process-path unit tests that relied on
    │                                    #   mocking vg._run / the in-process cross_check body are
    │                                    #   reframed to drive the loom path (mock the loom runner).
    │                                    #   Keep the real-vault VaultBackedGateTests (skip-guarded).
    └── crew/
        └── test_loom_resolve_contract.py # REPLACE — parity tests are moot. Rewrite as loom-
                                          #   authoritative resolve: loom is the only resolve path
                                          #   for allow_npx=True; loom-unresolvable → None (no
                                          #   in-process npx fallback). vault_available() (allow_npx
                                          #   =False) still resolves in-process — assert that.
```

**Responsibilities after the contract:**
- `resolve_vault(allow_npx=True)` = *ask loom where the vault is.* loom authoritative; loom-unresolvable → None (fail-closed). No in-process npx ladder on this path.
- `resolve_vault(allow_npx=False)` = *is a concrete vault install present?* in-process ladder (env → config → PATH → node_modules; **no npx, no loom**). This is `vault_available()`'s probe — UNCHANGED.
- `cross_check` = *re-derive the verdict via loom `gate`.* loom is the sole re-derivation engine; any loom error → `available: False` (fail-closed). No in-process `_run`/parse body.
- `gate_satisfied` = unchanged structure: probe `resolve_vault(project_dir)` (now loom-routed) → `cross_check` → fail-closed when unavailable. Inherits the loom path transparently.

---

## Flag decision (justified, per the prompt)

**KEEP `WICKED_LOOM_CUTOVER`; redefine `off` as a documented emergency disable that FAILS CLOSED.** Rationale:

- The flag's *logic* (`_loom.use_loom`: `off`→False, `on`→True, `auto`→resolvable) is unchanged. What changes is what "loom not used" *means* to the callers. Pre-contract: fall to the in-process body. Post-contract: there is no in-process body — so "loom not used" means the shimmed surface is **unavailable**, and the gate **fails closed** (I2). That is the only honest meaning left.
- Removing the flag entirely would discard a coarse operational kill-switch with zero cost to keep. Keeping it gives operators a one-env-var way to stop garden from shelling out to loom during an incident (e.g. a wedged `npx`), accepting that gating then fails closed until loom is restored. That matches the vault's own `WICKED_VAULT_BIN=""` kill-switch posture: disable cleanly, fail closed, never thrash, never vacuous-pass.
- We document the new semantics in `_loom.py` docstrings + `required-peers.md` so no one reads `off` as "safe in-process mode" (it no longer exists). The bootstrap probe already treats `off`/`WICKED_LOOM_BIN` set as "operator is driving deliberately, don't nag" — that stays correct.

Net: loom is now a **load-bearing required peer for gating**. `off` is an emergency disable, not a fallback selector.

---

## Task 1: Contract the `gate` surface — `cross_check` loom-authoritative, in-process body deleted

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/qe/vault_gate.py` (`cross_check`; delete in-process body + `_run`)
- Replace: `~/Projects/wicked-garden/tests/qe/test_loom_gate_contract.py`
- Modify: `~/Projects/wicked-garden/tests/qe/test_vault_gate.py`

The cutover's `cross_check` is: loom head → (on success) return mapped verdict; (on loom error) **fall through** to `args = [...]; run = _run(args, ...); parse`. The contract deletes everything from `args = ["cross-check", ...]` onward, plus the now-unused `_run` helper. The loom head's *trailing comment* ("loom errored -> fall through to in-process re-derivation") changes to a **fail-closed return**.

- [ ] **Step 1: Rewrite the gate contract test as loom-authoritative (TDD — write the new spec first)**

Replace `tests/qe/test_loom_gate_contract.py` entirely. The parity tests (loom==in-process) are moot — there is no in-process path. The new tests assert: loom is the ONLY re-derivation path; fail-closed when loom errors/unresolvable; `--with-attestations` still forwarded; the `gate: "unavailable"` mapping still fails closed. Hermetic — mock `_loom._default_run` / patch `_loom.resolve_loom`, never real npx.

```python
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _loom  # noqa: E402
import vault_gate as vg  # noqa: E402

_PROJECT = Path("/tmp/proj-loom-gate")


class GateLoomAuthoritative(unittest.TestCase):
    """Contract phase: loom `gate` is the SOLE re-derivation path. The
    in-process cross_check body is gone. loom unresolvable/errors → the gate
    is unavailable and FAILS CLOSED — never a vacuous pass (I2)."""

    def setUp(self):
        # Default the suite to off; each test opts the loom path on explicitly.
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN"):
            os.environ.pop(v, None)
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def _loom_gate_runner(self, overall):
        def fake_run(prefix, args, timeout):
            import json
            verdict = {"satisfied": overall == "PASS", "overall": overall,
                       "gate": "vault-cross-check", "claims": [{"id": "tests-pass"}]}
            return {"exit_code": 0 if overall == "PASS" else 1,
                    "stdout": json.dumps({"gate": verdict}), "stderr": "", "error": None}
        return fake_run

    def test_loom_pass_is_the_only_path(self):
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("PASS")):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertTrue(cc["available"])
        self.assertEqual(cc["overall"], "PASS")
        self.assertEqual(cc["claims"], [{"id": "tests-pass"}])

    def test_loom_reject_surfaced(self):
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("REJECT")):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertTrue(cc["available"])
        self.assertEqual(cc["overall"], "REJECT")

    def test_loom_gate_unavailable_maps_to_fail_closed(self):
        # loom reached, but vault unresolvable behind it -> gate: unavailable.
        def fake_run(prefix, args, timeout):
            import json
            return {"exit_code": 1, "stdout": json.dumps(
                {"gate": {"gate": "unavailable", "error": "no vault"}}),
                "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_loom_error_fails_closed_no_in_process_pass(self):
        # loom resolves but the subprocess errors (timeout/not-found). There is
        # NO in-process fallback now -> cross_check must report unavailable.
        def boom(prefix, args, timeout):
            return {"exit_code": None, "stdout": "", "stderr": "",
                    "error": "loom call exceeded 120s"}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", boom):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_loom_unresolvable_fails_closed(self):
        # auto + loom unresolvable -> the loom path is not taken; with no
        # in-process body, cross_check reports unavailable (fail-closed).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None):
            cc = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertFalse(cc["available"])
        self.assertEqual(cc["overall"], "ERROR")

    def test_gate_satisfied_fails_closed_when_loom_absent(self):
        # The load-bearing fail-closed invariant end-to-end: loom unresolvable
        # AND vault unresolvable -> gate_satisfied is unavailable, NOT a pass.
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        os.environ["WICKED_VAULT_BIN"] = ""  # vault kill-switch too
        with patch.object(_loom, "resolve_loom", return_value=None):
            verdict = vg.gate_satisfied(_PROJECT, "build-1", "test")
        self.assertFalse(verdict["satisfied"])
        self.assertEqual(verdict["gate"], "unavailable")
        self.assertFalse(verdict["re_derived"])

    def test_with_attestations_forwarded_to_loom(self):
        seen = {}

        def fake_run(prefix, args, timeout):
            import json
            seen["args"] = args
            return {"exit_code": 0, "stdout": json.dumps(
                {"gate": {"satisfied": True, "overall": "PASS"}}), "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            vg.cross_check("build-1", "review", project_dir=_PROJECT, with_attestations=True)
        self.assertIn("--with-attestations", seen["args"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test — confirm it fails on the right tests**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/qe/test_loom_gate_contract.py -v`
Expected: `test_loom_unresolvable_fails_closed` and `test_loom_error_fails_closed_no_in_process_pass` FAIL (the current code, on loom-unresolvable/error, falls through to the in-process `_run` body, which — with a mocked-away vault or real npx — does NOT return the fail-closed `available: False` these tests demand). The others may pass against the current loom head. (Note: this test sets `WICKED_LOOM_CUTOVER=on` in setUp, overriding the autouse `off` default that we remove in Task 4.)

- [ ] **Step 3: Edit `vault_gate.py` — delete the in-process re-derivation body of `cross_check` and the `_run` helper**

In `cross_check`, the loom head currently ends with `# loom errored -> fall through to in-process re-derivation (fail-soft).` and then the function continues with the in-process body. Replace the END of the loom head and DELETE the in-process body. The new `cross_check` body is **only** the loom head, with the trailing fall-through turned into a fail-closed return:

```python
def cross_check(
    scope: str,
    phase: str,
    *,
    project_dir: Optional[Path] = None,
    with_attestations: bool = False,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Run the produces re-derivation via ``wicked-loom gate`` and return its
    mechanical verdict.

    loom is the **sole** re-derivation engine (the in-process vault path was
    removed in the contract phase). loom re-hashes the recorded evidence and
    re-runs the verifier, mapping the result onto ``{available, overall,
    claims, ...}``.

    Fail-closed (I2): when loom is unresolvable, errors, or reports the vault
    unavailable behind it, ``available`` is False and ``overall`` is ERROR —
    we never invent a PASS. There is no in-process fallback; a missing loom is
    a missing gate, and a missing gate fails closed.
    """
    if _loom is None or not _loom.use_loom(project_dir=project_dir):
        # loom shim absent, or WICKED_LOOM_CUTOVER=off / auto-unresolvable.
        # No in-process re-derivation remains -> the gate is unavailable.
        return {"available": False, "overall": "ERROR",
                "error": "wicked-loom not in use (disabled or unresolvable)",
                "exit_code": None}

    loom_args = ["gate", phase, "--scope", scope]
    if with_attestations:
        loom_args.append("--with-attestations")
    out = _loom.run_json(loom_args, project_dir=project_dir, timeout=timeout)
    if out["error"] is not None or not isinstance(out.get("json"), dict):
        # loom unresolvable / timed out / non-JSON. Fail closed (I2).
        return {"available": False, "overall": "ERROR",
                "error": out.get("error") or "loom returned no usable verdict",
                "exit_code": out.get("exit_code")}

    verdict = out["json"].get("gate") or {}
    if verdict.get("gate") == "unavailable":
        # loom reached but the vault is unresolvable behind it -> fail closed.
        return {"available": False, "overall": "ERROR",
                "error": verdict.get("error", "vault unavailable via loom"),
                "exit_code": out.get("exit_code")}
    return {
        "available": True,
        "overall": verdict.get("overall", "ERROR"),
        "exit_code": out.get("exit_code"),
        "claims": verdict.get("claims", []),
        "mode": verdict.get("mode"),
        "contract_version": verdict.get("contract_version"),
        "detail": verdict.get("detail"),
        "raw": verdict,
    }
```

Then **delete the `_run` helper entirely** (the `def _run(...)` block under the `# Invocation` header) — it is now dead (R1: no dead code). Its sole caller was the deleted in-process `cross_check` body.

> Implementer note: keep the `_DEFAULT_TIMEOUT` constant (still used by the signature default). `subprocess` / `_argv_for` imports in `vault_gate.py` are still used by the `allow_npx=False` resolution ladder in `resolve_vault` (Task 2) — do NOT remove them. Confirm with a post-edit grep that `_run` has zero references.

- [ ] **Step 4: Reframe the in-process unit tests in `test_vault_gate.py`**

The real-vault `VaultBackedGateTests` (skip-guarded; resolves `WICKED_VAULT_BIN` / sibling checkout) drives `gate_satisfied` end-to-end. Post-contract, `gate_satisfied` → `cross_check` → loom (not the in-process `_run`). Those tests set `WICKED_VAULT_BIN` but do **not** set up loom — so with the autouse `off` default removed (Task 4) and `auto` resolving loom via npx on a dev box, they would try to shell a real loom. Guard them: skip unless a real loom is *also* resolvable, OR (simpler + hermetic) keep them pointed at the in-process vault by setting `WICKED_LOOM_CUTOVER=off` AND asserting the new fail-closed semantics. **Chosen approach:** these tests assert the *vault re-derivation contract*, which now lives in loom — so move that assertion to loom-backed coverage is out of scope (loom has its own suite). Here, mark `VaultBackedGateTests` to **also require a resolvable loom** and drive through it, OR skip when loom is absent. Concretely:

- In `VaultBackedGateTests.setUp`, after setting `WICKED_VAULT_BIN`, also require loom: add `WICKED_LOOM_CUTOVER` handling. Simplest hermetic fix that keeps the suite green on a Python-only CI: change the class skip guard to also skip when `_loom.resolve_loom(allow_npx=False)` is None (no concrete loom), since the gate now runs through loom. Update the skip reason to mention loom.
- The `RequiredFailClosedTests` (kill-switch `WICKED_VAULT_BIN=""`) currently assert `gate_satisfied` fails closed. With loom disabled too, they still must fail closed. Set `WICKED_LOOM_CUTOVER=off` in their `setUp` (alongside the vault kill-switch) so the gate is unambiguously unavailable; assert `gate: "unavailable"` unchanged. This keeps the anti-vacuous-PASS guarantee covered purely in-process (no loom, no vault → fail closed).
- The `ResolutionTests` (`resolve_vault` env cases) call `resolve_vault()` (allow_npx default True). Post-contract that is the loom-authoritative path. Set `WICKED_LOOM_CUTOVER=off` in their `setUp` so they exercise... no — `off` now makes `resolve_vault(allow_npx=True)` return None (loom disabled, no in-process fallback). These env-override tests (`WICKED_VAULT_BIN=/path`) are really testing the in-process ladder, which now only runs under `allow_npx=False`. **Reframe them to call `resolve_vault(allow_npx=False)`** (the concrete-install probe that keeps the in-process ladder). The `WICKED_VAULT_BIN` env override and `.mjs`→node and kill-switch cases all live on that path. Assert via `allow_npx=False`.

Apply these edits to `test_vault_gate.py`:
  1. `ResolutionTests`: change each `vg.resolve_vault()` → `vg.resolve_vault(allow_npx=False)` (these assert the in-process concrete-install ladder, which is what `vault_available` uses and what survives the contract). The empty-env kill-switch test already calls `vault_available()` (allow_npx=False) — keep it.
  2. `RequiredFailClosedTests.setUp`: add `os.environ["WICKED_LOOM_CUTOVER"] = "off"`; `tearDown` pops it. (Vault kill-switch + loom off → unambiguous fail-closed; the assertions are unchanged.)
  3. `VaultBackedGateTests`: change the class decorator skip to also require loom — replace `@unittest.skipIf(_locate_vault() is None, ...)` with a guard that skips when either the vault OR a concrete loom is unavailable, and set `WICKED_LOOM_CUTOVER` appropriately in setUp so the gate routes through the real loom. If wiring a real loom into this test proves heavy, the pragmatic alternative (allowed): keep `VaultBackedGateTests` skip-guarded on the vault as today but set `WICKED_LOOM_CUTOVER=off` in setUp and convert its three assertions to the fail-closed shape (since with loom off the gate is unavailable) — i.e. these become "vault present but loom off → fail-closed" coverage. **Pick whichever keeps CI green and hermetic; document the choice in the test docstring.**

> Implementer note: the goal is zero failures on a Python-only CI (no node, no npx, no loom). The cleanest path: drive the loom surface with MOCKED runners in `test_loom_gate_contract.py` (Step 1), and in `test_vault_gate.py` keep the in-process *resolution-ladder* tests (via `allow_npx=False`) plus the fail-closed tests (loom off + vault off). The real-subprocess `VaultBackedGateTests` stays skip-guarded so it never runs in plain CI.

- [ ] **Step 5: Run the gate tests**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/qe/test_loom_gate_contract.py tests/qe/test_vault_gate.py -v`
Expected: PASS. `_run` has no references (`grep -n "_run\b" scripts/qe/vault_gate.py` shows only the `_loom._default_run`-unrelated absence — i.e. no `def _run`/`_run(` calls).

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/qe/vault_gate.py tests/qe/test_loom_gate_contract.py tests/qe/test_vault_gate.py
git commit -m "feat(loom-contract): cross_check loom-authoritative; delete in-process re-derivation body + _run"
```

---

## Task 2: Contract the `resolve` surface — `resolve_vault(allow_npx=True)` loom-authoritative

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/qe/vault_gate.py` (`resolve_vault`)
- Replace: `~/Projects/wicked-garden/tests/crew/test_loom_resolve_contract.py`

The cutover's `resolve_vault` head tries loom (when `allow_npx and use_loom()`) and on loom-error/unresolvable **falls through** to the in-process ladder. The contract makes loom authoritative for the `allow_npx=True` path: loom-unresolvable → None (no in-process npx fallback). The `allow_npx=False` path (which the loom head already skips) keeps the full in-process ladder unchanged — that is `vault_available()`'s concrete-install probe, which MUST NOT break.

- [ ] **Step 1: Rewrite the resolve contract test as loom-authoritative**

Replace `tests/crew/test_loom_resolve_contract.py`. The parity test (loom argv == in-process argv) is moot — there is no in-process argv on the `allow_npx=True` path. New assertions: loom authoritative for `allow_npx=True`; loom-unresolvable → None (NOT the npx ladder); `vault_available()`/`allow_npx=False` still resolves in-process (loom NOT consulted). Hermetic.

```python
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _loom  # noqa: E402
import vault_gate as vg  # noqa: E402


class ResolveLoomAuthoritative(unittest.TestCase):
    """Contract phase: loom `resolve vault` is the SOLE resolution path for the
    run-the-vault case (allow_npx=True). The in-process npx ladder fallback is
    gone. The allow_npx=False concrete-install probe (vault_available) STAYS
    in-process and never consults loom."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN"):
            os.environ.pop(v, None)
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

    def tearDown(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def test_loom_resolve_is_authoritative(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0,
                    "stdout": '{"peer":"vault","command":["npx","--yes","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertEqual(vg.resolve_vault(), ["npx", "--yes", "wicked-vault"])

    def test_loom_command_null_surfaces_as_none(self):
        # loom reports the vault kill-switch / unresolvable -> command=null -> None.
        def fake_run(prefix, args, timeout):
            return {"exit_code": 1, "stdout": '{"peer":"vault","command":null}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertIsNone(vg.resolve_vault())

    def test_loom_unresolvable_returns_none_no_in_process_npx(self):
        # auto + loom unresolvable. There is NO in-process npx ladder on the
        # allow_npx=True path now -> resolve_vault returns None (fail-closed).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertIsNone(vg.resolve_vault())

    def test_off_disables_loom_path_returns_none(self):
        # off = emergency disable. allow_npx=True path no longer has an
        # in-process fallback -> None (the gate then fails closed downstream).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertIsNone(vg.resolve_vault())

    def test_vault_available_probe_stays_in_process(self):
        # allow_npx=False is the concrete-install probe: loom is NEVER consulted
        # (loom would report the npx last-resort as resolvable, corrupting the
        # "installed" signal). A concrete PATH install resolves in-process.
        with patch.object(_loom, "resolve_loom",
                          side_effect=AssertionError("loom must not be consulted")), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/local/bin/wicked-vault"
                          if b == "wicked-vault" else None):
            self.assertEqual(vg.resolve_vault(allow_npx=False), ["/usr/local/bin/wicked-vault"])
            self.assertTrue(vg.vault_available())

    def test_vault_available_false_for_npx_only(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "resolve_loom",
                          side_effect=AssertionError("loom must not be consulted")), \
             patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(vg.vault_available())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test — confirm it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolve_contract.py -v`
Expected: `test_loom_unresolvable_returns_none_no_in_process_npx` and `test_off_disables_loom_path_returns_none` FAIL — current `resolve_vault` falls through to the in-process npx ladder and returns `["npx","--yes","wicked-vault"]` instead of None.

- [ ] **Step 3: Edit `resolve_vault` — loom authoritative for `allow_npx=True`, keep in-process ladder for `allow_npx=False`**

The cutover head is:
```python
    if _loom is not None and allow_npx and _loom.use_loom(project_dir=project_dir):
        out = _loom.run_json(["resolve", "vault"], project_dir=project_dir)
        if out["error"] is None and isinstance(out.get("json"), dict):
            return out["json"].get("command")  # list[str] or None
        # loom errored -> fall through to in-process (transition fail-soft).
```
Replace it so that on the `allow_npx=True` path loom is **authoritative** — loom-unresolvable/error → return None (do NOT fall through). Restructure `resolve_vault` so the in-process ladder ONLY runs for the concrete-install probe (`allow_npx=False`):

```python
def resolve_vault(*, allow_npx: bool = True,
                  project_dir: Optional[Path] = None) -> Optional[List[str]]:
    """Return the argv prefix that invokes wicked-vault, or None.

    Two distinct callers, two paths (contract phase):

    - ``allow_npx=True`` (default; the run-the-vault path): **loom is
      authoritative.** Garden asks ``wicked-loom resolve vault`` and returns
      its ``command`` array (None when loom reports the vault unresolvable /
      kill-switched). loom unresolvable, disabled (``WICKED_LOOM_CUTOVER=off``),
      or erroring → None. There is no in-process npx ladder here anymore (the
      contract removed it); a missing loom means a missing resolver, and the
      gate downstream fails closed (I2).

    - ``allow_npx=False`` (the ``vault_available`` concrete-install probe):
      the in-process ladder (env → config → PATH → node_modules; **no npx, no
      loom**). loom is deliberately NOT consulted: it would report the npx
      last-resort as resolvable and corrupt the "is a concrete vault actually
      installed?" signal. This path is unchanged from before the contract.
    """
    if allow_npx:
        # Run-the-vault path: loom authoritative.
        if _loom is None or not _loom.use_loom(project_dir=project_dir):
            return None  # loom disabled / unresolvable -> no resolver
        out = _loom.run_json(["resolve", "vault"], project_dir=project_dir)
        if out["error"] is not None or not isinstance(out.get("json"), dict):
            return None  # loom errored -> fail-closed (no in-process fallback)
        return out["json"].get("command")  # list[str] or None

    # Concrete-install probe (allow_npx=False): in-process ladder, no loom/npx.
    if "WICKED_VAULT_BIN" in os.environ:
        env = os.environ["WICKED_VAULT_BIN"].strip()
        return _argv_for(env) if env else None  # empty == kill-switch

    pref = _read_config_preference("wicked-vault")
    if pref:
        return _argv_for(pref)

    found = shutil.which("wicked-vault")
    if found:
        return [found]

    base = Path(project_dir) if project_dir else Path.cwd()
    local = base / "node_modules" / ".bin" / "wicked-vault"
    if local.exists():
        return [str(local)]

    return None
```

> Implementer note: this DELETES the in-process `npx --yes wicked-vault` last-resort entirely from the `allow_npx=True` path (it was the redundant fallback the loom head shimmed). The `allow_npx=False` ladder never had an npx tier anyway (that is the point of the probe), so it is byte-for-byte the old logic minus the npx branch. `vault_available()` (calls `allow_npx=False`) is unchanged. The module docstring's "Resolution order" section (lines 22–35) should be updated to describe the two-path split; do that for honesty (R-docs), it is prose only.

- [ ] **Step 4: Update the module docstring's resolution-order section**

The `resolve_vault` docstring (above) is now authoritative; trim/rewrite the top-of-file "Resolution order for the vault CLI" block (lines ~22–35) to point at the two-path split rather than the old 5-tier ladder. Prose only; keep it short.

- [ ] **Step 5: Run the resolve tests + the gate tests + the loom resolver unit tests**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolve_contract.py tests/crew/test_loom_resolver.py tests/qe/ -v`
Expected: PASS. (`test_loom_resolver.py` tests `_loom.resolve_loom` itself — unchanged, still green.)

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/qe/vault_gate.py tests/crew/test_loom_resolve_contract.py
git commit -m "feat(loom-contract): resolve_vault loom-authoritative for allow_npx=True; vault_available stays in-process"
```

---

## Task 3: Update `_loom.py` docstrings — `off` no longer selects an in-process path

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/_loom.py` (docstrings only — NO logic change)

`_loom.use_loom`/`cutover_mode` logic is unchanged (the flag stays `{auto,on,off}`). But the docstrings describe `off`/`auto` as "fall back to the in-process path" — which no longer exists for the shimmed surfaces. Correct the prose so the flag's meaning is honest post-contract.

- [ ] **Step 1: Edit the module docstring + `cutover_mode`/`use_loom` docstrings**

In the module docstring (point 3), change the description of the flag from "lets every cutover try loom first and fall back to the in-process path (the transition default)" to reflect that loom is now load-bearing: `off` is an emergency disable that makes the shimmed surfaces (resolve, gate) unavailable → the gate fails closed; there is no in-process fallback to select. `auto` uses loom iff resolvable; `on` forces it.

In `use_loom`'s docstring, change "auto -> only when loom resolves (the transition default: fall back to the in-process path otherwise)." to "auto -> only when loom resolves. off/auto-unresolvable means the shimmed surface is unavailable (the gate fails closed); there is no in-process fallback after the contract phase."

> Implementer note: do NOT change `use_loom`'s return logic. `off`→False / `on`→True / `auto`→resolvable is still exactly right; the contract only changed what the *callers* do when `use_loom()` is False (return None / fail closed instead of running in-process). The flow surface (`phase_manager`) still uses `use_loom()` for its parity mirror — that is out of scope and unaffected. The `loom_available`/`resolve_loom`/`run_json` logic is untouched.

- [ ] **Step 2: Run the loom unit tests**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolver.py -v`
Expected: PASS (docstring-only change; logic identical).

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/_loom.py
git commit -m "docs(loom-contract): _loom flag docstrings — off is emergency disable, no in-process fallback"
```

---

## Task 4: Drop the `WICKED_LOOM_CUTOVER=off` autouse default from conftest

**Files:**
- Modify: `~/Projects/wicked-garden/tests/conftest.py`

The autouse `_loom_cutover_default_off` fixture forced `off` for the whole suite so legacy in-process unit tests ran deterministically without shelling to a real loom via the npx auto-fallback. After the contract there is **no in-process gate/resolve path** to select with `off`, so the rationale is gone for the shimmed surfaces. The gate/resolve tests now drive the loom path via MOCKED runners (they set `WICKED_LOOM_CUTOVER=on` and patch `_loom.resolve_loom`/`_loom._default_run` in their own setUp — already done in Tasks 1–2). The flow parity tests set the flag in their own body too.

**The risk to manage:** removing the default means any test that calls `cross_check`/`resolve_vault`/`gate_satisfied` WITHOUT setting the flag and WITHOUT mocking loom would, under `auto` on a box with `npx`, try to shell a real loom (network, slow, non-deterministic). We must ensure no such test exists.

- [ ] **Step 1: Audit for unguarded callers**

Run: `cd ~/Projects/wicked-garden && grep -rln "cross_check\|gate_satisfied\|resolve_vault\|vault_available" tests/ --include="*.py"`
For each hit, confirm the test either (a) sets `WICKED_LOOM_CUTOVER` explicitly + mocks the loom runner, (b) uses `allow_npx=False` (in-process probe, no loom), or (c) sets the vault kill-switch / loom off so the call fails closed deterministically. The files in play: `tests/qe/test_vault_gate.py`, `tests/qe/test_loom_gate_contract.py`, `tests/crew/test_loom_resolve_contract.py`. (Tasks 1–2 already made these self-contained.) Fix any straggler found here before removing the fixture.

- [ ] **Step 2: Remove the autouse fixture**

Delete the `_loom_cutover_default_off` fixture (lines ~49–69) from `tests/conftest.py`. Keep `pytest_configure` (sys.path ordering) and `_reset_bus_emit_counters`. Leave a one-line provenance comment where the fixture was, noting the contract phase removed it (the shimmed surfaces have no in-process path to default to; tests now drive loom via mocked runners).

> Defense-in-depth (recommended): instead of an `off` default, add a NEW autouse fixture that sets `WICKED_LOOM_CUTOVER=off` ONLY as a guard against accidental real-loom subprocess calls — no. That reintroduces the exact ambiguity we are removing. Better: leave NO default, and rely on each loom-touching test owning its flag (the T3 isolation rule). If a future test forgets, it fails loudly (real-loom attempt errors hermetically because npx is usually absent in CI), which is the correct signal. Document this in the provenance comment.

- [ ] **Step 3: Run the FULL suite**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/ -q`
Expected: 0 failed. Report the new total (was 497; the gate + resolve contract tests changed count — parity tests removed, loom-authoritative tests added). If any test fails because it relied on the `off` default, fix it by giving it an explicit flag + mocked runner (T3), not by restoring the global default.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/wicked-garden
git add tests/conftest.py
git commit -m "test(loom-contract): drop WICKED_LOOM_CUTOVER=off autouse default; tests own the loom flag"
```

---

## Task 5: Docs — loom is load-bearing for gating, not an optional shim

**Files:**
- Modify: `~/Projects/wicked-garden/docs/required-peers.md`
- Modify: `~/Projects/wicked-garden/hooks/scripts/bootstrap.py` (prose only — `_check_loom_dependency` message)

The cutover added the loom peer row with the bracketed clause "during cutover, garden falls back to its in-process runtime; after the contract phase, loom is the only runtime." Post-contract, the first half is no longer true for the shimmed surfaces. Tighten the prose so loom reads as load-bearing for gating + resolution.

- [ ] **Step 1: Edit `docs/required-peers.md`**

In the "## Why each is load-bearing" `wicked-loom` bullet, drop the cutover-fallback parenthetical. New ending: "Without it, the produces-gate has no re-derivation engine and fails closed — 'done' cannot be re-derived, so it cannot be asserted." Also update the loom table-row "What it does" cell if it implies optionality. Add a sentence (near the kill-switch paragraph) noting `WICKED_LOOM_CUTOVER=off` is now an *emergency disable* that fails the gate closed (no in-process fallback remains), parallel to the vault kill-switch.

- [ ] **Step 2: Edit `bootstrap.py` `_check_loom_dependency` message**

Change the return string's last clause from "(Cutover phase: garden falls back to its in-process runtime when loom is absent.)" to reflect that loom is now load-bearing: "(Gating + peer resolution route through loom; without it the produces-gate fails closed.)" Also update the function docstring's "During the cutover transition garden falls back to its in-process runtime when loom is absent" sentence the same way. Detection logic (PATH / skill-dir scan / fail-open) is UNCHANGED — only the prose.

> Implementer note: do NOT touch `_check_loom_dependency`'s control flow or the `WICKED_LOOM_BIN`/`WICKED_LOOM_CUTOVER=off` "don't nag" early-returns — those are still correct (an operator who set the kill-switch or disabled loom is driving deliberately). Only the human-facing message text changes.

- [ ] **Step 3: Verify + commit**

Run: `cd ~/Projects/wicked-garden && python3 -c "import ast; ast.parse(open('hooks/scripts/bootstrap.py').read()); print('bootstrap.py parses')" && grep -c "in-process" docs/required-peers.md`
Expected: parses; the `in-process` count in required-peers.md drops (the fallback claim is gone).

```bash
cd ~/Projects/wicked-garden
git add docs/required-peers.md hooks/scripts/bootstrap.py
git commit -m "docs(loom-contract): loom is load-bearing for gating; drop in-process-fallback prose"
```

---

## Final verification (HARD GATES — must all hold)

- [ ] **Full suite green:**
  `cd ~/Projects/wicked-garden && python3 -m pytest tests/ -q` → **0 failed**. Report the new total vs the 497 baseline.

- [ ] **Fail-closed preserved (the load-bearing invariant):**
  `python3 -m pytest tests/qe/test_loom_gate_contract.py -k "fails_closed or unavailable" -v` → the loom-unresolvable / loom-error / vault-absent cases all return `available: False` / `gate: "unavailable"` / `satisfied: false`. NEVER a pass.

- [ ] **Deletions are real (this is the contract — confirm, don't trust):**
  `git diff main -- scripts/qe/vault_gate.py` shows the in-process `cross_check` body (`args = ["cross-check", ...]; run = _run(...); json.loads(...)`) and the `_run` helper REMOVED (red lines), and the `allow_npx=True` in-process npx ladder REMOVED from `resolve_vault`. `grep -n "def _run\|_run(" scripts/qe/vault_gate.py` → no in-process `_run` definition/call remains.

- [ ] **`vault_available()` intact:** `python3 -m pytest tests/crew/test_loom_resolve_contract.py -k vault_available -v` and `tests/qe/test_vault_gate.py -k Resolution` → green (the `allow_npx=False` probe still resolves a concrete install in-process; loom never consulted).

- [ ] **Hermetic:** no test spawns a real loom/npx. `grep -rn "npx\|subprocess.run\|_default_run" tests/qe/test_loom_gate_contract.py tests/crew/test_loom_resolve_contract.py` → only mocked runners / patched `_default_run`; the real-vault `VaultBackedGateTests` stays skip-guarded.

- [ ] **Push:** `git push -u origin feat/loom-contract`. Do NOT open a PR or merge (the parent reviews + merges).

---

## Self-review

- **Honest-evidence preserved (I2):** every deleted path is a *re-derivation engine*, never a *fail-closed guard*. The new `cross_check` returns `available: False` on loom-absent/error/unavailable; `gate_satisfied` is structurally unchanged and still fails closed. The fail-closed test is mandatory (final verification gate 2). No vacuous-pass path is introduced — verified by the `test_loom_error_fails_closed_no_in_process_pass` + `test_gate_satisfied_fails_closed_when_loom_absent` tests.
- **`vault_available()` not broken:** the `allow_npx=False` in-process ladder is preserved verbatim (minus the npx tier it never had). Loom is never consulted on that path — asserted by `test_vault_available_probe_stays_in_process` (patches `resolve_loom` to raise if touched). This is the explicit "keep what `vault_available()` needs" requirement.
- **Scope discipline:** only `resolve` + `gate` (the shimmed surfaces) are contracted. The flow parity mirror, `flow_compiler`, `phase_manager` storage, `_integration_resolver`/`_capability_resolver`/`_capability_registry`, `_bus`/`_event_*`, and the compiler are LEFT ALONE (spec §6 future increments). The flow contract tests are NOT touched.
- **Flag decision justified:** `WICKED_LOOM_CUTOVER` kept as a documented emergency disable that fails closed; logic unchanged, prose corrected. Removing it was rejected (free coarse kill-switch, parallel to the vault's).
- **Deletions are real, not flag flips:** Task 1 deletes the `_run` helper and the in-process `cross_check` body; Task 2 deletes the `allow_npx=True` npx ladder. The final verification gate diffs `main` to confirm red lines exist. R1 (no dead code) holds: `_run` is removed because its only caller is gone.
- **Tests stay hermetic + isolated (T1/T3):** every loom-touching test sets its own flag in setUp and patches the loom runner; the autouse global default is removed so isolation is per-test, not suite-global. No real npx/network.
- **R6 (no god functions):** `cross_check` shrinks (one path, not two); `resolve_vault` splits cleanly by `allow_npx` into the loom path and the probe ladder. Neither grows.
