"""wicked-estate#595 (HOLD gate b of wicked-estate#584): garden's search and blast paths on a
store the codegraph import wrote.

The store is estate's gate fixture (`tests/fixtures/codegraph/coverage`), indexed with
`--codegraph` by the estate head under test (`scripts/codegraph-fixture-store.py store`).
Estate's CI sets WICKED_CODEGRAPH_FIXTURE_STORE and WICKED_ESTATE_MCP_BIN, runs this file from
garden's main, and fails when the `codegraph gate: garden` line is missing. Without the store
there is nothing to read, and the test skips and says so.

The calls are the ones skills/search/SKILL.md gives a seat: the read-only shim with the
`BlastRadius` and `SearchEntity` tools.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

STORE_ENV = "WICKED_CODEGRAPH_FIXTURE_STORE"
SHIM = Path(__file__).resolve().parent.parent / "scripts" / "_estate_client.py"
BASE = "ts-typescript . . . src/ts/base/Base#"
SQUARE = "ts-typescript . . . src/ts/shapes/Square#"


def _call(store: str, home: Path, tool: str, arguments: dict) -> dict:
    # Only the binary override survives from the caller: no run markers, no other store pin.
    env = {k: v for k, v in os.environ.items() if not k.startswith("WICKED_")}
    if os.environ.get("WICKED_ESTATE_MCP_BIN"):
        env["WICKED_ESTATE_MCP_BIN"] = os.environ["WICKED_ESTATE_MCP_BIN"]
    env["WICKED_HOME"] = str(home)
    env["WICKED_ESTATE_PERSISTENT"] = "0"
    out = subprocess.run(
        [sys.executable, str(SHIM), "--readonly", "--db", store, "call",
         json.dumps({"tool": tool, "arguments": arguments})],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert out.returncode == 0, f"{tool}: exit {out.returncode}: {out.stdout} {out.stderr}"
    doc = json.loads(out.stdout)
    assert doc.get("result") is not None, f"{tool}: {doc}"
    return doc["result"]


def test_garden_reads_the_codegraph_gate_store(tmp_path):
    store = os.environ.get(STORE_ENV)
    if not store:
        pytest.skip(f"codegraph gate: {STORE_ENV} is unset, so there is no store to read")
    home = tmp_path / "home"
    home.mkdir()

    # search: the symbol a codegraph edge binds resolves by name.
    found = _call(store, home, "SearchEntity", {"name": "Square"})
    ids = {m.get("id") or m.get("symbol") for m in found.get("matches", [])}
    assert SQUARE in ids, f"SearchEntity Square: {found}"

    # blast: Base's dependents include Square, through the codegraph-bound extends edge.
    blast = _call(store, home, "BlastRadius", {"symbol": BASE})
    dependents = {d.get("id") for d in blast.get("dependents", [])}
    assert SQUARE in dependents, f"BlastRadius Base: {blast}"

    print(f"codegraph gate: garden searched Square and found {len(dependents)} dependents of Base")
