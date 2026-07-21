"""Tests for PropagationEngine — multi-file rename propagation (L2-013) and
plan completeness (L2-014).

L2-013: plan_propagation with RENAME_FIELD includes ALL files that reference the
        target symbol in files_affected.
L2-014: format_plan output shows the complete affected file set before any patches
        are applied (plan completeness check).

Uses a synthetic patch-schema SQLite DB built in memory — no wicked-brain, no peers.
The DB is a minimal subset of the patch-schema (symbols + refs tables only); it does
not include every table or index that codegraph_db.build_patch_db() produces (e.g. no
metadata table), but includes all columns PropagationEngine queries.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from generators.propagation_engine import PropagationEngine  # noqa: E402
from generators.base import ChangeSpec, ChangeType  # noqa: E402
from patch import format_plan  # noqa: E402


def _make_patch_db(path: str) -> None:
    """Build a minimal patch-schema SQLite DB with symbols across 3 files.

    Graph:
      entity:User  (src/models/user.py)          — source of the rename
        ← refs/uses ← entity:UserSerializer      (src/api/serializers.py)
        ← refs/uses ← entity:UserFactory         (src/tests/factories.py)
      entity:Order (src/models/order.py)          — unrelated (control)
    """
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE symbols (
          id TEXT PRIMARY KEY, name TEXT, type TEXT, file_path TEXT,
          line_start INTEGER, line_end INTEGER, metadata TEXT, layer TEXT
        );
        CREATE TABLE refs (
          source_id TEXT, target_id TEXT, ref_type TEXT, confidence REAL
        );
        CREATE TABLE symbol_refs (source_id TEXT, target_id TEXT, ref_type TEXT);
        CREATE TABLE symbol_calls (symbol_id TEXT, target_id TEXT);
        CREATE TABLE symbol_imports (symbol_id TEXT, target_id TEXT);
        """
    )
    symbols = [
        ("entity:User",          "User",          "class", "src/models/user.py",       1, 20, None, "domain"),
        ("entity:UserSerializer","UserSerializer", "class", "src/api/serializers.py",   1, 15, None, "api"),
        ("entity:UserFactory",   "UserFactory",   "class", "src/tests/factories.py",   1, 10, None, "test"),
        ("entity:Order",         "Order",         "class", "src/models/order.py",      1, 18, None, "domain"),
    ]
    conn.executemany(
        "INSERT INTO symbols (id,name,type,file_path,line_start,line_end,metadata,layer) "
        "VALUES (?,?,?,?,?,?,?,?)",
        symbols,
    )
    # Serializer and Factory both reference (use) the User entity.
    refs = [
        ("entity:UserSerializer", "entity:User", "uses", 1.0),
        ("entity:UserFactory",    "entity:User", "uses", 1.0),
    ]
    conn.executemany(
        "INSERT INTO refs (source_id, target_id, ref_type, confidence) VALUES (?,?,?,?)",
        refs,
    )
    conn.commit()
    conn.close()


class PropagationMultiFilePlanTests(unittest.TestCase):
    """L2-013 — rename propagates to all referencing files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = str(Path(self._tmp.name) / "patch-symbols.db")
        _make_patch_db(self._db_path)
        self._engine = PropagationEngine(Path(self._db_path))

    def tearDown(self):
        self._engine.close()
        self._tmp.cleanup()

    def test_rename_plan_includes_all_referencing_files(self):
        """L2-013: RENAME_FIELD plan covers every file that references the target symbol."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        files = plan.files_affected

        self.assertIn("src/models/user.py", files,
                      "Source file must appear in files_affected")
        self.assertIn("src/api/serializers.py", files,
                      "Serializer references User — must appear in files_affected (L2-013)")
        self.assertIn("src/tests/factories.py", files,
                      "Factory references User — must appear in files_affected (L2-013)")

    def test_unrelated_file_not_in_plan(self):
        """L2-013 negative: files with no reference to the target symbol are excluded."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        self.assertNotIn("src/models/order.py", plan.files_affected,
                         "Order is unrelated to User rename — must NOT appear in plan")

    def test_rename_plan_referencing_symbols_in_all_affected(self):
        """L2-013: all symbols that reference the source appear in all_affected."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        all_ids = {s.id for s in plan.all_affected}

        # Direct consumers of User must appear somewhere in the plan
        self.assertIn("entity:UserSerializer", all_ids,
                      "UserSerializer (which uses User) must appear in all_affected")
        self.assertIn("entity:UserFactory", all_ids,
                      "UserFactory (which uses User) must appear in all_affected")

    def test_rename_plan_file_count_matches_all_affected_symbols(self):
        """L2-013: files_affected contains exactly the concrete expected file set for this graph."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        # Assert against the concrete expected set for this synthetic graph, not derived from plan
        # (deriving from all_affected would be tautological since files_affected IS that union).
        expected = {"src/models/user.py", "src/api/serializers.py", "src/tests/factories.py"}
        self.assertEqual(plan.files_affected, expected,
                         "files_affected must be exactly the 3 files in the User rename graph")

    def test_rename_plan_total_file_count(self):
        """L2-013: User has 2 consumers across 2 extra files → total 3 files affected."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        self.assertEqual(len(plan.files_affected), 3,
                         "Rename of User should affect 3 files: user.py + serializers.py + factories.py")


class PropagationPlanCompletenessTests(unittest.TestCase):
    """L2-014 — format_plan shows the complete affected file set."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = str(Path(self._tmp.name) / "patch-symbols.db")
        _make_patch_db(self._db_path)
        self._engine = PropagationEngine(Path(self._db_path))

    def tearDown(self):
        self._engine.close()
        self._tmp.cleanup()

    def test_format_plan_precedes_patches(self):
        """L2-014: plan is available before generate_patches is called (format_plan reads plan only)."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        # plan_propagation must succeed without generate_patches being called first
        plan = self._engine.plan_propagation(spec)
        output = format_plan(plan, change_type=ChangeType.RENAME_FIELD.value)
        self.assertIsNotNone(output)
        self.assertGreater(len(output), 0, "format_plan output must not be empty")

    def test_format_plan_shows_source_file_full_path(self):
        """L2-014: source file appears with full path in format_plan output."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        output = format_plan(plan, change_type=ChangeType.RENAME_FIELD.value)
        self.assertIn("src/models/user.py", output,
                      "Source file full path must appear in format_plan output (L2-014)")

    def test_format_plan_shows_all_impact_symbol_names(self):
        """L2-014: all symbols in this small synthetic graph appear in format_plan output.

        Note: format_plan truncates each impact section to the first 10 symbols — this test
        is valid only for plans with ≤ 10 impacts per section (which this 3-symbol graph is).
        Larger plans may have impact names truncated with '... and N more'.
        """
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        output = format_plan(plan, change_type=ChangeType.RENAME_FIELD.value)
        # Assert the concrete expected names for this synthetic graph (not dynamically derived).
        expected_names = {"User", "UserSerializer", "UserFactory"}
        for name in expected_names:
            self.assertIn(
                name, output,
                f"Symbol '{name}' must appear in format_plan output (L2-014 plan completeness)",
            )

    def test_format_plan_total_line_reflects_file_count(self):
        """L2-014: the 'Total:' footer in format_plan states the correct file count."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        output = format_plan(plan, change_type=ChangeType.RENAME_FIELD.value)
        expected_file_count = len(plan.files_affected)
        # format_plan footer: "Total: N symbols in M files"
        self.assertIn(
            f"in {expected_file_count} files", output,
            f"format_plan footer must state 'in {expected_file_count} files' (L2-014)",
        )

    def test_format_plan_shows_source_symbol_name(self):
        """L2-014: plan output names the source symbol so the developer knows what changed."""
        spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id="entity:User",
        )
        plan = self._engine.plan_propagation(spec)
        output = format_plan(plan, change_type=ChangeType.RENAME_FIELD.value)
        self.assertIn("User", output, "Plan must name the source symbol")


if __name__ == "__main__":
    unittest.main()
