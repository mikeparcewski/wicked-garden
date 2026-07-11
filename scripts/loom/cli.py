"""cli.py — argument dispatch + JSON output for the peer-resolution surface.

Absorbed from wicked-loom (Phase B — ECOSYSTEM-RATIONALIZATION.md §5a).

ACTIVE commands (absorbed into wicked-garden):
  loom resolve <peer>              -> {"peer","command"}            exit 0/1
  loom doctor [--strict]           -> {"peers":[check rows], ...}   exit 0/1
  loom compose install [--peer X]  -> {"results":[install rows]}    exit 0/1
  loom gate <produces> [--scope S] -> {"gate":{...}}                exit 0/1

RETIRED commands (NOT included — replaced by wicked-crew + wicked-orchestration):
  loom flow run    — RETIRED (was: run a flow from a JSON definition)
  loom flow status — RETIRED (was: read persisted flow state)
  loom flow resume — RETIRED (was: resume a parked/running flow)

No business logic lives here — only parsing + formatting.
"""

from __future__ import annotations

import json
import sys
from typing import Optional

from loom import manifest
from loom.compose import check_all, install_peer
from loom.resolve import resolve
from loom.gate import run_gate


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")


def _cmd_resolve(args: list) -> int:
    if not args:
        _emit({"error": "usage: loom resolve <peer>"})
        return 2
    cmd = resolve(args[0])
    _emit({"peer": args[0], "command": cmd})
    return 0 if cmd is not None else 1


def _cmd_doctor(args: list) -> int:
    """Report every peer's reachability AND declared capability.

    Two orthogonal signals live on each row:
      * ``status``        — runtime REACHABILITY (ok/drift/present/missing/error)
      * ``capability_ok`` — declared CAPABILITY readiness (True only for ``wired``)

    Default exit keys on reachability only (``status == "ok"``). ``--strict``
    makes the EXIT additionally assert ``capability_ok`` for every peer.
    """
    strict = "--strict" in args
    rows = check_all()
    all_reachable = all(r.get("status") == "ok" for r in rows)
    not_capable = [r.get("peer") for r in rows if not r.get("capability_ok")]
    all_capable = not not_capable
    _emit({
        "peers": rows,
        "all_reachable": all_reachable,
        "all_capable": all_capable,
        "not_capable": not_capable,
        "strict": strict,
    })
    ok = all_reachable and (all_capable if strict else True)
    return 0 if ok else 1


def _cmd_compose(args: list) -> int:
    if not args or args[0] != "install":
        _emit({"error": "usage: loom compose install [--peer <name>]"})
        return 2
    target = None
    if "--peer" in args:
        i = args.index("--peer")
        if i + 1 < len(args):
            target = args[i + 1]
    names = [target] if target else list(manifest.PEERS)
    results = [install_peer(n) for n in names]
    _emit({"results": results})
    return 0 if all(r.get("status") == "installed" for r in results) else 1


_VALUE_OPTS = ("--scope", "--verifier-spec")


def _positionals(args: list) -> list:
    """Return the positional tokens, skipping flags and value-taking option tokens."""
    out: list = []
    i = 0
    n = len(args)
    while i < n:
        tok = args[i]
        if tok in _VALUE_OPTS:
            i += 2
            continue
        if tok.startswith("--"):
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _opt(args: list, name: str) -> Optional[str]:
    """Return the value following ``--name`` in args, or None."""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def _cmd_gate(args: list) -> int:
    scope = _opt(args, "--scope") or "default"
    verifier_spec = _opt(args, "--verifier-spec")
    positional = _positionals(args)
    produces = positional[0] if positional else None
    if produces is None:
        _emit({"error": "usage: loom gate <produces> [--scope S] "
                        "[--verifier-spec PATH] [--with-attestations]"})
        return 2
    verdict = run_gate(produces, scope=scope, verifier_spec=verifier_spec,
                       with_attestations="--with-attestations" in args)
    _emit({"gate": verdict})
    return 0 if verdict.get("satisfied") else 1


_DISPATCH = {
    "resolve": _cmd_resolve,
    "doctor": _cmd_doctor,
    "compose": _cmd_compose,
    "gate": _cmd_gate,
    # flow subcommands are RETIRED — not included. Use wicked-crew for
    # multi-phase orchestration (see ECOSYSTEM-RATIONALIZATION.md §5a).
}


def main(argv: "list[str] | None" = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _emit({"commands": list(_DISPATCH)})
        return 0
    handler = _DISPATCH.get(argv[0])
    if handler is None:
        if argv[0] == "flow":
            _emit({
                "error": "loom flow is retired",
                "detail": (
                    "loom flow run/status/resume was part of the loom conduct "
                    "surface, replaced by wicked-crew + wicked-orchestration "
                    "(ECOSYSTEM-RATIONALIZATION.md §5a Phase B). "
                    "See the wicked-garden-archetype skill's migrate action for the migration path."
                ),
            })
            return 2
        _emit({"error": f"unknown command: {argv[0]}", "commands": list(_DISPATCH)})
        return 2
    try:
        return handler(argv[1:])
    except Exception as e:  # noqa: BLE001 — surface as data, never traceback.
        _emit({"error": f"{type(e).__name__}: {e}",
               "command": argv[0],
               "detail": "loom never raises at the CLI boundary (R4)."})
        return 2


if __name__ == "__main__":
    sys.exit(main())
