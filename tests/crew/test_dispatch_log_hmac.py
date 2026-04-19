"""Tests for HMAC-signed dispatch-log verification (#500).

Covers:
  - HMAC happy path: append + verify round-trip with matching secret
  - HMAC mismatch rejection via :class:`DispatchLogTamperError`
  - Legacy entry fallback (no ``hmac`` field → orphan-only, one-time WARN)
  - HMAC is NOT placed in audit records (secret + MAC never leak)
  - Secret is canonically hashed — key reordering does not break verify

Deterministic. No wall-clock dependency in assertions.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import dispatch_log  # noqa: E402
from dispatch_log import (  # noqa: E402
    DispatchLogTamperError,
    append,
    check_orphan,
    read_entries,
    set_hmac_secret,
)
from gate_result_schema import GateResultAuthorizationError  # noqa: E402


_FIXED_SECRET = "a" * 64  # deterministic hex-shape secret for tests


def _make_project(tmp: str, phase: str = "design") -> Path:
    project = Path(tmp) / "proj"
    (project / "phases" / phase).mkdir(parents=True)
    return project


class _HmacTestBase(unittest.TestCase):
    """Shared fixture that pins the HMAC secret so tests are deterministic."""

    def setUp(self) -> None:
        dispatch_log._reset_state_for_tests()
        set_hmac_secret(_FIXED_SECRET)

    def tearDown(self) -> None:
        dispatch_log._reset_state_for_tests()


class HmacHappyPath(_HmacTestBase):
    def test_append_writes_hmac_field(self):
        """Round-trip: appended record carries an ``hmac`` hex string."""
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="security-engineer",
                gate="design-quality",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T10:00:00+00:00",
            )
            entries = read_entries(project, "design")
            self.assertEqual(len(entries), 1)
            self.assertIn("hmac", entries[0])
            self.assertRegex(entries[0]["hmac"], r"^[0-9a-f]{64}$")

    def test_matching_entry_verifies_and_accepts(self):
        """A matching dispatch + correct HMAC → no raise from check_orphan."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="security-engineer",
                gate="design-quality",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T09:00:00+00:00",
            )
            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            check_orphan(parsed, project, "design")  # no raise


class HmacMismatch(_HmacTestBase):
    def test_tampered_hmac_raises_tamper_error(self):
        """Rewriting an entry's ``hmac`` → DispatchLogTamperError on verify."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="security-engineer",
                gate="design-quality",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T09:00:00+00:00",
            )
            # Forge the log: keep the entry body but rewrite the HMAC
            # to something an attacker without the secret would pick.
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            entry = json.loads(log_path.read_text().strip())
            entry["hmac"] = "0" * 64  # deterministic fake
            log_path.write_text(json.dumps(entry) + "\n")

            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            with self.assertRaises(DispatchLogTamperError) as cm:
                check_orphan(parsed, project, "design")
            self.assertEqual(cm.exception.reason, "dispatch-log-hmac-mismatch")
            self.assertEqual(cm.exception.violation_class, "authorization")
            # Subclasses the existing auth-error so legacy handlers catch it.
            self.assertIsInstance(cm.exception, GateResultAuthorizationError)

    def test_mismatched_body_raises_tamper_error(self):
        """Rewriting the entry body (without re-signing) also trips the MAC."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="security-engineer",
                gate="design-quality",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T09:00:00+00:00",
            )
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            entry = json.loads(log_path.read_text().strip())
            # Swap the dispatcher identity to simulate an attacker
            # promoting a fast-pass reviewer into the slot.
            entry["dispatcher_agent"] = "wicked-garden:crew:auto-approve"
            log_path.write_text(json.dumps(entry) + "\n")

            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            with self.assertRaises(DispatchLogTamperError):
                check_orphan(parsed, project, "design")


class LegacyFallback(_HmacTestBase):
    def test_legacy_entry_no_hmac_accepts_with_warn(self):
        """Pre-#500 entries (no ``hmac``) downgrade to orphan-only + WARN."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            # Hand-craft a legacy entry (no hmac field). Matches the
            # pre-#500 on-disk shape exactly.
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            legacy = {
                "reviewer": "security-engineer",
                "phase": "design",
                "gate": "design-quality",
                "dispatched_at": "2026-04-19T09:00:00+00:00",
                "dispatcher_agent": "wicked-garden:crew:phase-manager",
                "expected_result_path": "gate-result.json",
                "dispatch_id": "d-legacy",
            }
            log_path.write_text(json.dumps(legacy) + "\n")

            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }

            buf = io.StringIO()
            with redirect_stderr(buf):
                check_orphan(parsed, project, "design")  # no raise

            stderr_text = buf.getvalue()
            self.assertIn("legacy dispatch-log entry", stderr_text)
            self.assertIn("downgrading to orphan-detection", stderr_text)

    def test_legacy_warn_fires_at_most_once_per_process(self):
        """Two legacy verifies → exactly one WARN line (rate-limited)."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            legacy = {
                "reviewer": "r",
                "phase": "design",
                "gate": "g",
                "dispatched_at": "2026-04-19T09:00:00+00:00",
                "dispatcher_agent": "x",
                "expected_result_path": "gate-result.json",
                "dispatch_id": "d-legacy",
            }
            log_path.write_text(
                json.dumps(legacy) + "\n"
                + json.dumps({**legacy, "dispatch_id": "d-legacy-2",
                              "dispatched_at": "2026-04-19T09:30:00+00:00"})
                + "\n"
            )
            parsed = {
                "reviewer": "r",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "g",
            }

            buf = io.StringIO()
            with redirect_stderr(buf):
                check_orphan(parsed, project, "design")
                # Second call — same process. Warn should NOT re-fire.
                check_orphan(parsed, project, "design")

            stderr_text = buf.getvalue()
            self.assertEqual(
                stderr_text.count("legacy dispatch-log entry"),
                1,
                "legacy WARN should be rate-limited to once per process",
            )


class SecretManagement(_HmacTestBase):
    def test_secret_never_appears_in_record(self):
        """Safety net: the secret itself must never land on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="r",
                gate="g",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T09:00:00+00:00",
            )
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            raw = log_path.read_text()
            self.assertNotIn(_FIXED_SECRET, raw)

    def test_canonical_signing_order_insensitive(self):
        """Verify uses sorted JSON — field-order reshuffles still verify."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(
                project, "design",
                reviewer="r",
                gate="g",
                dispatch_id="d-1",
                dispatched_at="2026-04-19T09:00:00+00:00",
            )
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            entry = json.loads(log_path.read_text().strip())
            # Re-serialize with reversed key order — byte-wise different,
            # canonically equivalent.
            reordered = {k: entry[k] for k in reversed(list(entry.keys()))}
            log_path.write_text(json.dumps(reordered) + "\n")

            parsed = {
                "reviewer": "r",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "g",
            }
            # No raise — canonical hash is order-independent.
            check_orphan(parsed, project, "design")


if __name__ == "__main__":
    unittest.main()
