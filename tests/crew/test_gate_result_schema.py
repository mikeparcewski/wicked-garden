"""Unit tests for ``scripts/crew/gate_result_schema.py`` (#479).

Covers:
  - AC-1 enum verdict enforcement
  - AC-2 field length caps (byte + char units)
  - AC-3 required fields + ISO-8601 timestamp
  - AC-4 banned-reviewer-at-load (names + prefixes)
  - Nested recursion (rubric_breakdown.notes cap)
  - Caller-contract regression (design-addendum-1 D-7):
    JSONDecodeError now raises GateResultSchemaError instead of
    silently returning None.

Deterministic (no wall-clock, no random, no sleep). Stdlib-only.
"""

from __future__ import annotations

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

from gate_result_constants import (  # noqa: E402
    MAX_CONDITION_BYTES,
    MAX_REASON_BYTES,
    MAX_REVIEWER_NAME_CHARS,
    MAX_RUBRIC_NOTES_BYTES,
)
from gate_result_schema import (  # noqa: E402
    BANNED_SOURCE_AGENTS,
    GateResultSchemaError,
    validate_gate_result,
)
import phase_manager as pm  # noqa: E402


def _valid_gate_result(**overrides):
    base = {
        "verdict": "APPROVE",
        "reviewer": "security-engineer",
        "recorded_at": "2026-04-19T10:00:00+00:00",
        "reason": "All conditions met.",
        "score": 0.9,
        "min_score": 0.7,
        "conditions": [],
    }
    base.update(overrides)
    return base


class ValidGateResultPasses(unittest.TestCase):
    def test_minimal_valid_payload_passes(self):
        validate_gate_result(_valid_gate_result())

    def test_valid_with_result_alias_passes(self):
        # `result` is an accepted alias for `verdict` (legacy callers).
        payload = _valid_gate_result()
        del payload["verdict"]
        payload["result"] = "CONDITIONAL"
        validate_gate_result(payload)


class EnumEnforcement(unittest.TestCase):
    def test_invalid_verdict_enum_raises(self):
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(_valid_gate_result(verdict="MAYBE"))
        # B-2: reason now carries a hash-prefix tag, not the raw value.
        # Shape: ``invalid-verdict-enum:invalid-enum:verdict:<16-hex>``.
        self.assertTrue(
            cm.exception.reason.startswith("invalid-verdict-enum:invalid-enum:verdict:"),
            f"unexpected reason shape: {cm.exception.reason!r}",
        )
        self.assertNotIn(
            "MAYBE", cm.exception.reason,
            "raw value must not appear in reason (B-2 content-leak fix)",
        )
        self.assertEqual(cm.exception.violation_class, "schema")

    def test_invalid_result_enum_raises(self):
        payload = _valid_gate_result()
        del payload["verdict"]
        payload["result"] = "MAYBE"
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        # B-2: hash-prefix tag, not raw value.
        self.assertTrue(
            cm.exception.reason.startswith("invalid-result-enum:invalid-enum:result:"),
            f"unexpected reason shape: {cm.exception.reason!r}",
        )
        self.assertNotIn("MAYBE", cm.exception.reason)

    def test_missing_both_verdict_and_result_raises(self):
        payload = _valid_gate_result()
        del payload["verdict"]
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertIn("missing-required-field", cm.exception.reason)


class RequiredFields(unittest.TestCase):
    def test_missing_reviewer_raises(self):
        payload = _valid_gate_result()
        del payload["reviewer"]
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertEqual(cm.exception.reason, "missing-required-field:reviewer")

    def test_missing_recorded_at_raises(self):
        payload = _valid_gate_result()
        del payload["recorded_at"]
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertEqual(cm.exception.reason, "missing-required-field:recorded_at")

    def test_invalid_timestamp_raises(self):
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(_valid_gate_result(recorded_at="yesterday"))
        self.assertEqual(cm.exception.reason, "invalid-timestamp:recorded_at")


class FieldSizeCaps(unittest.TestCase):
    def test_reason_oversize_raises(self):
        oversized = "a" * (MAX_REASON_BYTES + 1)
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(_valid_gate_result(reason=oversized))
        self.assertIn("field-oversize:reason", cm.exception.reason)
        # Enforcement value must match the constant, not a magic literal.
        self.assertIn(str(MAX_REASON_BYTES), cm.exception.reason)

    def test_condition_oversize_raises(self):
        oversized = "b" * (MAX_CONDITION_BYTES + 1)
        payload = _valid_gate_result(conditions=[oversized])
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertIn("field-oversize:conditions[0]", cm.exception.reason)
        self.assertIn(str(MAX_CONDITION_BYTES), cm.exception.reason)

    def test_reviewer_over_char_cap_raises(self):
        # Use chars (not bytes) — reviewer cap is measured in chars.
        oversized = "r" * (MAX_REVIEWER_NAME_CHARS + 1)
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(_valid_gate_result(reviewer=oversized))
        self.assertIn("field-oversize:reviewer", cm.exception.reason)

    def test_nested_rubric_notes_cap_enforced(self):
        oversized = "n" * (MAX_RUBRIC_NOTES_BYTES + 1)
        payload = _valid_gate_result(
            rubric_breakdown={
                "user_story": {"score": 2, "notes": oversized},
            }
        )
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertIn("rubric_breakdown.user_story.notes", cm.exception.reason)


class BannedReviewerAtLoad(unittest.TestCase):
    def test_exact_banned_name_rejected(self):
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(_valid_gate_result(reviewer="just-finish-auto"))
        self.assertTrue(
            cm.exception.reason.startswith("banned-reviewer-at-load:"),
            cm.exception.reason,
        )

    def test_auto_approve_prefix_rejected(self):
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(
                _valid_gate_result(reviewer="auto-approve-anything")
            )
        self.assertTrue(
            cm.exception.reason.startswith("banned-reviewer-at-load:"),
            cm.exception.reason,
        )

    def test_self_review_prefix_rejected(self):
        # Design-addendum-1 D-2 union picks up self-review-* prefix.
        with self.assertRaises(GateResultSchemaError):
            validate_gate_result(
                _valid_gate_result(reviewer="self-review-bogus")
            )

    def test_banned_sources_union_non_empty(self):
        # Protects against accidental upstream constant wipes.
        self.assertGreater(len(BANNED_SOURCE_AGENTS), 0)


class LoaderContractShift(unittest.TestCase):
    """Design-addendum-1 D-7 regression guard.

    Previously, ``_load_gate_result`` swallowed ``json.JSONDecodeError``
    and returned ``None`` — which ``approve_phase`` treated as
    "gate not run", silently passing the malformed file. The new
    contract raises ``GateResultSchemaError`` so the caller sees the
    violation explicitly.
    """

    def test_load_gate_result_raises_on_json_decode_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "proj"
            phase_dir = project_dir / "phases" / "design"
            phase_dir.mkdir(parents=True)
            (phase_dir / "gate-result.json").write_text("{not-json")
            with self.assertRaises(GateResultSchemaError) as cm:
                pm._load_gate_result(project_dir, "design")
            self.assertTrue(cm.exception.reason.startswith("malformed-json:"))
            self.assertEqual(cm.exception.violation_class, "schema")

    def test_load_gate_result_returns_none_when_file_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "proj"
            (project_dir / "phases" / "design").mkdir(parents=True)
            self.assertIsNone(pm._load_gate_result(project_dir, "design"))

    def test_load_gate_result_raises_on_schema_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "proj"
            phase_dir = project_dir / "phases" / "design"
            phase_dir.mkdir(parents=True)
            (phase_dir / "gate-result.json").write_text(
                json.dumps({"verdict": "MAYBE", "reviewer": "x",
                            "recorded_at": "2026-04-19T10:00:00+00:00"})
            )
            with self.assertRaises(GateResultSchemaError) as cm:
                pm._load_gate_result(project_dir, "design")
            # B-2: reason no longer carries raw "MAYBE"; hash-prefix tag only.
            self.assertTrue(
                cm.exception.reason.startswith(
                    "invalid-verdict-enum:invalid-enum:verdict:"
                ),
                f"unexpected reason shape: {cm.exception.reason!r}",
            )
            self.assertNotIn("MAYBE", cm.exception.reason)


class SchemaValidationOffFlag(unittest.TestCase):
    """Design-addendum-1 D-1 scoped emergency lever."""

    def test_off_flag_bypasses_validation(self):
        # With the flag, a payload that would normally fail should pass.
        bad = {"verdict": "MAYBE"}
        with patch.dict(os.environ, {
            "WG_GATE_RESULT_SCHEMA_VALIDATION": "off",
            "WG_GATE_RESULT_STRICT_AFTER": "2099-01-01",
        }):
            # No exception.
            validate_gate_result(bad)


class ContentLeakRegression(unittest.TestCase):
    """B-2: attacker-controlled field values MUST NOT appear literally in
    ``GateResultSchemaError.reason`` nor in any audit-log reason passthrough.

    The violation_class + field + sha256 prefix pattern is enforced at the
    raise sites (gate_result_schema.py lines 291 / 307 / 532 pre-fix).
    """

    _SCRIPT_PAYLOAD = "<script>alert(1)</script>"

    def test_banned_reviewer_reason_has_no_raw_script_tag(self):
        from gate_result_schema import _is_banned_reviewer
        # Craft a reviewer value that both looks banned and carries a
        # script tag. ``auto-approve-`` prefix is banned per _event_schema.
        reviewer_value = f"auto-approve-{self._SCRIPT_PAYLOAD}"
        self.assertTrue(_is_banned_reviewer(reviewer_value))

        payload = _valid_gate_result(reviewer=reviewer_value)
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertNotIn(
            self._SCRIPT_PAYLOAD, cm.exception.reason,
            f"raw script tag MUST NOT appear in exception.reason "
            f"(got {cm.exception.reason!r})",
        )
        self.assertNotIn("<script>", cm.exception.reason)
        self.assertNotIn("alert(1)", cm.exception.reason)

    def test_invalid_verdict_reason_has_no_raw_script_tag(self):
        payload = _valid_gate_result(verdict=self._SCRIPT_PAYLOAD)
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertNotIn(self._SCRIPT_PAYLOAD, cm.exception.reason)
        self.assertNotIn("<script>", cm.exception.reason)

    def test_invalid_rigor_tier_reason_has_no_raw_script_tag(self):
        payload = _valid_gate_result(rigor_tier=self._SCRIPT_PAYLOAD)
        with self.assertRaises(GateResultSchemaError) as cm:
            validate_gate_result(payload)
        self.assertNotIn(self._SCRIPT_PAYLOAD, cm.exception.reason)

    def test_audit_log_passthrough_of_reason_is_capped(self):
        """B-2: ``gate_ingest_audit.append_audit_entry`` must cap /
        sanitize the reason it writes. Upstream already hash-prefixes;
        this is belt-and-suspenders — a future-caller regression that
        hands us a raw-content reason must still not leak literally
        onto disk (256-char cap).
        """
        from gate_ingest_audit import append_audit_entry
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "proj"
            (project_dir / "phases" / "build").mkdir(parents=True)
            huge_injection = self._SCRIPT_PAYLOAD + ("X" * 1024)
            append_audit_entry(
                project_dir, "build",
                event="schema_violation",
                reason=huge_injection,
                offending_field="reviewer",
                offending_value=huge_injection,
                raw_bytes=b"{}",
            )
            audit_path = (
                project_dir / "phases" / "build" / "gate-ingest-audit.jsonl"
            )
            text = audit_path.read_text(encoding="utf-8")
            record = json.loads(text.strip().splitlines()[0])
            # Reason must be capped to a safe upper bound (256 chars).
            self.assertLessEqual(len(record["reason"]), 256)
            # Offending VALUE is hashed (not passed through).
            self.assertTrue(
                record["violation_snippet_hash"].startswith("sha256:"),
            )
            # ``record["violation_snippet_hash"]`` must NOT contain the
            # raw payload characters.
            self.assertNotIn("<script>", record["violation_snippet_hash"])


if __name__ == "__main__":
    unittest.main()
