"""gate.py — the synchronous, fail-closed produces gate (vault re-derivation).

Absorbed from wicked-loom (Phase B — ECOSYSTEM-RATIONALIZATION.md §5a).

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
