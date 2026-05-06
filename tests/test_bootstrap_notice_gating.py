"""tests/test_bootstrap_notice_gating.py — first-session-per-project gating
for [Setup] and [Quick Start] briefing notices (v9.2.10).

Provenance: every session of every wicked-garden user emitted

  [Setup] Run `/wicked-garden:setup --reconfigure` to change connection or re-onboard.
  [Quick Start] Available commands for this project: ...

These notices are useful exactly once per project. Emitting them on every
session is chronic noise — same anti-pattern as the v9.2.6 [Memory] reminder
that v9.2.2 first attempted to latch (and got bit by SessionState being
per-session). v9.2.10 fixes it correctly via a per-project sentinel file
under the wicked-garden local store, which is naturally scoped per project
because `get_local_path("wicked-garden", ...)` resolves under the active
project's slug.

T1: deterministic — uses a tmp_path-redirected sentinel file.
T3: isolated — monkeypatches `_notice_path` to point at tmp.
T4: single focus — the notice-shown contract.
T6: docstring cites v9.2.10 (this PR).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


@pytest.fixture
def tmp_notice_path(tmp_path, monkeypatch):
    """Redirect the bootstrap notice sentinel to a tmp file."""
    import bootstrap  # noqa: F401  — module loaded with sys.path adjustments above
    sentinel = tmp_path / "shown.json"
    monkeypatch.setattr(bootstrap, "_notice_path", lambda: sentinel)
    return sentinel


def test_first_show_records_notice(tmp_notice_path):
    """First call emits (returns False from _notice_already_shown)
    and recording marks it as shown."""
    import bootstrap

    notice_id = "setup_reconfigure"
    assert bootstrap._notice_already_shown(notice_id) is False
    bootstrap._record_notice_shown(notice_id)
    assert bootstrap._notice_already_shown(notice_id) is True


def test_subsequent_calls_see_notice_as_shown(tmp_notice_path):
    """After a notice is recorded, subsequent _notice_already_shown calls
    return True so the briefing logic suppresses the line."""
    import bootstrap

    bootstrap._record_notice_shown("quick_start")
    # Multiple checks all return True — sticky across reads.
    assert bootstrap._notice_already_shown("quick_start") is True
    assert bootstrap._notice_already_shown("quick_start") is True
    assert bootstrap._notice_already_shown("quick_start") is True


def test_two_notices_track_independently(tmp_notice_path):
    """Recording one notice does not mark another as shown."""
    import bootstrap

    bootstrap._record_notice_shown("setup_reconfigure")
    assert bootstrap._notice_already_shown("setup_reconfigure") is True
    assert bootstrap._notice_already_shown("quick_start") is False


def test_record_persists_iso_timestamp(tmp_notice_path):
    """Each entry stores `shown_at` as an ISO-8601 UTC string for forensics."""
    import bootstrap

    bootstrap._record_notice_shown("setup_reconfigure")
    data = json.loads(tmp_notice_path.read_text())
    assert "setup_reconfigure" in data
    assert "shown_at" in data["setup_reconfigure"]
    ts = data["setup_reconfigure"]["shown_at"]
    # Z-suffix UTC timestamp, length 20 (e.g. "2026-05-06T14:23:45Z").
    assert ts.endswith("Z")
    assert len(ts) == 20


def test_unresolvable_path_fails_open(tmp_path, monkeypatch):
    """If `_notice_path` returns None (e.g. local store unreachable),
    _notice_already_shown returns False and _record_notice_shown is a no-op
    rather than raising. Bootstrap must never hard-fail on this."""
    import bootstrap

    monkeypatch.setattr(bootstrap, "_notice_path", lambda: None)
    assert bootstrap._notice_already_shown("anything") is False
    # Must not raise.
    bootstrap._record_notice_shown("anything")
    assert bootstrap._notice_already_shown("anything") is False


def test_corrupt_json_treated_as_empty(tmp_notice_path):
    """A malformed sentinel file behaves like an empty one — first-show
    semantics are preserved rather than raising."""
    import bootstrap

    tmp_notice_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_notice_path.write_text("{not json")
    assert bootstrap._notice_already_shown("setup_reconfigure") is False
    # Recording overwrites the corrupt content with a fresh dict.
    bootstrap._record_notice_shown("setup_reconfigure")
    assert bootstrap._notice_already_shown("setup_reconfigure") is True


def test_critical_skills_silent_when_present():
    """v9.2.10: the [Skills] happy-path message was dropped. When all
    critical v6 skills exist on disk, _check_critical_skills returns None
    rather than the chronic 'present on disk' notice."""
    import bootstrap

    result = bootstrap._check_critical_skills()
    # All critical skills exist in the wicked-garden repo by construction.
    assert result is None, (
        f"_check_critical_skills should return None when skills present; got: {result!r}"
    )


def test_memory_instructions_constant_removed():
    """v9.2.11 deleted _MEMORY_INSTRUCTIONS entirely. v9.2.10 only stopped
    APPENDING it to the briefing; the constant was preserved as a silent-
    contract-drift defence in case any other module imported it. v9.2.11
    confirmed zero imports across hooks/, scripts/, tests/, commands/ and
    removed the dead constant. This test now asserts the absence — adding
    it back is a regression."""
    import bootstrap

    assert not hasattr(bootstrap, "_MEMORY_INSTRUCTIONS"), (
        "_MEMORY_INSTRUCTIONS was deleted in v9.2.11 because it had zero "
        "consumers. If you need this constant, prefer adding the guidance "
        "to CLAUDE.md (which is loaded into context by Claude Code itself)."
    )
