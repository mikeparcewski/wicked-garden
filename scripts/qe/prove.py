#!/usr/bin/env python3
"""prove.py — the one-line re-derivation verb.

The produces-gate is the plugin's most valuable feature for an agent: it stops
"done" from being self-asserted. But using it is a ~5-step ritual (vault init →
author a contract.json → declare-contract → record --run → gate). That friction
is exactly why an agent skips it and just *claims* the work is done — turning
the gate into ceremony that exists but isn't used.

This collapses the ritual into one verb an agent reaches for by reflex:

    prove.py tests-pass --by "pytest -q"
    prove.py build-clean --by "npm run build" --verifier exit_code_eq:0

It re-derives, never asserts: it RUNS <command>, freezes the real exit code as
vault evidence, then gates by re-running the verifier against that frozen
evidence. Exit 0 iff the gate PASSES (re-derived). When the loom/vault backend
is unresolvable it FAILS CLOSED (exit 3, gate: "unavailable") — never a vacuous
pass. Reuses scripts/qe/vault_gate.py (resolve + gate_satisfied) and the vault
CLI; it invents no new gating logic.

Stdlib-only. Cross-platform (argv lists, shell=False).
"""

from __future__ import annotations

import argparse
import json
import subprocess  # noqa: S404 — argv lists only, shell=False
import sys
import tempfile
from pathlib import Path

# Importing the sibling gate module must work whether this runs as a CLI
# (`python3 scripts/qe/prove.py …` → only scripts/qe on sys.path) or imported.
# Add scripts/ for vault_gate's own sibling import (_loom). This is the same
# CLI-import discipline a subdir script that imports a top-level sibling needs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import vault_gate  # scripts/qe sibling
except ImportError:  # pragma: no cover
    vault_gate = None  # type: ignore


_VERIFIERS = {
    # name:arg  ->  vault verifier spec
    "exit_code_eq": lambda arg: {"kind": "exit_code_eq", "params": {"code": int(arg)}},
}


def _parse_verifier(spec: str) -> dict:
    """`exit_code_eq:0` -> {kind, params}. Defaults to exit_code_eq:0."""
    name, _, arg = spec.partition(":")
    builder = _VERIFIERS.get(name)
    if builder is None:
        raise ValueError(f"unsupported verifier '{name}'; known: {sorted(_VERIFIERS)}")
    return builder(arg or "0")


def _vault(prefix: list[str], project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(prefix + list(args), cwd=str(project_dir),
                          capture_output=True, text=True, timeout=300)


def prove(claim: str, command: str, *, verifier: str = "exit_code_eq:0",
          scope: str = "prove", phase: str = "verify",
          project_dir: str = ".", with_attestations: bool = False) -> dict:
    """Re-derive a single claim end to end; return the gate verdict dict.

    ``with_attestations`` forwards to the gate's hard-gate requirement (the
    evaluator must not be the agent that did the work) — use it for
    incident/migrate/review gates."""
    if vault_gate is None:
        return {"satisfied": False, "gate": "unavailable", "re_derived": False,
                "error": "vault_gate import failed"}
    pd = Path(project_dir).resolve()
    prefix = vault_gate.resolve_vault(project_dir=pd)  # loom-resolved vault argv
    if prefix is None:
        return {"satisfied": False, "gate": "unavailable", "re_derived": False,
                "error": ("evidence backend (wicked-loom/wicked-vault) not "
                          "resolvable — fails closed, never a vacuous pass")}
    try:
        verifier_spec = _parse_verifier(verifier)
    except ValueError as e:
        return {"satisfied": False, "gate": "error", "re_derived": False,
                "error": str(e)}

    # init (idempotent — ignore "already initialized"), declare, record --run.
    _vault(prefix, pd, "init")
    claim_spec = {
        "claim_id": claim, "kind": "test-run",
        "verifier": verifier_spec, "required": True,
    }
    if with_attestations:
        # Hard gate (incident/migrate/review): the doer's own evidence cannot
        # satisfy it. Opt the contract into the vault's attestation enforcement
        # (`require_attestation`) so the gate REJECTs as UNATTESTED until an
        # INDEPENDENT evaluator records `wicked-vault attest` (evaluator !=
        # creator). Without this flag the contract is integrity-only and the
        # gate would pass on the doer's evidence alone — a vacuous hard gate.
        claim_spec["require_attestation"] = True
    contract = {"required_evidence": [claim_spec]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write(json.dumps(contract))
        spec_path = fh.name
    try:
        _vault(prefix, pd, "declare-contract", "--scope", scope, "--phase", phase,
               "--spec", spec_path)
        _vault(prefix, pd, "record", "--scope", scope, "--phase", phase,
               "--claim", claim, "--kind", "test-run", "--source", command,
               "--criteria", f"{claim}: `{command}` satisfies {verifier}",
               "--verifier", verifier, "--run")
    finally:
        try:
            Path(spec_path).unlink()
        except OSError:
            pass

    # The verdict is RE-DERIVED by the gate, not taken from the record above.
    return vault_gate.gate_satisfied(pd, scope, phase,
                                     with_attestations=with_attestations)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Prove a claim by re-deriving it (run + gate), not asserting it.")
    p.add_argument("claim", help="claim id, e.g. tests-pass")
    p.add_argument("--by", required=True, metavar="COMMAND",
                   help="the command whose real exit code is the evidence; it "
                        "runs in --project-dir, so prefer absolute paths or a "
                        "command valid from there")
    p.add_argument("--verifier", default="exit_code_eq:0",
                   help="verifier spec (default: exit_code_eq:0)")
    p.add_argument("--scope", default="prove")
    p.add_argument("--phase", default="verify")
    p.add_argument("--project-dir", default=".")
    p.add_argument("--with-attestations", action="store_true",
                   help="hard gate (incident/migrate/review): require an "
                        "INDEPENDENT attestation. The gate stays REJECT "
                        "(UNATTESTED) until someone other than the doer runs "
                        "`wicked-vault attest <artifact> --opinion pass` — the "
                        "doer's own evidence cannot satisfy it")
    a = p.parse_args()
    verdict = prove(a.claim, a.by, verifier=a.verifier, scope=a.scope,
                    phase=a.phase, project_dir=a.project_dir,
                    with_attestations=a.with_attestations)
    print(json.dumps(verdict, indent=2))
    if verdict.get("satisfied"):
        return 0
    # distinguish fail-closed (backend gone) from a real REJECT
    return 3 if verdict.get("gate") == "unavailable" else 1


if __name__ == "__main__":
    sys.exit(main())
