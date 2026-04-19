"""tests/crew/test_consumer_deletion.py — Verify qe:scenario-scaffold consumer is deleted (D7).

Provenance: AC-7, AC-16
T1: deterministic — pure file existence checks
T3: isolated — read-only
T4: single focus per test
T5: descriptive names
T6: each docstring cites its AC
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
QE_CONSUMERS_PATH = REPO_ROOT / "scripts" / "qe" / "_bus_consumers.py"
BUS_CONSUMERS_JSON = REPO_ROOT / "scripts" / "_bus_consumers.json"


def test_qe_bus_consumers_py_does_not_exist():
    """AC-7, AC-16: scripts/qe/_bus_consumers.py must not exist in the repo."""
    assert not QE_CONSUMERS_PATH.exists(), (
        f"scripts/qe/_bus_consumers.py still exists at {QE_CONSUMERS_PATH}. "
        "D7 requires this file to be deleted (git rm)."
    )


def test_bus_consumers_json_exists():
    """AC-7, AC-16: scripts/_bus_consumers.json must exist (only the entry was removed)."""
    assert BUS_CONSUMERS_JSON.exists(), (
        f"scripts/_bus_consumers.json not found at {BUS_CONSUMERS_JSON}"
    )


def test_entry_38_absent_from_bus_consumers_json():
    """AC-16: entry with id='qe:scenario-scaffold' must not exist in _bus_consumers.json."""
    data = json.loads(BUS_CONSUMERS_JSON.read_text(encoding="utf-8"))
    consumers = data.get("consumers", [])
    for entry in consumers:
        assert entry.get("id") != "qe:scenario-scaffold", (
            f"Entry 'qe:scenario-scaffold' still exists in _bus_consumers.json. "
            "D7 requires this entry to be removed."
        )


def test_no_qe_bus_consumers_module_reference_in_registry():
    """AC-16: no entry in _bus_consumers.json should reference scripts/qe/_bus_consumers.py."""
    data = json.loads(BUS_CONSUMERS_JSON.read_text(encoding="utf-8"))
    consumers = data.get("consumers", [])
    for entry in consumers:
        module = entry.get("module", "")
        assert "scripts/qe/_bus_consumers" not in module, (
            f"Entry {entry.get('id')!r} still references deleted module: {module}"
        )
