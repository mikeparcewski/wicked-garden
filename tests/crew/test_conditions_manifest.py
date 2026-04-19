#!/usr/bin/env python3
"""
Unit tests for scripts/crew/conditions_manifest.py (issue #477).

Covers:
    - mark_cleared flips a condition atomically.
    - Crash between sidecar-write and manifest-update leaves an orphan
      that recover() reconciles.
    - recover() is idempotent.
    - Unknown condition_id raises ValueError.
    - Missing manifest raises FileNotFoundError.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "crew"))

import conditions_manifest  # noqa: E402  (path setup above)


def _write_manifest(path: Path, conditions):
    """Write a fresh conditions-manifest.json fixture."""
    payload = {
        "source_gate": "design",
        "created_at": "2026-01-01T00:00:00Z",
        "conditions": conditions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


class MarkClearedTests(unittest.TestCase):
    """Happy-path + error behavior of ``mark_cleared``."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest_path = self.root / "phases" / "design" / "conditions-manifest.json"
        _write_manifest(
            self.manifest_path,
            [
                {"id": "CONDITION-1", "description": "foo", "verified": False,
                 "resolution": None, "verified_at": None},
                {"id": "CONDITION-2", "description": "bar", "verified": False,
                 "resolution": None, "verified_at": None},
            ],
        )

    def test_mark_cleared_flips_condition_and_writes_sidecar(self) -> None:
        updated = conditions_manifest.mark_cleared(
            self.manifest_path, "CONDITION-1",
            resolution_ref="phases/design/amendments.jsonl#AMD-1",
            note="resolved by design addendum",
        )
        self.assertTrue(updated["conditions"][0]["verified"])
        self.assertEqual(
            updated["conditions"][0]["resolution"],
            "phases/design/amendments.jsonl#AMD-1",
        )
        self.assertFalse(updated["conditions"][1]["verified"],
                         "sibling condition must not be touched")

        # Sidecar present on disk.
        sidecar = self.manifest_path.parent / "conditions-manifest.CONDITION-1.resolution.json"
        self.assertTrue(sidecar.exists())
        sidecar_payload = json.loads(sidecar.read_text())
        self.assertEqual(sidecar_payload["condition_id"], "CONDITION-1")
        self.assertEqual(
            sidecar_payload["resolution_ref"],
            "phases/design/amendments.jsonl#AMD-1",
        )

        # Persisted manifest matches the returned dict.
        reloaded = json.loads(self.manifest_path.read_text())
        self.assertTrue(reloaded["conditions"][0]["verified"])
        self.assertEqual(reloaded["conditions"][0]["resolution_note"],
                         "resolved by design addendum")

    def test_mark_cleared_raises_on_missing_condition(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            conditions_manifest.mark_cleared(
                self.manifest_path, "CONDITION-99", "ref"
            )
        self.assertIn("CONDITION-99", str(ctx.exception))

    def test_mark_cleared_raises_on_missing_manifest(self) -> None:
        with self.assertRaises(FileNotFoundError):
            conditions_manifest.mark_cleared(
                self.root / "does-not-exist.json", "CONDITION-1", "ref"
            )


class CrashRecoveryTests(unittest.TestCase):
    """Simulate a crash between sidecar-write and manifest-flip.

    The fix: recover() scans for orphan sidecars and finishes the flip.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest_path = self.root / "phases" / "design" / "conditions-manifest.json"
        _write_manifest(
            self.manifest_path,
            [
                {"id": "CONDITION-1", "description": "foo", "verified": False,
                 "resolution": None, "verified_at": None},
            ],
        )

    def test_crash_between_sidecar_and_manifest_is_recovered(self) -> None:
        # Simulate: mark_cleared raises AFTER the sidecar lands but
        # BEFORE the manifest is replaced. We do this by patching
        # atomic_write_json to raise on its SECOND call.
        calls: list = []
        real_write = conditions_manifest.atomic_write_json

        def selective_write(path, data):
            calls.append(path)
            if len(calls) == 2:
                # Second call is the manifest flip — simulate crash.
                raise RuntimeError("simulated crash mid-flip")
            return real_write(path, data)

        with mock.patch.object(
            conditions_manifest, "atomic_write_json",
            side_effect=selective_write,
        ):
            with self.assertRaises(RuntimeError):
                conditions_manifest.mark_cleared(
                    self.manifest_path, "CONDITION-1",
                    resolution_ref="phases/design/amendments.jsonl#AMD-1",
                )

        # Sidecar is on disk; manifest still shows unverified.
        sidecar = self.manifest_path.parent / "conditions-manifest.CONDITION-1.resolution.json"
        self.assertTrue(sidecar.exists(), "sidecar must have landed first")
        manifest_before = json.loads(self.manifest_path.read_text())
        self.assertFalse(
            manifest_before["conditions"][0]["verified"],
            "manifest must still be uncleared after crash",
        )

        # Recovery finds the orphan and finishes the flip.
        reconciled = conditions_manifest.recover(self.manifest_path)
        self.assertEqual(reconciled, ["CONDITION-1"])

        manifest_after = json.loads(self.manifest_path.read_text())
        self.assertTrue(manifest_after["conditions"][0]["verified"])
        self.assertEqual(
            manifest_after["conditions"][0]["resolution"],
            "phases/design/amendments.jsonl#AMD-1",
        )

    def test_recover_is_idempotent(self) -> None:
        # First clear normally.
        conditions_manifest.mark_cleared(
            self.manifest_path, "CONDITION-1", "ref-1"
        )
        # Running recover now should be a no-op (condition already verified).
        reconciled = conditions_manifest.recover(self.manifest_path)
        self.assertEqual(
            reconciled, [],
            "recovery must be a no-op when the manifest is already consistent",
        )

    def test_recover_ignores_sidecars_for_missing_conditions(self) -> None:
        # Plant a sidecar for a condition that no longer exists in the
        # manifest (e.g. manifest was regenerated since the crash).
        sidecar = self.manifest_path.parent / "conditions-manifest.GHOST.resolution.json"
        sidecar.write_text(json.dumps({
            "condition_id": "GHOST",
            "resolution_ref": "irrelevant",
            "note": None,
            "written_at": "2026-01-01T00:00:00Z",
        }))
        reconciled = conditions_manifest.recover(self.manifest_path)
        self.assertEqual(reconciled, [])
        # Manifest is untouched.
        reloaded = json.loads(self.manifest_path.read_text())
        self.assertFalse(reloaded["conditions"][0]["verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
