#!/usr/bin/env python3
"""inject_all.py — run every injected-edge extractor against the codegraph graph.

`codegraph index` rebuilds the *static* graph (symbols + imports/calls/refs) and
knows nothing about wicked-garden's injected layer — the string-keyed relationships
grep and a static call-graph can't see:

  - bus producer → consumer        (emit + _bus_consumers.json)
  - command → agent dispatch       (subagent_type)
  - agent → capability             (tool-capabilities + CAPABILITY_REGISTRY)

Those edges are INSERTed on top of the static graph and are dropped whenever the
graph is re-indexed. This is the single entry point — search:index, CI, or a
pre-push refresh — that re-applies all of them in one pass, so blast-radius and
lineage see the complete picture instead of a stale or empty injected layer (#916).

Stdlib-only. Idempotent (each extractor clears and re-inserts only its own edges).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inject_capability_edges  # noqa: E402
import inject_dispatch_edges  # noqa: E402
import inject_edges  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
# (label, module) — bus first (anchors to real code nodes), then the markdown layers
_EXTRACTORS = (
    ("bus", inject_edges),
    ("dispatch", inject_dispatch_edges),
    ("capability", inject_capability_edges),
)


def inject_all(db_path: Path) -> Dict[str, Any]:
    """Run every extractor against db_path; return per-extractor stats + a total."""
    out: Dict[str, Any] = {}
    total = 0
    for label, module in _EXTRACTORS:
        stats = module.inject(db_path)
        out[label] = stats
        total += int(stats.get("edges_added", 0))
    out["total_injected_edges"] = total
    return out


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else _REPO / ".codegraph" / "codegraph.db"
    if not db.exists():
        print(json.dumps({"error": f"codegraph db not found at {db}; run `codegraph index` first"}))
        return 1
    print(json.dumps(inject_all(db), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
