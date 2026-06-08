# wicked-loom — Cutover Phase (garden-side strangler migration) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut wicked-garden's in-process runtime over to the shipped `wicked-loom` CLI, **one surface at a time, lowest-risk first** — `resolve` → `gate` → `flow` — then add `wicked-loom` as the 5th required peer and introduce the garden archetype→flow-definition compiler (the §3.1 seam). Each cutover ships behind a **contract test** asserting the loom-shelled path produces results IDENTICAL to the in-process path it replaces (the strangler safety net), and stays **fail-soft during transition** (loom unresolvable → fall back to the still-present in-process code; gates still fail **closed**). The old in-process code is LEFT IN PLACE behind the shim — rollback is trivial. Deleting it is the **contract** phase (a later plan).

**Architecture:** Garden already invokes Python via `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <script.py>` and peers via `npx <peer>`. The cutover adds one thin garden-side module — `scripts/_loom.py` — that resolves the loom CLI on a ladder mirroring the vault's (`WICKED_LOOM_BIN` → config → `PATH` → `node_modules/.bin` → `npx wicked-loom`, with `WICKED_LOOM_BIN=""` as the kill-switch) and runs it as a subprocess returning parsed JSON. Each cutover target (`resolve_vault`, `cross_check`/`gate_satisfied`, phase mechanics) gains a **try-loom-first, fall-back-to-in-process** branch gated by a single feature flag (`WICKED_LOOM_CUTOVER`, default `auto`). No in-process function is deleted; each grows a shim head. The flow-definition compiler (`scripts/crew/flow_compiler.py`) is a NEW pure module that reads `.claude-plugin/archetypes.json` + the `_HARD_GATE_PHASES` map and emits the §3.1 flow-definition JSON that `loom flow run` consumes.

**Tech Stack:** Python 3.9+ (stdlib only — mirrors garden's hook discipline; loom is reached as a subprocess, never imported). `pytest` (garden's existing suite; `testpaths = ["tests"]`, `tests/conftest.py` puts `scripts/` on `sys.path[0]`). Tests inject the loom subprocess runner (same pattern as `vault_gate._run`) so no test spawns a real loom or touches the network. The shipped loom CLI surface this plan targets:

- `loom resolve <peer>` → `{"peer","command":[...]|null}`, exit 0 iff resolvable (wicked-loom 0.1.0).
- `loom gate <produces> --scope S [--verifier-spec PATH] [--with-attestations]` → `{"gate": <verdict>}`, exit 0 iff `gate.satisfied` (wicked-loom 0.2.0 / conduct).
- `loom flow run <flow-def.json> [--state-dir D]` · `loom flow status <flow-id>` · `loom flow resume <flow-id>` → `{"flow": <state>}` (wicked-loom 0.2.0 / conduct).

**Decisions locked for this plan (override in review):**
- **loom resolution ladder = a faithful mirror of the vault ladder** (D5; §10 invariants). `WICKED_LOOM_BIN` env (empty = kill-switch) → `tool_preferences.wicked-loom` in `config.json` → `wicked-loom` on `PATH` → `node_modules/.bin/wicked-loom` → `npx --yes wicked-loom`. This is the exact shape of `vault_gate.resolve_vault`, lifted to a peer-neutral helper.
- **One cutover feature flag, `WICKED_LOOM_CUTOVER`** ∈ `{auto, on, off}`, default `auto`. `auto` = use loom **iff resolvable**, else in-process (the transition default). `on` = loom required for that surface (used by the contract tests to force the loom path). `off` = in-process only (instant rollback / kill-switch). Read once per call via a tiny `_loom.cutover_mode()` helper.
- **Garden never imports loom Python** — it shells `npx wicked-loom` (or the resolved bin) exactly as it shells the vault. Loom stays a sibling primitive; garden's plugin packaging stays decoupled from loom's Python env (D5).
- **Gate fail-closed posture is preserved verbatim.** The loom `gate` path and the in-process `gate_satisfied` path BOTH fail closed when the vault is unresolvable. Loom unresolvable for the *gate surface* falls back to the in-process gate (which itself fails closed) — never a vacuous pass (I2).
- **`flow` cutover is additive, not a replacement of `phase_manager`'s storage.** Garden keeps `phase_manager` as its project-state store; the `flow` cutover mirrors *advance/approve/park* decisions through `loom flow` and contract-tests that the park-at-hard-gate verdict matches `_HARD_GATE_PHASES`. The DomainStore-backed `ProjectState` is unchanged (it is part of the STAY surface; the contract phase decides its fate).
- **Target repos:** garden = `~/Projects/wicked-garden` (this plan edits it); loom = `~/Projects/wicked-loom` (consumed as a published peer `npx wicked-loom`, **not** edited here; conduct/0.2.0 must be published first — see Execution Handoff).

**Source material to read in wicked-garden before Task 1 (grounding):**
- `scripts/qe/vault_gate.py` — the `resolve_vault` ladder (lines 69–106), `_argv_for` (58–66), `_read_config_preference` (117–130), `cross_check` (170–213), `gate_satisfied` (220–293), and the CLI dispatch (304–348). The `resolve` and `gate` cutovers shim these.
- `scripts/crew/phase_manager.py` — `_HARD_GATE_PHASES` (287–296), `_is_hard_gate` (299–304), `approve_phase` (307–422), and the CLI (460–610). The `flow` cutover mirrors these decisions through `loom flow`.
- `.claude-plugin/archetypes.json` — `archetypes.{name}.{phases,produces,hitl}` and `$hitl_levels`. The flow compiler reads this.
- `docs/required-peers.md` — the four-peer table + "required at install, resilient at runtime" stance. Task 4 adds loom as the 5th row.
- `commands/setup.md` §2.5–2.7 — the per-peer verify pattern. Task 4 adds a loom verify step in the same shape.
- Plan A (`docs/plans/2026-06-08-wicked-loom-expand-compose.md`) and Plan B (`docs/plans/2026-06-08-wicked-loom-conduct.md`) — the exact loom CLI contract (commands, JSON output keys, exit codes) this plan shells to.

**Out of scope (DEFERRED — do NOT do in this plan):**
- The **CONTRACT phase** — deleting the now-dead in-process runtime code (the `→ loom` rows in spec §6). That is a separate, *later* plan, run only after this cutover is proven in production. This cutover deliberately LEAVES the in-process code in place behind the shim so rollback is `WICKED_LOOM_CUTOVER=off` (or a one-line revert).
- The **headless daemon / bus-consumer** (spec D3, §9 D-headless). `loom flow` is driven synchronously from garden; no unattended execution, no projector.
- Editing the loom repo. Conduct (0.2.0) is Plan B's deliverable; this plan assumes it is published and reachable via `npx wicked-loom`.
- The compiler↔loom synergy (spec §9): the garden `/wicked-garden:compile` emitter stays self-contained and resolves the vault directly via npx — untouched here.

**Bulletproof standards:** R1–R6 (no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions) and T1–T6 (determinism, no sleep-based sync, isolation, single-assertion focus, descriptive names, provenance). The loom subprocess is injected everywhere so no unit test spawns a real loom or hits the network. Contract tests are the load-bearing artifact: each asserts `loom_path(x) == in_process_path(x)` for the same inputs.

---

## File Structure

```
wicked-garden/
├── scripts/
│   ├── _loom.py                 # NEW — peer-neutral loom CLI resolver + JSON subprocess runner
│   │                            #        + cutover_mode() flag. Mirrors vault_gate's ladder.
│   ├── qe/
│   │   └── vault_gate.py        # MODIFY — resolve_vault grows a loom-first head (Task 1);
│   │                            #          cross_check grows a loom-gate head (Task 2).
│   │                            #          In-process bodies STAY as the fallback.
│   └── crew/
│       ├── flow_compiler.py     # NEW — archetype catalog → flow-definition JSON (the §3.1 seam, Task 5)
│       └── phase_manager.py     # MODIFY — approve_phase/advance grow a loom-flow mirror head (Task 3);
│                                #          in-process body STAYS.
├── hooks/scripts/
│   └── bootstrap.py             # MODIFY — _check_loom_dependency added (Task 4, peer-detection portion only)
├── docs/
│   └── required-peers.md        # MODIFY — add the 5th peer row + stance note (Task 4)
├── commands/
│   └── setup.md                 # MODIFY — add §2.8 Verify wicked-loom (Task 4)
├── .claude-plugin/
│   └── plugin.json              # MODIFY — add wicked-loom pin to the peer description (Task 4)
└── tests/
    ├── crew/
    │   ├── test_loom_resolver.py          # NEW — _loom.py unit tests (Task 0)
    │   ├── test_loom_resolve_contract.py  # NEW — resolve cutover contract test (Task 1)
    │   ├── test_loom_flow_contract.py     # NEW — flow cutover contract test (Task 3)
    │   └── test_flow_compiler.py          # NEW — archetype→flow-def compiler tests (Task 5)
    └── qe/
        └── test_loom_gate_contract.py     # NEW — gate cutover contract test (Task 2)
```

**Responsibilities (one per file, justifying the layout):**
- `scripts/_loom.py` = *find loom + run it + read the flag* (the only file that knows how to reach the loom CLI). Peer-neutral resolution helper (mirrors `vault_gate.resolve_vault`), a JSON subprocess runner, and `cutover_mode()`. Pure of any surface logic — `resolve`/`gate`/`flow` shims call into it.
- `scripts/qe/vault_gate.py` (modified) = keeps both paths for the resolve + gate surfaces; the shim head tries loom, the unchanged body is the fallback. One responsibility per function still holds — the head is a 4-line guard, not a rewrite.
- `scripts/crew/flow_compiler.py` = *translate one archetype into a flow definition* (the §3.1 handoff contract). Pure, deterministic, reads the catalog + the hard-gate map; emits the JSON loom consumes. No I/O beyond reading the catalog.
- `scripts/crew/phase_manager.py` (modified) = keeps its DomainStore state authority; the shim head mirrors the advance/park decision through `loom flow` for parity, never replacing the disk write.
- `hooks/scripts/bootstrap.py` (modified) = adds one peer-detection function in the exact shape of `_check_vault_dependency` / `_check_bus_dependency`.

Why `_loom.py` is its own file and not folded into `vault_gate.py`: it is peer-neutral (used by the resolve, gate, AND flow cutovers) and must be importable from `scripts/` and `scripts/crew/` alike; co-locating it with the vault gate would couple three surfaces to one. Why the compiler is separate from `phase_manager.py`: the compiler is pure catalog→JSON with zero state; mixing it into the stateful phase manager would violate R6.

**The flow-definition shape this plan emits** (spec §3.1; consumed verbatim by `loom flow run`, per Plan B):

```jsonc
{
  "flow_id": "build-<project>",
  "phases": [
    { "name": "plan",      "gate": null,                   "hitl": "none",              "produces": [] },
    { "name": "implement", "gate": null,                   "hitl": "none",              "produces": [] },
    { "name": "test",      "gate": "produces:test-report", "hitl": "discrete:review",   "produces": ["test-report"] },
    { "name": "review",    "gate": "produces:verdict",     "hitl": "hard:final-verdict","produces": ["verdict"] }
  ],
  "peers_required": ["vault", "testing"],
  "verifier_spec_ref": null
}
```

---

## Task 0: The loom CLI resolver + JSON runner + cutover flag (`scripts/_loom.py`)

**Files:**
- Create: `~/Projects/wicked-garden/scripts/_loom.py`
- Test: `~/Projects/wicked-garden/tests/crew/test_loom_resolver.py`

This is the foundation every cutover stands on: resolve the loom CLI on a ladder that mirrors the vault's, run it as a subprocess that returns parsed JSON, and read the `WICKED_LOOM_CUTOVER` flag. Ported in shape from `vault_gate.resolve_vault` / `_argv_for` / `_read_config_preference` / `_run`, generalized to "loom" and made injectable for tests (the `run` parameter, same as `vault_gate`).

- [ ] **Step 1: Write the failing test**

```python
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import _loom  # noqa: E402


class ResolveLadderTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("WICKED_LOOM_BIN")
        os.environ.pop("WICKED_LOOM_BIN", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("WICKED_LOOM_BIN", None)
        else:
            os.environ["WICKED_LOOM_BIN"] = self._saved

    def test_env_override_wins(self):
        os.environ["WICKED_LOOM_BIN"] = "/opt/custom/loom"
        self.assertEqual(_loom.resolve_loom(), ["/opt/custom/loom"])

    def test_empty_env_is_killswitch(self):
        os.environ["WICKED_LOOM_BIN"] = ""
        self.assertIsNone(_loom.resolve_loom())

    def test_mjs_override_invoked_via_node(self):
        os.environ["WICKED_LOOM_BIN"] = "/some/loom.mjs"
        self.assertEqual(_loom.resolve_loom(), ["node", "/some/loom.mjs"])

    def test_path_lookup_when_no_env(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/local/bin/wicked-loom" if b == "wicked-loom" else None):
            self.assertEqual(_loom.resolve_loom(allow_npx=False), ["/usr/local/bin/wicked-loom"])

    def test_npx_fallback_when_not_on_path(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertEqual(_loom.resolve_loom(), ["npx", "--yes", "wicked-loom"])

    def test_loom_available_excludes_npx(self):
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(_loom.loom_available())


class RunTests(unittest.TestCase):
    def test_run_returns_parsed_json_on_success(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0, "stdout": '{"peer":"vault","command":["npx","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["resolve", "vault"], _run=fake_run)
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(out["json"]["command"], ["npx", "wicked-vault"])

    def test_run_unresolvable_reports_error_not_raise(self):
        with patch.object(_loom, "resolve_loom", return_value=None):
            out = _loom.run_json(["resolve", "vault"])
        self.assertIsNone(out["json"])
        self.assertEqual(out["error"], "wicked-loom not resolvable")

    def test_run_non_json_output_is_error_not_raise(self):
        def fake_run(prefix, args, timeout):
            return {"exit_code": 0, "stdout": "not json", "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            out = _loom.run_json(["doctor"], _run=fake_run)
        self.assertIsNone(out["json"])
        self.assertIn("non-JSON", out["error"])


class CutoverModeTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("WICKED_LOOM_CUTOVER")
        os.environ.pop("WICKED_LOOM_CUTOVER", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("WICKED_LOOM_CUTOVER", None)
        else:
            os.environ["WICKED_LOOM_CUTOVER"] = self._saved

    def test_default_is_auto(self):
        self.assertEqual(_loom.cutover_mode(), "auto")

    def test_explicit_off(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        self.assertEqual(_loom.cutover_mode(), "off")

    def test_unknown_value_falls_back_to_auto(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "frobnicate"
        self.assertEqual(_loom.cutover_mode(), "auto")

    def test_use_loom_off_is_false(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        self.assertFalse(_loom.use_loom())

    def test_use_loom_auto_true_only_when_resolvable(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None):
            self.assertFalse(_loom.use_loom())
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]):
            self.assertTrue(_loom.use_loom())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_loom'`

- [ ] **Step 3: Write `scripts/_loom.py`**

```python
#!/usr/bin/env python3
"""_loom.py — resolve + run the wicked-loom CLI, peer-neutral.

The garden's strangler shim toward wicked-loom. Garden NEVER imports loom's
Python; it shells the published ``wicked-loom`` CLI exactly as it shells
``wicked-vault``. This module owns three things and nothing else:

  1. resolve_loom() — the runtime resolution ladder, a faithful mirror of
     vault_gate.resolve_vault: WICKED_LOOM_BIN env (empty = kill-switch) ->
     config tool_preferences.wicked-loom -> PATH -> node_modules/.bin -> npx.
  2. run_json() — run a loom subcommand, return {exit_code, json, stdout,
     stderr, error}. Never raises (R4 — surface as data). Non-JSON / not-found
     / timeout all come back as error, json=None.
  3. cutover_mode() / use_loom() — the WICKED_LOOM_CUTOVER feature flag
     ({auto,on,off}, default auto) that lets every cutover try loom first and
     fall back to the in-process path (the transition default), or be killed
     (off) for instant rollback.

Stdlib-only. Cross-platform (argv lists, shutil.which, no shell).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404 — argv lists only, shell=False
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
_DEFAULT_TIMEOUT = 120
_CUTOVER_MODES = ("auto", "on", "off")
_PACKAGE = "wicked-loom"
_ENV_BIN = "WICKED_LOOM_BIN"
_ENV_FLAG = "WICKED_LOOM_CUTOVER"


def _argv_for(target: str) -> List[str]:
    """A .mjs/.js path is a script -> invoke via node; else run directly."""
    if target.endswith((".mjs", ".js")):
        return ["node", target]
    return [target]


def _read_config_preference(key: str) -> Optional[str]:
    """Read ``tool_preferences.{key}`` from config.json; None on any error."""
    try:
        if not _CONFIG_PATH.exists():
            return None
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        prefs = data.get("tool_preferences")
        if isinstance(prefs, dict):
            value = prefs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    except (json.JSONDecodeError, OSError):
        return None


def resolve_loom(*, allow_npx: bool = True,
                 project_dir: Optional[Path] = None) -> Optional[List[str]]:
    """Return the argv prefix that invokes wicked-loom, or None.

    Ladder (first hit wins), mirroring vault_gate.resolve_vault:
      1. WICKED_LOOM_BIN env. Set-but-empty is the kill-switch -> None.
      2. tool_preferences.wicked-loom in config.json.
      3. wicked-loom on PATH.
      4. project-local node_modules/.bin/wicked-loom.
      5. npx --yes wicked-loom (only when allow_npx).
    """
    if _ENV_BIN in os.environ:
        env = os.environ[_ENV_BIN].strip()
        return _argv_for(env) if env else None  # empty == kill-switch

    pref = _read_config_preference(_PACKAGE)
    if pref:
        return _argv_for(pref)

    found = shutil.which(_PACKAGE)
    if found:
        return [found]

    base = Path(project_dir) if project_dir else Path.cwd()
    local = base / "node_modules" / ".bin" / _PACKAGE
    if local.exists():
        return [str(local)]

    if allow_npx and shutil.which("npx"):
        return ["npx", "--yes", _PACKAGE]

    return None


def loom_available(project_dir: Optional[Path] = None) -> bool:
    """True iff a concrete loom install resolves (not the npx last-resort).
    The signal setup + bootstrap use to decide whether the peer is installed."""
    return resolve_loom(allow_npx=False, project_dir=project_dir) is not None


def _default_run(prefix: List[str], args: List[str], timeout: int) -> Dict[str, Any]:
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False
            prefix + args, capture_output=True, text=True, timeout=timeout,
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr, "error": None}
    except FileNotFoundError:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": "loom executable not found"}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": f"loom call exceeded {timeout}s"}


Runner = Callable[..., Dict[str, Any]]


def run_json(args: List[str], *, timeout: int = _DEFAULT_TIMEOUT,
             project_dir: Optional[Path] = None,
             _run: Runner = _default_run) -> Dict[str, Any]:
    """Run ``loom <args>``; return {exit_code, json, stdout, stderr, error}.

    Never raises (R4). json is the parsed stdout or None (unresolvable,
    not-found, timeout, or non-JSON output).
    """
    prefix = resolve_loom(project_dir=project_dir)
    if prefix is None:
        return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                "error": "wicked-loom not resolvable"}
    run = _run(prefix, args, timeout)
    if run["error"] is not None:
        return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                "error": run["error"]}
    try:
        parsed = json.loads(run["stdout"]) if (run["stdout"] or "").strip() else {}
    except json.JSONDecodeError:
        return {"exit_code": run["exit_code"], "json": None,
                "stdout": run["stdout"], "stderr": run["stderr"],
                "error": "loom returned non-JSON output"}
    return {"exit_code": run["exit_code"], "json": parsed,
            "stdout": run["stdout"], "stderr": run["stderr"], "error": None}


def cutover_mode() -> str:
    """The WICKED_LOOM_CUTOVER flag, normalized. Unknown -> 'auto'."""
    raw = os.environ.get(_ENV_FLAG, "").strip().lower()
    return raw if raw in _CUTOVER_MODES else "auto"


def use_loom(*, project_dir: Optional[Path] = None) -> bool:
    """Should this call go through loom?

    off  -> never. on -> always (caller must handle an unresolvable loom).
    auto -> only when loom resolves (the transition default: fall back to the
            in-process path otherwise).
    """
    mode = cutover_mode()
    if mode == "off":
        return False
    if mode == "on":
        return True
    return resolve_loom(project_dir=project_dir) is not None


__all__ = ["resolve_loom", "loom_available", "run_json",
           "cutover_mode", "use_loom"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolver.py -v`
Expected: PASS (14 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/_loom.py tests/crew/test_loom_resolver.py
git commit -m "feat(loom-cutover): loom CLI resolver + JSON runner + cutover flag"
```

---

## Task 1: Cut over `resolve` — garden's peer resolution shells to `loom resolve`

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/qe/vault_gate.py` (`resolve_vault`, lines 69–106)
- Test: `~/Projects/wicked-garden/tests/crew/test_loom_resolve_contract.py`

Lowest-risk surface first (spec §7: `resolve` → `gate` → `flow`). `resolve_vault` grows a loom-first head: when `use_loom()` is true, shell `loom resolve vault` and use its `command` array; otherwise (or on any loom error) fall through to the unchanged in-process ladder. The **contract test** asserts the loom path returns the SAME argv the in-process path returns for the same environment.

- [ ] **Step 1: Write the failing contract test**

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


class ResolveCutoverContract(unittest.TestCase):
    """Strangler safety net: the loom-shelled resolve path must return the
    SAME argv the in-process resolve_vault returns for the same inputs."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def test_loom_resolve_matches_in_process_for_npx_case(self):
        # In-process: no env, not on PATH -> npx --yes wicked-vault.
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            in_proc = vg.resolve_vault()
        self.assertEqual(in_proc, ["npx", "--yes", "wicked-vault"])

        # Loom path: force loom on; loom resolve vault returns the SAME argv.
        os.environ["WICKED_LOOM_CUTOVER"] = "on"

        def fake_run(prefix, args, timeout):
            return {"exit_code": 0,
                    "stdout": '{"peer":"vault","command":["npx","--yes","wicked-vault"]}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            via_loom = vg.resolve_vault()
        self.assertEqual(via_loom, in_proc)

    def test_loom_unresolvable_falls_back_to_in_process(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(shutil, "which", side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            via = vg.resolve_vault()
        # auto + loom unresolvable -> in-process path used (fail-soft).
        self.assertEqual(via, ["npx", "--yes", "wicked-vault"])

    def test_loom_killswitch_env_still_honored_through_loom(self):
        # WICKED_VAULT_BIN="" is the vault kill-switch; the loom resolve path
        # must surface the same None (loom resolve returns command=null).
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        os.environ["WICKED_VAULT_BIN"] = ""

        def fake_run(prefix, args, timeout):
            return {"exit_code": 1, "stdout": '{"peer":"vault","command":null}',
                    "stderr": "", "error": None}
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", fake_run):
            self.assertIsNone(vg.resolve_vault())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolve_contract.py -v`
Expected: FAIL — `test_loom_resolve_matches_in_process_for_npx_case` (and the others) fail because `resolve_vault` does not yet consult loom; the `on` path still runs in-process and ignores the mocked loom output.

- [ ] **Step 3: Edit `vault_gate.py` — add the loom-first head to `resolve_vault`**

Add the import near the top of the file (after the existing stdlib imports, before `_CONFIG_PATH`):

```python
# Strangler shim toward wicked-loom (cutover phase). The in-process body below
# STAYS as the fallback; loom is tried first only when the cutover flag allows.
try:
    import _loom  # scripts/ is on sys.path for hook + CLI invocations
except ImportError:  # pragma: no cover — loom shim absent => pure in-process
    _loom = None  # type: ignore
```

Then insert the loom head at the very top of `resolve_vault` (before the existing `if "WICKED_VAULT_BIN" in os.environ:` block at line 86):

```python
    # --- loom cutover head (resolve surface) ---------------------------------
    # Try loom first iff the cutover flag allows AND loom is reachable. Any loom
    # error falls through to the unchanged in-process ladder (fail-soft, §7/§10).
    if _loom is not None and allow_npx and _loom.use_loom(project_dir=project_dir):
        out = _loom.run_json(["resolve", "vault"], project_dir=project_dir)
        if out["error"] is None and isinstance(out.get("json"), dict):
            # loom resolve returns {"peer","command":[...]|null}; null == the
            # vault kill-switch / unresolvable, which we surface as None.
            return out["json"].get("command")  # list[str] or None
        # loom errored -> fall through to in-process (transition fail-soft).
    # -------------------------------------------------------------------------
```

> Implementer note: `allow_npx` guards the loom head because `vault_available()` calls `resolve_vault(allow_npx=False)` to detect a *concrete* install — that probe must stay in-process (loom's `resolve` would report the npx fallback as resolvable and corrupt the "installed" signal). Keeping the loom head behind `allow_npx` preserves `vault_available()`'s exact semantics. If a future loom `resolve --no-npx` lands, revisit; for now this is the faithful boundary.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_resolve_contract.py tests/qe/test_vault_gate.py -v`
Expected: PASS — the 3 new contract tests AND the existing `test_vault_gate.py` suite (the in-process path is untouched when the flag is `off`/`auto`-unresolvable, which is the default in CI).

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/qe/vault_gate.py tests/crew/test_loom_resolve_contract.py
git commit -m "feat(loom-cutover): resolve_vault shells to loom resolve, fail-soft to in-process"
```

---

## Task 2: Cut over `gate` — garden's vault gate shells to `loom gate`

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/qe/vault_gate.py` (`cross_check`, lines 170–213)
- Test: `~/Projects/wicked-garden/tests/qe/test_loom_gate_contract.py`

Second surface (spec §7). `cross_check` grows a loom-first head: when `use_loom()` is true, shell `loom gate <phase> --scope <scope> [--with-attestations] [--verifier-spec ...]` and map its `{"gate": <verdict>}` onto `cross_check`'s existing return shape; otherwise fall through to the unchanged in-process `_run`+parse. **`gate_satisfied` is unchanged** — it calls `cross_check`, so it transparently inherits the loom path while keeping its fail-closed posture (loom gate also fails closed; if loom is unreachable in `auto`, the in-process gate runs and itself fails closed — never a vacuous pass, I2). The contract test asserts: identical `overall` for PASS and REJECT, and identical fail-closed verdict when the vault is unresolvable on both paths.

- [ ] **Step 1: Write the failing contract test**

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


class GateCutoverContract(unittest.TestCase):
    """Strangler safety net: the loom-shelled gate verdict must match the
    in-process cross_check verdict (same overall + satisfied) for PASS,
    REJECT, and the fail-closed-when-vault-absent case."""

    def setUp(self):
        for v in ("WICKED_VAULT_BIN", "WICKED_LOOM_BIN", "WICKED_LOOM_CUTOVER"):
            os.environ.pop(v, None)

    def _loom_gate_runner(self, overall):
        def fake_run(prefix, args, timeout):
            import json
            verdict = {"satisfied": overall == "PASS", "overall": overall,
                       "gate": "vault-cross-check"}
            return {"exit_code": 0 if overall == "PASS" else 1,
                    "stdout": json.dumps({"gate": verdict}), "stderr": "", "error": None}
        return fake_run

    def test_loom_pass_matches_in_process_pass(self):
        # In-process PASS (stub the vault subprocess).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        with patch.object(vg, "resolve_vault", return_value=["wicked-vault"]), \
             patch.object(vg, "_run", return_value={"exit_code": 0, "error": None,
                          "stdout": '{"overall":"PASS"}', "stderr": ""}):
            in_proc = vg.cross_check("build-1", "test", project_dir=_PROJECT)

        # Loom PASS.
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("PASS")):
            via_loom = vg.cross_check("build-1", "test", project_dir=_PROJECT)

        self.assertEqual(via_loom["overall"], in_proc["overall"])
        self.assertTrue(via_loom["available"])

    def test_loom_reject_matches_in_process_reject(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
        with patch.object(_loom, "resolve_loom", return_value=["wicked-loom"]), \
             patch.object(_loom, "_default_run", self._loom_gate_runner("REJECT")):
            via_loom = vg.cross_check("build-1", "test", project_dir=_PROJECT)
        self.assertEqual(via_loom["overall"], "REJECT")

    def test_gate_fails_closed_when_loom_errors_and_vault_absent(self):
        # auto + loom unresolvable -> in-process gate runs; vault also absent
        # -> fail closed. The loom error never invents a PASS (I2).
        os.environ["WICKED_LOOM_CUTOVER"] = "auto"
        with patch.object(_loom, "resolve_loom", return_value=None), \
             patch.object(vg, "resolve_vault", return_value=None):
            verdict = vg.gate_satisfied(_PROJECT, "build-1", "test")
        self.assertFalse(verdict["satisfied"])
        self.assertEqual(verdict["gate"], "unavailable")

    def test_loom_with_attestations_forwarded(self):
        os.environ["WICKED_LOOM_CUTOVER"] = "on"
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

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/qe/test_loom_gate_contract.py -v`
Expected: FAIL — the loom-path tests fail because `cross_check` does not yet consult loom.

- [ ] **Step 3: Edit `vault_gate.py` — add the loom-first head to `cross_check`**

Insert at the top of `cross_check` (immediately after the docstring, before `args = ["cross-check", ...]` at line 188). Reuse the module-level `_loom` import added in Task 1:

```python
    # --- loom cutover head (gate surface) ------------------------------------
    # Try loom first iff the cutover flag allows AND loom is reachable. Maps
    # loom's {"gate": <verdict>} onto cross_check's return shape. Any loom error
    # falls through to the in-process re-derivation (which itself fails closed).
    if _loom is not None and _loom.use_loom(project_dir=project_dir):
        loom_args = ["gate", phase, "--scope", scope]
        if with_attestations:
            loom_args.append("--with-attestations")
        out = _loom.run_json(loom_args, project_dir=project_dir, timeout=timeout)
        if out["error"] is None and isinstance(out.get("json"), dict):
            verdict = out["json"].get("gate") or {}
            gate_kind = verdict.get("gate")
            if gate_kind == "unavailable":
                # loom reached but the vault is unresolvable behind it -> the
                # gate is unavailable; fail closed exactly as in-process (I2).
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
        # loom errored -> fall through to in-process re-derivation (fail-soft).
    # -------------------------------------------------------------------------
```

> Implementer note: the `verifier_spec` forwarding (`--verifier-spec PATH`) is wired when the flow compiler (Task 5) starts attaching `verifier_spec_ref`; `cross_check`'s current garden signature has no `verifier_spec` parameter, so this head forwards only `--scope`/`--phase`/`--with-attestations` — the exact arguments the in-process path builds (lines 188–190). Do NOT add a `verifier_spec` parameter to `cross_check` in this task (out of scope; it belongs with the compiler handoff). The loom gate is fail-soft on a missing verifier spec by construction (I3), so omitting it is safe.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/qe/test_loom_gate_contract.py tests/qe/test_vault_gate.py -v`
Expected: PASS — the 4 new contract tests AND the existing `test_vault_gate.py` (in-process path unchanged when the flag is off/auto-unresolvable).

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/qe/vault_gate.py tests/qe/test_loom_gate_contract.py
git commit -m "feat(loom-cutover): cross_check shells to loom gate, fail-closed preserved"
```

---

## Task 3: Cut over `flow` — garden's phase advance/park mirrors `loom flow`

**Files:**
- Modify: `~/Projects/wicked-garden/scripts/crew/phase_manager.py` (`approve_phase`, lines 307–422; `_is_hard_gate`, 299–304)
- Test: `~/Projects/wicked-garden/tests/crew/test_loom_flow_contract.py`

Highest-risk surface, done last (spec §7). `phase_manager` keeps its DomainStore `ProjectState` authority — the `flow` cutover does NOT replace storage. Instead, `approve_phase` grows a loom **mirror head**: when `use_loom()` is true, it asks loom whether the (archetype, phase) is a hard gate by consulting the loom flow runner's verdict, and the **contract test** asserts loom's park-at-hard-gate decision matches `_HARD_GATE_PHASES` for every archetype. This proves the two phase engines agree on the load-bearing decision (where the human-in-the-loop stop is) before any later plan moves storage onto loom.

The mirror is read-only parity: the in-process hard-gate enforcement (the `ValueError` guard at lines 332–351) is unchanged and remains authoritative during the cutover. Loom is consulted to *cross-check the decision*, not to gate the write.

- [ ] **Step 1: Write the failing contract test**

```python
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _loom  # noqa: E402
import phase_manager as pm  # noqa: E402
import flow_compiler as fc  # noqa: E402 — Task 5; import guarded below

# (archetype, hard-gate phase) pairs the in-process map declares.
_EXPECTED_HARD_GATES = {
    "migrate": "cutover",
    "incident": "mitigate",
    "review": "remediate-or-accept",
    "specify": "validate",
    "decide": "record",
}


class FlowHardGateParityContract(unittest.TestCase):
    """Strangler safety net: loom's park-at-hard-gate decision (derived from
    the compiled flow definition) must match phase_manager._HARD_GATE_PHASES
    for every archetype. The two engines must agree on WHERE the human stops."""

    def test_compiled_flow_hard_phase_matches_in_process_map(self):
        for archetype, hard_phase in _EXPECTED_HARD_GATES.items():
            flow_def = fc.compile_flow(archetype, flow_id=f"{archetype}-x")
            hard_phases = [p["name"] for p in flow_def["phases"]
                           if isinstance(p.get("hitl"), str) and p["hitl"].startswith("hard:")]
            self.assertIn(hard_phase, hard_phases,
                          f"{archetype}: compiled flow hard phase != in-process map")

    def test_non_hard_archetypes_compile_no_hard_phase(self):
        for archetype in ("triage", "explore", "build", "ship"):
            flow_def = fc.compile_flow(archetype, flow_id=f"{archetype}-x")
            hard_phases = [p["name"] for p in flow_def["phases"]
                           if isinstance(p.get("hitl"), str) and p["hitl"].startswith("hard:")]
            self.assertEqual(hard_phases, [],
                             f"{archetype} should have no hard:* phase")

    def test_approve_phase_in_process_authority_unchanged_when_loom_off(self):
        # With cutover off, approve_phase behaves exactly as before: a hard gate
        # without --confirmed-by raises ValueError (the in-process guard).
        os.environ["WICKED_LOOM_CUTOVER"] = "off"
        st = pm.ProjectState(name="m1", current_phase="cutover",
                             created_at=pm.get_utc_timestamp(),
                             phase_plan=["plan", "expand", "backfill", "cutover", "contract"],
                             extras={"v11_archetype": "migrate"})
        with patch.object(pm, "save_project_state", lambda s: None):
            with self.assertRaises(ValueError):
                pm.approve_phase(st, "cutover")

    def tearDown(self):
        os.environ.pop("WICKED_LOOM_CUTOVER", None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_flow_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'flow_compiler'` (the compiler is Task 5; this test pins the parity contract the flow cutover depends on, so it is written here and goes green after Task 5).

> Sequencing note: this contract test depends on `flow_compiler.compile_flow` (Task 5). It is written in Task 3 because it is the *flow cutover's* safety net, but it will not pass until Task 5 ships the compiler. Run Task 3 Step 3 (the mirror head) now; let Step 4 below confirm the in-process-authority subtest passes immediately, and the two parity subtests pass after Task 5. (Subagent-driven execution: keep this task open until Task 5 closes, then re-run.)

- [ ] **Step 3: Edit `phase_manager.py` — add the loom mirror head to `approve_phase`**

Add the module-level loom import near the existing `_bus_emit_safe` import block (after line 43, before `_bus_emit_safe`):

```python
# Strangler shim toward wicked-loom (cutover phase). Read-only parity mirror:
# the in-process hard-gate enforcement below STAYS authoritative; loom is
# consulted only to cross-check the park-at-hard-gate decision during cutover.
try:
    import _loom  # scripts/ is on sys.path
except ImportError:  # pragma: no cover
    _loom = None  # type: ignore


def _loom_confirms_hard_gate(archetype: str, phase: str) -> "Optional[bool]":
    """Ask loom (via the compiled flow def) whether (archetype, phase) is a
    hard gate. Returns True/False, or None when loom is unavailable/uncertain
    (in which case the in-process _HARD_GATE_PHASES map remains authoritative).
    Best-effort, fail-soft — never raises, never blocks the state write."""
    if _loom is None or not _loom.use_loom():
        return None
    try:
        from flow_compiler import compile_flow
        flow_def = compile_flow(archetype, flow_id=f"{archetype}-parity")
        for p in flow_def.get("phases", []):
            if p.get("name") == phase:
                hitl = p.get("hitl")
                return isinstance(hitl, str) and hitl.startswith("hard:")
        return False
    except Exception:
        return None  # fail-soft: in-process map stays authoritative
```

Then insert the parity cross-check inside `approve_phase`, immediately after `phase = resolve_phase(phase)` (line 329) and before the hard-gate guard (line 332):

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
```

> Implementer note: the mirror is intentionally read-only this phase — it emits a `wicked.loom.parity_mismatch` event when the engines disagree (so production surfaces any drift before the contract phase moves storage onto loom) but never alters the write path. Replacing `phase_manager`'s storage with `loom flow run|status|resume` is the contract phase, not this one. The `Optional` type is already imported at line 35.

- [ ] **Step 4: Run test to verify it passes (in-process subtest now; parity subtests after Task 5)**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_loom_flow_contract.py -v -k in_process`
Expected: PASS — `test_approve_phase_in_process_authority_unchanged_when_loom_off`. The two parity subtests stay red until Task 5 ships `flow_compiler`. Re-run the full file at the end of Task 5.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/crew/phase_manager.py tests/crew/test_loom_flow_contract.py
git commit -m "feat(loom-cutover): approve_phase mirrors loom park-at-hard-gate decision (read-only parity)"
```

---

## Task 4: Add wicked-loom as the 5th required peer

**Files:**
- Modify: `~/Projects/wicked-garden/docs/required-peers.md`
- Modify: `~/Projects/wicked-garden/commands/setup.md`
- Modify: `~/Projects/wicked-garden/hooks/scripts/bootstrap.py` (add `_check_loom_dependency`, peer-detection portion only)
- Modify: `~/Projects/wicked-garden/.claude-plugin/plugin.json` (peer description)

Promote loom from "shimmed tool" to a declared peer — **required at install, resilient at runtime**, the same stance as the other four (§7, docs/required-peers.md). This is doc + setup + bootstrap-probe wiring; no new runtime logic (the runtime resolver is `_loom.resolve_loom` from Task 0).

- [ ] **Step 1: Edit `docs/required-peers.md`** — change "four peers" → "five peers" in the opening paragraph and the "## The four peers" heading (→ "## The five peers"), and add a row to the peer table:

```markdown
| **wicked-loom** | The orchestration runtime garden drives: peer resolution (`loom resolve`), synchronous fail-closed evidence gating (`loom gate`), and the archetype-agnostic flow runtime (`loom flow run/status/resume`). Garden compiles its archetype catalog into a flow definition and shells to loom to run it. | `npx wicked-loom` (npm; pinned `^0.2.0` in `plugin.json`) | `/wicked-garden:setup` verifies at install; resolved at runtime via `WICKED_LOOM_BIN` → config → `PATH` → `node_modules` → `npx wicked-loom`, with `WICKED_LOOM_BIN=""` as the kill-switch |
```

Add to the "## Why each is load-bearing" list:

```markdown
- **wicked-loom runs the work.** Garden classifies and steers; loom resolves
  the peers, re-derives the gates, and advances the phases — parking at every
  hard gate. Without it, garden has the archetype intelligence but no runtime
  to execute it (during cutover, garden falls back to its in-process runtime;
  after the contract phase, loom is the only runtime).
```

> Note: during the cutover phase the wording must stay honest — loom is required at install going forward, but garden still carries the in-process fallback (it is not deleted until the contract phase). The "resilient at runtime" stance already covers the transient-outage case; the bracket above states the cutover-vs-contract distinction explicitly.

- [ ] **Step 2: Edit `commands/setup.md`** — add a new verify step §2.8 after §2.7 (wicked-bus), in the exact shape of §2.5 (wicked-testing):

```markdown
### 2.8 Verify wicked-loom (Required)

```bash
npx wicked-loom doctor 2>/dev/null && npx wicked-loom resolve vault 2>/dev/null || echo "MISSING"
```

- `MISSING` → blocking. wicked-loom is the orchestration runtime garden drives — peer resolution, evidence gating, and flow execution. Show "wicked-loom is not installed. wicked-garden requires it as a peer (sibling to wicked-testing / wicked-vault / wicked-brain / wicked-bus)." **INTERACTIVE mode**: AskUserQuestion header "wicked-loom Required", options "Install now (Required)" = "Run: npm i -g wicked-loom (or use via npx)" / "Exit setup" = "Cancel — I'll install manually and re-run". **PLAIN_TEXT mode**: present numbered options and STOP. If install: run `npm i -g wicked-loom` (or confirm `npx wicked-loom doctor` resolves), then re-probe. On failure, show stderr and exit with manual instructions. If exit: "Install wicked-loom then restart with `/wicked-garden:setup`."
- A JSON line from `doctor` → check the version satisfies `^0.2.0` (the pin from `plugin.json`; 0.2.0 ships the gate + flow surfaces this garden shells to). Then verify the garden can resolve it: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys; sys.path.insert(0,'scripts'); import _loom; print(_loom.resolve_loom())"` should print a non-null argv. Note: `WICKED_LOOM_CUTOVER=off` disables the loom path (the garden runs its in-process fallback) — used for rollback during the cutover transition.
```

- [ ] **Step 3: Edit `bootstrap.py`** — add `_check_loom_dependency` modeled on `_check_vault_dependency` (lines 640–685). Insert after `_check_vault_dependency` (after line 686):

```python
def _check_loom_dependency():
    """Return a briefing note if wicked-loom is not resolvable, else None.

    wicked-loom is a required peer (the 5th, sibling to wicked-testing /
    wicked-vault / wicked-brain / wicked-bus): garden shells to it for peer
    resolution, evidence gating, and flow execution. During the cutover
    transition garden falls back to its in-process runtime when loom is
    absent, so this is a one-line install pointer, never a block.

    Fast + stdlib-only (no subprocess to npx): checks PATH and loose skill
    installs only. Always fails open — never blocks the session.
    """
    try:
        import shutil

        # WICKED_LOOM_BIN explicitly set (even empty kill-switch) or the cutover
        # flag turned off → operator is driving deliberately; don't nag.
        if "WICKED_LOOM_BIN" in os.environ:
            return None
        if os.environ.get("WICKED_LOOM_CUTOVER", "").strip().lower() == "off":
            return None
        if shutil.which("wicked-loom"):
            return None

        skill_roots = [Path.home() / ".claude" / "skills"]
        cfg = os.environ.get("CLAUDE_CONFIG_DIR")
        if cfg:
            skill_roots.append(Path(cfg) / "skills")
        for root in skill_roots:
            try:
                if root.exists():
                    for entry in root.iterdir():
                        if entry.is_dir() and entry.name.startswith("wicked-loom"):
                            return None
            except OSError:
                continue  # fail open

        return (
            "[wicked-loom] REQUIRED but not installed.\n"
            "Install now: npm i -g wicked-loom  (or run via: npx wicked-loom)\n"
            "wicked-loom is the orchestration runtime garden drives for peer "
            "resolution, evidence gating, and flow execution. (Cutover phase: "
            "garden falls back to its in-process runtime when loom is absent.)"
        )
    except Exception:
        return None  # Fail open — never block session start
```

Then wire it into wherever `_check_vault_dependency()`'s note is collected for the SessionStart briefing (find the call site — grep `_check_vault_dependency(` in bootstrap.py — and add a parallel `_check_loom_dependency()` call appending its note to the same briefing list).

- [ ] **Step 4: Edit `.claude-plugin/plugin.json`** — update the description's peer clause. Change "Requires four sibling peers verified at setup — wicked-testing, wicked-vault, wicked-brain, wicked-bus" to "Requires five sibling peers verified at setup — wicked-testing, wicked-vault, wicked-brain, wicked-bus, wicked-loom".

- [ ] **Step 5: Verify the docs + structural checks pass**

Run: `cd ~/Projects/wicked-garden && python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); print('plugin.json valid')" && grep -c "wicked-loom" docs/required-peers.md commands/setup.md`
Expected: `plugin.json valid`; both files report ≥1 `wicked-loom` mention. (If the repo has a `/wg-check` structural validator, run it too: `python3 -m pytest tests/ -k "peer or required" -v` for any peer-count assertion that needs the 5th row.)

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/wicked-garden
git add docs/required-peers.md commands/setup.md hooks/scripts/bootstrap.py .claude-plugin/plugin.json
git commit -m "feat(loom-cutover): wicked-loom is the 5th required peer (docs + setup + bootstrap probe)"
```

---

## Task 5: The archetype → flow-definition compiler (`scripts/crew/flow_compiler.py`)

**Files:**
- Create: `~/Projects/wicked-garden/scripts/crew/flow_compiler.py`
- Test: `~/Projects/wicked-garden/tests/crew/test_flow_compiler.py`

The §3.1 seam — the thin garden layer that makes loom archetype-agnostic. It reads `.claude-plugin/archetypes.json` (`phases`, `produces`, `hitl`) plus the hard-gate phase map and emits the flow-definition JSON `loom flow run` consumes. **Pure + deterministic**: catalog in, JSON out, no I/O beyond reading the catalog.

The translation rule (resolving the §3.1 ↔ catalog mismatch — documented under Ambiguities):
- The catalog's `hitl` is **archetype-level** (one discipline string per archetype, e.g. `hard:cutover-gate`). The flow definition needs **per-phase** `hitl`. Rule: every phase defaults to `hitl: "none"`; the archetype's hard/discrete gate is attached to its **gate phase** — the hard-gate phase from `_HARD_GATE_PHASES` (e.g. `migrate.cutover`), or for non-hard gating archetypes the catalog's last produces-bearing phase. The attached value is the catalog's `hitl` verbatim (so `hard:cutover-gate` lands on the `cutover` phase).
- A phase gets a `gate` iff it is the phase that produces a gated artifact. Rule: the **last phase** carries `gate: "produces:<first-produces-id>"` for gating archetypes (build/migrate/review/incident/ship/specify/decide); gateless archetypes (triage/explore) get `gate: null` on all phases. `peers_required` is `["vault", "testing"]` for archetypes whose produces include `test-report`, else `["vault"]`. `verifier_spec_ref` is `null` (wired later, spec §9 / #887 — out of scope here).

- [ ] **Step 1: Write the failing test**

```python
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import flow_compiler as fc  # noqa: E402


class CompileFlowTests(unittest.TestCase):
    def test_build_flow_shape(self):
        fd = fc.compile_flow("build", flow_id="build-1")
        self.assertEqual(fd["flow_id"], "build-1")
        self.assertEqual([p["name"] for p in fd["phases"]],
                         ["plan", "implement", "test", "review"])
        # build is discrete:review-gate -> no hard:* phase.
        self.assertFalse(any(p["hitl"].startswith("hard:") for p in fd["phases"]))

    def test_migrate_cutover_is_the_hard_phase(self):
        fd = fc.compile_flow("migrate", flow_id="m-1")
        hard = [p for p in fd["phases"] if p["hitl"].startswith("hard:")]
        self.assertEqual(len(hard), 1)
        self.assertEqual(hard[0]["name"], "cutover")
        self.assertEqual(hard[0]["hitl"], "hard:cutover-gate")

    def test_triage_is_fully_gateless(self):
        fd = fc.compile_flow("triage", flow_id="t-1")
        self.assertTrue(all(p["gate"] is None for p in fd["phases"]))
        self.assertTrue(all(p["hitl"] == "none" for p in fd["phases"]))

    def test_gating_archetype_has_a_gate_on_last_phase(self):
        fd = fc.compile_flow("build", flow_id="b-1")
        self.assertIsNotNone(fd["phases"][-1]["gate"])
        self.assertTrue(fd["phases"][-1]["gate"].startswith("produces:"))

    def test_peers_required_includes_testing_when_test_report_produced(self):
        self.assertIn("testing", fc.compile_flow("build", flow_id="b-1")["peers_required"])
        self.assertNotIn("testing", fc.compile_flow("decide", flow_id="d-1")["peers_required"])

    def test_verifier_spec_ref_is_null(self):
        self.assertIsNone(fc.compile_flow("build", flow_id="b-1")["verifier_spec_ref"])

    def test_unknown_archetype_raises(self):
        with self.assertRaises(ValueError):
            fc.compile_flow("frobnicate", flow_id="x-1")

    def test_unsafe_flow_id_raises(self):
        with self.assertRaises(ValueError):
            fc.compile_flow("build", flow_id="../etc/passwd")

    def test_output_is_json_serializable(self):
        import json
        json.dumps(fc.compile_flow("incident", flow_id="i-1"))  # must not raise


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_flow_compiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'flow_compiler'`

- [ ] **Step 3: Write `scripts/crew/flow_compiler.py`**

```python
#!/usr/bin/env python3
"""flow_compiler.py — compile a garden archetype into a loom flow definition.

The §3.1 seam: garden owns the archetype catalog; loom is archetype-agnostic
and runs a generic flow definition. This module is the thin handoff contract —
it reads .claude-plugin/archetypes.json (phases, produces, hitl) plus the
hard-gate phase map and emits the flow-definition JSON `loom flow run` consumes.

Pure + deterministic: catalog in, dict out. The only I/O is reading the catalog.

Flow-definition shape (consumed verbatim by wicked-loom `flow run`):
  {
    "flow_id": str,
    "phases": [{ "name", "gate": "produces:<id>"|null, "hitl": str, "produces": [...] }],
    "peers_required": [str],
    "verifier_spec_ref": str|null,
  }

Translation rules (see the cutover plan's Ambiguities section):
  - The catalog's `hitl` is archetype-level; the flow def needs it per-phase.
    Every phase defaults to "none"; the archetype's gate discipline is attached
    to its gate phase — the hard-gate phase from _HARD_GATE_PHASES when present,
    else the last phase — verbatim (so "hard:cutover-gate" lands on "cutover").
  - The last phase of a GATING archetype carries gate="produces:<first-produces>";
    gateless archetypes (triage/explore) carry gate=null on every phase.
  - peers_required = ["vault","testing"] iff produces includes "test-report",
    else ["vault"]. verifier_spec_ref is null (wired later, spec §9 / #887).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# scripts/crew/ is on sys.path; import the authoritative hard-gate map so the
# compiler and phase_manager agree by construction (the parity contract).
from phase_manager import _HARD_GATE_PHASES  # noqa: E402

_FLOW_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Archetypes whose `hitl` is "continuous"/"none" do not produce a re-derivable
# gated artifact -> the flow is gateless (no per-phase produces gate).
_GATELESS_HITL = ("none", "continuous")


def _catalog_path() -> Path:
    """Resolve .claude-plugin/archetypes.json relative to the repo root."""
    root = Path(os.environ["CLAUDE_PLUGIN_ROOT"]) if os.environ.get("CLAUDE_PLUGIN_ROOT") \
        else Path(__file__).resolve().parents[2]
    return root / ".claude-plugin" / "archetypes.json"


def _load_catalog() -> Dict[str, Any]:
    return json.loads(_catalog_path().read_text(encoding="utf-8")).get("archetypes", {})


def _hard_phase_for(archetype: str) -> Optional[str]:
    """The single hard-gate phase for an archetype, or None."""
    pair = _HARD_GATE_PHASES.get(archetype, ())
    return pair[0] if pair else None


def compile_flow(archetype: str, *, flow_id: str,
                 catalog: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compile one archetype into a loom flow definition (a JSON-able dict)."""
    if not isinstance(flow_id, str) or not _FLOW_ID_RE.match(flow_id):
        raise ValueError(f"unsafe flow_id: {flow_id!r} (kebab/snake/alnum, max 64)")

    cat = catalog if catalog is not None else _load_catalog()
    arch = cat.get(archetype)
    if not arch:
        raise ValueError(f"unknown archetype: {archetype!r} (known: {sorted(cat)})")

    phase_names: List[str] = list(arch.get("phases", []))
    produces: List[str] = list(arch.get("produces", []))
    hitl: str = arch.get("hitl", "none")
    gateless = hitl in _GATELESS_HITL or not phase_names

    hard_phase = _hard_phase_for(archetype)
    # The gate phase: the hard-gate phase if declared, else the last phase.
    gate_phase = hard_phase if hard_phase in phase_names else (
        phase_names[-1] if phase_names else None)

    first_produces = produces[0] if produces else None

    phases: List[Dict[str, Any]] = []
    for name in phase_names:
        is_gate_phase = (name == gate_phase) and not gateless
        phases.append({
            "name": name,
            "gate": f"produces:{first_produces}" if (is_gate_phase and first_produces) else None,
            "hitl": hitl if (name == gate_phase and not gateless) else "none",
            "produces": list(produces) if is_gate_phase else [],
        })

    peers = ["vault", "testing"] if "test-report" in produces else ["vault"]
    return {
        "flow_id": flow_id,
        "phases": phases,
        "peers_required": peers,
        "verifier_spec_ref": None,
    }


__all__ = ["compile_flow"]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compile an archetype to a loom flow definition.")
    parser.add_argument("archetype")
    parser.add_argument("--flow-id", required=True)
    a = parser.parse_args()
    print(json.dumps(compile_flow(a.archetype, flow_id=a.flow_id), indent=2))
```

> Implementer note: add `import os` to the imports (used by `_catalog_path`). The `from phase_manager import _HARD_GATE_PHASES` import is the deliberate single source of truth — the compiler and the phase manager must agree on the hard-gate phase set by construction, which is exactly what Task 3's parity contract test asserts.

- [ ] **Step 4: Run test to verify it passes (compiler + the deferred Task 3 parity subtests)**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/crew/test_flow_compiler.py tests/crew/test_loom_flow_contract.py -v`
Expected: PASS — 9 compiler tests AND now all of `test_loom_flow_contract.py` (the two parity subtests deferred from Task 3 go green because `flow_compiler` exists).

- [ ] **Step 5: Smoke the compiler CLI**

Run: `cd ~/Projects/wicked-garden && python3 scripts/crew/flow_compiler.py migrate --flow-id migrate-smoke`
Expected: a JSON flow definition with 5 phases; the `cutover` phase has `"hitl": "hard:cutover-gate"` and the last phase carries a `produces:shape-change` gate.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/wicked-garden
git add scripts/crew/flow_compiler.py tests/crew/test_flow_compiler.py
git commit -m "feat(loom-cutover): archetype->flow-definition compiler (the §3.1 seam)"
```

---

## Task 6: Full-suite green + end-to-end smoke + handoff note

**Files:** none (verification only).

- [ ] **Step 1: Run the full garden suite**

Run: `cd ~/Projects/wicked-garden && python3 -m pytest tests/ -q`
Expected: PASS — no regressions. The cutover defaults to `auto`, and in CI loom is unresolvable, so every existing test exercises the unchanged in-process path. New tests: 14 (resolver) + 3 (resolve contract) + 4 (gate contract) + 3 (flow contract) + 9 (compiler) = **33 new tests**, all green.

- [ ] **Step 2: End-to-end smoke with loom forced on (requires a published `npx wicked-loom` ≥0.2.0)**

Run:
```bash
cd ~/Projects/wicked-garden
WICKED_LOOM_CUTOVER=on sh scripts/_python.sh -c "import sys; sys.path.insert(0,'scripts'); sys.path.insert(0,'scripts/qe'); import vault_gate as vg; print(vg.resolve_vault())"
```
Expected: a non-null argv printed by the **loom** path (proving the resolve cutover reaches the real CLI). If `npx wicked-loom` is not yet published, this smoke is SKIPPED — note it in the handoff and rely on the injected-runner contract tests (Step 1), which prove parity without the network.

- [ ] **Step 3: Confirm rollback works**

Run: `cd ~/Projects/wicked-garden && WICKED_LOOM_CUTOVER=off python3 -m pytest tests/qe/test_vault_gate.py tests/crew/test_loom_flow_contract.py -q`
Expected: PASS — with the flag off, every surface runs the in-process path; the cutover is fully reversible by a single env var (no code revert needed).

- [ ] **Step 4: Report (no autonomous push)**

Report to the operator: the three surfaces (`resolve`/`gate`/`flow`) are cut over behind contract tests + the `WICKED_LOOM_CUTOVER` flag; loom is the declared 5th peer; the flow compiler exists. The in-process code is intact behind the shim (rollback = `WICKED_LOOM_CUTOVER=off`). The CONTRACT phase (deleting the in-process runtime) is the next plan — run it only after this cutover is proven in production. Do NOT run `npm publish`, `/wg-release`, or delete any in-process code in this plan.

---

## Self-Review

**1. Spec coverage** — checked against §6 (extraction inventory: which files cut over) and §7 step 2 (the cutover):

| Spec item (§6 / §7) | Where realized | Status |
|---|---|---|
| §7 cutover order `resolve` → `gate` → `flow`, one surface at a time | Tasks 1 → 2 → 3, in that order | ✓ |
| §6 `_integration_resolver.py` / `_capability_resolver.py` / `_capability_registry.py` → loom (compose/resolution) | The **resolution** they back is cut over via Task 1 (`resolve_vault` → `loom resolve`) + the `_loom.resolve_loom` ladder (Task 0). These files are NOT deleted (contract phase); the runtime *peer resolution path* is what cuts over. | ✓ (cutover, not deletion) |
| §6 `scripts/qe/vault_gate.py` → loom (conduct/gate) | Task 2 — `cross_check` shells to `loom gate`; `gate_satisfied` inherits it unchanged | ✓ |
| §6 `scripts/crew/phase_manager.py` → loom (conduct/state) | Task 3 — `approve_phase` mirrors `loom flow` park-at-hard-gate (read-only parity; storage move is the contract phase) | ✓ (parity mirror, not storage replacement — deliberate, stated) |
| §6 `bootstrap.py` PARTIAL — peer detect portion → loom compose | Task 4 — `_check_loom_dependency` probe added; the existing detect functions STAY (PARTIAL boundary confirmed empirically in contract phase per §6) | ✓ |
| §7 add wicked-loom as the 5th required peer (docs/required-peers.md + setup) | Task 4 — required-peers.md row + setup.md §2.8 + plugin.json + bootstrap probe | ✓ |
| §7 introduce the archetype → flow-definition compiler (§3.1 seam) | Task 5 — `flow_compiler.compile_flow` reads the catalog + hard-gate map, emits the §3.1 JSON | ✓ |
| §7 / §10 each cutover fail-soft during transition (loom unresolvable → fall back / degrade, never break a session) | Every cutover head guards on `_loom.use_loom()` and falls through to the unchanged in-process body; default flag `auto` | ✓ |
| §10 / I2 gates still fail-closed | Task 2 — loom `gate: "unavailable"` maps to `available: False`; loom error in `auto` falls to in-process gate which itself fails closed; `test_gate_fails_closed_when_loom_errors_and_vault_absent` | ✓ |
| **House requirement: contract test per cutover (strangler safety net, identical results)** | Task 1 `test_loom_resolve_matches_in_process_for_npx_case`; Task 2 `test_loom_pass_matches_in_process_pass` / `_reject_matches_`; Task 3 `test_compiled_flow_hard_phase_matches_in_process_map` | ✓ |
| §11 success #3 no regression: gate behavior identical pre/post | Contract tests + in-process path untouched (flag default leaves it active in CI) | ✓ |
| §11 success #6 loom is archetype-agnostic | Task 5 emits a generic flow def; loom branches only on `gate`/`hitl` (Plan B I6) — garden never hands loom an archetype name | ✓ |

**Explicitly out of scope (stated up front, intentional gaps):** the CONTRACT phase (deleting the `→ loom` rows in §6 — a later plan); the headless daemon (D3, §9). These are NOT covered here by design — the cutover leaves the in-process code in place behind the shim for trivial rollback. No unintended gap.

**2. Placeholder scan** — No `TBD`/`TODO`/"add error handling"/"similar to Task N". Every code step shows complete, runnable code; every run step shows the exact `python3 -m pytest …` command + expected pass/fail. The four implementer notes (Task 1 `allow_npx` boundary, Task 2 `verifier_spec` deferral, Task 3 read-only-parity rationale, Task 5 `import os` + single-source-of-truth import) are concrete clarifications, not deferred work. The Task 3↔5 sequencing dependency is called out explicitly (the parity subtests go green after Task 5). ✓

**3. Type consistency** —
- `_loom.resolve_loom() -> list[str] | None` is consumed identically by `vault_gate.resolve_vault`'s loom head (returns the `command` array) and `_loom.use_loom`. ✓
- `_loom.run_json(args, *, timeout, project_dir, _run) -> {exit_code, json, stdout, stderr, error}` — every caller (resolve head, gate head) reads `out["error"]` then `out["json"]`. ✓
- `cross_check`'s return shape `{available, overall, exit_code, claims, mode, contract_version, detail, raw}` is produced identically by the in-process body (lines 204–213) and the loom head's mapping; `gate_satisfied` reads `available` + `overall` from both. ✓
- `compile_flow(archetype, *, flow_id, catalog=None) -> dict` with phase dicts `{name, gate, hitl, produces}` — consumed by Task 3's parity test (`p["name"]`, `p["hitl"]`) and matches Plan B's flow-def field semantics (`gate`: `null`|`"produces:<id>"`; `hitl`: `"hard:*"`|else) exactly. ✓
- `_HARD_GATE_PHASES` is imported by `flow_compiler` from `phase_manager` (single source of truth) and asserted-against in Task 3's contract test — the compiler and the phase manager agree by construction. ✓
- `cutover_mode() -> str ∈ {auto,on,off}` and `use_loom() -> bool` consistent across `_loom`, the two gate/resolve heads, and the phase-manager mirror. ✓

**One self-review fix applied inline:** Task 3's contract test depends on Task 5's `flow_compiler`; rather than reorder (which would put the highest-risk surface's safety net after its shim), the plan keeps the spec's `resolve→gate→flow` order and explicitly flags that two of Task 3's subtests go green only after Task 5, with the in-process-authority subtest passing immediately. This keeps the cutover ordering faithful to §7 while being honest about the cross-task test dependency.

---

## Ambiguities resolved (and how)

1. **How does garden invoke the loom CLI cross-platform?** Garden already uses `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"` for Python and `npx <peer>` for peers. Resolution: `scripts/_loom.py` mirrors `vault_gate.resolve_vault`'s ladder verbatim — `WICKED_LOOM_BIN` (empty = kill-switch) → `tool_preferences.wicked-loom` in `config.json` → `wicked-loom` on `PATH` → `node_modules/.bin/wicked-loom` → `npx --yes wicked-loom`. A `.mjs`/`.js` override is invoked via `node` (same `_argv_for` rule). Argv lists, `shutil.which`, no shell — cross-platform by construction.

2. **The loom CLI surface targeted.** The shipped loom repo at `~/Projects/wicked-loom` is at **0.1.0 (compose only)** — it ships `resolve`/`doctor`/`compose`. The `gate` and `flow` surfaces are Plan B (conduct), landing as **0.2.0**. Resolution: Task 1 (`resolve`) works against 0.1.0; Tasks 2–3 (`gate`/`flow`) require 0.2.0. The plan pins `^0.2.0` and the end-to-end smoke (Task 6 Step 2) is SKIPPED-with-note if 0.2.0 is not yet published — the injected-runner contract tests prove parity without it. Execution Handoff states conduct must be published first.

3. **§3.1 flow-def `hitl` is per-phase, but the catalog's `hitl` is archetype-level.** The catalog gives one `hitl` string per archetype (e.g. `migrate` → `hard:cutover-gate`) and names hard-gate phases only in `phase_manager._HARD_GATE_PHASES`. Resolution (the compiler's translation rule): every phase defaults to `hitl: "none"`; the archetype's discipline is attached to its gate phase — the hard-gate phase from `_HARD_GATE_PHASES` when present, else the last phase — verbatim. The compiler imports `_HARD_GATE_PHASES` from `phase_manager` so the two engines agree by construction (asserted by Task 3's parity contract).

4. **Which phase carries the `gate`?** The catalog lists `produces` at the archetype level, not per phase. Resolution: the gate phase (above) carries `gate: "produces:<first-produces-id>"`; gateless archetypes (`hitl` ∈ {none, continuous}: triage, explore) get `gate: null` everywhere. This matches Plan B's flow-def semantics (`null` → advance freely; `produces:<id>` → re-derive that contract).

5. **Does the `flow` cutover replace `phase_manager`'s storage?** No — that would be a high-risk storage migration, and §7 contracts (deletes) are the *next* phase. Resolution: the `flow` cutover is a **read-only parity mirror** — `approve_phase` cross-checks loom's park-at-hard-gate decision against `_HARD_GATE_PHASES` and emits `wicked.loom.parity_mismatch` on disagreement, but the in-process guard stays authoritative. This surfaces drift in production before the contract phase moves storage onto `loom flow`.

6. **How is the gate fail-closed posture preserved across the shim?** Both paths fail closed. The loom `gate` returns `gate: "unavailable"` when the vault is unresolvable behind it → mapped to `available: False` → `gate_satisfied` returns the unavailable verdict. If loom *itself* is unreachable in `auto` mode, the head falls through to the in-process `cross_check`, which fails closed on a missing vault exactly as today. A loom error never invents a PASS (I2), proven by `test_gate_fails_closed_when_loom_errors_and_vault_absent`.

7. **`vault_available()` must not be corrupted by loom's npx fallback.** `vault_available()` calls `resolve_vault(allow_npx=False)` to detect a *concrete* install. Loom's `resolve` would report the npx fallback as resolvable. Resolution: the loom head in `resolve_vault` is guarded by `allow_npx` — the concrete-install probe stays in-process, preserving the exact "installed" signal setup and bootstrap rely on.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-08-wicked-loom-cutover.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`. Note the Task 3 ↔ Task 5 dependency: Task 3's two parity subtests go green only after Task 5 ships the compiler — keep Task 3 open and re-run its full file at the end of Task 5.
2. **Inline Execution** — execute in this session with checkpoints. REQUIRED SUB-SKILL: `superpowers:executing-plans`.

Notes for the executor:
- Execution happens in **wicked-garden** (`~/Projects/wicked-garden`), editing existing files. The in-process runtime code is **left in place behind the shim** — do NOT delete it; that is the contract phase.
- **Prerequisite for Tasks 2–3:** `wicked-loom@0.2.0` (the conduct surface — `gate`, `flow`) must be published and reachable via `npx wicked-loom`. Plan B (`docs/plans/2026-06-08-wicked-loom-conduct.md`) is its deliverable. Task 1 (`resolve`) works against the already-shipped 0.1.0. The contract tests are hermetic (loom subprocess injected) and prove parity without a published loom; only the Task 6 end-to-end smoke needs the real CLI.
- Garden imports nothing from loom's Python — it shells `npx wicked-loom` via `scripts/_loom.py`. Loom stays a sibling primitive.
- Rollback during transition is a single env var: `WICKED_LOOM_CUTOVER=off` runs every surface in-process. No code revert needed.
- The CONTRACT phase (deleting the `→ loom` rows in spec §6, re-measuring footprint, absorbing #843) is the **next** plan — run it only after this cutover is proven in production.

**Which approach?**
