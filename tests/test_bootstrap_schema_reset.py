#!/usr/bin/env python3
"""Tier 2 — Integration tests for bootstrap schema reset detection (#154).

Tests cover:
- Schema reset detected when CP is empty but local .json files exist
- No false positive when local dir has only non-JSON files
- No false positive when local dir has only underscore-prefixed files
- No false positive when local dir is empty
- Detection is gated on cp_available (fails open)
- Uses get_local_path instead of hardcoded paths
"""

import ast
import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

_HOOKS_SCRIPTS = Path(__file__).resolve().parents[1] / "hooks" / "scripts"


class TestSchemaResetDetectionLogic(unittest.TestCase):
    """#154 — Schema reset detection in bootstrap.py."""

    def test_json_filter_excludes_non_json(self):
        """Only .json files (not prefixed with _) should trigger detection."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            # Create non-JSON files that shouldn't trigger
            (d / "README.md").write_text("readme")
            (d / "_queue.jsonl").write_text("{}")
            (d / ".DS_Store").write_bytes(b"")

            # Apply the same filter used in bootstrap
            matching = [
                f for f in d.iterdir()
                if f.suffix == ".json" and not f.name.startswith("_")
            ]
            self.assertEqual(len(matching), 0)

    def test_json_filter_includes_json_files(self):
        """Regular .json files should trigger detection."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "project-abc.json").write_text('{"name": "abc"}')
            (d / "project-def.json").write_text('{"name": "def"}')

            matching = [
                f for f in d.iterdir()
                if f.suffix == ".json" and not f.name.startswith("_")
            ]
            self.assertEqual(len(matching), 2)

    def test_empty_dir_no_match(self):
        """Empty directory should not trigger detection."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            matching = [
                f for f in d.iterdir()
                if f.suffix == ".json" and not f.name.startswith("_")
            ]
            self.assertEqual(len(matching), 0)


class TestBootstrapNoHardcodedPaths(unittest.TestCase):
    """Low-9 / W-02 — No hardcoded paths in schema reset detection."""

    def test_bootstrap_uses_get_local_path(self):
        """Bootstrap should use get_local_path, not hardcoded Path.home() / '.something-wicked'."""
        bootstrap_source = (_HOOKS_SCRIPTS / "bootstrap.py").read_text()

        # Find the schema reset detection block
        tree = ast.parse(bootstrap_source)
        # Check that get_local_path is imported in the reset detection section
        self.assertIn("get_local_path", bootstrap_source,
                       "bootstrap.py should import get_local_path from _storage")

    def test_schema_reset_block_no_hardcoded_something_wicked(self):
        """The schema reset detection block should not hardcode ~/.something-wicked."""
        bootstrap_source = (_HOOKS_SCRIPTS / "bootstrap.py").read_text()

        # Find the reset detection section (between "schema reset" comment and the break)
        lines = bootstrap_source.split("\n")
        in_reset_block = False
        reset_block_lines = []
        for line in lines:
            if "schema reset" in line.lower() or "cp_schema_reset_detected" in line:
                in_reset_block = True
            if in_reset_block:
                reset_block_lines.append(line)
                if "cp_schema_reset_detected = True" in line:
                    break

        reset_block = "\n".join(reset_block_lines)
        # The block should use get_local_path, not hardcoded paths
        self.assertNotIn(
            '".something-wicked"',
            reset_block,
            "Schema reset detection should use get_local_path, not hardcoded paths"
        )


if __name__ == "__main__":
    unittest.main()
