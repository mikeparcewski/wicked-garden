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
