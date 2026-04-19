"""tests/crew/conftest.py — sys.path setup for tests/crew/ suite.

Ensures scripts/ appears before scripts/crew/ in sys.path so that
`from crew.archetype_detect import ...` resolves correctly regardless of
test collection order. This fixes a pre-existing batch-1 issue where
test_phase_manager.py (which inserts scripts/crew/ at index 0) would
shadow the crew/ package namespace when collected before test_archetype_detect.

Provenance: sys.path isolation fix for combined pytest run (build batch 2).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = str(_REPO_ROOT / "scripts")
_SCRIPTS_CREW = str(_REPO_ROOT / "scripts" / "crew")

# Ensure scripts/ is first so `from crew.X import` works as a package import.
# scripts/crew/ is still available for direct imports (e.g. `import phase_manager`).
if _SCRIPTS in sys.path:
    sys.path.remove(_SCRIPTS)
sys.path.insert(0, _SCRIPTS)

if _SCRIPTS_CREW not in sys.path:
    sys.path.append(_SCRIPTS_CREW)
