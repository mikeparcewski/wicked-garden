#!/usr/bin/env python3
"""tests/crew/test_yolo_guardrails.py — #470 full-rigor yolo guardrails.

Covers the three guardrails layered onto `phase_manager.yolo_action()`:

  1. Justification required (>= 40 chars) at full rigor.
  2. 5-minute cooldown after an auto-revoke (scope-increase trigger).
  3. Second-persona review sentinel must exist with non-trivial content.

Also verifies that:
  - Lower rigor tiers (standard/minimal) are NOT subject to the guardrails.
  - The audit line carries the justification in a structured `justification`
    field when granted at full rigor.
  - The cooldown helper parses both `Z`-suffix and offset ISO timestamps.

Stdlib-only; no sleep-based sync (T2); single-assertion focus (T4);
descriptive names (T5).
"""

import json
import sys as _sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
if str(_SCRIPTS / "crew") not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS / "crew"))

import phase_manager  # noqa: E402


# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------


def _state(name: str, *, rigor_tier: str = "full", yolo: bool = False):
    """Build a minimal ProjectState at the requested rigor tier."""
    extras = {"rigor_tier": rigor_tier}
    if yolo:
        extras["yolo_approved_by_user"] = True
    return phase_manager.ProjectState(
        name=name,
        current_phase="build",
        created_at="2026-04-19T10:00:00Z",
        phase_plan=["clarify", "design", "build", "review"],
        phases={},
        extras=extras,
    )


def _stage_sentinel(project_dir: Path, *, content_bytes: int = 200) -> Path:
    """Create the second-persona review sentinel with `content_bytes` of
    non-whitespace payload. Returns the sentinel path."""
    sentinel = project_dir / "phases" / "yolo-approval" / "second-persona-review.md"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    # Stuff a prefix then pad with non-whitespace 'x' chars to reach target.
    prefix = "# Second-persona review\nSenior engineer reviewed. "
    pad_len = max(0, content_bytes - len(prefix))
    sentinel.write_text(prefix + ("x" * pad_len))
    return sentinel


def _valid_justification() -> str:
    """Return a justification that clears the 40-char minimum."""
    return (
        "Refactor scoped to module X; rollback plan in place; "
        "persona review on file."
    )


# ---------------------------------------------------------------------------
# Guardrail 1 — Justification required (>= 40 chars)
# ---------------------------------------------------------------------------


class TestJustificationRequired(unittest.TestCase):
    """Full-rigor yolo approve rejects short/empty justifications."""

    def test_approve_rejects_empty_reason_at_full_rigor(self):
        """Empty reason at full rigor raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action("p", "approve", reason="")
            self.assertIn("yolo-justification-required", str(ctx.exception))

    def test_approve_rejects_short_reason_at_full_rigor(self):
        """Reason below the 40-char minimum raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action("p", "approve", reason="too short")
            self.assertIn("yolo-justification-required", str(ctx.exception))

    def test_approve_accepts_40_char_justification(self):
        """Reason exactly 40 chars is accepted (boundary condition)."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            state = _state("p", rigor_tier="full")
            exact_40 = "x" * 40
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action("p", "approve", reason=exact_40)
            self.assertTrue(result["yolo_approved_by_user"])

    def test_justification_recorded_in_audit_extra(self):
        """Grant audit line carries structured `justification` + rigor_tier."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            state = _state("p", rigor_tier="full")
            justification = _valid_justification()
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                phase_manager.yolo_action("p", "approve", reason=justification)
            # Audit line must contain the justification text.
            lines = [
                json.loads(ln) for ln in
                (project_dir / "yolo-audit.jsonl").read_text().splitlines()
                if ln.strip()
            ]
            grant = next(l for l in lines if l["event"] == "granted")
            self.assertEqual(grant.get("justification"), justification)

    def test_approve_below_full_rigor_accepts_any_reason(self):
        """At standard rigor, short reasons do NOT trigger the guardrail."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state("p", rigor_tier="standard")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                # No sentinel, no justification — lower tier is unaffected.
                result = phase_manager.yolo_action("p", "approve", reason="ok")
            self.assertTrue(result["yolo_approved_by_user"])


# ---------------------------------------------------------------------------
# Guardrail 2 — Cooldown after auto-revoke
# ---------------------------------------------------------------------------


class TestCooldownAfterAutoRevoke(unittest.TestCase):
    """5-minute cooldown blocks re-grant after a scope-increase revoke."""

    def _write_auto_revoke_audit(self, project_dir: Path, ts_iso: str):
        """Append a scope-increase auto-revoke audit record."""
        audit = project_dir / "yolo-audit.jsonl"
        audit.write_text(json.dumps({
            "event": "revoked",
            "timestamp": ts_iso,
            "reason": "scope-increase@execute",
            "scope": f"project:{project_dir.name}",
            "prior_value": True,
            "new_value": False,
        }) + "\n")

    def test_cooldown_blocks_regrant_within_window(self):
        """Auto-revoke < 300s ago blocks re-grant."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            # Auto-revoke 60s ago → well inside the 300s cooldown.
            recent = (datetime.now(timezone.utc) - timedelta(seconds=60))
            self._write_auto_revoke_audit(project_dir, recent.isoformat())
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action(
                        "p", "approve", reason=_valid_justification(),
                    )
            self.assertIn("yolo-cooldown-active", str(ctx.exception))

    def test_cooldown_lifted_after_window(self):
        """Auto-revoke > 300s ago no longer blocks re-grant."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            old = (datetime.now(timezone.utc) - timedelta(seconds=600))
            self._write_auto_revoke_audit(project_dir, old.isoformat())
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action(
                    "p", "approve", reason=_valid_justification(),
                )
            self.assertTrue(result["yolo_approved_by_user"])

    def test_manual_revoke_does_not_trigger_cooldown(self):
        """User-initiated revokes (not scope-increase) skip cooldown."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            # Manual revoke reason does NOT match "scope-increase@*".
            audit = project_dir / "yolo-audit.jsonl"
            audit.write_text(json.dumps({
                "event": "revoked",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "user-revoked",
                "scope": f"project:{project_dir.name}",
                "prior_value": True,
                "new_value": False,
            }) + "\n")
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action(
                    "p", "approve", reason=_valid_justification(),
                )
            self.assertTrue(result["yolo_approved_by_user"])

    def test_helper_handles_z_suffix_timestamp(self):
        """_parse_iso_timestamp accepts get_utc_timestamp()'s Z format."""
        dt = phase_manager._parse_iso_timestamp("2026-04-18T10:00:00Z")
        self.assertIsNotNone(dt)
        # Parsed dt is tz-aware UTC.
        self.assertIsNotNone(dt.tzinfo)

    def test_helper_returns_none_on_missing_audit(self):
        """No audit file → no prior auto-revoke → no cooldown error."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            self.assertIsNone(phase_manager._check_yolo_cooldown(project_dir))


# ---------------------------------------------------------------------------
# Guardrail 3 — Second-persona review sentinel
# ---------------------------------------------------------------------------


class TestSecondPersonaReview(unittest.TestCase):
    """Full-rigor grant requires a non-trivial second-persona review sentinel."""

    def test_missing_sentinel_blocks_grant(self):
        """Absent sentinel raises ValueError with actionable guidance."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action(
                        "p", "approve", reason=_valid_justification(),
                    )
            self.assertIn("yolo-second-persona-review-missing", str(ctx.exception))

    def test_trivial_sentinel_blocks_grant(self):
        """Sentinel < 100 bytes of non-whitespace raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            # Stage a tiny sentinel (well under 100 bytes of content).
            sentinel = project_dir / "phases" / "yolo-approval" / "second-persona-review.md"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("ok")
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action(
                        "p", "approve", reason=_valid_justification(),
                    )
            self.assertIn("yolo-second-persona-review-trivial", str(ctx.exception))

    def test_populated_sentinel_allows_grant(self):
        """Sentinel with >= 100 bytes of content allows grant at full rigor."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            _stage_sentinel(project_dir)
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action(
                    "p", "approve", reason=_valid_justification(),
                )
            self.assertTrue(result["yolo_approved_by_user"])

    def test_whitespace_only_sentinel_blocks_grant(self):
        """A sentinel stuffed with whitespace alone still blocks the grant."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            sentinel = project_dir / "phases" / "yolo-approval" / "second-persona-review.md"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            # Lots of bytes, but all whitespace → stripped length is 0.
            sentinel.write_text("\n\n\n\n\n\n\n\n" + (" " * 500))
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action(
                        "p", "approve", reason=_valid_justification(),
                    )
            self.assertIn("yolo-second-persona-review-trivial", str(ctx.exception))


# ---------------------------------------------------------------------------
# Lower-rigor tiers bypass every guardrail
# ---------------------------------------------------------------------------


class TestLowerRigorBypassesGuardrails(unittest.TestCase):
    """Minimal / standard tiers retain legacy behaviour — no guardrails."""

    def test_standard_tier_grants_without_sentinel_or_cooldown(self):
        """Standard rigor: no sentinel, recent auto-revoke, short reason → ok."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            # Write a recent auto-revoke that would trigger cooldown at full.
            (project_dir / "yolo-audit.jsonl").write_text(json.dumps({
                "event": "revoked",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "scope-increase@execute",
                "prior_value": True,
                "new_value": False,
            }) + "\n")
            state = _state("p", rigor_tier="standard")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action("p", "approve", reason="go")
            # Lower tier bypasses guardrails — grant succeeds.
            self.assertTrue(result["yolo_approved_by_user"])

    def test_minimal_tier_grants_without_sentinel(self):
        """Minimal rigor: no sentinel needed."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state("p", rigor_tier="minimal")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                result = phase_manager.yolo_action("p", "approve", reason="")
            self.assertTrue(result["yolo_approved_by_user"])


# ---------------------------------------------------------------------------
# Ordering — first-hit error surfaces (stable for CLI parsing)
# ---------------------------------------------------------------------------


class TestGuardrailEvaluationOrder(unittest.TestCase):
    """Guardrails short-circuit in a stable order: justification → cooldown → sentinel."""

    def test_justification_checked_before_sentinel(self):
        """Missing justification AND missing sentinel → justification wins."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "p"
            project_dir.mkdir()
            state = _state("p", rigor_tier="full")
            with patch.object(phase_manager, "load_project_state", return_value=state), \
                 patch.object(phase_manager, "save_project_state"), \
                 patch.object(phase_manager, "get_project_dir", return_value=project_dir):
                with self.assertRaises(ValueError) as ctx:
                    phase_manager.yolo_action("p", "approve", reason="x")
            # The justification error prefix is the first one users see.
            self.assertIn("yolo-justification-required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
