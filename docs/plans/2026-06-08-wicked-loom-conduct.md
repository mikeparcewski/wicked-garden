# wicked-loom — Conduct Module, Plan B (gate + flow runtime) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `wicked-loom` **conduct** surface — a synchronous, fail-closed vault re-derivation gate and an archetype-agnostic flow runtime that advances declarative flow definitions, executes per-phase gates, parks at hard gates, and persists deterministic per-flow state — built on Plan A's `resolve()`/`compose` core, with garden untouched.

**Architecture:** Four new stdlib-only Python modules added to the existing `python/loom/` package: `gate.py` (sync vault `cross-check`, ported from garden's `scripts/qe/vault_gate.py`), `flowstate.py` (local-JSON per-flow state, phase_manager-style), `busemit.py` (thin best-effort fire-and-forget bus emit — emission only; no consumer), and `flow.py` (the generic phase-loop that wires gate + state + emit together). Subprocess execution is injected everywhere (matching `compose.py`'s `RunResult`/`Runner` pattern) so no test ever spawns a real vault or touches the network. `cli.py` gains a `gate` command and a `flow` command group. **Conduct only** — compose was Plan A.

**Tech Stack:** Python 3.9+ (stdlib only — no third-party deps, mirroring Plan A and garden's hook discipline), `pytest` for tests, the existing `bin/loom.mjs` Node shim (unchanged). Reuses `loom.resolve.resolve("vault")` for vault resolution and `loom.compose.RunResult`/`Runner` for the injected subprocess seam.

**Decisions locked for this plan (override in review):**
- **Scope = conduct, synchronous core only.** `loom gate`, `loom flow run|status|resume`. The headless daemon / bus-consumer / projector is **DEFERRED per spec decision D3 and §9 (D-headless)** — explicitly OUT OF SCOPE here (see "Out of scope" below). Only the *contract* (park-at-hard-gate, event names) is realized, not unattended execution.
- **File layout:** `gate.py`, `flow.py`, `flowstate.py`, `busemit.py` — one responsibility per file (justified in File Structure). Vault subprocess and bus subprocess are both injected `Runner`s so flow/gate tests are hermetic.
- **Target repo:** `~/Projects/wicked-loom` (the package Plan A created). Plan B adds files to it; garden (`~/Projects/wicked-garden`) is untouched.

**Source material to read in wicked-garden before Task 1 (grounding only — do not import from garden):**
- `scripts/qe/vault_gate.py` — the exact `cross-check` invocation (`["cross-check", "--scope", scope, "--phase", phase, ("--with-attestations")]`), how it parses the `overall` PASS/REJECT/ERROR field, and the fail-closed posture when the vault is unresolvable or unrunnable. `gate.py` is a faithful, injected-runner port of this.
- `scripts/crew/phase_manager.py` — the `ProjectState` dataclass + `save_project_state`/`load_project_state` JSON pattern and the `_bus_emit_safe` fire-and-forget wrapper. `flowstate.py` and `busemit.py` mirror these, slimmed.
- Plan A (`docs/plans/2026-06-08-wicked-loom-expand-compose.md`) — the code style, the `RunResult(returncode, stdout, stderr)` injected-runner pattern, and the `cli.py` dispatch shape this plan extends.

**Out of scope (DEFERRED — do NOT build in Plan B):**
- The bus **consumer / projector** and headless unattended execution (spec §4.2 "Project", §4.3 surface #2). `busemit.py` is emission ONLY — best-effort, fail-soft, never blocking; an emitted event NEVER satisfies a gate (invariant I4). No subscriber, no event-sourced state rebuild.
- `loom compose` changes (Plan A is frozen).
- The garden-side archetype→flow-definition compiler (§3.1, §7 step 2) and the garden `gate`/`flow` cutover shims (§7) — those are the cutover plan, not Plan B. Loom only *consumes* a hand-authored flow definition (success criterion #6).

**Bulletproof standards:** R1–R6 (no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions) and T1–T6 (determinism, no sleep-based sync, isolation, single-assertion focus, descriptive names, provenance). The gate must be synchronous + fully mockable (never hit the network or a real vault in a unit test); flow state must be deterministic (no wall-clock-dependent assertions — timestamps are written but never asserted-on for equality).

---

## File Structure

```
wicked-loom/
├── python/loom/
│   ├── gate.py        # NEW — synchronous vault cross-check (re-derive). Ported
│   │                  #       from garden scripts/qe/vault_gate.py, runner injected.
│   ├── flowstate.py   # NEW — per-flow JSON state: load/save/new, one file per flow_id.
│   ├── busemit.py     # NEW — thin best-effort fire-and-forget bus emit (emission only).
│   ├── flow.py        # NEW — the generic phase-loop: run/status/resume; wires
│   │                  #       gate + flowstate + busemit. Archetype-agnostic.
│   ├── resolve.py     # (Plan A) reused by gate.py for vault resolution.
│   ├── compose.py     # (Plan A) RunResult/Runner reused by gate.py + busemit.py.
│   ├── manifest.py    # (Plan A) unchanged.
│   └── cli.py         # MODIFY — add `gate` + `flow` (run|status|resume) dispatch.
├── tests/
│   ├── test_gate.py        # NEW
│   ├── test_flowstate.py   # NEW
│   ├── test_busemit.py     # NEW
│   ├── test_flow.py        # NEW
│   └── test_cli.py         # MODIFY — add gate + flow CLI cases.
```

**Responsibilities (one per file, justifying the layout):**
- `gate.py` = *re-derive evidence for one produces* (the honest-evidence engine). Pure of state/flow concerns; takes an injected runner; returns a status dict. This is the §4.2 "Execute a gate" bullet and invariants I1/I2/I3.
- `flowstate.py` = *persist one flow's progress to disk* (data + I/O only — no gate, no bus). The §4.2 "Run a flow → persist phase state" storage half. Deterministic, no network (spec §10).
- `busemit.py` = *announce a transition, best-effort* (emission only — the §4.3 #3 event contract producer side; the consumer is deferred per D3/I4). Isolated so flow logic never couples to bus availability.
- `flow.py` = *advance phases, calling gate + state + emit* (the §4.2 "Run a flow" + "Park at hard gate" orchestration; invariants I5/I6). It is the only file that knows the flow-definition shape; it is archetype-agnostic (I6 — it must not branch on archetype names).
- `cli.py` = *argument dispatch only* (unchanged philosophy from Plan A — no business logic).

Why `busemit.py` is separate from `flowstate.py`: state is the **source of truth** (deterministic, must persist); the bus is **optional infrastructure** (fail-open). Mixing them would let a bus failure threaten a state write (it must not — I4 / spec §10). Why `gate.py` is separate from `flow.py`: the gate is independently shippable as `loom gate` (a garden cutover target on its own, §7) and must be unit-testable without any flow.

**The flow-definition shape this plan consumes** (spec §3.1 — loom executes it, garden authors it):

```jsonc
{
  "flow_id": "build-1234",
  "phases": [
    { "name": "plan",      "gate": null,                   "hitl": "none",     "produces": [] },
    { "name": "implement", "gate": null,                   "hitl": "none",     "produces": [] },
    { "name": "test",      "gate": "produces:test-report", "hitl": "discrete:review",   "produces": ["test-report"] },
    { "name": "review",    "gate": "produces:verdict",     "hitl": "hard:final-verdict","produces": ["verdict"] }
  ],
  "peers_required": ["vault", "testing"],
  "verifier_spec_ref": null
}
```

Field semantics loom relies on (and nothing else — I6):
- `gate`: `null` → no gate, advance freely. `"produces:<name>"` → run a vault cross-check whose `--phase` is `<name>` (the produces contract id). Any non-null, non-`produces:` value is treated as a generic gate on the literal string (still re-derived; fail-soft only on an unknown verifier spec, never a vacuous pass).
- `hitl`: `"hard:*"` → a **hard gate**: even on a PASS, the flow PARKS for human verdict (I5); loom never self-approves a hard gate. `"discrete:*"`/`"continuous"`/`"none"` → not hard; a satisfied gate advances automatically.
- `verifier_spec_ref`: optional path passed through to the gate as `--verifier-spec`; absent/unreadable → generic detection, never blocks (I3).

---

## Task 1: Synchronous vault gate (`gate.py`)

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/gate.py`
- Test: `~/Projects/wicked-loom/tests/test_gate.py`

Faithful injected-runner port of garden's `scripts/qe/vault_gate.cross_check` + the fail-closed posture of `gate_satisfied`. The vault command prefix comes from `loom.resolve.resolve("vault")`; the subprocess is run through an injected `Runner` (the same `RunResult` shape as `compose.py`) so tests never spawn the vault. Invariants: **I1** synchronous/in-line (one blocking call per invocation, no events), **I2** fail-closed (vault unresolvable OR unrunnable → `gate: "unavailable"`, `satisfied: False` — never a pass), **I3** fail-soft on the verifier spec only (a `verifier_spec` arg is passed through when present; its absence never blocks). Hard gates require `with_attestations=True` (the independent attester), forwarded to the vault as `--with-attestations`.

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from loom import gate
from loom.compose import RunResult


def _runner(stdout="", code=0):
    def run(cmd, timeout=None):
        return RunResult(returncode=code, stdout=stdout, stderr="")
    return run


def test_gate_passes_when_vault_reports_pass():
    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        r = gate.run_gate("test-report", scope="build-1",
                          run=_runner(stdout='{"overall":"PASS"}'))
    assert r["satisfied"] is True
    assert r["gate"] == "vault-cross-check"
    assert r["re_derived"] is True
    assert r["overall"] == "PASS"


def test_gate_rejects_when_vault_reports_reject():
    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        r = gate.run_gate("test-report", scope="build-1",
                          run=_runner(stdout='{"overall":"REJECT"}'))
    assert r["satisfied"] is False
    assert r["overall"] == "REJECT"


def test_gate_fails_closed_when_vault_unresolvable():
    with patch.object(gate, "resolve", return_value=None):
        r = gate.run_gate("test-report", scope="build-1", run=_runner())
    assert r["satisfied"] is False
    assert r["gate"] == "unavailable"
    assert r["re_derived"] is False


def test_gate_fails_closed_when_vault_unrunnable():
    def boom(cmd, timeout=None):
        raise FileNotFoundError("vault gone")
    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        r = gate.run_gate("test-report", scope="build-1", run=boom)
    assert r["satisfied"] is False
    assert r["gate"] == "unavailable"


def test_gate_fails_closed_on_non_json_output():
    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        r = gate.run_gate("test-report", scope="build-1",
                          run=_runner(stdout="not json"))
    assert r["satisfied"] is False
    assert r["overall"] == "ERROR"


def test_with_attestations_forwarded_to_vault():
    seen = {}

    def run(cmd, timeout=None):
        seen["cmd"] = cmd
        return RunResult(returncode=0, stdout='{"overall":"PASS"}', stderr="")

    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        gate.run_gate("verdict", scope="build-1", with_attestations=True, run=run)
    assert "--with-attestations" in seen["cmd"]


def test_verifier_spec_forwarded_when_present():
    seen = {}

    def run(cmd, timeout=None):
        seen["cmd"] = cmd
        return RunResult(returncode=0, stdout='{"overall":"PASS"}', stderr="")

    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        gate.run_gate("verdict", scope="build-1",
                      verifier_spec="/tmp/verify.json", run=run)
    assert "--verifier-spec" in seen["cmd"]
    assert "/tmp/verify.json" in seen["cmd"]


def test_verifier_spec_absent_is_fail_soft_not_blocking():
    # No verifier_spec given -> the gate still runs and can PASS (I3).
    with patch.object(gate, "resolve", return_value=["wicked-vault"]):
        r = gate.run_gate("verdict", scope="build-1",
                          run=_runner(stdout='{"overall":"PASS"}'))
    assert r["satisfied"] is True
    assert "--verifier-spec" not in r.get("argv", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.gate'`

- [ ] **Step 3: Write `gate.py`**

```python
"""gate.py — the synchronous, fail-closed produces gate (vault re-derivation).

Ported from wicked-garden scripts/qe/vault_gate.py, with the subprocess
execution injected (the ``run`` parameter, same RunResult shape as compose.py)
so callers and tests control side effects and no real vault is ever spawned in
a unit test.

Invariants (spec §5):
  I1 — synchronous + in-line: exactly one blocking vault call per invocation;
       no events are consulted. An event NEVER satisfies a gate.
  I2 — fail-closed: vault unresolvable OR unrunnable OR non-JSON ->
       gate "unavailable" / overall "ERROR", satisfied False. Never a pass.
  I3 — fail-soft on the verifier spec only: a present ``verifier_spec`` is
       forwarded to the vault; its ABSENCE never blocks and never vacates the
       gate — the vault falls back to generic detection.

Hard gates additionally require an independent attestation: pass
``with_attestations=True`` -> ``--with-attestations`` forwarded to the vault.

The return is a status dict (R4 — surface as data, never raise):
  {satisfied, re_derived, gate, overall, exit_code, argv, detail, error}
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from loom.compose import RunResult, _default_run
from loom.resolve import resolve

Runner = Callable[..., RunResult]

_DEFAULT_TIMEOUT = 120  # seconds; bounds the blocking re-derivation (R5).


def _build_argv(vault_prefix: list, produces: str, scope: str, *,
                with_attestations: bool,
                verifier_spec: Optional[str]) -> list:
    """The full vault argv: <prefix> cross-check --scope S --phase <produces> ...

    ``produces`` maps to the vault's ``--phase`` (the produces-contract id, e.g.
    "test-report"); ``scope`` maps to ``--scope`` (the project/flow scope).
    """
    argv = list(vault_prefix) + ["cross-check", "--scope", scope, "--phase", produces]
    if with_attestations:
        argv.append("--with-attestations")
    if verifier_spec:
        argv += ["--verifier-spec", verifier_spec]
    return argv


def run_gate(produces: str, *, scope: str,
             with_attestations: bool = False,
             verifier_spec: Optional[str] = None,
             run: Runner = _default_run,
             timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """Re-derive ``produces`` via ``vault cross-check`` and return the verdict.

    Fail-closed (I2): no resolvable vault, an unrunnable vault, or non-JSON
    output all yield ``satisfied: False`` with ``gate: "unavailable"`` (or
    overall "ERROR") — never an invented pass.
    """
    vault_prefix = resolve("vault")
    if vault_prefix is None:
        return {
            "satisfied": False,
            "re_derived": False,
            "gate": "unavailable",
            "overall": "ERROR",
            "argv": [],
            "error": "wicked-vault not resolvable",
            "detail": "Gate fails closed — 'done' cannot be self-asserted (I2).",
        }

    argv = _build_argv(vault_prefix, produces, scope,
                       with_attestations=with_attestations,
                       verifier_spec=verifier_spec)
    try:
        result = run(argv, timeout=timeout)
    except Exception as e:  # noqa: BLE001 — surface as data, fail closed (R4/I2)
        return {
            "satisfied": False,
            "re_derived": False,
            "gate": "unavailable",
            "overall": "ERROR",
            "argv": argv,
            "error": str(e),
            "detail": "vault resolvable but not runnable; gate fails closed (I2).",
        }

    try:
        parsed = json.loads(result.stdout) if (result.stdout or "").strip() else {}
    except json.JSONDecodeError:
        return {
            "satisfied": False,
            "re_derived": True,
            "gate": "vault-cross-check",
            "overall": "ERROR",
            "exit_code": result.returncode,
            "argv": argv,
            "error": "vault returned non-JSON output",
            "detail": result.stderr.strip()[:500],
        }

    overall = parsed.get("overall", "ERROR")
    return {
        "satisfied": overall == "PASS",
        "re_derived": True,
        "gate": "vault-cross-check",
        "overall": overall,
        "exit_code": result.returncode,
        "argv": argv,
        "claims": parsed.get("claims", []),
        "contract_version": parsed.get("contract_version"),
        "detail": parsed.get("detail"),
        "error": None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_gate.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/gate.py tests/test_gate.py
git commit -m "feat: synchronous fail-closed vault gate (conduct)"
```

---

## Task 2: Per-flow state persistence (`flowstate.py`)

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/flowstate.py`
- Test: `~/Projects/wicked-loom/tests/test_flowstate.py`

One JSON file per `flow_id`, phase_manager-style. The state directory is injected (a `Path`) so tests use `tmp_path` and never touch a real home dir — deterministic, no network (spec §10). State records: `flow_id`, the original `phases` list, `current_phase` (index into `phases`), per-phase `gate_verdicts`, `parked` (bool) + `parked_reason`, `status` (`running`|`parked`|`completed`), and `created_at`/`updated_at` timestamps (written, never asserted-on for equality — T1 determinism). Nothing here raises on a normal path; a missing file on load returns `None`.

- [ ] **Step 1: Write the failing test**

```python
from loom import flowstate

_FLOW = {
    "flow_id": "build-1",
    "phases": [
        {"name": "plan", "gate": None, "hitl": "none"},
        {"name": "test", "gate": "produces:test-report", "hitl": "discrete:review"},
    ],
    "peers_required": ["vault"],
    "verifier_spec_ref": None,
}


def test_new_state_starts_at_phase_zero_running(tmp_path):
    st = flowstate.new_state(_FLOW, state_dir=tmp_path)
    assert st["flow_id"] == "build-1"
    assert st["current_phase"] == 0
    assert st["status"] == "running"
    assert st["parked"] is False
    assert st["gate_verdicts"] == {}


def test_save_then_load_roundtrips(tmp_path):
    st = flowstate.new_state(_FLOW, state_dir=tmp_path)
    flowstate.save_state(st, state_dir=tmp_path)
    loaded = flowstate.load_state("build-1", state_dir=tmp_path)
    assert loaded["flow_id"] == "build-1"
    assert loaded["phases"] == _FLOW["phases"]
    assert loaded["current_phase"] == 0


def test_load_missing_flow_returns_none(tmp_path):
    assert flowstate.load_state("nope", state_dir=tmp_path) is None


def test_state_file_path_is_one_file_per_flow_id(tmp_path):
    flowstate.save_state(flowstate.new_state(_FLOW, state_dir=tmp_path),
                         state_dir=tmp_path)
    expected = tmp_path / "build-1.json"
    assert expected.exists()


def test_record_verdict_is_persisted(tmp_path):
    st = flowstate.new_state(_FLOW, state_dir=tmp_path)
    st["gate_verdicts"]["test"] = {"satisfied": True, "overall": "PASS"}
    flowstate.save_state(st, state_dir=tmp_path)
    loaded = flowstate.load_state("build-1", state_dir=tmp_path)
    assert loaded["gate_verdicts"]["test"]["satisfied"] is True


def test_unsafe_flow_id_is_rejected(tmp_path):
    bad = dict(_FLOW, flow_id="../etc/passwd")
    try:
        flowstate.new_state(bad, state_dir=tmp_path)
        raised = False
    except ValueError:
        raised = True
    assert raised is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_flowstate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.flowstate'`

- [ ] **Step 3: Write `flowstate.py`**

```python
"""flowstate.py — per-flow JSON state. One file per flow_id.

phase_manager-style local state (spec §4.2 "persist phase state", §10 "local
JSON, deterministic, no network"). The state directory is a parameter so tests
inject a tmp dir and production injects a project-scoped path; this module never
hardcodes a home path and never spawns a process.

State schema:
  flow_id        : str (validated kebab/snake/alphanumeric, max 64 — no path sep)
  phases         : list[dict]  (the original flow-def phases, verbatim)
  current_phase  : int         (index into phases; == len(phases) when completed)
  gate_verdicts  : dict[phase_name -> verdict dict]
  parked         : bool
  parked_reason  : str | None
  status         : "running" | "parked" | "completed"
  created_at     : ISO8601 str (written, never asserted-on)
  updated_at     : ISO8601 str (written, never asserted-on)

Nothing here raises except on an unsafe flow_id (ValueError — a guard, not a
swallowed error, R4). A missing state file on load returns None.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_FLOW_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

STATUS_RUNNING = "running"
STATUS_PARKED = "parked"
STATUS_COMPLETED = "completed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_flow_id(flow_id: str) -> str:
    if not isinstance(flow_id, str) or not _FLOW_ID_RE.match(flow_id):
        raise ValueError(f"unsafe flow_id: {flow_id!r} (kebab/snake/alnum, max 64)")
    return flow_id


def _state_path(flow_id: str, state_dir: Path) -> Path:
    return Path(state_dir) / f"{_validate_flow_id(flow_id)}.json"


def new_state(flow_def: dict, *, state_dir: Path) -> dict:
    """Build a fresh running state from a flow definition. Does not persist."""
    flow_id = _validate_flow_id(flow_def["flow_id"])
    now = _now()
    return {
        "flow_id": flow_id,
        "phases": list(flow_def.get("phases", [])),
        "peers_required": list(flow_def.get("peers_required", [])),
        "verifier_spec_ref": flow_def.get("verifier_spec_ref"),
        "current_phase": 0,
        "gate_verdicts": {},
        "parked": False,
        "parked_reason": None,
        "status": STATUS_RUNNING,
        "created_at": now,
        "updated_at": now,
    }


def save_state(state: dict, *, state_dir: Path) -> Path:
    """Atomically write the state file for ``state['flow_id']`` and return its path."""
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    path = _state_path(state["flow_id"], state_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_state(flow_id: str, *, state_dir: Path) -> Optional[dict]:
    """Load the state for ``flow_id``; None if no file exists."""
    path = _state_path(flow_id, state_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_flowstate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/flowstate.py tests/test_flowstate.py
git commit -m "feat: per-flow JSON state persistence (conduct)"
```

---

## Task 3: Best-effort bus emission (`busemit.py`)

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/busemit.py`
- Test: `~/Projects/wicked-loom/tests/test_busemit.py`

Emission ONLY (the §4.3 #3 event-contract producer side). Fire-and-forget, fail-soft: a bus that is unresolvable, errors, or times out NEVER raises and NEVER blocks the caller (invariant I4 — the bus is the spine for everything that is *not* a gate verdict, and an event never satisfies a gate). The bus command resolves via `loom.resolve.resolve("bus")` and runs through an injected `Runner`. Event names are the stable set from spec §4.3: `loom:flow:started|phase-advanced|gate-passed|gate-failed|needs-human|completed`. **No consumer/projector is built here — deferred per D3.**

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from loom import busemit
from loom.compose import RunResult


def test_event_names_are_the_spec_set():
    assert busemit.EVENTS["started"] == "loom:flow:started"
    assert busemit.EVENTS["phase-advanced"] == "loom:flow:phase-advanced"
    assert busemit.EVENTS["gate-passed"] == "loom:flow:gate-passed"
    assert busemit.EVENTS["gate-failed"] == "loom:flow:gate-failed"
    assert busemit.EVENTS["needs-human"] == "loom:flow:needs-human"
    assert busemit.EVENTS["completed"] == "loom:flow:completed"


def test_emit_invokes_bus_with_event_and_payload():
    seen = {}

    def run(cmd, timeout=None):
        seen["cmd"] = cmd
        return RunResult(returncode=0, stdout="", stderr="")

    with patch.object(busemit, "resolve", return_value=["wicked-bus"]):
        ok = busemit.emit("started", {"flow_id": "build-1"}, run=run)
    assert ok is True
    assert "loom:flow:started" in seen["cmd"]


def test_emit_is_fail_soft_when_bus_unresolvable():
    with patch.object(busemit, "resolve", return_value=None):
        ok = busemit.emit("started", {"flow_id": "build-1"})
    assert ok is False  # best-effort: reports, never raises


def test_emit_never_raises_when_bus_errors():
    def boom(cmd, timeout=None):
        raise FileNotFoundError("bus gone")

    with patch.object(busemit, "resolve", return_value=["wicked-bus"]):
        ok = busemit.emit("needs-human", {"flow_id": "build-1"}, run=boom)
    assert ok is False  # swallowed at the boundary by design (I4), reported as data


def test_emit_unknown_event_is_false_not_raise():
    with patch.object(busemit, "resolve", return_value=["wicked-bus"]):
        ok = busemit.emit("frobnicate", {"flow_id": "build-1"})
    assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_busemit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.busemit'`

- [ ] **Step 3: Write `busemit.py`**

```python
"""busemit.py — best-effort fire-and-forget bus emission. Emission ONLY.

The bus is the spine for everything that is NOT a gate verdict (spec §4.4/I4):
phase transitions, needs-human parks, audit. Emission is fire-and-forget — an
unresolvable, erroring, or slow bus must NEVER raise and NEVER block the flow.
An emitted event NEVER satisfies a gate (I4) — gates are synchronous and direct
(gate.py); this module only announces.

The bus consumer / projector and any headless reaction to these events are
DEFERRED (spec D3 / §9 D-headless). This file is the producer side only.

Stable event names (spec §4.3 #3):
  loom:flow:started | phase-advanced | gate-passed | gate-failed
                    | needs-human | completed
"""

from __future__ import annotations

import json
from typing import Callable

from loom.compose import RunResult, _default_run
from loom.resolve import resolve

Runner = Callable[..., RunResult]

_EMIT_TIMEOUT = 5  # seconds; emission is best-effort, keep it short (R5).

EVENTS: dict = {
    "started": "loom:flow:started",
    "phase-advanced": "loom:flow:phase-advanced",
    "gate-passed": "loom:flow:gate-passed",
    "gate-failed": "loom:flow:gate-failed",
    "needs-human": "loom:flow:needs-human",
    "completed": "loom:flow:completed",
}


def emit(event_key: str, payload: dict, *, run: Runner = _default_run) -> bool:
    """Fire-and-forget emit. Returns True iff the bus accepted it (exit 0).

    Never raises: an unknown event, an unresolvable bus, or any subprocess
    failure is reported as ``False`` (I4 — the bus is optional infrastructure).
    """
    event_type = EVENTS.get(event_key)
    if event_type is None:
        return False

    bus_prefix = resolve("bus")
    if bus_prefix is None:
        return False

    argv = list(bus_prefix) + ["emit", event_type, json.dumps(payload)]
    try:
        result = run(argv, timeout=_EMIT_TIMEOUT)
    except Exception:  # noqa: BLE001 — fire-and-forget; bus is optional (I4)
        return False
    return result.returncode == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_busemit.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/busemit.py tests/test_busemit.py
git commit -m "feat: best-effort fire-and-forget bus emission (conduct)"
```

---

## Task 4: The flow runner (`flow.py`)

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/flow.py`
- Test: `~/Projects/wicked-loom/tests/test_flow.py`

The generic, **archetype-agnostic** phase-loop (invariant I6 — it branches on the flow definition's `gate`/`hitl` fields, NEVER on archetype names). It wires Task 1 (gate), Task 2 (state), Task 3 (emit). The vault runner and bus runner are injected separately so a flow test never spawns either. Three operations:

- `run_flow(flow_def, …)` — create state, emit `started`, then advance.
- `status(flow_id, …)` — read persisted state (no advance, no side effects beyond read).
- `resume(flow_id, …)` — reload a parked/running flow and advance again (the human approves a hard gate out-of-band; resume moves past it).

**Advance loop (the heart of conduct, spec §3.1 + §4.2):** from `current_phase`, for each phase:
1. If the phase has no `gate` → emit `phase-advanced`, increment, continue.
2. Else run the gate (Task 1) → record the verdict in state.
   - Gate **not satisfied** → emit `gate-failed`, persist, STOP (status stays `running`; the flow is blocked on real evidence, not parked-for-human).
   - Gate **satisfied** + `hitl` is `hard:*` → emit `gate-passed` then `needs-human`, set `parked=True`, status `parked`, persist, STOP. **Loom never self-approves a hard gate (I5).**
   - Gate **satisfied** + not hard → emit `gate-passed` + `phase-advanced`, increment, continue.
3. When `current_phase == len(phases)` → status `completed`, emit `completed`, persist, STOP.

`resume` clears `parked` for the phase the human just approved (it advances PAST the parked hard-gate phase without re-running it — the human verdict is the authority there, per I5), then runs the same loop.

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from loom import flow
from loom.compose import RunResult


def _vault(overall="PASS", code=0):
    def run(cmd, timeout=None):
        import json
        return RunResult(returncode=code, stdout=json.dumps({"overall": overall}),
                         stderr="")
    return run


def _silent_bus():
    def run(cmd, timeout=None):
        return RunResult(returncode=0, stdout="", stderr="")
    return run


def _flow_def(flow_id="build-1"):
    return {
        "flow_id": flow_id,
        "phases": [
            {"name": "plan", "gate": None, "hitl": "none"},
            {"name": "implement", "gate": None, "hitl": "none"},
            {"name": "test", "gate": "produces:test-report", "hitl": "discrete:review"},
            {"name": "review", "gate": "produces:verdict", "hitl": "hard:final-verdict"},
        ],
        "peers_required": ["vault"],
        "verifier_spec_ref": None,
    }


def test_gateless_phases_advance_freely(tmp_path):
    fd = {"flow_id": "g-1",
          "phases": [{"name": "a", "gate": None, "hitl": "none"},
                     {"name": "b", "gate": None, "hitl": "none"}],
          "peers_required": [], "verifier_spec_ref": None}
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        st = flow.run_flow(fd, state_dir=tmp_path,
                           vault_run=_vault(), bus_run=_silent_bus())
    assert st["status"] == "completed"
    assert st["current_phase"] == 2


def test_flow_parks_at_hard_gate_after_pass(tmp_path):
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        st = flow.run_flow(_flow_def(), state_dir=tmp_path,
                           vault_run=_vault("PASS"), bus_run=_silent_bus())
    assert st["status"] == "parked"
    assert st["parked"] is True
    # parks AT the hard-gate phase ("review", index 3), not past it (I5).
    assert st["current_phase"] == 3
    assert st["gate_verdicts"]["review"]["satisfied"] is True


def test_flow_stops_unparked_when_gate_fails(tmp_path):
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        st = flow.run_flow(_flow_def(), state_dir=tmp_path,
                           vault_run=_vault("REJECT"), bus_run=_silent_bus())
    # stops at the first gated phase ("test", index 2) — not parked, just blocked.
    assert st["status"] == "running"
    assert st["parked"] is False
    assert st["current_phase"] == 2
    assert st["gate_verdicts"]["test"]["satisfied"] is False


def test_flow_fails_closed_when_vault_unresolvable(tmp_path):
    with patch.object(flow, "resolve", return_value=None):
        st = flow.run_flow(_flow_def(), state_dir=tmp_path,
                           vault_run=_vault(), bus_run=_silent_bus())
    assert st["status"] == "running"  # blocked at the gate, not advanced
    assert st["current_phase"] == 2
    assert st["gate_verdicts"]["test"]["gate"] == "unavailable"


def test_status_reads_without_advancing(tmp_path):
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        flow.run_flow(_flow_def("s-1"), state_dir=tmp_path,
                      vault_run=_vault("PASS"), bus_run=_silent_bus())
    st = flow.status("s-1", state_dir=tmp_path)
    assert st["flow_id"] == "s-1"
    assert st["status"] == "parked"


def test_status_unknown_flow_is_none(tmp_path):
    assert flow.status("nope", state_dir=tmp_path) is None


def test_resume_advances_past_an_approved_hard_gate(tmp_path):
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        flow.run_flow(_flow_def("r-1"), state_dir=tmp_path,
                      vault_run=_vault("PASS"), bus_run=_silent_bus())
        # human approved the parked hard gate out-of-band -> resume.
        st = flow.resume("r-1", state_dir=tmp_path,
                         vault_run=_vault("PASS"), bus_run=_silent_bus())
    assert st["status"] == "completed"
    assert st["parked"] is False
    assert st["current_phase"] == 4


def test_resume_unknown_flow_returns_none(tmp_path):
    assert flow.resume("nope", state_dir=tmp_path,
                       vault_run=_silent_bus(), bus_run=_silent_bus()) is None


def test_flow_is_archetype_agnostic(tmp_path):
    # A flow def with a made-up archetype-shaped name still runs purely off
    # gate/hitl fields — loom must not branch on archetype names (I6).
    fd = {"flow_id": "x-1",
          "phases": [{"name": "totally-made-up-phase", "gate": None, "hitl": "none"}],
          "peers_required": [], "verifier_spec_ref": None}
    with patch.object(flow, "resolve", return_value=["wicked-vault"]):
        st = flow.run_flow(fd, state_dir=tmp_path,
                           vault_run=_vault(), bus_run=_silent_bus())
    assert st["status"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_flow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.flow'`

- [ ] **Step 3: Write `flow.py`**

```python
"""flow.py — the archetype-agnostic flow runner (conduct orchestration).

Executes a declarative flow definition (spec §3.1): advance phases; on a gated
phase, re-derive synchronously via gate.py; park at a hard gate; persist state
via flowstate.py; announce transitions via busemit.py (best-effort).

Invariants (spec §5):
  I1/I2/I3 — inherited from gate.py (synchronous, fail-closed, fail-soft spec).
  I4 — bus emission is best-effort and never gates; an event never advances a
       phase. Only a re-derived gate verdict advances.
  I5 — autonomy never overrides a hard gate: on a satisfied hard:* gate the flow
       PARKS and emits needs-human; it never self-approves. ``resume`` advances
       past an approved hard gate only because a human acted out-of-band.
  I6 — archetype-agnostic: this module branches ONLY on the flow definition's
       ``gate`` / ``hitl`` fields, never on archetype names.

The vault runner and bus runner are injected (``vault_run`` / ``bus_run``) so a
flow test never spawns a real vault or bus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from loom import busemit, flowstate
from loom.compose import RunResult, _default_run
from loom.gate import run_gate
from loom.resolve import resolve  # re-exported so tests can patch flow.resolve

Runner = Callable[..., RunResult]

_GATE_PREFIX = "produces:"


def _is_hard(hitl: Optional[str]) -> bool:
    """A hard gate is any hitl discipline of the form ``hard:*`` (spec §3.1)."""
    return isinstance(hitl, str) and hitl.startswith("hard:")


def _produces_of(gate_spec: str) -> str:
    """Map a flow-def gate string to the vault produces id.

    "produces:test-report" -> "test-report". A non-"produces:" gate string is
    passed through verbatim (still re-derived; never a vacuous pass — I2).
    """
    if gate_spec.startswith(_GATE_PREFIX):
        return gate_spec[len(_GATE_PREFIX):]
    return gate_spec


def _advance(state: dict, *, state_dir: Path,
             vault_run: Runner, bus_run: Runner) -> dict:
    """Run the phase loop from state['current_phase']; persist + return state."""
    phases = state["phases"]
    flow_id = state["flow_id"]
    verifier_spec = state.get("verifier_spec_ref")

    while state["current_phase"] < len(phases):
        phase = phases[state["current_phase"]]
        name = phase.get("name", str(state["current_phase"]))
        gate_spec = phase.get("gate")
        hitl = phase.get("hitl")

        if not gate_spec:
            busemit.emit("phase-advanced",
                         {"flow_id": flow_id, "phase": name}, run=bus_run)
            state["current_phase"] += 1
            continue

        verdict = run_gate(_produces_of(gate_spec), scope=flow_id,
                           with_attestations=_is_hard(hitl),
                           verifier_spec=verifier_spec, run=vault_run)
        state["gate_verdicts"][name] = verdict

        if not verdict.get("satisfied"):
            busemit.emit("gate-failed",
                         {"flow_id": flow_id, "phase": name,
                          "overall": verdict.get("overall")}, run=bus_run)
            flowstate.save_state(state, state_dir=state_dir)
            return state  # blocked on evidence; status stays "running" (I2)

        busemit.emit("gate-passed",
                     {"flow_id": flow_id, "phase": name}, run=bus_run)

        if _is_hard(hitl):
            state["parked"] = True
            state["parked_reason"] = f"hard gate at phase '{name}' ({hitl})"
            state["status"] = flowstate.STATUS_PARKED
            busemit.emit("needs-human",
                         {"flow_id": flow_id, "phase": name, "hitl": hitl},
                         run=bus_run)
            flowstate.save_state(state, state_dir=state_dir)
            return state  # PARK — loom never self-approves a hard gate (I5)

        busemit.emit("phase-advanced",
                     {"flow_id": flow_id, "phase": name}, run=bus_run)
        state["current_phase"] += 1

    state["status"] = flowstate.STATUS_COMPLETED
    busemit.emit("completed", {"flow_id": flow_id}, run=bus_run)
    flowstate.save_state(state, state_dir=state_dir)
    return state


def run_flow(flow_def: dict, *, state_dir: Path,
             vault_run: Runner = _default_run,
             bus_run: Runner = _default_run) -> dict:
    """Start a new flow: build state, emit started, advance through phases."""
    state = flowstate.new_state(flow_def, state_dir=state_dir)
    flowstate.save_state(state, state_dir=state_dir)
    busemit.emit("started", {"flow_id": state["flow_id"]}, run=bus_run)
    return _advance(state, state_dir=state_dir,
                    vault_run=vault_run, bus_run=bus_run)


def status(flow_id: str, *, state_dir: Path) -> Optional[dict]:
    """Read persisted flow state without advancing or any side effect."""
    return flowstate.load_state(flow_id, state_dir=state_dir)


def resume(flow_id: str, *, state_dir: Path,
           vault_run: Runner = _default_run,
           bus_run: Runner = _default_run) -> Optional[dict]:
    """Resume a parked/running flow. If parked at a hard gate, a human has
    approved it out-of-band (I5) — advance PAST that phase without re-running
    its gate, then continue the normal loop."""
    state = flowstate.load_state(flow_id, state_dir=state_dir)
    if state is None:
        return None
    if state.get("parked"):
        state["parked"] = False
        state["parked_reason"] = None
        state["status"] = flowstate.STATUS_RUNNING
        state["current_phase"] += 1  # human-approved hard gate: step past it
    return _advance(state, state_dir=state_dir,
                    vault_run=vault_run, bus_run=bus_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_flow.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/flow.py tests/test_flow.py
git commit -m "feat: archetype-agnostic flow runner with park-at-hard-gate (conduct)"
```

---

## Task 5: CLI surface — `gate` + `flow` (run|status|resume)

**Files:**
- Modify: `~/Projects/wicked-loom/python/loom/cli.py`
- Modify: `~/Projects/wicked-loom/tests/test_cli.py`

Extend Plan A's dispatch with two commands. Logic stays in `gate.py`/`flow.py` (R6 — `cli.py` only parses args + formats JSON). State directory defaults to a project-scoped local path; a `--state-dir` flag overrides it (tests pass `--state-dir`).

- `loom gate <produces> [--scope S] [--verifier-spec PATH] [--with-attestations]` → `{"gate": <verdict>}`; exit 0 iff satisfied.
- `loom flow run <flow-def.json> [--state-dir D]` → `{"flow": <state>}`; exit 0 iff status `completed`, 2 if parked/blocked.
- `loom flow status <flow-id> [--state-dir D]` → `{"flow": <state>}`; exit 0 if found, 1 if not.
- `loom flow resume <flow-id> [--state-dir D]` → `{"flow": <state>}`; exit 0 iff `completed`, 2 if parked/blocked, 1 if not found.

- [ ] **Step 1: Write the failing test (append to `tests/test_cli.py`)**

```python
import json as _json
import os
from unittest.mock import patch

# (re-uses the _run helper + imports already at the top of test_cli.py)


def test_gate_command_satisfied_exits_zero():
    verdict = {"satisfied": True, "overall": "PASS", "gate": "vault-cross-check"}
    with patch("loom.cli.run_gate", return_value=verdict) as m:
        code, out = _run(["gate", "test-report", "--scope", "build-1"])
    assert code == 0
    assert _json.loads(out)["gate"]["satisfied"] is True
    m.assert_called_once()


def test_gate_command_unsatisfied_exits_one():
    verdict = {"satisfied": False, "overall": "REJECT", "gate": "vault-cross-check"}
    with patch("loom.cli.run_gate", return_value=verdict):
        code, _ = _run(["gate", "test-report", "--scope", "build-1"])
    assert code == 1


def test_gate_command_forwards_flags():
    with patch("loom.cli.run_gate", return_value={"satisfied": True}) as m:
        _run(["gate", "verdict", "--scope", "b1",
              "--verifier-spec", "/tmp/v.json", "--with-attestations"])
    _, kwargs = m.call_args
    assert kwargs["scope"] == "b1"
    assert kwargs["verifier_spec"] == "/tmp/v.json"
    assert kwargs["with_attestations"] is True


def test_gate_requires_produces_arg():
    code, _ = _run(["gate"])
    assert code == 2


def test_flow_run_completed_exits_zero(tmp_path):
    fd = {"flow_id": "cli-1",
          "phases": [{"name": "a", "gate": None, "hitl": "none"}],
          "peers_required": [], "verifier_spec_ref": None}
    p = tmp_path / "flow.json"
    p.write_text(_json.dumps(fd), encoding="utf-8")
    completed = {"flow_id": "cli-1", "status": "completed"}
    with patch("loom.cli.run_flow", return_value=completed) as m:
        code, out = _run(["flow", "run", str(p), "--state-dir", str(tmp_path)])
    assert code == 0
    assert _json.loads(out)["flow"]["status"] == "completed"
    m.assert_called_once()


def test_flow_run_parked_exits_two(tmp_path):
    fd = {"flow_id": "cli-2", "phases": [], "peers_required": [],
          "verifier_spec_ref": None}
    p = tmp_path / "flow.json"
    p.write_text(_json.dumps(fd), encoding="utf-8")
    with patch("loom.cli.run_flow", return_value={"status": "parked"}):
        code, _ = _run(["flow", "run", str(p), "--state-dir", str(tmp_path)])
    assert code == 2


def test_flow_status_found_exits_zero(tmp_path):
    with patch("loom.cli.flow_status", return_value={"flow_id": "x", "status": "running"}):
        code, out = _run(["flow", "status", "x", "--state-dir", str(tmp_path)])
    assert code == 0
    assert _json.loads(out)["flow"]["flow_id"] == "x"


def test_flow_status_missing_exits_one(tmp_path):
    with patch("loom.cli.flow_status", return_value=None):
        code, _ = _run(["flow", "status", "nope", "--state-dir", str(tmp_path)])
    assert code == 1


def test_flow_resume_completed_exits_zero(tmp_path):
    with patch("loom.cli.flow_resume", return_value={"status": "completed"}):
        code, _ = _run(["flow", "resume", "x", "--state-dir", str(tmp_path)])
    assert code == 0


def test_flow_resume_missing_exits_one(tmp_path):
    with patch("loom.cli.flow_resume", return_value=None):
        code, _ = _run(["flow", "resume", "nope", "--state-dir", str(tmp_path)])
    assert code == 1


def test_flow_unknown_subcommand_exits_two():
    code, _ = _run(["flow", "frobnicate"])
    assert code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_cli.py -v`
Expected: FAIL — the new tests error (`AttributeError: <module 'loom.cli'> does not have the attribute 'run_gate'` / unknown command `gate`). The 6 Plan A cli tests still PASS.

- [ ] **Step 3: Edit `cli.py` — add imports**

Replace the import block (currently importing only `manifest`, `check_all`, `install_peer`, `resolve`) so it also brings in the conduct entry points. The full new import block:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from loom import manifest
from loom.compose import check_all, install_peer
from loom.resolve import resolve
from loom.gate import run_gate
from loom.flow import run_flow, status as flow_status, resume as flow_resume
```

- [ ] **Step 4: Edit `cli.py` — add the state-dir default + `gate` handler**

Add this helper and handler above the `_DISPATCH` table:

```python
def _default_state_dir() -> Path:
    """Project-scoped local state dir. Honors WICKED_LOOM_STATE_DIR; else a
    cwd-anchored .wicked-loom/flows dir (deterministic, no network — spec §10)."""
    import os
    override = os.environ.get("WICKED_LOOM_STATE_DIR", "").strip()
    if override:
        return Path(override)
    return Path.cwd() / ".wicked-loom" / "flows"


def _opt(args: list, name: str) -> "str | None":
    """Return the value following ``--name`` in args, or None."""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def _cmd_gate(args: list) -> int:
    positional = [a for a in args if not a.startswith("--")]
    # Strip values that belong to --scope / --verifier-spec from positionals.
    scope = _opt(args, "--scope") or "default"
    verifier_spec = _opt(args, "--verifier-spec")
    consumed = {scope, verifier_spec}
    produces = next((a for a in positional if a not in consumed), None)
    if produces is None:
        _emit({"error": "usage: loom gate <produces> [--scope S] "
                        "[--verifier-spec PATH] [--with-attestations]"})
        return 2
    verdict = run_gate(produces, scope=scope, verifier_spec=verifier_spec,
                       with_attestations="--with-attestations" in args)
    _emit({"gate": verdict})
    return 0 if verdict.get("satisfied") else 1
```

- [ ] **Step 5: Edit `cli.py` — add the `flow` handler**

Add this handler above the `_DISPATCH` table:

```python
def _cmd_flow(args: list) -> int:
    if not args:
        _emit({"error": "usage: loom flow <run|status|resume> ..."})
        return 2
    sub, rest = args[0], args[1:]
    state_dir = Path(_opt(rest, "--state-dir") or _default_state_dir())
    positional = [a for a in rest if not a.startswith("--") and a != str(state_dir)]

    if sub == "run":
        if not positional:
            _emit({"error": "usage: loom flow run <flow-def.json> [--state-dir D]"})
            return 2
        flow_def = json.loads(Path(positional[0]).read_text(encoding="utf-8"))
        st = run_flow(flow_def, state_dir=state_dir)
        _emit({"flow": st})
        return 0 if st.get("status") == "completed" else 2

    if sub == "status":
        if not positional:
            _emit({"error": "usage: loom flow status <flow-id> [--state-dir D]"})
            return 2
        st = flow_status(positional[0], state_dir=state_dir)
        _emit({"flow": st})
        return 0 if st is not None else 1

    if sub == "resume":
        if not positional:
            _emit({"error": "usage: loom flow resume <flow-id> [--state-dir D]"})
            return 2
        st = flow_resume(positional[0], state_dir=state_dir)
        _emit({"flow": st})
        if st is None:
            return 1
        return 0 if st.get("status") == "completed" else 2

    _emit({"error": f"unknown flow subcommand: {sub}",
           "subcommands": ["run", "status", "resume"]})
    return 2
```

- [ ] **Step 6: Edit `cli.py` — register both in `_DISPATCH`**

Change the dispatch table to include the conduct commands:

```python
_DISPATCH = {
    "resolve": _cmd_resolve,
    "doctor": _cmd_doctor,
    "compose": _cmd_compose,
    "gate": _cmd_gate,
    "flow": _cmd_flow,
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_cli.py -v`
Expected: PASS — 17 tests (6 Plan A + 11 new conduct cases).

- [ ] **Step 8: Smoke the full path through the Node shim (fail-closed, no vault)**

Run:
```bash
cd ~/Projects/wicked-loom && WICKED_VAULT_BIN="" node bin/loom.mjs gate test-report --scope smoke
```
Expected: a JSON line whose `gate.gate == "unavailable"` and `gate.satisfied == false`, exit code 1 — proving the shim → python3 → conduct path works AND the gate fails closed when the vault is killed (I2). (`echo $?` → `1`.)

- [ ] **Step 9: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/cli.py tests/test_cli.py
git commit -m "feat: conduct CLI — gate + flow run/status/resume"
```

---

## Task 6: README conduct section + full suite + publish-readiness

**Files:**
- Modify: `~/Projects/wicked-loom/README.md`

- [ ] **Step 1: Append a conduct section to `README.md`**

```markdown
## Conduct (gate + flow)

Synchronous, fail-closed evidence gating and an archetype-agnostic flow runtime.

    npx wicked-loom gate test-report --scope build-1        # re-derive one produces via the vault
    npx wicked-loom gate verdict --scope b1 --with-attestations
    npx wicked-loom flow run ./flow-def.json                 # run a flow definition
    npx wicked-loom flow status build-1                      # read a flow's state
    npx wicked-loom flow resume build-1                      # continue past an approved hard gate

**Invariants:** gates are synchronous and re-derive every call (an event never
satisfies a gate); a missing vault fails **closed** (`gate: "unavailable"`,
never a pass); the verifier spec is fail-**soft** (absent → generic detection,
never blocks). The runner is archetype-agnostic — it executes any flow
definition (`phases[]` with optional `gate`/`hitl`, `peers_required`,
`verifier_spec_ref`) and parks at any `hard:*` gate, never self-approving.

The headless bus-consumer / unattended execution mode is **deferred** — this
release emits transition events best-effort but does not react to them.

## Flow definition

    {
      "flow_id": "build-1",
      "phases": [
        { "name": "plan",   "gate": null,                   "hitl": "none" },
        { "name": "test",   "gate": "produces:test-report", "hitl": "discrete:review" },
        { "name": "review", "gate": "produces:verdict",     "hitl": "hard:final-verdict" }
      ],
      "peers_required": ["vault", "testing"],
      "verifier_spec_ref": null
    }
```

- [ ] **Step 2: Run the full suite**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest -v`
Expected: PASS — 50 tests total: 22 Plan A (4 manifest + 5 resolve + 7 compose + 6 cli)… now cli is 17, so the count is **22 Plan A non-cli + new** → exact tally: 4 manifest + 5 resolve + 7 compose + 17 cli + 8 gate + 6 flowstate + 5 busemit + 9 flow = **61 tests**.

- [ ] **Step 3: Dry-run the npm package contents**

Run: `cd ~/Projects/wicked-loom && npm pack --dry-run`
Expected: the tarball lists `bin/`, `python/` (now including `gate.py`, `flow.py`, `flowstate.py`, `busemit.py`), `README.md`, `package.json` — and NOT `tests/` or `__pycache__/`.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/wicked-loom
git add README.md
git commit -m "docs: README conduct section + flow-def reference"
```

- [ ] **Step 5: STOP — version bump + publish are human-gated**

Do **not** run `npm publish` autonomously. Conduct adds a feature surface → this is a **minor** bump (`0.1.0` → `0.2.0`); report to the operator that conduct is implemented (suite green, `npm pack` clean) and let them bump `package.json`/`__init__.py`, publish, and tag. The garden-side cutover (shelling garden's `gate`/`flow` shims to loom + the archetype→flow compiler) is a separate plan.

---

## Self-Review

**1. Spec coverage** — checked against §4.2 (conduct module), §4.3 (surfaces/CLI/events), §5 (invariants I1–I6):

| Spec item | Where realized |
|---|---|
| §4.2 Execute a gate — sync vault re-derive via `cross-check` | Task 1 `gate.run_gate` (ported from `vault_gate.cross_check`). ✓ |
| §4.2 Missing vault → `unavailable`, fail-closed, never vacuous pass (**I2**) | Task 1 `test_gate_fails_closed_when_vault_unresolvable` / `_unrunnable` / `_on_non_json_output`. ✓ |
| §4.2 Hard gates require independent attestation (`--with-attestations`) | Task 1 `test_with_attestations_forwarded`; Task 4 forwards `with_attestations=_is_hard(hitl)`. ✓ |
| §4.2 `verifier_spec_ref` present → read it; absent/stale → generic, never blocks (**I3**) | Task 1 `test_verifier_spec_forwarded` + `_absent_is_fail_soft`; Task 4 threads `verifier_spec_ref` through. ✓ |
| §4.2 Run a flow — advance phases, persist state | Task 4 `run_flow`/`_advance` + Task 2 `flowstate`. ✓ |
| §4.2 Park at hard gate — stop + emit `needs-human`, do not self-approve (**I5**) | Task 4 `test_flow_parks_at_hard_gate_after_pass`. ✓ |
| §4.2 Project (bus consumer / headless) | **DEFERRED** — explicitly out of scope (D3 / §9). Stated up-front + in README. ✓ (intentional gap) |
| §4.3 CLI `loom gate <produces> [--verifier-spec] [--with-attestations]` | Task 5 `_cmd_gate`. ✓ |
| §4.3 CLI `loom flow run|status|resume` | Task 5 `_cmd_flow`. ✓ |
| §4.3 Event contract `loom:flow:started\|phase-advanced\|gate-passed\|gate-failed\|needs-human\|completed` | Task 3 `busemit.EVENTS` (exact strings asserted in `test_event_names_are_the_spec_set`); emitted in Task 4. ✓ |
| §4.3 Bus-consumer / daemon surface | **DEFERRED** (D3). ✓ (intentional gap) |
| **I1** gate synchronous + in-line, event never satisfies | Task 1 (one blocking call, no events read); reinforced by Task 3/4 separation (bus is emission-only). ✓ |
| **I2** fail-closed | Task 1 + Task 4 `test_flow_fails_closed_when_vault_unresolvable`. ✓ |
| **I3** fail-soft on verifier spec only | Task 1 (absence never blocks). ✓ |
| **I4** bus = spine for non-verdict; event never satisfies a gate | Task 3 `busemit` is fire-and-forget, returns bool, never feeds gate logic; Task 4 ignores emit results. ✓ |
| **I5** autonomy never overrides a hard gate | Task 4 park-at-hard-gate; `resume` only advances because a human acted out-of-band. ✓ |
| **I6** archetype-agnostic | Task 4 `test_flow_is_archetype_agnostic`; `flow.py` branches only on `gate`/`hitl`. ✓ |
| §5/§10 state deterministic, no network | Task 2 `flowstate` (injected `state_dir`, atomic write, no subprocess); flow/gate runners injected. ✓ |
| Reuse `resolve.resolve()` for vault resolution | Task 1 `gate.py` imports `from loom.resolve import resolve`. ✓ |
| Match compose.py runner-injection pattern | Tasks 1/3/4 use `RunResult`/`Runner`/`_default_run` from `compose.py`. ✓ |

No unintended gaps. The only uncovered spec bullets (§4.2 "Project", §4.3 surface #2 daemon) are the **deferred** headless mode — explicitly excluded by D3 and flagged in three places (header "Out of scope", README, this table).

**2. Placeholder scan** — No `TBD`/`TODO`/"add error handling"/"handle edge cases"/"similar to Task N". Every code step shows complete, runnable code. Every run step shows the exact `PYTHONPATH=python python3 -m pytest …` command and expected pass/fail. Error handling is concrete everywhere (gate fail-closed branches written out; busemit `except Exception` documented as the I4 boundary; flowstate `ValueError` on unsafe id). ✓

**3. Type consistency** —
- `RunResult(returncode, stdout, stderr)` and the `Runner = Callable[..., RunResult]` alias are imported from `compose.py` and used identically in `gate.py`, `busemit.py`, `flow.py`, and every test (`_runner`/`_vault`/`_silent_bus` all build `RunResult`). ✓
- `run_gate(produces, *, scope, with_attestations=False, verifier_spec=None, run=…, timeout=…) -> dict`: the signature in Task 1 matches every call site — Task 4 (`run_gate(_produces_of(gate_spec), scope=flow_id, with_attestations=_is_hard(hitl), verifier_spec=verifier_spec, run=vault_run)`) and Task 5 (`run_gate(produces, scope=scope, verifier_spec=verifier_spec, with_attestations=…)`). The CLI test asserts kwargs `scope`/`verifier_spec`/`with_attestations` — all present. ✓
- `flowstate`: `new_state(flow_def, *, state_dir)`, `save_state(state, *, state_dir)`, `load_state(flow_id, *, state_dir)` — used with identical keyword `state_dir` in `flow.py` and the tests. Status constants `STATUS_RUNNING/PARKED/COMPLETED` referenced from `flow.py` consistently. ✓
- `flow`: `run_flow(flow_def, *, state_dir, vault_run, bus_run)`, `status(flow_id, *, state_dir)`, `resume(flow_id, *, state_dir, vault_run, bus_run)` — `cli.py` imports them as `run_flow`, `status as flow_status`, `resume as flow_resume` and calls with matching kwargs. ✓
- `busemit.emit(event_key, payload, *, run) -> bool` — called from `flow.py` with the event keys `"started"`/`"phase-advanced"`/`"gate-passed"`/`"gate-failed"`/`"needs-human"`/`"completed"`, all of which are keys in `EVENTS`. ✓
- State dict keys (`flow_id`, `phases`, `current_phase`, `gate_verdicts`, `parked`, `parked_reason`, `status`, `verifier_spec_ref`) are written by `flowstate.new_state` and read by `flow._advance`/`resume` with the same names. ✓

One self-review fix applied inline: Task 6 Step 2's expected count was first written as "50" then corrected to the exact tally **61** (4+5+7+17+8+6+5+9), because cli grows from 6 → 17 tests in Task 5. The per-task expected counts (8/6/5/9/17) are the authoritative figures.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-08-wicked-loom-conduct.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in this session with checkpoints. REQUIRED SUB-SKILL: `superpowers:executing-plans`.

Notes for the executor:
- Execution happens in the **existing** `~/Projects/wicked-loom` repo (the package Plan A created), NOT in wicked-garden. Plan A (compose) must already be merged there.
- Read garden's `scripts/qe/vault_gate.py` and `scripts/crew/phase_manager.py` for grounding before Task 1/Task 2, but **import nothing from garden** — loom is a standalone primitive (success criterion #1).
- Every test is hermetic: vault and bus subprocesses are injected; `state_dir` is a `tmp_path`. No test may spawn a real vault/bus or touch the network (T1/T3).
- The headless daemon / bus-consumer is DEFERRED (D3). Do not build it. If a need surfaces, it is a separate plan that consumes the event contract `busemit.py` already produces.

**Which approach?**
