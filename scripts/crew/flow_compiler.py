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
import os
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
