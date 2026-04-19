#!/usr/bin/env python3
"""tests/crew/test_parallelization_enforcement.py — SC-6 / AC-α10.

Verifies that ``phase_manager._check_parallelization`` enforces:
    - sub_task_count < 2 → vacuously OK.
    - sub_task_count >= 2 AND dispatched_in_parallel=True → OK.
    - sub_task_count >= 2 AND dispatched_in_parallel=False AND serial_reason empty
        → fails with reason 'parallelization-check-missing'.
"""

import unittest
from pathlib import Path
import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


class TestParallelizationCheck(unittest.TestCase):
    """AC-α10 — parallelization check enforcement."""

    def test_single_subtask_is_vacuous(self):
        """sub_task_count < 2 skips the check."""
        check = {"sub_task_count": 1, "dispatched_in_parallel": False, "serial_reason": None}
        self.assertIsNone(phase_manager._check_parallelization(check))

    def test_parallel_dispatch_passes(self):
        """dispatched_in_parallel=True with N>=2 passes."""
        check = {"sub_task_count": 3, "dispatched_in_parallel": True, "serial_reason": None}
        self.assertIsNone(phase_manager._check_parallelization(check))

    def test_serial_without_reason_fails(self):
        """dispatched_in_parallel=False with empty serial_reason fails."""
        check = {"sub_task_count": 3, "dispatched_in_parallel": False, "serial_reason": ""}
        fail = phase_manager._check_parallelization(check)
        self.assertEqual(fail, "parallelization-check-missing")

    def test_serial_with_reason_passes(self):
        """dispatched_in_parallel=False with non-empty serial_reason passes."""
        check = {
            "sub_task_count": 3,
            "dispatched_in_parallel": False,
            "serial_reason": "Sub-tasks share a file — sequential writes required.",
        }
        self.assertIsNone(phase_manager._check_parallelization(check))

    def test_missing_check_dict_fails(self):
        """A non-dict parallelization_check fails."""
        self.assertEqual(phase_manager._check_parallelization(None), "parallelization-check-missing")


if __name__ == "__main__":
    unittest.main()
