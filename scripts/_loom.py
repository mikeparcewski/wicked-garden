#!/usr/bin/env python3
"""_loom.py — wicked-loom peer-resolution runtime (absorbed, Phase B).

After the wicked-* ecosystem rationalization (ECOSYSTEM-RATIONALIZATION.md
§5a Phase B), wicked-loom's peer-resolution capabilities are absorbed into
wicked-garden as ``scripts/loom/``.  The standalone ``wicked-loom`` npm
package is no longer required — this module dispatches to the internal Python
modules in-process (no subprocess for loom itself).

The external interface is UNCHANGED — all callers (vault_gate.py,
phase_manager.py, bootstrap.py) continue to call resolve_loom(),
run_json(), use_loom(), loom_available() exactly as before.

RETIRED (not callable through this shim):
  loom flow run / status / resume — replaced by wicked-crew.

ABSORBED (available in-process):
  loom resolve <peer>             -> scripts/loom/resolve.py
  loom doctor [--strict]          -> scripts/loom/compose.py
  loom compose install [--peer X] -> scripts/loom/compose.py
  loom gate <produces> [--scope S]-> scripts/loom/gate.py

Resolution notes
----------------
The ``WICKED_LOOM_BIN`` env var is still respected as the highest-priority
override (env override beats internal), so debugging with a custom binary
still works.  ``WICKED_LOOM_CUTOVER=off`` is the kill-switch — it disables
loom entirely (gates fail closed, peer resolution unavailable), identical to
the pre-absorption kill-switch.  The internal path is selected by default
when the ``scripts/loom/`` package is importable (always true in a garden
install); the external subprocess fallback is used only when the internal
package is absent or ``_run`` is injected by tests.

Stdlib-only (plus the absorbed scripts/loom/ package). Cross-platform
(argv lists, shutil.which, no shell).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404 — argv lists only, shell=False
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
_DEFAULT_TIMEOUT = 120
_CUTOVER_MODES = ("auto", "on", "off")
_PACKAGE = "wicked-loom"
_ENV_BIN = "WICKED_LOOM_BIN"
_ENV_FLAG = "WICKED_LOOM_CUTOVER"

# ---------------------------------------------------------------------------
# Internal module import (absorbed loom package)
# ---------------------------------------------------------------------------
# Add scripts/ to sys.path so ``import loom`` finds scripts/loom/ regardless
# of which directory the caller is running from.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    from loom import resolve as _loom_resolve_mod
    from loom import compose as _loom_compose_mod
    from loom import gate as _loom_gate_mod
    from loom import manifest as _loom_manifest_mod
    _HAVE_INTERNAL = True
except ImportError:  # pragma: no cover — only absent if scripts/loom/ is missing
    _HAVE_INTERNAL = False


# ---------------------------------------------------------------------------
# Resolution ladder (for the external CLI fallback)
# ---------------------------------------------------------------------------

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

    After absorption the primary path is the internal Python module
    (``_HAVE_INTERNAL``), not a subprocess.  ``resolve_loom()`` now reflects
    that: it returns a sentinel ``["_internal"]`` when the absorbed package is
    importable, and falls back to the external CLI ladder only when it is not.

    The ``WICKED_LOOM_BIN`` env override still takes highest priority — an
    explicit override or kill-switch beats everything including the internal
    module.  This preserves the debugging escape hatch and the empty-string
    kill-switch semantics.

    Ladder (first hit wins):
      1. WICKED_LOOM_BIN env. Set-but-empty is the kill-switch -> None.
      2. Internal absorbed module (scripts/loom/) -> ["_internal"] sentinel.
      3. tool_preferences.wicked-loom in config.json.
      4. wicked-loom on PATH.
      5. project-local node_modules/.bin/wicked-loom.
      6. npx --yes wicked-loom (only when allow_npx).
    """
    # Step 1: explicit env override / kill-switch (highest priority)
    if _ENV_BIN in os.environ:
        env = os.environ[_ENV_BIN].strip()
        return _argv_for(env) if env else None  # empty == kill-switch

    # Step 2: absorbed internal module (always available in a garden install)
    if _HAVE_INTERNAL:
        return ["_internal"]

    # Steps 3-6: external CLI fallback
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
    """True iff loom is concretely available — internal module or external install.

    After absorption this returns True whenever the internal module is
    importable (i.e., always in a properly installed wicked-garden).  The
    ``allow_npx=False`` semantics from before absorption: the npx last-resort
    is excluded.  The internal module is a concrete install by definition.
    """
    if _HAVE_INTERNAL:
        return True
    # External concrete probe (no npx)
    return resolve_loom(allow_npx=False, project_dir=project_dir) is not None


# ---------------------------------------------------------------------------
# Internal dispatch (in-process, no subprocess for loom itself)
# ---------------------------------------------------------------------------

def _fmt(exit_code: int, payload: dict) -> Dict[str, Any]:
    """Wrap an internal result in the standard run_json return shape."""
    raw = json.dumps(payload)
    return {"exit_code": exit_code, "json": payload, "stdout": raw,
            "stderr": "", "error": None}


def _internal_resolve(args: List[str],
                      project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """``loom resolve <peer>`` — in-process via loom.resolve."""
    if not args:
        payload = {"error": "usage: loom resolve <peer>"}
        return {"exit_code": 2, "json": payload, "stdout": json.dumps(payload),
                "stderr": "", "error": None}
    peer_name = args[0]
    cmd = _loom_resolve_mod.resolve(peer_name)
    payload = {"peer": peer_name, "command": cmd}
    return _fmt(0 if cmd is not None else 1, payload)


def _internal_doctor(args: List[str]) -> Dict[str, Any]:
    """``loom doctor [--strict]`` — in-process via loom.compose."""
    strict = "--strict" in args
    rows = _loom_compose_mod.check_all()
    all_reachable = all(r.get("status") == "ok" for r in rows)
    not_capable = [r.get("peer") for r in rows if not r.get("capability_ok")]
    all_capable = not not_capable
    payload = {
        "peers": rows,
        "all_reachable": all_reachable,
        "all_capable": all_capable,
        "not_capable": not_capable,
        "strict": strict,
    }
    ok = all_reachable and (all_capable if strict else True)
    return _fmt(0 if ok else 1, payload)


def _internal_compose(args: List[str]) -> Dict[str, Any]:
    """``loom compose install [--peer X]`` — in-process via loom.compose."""
    if not args or args[0] != "install":
        payload = {"error": "usage: loom compose install [--peer <name>]"}
        return {"exit_code": 2, "json": payload, "stdout": json.dumps(payload),
                "stderr": "", "error": None}
    target: Optional[str] = None
    if "--peer" in args:
        i = args.index("--peer")
        if i + 1 < len(args):
            target = args[i + 1]
    names = [target] if target else list(_loom_manifest_mod.PEERS)
    results = [_loom_compose_mod.install_peer(n) for n in names]
    payload = {"results": results}
    all_ok = all(r.get("status") == "installed" for r in results)
    return _fmt(0 if all_ok else 1, payload)


def _internal_gate(args: List[str],
                   project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """``loom gate <produces> [--scope S] [--with-attestations]`` — in-process.

    CWD preservation: the external loom subprocess path ran loom in
    ``project_dir``, so vault (spawned by loom) also ran in that directory.
    The internal path skips the loom subprocess, so we must forward
    ``project_dir`` as the vault subprocess's CWD explicitly.  Without this,
    vault runs in the parent process CWD and cannot find the project's
    ``.wicked/`` store — "no contract declared" (the #891 cwd regression,
    re-introduced at the in-process boundary).
    """
    # Replicate cli.py's _positionals / _opt without importing cli (avoid
    # circular dep; the cli module imports from loom.* not from _loom).
    _value_opts = ("--scope", "--verifier-spec")

    def _positionals(a: list) -> list:
        out, i, n = [], 0, len(a)
        while i < n:
            tok = a[i]
            if tok in _value_opts:
                i += 2
                continue
            if tok.startswith("--"):
                i += 1
                continue
            out.append(tok)
            i += 1
        return out

    def _opt(a: list, name: str) -> Optional[str]:
        if name in a:
            idx = a.index(name)
            if idx + 1 < len(a):
                return a[idx + 1]
        return None

    scope = _opt(args, "--scope") or "default"
    verifier_spec = _opt(args, "--verifier-spec")
    positional = _positionals(args)
    produces = positional[0] if positional else None

    if produces is None:
        payload = {"error": "usage: loom gate <produces> [--scope S] "
                            "[--verifier-spec PATH] [--with-attestations]"}
        return {"exit_code": 2, "json": payload, "stdout": json.dumps(payload),
                "stderr": "", "error": None}

    # Build a runner that honours project_dir as the vault subprocess CWD.
    # gate.run_gate shells wicked-vault (still external); only the loom layer
    # moved in-process.  When project_dir is provided we inject a custom runner
    # so vault runs in the project directory — mirroring how the old external
    # loom subprocess ran in project_dir and its own vault call inherited it.
    if project_dir is not None:
        _cwd = str(project_dir)

        def _project_run(cmd: list, timeout: int = 30):  # type: ignore[override]
            from loom.compose import RunResult
            p = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=_cwd,
            )
            return RunResult(returncode=p.returncode,
                             stdout=p.stdout, stderr=p.stderr)

        run_kwarg: Dict[str, Any] = {"run": _project_run}
    else:
        run_kwarg = {}

    verdict = _loom_gate_mod.run_gate(
        produces, scope=scope, verifier_spec=verifier_spec,
        with_attestations="--with-attestations" in args,
        **run_kwarg,
    )
    payload = {"gate": verdict}
    return _fmt(0 if verdict.get("satisfied") else 1, payload)


def _dispatch_internal(args: List[str],
                       project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Dispatch a loom command to the absorbed in-process modules.

    Returns the same {exit_code, json, stdout, stderr, error} shape as the
    external subprocess path so all callers are unchanged.
    """
    if not args:
        payload = {"commands": ["resolve", "doctor", "compose", "gate"]}
        return _fmt(0, payload)
    cmd = args[0]
    rest = args[1:]
    if cmd == "resolve":
        return _internal_resolve(rest, project_dir=project_dir)
    if cmd == "doctor":
        return _internal_doctor(rest)
    if cmd == "compose":
        return _internal_compose(rest)
    if cmd == "gate":
        return _internal_gate(rest, project_dir=project_dir)
    if cmd == "flow":
        payload = {
            "error": "loom flow is retired",
            "detail": (
                "loom flow run/status/resume was the loom conduct surface, "
                "replaced by wicked-crew + wicked-orchestration "
                "(ECOSYSTEM-RATIONALIZATION.md §5a Phase B)."
            ),
        }
        return {"exit_code": 2, "json": payload, "stdout": json.dumps(payload),
                "stderr": "", "error": "loom flow is retired"}
    payload = {"error": f"unknown command: {cmd}",
               "commands": ["resolve", "doctor", "compose", "gate"]}
    return {"exit_code": 2, "json": payload, "stdout": json.dumps(payload),
            "stderr": "", "error": f"unknown loom command: {cmd}"}


# ---------------------------------------------------------------------------
# External subprocess runner (fallback / test injection)
# ---------------------------------------------------------------------------

def _default_run(prefix: List[str], args: List[str], timeout: int,
                 cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False
            prefix + args, capture_output=True, text=True, timeout=timeout,
            cwd=cwd,
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
             _run: Optional[Runner] = None) -> Dict[str, Any]:
    """Run ``loom <args>``; return {exit_code, json, stdout, stderr, error}.

    Never raises (R4). json is the parsed result or None (unresolvable,
    not-found, timeout, non-JSON, or retired command).

    Dispatch order:
      1. WICKED_LOOM_BIN env override (highest priority — beats even internal):
         - Empty string  -> kill-switch; return "not resolvable" immediately.
         - Non-empty str -> use the specified external binary (debugging escape hatch).
      2. Internal absorbed modules (in-process) — when _HAVE_INTERNAL is True
         and no _run override is injected AND no WICKED_LOOM_BIN is set.
         This is the post-absorption default for normal operation.
      3. External subprocess — when _run is injected (tests), when the
         internal package is absent, or when WICKED_LOOM_BIN is explicitly set.

    ``_run`` is the injected subprocess runner (tests pass a fake). When
    None AND _HAVE_INTERNAL (and WICKED_LOOM_BIN is unset), the internal
    path is used (no subprocess for loom). When None AND not _HAVE_INTERNAL,
    resolves _default_run at call time — so monkeypatching
    ``_loom._default_run`` (the documented test seam) takes effect; binding
    it as a default-arg value would freeze it at def-time.
    """
    # Step 1: explicit WICKED_LOOM_BIN env override (beats internal module).
    # Non-empty -> debugging escape hatch: use that binary, skip internal.
    # Empty     -> deliberate kill-switch: no loom at all.
    _env_override = os.environ.get(_ENV_BIN)
    if _env_override is not None:
        if not _env_override.strip():
            return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                    "error": "wicked-loom not resolvable"}
        # Non-empty override: fall through to external subprocess below.
    elif _HAVE_INTERNAL and _run is None:
        # Step 2: internal path — env override unset, internal modules available,
        # no test injection.
        return _dispatch_internal(args, project_dir=project_dir)

    # External subprocess path (env override / test injection / no internal).
    prefix = resolve_loom(project_dir=project_dir)
    if prefix is None or prefix == ["_internal"]:
        # "_internal" sentinel: internal was selected but _run was injected
        # for testing; fall back to "not resolvable" in that edge case so
        # tests that inject _run and expect the external path still work.
        # (Normally _run injection only happens in tests that also mock
        # resolve_loom, so this path is rarely hit in practice.)
        if prefix == ["_internal"] and _run is not None:
            # Test is injecting _run to exercise the subprocess path; honour it.
            pass  # fall through to the _run invocation below with a dummy prefix
        else:
            return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                    "error": "wicked-loom not resolvable"}

    if _run is not None:
        # Test seam: injected runner, use whatever prefix resolve_loom returned
        # (or a mock prefix from patch.object).
        effective_prefix = prefix if prefix and prefix != ["_internal"] else [_PACKAGE]
        run_result = _run(effective_prefix, args, timeout)
    else:
        cwd = str(project_dir) if project_dir is not None else None
        run_result = _default_run(prefix, args, timeout, cwd=cwd)

    if run_result["error"] is not None:
        return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                "error": run_result["error"]}
    try:
        parsed = json.loads(run_result["stdout"]) if (run_result["stdout"] or "").strip() else {}
    except json.JSONDecodeError:
        return {"exit_code": run_result["exit_code"], "json": None,
                "stdout": run_result["stdout"], "stderr": run_result["stderr"],
                "error": "loom returned non-JSON output"}
    return {"exit_code": run_result["exit_code"], "json": parsed,
            "stdout": run_result["stdout"], "stderr": run_result["stderr"],
            "error": None}


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def cutover_mode() -> str:
    """The WICKED_LOOM_CUTOVER flag, normalized. Unknown -> 'auto'.

    After absorption: 'auto' always uses loom (internal module is always
    available).  'off' remains the kill-switch — disables loom entirely and
    causes gates to fail closed.  'on' is unchanged.
    """
    raw = os.environ.get(_ENV_FLAG, "").strip().lower()
    return raw if raw in _CUTOVER_MODES else "auto"


def use_loom(*, project_dir: Optional[Path] = None) -> bool:
    """Should this call go through loom?

    off  -> never (emergency kill-switch; gate fails closed).
    on   -> always.
    auto -> True when internal module is available (always in garden install),
            OR when the external CLI resolves (backward compat for environments
            without the absorbed package).

    After absorption: auto is effectively always True in a garden install
    because _HAVE_INTERNAL is True.  The kill-switch (off) is preserved for
    emergency disable.
    """
    mode = cutover_mode()
    if mode == "off":
        return False
    if mode == "on":
        return True
    # auto: internal (absorbed) takes priority over external CLI check
    if _HAVE_INTERNAL:
        return True
    return resolve_loom(project_dir=project_dir) is not None


__all__ = ["resolve_loom", "loom_available", "run_json",
           "cutover_mode", "use_loom", "_HAVE_INTERNAL"]
