"""loom — absorbed peer-resolution runtime (wicked-loom Phase B absorption).

This package is the absorbed peer-resolution surface from wicked-loom,
moved into wicked-garden as part of the wicked-* ecosystem rationalization
(ECOSYSTEM-RATIONALIZATION.md §5a Phase B).

KEPT (peer-resolution surface — this package):
  manifest.py  — peer registry: peer names, version pins, install/probe commands
  resolve.py   — runtime resolution ladder: env → PATH → npx
  compose.py   — version-check + install orchestration (doctor / compose install)
  gate.py      — synchronous fail-closed produces gate (vault cross-check wrapper)
  cli.py       — slim CLI: resolve / doctor / compose / gate ONLY

RETIRED (flow conductor surface — NOT included):
  flow.py      — loom flow run/status/resume  → RETIRED, replaced by wicked-crew
  flowstate.py — flow state persistence       → RETIRED
  busemit.py   — bus event emission for flow  → RETIRED

wicked-loom as a standalone npm package is absorbed — users do not need to
install it separately. The external CLI (wicked-loom / loom) is no longer
required; garden's scripts/_loom.py dispatches to this package in-process.
"""
