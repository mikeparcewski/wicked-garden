#!/usr/bin/env python3
"""_codegraph.py — resolve + run the codegraph CLI, peer-neutral.

The garden's runtime shim for the adopted static code-graph engine
(``@colbymchenry/codegraph``, MIT). Mirrors ``_loom.py``/``vault_gate.resolve_vault``:
the garden NEVER imports codegraph's TypeScript; it shells the published CLI
exactly as it shells wicked-loom/wicked-vault. See docs/adr/0001-code-relationship-graph-engine.md.

This module owns:
  1. resolve_codegraph() — the resolution ladder: WICKED_CODEGRAPH_BIN env
     (empty = kill-switch) -> config tool_preferences.codegraph -> PATH ->
     node_modules/.bin -> ``npx @colbymchenry/codegraph``.
  2. run_json() — run a codegraph subcommand with --json, return
     {exit_code, json, stdout, stderr, error}. Never raises (R4 — surface as data).
  3. db_path() — the SQLite graph location for a project (<project>/.codegraph/codegraph.db),
     which injected-edge extractors + blast-radius/lineage/patch read directly.

Stdlib-only. Cross-platform (argv lists, shutil.which, no shell).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404 — argv lists only, shell=False
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
_DEFAULT_TIMEOUT = 300
_PACKAGE = "@colbymchenry/codegraph"
_ENV_BIN = "WICKED_CODEGRAPH_BIN"


def _argv_for(target: str) -> List[str]:
    """A .mjs/.js path is a script -> invoke via node; else run directly."""
    if target.endswith((".mjs", ".js")):
        return ["node", target]
    return [target]


def _read_config_preference(key: str) -> Optional[str]:
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


def resolve_codegraph(*, allow_npx: bool = True,
                      project_dir: Optional[Path] = None) -> Optional[List[str]]:
    """Return the argv prefix that invokes codegraph, or None.

    ``WICKED_CODEGRAPH_BIN=""`` (set-but-empty) is the deliberate kill-switch -> None.
    With ``allow_npx=False`` the npx last-resort is skipped (the "is a concrete
    install present?" probe used by setup/bootstrap)."""
    if _ENV_BIN in os.environ:
        env = os.environ[_ENV_BIN].strip()
        return _argv_for(env) if env else None  # empty == kill-switch

    pref = _read_config_preference("codegraph")
    if pref:
        return _argv_for(pref)

    found = shutil.which("codegraph")
    if found:
        return [found]

    base = Path(project_dir) if project_dir else Path.cwd()
    local = base / "node_modules" / ".bin" / "codegraph"
    if local.exists():
        return [str(local)]

    if allow_npx and shutil.which("npx"):
        return ["npx", "-y", _PACKAGE]

    return None


def codegraph_available(project_dir: Optional[Path] = None) -> bool:
    """True iff a CONCRETE codegraph install resolves (not the npx last-resort)."""
    return resolve_codegraph(allow_npx=False, project_dir=project_dir) is not None


def db_path(project_dir: Optional[Path] = None) -> Path:
    base = Path(project_dir) if project_dir else Path.cwd()
    return base / ".codegraph" / "codegraph.db"


def _default_run(prefix: List[str], args: List[str], timeout: int,
                 cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False
            prefix + args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr, "error": None}
    except FileNotFoundError:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": "codegraph executable not found"}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": f"codegraph call exceeded {timeout}s"}


def run_json(args: List[str], *, timeout: int = _DEFAULT_TIMEOUT,
             project_dir: Optional[Path] = None, _run=None) -> Dict[str, Any]:
    """Run ``codegraph <args> --json``; return {exit_code, json, stdout, stderr, error}.
    Never raises (R4). json is parsed stdout or None (unresolvable/non-JSON/timeout).
    The codegraph subprocess runs in project_dir (its graph is per-project)."""
    prefix = resolve_codegraph(project_dir=project_dir)
    if prefix is None:
        return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                "error": "codegraph not resolvable"}
    cwd = str(project_dir) if project_dir is not None else None
    if _run is not None:
        run = _run(prefix, args, timeout)
    else:
        run = _default_run(prefix, args, timeout, cwd=cwd)
    if run["error"] is not None:
        return {"exit_code": None, "json": None, "stdout": "", "stderr": "",
                "error": run["error"]}
    try:
        parsed = json.loads(run["stdout"]) if (run["stdout"] or "").strip() else {}
    except json.JSONDecodeError:
        return {"exit_code": run["exit_code"], "json": None,
                "stdout": run["stdout"], "stderr": run["stderr"],
                "error": "codegraph returned non-JSON output"}
    return {"exit_code": run["exit_code"], "json": parsed,
            "stdout": run["stdout"], "stderr": run["stderr"], "error": None}


__all__ = ["resolve_codegraph", "codegraph_available", "db_path", "run_json"]
