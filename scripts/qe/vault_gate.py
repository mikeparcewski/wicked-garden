#!/usr/bin/env python3
"""vault_gate.py — the garden's produces-gate, backed by wicked-vault.

This is the load-bearing replacement for ``evidence_tracker``'s
*satisfied-when-claimed* model. The tracker records what an archetype
*claims* to have produced and never re-derives it; that lets a build's
review gate pass on a self-asserted "tests pass". ``wicked-vault``
instead re-derives — it recomputes the envelope hash and re-runs the
pure verifier every time, never trusting a cached status — and answers
``cross-check`` with a mechanical PASS / REJECT / ERROR.

So the gate becomes: *is the claim actually backed by evidence that
clears its declared contract?* — not *did someone say it was done?*

**Required peer, fail-closed by default.** wicked-vault is a required
sibling (like wicked-bus / wicked-brain / wicked-testing). When it is
genuinely unresolvable, ``gate_satisfied`` (``require=True`` default)
**fails closed** — it never self-asserts a PASS. ``require=False`` is an
explicit opt-out to the doctrine-light ``evidence_tracker`` claim-only
path for throwaway/low-rigor work.

Resolution order for the vault CLI (see ``resolve_vault``):
    1. ``WICKED_VAULT_BIN`` env var (explicit override; a ``.mjs``/``.js``
       path is invoked via ``node``, anything else is run directly).
       **Set-but-empty is a kill-switch** → unresolvable (forces
       fail-closed / opt-out; used for offline dev, see CONTRIBUTING.md).
    2. ``tool_preferences.wicked-vault`` in
       ``~/.something-wicked/wicked-garden/config.json``.
    3. A ``wicked-vault`` executable on ``PATH``.
    4. A project-local ``node_modules/.bin/wicked-vault``.
    5. ``npx --yes wicked-vault`` — the portable fallback. The vault is
       commonly run via npx (``npx wicked-vault-install`` does not place a
       global binary), so this tier is what lets the required peer resolve
       out of the box; it is *not* counted as a concrete install
       (``vault_available`` excludes it). ``--yes`` fetches once, then caches.

Stdlib-only. Cross-platform (argv lists, ``shutil.which``, no shell).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404 — argv lists only, shell=False
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
_DEFAULT_TIMEOUT = 120

# Strangler shim toward wicked-loom (cutover phase). The in-process body below
# STAYS as the fallback; loom is tried first only when the cutover flag allows.
try:
    import _loom  # scripts/ is on sys.path for hook + CLI invocations
except ImportError:  # pragma: no cover — loom shim absent => pure in-process
    _loom = None  # type: ignore


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _argv_for(target: str) -> List[str]:
    """Turn a resolved vault location into an argv prefix.

    A ``.mjs``/``.js`` file is a script → invoke via ``node``. Anything
    else (an executable name or a shim) is run directly.
    """
    if target.endswith((".mjs", ".js")):
        return ["node", target]
    return [target]


def resolve_vault(*, allow_npx: bool = True,
                  project_dir: Optional[Path] = None) -> Optional[List[str]]:
    """Return the argv prefix that invokes wicked-vault, or None.

    Resolution tiers (first hit wins):
      1. ``WICKED_VAULT_BIN`` env. Set-but-empty is a deliberate
         **kill-switch** → return None (forces fail-closed / opt-out).
      2. ``tool_preferences.wicked-vault`` in config.json.
      3. ``wicked-vault`` on PATH (a global ``npm i -g``).
      4. a project-local ``node_modules/.bin/wicked-vault`` — resolved
         under ``project_dir`` when given, else the cwd (so a gate run from
         a different cwd still finds the target repo's local install).
      5. ``npx --yes wicked-vault`` — the portable fallback, only when
         ``allow_npx``; not counted as a concrete install (``vault_available``).

    None means no vault is resolvable at all.
    """
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

    if allow_npx and shutil.which("npx"):
        return ["npx", "--yes", "wicked-vault"]

    return None


def vault_available(project_dir: Optional[Path] = None) -> bool:
    """True iff a **concrete** vault install is resolvable (env, config,
    PATH, or node_modules) — not the npx last-resort. This is the signal
    setup and the SessionStart bootstrap use to decide whether the
    required peer is actually installed."""
    return resolve_vault(allow_npx=False, project_dir=project_dir) is not None


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


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------

def _run(
    args: List[str],
    *,
    project_dir: Optional[Path],
    timeout: int,
) -> Dict[str, Any]:
    """Run the vault CLI; return ``{exit_code, stdout, stderr, error}``.

    ``error`` is populated (and exit_code left None) only when the CLI
    could not be executed at all — not found, or timed out.
    """
    prefix = resolve_vault(project_dir=project_dir)
    if prefix is None:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": "wicked-vault not resolvable"}
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False
            prefix + args,
            cwd=str(project_dir) if project_dir else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr, "error": None}
    except FileNotFoundError:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": "vault executable not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": "", "stderr": "",
                "error": f"vault cross-check exceeded {timeout}s"}


def cross_check(
    scope: str,
    phase: str,
    *,
    project_dir: Optional[Path] = None,
    with_attestations: bool = False,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Run ``wicked-vault cross-check`` and return its mechanical verdict.

    Returns a dict with ``available`` (False when no vault is resolvable
    or it could not be run) and, when available, the parsed ``overall``
    (PASS / REJECT / ERROR), ``exit_code``, ``claims``, ``mode``, and
    ``contract_version``.

    Per G5 the vault is fail-closed: no contract declared → ERROR. We
    surface that verbatim; we never invent a PASS.
    """
    args = ["cross-check", "--scope", scope, "--phase", phase]
    if with_attestations:
        args.append("--with-attestations")

    run = _run(args, project_dir=project_dir, timeout=timeout)
    if run["error"] is not None:
        return {"available": False, "overall": "ERROR",
                "error": run["error"], "exit_code": None}

    try:
        parsed = json.loads(run["stdout"]) if run["stdout"].strip() else {}
    except json.JSONDecodeError:
        return {"available": True, "overall": "ERROR", "exit_code": run["exit_code"],
                "error": "vault returned non-JSON output",
                "stderr": run["stderr"][:500]}

    return {
        "available": True,
        "overall": parsed.get("overall", "ERROR"),
        "exit_code": run["exit_code"],
        "claims": parsed.get("claims", []),
        "mode": parsed.get("mode"),
        "contract_version": parsed.get("contract_version"),
        "detail": parsed.get("detail"),
        "raw": parsed,
    }


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def gate_satisfied(
    project_dir: Path,
    scope: str,
    phase: str,
    *,
    with_attestations: bool = False,
    require: bool = True,
) -> Dict[str, Any]:
    """The produces-gate. The vault is a **required** evidence backend
    (installed by ``/wicked-garden:setup``), so the default is to re-derive
    or **fail closed** — never to self-assert a PASS.

    Returns ``{satisfied, re_derived, gate, ...}``. ``re_derived`` is the
    honesty flag: True means the verdict was recomputed from frozen
    evidence; False means either a fail-closed "unavailable" verdict or the
    explicitly opted-out claim-only path.

    - vault resolvable → run cross-check, ``re_derived: true``.
    - vault unresolvable, ``require=True`` (default) → fail closed:
      ``satisfied: false``, ``gate: "unavailable"`` with remediation.
    - vault unresolvable, ``require=False`` → legacy claim-only path
      (opt-out for throwaway/low-rigor work; treat "done" with suspicion).
    """
    if resolve_vault(project_dir=Path(project_dir)) is not None:
        cc = cross_check(scope, phase, project_dir=Path(project_dir),
                         with_attestations=with_attestations)
        if cc.get("available"):
            return {
                "satisfied": cc.get("overall") == "PASS",
                "re_derived": True,
                "gate": "vault-cross-check",
                "overall": cc.get("overall"),
                "claims": cc.get("claims", []),
                "contract_version": cc.get("contract_version"),
                "detail": cc.get("detail"),
                "error": cc.get("error"),
            }
        # Resolver pointed at a vault but it could not be run (offline npx,
        # missing executable). Fail closed — do not invent a PASS.
        if require:
            return {
                "satisfied": False, "re_derived": False, "gate": "unavailable",
                "error": cc.get("error", "vault resolvable but not runnable"),
                "reason": "wicked-vault could not be executed; gate fails closed.",
            }

    if require:
        return {
            "satisfied": False,
            "re_derived": False,
            "gate": "unavailable",
            "reason": (
                "wicked-vault is a required evidence backend but is not "
                "resolvable. Install it (`npm i -g wicked-vault` or "
                "`npx wicked-vault-install`) and re-run /wicked-garden:setup. "
                "Gate fails closed — 'done' cannot be self-asserted."
            ),
        }

    # Explicit opt-out (require=False): the doctrine-light tracker.
    _here = str(Path(__file__).resolve().parent)
    if _here not in sys.path:
        sys.path.insert(0, _here)
    import evidence_tracker as et  # noqa: E402

    return {
        "satisfied": et.produces_satisfied(Path(project_dir)),
        "re_derived": False,
        "gate": "claim-only",
        "reason": (
            "vault opt-out (require=False) — gate is doctrine-light "
            "(satisfied-when-claimed, not re-derived)."
        ),
    }


__all__ = ["resolve_vault", "vault_available", "cross_check", "gate_satisfied"]


# ---------------------------------------------------------------------------
# CLI — so markdown playbooks can call the gate from Bash.
#   exit 0 == satisfied (gate / cross-check both gate on exit code)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="wicked-vault-backed produces gate.")
    sub = parser.add_subparsers(dest="action", required=True)

    res = sub.add_parser("resolve", help="show how the vault CLI resolves")

    cc = sub.add_parser("cross-check", help="run vault cross-check for a phase")
    cc.add_argument("project_dir")
    cc.add_argument("--scope", required=True)
    cc.add_argument("--phase", required=True)
    cc.add_argument("--with-attestations", action="store_true")

    g = sub.add_parser("gate", help="gate verdict (vault required; fail-closed)")
    g.add_argument("project_dir")
    g.add_argument("--scope", required=True)
    g.add_argument("--phase", required=True)
    g.add_argument("--with-attestations", action="store_true")
    g.add_argument("--no-require", action="store_true",
                   help="opt out of the requirement (low-rigor claim-only fallback)")

    a = parser.parse_args()

    if a.action == "resolve":
        prefix = resolve_vault()
        print(json.dumps({
            "resolvable": prefix is not None,
            "installed": vault_available(),  # concrete install (not npx)
            "argv_prefix": prefix,
        }))
        sys.exit(0)

    if a.action == "cross-check":
        out = cross_check(a.scope, a.phase, project_dir=Path(a.project_dir),
                         with_attestations=a.with_attestations)
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("overall") == "PASS" else 1)

    if a.action == "gate":
        out = gate_satisfied(Path(a.project_dir), a.scope, a.phase,
                            with_attestations=a.with_attestations,
                            require=not a.no_require)
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("satisfied") else 1)
