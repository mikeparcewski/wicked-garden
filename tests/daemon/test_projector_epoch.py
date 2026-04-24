"""tests/daemon/test_projector_epoch.py — Regression tests for _to_epoch timezone fix.

Locks the fix for the timezone-stripping bug identified in PR #599 review:
the original _to_epoch discarded the UTC offset, treating offset times as UTC.
This caused data corruption (off-by-N hours) for non-UTC timestamps.

T1: deterministic — no wall-clock; all expected values are pre-computed constants.
T2: no sleep-based sync.
T3: isolated — no shared state; _to_epoch is a pure function.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #589 review item #1 (gemini-code-assist), timezone regression fix.
"""

from __future__ import annotations

# sys.path setup is handled by tests/daemon/conftest.py — no mutation needed here.

import pytest


# ---------------------------------------------------------------------------
# UTC epoch pre-computed constants for known timestamps
# ---------------------------------------------------------------------------

# "2026-04-24T12:00:00+02:00" = 10:00:00 UTC = 1777024800
_TS_OFFSET_PLUS_TWO = "2026-04-24T12:00:00+02:00"
_TS_OFFSET_PLUS_TWO_UTC_EPOCH = 1777024800  # 2026-04-24 10:00:00 UTC

# "2026-04-24T12:00:00-05:00" = 17:00:00 UTC = 1777050000
_TS_OFFSET_MINUS_FIVE = "2026-04-24T12:00:00-05:00"
_TS_OFFSET_MINUS_FIVE_UTC_EPOCH = 1777050000  # 2026-04-24 17:00:00 UTC

# "2026-04-24T10:00:00+00:00" = 10:00:00 UTC = 1777024800
_TS_UTC_EXPLICIT = "2026-04-24T10:00:00+00:00"
_TS_UTC_EXPLICIT_EPOCH = 1777024800

# "2026-04-24T10:00:00Z" — Z suffix normalised to +00:00
_TS_UTC_Z = "2026-04-24T10:00:00Z"
_TS_UTC_Z_EPOCH = 1777024800

# "2026-04-24T10:00:00" — naive; assumed UTC per Decision #9
_TS_NAIVE = "2026-04-24T10:00:00"
_TS_NAIVE_EPOCH = 1777024800


# ---------------------------------------------------------------------------
# Regression: +02:00 offset must be honoured (the original bug)
# ---------------------------------------------------------------------------


def test_to_epoch_offset_plus_two_returns_utc_epoch() -> None:
    """_to_epoch("2026-04-24T12:00:00+02:00") must return 2026-04-24T10:00:00 UTC.

    Regression for the bug where the offset was stripped and the clock time
    (12:00) was treated as UTC instead of converting to UTC first (10:00).
    Off-by-7200 seconds = 2 hours of data corruption.
    """
    from daemon.projector import _to_epoch  # type: ignore[import]

    result = _to_epoch(_TS_OFFSET_PLUS_TWO)
    assert result == _TS_OFFSET_PLUS_TWO_UTC_EPOCH, (
        f"_to_epoch({_TS_OFFSET_PLUS_TWO!r}) returned {result}, "
        f"expected UTC epoch {_TS_OFFSET_PLUS_TWO_UTC_EPOCH} "
        f"(2026-04-24T10:00:00 UTC). "
        "The timezone offset (+02:00) must be applied before computing epoch."
    )


def test_to_epoch_offset_minus_five_returns_utc_epoch() -> None:
    """_to_epoch("2026-04-24T12:00:00-05:00") must return 2026-04-24T17:00:00 UTC."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    result = _to_epoch(_TS_OFFSET_MINUS_FIVE)
    assert result == _TS_OFFSET_MINUS_FIVE_UTC_EPOCH, (
        f"_to_epoch({_TS_OFFSET_MINUS_FIVE!r}) returned {result}, "
        f"expected UTC epoch {_TS_OFFSET_MINUS_FIVE_UTC_EPOCH} "
        f"(2026-04-24T17:00:00 UTC). "
        "The negative offset (-05:00) must be applied before computing epoch."
    )


# ---------------------------------------------------------------------------
# UTC variants: Z suffix and explicit +00:00 must agree
# ---------------------------------------------------------------------------


def test_to_epoch_utc_z_suffix_matches_explicit_utc() -> None:
    """Z-suffix and explicit +00:00 must produce the same epoch."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch(_TS_UTC_Z) == _to_epoch(_TS_UTC_EXPLICIT) == _TS_UTC_EXPLICIT_EPOCH, (
        "Z-suffix and +00:00 must produce identical UTC epoch."
    )


def test_to_epoch_naive_string_treated_as_utc() -> None:
    """A naive ISO string (no tzinfo) is assumed UTC per Decision #9."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    result = _to_epoch(_TS_NAIVE)
    assert result == _TS_NAIVE_EPOCH, (
        f"_to_epoch({_TS_NAIVE!r}) returned {result}, "
        f"expected {_TS_NAIVE_EPOCH} (naive = UTC per Decision #9)."
    )


# ---------------------------------------------------------------------------
# Passthrough: int and float values unchanged
# ---------------------------------------------------------------------------


def test_to_epoch_int_passthrough() -> None:
    """Integer epoch values pass through unchanged."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch(1_700_000_000) == 1_700_000_000


def test_to_epoch_float_truncates_to_int() -> None:
    """Float epoch values are truncated (floor) to int."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch(1_700_000_000.9) == 1_700_000_000


# ---------------------------------------------------------------------------
# Edge cases: None and bad input
# ---------------------------------------------------------------------------


def test_to_epoch_none_returns_none() -> None:
    """None input returns None without raising."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch(None) is None


def test_to_epoch_invalid_string_returns_none() -> None:
    """Unparseable string returns None without raising."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch("not-a-date") is None


def test_to_epoch_unknown_type_returns_none() -> None:
    """Non-string, non-numeric input returns None without raising."""
    from daemon.projector import _to_epoch  # type: ignore[import]

    assert _to_epoch({"ts": 123}) is None
