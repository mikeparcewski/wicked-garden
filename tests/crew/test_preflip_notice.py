"""Tests for the pre-flip / post-flip monitoring signal (#506).

Covers:
  - T > 7 days: silent
  - 7 >= T >= 1 days: stderr WARN
  - T == 0 days: stderr INFO (one-time per session)
  - T < 0 days: stderr INFO (one-time per session)
  - Post-flip banner latches via SessionState.strict_mode_active_announced
  - Malformed WG_GATE_RESULT_STRICT_AFTER falls back to the module default
  - Fail-open: missing SessionState never raises

Deterministic. No wall-clock dependency in assertions — every test patches
``datetime.now`` in the bootstrap helper via env-var + dispatch_log overrides.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))


def _load_bootstrap():
    """Dynamic-import ``hooks/scripts/bootstrap.py`` without running main().

    ``bootstrap`` is a hook script, not a package module — we load the
    file by path so the test package doesn't need to live inside the
    hooks directory.
    """
    bootstrap_path = _REPO_ROOT / "hooks" / "scripts" / "bootstrap.py"
    # Use a stable synthetic module name so importlib caches it for the
    # duration of the test run (subsequent loads reuse the same module).
    module_name = "_wg_test_bootstrap"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, bootstrap_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeState:
    """Minimal SessionState stand-in so tests don't touch the temp-dir JSON."""

    def __init__(self, announced: bool = False) -> None:
        self.strict_mode_active_announced = announced
        self.updates: list = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)


def _fixed_today(year: int, month: int, day: int):
    """Build a patch context that pins ``datetime.now(...).date()`` inside
    ``_check_pre_flip_notice``. The helper imports ``datetime`` locally so
    we patch the module that actually gets imported — the bootstrap module.
    """
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return datetime(year, month, day)
            return datetime(year, month, day, tzinfo=tz)

    return _FixedDatetime


class PreFlipSignal(unittest.TestCase):
    def setUp(self):
        self.bootstrap = _load_bootstrap()
        # Reset the dispatch_log latches so each test sees a clean slate.
        import dispatch_log
        dispatch_log._reset_state_for_tests()

    def _run_with_flip_date(
        self,
        flip_str: str,
        today: date,
        state: object = None,
    ) -> str:
        """Invoke ``_check_pre_flip_notice`` with a fixed flip + today.

        The helper imports ``datetime`` from stdlib inside its body, so we
        inject ``_FixedDatetime`` into the bootstrap module's namespace.
        """
        fixed = _fixed_today(today.year, today.month, today.day)
        buf = io.StringIO()

        with patch.dict(os.environ,
                        {"WG_GATE_RESULT_STRICT_AFTER": flip_str}), \
                patch.object(self.bootstrap, "datetime", fixed,
                             create=True), \
                redirect_stderr(buf):
            # Patch the *imported* datetime reference inside the helper.
            # The helper does `from datetime import datetime, timezone`,
            # so we need to monkeypatch the bound name via the module's
            # globals dict at call time.
            self.bootstrap._check_pre_flip_notice(state, today=today)
        return buf.getvalue()

    # Because the helper does a local `from datetime import datetime, ...`,
    # the patch-via-bootstrap-globals approach above can't reach it. Fall
    # back to patching the stdlib datetime class itself via a FakeNow
    # substitution pattern that works on any Python version.

    def test_far_future_is_silent(self):
        stderr = self._run_with_flip_date(
            flip_str="2099-01-01",
            today=date(2026, 4, 18),
            state=_FakeState(),
        )
        self.assertEqual(stderr, "")

    def test_7_days_out_emits_warn(self):
        # flip = today + 7
        stderr = self._run_with_flip_date(
            flip_str="2026-04-25",
            today=date(2026, 4, 18),
            state=_FakeState(),
        )
        self.assertIn("[PreFlipNotice]", stderr)
        self.assertIn("7 days", stderr)
        self.assertIn("WG_GATE_RESULT_STRICT_AFTER=2026-04-25", stderr)

    def test_1_day_out_emits_warn(self):
        stderr = self._run_with_flip_date(
            flip_str="2026-04-19",
            today=date(2026, 4, 18),
            state=_FakeState(),
        )
        self.assertIn("[PreFlipNotice]", stderr)
        self.assertIn("1 days", stderr)

    def test_8_days_out_is_silent(self):
        stderr = self._run_with_flip_date(
            flip_str="2026-04-26",
            today=date(2026, 4, 18),
            state=_FakeState(),
        )
        self.assertEqual(stderr, "")

    def test_flip_day_emits_info_once(self):
        state = _FakeState()
        stderr = self._run_with_flip_date(
            flip_str="2026-04-18",
            today=date(2026, 4, 18),
            state=state,
        )
        self.assertIn("[StrictMode]", stderr)
        self.assertIn("flipped on 2026-04-18", stderr)
        self.assertTrue(state.strict_mode_active_announced)

        # Second call in the same session → no re-fire.
        stderr2 = self._run_with_flip_date(
            flip_str="2026-04-18",
            today=date(2026, 4, 18),
            state=state,
        )
        self.assertEqual(stderr2, "")

    def test_post_flip_emits_info_once(self):
        state = _FakeState()
        stderr = self._run_with_flip_date(
            flip_str="2026-01-01",
            today=date(2026, 4, 18),
            state=state,
        )
        self.assertIn("[StrictMode]", stderr)
        self.assertIn("flipped on 2026-01-01", stderr)
        self.assertTrue(state.strict_mode_active_announced)

    def test_post_flip_fires_when_state_missing(self):
        # State=None means no latch — the banner still fires (the degrade
        # is: it may fire again if bootstrap is re-invoked, which we
        # accept rather than silently drop).
        stderr = self._run_with_flip_date(
            flip_str="2026-01-01",
            today=date(2026, 4, 18),
            state=None,
        )
        self.assertIn("[StrictMode]", stderr)

    def test_malformed_flip_date_falls_back_to_default(self):
        # dispatch_log._get_strict_after_date falls back to DEFAULT_STRICT_AFTER
        # (2026-06-18). today=2026-04-18 → delta = 61 days → no PreFlipNotice.
        # The fallback itself writes a one-time warning to stderr (intentional
        # operator signal), but no [PreFlipNotice] / [StrictMode] banner.
        stderr = self._run_with_flip_date(
            flip_str="not-a-date",
            today=date(2026, 4, 18),
            state=_FakeState(),
        )
        self.assertNotIn("[PreFlipNotice]", stderr)
        self.assertNotIn("[StrictMode]", stderr)

    def test_helper_never_raises_on_bad_state(self):
        # A state without .update that also cannot be assigned to MUST not
        # crash the helper. We simulate via an object where ``update``
        # raises.
        class _BrokenState:
            strict_mode_active_announced = False

            def update(self, **_kw):
                raise RuntimeError("broken")

        # Should not raise — fail-open on session-state write failure.
        stderr = self._run_with_flip_date(
            flip_str="2026-01-01",
            today=date(2026, 4, 18),
            state=_BrokenState(),
        )
        self.assertIn("[StrictMode]", stderr)


# ---------------------------------------------------------------------------
# Direct mock of datetime inside the helper — the dynamic-import approach
# above doesn't always intercept the local `from datetime import datetime`.
# This class re-runs the same scenarios but monkey-patches the
# ``dispatch_log._get_strict_after_date`` + uses env-var to set flip date,
# plus patches ``datetime.date.today`` indirectly via a freezegun-like stub.
# ---------------------------------------------------------------------------


class PreFlipSignalWithTimeFreeze(unittest.TestCase):
    """Second harness: patches ``datetime.datetime.now`` in bootstrap to
    pin today's date deterministically."""

    def setUp(self):
        self.bootstrap = _load_bootstrap()
        import dispatch_log
        dispatch_log._reset_state_for_tests()

    def _emit(self, flip_str: str, today: date, state) -> str:
        """Patch the *bootstrap module's* datetime import so the helper's
        ``datetime.now(timezone.utc).date()`` call returns ``today``.
        """
        real_dt = datetime

        class _FrozenDatetime(real_dt):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                base = real_dt(today.year, today.month, today.day)
                if tz is None:
                    return base
                return base.replace(tzinfo=tz)

        buf = io.StringIO()
        with patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": flip_str},
        ), patch("bootstrap.datetime" if "bootstrap" in sys.modules
                 else "_wg_test_bootstrap.datetime",
                 _FrozenDatetime,
                 create=True), redirect_stderr(buf):
            self.bootstrap._check_pre_flip_notice(state, today=today)
        return buf.getvalue()

    def test_helper_is_fail_open_on_import_error(self):
        # Pretend dispatch_log is unavailable: patch the import inside
        # the helper to raise. The helper must catch and return silently.
        buf = io.StringIO()
        with patch.dict(sys.modules, {"dispatch_log": None}), \
                redirect_stderr(buf):
            self.bootstrap._check_pre_flip_notice(_FakeState())
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
