"""tests/conftest.py — Root conftest for sys.path ordering across the test suite.

Establishes scripts/ at position 0 before any test module is collected, so that
`from crew.archetype_detect import ...` (batch-1 style) resolves correctly
regardless of which test file is collected first.

Without this, test_adopt_legacy.py (collected first alphabetically) inserts
scripts/crew/ at sys.path[0], which causes scripts/crew/crew.py to shadow the
crew/ directory namespace, making `from crew.archetype_detect import ...` fail
in later-collected tests with `No module named 'crew.archetype_detect'`.

Uses pytest_configure hook — runs before any test module is imported during
collection, ensuring scripts/ is at sys.path[0] from the very start.

Provenance: sys.path isolation fix (build batch 2 — not a scope change).

Site 3 addition: autouse fixture that resets _bus.py emit counters before
each test so counter state from one test cannot bleed into another.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(_REPO_ROOT / "scripts")
_SCRIPTS_CREW = str(_REPO_ROOT / "scripts" / "crew")


def pytest_configure(config):
    """Run before any test module is imported — sets up sys.path correctly.

    Ensures scripts/ is at position 0 so package imports work. Also adds
    scripts/crew/ at the end for direct imports (e.g. `import phase_manager`).
    """
    # Remove any existing scripts/ entry (may be present from earlier conftest)
    while _SCRIPTS in sys.path:
        sys.path.remove(_SCRIPTS)
    # Insert scripts/ at position 0 — highest priority
    sys.path.insert(0, _SCRIPTS)

    # Append scripts/crew/ for backward-compat direct imports (import phase_manager)
    if _SCRIPTS_CREW not in sys.path:
        sys.path.append(_SCRIPTS_CREW)


@pytest.fixture(autouse=True)
def _reset_bus_emit_counters():
    """Reset _bus.py emit health counters before each test.

    Prevents counter state from leaking between tests when _bus is imported
    by any test in the suite. Fail-open: if _bus cannot be imported (e.g.
    in isolated test environments), the fixture is a no-op.
    """
    try:
        import _bus
        _bus._bus_reset_stats()
    except ImportError:
        pass
    yield
    # Post-test reset is intentionally omitted — the pre-test reset above
    # is sufficient. Post-test would mask counter assertions in teardown.
