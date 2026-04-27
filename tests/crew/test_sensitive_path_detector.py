"""Tests for ``scripts/crew/detectors/sensitive_path.py``.

PR-2 of the steering detector epic (#679). Covers:

  * Each category fires exactly one event with the right action and category
    (auth, payments, migration, secrets).
  * Brainstorm-mandated extension filter — README/docs inside a sensitive
    directory do NOT trigger events.
  * Test files inside sensitive directories DO trigger (they reference the
    sensitive code paths).
  * Multiple matches, empty input, custom-pattern override.
  * Every emitted payload passes the PR-1 schema validator.
  * Bus emit failure is handled gracefully (no exceptions, count = 0).
  * Input validation: empty session_id / project_slug → ValueError.
  * Extension filter is case-insensitive (e.g. ``.PY`` still matches).
  * Path normalization handles backslashes / leading ``./``.

Pure stdlib + unittest. No external fixtures. Subprocess mocking is done
via ``unittest.mock.patch`` against the module's ``subprocess.run`` reference.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from crew.detectors import sensitive_path as detector  # noqa: E402
from crew.steering_event_schema import validate_payload  # noqa: E402


_FIXED_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _detect(paths, **overrides):
    """Helper — call the detector with sensible defaults for tests."""
    kwargs = {
        "session_id": "sess-001",
        "project_slug": "demo",
        "now": _FIXED_NOW,
    }
    kwargs.update(overrides)
    return detector.detect_sensitive_path_touch(paths, **kwargs)


# ---------------------------------------------------------------------------
# Per-category positive cases
# ---------------------------------------------------------------------------

class CategoryDetection(unittest.TestCase):

    def test_auth_path_fires_force_full_rigor(self):
        events = _detect(["src/auth/login.py"])
        self.assertEqual(len(events), 1, events)
        ev = events[0]
        self.assertEqual(ev["evidence"]["category"], "auth")
        self.assertEqual(ev["recommended_action"], "force-full-rigor")
        self.assertEqual(ev["evidence"]["file"], "src/auth/login.py")
        self.assertEqual(ev["detector"], "sensitive-path")

    def test_payments_path_fires_force_full_rigor(self):
        events = _detect(["api/payments/charge.go"])
        self.assertEqual(len(events), 1, events)
        ev = events[0]
        self.assertEqual(ev["evidence"]["category"], "payments")
        self.assertEqual(ev["recommended_action"], "force-full-rigor")

    def test_migration_path_fires_regen_test_strategy(self):
        events = _detect(["db/migrations/001_users.sql"])
        self.assertEqual(len(events), 1, events)
        ev = events[0]
        self.assertEqual(ev["evidence"]["category"], "migration")
        self.assertEqual(ev["recommended_action"], "regen-test-strategy")

    def test_secrets_path_fires_require_council_review(self):
        events = _detect(["config/secrets.env"])
        self.assertEqual(len(events), 1, events)
        ev = events[0]
        self.assertEqual(ev["evidence"]["category"], "secrets")
        self.assertEqual(ev["recommended_action"], "require-council-review")

    def test_credential_filename_fires_secrets(self):
        # `credential` substring should match `**/*credential*` glob.
        events = _detect(["lib/aws_credential_loader.py"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["category"], "secrets")

    def test_token_filename_fires_secrets(self):
        events = _detect(["src/refresh_token.ts"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["category"], "secrets")

    def test_authentication_directory_matches_auth(self):
        events = _detect(["src/authentication/oauth.py"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["category"], "auth")


# ---------------------------------------------------------------------------
# Extension filter (the brainstorm-mandated guardrail)
# ---------------------------------------------------------------------------

class ExtensionFilter(unittest.TestCase):

    def test_readme_inside_auth_does_not_trigger(self):
        events = _detect(["src/auth/README.md"])
        self.assertEqual(events, [])

    def test_readme_at_repo_root_does_not_trigger(self):
        events = _detect(["README.md"])
        self.assertEqual(events, [])

    def test_doc_inside_payments_does_not_trigger(self):
        events = _detect(["docs/payments/overview.md"])
        self.assertEqual(events, [])

    def test_test_file_inside_auth_DOES_trigger(self):
        # Tests reference the sensitive code paths — they should escalate too.
        events = _detect(["tests/auth/test_login.py"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["category"], "auth")

    def test_extension_match_is_case_insensitive(self):
        events = _detect(["src/auth/Login.PY"])
        self.assertEqual(len(events), 1, events)


# ---------------------------------------------------------------------------
# Cardinality, empty input, custom patterns
# ---------------------------------------------------------------------------

class CardinalityAndOverrides(unittest.TestCase):

    def test_multiple_paths_produce_multiple_events(self):
        events = _detect([
            "src/auth/login.py",
            "api/billing/invoice.ts",
            "db/migrations/002.sql",
            "README.md",  # should be filtered out
        ])
        # 3 sensitive paths -> 3 events; README dropped by extension filter.
        self.assertEqual(len(events), 3, events)
        categories = sorted(ev["evidence"]["category"] for ev in events)
        self.assertEqual(categories, ["auth", "migration", "payments"])

    def test_empty_path_list_returns_empty(self):
        self.assertEqual(_detect([]), [])

    def test_blank_paths_are_skipped(self):
        events = _detect(["", "   ", "src/auth/login.py"])
        self.assertEqual(len(events), 1, events)

    def test_custom_patterns_override_defaults(self):
        custom = [
            {"glob": "**/admin/**", "extensions": [".py"], "category": "auth"},
        ]
        # auth/login.py should NOT match the override patterns.
        no_default = _detect(["src/auth/login.py"], patterns=custom)
        self.assertEqual(no_default, [])
        # admin/whatever.py SHOULD match.
        custom_hit = _detect(["src/admin/users.py"], patterns=custom)
        self.assertEqual(len(custom_hit), 1, custom_hit)
        self.assertEqual(custom_hit[0]["evidence"]["category"], "auth")

    def test_path_with_backslash_is_normalized(self):
        events = _detect(["src\\auth\\login.py"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["file"], "src/auth/login.py")

    def test_leading_dot_slash_is_normalized(self):
        events = _detect(["./src/auth/login.py"])
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["evidence"]["file"], "src/auth/login.py")


# ---------------------------------------------------------------------------
# Schema integration (#681)
# ---------------------------------------------------------------------------

class SchemaIntegration(unittest.TestCase):
    """Every payload the detector returns MUST pass the PR-1 schema validator."""

    def test_every_default_payload_passes_schema(self):
        events = _detect([
            "src/auth/login.py",
            "api/payments/charge.go",
            "db/migrations/001.sql",
            "config/secrets.env",
            "src/refresh_token.ts",
            "src/authentication/oauth.py",
        ])
        self.assertGreater(len(events), 0, "expected at least one event")
        for ev in events:
            errors, _warnings = validate_payload(detector.EVENT_TYPE, ev)
            self.assertEqual(
                errors, [],
                f"payload failed schema validation: {ev} errors={errors}",
            )

    def test_payload_event_type_is_escalated(self):
        # The detector is for force-rigor signals — must be `escalated`,
        # not `advised`.
        self.assertEqual(detector.EVENT_TYPE, "wicked.steer.escalated")

    def test_payload_subdomain_is_correct(self):
        self.assertEqual(detector.EVENT_SUBDOMAIN, "crew.detector.sensitive-path")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class InputValidation(unittest.TestCase):

    def test_empty_session_id_raises(self):
        with self.assertRaises(ValueError):
            detector.detect_sensitive_path_touch(
                ["src/auth/login.py"], session_id="", project_slug="demo",
            )

    def test_whitespace_session_id_raises(self):
        with self.assertRaises(ValueError):
            detector.detect_sensitive_path_touch(
                ["src/auth/login.py"], session_id="   ", project_slug="demo",
            )

    def test_empty_project_slug_raises(self):
        with self.assertRaises(ValueError):
            detector.detect_sensitive_path_touch(
                ["src/auth/login.py"], session_id="s1", project_slug="",
            )

    def test_custom_pattern_missing_required_key_raises(self):
        with self.assertRaises(ValueError):
            detector.detect_sensitive_path_touch(
                ["x.py"],
                session_id="s1", project_slug="demo",
                patterns=[{"glob": "**/x.py", "extensions": [".py"]}],  # no category
            )


# ---------------------------------------------------------------------------
# Emitter — bus interaction
# ---------------------------------------------------------------------------

class EmitterBehavior(unittest.TestCase):

    def test_empty_payloads_returns_zero(self):
        # Doesn't even need to consult the bus.
        self.assertEqual(detector.emit_sensitive_path_events([]), 0)

    def test_bus_unreachable_fails_open(self):
        events = _detect(["src/auth/login.py"])
        with mock.patch.object(detector, "_resolve_bus_command", return_value=None):
            count = detector.emit_sensitive_path_events(events)
        self.assertEqual(count, 0, "bus unreachable must return 0, not raise")

    def test_emit_subprocess_failure_is_handled(self):
        events = _detect(["src/auth/login.py"])

        class _FakeProc:
            returncode = 1
            stderr = "bus offline"

        with mock.patch.object(
            detector, "_resolve_bus_command", return_value=["wicked-bus"]
        ), mock.patch.object(
            detector.subprocess, "run", return_value=_FakeProc()
        ):
            count = detector.emit_sensitive_path_events(events)

        self.assertEqual(count, 0, "non-zero returncode must count as failure")

    def test_emit_subprocess_timeout_is_handled(self):
        events = _detect(["src/auth/login.py"])

        def _raise(*_args, **_kwargs):
            raise detector.subprocess.TimeoutExpired(cmd="wicked-bus", timeout=5)

        with mock.patch.object(
            detector, "_resolve_bus_command", return_value=["wicked-bus"]
        ), mock.patch.object(
            detector.subprocess, "run", side_effect=_raise
        ):
            count = detector.emit_sensitive_path_events(events)

        self.assertEqual(count, 0, "subprocess timeout must count as failure, not raise")

    def test_successful_emit_increments_count(self):
        events = _detect(["src/auth/login.py", "api/payments/charge.go"])

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            detector, "_resolve_bus_command", return_value=["wicked-bus"]
        ), mock.patch.object(
            detector.subprocess, "run", return_value=_OkProc()
        ) as run_mock:
            count = detector.emit_sensitive_path_events(events)

        self.assertEqual(count, 2)
        self.assertEqual(run_mock.call_count, 2)
        # Verify the wired event_type/domain/subdomain made it to argv.
        first_argv = run_mock.call_args_list[0][0][0]
        self.assertIn("--type", first_argv)
        self.assertIn("wicked.steer.escalated", first_argv)
        self.assertIn("--subdomain", first_argv)
        self.assertIn("crew.detector.sensitive-path", first_argv)

    def test_emitter_drops_invalid_payloads_without_emitting(self):
        # Hand-crafted bad payload (missing session_id) — the emitter must
        # re-validate at the bus boundary and drop it.
        bad = {
            "detector": "sensitive-path",
            "signal": "x",
            "threshold": {},
            "recommended_action": "force-full-rigor",
            "evidence": {"x": 1},
            # missing session_id, project_slug, timestamp
        }

        class _OkProc:
            returncode = 0
            stderr = ""

        with mock.patch.object(
            detector, "_resolve_bus_command", return_value=["wicked-bus"]
        ), mock.patch.object(
            detector.subprocess, "run", return_value=_OkProc()
        ) as run_mock:
            count = detector.emit_sensitive_path_events([bad])

        self.assertEqual(count, 0, "invalid payload must not be emitted")
        run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Glob -> regex translation
# ---------------------------------------------------------------------------

class GlobTranslation(unittest.TestCase):
    """Direct coverage of the regex translator — easier to debug than via detect."""

    def test_double_star_matches_zero_segments(self):
        rx = detector._glob_to_regex("**/auth/**")
        self.assertTrue(rx.match("auth/login.py"))

    def test_double_star_matches_many_segments(self):
        rx = detector._glob_to_regex("**/auth/**")
        self.assertTrue(rx.match("a/b/c/auth/x/y.py"))

    def test_glob_matches_full_path_only(self):
        # Anchored — partial dir name shouldn't match.
        rx = detector._glob_to_regex("**/auth/**")
        # 'authy' is not 'auth'
        self.assertFalse(rx.match("src/authy/login.py"))

    def test_single_star_does_not_cross_separator(self):
        rx = detector._glob_to_regex("**/payment*/**")
        self.assertTrue(rx.match("api/payments/charge.go"))
        self.assertTrue(rx.match("api/payment_intents/x.py"))

    def test_secret_substring_glob(self):
        rx = detector._glob_to_regex("**/*secret*")
        self.assertTrue(rx.match("config/secrets.env"))
        self.assertTrue(rx.match("a/b/my_secret_thing.py"))


# ---------------------------------------------------------------------------
# Determinism — fixed `now` produces stable timestamps
# ---------------------------------------------------------------------------

class DeterminismFixedNow(unittest.TestCase):

    def test_fixed_now_produces_fixed_timestamp(self):
        events = _detect(["src/auth/login.py"])
        self.assertEqual(events[0]["timestamp"], "2026-04-27T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
