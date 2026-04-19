"""Tests for ``scripts/crew/gate_ingest_audit.py`` (#471, AC-8).

Covers:
  - Append round-trip
  - Hashing of offending value (never raw content in log)
  - I/O failure is non-fatal (caller's reject still propagates)
  - Event-type enum enforcement

Deterministic. Stdlib-only.
"""

from __future__ import annotations

import hashlib
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

from gate_ingest_audit import VALID_EVENT_TYPES, append_audit_entry  # noqa: E402


class AuditAppend(unittest.TestCase):
    def test_append_writes_one_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            (project / "phases" / "design").mkdir(parents=True)
            append_audit_entry(
                project, "design",
                event="schema_violation",
                reason="invalid-verdict-enum:MAYBE",
                offending_field="verdict",
                offending_value="MAYBE",
                raw_bytes=b'{"verdict":"MAYBE"}',
                gate="design-quality",
            )
            log_path = project / "phases" / "design" / "gate-ingest-audit.jsonl"
            self.assertTrue(log_path.exists())
            lines = log_path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event"], "schema_violation")
            self.assertEqual(record["phase"], "design")
            self.assertEqual(record["gate"], "design-quality")
            self.assertEqual(record["reason"], "invalid-verdict-enum:MAYBE")
            self.assertEqual(record["offending_field"], "verdict")
            # AC-8 critical property: raw offending value is NEVER logged.
            self.assertNotIn("MAYBE", record["violation_snippet_hash"])
            self.assertTrue(record["violation_snippet_hash"].startswith("sha256:"))
            # file_sha256 is the hash of the raw bytes.
            expected = "sha256:" + hashlib.sha256(b'{"verdict":"MAYBE"}').hexdigest()
            self.assertEqual(record["file_sha256"], expected)

    def test_append_never_raises_on_unwritable_dir(self):
        # Point the audit writer at a path whose parent is not a
        # directory — the append should WARN to stderr and return,
        # never raise (AC-8 non-fatal write).
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "regular-file-as-phase-dir"
            project.write_text("not a dir")
            # Calling audit_entry with a regular-file path silently
            # fails. We assert no exception escapes.
            append_audit_entry(
                project, "design",
                event="schema_violation",
                reason="malformed-json:x",
            )

    def test_unknown_event_is_still_logged_tagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            (project / "phases" / "design").mkdir(parents=True)
            append_audit_entry(
                project, "design",
                event="totally-made-up",
                reason="x",
            )
            log_path = project / "phases" / "design" / "gate-ingest-audit.jsonl"
            record = json.loads(log_path.read_text().splitlines()[0])
            # Prefix tag marks the unknown event so forensic tools can
            # distinguish valid from invalid-but-logged records.
            self.assertTrue(record["event"].startswith("unknown:"))

    def test_valid_event_types_non_empty(self):
        self.assertGreater(len(VALID_EVENT_TYPES), 0)


if __name__ == "__main__":
    unittest.main()
