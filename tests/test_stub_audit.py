#!/usr/bin/env python3
"""
tests/test_stub_audit.py

AC-STUB-1, AC-STUB-3, AC-STUB-4: Pass stubs in scripts/ are annotated or implemented.

Verifies that:
- High-risk files have no bare uncommented pass statements
- Abstract base class stubs have been replaced with raise NotImplementedError
- NotImplementedError messages are descriptive

Does NOT require external deps — read-only file access to scripts/.
"""

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"

# High-risk files per AC-STUB-3
_HIGH_RISK_FILES = [
    _SCRIPTS / "patch" / "generators" / "propagation_engine.py",
    _SCRIPTS / "search" / "unified_search.py",
    _SCRIPTS / "search" / "watcher.py",
    _SCRIPTS / "crew" / "phase_manager.py",
]

# Abstract base files per AC-STUB-4
_BASE_FILES = [
    _SCRIPTS / "search" / "adapters" / "base.py",
    _SCRIPTS / "search" / "linkers" / "base.py",
    _SCRIPTS / "patch" / "generators" / "base.py",
]


def _has_inline_comment(line: str) -> bool:
    """Return True if a 'pass' line has an inline comment after it."""
    stripped = line.rstrip()
    return bool(re.search(r'pass\s*#', stripped))


def _is_bare_pass(line: str) -> bool:
    """Return True if the line is a bare uncommented pass statement."""
    return bool(re.match(r'^\s+pass\s*$', line))


class TestStubAudit(unittest.TestCase):
    """AC-STUB-1, AC-STUB-3, AC-STUB-4: Pass stubs are annotated or implemented."""

    def test_no_bare_pass_in_high_risk_files(self):
        """AC-STUB-3: High-risk files must have no bare uncommented pass statements.

        Each pass line must either:
        - Have an inline comment after it, OR
        - Be preceded by an 'except' line (exception silencer context — acceptable)
        """
        failures = []
        for file_path in _HIGH_RISK_FILES:
            self.assertTrue(file_path.exists(), f"High-risk file not found: {file_path}")
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if _is_bare_pass(line):
                    # Check if previous non-empty line contains 'except'
                    prev_line = ""
                    for j in range(i - 1, max(i - 3, -1), -1):
                        stripped = lines[j].strip()
                        if stripped:
                            prev_line = stripped
                            break
                    # Bare pass after except with no comment is still acceptable
                    # (the AC says must have inline comment)
                    failures.append(
                        f"{file_path.relative_to(_REPO_ROOT)}:{i + 1}: "
                        f"bare uncommented pass (context: '{prev_line[:60]}')"
                    )

        self.assertEqual(
            failures, [],
            f"Bare uncommented pass statements found in high-risk files:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_abstract_base_stubs_annotated(self):
        """AC-STUB-4: Abstract base class stubs must not contain bare pass.

        The pass statements in the named base files should have been replaced
        with raise NotImplementedError(...) or annotated.
        """
        failures = []
        for file_path in _BASE_FILES:
            self.assertTrue(file_path.exists(), f"Base file not found: {file_path}")
            src = file_path.read_text(encoding="utf-8")
            lines = src.splitlines()
            for i, line in enumerate(lines):
                if _is_bare_pass(line):
                    # Check surrounding context — should not be inside abstractmethod
                    context = "\n".join(lines[max(0, i - 5):i + 1])
                    if "@abstractmethod" in context or "def " in context:
                        failures.append(
                            f"{file_path.relative_to(_REPO_ROOT)}:{i + 1}: "
                            f"bare pass in abstract/method context"
                        )

        self.assertEqual(
            failures, [],
            f"Bare pass found in abstract method context in base files:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_base_not_implemented_message_is_descriptive(self):
        """AC-STUB-4: raise NotImplementedError messages in base files must be non-empty and descriptive."""
        for file_path in _BASE_FILES:
            self.assertTrue(file_path.exists(), f"Base file not found: {file_path}")
            src = file_path.read_text(encoding="utf-8")
            # Find all NotImplementedError raises
            matches = re.findall(r'raise NotImplementedError\(([^)]+)\)', src)
            for match in matches:
                msg = match.strip().strip('"\'')
                self.assertTrue(
                    len(msg) > 10,
                    f"{file_path.name}: NotImplementedError message too short or empty: {match!r}"
                )
                self.assertNotIn(
                    msg.lower(), {"not implemented", "notimplemented", "todo"},
                    f"{file_path.name}: NotImplementedError message must be descriptive, not: {match!r}"
                )

    def test_no_bare_pass_in_scripts_overall(self):
        """AC-STUB-1: No bare uncommented pass remains anywhere in scripts/.

        This is the final AC-STUB-1 pass condition: grep returns zero results.
        """
        failures = []
        for py_file in sorted(_SCRIPTS.rglob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if _is_bare_pass(line):
                    failures.append(f"{py_file.relative_to(_REPO_ROOT)}:{i + 1}")

        self.assertEqual(
            failures, [],
            f"Bare uncommented pass statements still exist in scripts/:\n"
            + "\n".join(f"  - {f}" for f in failures)
            + "\n\nAll bare pass must have an inline comment (# fail open / # intentional: <reason>)"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
