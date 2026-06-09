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

**Loom is authoritative (contract phase).** The re-derivation engine is
now ``wicked-loom``: ``cross_check`` shells ``loom gate`` and ``resolve_vault``
(default ``allow_npx=True``) shells ``loom resolve vault``. The in-process
vault re-derivation + npx resolution ladder were removed once loom became
load-bearing. Resolution splits into two paths (see ``resolve_vault``):
    - ``allow_npx=True`` — loom authoritative; loom-unresolvable/disabled/
      erroring → None (no in-process fallback; the gate then fails closed).
    - ``allow_npx=False`` — the ``vault_available`` concrete-install probe:
      an in-process ladder (``WICKED_VAULT_BIN`` env, with set-but-empty as
      the kill-switch → config → PATH → ``node_modules/.bin``; **no npx, no
      loom** — npx/loom would report the last-resort as resolvable and corrupt
      the "is a concrete vault installed?" signal). Unchanged from pre-contract.

Stdlib-only. Cross-platform (argv lists, ``shutil.which``, no shell).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_PATH = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
_DEFAULT_TIMEOUT = 120

# wicked-loom is the authoritative runtime for the resolve + gate surfaces
# (contract phase: the in-process re-derivation + npx ladder were removed).
# When the loom shim is absent the shimmed surfaces are unavailable and the
# gate fails closed — there is no in-process fallback.
# ``_loom`` is a sibling module in scripts/. When this runs as a CLI
# (`python3 scripts/qe/vault_gate.py …`, incl. via _python.sh) only scripts/qe
# is on sys.path, so add scripts/ — otherwise the import fails, the loom shim
# is None, and EVERY gate silently fails closed ("unavailable") even with loom
# + vault installed. Module-level imports (hooks, conftest) already have
# scripts/ on the path; this makes the CLI path behave the same. phase_manager
# does the same insert. (Regression introduced by the loom cutover, #891.)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import _loom
except ImportError:  # pragma: no cover — loom shim absent => surfaces unavailable
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

    Two distinct callers, two paths (contract phase):

    - ``allow_npx=True`` (default; the run-the-vault path): **loom is
      authoritative.** Garden asks ``wicked-loom resolve vault`` and returns
      its ``command`` array (None when loom reports the vault unresolvable /
      kill-switched). loom unresolvable, disabled (``WICKED_LOOM_CUTOVER=off``),
      or erroring → None. There is no in-process npx ladder here anymore (the
      contract removed it); a missing loom means a missing resolver, and the
      gate downstream fails closed (I2).

    - ``allow_npx=False`` (the ``vault_available`` concrete-install probe):
      the in-process ladder (``WICKED_VAULT_BIN`` env → config → PATH →
      ``node_modules/.bin``; **no npx, no loom**). loom is deliberately NOT
      consulted: it would report the npx last-resort as resolvable and corrupt
      the "is a concrete vault actually installed?" signal. This path is
      unchanged from before the contract. ``WICKED_VAULT_BIN=""`` (set-but-
      empty) is the deliberate kill-switch → None.
    """
    if allow_npx:
        # Run-the-vault path: loom authoritative, no in-process fallback.
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
    claims, mode, contract_version, detail, raw}``.

    **Fail-closed (I2).** When loom is unresolvable, disabled
    (``WICKED_LOOM_CUTOVER=off``), errors, returns non-JSON, or reports the
    vault unavailable behind it, ``available`` is False and ``overall`` is
    ERROR — we never invent a PASS. There is no in-process fallback; a missing
    loom is a missing gate, and a missing gate fails closed.
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
        # loom unresolvable / timed out / non-JSON -> fail closed (I2).
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


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def _sentinel_stamp(project_dir: Path, result: Dict[str, Any],
                    scope: str, phase: str) -> None:
    """Stamp this verdict into the claim-sentinel ledger (fail-open).

    gate_satisfied is the single front door for re-derivation, so stamping here
    means every prove/gate run — from any command, any cwd — leaves the record
    the sentinel's claim-time invariants (ref-watch, TaskCompleted) check against."""
    try:
        from pathlib import Path as _P
        import sys as _sys
        sentinel_dir = _P(__file__).resolve().parents[1] / "sentinel"
        if str(sentinel_dir) not in _sys.path:
            _sys.path.insert(0, str(sentinel_dir))
        from invariants import stamp_verdict  # type: ignore
        stamp_verdict(_P(project_dir),
                      overall=str(result.get("overall", "ERROR")),
                      satisfied=bool(result.get("satisfied")),
                      re_derived=bool(result.get("re_derived")),
                      scope=scope, phase=phase)
    except Exception:  # noqa: BLE001 — the sentinel must never break the gate
        return


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
            result = {
                "satisfied": cc.get("overall") == "PASS",
                "re_derived": True,
                "gate": "vault-cross-check",
                "overall": cc.get("overall"),
                "claims": cc.get("claims", []),
                "contract_version": cc.get("contract_version"),
                "detail": cc.get("detail"),
                "error": cc.get("error"),
            }
            _sentinel_stamp(Path(project_dir), result, scope, phase)
            return result
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
            # Honesty signal: did the loom shim import succeed? If False, the
            # gate fails closed regardless of whether loom/vault are installed
            # (the CLI sys.path bug). Lets callers/tests distinguish "loom shim
            # broken" from "vault genuinely absent".
            "loom_shim_loaded": _loom is not None,
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
