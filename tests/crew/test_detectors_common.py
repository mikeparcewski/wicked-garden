"""Tests for ``scripts/crew/detectors/_common.py``.

PR-4 of the steering detector epic (#679). Covers the shared helpers all
four PR-4 detectors (and PR-2's sensitive-path) lean on:

  * ``resolve_bus_command`` — direct binary > npx-with-probe > None
  * ``emit_validated_payloads`` — schema-validate-then-emit, fail-open
  * ``utc_iso8601`` — deterministic timestamp formatting
  * ``require_non_empty_string`` — input guard
  * ``build_standard_arg_parser`` — standard CLI surface

Pure stdlib + unittest. Subprocess mocking via ``unittest.mock.patch``
against the module's ``subprocess.run`` reference.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.detectors import _common as common  # noqa: E402


# ---------------------------------------------------------------------------
# resolve_bus_command
# ---------------------------------------------------------------------------

class ResolveBusCommand(unittest.TestCase):

    def test_direct_binary_is_preferred(self):
        with mock.patch.object(
            common.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/wicked-bus" if name == "wicked-bus" else None,
        ):
            cmd = common.resolve_bus_command()
        self.assertEqual(cmd, ["/usr/local/bin/wicked-bus"])

    def test_no_binary_no_npx_returns_none(self):
        with mock.patch.object(common.shutil, "which", return_value=None):
            cmd = common.resolve_bus_command()
        self.assertIsNone(cmd)

    def test_npx_with_successful_probe_returns_npx_prefix(self):
        which_results = {"wicked-bus": None, "npx": "/usr/local/bin/npx"}

        class _OkProbe:
            returncode = 0
            stderr = ""
            stdout = "{}"

        with mock.patch.object(
            common.shutil, "which", side_effect=lambda n: which_results.get(n),
        ), mock.patch.object(
            common.subprocess, "run", return_value=_OkProbe(),
        ):
            cmd = common.resolve_bus_command()
        self.assertEqual(cmd, ["/usr/local/bin/npx", "wicked-bus"])

    def test_npx_with_failing_probe_returns_none(self):
        which_results = {"wicked-bus": None, "npx": "/usr/local/bin/npx"}

        class _FailProbe:
            returncode = 1
            stderr = "boom"
            stdout = ""

        with mock.patch.object(
            common.shutil, "which", side_effect=lambda n: which_results.get(n),
        ), mock.patch.object(
            common.subprocess, "run", return_value=_FailProbe(),
        ):
            cmd = common.resolve_bus_command()
        self.assertIsNone(cmd)

    def test_npx_probe_timeout_returns_none(self):
        which_results = {"wicked-bus": None, "npx": "/usr/local/bin/npx"}

        def _raise(*_a, **_kw):
            raise common.subprocess.TimeoutExpired(cmd="npx", timeout=5)

        with mock.patch.object(
            common.shutil, "which", side_effect=lambda n: which_results.get(n),
        ), mock.patch.object(
            common.subprocess, "run", side_effect=_raise,
        ):
            cmd = common.resolve_bus_command()
        self.assertIsNone(cmd)


# ---------------------------------------------------------------------------
# emit_validated_payloads
# ---------------------------------------------------------------------------

_VALID_PAYLOAD: dict = {
    "detector": "blast-radius",
    "signal": "x",
    "threshold": {"k": 1},
    "recommended_action": "force-full-rigor",
    "evidence": {"k": 1},
    "session_id": "s1",
    "project_slug": "demo",
    "timestamp": "2026-04-27T10:00:00Z",
}


class EmitValidatedPayloads(unittest.TestCase):

    def test_empty_input_returns_zero_no_subprocess(self):
        with mock.patch.object(common.subprocess, "run") as run_mock:
            count = common.emit_validated_payloads(
                [],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
            )
        self.assertEqual(count, 0)
        run_mock.assert_not_called()

    def test_bus_unreachable_fails_open(self):
        with mock.patch.object(common, "resolve_bus_command", return_value=None):
            count = common.emit_validated_payloads(
                [dict(_VALID_PAYLOAD)],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
            )
        self.assertEqual(count, 0, "must fail-open, not raise")

    def test_invalid_payload_dropped_not_emitted(self):
        bad = {"detector": "blast-radius"}  # missing required fields

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = common.emit_validated_payloads(
                [bad],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
                bus_cmd=["wicked-bus"],
            )
        self.assertEqual(count, 0, "invalid payload must drop")
        run_mock.assert_not_called()

    def test_subprocess_returncode_nonzero_counts_zero(self):
        class _FailProc:
            returncode = 1
            stderr = "down"

        with mock.patch.object(
            common.subprocess, "run", return_value=_FailProc(),
        ):
            count = common.emit_validated_payloads(
                [dict(_VALID_PAYLOAD)],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
                bus_cmd=["wicked-bus"],
            )
        self.assertEqual(count, 0)

    def test_subprocess_timeout_counts_zero(self):
        def _raise(*_a, **_kw):
            raise common.subprocess.TimeoutExpired(cmd="wicked-bus", timeout=10)

        with mock.patch.object(common.subprocess, "run", side_effect=_raise):
            count = common.emit_validated_payloads(
                [dict(_VALID_PAYLOAD)],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
                bus_cmd=["wicked-bus"],
            )
        self.assertEqual(count, 0)

    def test_successful_emit_returns_count(self):
        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            common.subprocess, "run", return_value=_OkProc(),
        ) as run_mock:
            count = common.emit_validated_payloads(
                [dict(_VALID_PAYLOAD), dict(_VALID_PAYLOAD)],
                event_type="wicked.steer.escalated",
                subdomain="crew.detector.blast-radius",
                bus_cmd=["wicked-bus"],
            )
        self.assertEqual(count, 2)
        self.assertEqual(run_mock.call_count, 2)
        # Confirm the wired event_type/domain/subdomain landed on argv.
        argv = run_mock.call_args_list[0][0][0]
        self.assertIn("--type", argv)
        self.assertIn("wicked.steer.escalated", argv)
        self.assertIn("--subdomain", argv)
        self.assertIn("crew.detector.blast-radius", argv)
        self.assertIn("--domain", argv)
        self.assertIn(common.EVENT_DOMAIN, argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class HelperFunctions(unittest.TestCase):

    def test_utc_iso8601_with_fixed_now(self):
        ts = common.utc_iso8601(datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(ts, "2026-04-27T10:00:00Z")

    def test_utc_iso8601_default_now_is_well_formed(self):
        ts = common.utc_iso8601()
        self.assertTrue(ts.endswith("Z"))
        self.assertEqual(len(ts), 20)  # YYYY-MM-DDTHH:MM:SSZ

    def test_require_non_empty_string_passes(self):
        self.assertEqual(common.require_non_empty_string("x", "field"), "x")

    def test_require_non_empty_string_rejects_empty(self):
        with self.assertRaises(ValueError):
            common.require_non_empty_string("", "field")

    def test_require_non_empty_string_rejects_whitespace(self):
        with self.assertRaises(ValueError):
            common.require_non_empty_string("   ", "field")

    def test_require_non_empty_string_rejects_non_string(self):
        with self.assertRaises(ValueError):
            common.require_non_empty_string(42, "field")

    def test_build_standard_arg_parser_has_required_options(self):
        parser = common.build_standard_arg_parser("test", "test desc")
        # Required args must be present — parsing without them errors.
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        ns = parser.parse_args([
            "--session-id", "s1", "--project-slug", "demo",
        ])
        self.assertEqual(ns.session_id, "s1")
        self.assertEqual(ns.project_slug, "demo")
        self.assertFalse(ns.dry_run)

    def test_build_standard_arg_parser_dry_run_flag(self):
        parser = common.build_standard_arg_parser("test", "test desc")
        ns = parser.parse_args([
            "--session-id", "s1", "--project-slug", "demo", "--dry-run",
        ])
        self.assertTrue(ns.dry_run)


if __name__ == "__main__":
    unittest.main()
