"""tests/test_yolo_revoke_attribution.py — Issue #581 revoke-attribution.

Live wicked-bus data showed ``wicked.crew.yolo_revoked`` firing on ~49% of
gate decisions (111 revokes / 225 decisions). Before tuning thresholds we
need **attribution**: which trigger fires the revoke most often? This test
suite locks in the Issue #581 contract:

* Every value in :data:`scripts.crew.yolo_constants.VALID_REVOKE_REASONS`
  is accepted by the validator.
* Any value outside the taxonomy is rejected.
* ``reason == "other"`` without a non-empty ``revoke_note`` is rejected
  (the escape hatch must name the instrumentation gap).
* ``yolo-audit.jsonl`` lines emitted on revoke carry ``revoke_reason``.
* ``wicked.crew.yolo_revoked`` bus payloads carry ``revoke_reason``.

Stdlib-only (T-rules: stdlib-only + deterministic). No sleep-based sync
(T2). Each test asserts a single behaviour (T4) with a descriptive name
(T5). Docstrings cite Issue #581 (T6 provenance).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Root conftest already normalises sys.path; belt-and-braces for direct
# invocation (`python3 -m unittest tests/test_yolo_revoke_attribution.py`).
for p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import phase_manager  # noqa: E402
from crew.yolo_constants import (  # noqa: E402
    VALID_REVOKE_REASONS,
    validate_revoke_reason,
)


# ---------------------------------------------------------------------------
# Taxonomy (Part A — Issue #581)
# ---------------------------------------------------------------------------


class TestTaxonomyMembership(unittest.TestCase):
    """Issue #581: the taxonomy is a fixed, immutable contract."""

    def test_taxonomy_is_frozenset(self):
        """Issue #581 spec: ``VALID_REVOKE_REASONS`` is a frozenset."""
        self.assertIsInstance(VALID_REVOKE_REASONS, frozenset)

    def test_taxonomy_contains_all_seven_specified_values(self):
        """Issue #581 spec: taxonomy is exactly the seven listed values."""
        expected = {
            "gate.conditional",
            "gate.reject",
            "scope.change",
            "retier.up",
            "cooldown.hit",
            "user.override",
            "other",
        }
        self.assertEqual(VALID_REVOKE_REASONS, expected)


class TestValidatorAcceptsTaxonomy(unittest.TestCase):
    """Issue #581: every taxonomy value is accepted by the validator."""

    def test_gate_conditional_is_accepted(self):
        """Issue #581: ``gate.conditional`` is a valid revoke reason."""
        # Validator returns None on success — we assert it does not raise.
        self.assertIsNone(validate_revoke_reason("gate.conditional"))

    def test_gate_reject_is_accepted(self):
        """Issue #581: ``gate.reject`` is a valid revoke reason."""
        self.assertIsNone(validate_revoke_reason("gate.reject"))

    def test_scope_change_is_accepted(self):
        """Issue #581: ``scope.change`` is a valid revoke reason."""
        self.assertIsNone(validate_revoke_reason("scope.change"))

    def test_retier_up_is_accepted(self):
        """Issue #581: ``retier.up`` is a valid revoke reason."""
        self.assertIsNone(validate_revoke_reason("retier.up"))

    def test_cooldown_hit_is_accepted(self):
        """Issue #581: ``cooldown.hit`` is a valid revoke reason."""
        self.assertIsNone(validate_revoke_reason("cooldown.hit"))

    def test_user_override_is_accepted(self):
        """Issue #581: ``user.override`` is a valid revoke reason."""
        self.assertIsNone(validate_revoke_reason("user.override"))

    def test_other_with_non_empty_note_is_accepted(self):
        """Issue #581: ``other`` is valid when paired with a note."""
        self.assertIsNone(
            validate_revoke_reason("other", note="unattributed: legacy path")
        )


class TestValidatorRejectsInvalid(unittest.TestCase):
    """Issue #581: invalid reasons are rejected (fixed taxonomy contract)."""

    def test_unknown_reason_raises_value_error(self):
        """Issue #581: unknown tag raises ValueError naming the tag."""
        with self.assertRaises(ValueError) as ctx:
            validate_revoke_reason("made.up.reason")
        self.assertIn("invalid-revoke-reason", str(ctx.exception))

    def test_empty_string_reason_raises_value_error(self):
        """Issue #581: empty string is not in the taxonomy -> rejected."""
        with self.assertRaises(ValueError):
            validate_revoke_reason("")

    def test_misspelled_reason_raises_value_error(self):
        """Issue #581: common typo (missing dot) is rejected."""
        with self.assertRaises(ValueError):
            validate_revoke_reason("scope_change")


class TestOtherRequiresNote(unittest.TestCase):
    """Issue #581: ``other`` without a note fails — forces the gap to be named."""

    def test_other_without_note_raises_value_error(self):
        """Issue #581: ``other`` + no note fails the validator."""
        with self.assertRaises(ValueError) as ctx:
            validate_revoke_reason("other")
        self.assertIn("revoke-reason-other-requires-note", str(ctx.exception))

    def test_other_with_none_note_raises_value_error(self):
        """Issue #581: explicit ``None`` note is treated as missing."""
        with self.assertRaises(ValueError):
            validate_revoke_reason("other", note=None)

    def test_other_with_whitespace_note_raises_value_error(self):
        """Issue #581: whitespace-only note does not satisfy the gap-naming rule."""
        with self.assertRaises(ValueError):
            validate_revoke_reason("other", note="   \t\n  ")


# ---------------------------------------------------------------------------
# Audit log (Part B — Issue #581)
# ---------------------------------------------------------------------------


def _state_with_yolo(name: str = "p") -> phase_manager.ProjectState:
    """Build a minimal yolo-approved ProjectState for revoke tests."""
    return phase_manager.ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-23T00:00:00Z",
        phase_plan=["clarify", "design", "build", "review"],
        phases={},
        extras={"yolo_approved_by_user": True, "rigor_tier": "full"},
    )


def _read_audit_lines(project_dir: Path) -> list[dict]:
    """Return parsed ``yolo-audit.jsonl`` records (newest-last)."""
    path = project_dir / "yolo-audit.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestAuditLogCarriesRevokeReason(unittest.TestCase):
    """Issue #581 Part B — ``yolo-audit.jsonl`` carries ``revoke_reason``."""

    def test_scope_change_revoke_stamps_reason_in_audit(self):
        """Issue #581: augment mutation -> audit line has ``revoke_reason='scope.change'``."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            phase_manager._apply_scope_increase_revoke(
                state,
                plan_mutations=[{"op": "augment", "detail": "added coverage phase"}],
                project_dir=project_dir,
                trigger="execute",
            )
            lines = _read_audit_lines(project_dir)
            revoke_records = [ln for ln in lines if ln.get("event") == "revoked"]
            self.assertEqual(len(revoke_records), 1)
            self.assertEqual(revoke_records[0].get("revoke_reason"), "scope.change")

    def test_retier_up_revoke_stamps_reason_in_audit(self):
        """Issue #581: re_tier->full mutation -> audit line has ``revoke_reason='retier.up'``."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            phase_manager._apply_scope_increase_revoke(
                state,
                plan_mutations=[
                    {"op": "re_tier", "new_rigor_tier": "full"},
                ],
                project_dir=project_dir,
                trigger="execute",
            )
            lines = _read_audit_lines(project_dir)
            revoke_records = [ln for ln in lines if ln.get("event") == "revoked"]
            self.assertEqual(len(revoke_records), 1)
            self.assertEqual(revoke_records[0].get("revoke_reason"), "retier.up")

    def test_retier_up_wins_over_augment_when_both_present(self):
        """Issue #581: retier.up is the stronger signal -> wins when batched with augment."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            phase_manager._apply_scope_increase_revoke(
                state,
                plan_mutations=[
                    {"op": "augment"},
                    {"op": "re_tier", "new_rigor_tier": "full"},
                ],
                project_dir=project_dir,
                trigger="execute",
            )
            lines = _read_audit_lines(project_dir)
            revoke_records = [ln for ln in lines if ln.get("event") == "revoked"]
            self.assertEqual(revoke_records[0].get("revoke_reason"), "retier.up")

    def test_user_cli_revoke_stamps_user_override_in_audit(self):
        """Issue #581: CLI revoke -> audit line has ``revoke_reason='user.override'``."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                phase_manager.yolo_action("p", "revoke", reason="user changed mind")
            lines = _read_audit_lines(project_dir)
            revoke_records = [ln for ln in lines if ln.get("event") == "revoked"]
            self.assertEqual(len(revoke_records), 1)
            self.assertEqual(revoke_records[0].get("revoke_reason"), "user.override")


# ---------------------------------------------------------------------------
# Bus payload (Part A — Issue #581)
# ---------------------------------------------------------------------------


class TestBusPayloadCarriesRevokeReason(unittest.TestCase):
    """Issue #581 Part A — ``wicked.crew.yolo_revoked`` payload carries the reason."""

    def _capture_bus_emit(self):
        """Patch ``_bus.emit_event`` and return the list it appends to.

        The revoke helper late-imports ``_bus``; patching the module-level
        function is the minimally-invasive way to observe emit calls
        without reaching into the bus internals.
        """
        import _bus  # type: ignore
        captured: list[tuple[str, dict]] = []

        def fake_emit(event_type, payload, *args, **kwargs):
            captured.append((event_type, payload))

        return _bus, fake_emit, captured

    def test_scope_change_bus_payload_includes_revoke_reason(self):
        """Issue #581: augment -> bus payload has ``revoke_reason='scope.change'``."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            bus_mod, fake_emit, captured = self._capture_bus_emit()
            with patch.object(bus_mod, "emit_event", fake_emit):
                phase_manager._apply_scope_increase_revoke(
                    state,
                    plan_mutations=[{"op": "augment"}],
                    project_dir=project_dir,
                    trigger="approve",
                )
            revoke_emits = [
                p for (event, p) in captured
                if event == "wicked.crew.yolo_revoked"
            ]
            self.assertEqual(len(revoke_emits), 1)
            self.assertEqual(revoke_emits[0].get("revoke_reason"), "scope.change")

    def test_retier_up_bus_payload_includes_revoke_reason(self):
        """Issue #581: re_tier->full -> bus payload has ``revoke_reason='retier.up'``."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            bus_mod, fake_emit, captured = self._capture_bus_emit()
            with patch.object(bus_mod, "emit_event", fake_emit):
                phase_manager._apply_scope_increase_revoke(
                    state,
                    plan_mutations=[
                        {"op": "re_tier", "new_rigor_tier": "full"},
                    ],
                    project_dir=project_dir,
                    trigger="execute",
                )
            revoke_emits = [
                p for (event, p) in captured
                if event == "wicked.crew.yolo_revoked"
            ]
            self.assertEqual(len(revoke_emits), 1)
            self.assertEqual(revoke_emits[0].get("revoke_reason"), "retier.up")

    def test_no_revoke_means_no_bus_emit(self):
        """Issue #581 Part C — we did not change when revokes fire.

        A mutation batch with no scope-increase/retier-up must NOT emit a
        revoke bus event. This guards against accidental behavior drift.
        """
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state_with_yolo()
            bus_mod, fake_emit, captured = self._capture_bus_emit()
            with patch.object(bus_mod, "emit_event", fake_emit):
                fired = phase_manager._apply_scope_increase_revoke(
                    state,
                    plan_mutations=[{"op": "refine", "detail": "minor wording"}],
                    project_dir=project_dir,
                    trigger="execute",
                )
            self.assertFalse(fired)
            self.assertEqual(captured, [])


# ---------------------------------------------------------------------------
# Append-audit contract — direct helper exercise (Part B — Issue #581)
# ---------------------------------------------------------------------------


class TestAppendYoloAuditAcceptsAttribution(unittest.TestCase):
    """Issue #581: ``_append_yolo_audit`` records attribution when supplied."""

    def test_revoke_reason_kwarg_lands_in_record(self):
        """Issue #581: ``revoke_reason='cooldown.hit'`` appears in the JSON line."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            phase_manager._append_yolo_audit(
                project_dir,
                event="revoked",
                reason="synthetic test",
                prior_value=True,
                new_value=False,
                revoke_reason="cooldown.hit",
            )
            lines = _read_audit_lines(project_dir)
            self.assertEqual(lines[-1].get("revoke_reason"), "cooldown.hit")

    def test_revoke_note_kwarg_lands_in_record(self):
        """Issue #581: ``revoke_note`` text survives the round-trip."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            phase_manager._append_yolo_audit(
                project_dir,
                event="revoked",
                reason="synthetic test",
                prior_value=True,
                new_value=False,
                revoke_reason="other",
                revoke_note="unattributed: legacy dispatcher path",
            )
            lines = _read_audit_lines(project_dir)
            self.assertEqual(
                lines[-1].get("revoke_note"),
                "unattributed: legacy dispatcher path",
            )

    def test_non_revoke_events_still_work_without_attribution(self):
        """Issue #581 Part C — non-revoke audit writes still succeed unchanged.

        Granted + auto-accepted + user-override-conditional events do not
        carry attribution, and the helper must stay tolerant.
        """
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            phase_manager._append_yolo_audit(
                project_dir,
                event="granted",
                reason="user-granted",
                prior_value=False,
                new_value=True,
            )
            lines = _read_audit_lines(project_dir)
            self.assertEqual(len(lines), 1)
            self.assertNotIn("revoke_reason", lines[-1])


if __name__ == "__main__":
    unittest.main()
