"""Tests for ``scripts/crew/log_retention.py`` (#505).

Covers:
  - Below threshold: no rotation
  - Above threshold: rotation fires, archive is gzipped, fresh log starts
  - ``WG_LOG_RETENTION_MAX_MB`` env var override
  - Integration with ``dispatch_log.append`` + ``gate_ingest_audit.append_audit_entry``
  - Fail-open on unwritable archive dir
  - Malformed env var falls back to default

Deterministic. Stdlib-only. No wall-clock dependency in assertions.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import dispatch_log  # noqa: E402
from log_retention import (  # noqa: E402
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_MAX_SIZE_BYTES,
    rotate_if_needed,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RotationTriggerAtThreshold(unittest.TestCase):
    def test_below_threshold_does_not_rotate(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "phases" / "design" / "dispatch-log.jsonl"
            _write(log, "x" * 100)
            result = rotate_if_needed(log, max_size_bytes=1024)
            self.assertIsNone(result)
            # Archive directory never created when no rotation fires.
            self.assertFalse((log.parent / DEFAULT_ARCHIVE_DIR).exists())
            # Original file untouched.
            self.assertEqual(log.read_text(), "x" * 100)

    def test_at_threshold_rotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "phases" / "design" / "dispatch-log.jsonl"
            _write(log, "x" * 2048)
            result = rotate_if_needed(log, max_size_bytes=1024)
            self.assertIsNotNone(result)
            # Archive exists, is gzipped, decodes to original payload.
            self.assertTrue(result.exists())
            self.assertTrue(result.name.endswith(".jsonl.gz"))
            with gzip.open(result, "rb") as fp:
                self.assertEqual(fp.read(), b"x" * 2048)
            # Fresh log is empty and preserved at the original path.
            self.assertTrue(log.exists())
            self.assertEqual(log.read_text(), "")

    def test_missing_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "does-not-exist.jsonl"
            result = rotate_if_needed(log, max_size_bytes=10)
            self.assertIsNone(result)

    def test_directory_passed_instead_of_file_skips_safely(self):
        # Callers that accidentally hand us a directory must not crash.
        with tempfile.TemporaryDirectory() as tmp:
            as_dir = Path(tmp) / "not-a-file"
            as_dir.mkdir()
            result = rotate_if_needed(as_dir, max_size_bytes=1)
            self.assertIsNone(result)


class EnvVarOverride(unittest.TestCase):
    def test_env_var_lowers_threshold(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WG_LOG_RETENTION_MAX_MB": "0.001"}  # ~1KB
        ):
            log = Path(tmp) / "phases" / "design" / "dispatch-log.jsonl"
            _write(log, "x" * 2048)
            # No explicit max_size_bytes — env-var override should apply.
            result = rotate_if_needed(log)
            self.assertIsNotNone(result)

    def test_malformed_env_var_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WG_LOG_RETENTION_MAX_MB": "not-a-number"}
        ):
            log = Path(tmp) / "phases" / "design" / "dispatch-log.jsonl"
            _write(log, "x" * 2048)
            # Should not rotate — 2KB is well below the 10MB default.
            result = rotate_if_needed(log)
            self.assertIsNone(result)

    def test_zero_env_var_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WG_LOG_RETENTION_MAX_MB": "0"}
        ):
            log = Path(tmp) / "phases" / "design" / "dispatch-log.jsonl"
            _write(log, "x" * 2048)
            # Zero → default, no rotation for small file.
            result = rotate_if_needed(log)
            self.assertIsNone(result)


class RotationFailOpen(unittest.TestCase):
    def test_unwritable_archive_dir_returns_none(self):
        # Simulate mkdir failure by pointing archive dir into a regular file.
        with tempfile.TemporaryDirectory() as tmp:
            log_parent = Path(tmp) / "phases" / "design"
            log_parent.mkdir(parents=True)
            log = log_parent / "dispatch-log.jsonl"
            _write(log, "x" * 2048)

            # Create a file where the archive dir should live.
            (log_parent / "archive").write_text("blocking")

            # Rotation should fail open and leave the original intact.
            result = rotate_if_needed(log, max_size_bytes=1024)
            self.assertIsNone(result)
            self.assertEqual(log.read_text(), "x" * 2048)


class DefaultConstants(unittest.TestCase):
    def test_default_max_is_10mb(self):
        self.assertEqual(DEFAULT_MAX_SIZE_BYTES, 10 * 1024 * 1024)

    def test_default_archive_dir(self):
        self.assertEqual(DEFAULT_ARCHIVE_DIR, "archive")


# ---------------------------------------------------------------------------
# Integration — callers invoke rotate_if_needed before each append.
# ---------------------------------------------------------------------------


class DispatchLogRotatesOnAppend(unittest.TestCase):
    def setUp(self):
        dispatch_log._reset_state_for_tests()
        dispatch_log.set_hmac_secret("b" * 64)

    def tearDown(self):
        dispatch_log._reset_state_for_tests()

    def test_append_triggers_rotation_above_threshold(self):
        """Rotation runs in the projector path post PR-#800.

        Pre-PR-#800 ``dispatch_log.append`` called ``rotate_if_needed``
        before writing — that lived alongside the legacy direct write.
        Both moved to the projector handler ``_dispatch_log_appended``
        when the source-side write was deleted.  This test drives a
        real bus → projector roundtrip so rotation fires under the new
        architecture.
        """
        # Reuse the daemon-pipeline helper from sibling test file.
        from tests.crew.test_dispatch_log import (
            _setup_daemon_db_for_test,
            _simulate_bus_pipeline,
        )

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WG_LOG_RETENTION_MAX_MB": "0.001"}  # ~1KB
        ):
            project = Path(tmp) / "proj"
            (project / "phases" / "design").mkdir(parents=True)
            db_path = _setup_daemon_db_for_test(Path(tmp), project)

            # Pre-seed the log beyond threshold so the next append rotates.
            log = project / "phases" / "design" / "dispatch-log.jsonl"
            log.write_text("x" * 2048)

            with patch.dict(
                os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
            ), patch("_bus.emit_event",
                     side_effect=_simulate_bus_pipeline(db_path)):
                dispatch_log.append(
                    project, "design",
                    reviewer="r",
                    gate="g",
                    dispatch_id="d-after-rotate",
                    dispatched_at="2026-04-19T09:00:00+00:00",
                )

            # Archive was created (rotation ran inside the projector).
            archive_dir = log.parent / DEFAULT_ARCHIVE_DIR
            self.assertTrue(archive_dir.exists())
            archives = list(archive_dir.glob("dispatch-log.*.jsonl.gz"))
            self.assertEqual(len(archives), 1)
            # Fresh log contains only the new record (pre-seed rotated away).
            lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["dispatch_id"], "d-after-rotate")
            os.environ.pop("WG_DAEMON_DB", None)


class AuditLogRotatesOnAppend(unittest.TestCase):
    def test_audit_append_triggers_rotation(self):
        from gate_ingest_audit import append_audit_entry

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WG_LOG_RETENTION_MAX_MB": "0.001"}  # ~1KB
        ):
            project = Path(tmp) / "proj"
            (project / "phases" / "design").mkdir(parents=True)
            audit = project / "phases" / "design" / "gate-ingest-audit.jsonl"
            # Seed above threshold.
            audit.write_text("x" * 2048)

            append_audit_entry(
                project, "design",
                event="schema_violation",
                reason="test-trigger",
                offending_field="verdict",
            )

            archive_dir = audit.parent / DEFAULT_ARCHIVE_DIR
            self.assertTrue(archive_dir.exists())
            archives = list(archive_dir.glob("gate-ingest-audit.*.jsonl.gz"))
            self.assertEqual(len(archives), 1)
            # Fresh log has exactly one new audit record.
            lines = [ln for ln in audit.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
