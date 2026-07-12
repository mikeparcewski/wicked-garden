"""tests/test_heavy_cadence_redesign.py — heavy-cadence teardown reliability.

Provenance: pre-v9.2.15, four heavy functions ran on EVERY Stop hook (per turn):
  - _run_memory_decay        (~30 brain `lint` calls/session)
  - _run_working_consolidation (~30 brain `compile` calls/session, 10s each)
  - _run_quality_telemetry   (timeline.jsonl appends inflated 30x)
  - _run_guard_pipeline      (findings.json overwritten per-turn)

v9.2.15 moved them to a SessionEnd primary + 60-min Stop fallback, with a
sidecar at <local store>/wicked-garden/heavy-cadence/last_run.json persisting
`last_heavy_run_ts` cross-session.

v9.2.16 (#842) — dogfood telemetry showed SessionEnd fires for only ~40% of
human and ~1% of agent sessions; the 60-min-only Stop gate dropped short
sessions entirely (78% of runs were the "fallback", and short sessions still
got nothing). The deterministic fix:
  - Stop carries the SAME teardown, guarded to run at most ONCE per session.
  - De-dupe by session_id so SessionEnd + Stop never double-run and per-turn
    Stops don't repeat (already_ran_this_session()).
  - Turn-count-OR-60-min gate (FALLBACK_TURN_THRESHOLD) so busy short sessions
    still get teardown even when SessionEnd never fires.

T1: deterministic — sidecar read/write under tmp_path, frozen-time gate tests
T3: isolated — monkeypatches `_sidecar_path` to point at tmp
T4: single focus — de-dupe + turn/time gate + orchestration contracts
T6: docstring cites #842 and the audit findings.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "hooks" / "scripts"))


@pytest.fixture
def tmp_sidecar(tmp_path, monkeypatch):
    """Redirect the heavy-cadence sidecar to a tmp file."""
    import _heavy_cadence  # noqa
    sentinel = tmp_path / "last_run.json"
    monkeypatch.setattr(_heavy_cadence, "_sidecar_path", lambda: sentinel)
    return sentinel


def _write_sidecar_file(path: Path, *, minutes_ago: float, session_id: str = "",
                        trigger: str = "session_end") -> None:
    """Seed the sidecar with a run `minutes_ago` in the past."""
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "last_heavy_run_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigger": trigger,
        "session_id": session_id,
    }))


# ---------------------------------------------------------------------------
# Sidecar read / write contract
# ---------------------------------------------------------------------------

def test_sidecar_read_returns_empty_dict_when_missing(tmp_sidecar):
    import _heavy_cadence
    assert _heavy_cadence._read_sidecar() == {}


def test_sidecar_read_returns_empty_dict_on_corrupt_json(tmp_sidecar):
    import _heavy_cadence
    tmp_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_sidecar.write_text("{not json")
    assert _heavy_cadence._read_sidecar() == {}


def test_sidecar_write_persists_iso_timestamp_and_trigger(tmp_sidecar):
    import _heavy_cadence
    _heavy_cadence._write_sidecar("session_end", session_id="test-session")
    data = json.loads(tmp_sidecar.read_text())
    assert data["trigger"] == "session_end"
    assert data["session_id"] == "test-session"
    assert "last_heavy_run_ts" in data
    assert data["last_heavy_run_ts"].endswith("Z")
    assert len(data["last_heavy_run_ts"]) == 20


def test_sidecar_write_no_op_when_path_unresolvable(tmp_path, monkeypatch):
    import _heavy_cadence
    monkeypatch.setattr(_heavy_cadence, "_sidecar_path", lambda: None)
    _heavy_cadence._write_sidecar("session_end")  # must not raise
    assert _heavy_cadence._read_sidecar() == {}


def test_sidecar_write_is_atomic(tmp_sidecar):
    """v9.2.15 council mitigation: _write_sidecar must use temp-file + os.replace
    so a concurrent reader sees either the old sidecar OR the new sidecar, never
    a half-written file. Verify no `.tmp.*` leftovers and valid final JSON."""
    import _heavy_cadence
    _heavy_cadence._write_sidecar("session_end", session_id="atomicity-test")

    data = json.loads(tmp_sidecar.read_text())
    assert data["session_id"] == "atomicity-test"

    leftovers = list(tmp_sidecar.parent.glob(f"{tmp_sidecar.name}.tmp.*"))
    assert leftovers == [], (
        f"Atomic write left behind temp file(s): {leftovers}. "
        f"Contract: write to <name>.tmp.<pid> then os.replace."
    )


def test_sidecar_temp_path_uses_pid_disambiguation():
    """Parallel writers must not collide on the same temp path before either
    calls os.replace — the temp path must include os.getpid()."""
    import _heavy_cadence
    import inspect
    src = inspect.getsource(_heavy_cadence._write_sidecar)
    assert "os.getpid()" in src, (
        "_write_sidecar temp path must include os.getpid() to disambiguate "
        "parallel writers."
    )
    assert "os.replace" in src, (
        "_write_sidecar must use os.replace (atomic on POSIX + Windows) "
        "instead of bare write_text."
    )


# ---------------------------------------------------------------------------
# De-dupe guard (v9.2.16, #842) — the keystone reliability contract
# ---------------------------------------------------------------------------

def test_already_ran_false_when_session_id_unknown(tmp_sidecar):
    """An unknown/empty session_id can never be matched — return False so the
    caller falls through to the time/turn gate rather than silently skipping."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=1, session_id="sess-A")
    assert _heavy_cadence.already_ran_this_session(None) is False
    assert _heavy_cadence.already_ran_this_session("") is False


def test_already_ran_false_when_sidecar_missing(tmp_sidecar):
    import _heavy_cadence
    assert _heavy_cadence.already_ran_this_session("sess-A") is False


def test_already_ran_true_when_session_matches(tmp_sidecar):
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=1, session_id="sess-A")
    assert _heavy_cadence.already_ran_this_session("sess-A") is True


def test_already_ran_false_when_session_differs(tmp_sidecar):
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=1, session_id="sess-A")
    assert _heavy_cadence.already_ran_this_session("sess-B") is False


def test_fallback_deduped_when_session_already_ran(tmp_sidecar):
    """The core de-dupe: once heavy cadence ran for this session (SessionEnd or
    an earlier Stop), should_run_fallback() must return False for that session —
    even with a huge turn_count — so Stop does not re-run it every turn and does
    not double-run against SessionEnd."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=1, session_id="sess-A")
    assert _heavy_cadence.should_run_fallback(session_id="sess-A", turn_count=999) is False


def test_session_end_and_stop_do_not_double_run(tmp_sidecar, monkeypatch):
    """End-to-end de-dupe: after run_heavy_cadence records session 'S', a
    subsequent Stop for the SAME session must not fire again."""
    import _heavy_cadence
    for fn in ("_run_memory_decay", "_run_memory_consolidation", "_run_guard_pipeline"):
        monkeypatch.setattr(_heavy_cadence, fn, lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: [])

    # SessionEnd (or a first Stop) runs and records session 'S'.
    _heavy_cadence.run_heavy_cadence("session_end", session_id="S")
    assert json.loads(tmp_sidecar.read_text())["session_id"] == "S"

    # A later Stop for the same session is de-duped.
    assert _heavy_cadence.should_run_fallback(session_id="S", turn_count=999) is False


# ---------------------------------------------------------------------------
# Turn-count OR time gate — catches short sessions SessionEnd would drop
# ---------------------------------------------------------------------------

def test_fallback_fires_when_sidecar_missing(tmp_sidecar):
    """First Stop call ever must run the teardown to seed the sidecar."""
    import _heavy_cadence
    assert _heavy_cadence.should_run_fallback(session_id="sess-A", turn_count=0) is True


def test_fallback_turn_arm_fires_below_time_window(tmp_sidecar):
    """A NEW session (different session_id) that crosses the turn threshold must
    fire even though <60 min elapsed — catches busy short-wall-clock sessions
    (e.g. agent runs) whose SessionEnd never fired."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=5, session_id="prev-session")
    assert _heavy_cadence.should_run_fallback(
        session_id="new-session", turn_count=_heavy_cadence.FALLBACK_TURN_THRESHOLD
    ) is True


def test_fallback_suppressed_when_new_session_short_and_recent(tmp_sidecar):
    """A NEW session with few turns AND <60 min since the last run must NOT
    fire — a heavy run just happened, so brain/telemetry state is fresh and a
    2-turn session is not worth a second teardown."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=5, session_id="prev-session")
    assert _heavy_cadence.should_run_fallback(
        session_id="new-session", turn_count=3
    ) is False


def test_fallback_time_arm_fires_when_last_run_older_than_60_min(tmp_sidecar):
    """A run 70 minutes ago MUST trigger the teardown (catch-up case) even for a
    low-turn session — the time arm covers long idle sessions."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=70, session_id="prev-session")
    assert _heavy_cadence.should_run_fallback(session_id="new-session", turn_count=0) is True


def test_fallback_suppressed_within_60_min_window_legacy_call(tmp_sidecar):
    """Backward-compat: the pre-v9.2.16 call shape (no session_id, no turn_count)
    still resolves to the pure 60-min time gate — 30 min ago → suppressed."""
    import _heavy_cadence
    _write_sidecar_file(tmp_sidecar, minutes_ago=30, session_id="sess-A")
    assert _heavy_cadence.should_run_fallback() is False


def test_fallback_fires_on_corrupt_timestamp(tmp_sidecar):
    """A malformed timestamp is treated as never-run — defensive self-heal."""
    import _heavy_cadence
    tmp_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_sidecar.write_text(json.dumps({
        "last_heavy_run_ts": "not-an-iso-timestamp",
        "trigger": "session_end",
        "session_id": "other",
    }))
    assert _heavy_cadence.should_run_fallback(session_id="sess-A", turn_count=0) is True


def test_fallback_interval_is_60_minutes():
    """Locked constant — change is a deliberate decision."""
    import _heavy_cadence
    assert _heavy_cadence.FALLBACK_INTERVAL_SECS == 60 * 60


def test_fallback_turn_threshold_is_30():
    """Locked constant — the turn arm of the gate."""
    import _heavy_cadence
    assert _heavy_cadence.FALLBACK_TURN_THRESHOLD == 30


# ---------------------------------------------------------------------------
# run_heavy_cadence orchestration — runs all four + writes sidecar
# ---------------------------------------------------------------------------

def test_run_heavy_cadence_writes_sidecar_after_run(tmp_sidecar, monkeypatch):
    """Every successful invocation persists timestamp + trigger + session_id so
    the next Stop's de-dupe/gate has a deterministic answer."""
    import _heavy_cadence
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: [])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: [])

    messages = _heavy_cadence.run_heavy_cadence("session_end", session_id="test")
    assert messages == []
    data = json.loads(tmp_sidecar.read_text())
    assert data["trigger"] == "session_end"
    assert data["session_id"] == "test"


def test_run_heavy_cadence_stop_fallback_records_correct_trigger(tmp_sidecar, monkeypatch):
    """When the Stop path runs the teardown, the sidecar records stop_fallback —
    so the trigger distribution reflects which path actually did the work."""
    import _heavy_cadence
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: [])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: [])

    _heavy_cadence.run_heavy_cadence(
        _heavy_cadence.TRIGGER_STOP_FALLBACK, session_id="agent-sess"
    )
    data = json.loads(tmp_sidecar.read_text())
    assert data["trigger"] == "stop_fallback"
    assert data["session_id"] == "agent-sess"


def test_run_heavy_cadence_aggregates_messages(tmp_sidecar, monkeypatch):
    """All four functions' messages flow through to the caller."""
    import _heavy_cadence
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: ["[Memory] Decay: 1, 2"])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", lambda root: ["[Memory] Consolidation: 3, 4"])
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: ["[Telemetry] Drift detected"])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: ["[Guard] 5 findings"])

    messages = _heavy_cadence.run_heavy_cadence("stop_fallback", session_id="test")
    assert len(messages) == 4
    assert any("Decay" in m for m in messages)
    assert any("Consolidation" in m for m in messages)
    assert any("Drift" in m for m in messages)
    assert any("Guard" in m for m in messages)


def test_run_heavy_cadence_does_not_write_sidecar_on_raise(tmp_sidecar, monkeypatch):
    """If a heavy function raises (test stub without the real fail-open), the
    sidecar is NOT written — preserving the "next Stop retries" property."""
    import _heavy_cadence
    def boom(root, *args):
        raise RuntimeError("brain unreachable")
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", boom)
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: [])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: [])
    with pytest.raises(RuntimeError):
        _heavy_cadence.run_heavy_cadence("session_end", session_id="s")
    assert not tmp_sidecar.exists()


# ---------------------------------------------------------------------------
# stop.py contract: carries the teardown with the de-duped gate
# ---------------------------------------------------------------------------

def test_stop_py_no_longer_calls_heavy_functions_directly():
    """stop.py must invoke the heavy work only via run_heavy_cadence() inside
    the should_run_fallback() branch, never the four functions directly."""
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()
    direct_calls = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
        and any(call in line for call in (
            "_run_memory_decay()",
            "_run_working_consolidation()",
            "_run_quality_telemetry(",
            "_run_guard_pipeline()",
        ))
        and "def " not in line
    ]
    assert not direct_calls, (
        f"stop.py main flow still calls heavy functions directly: {direct_calls}"
    )


def test_stop_py_imports_heavy_cadence():
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()
    assert "from _heavy_cadence import" in text
    assert "should_run_fallback" in text
    assert "run_heavy_cadence" in text


def test_stop_py_passes_session_id_and_turn_count_to_gate():
    """v9.2.16: the Stop gate must be per-session (de-dupe) and turn-aware, so
    stop.py must pass BOTH session_id and turn_count into should_run_fallback."""
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()
    assert "should_run_fallback(session_id=session_id, turn_count=turn_count)" in text, (
        "stop.py must call should_run_fallback with session_id + turn_count so "
        "the de-dupe guard and turn arm are active."
    )


# ---------------------------------------------------------------------------
# session_end.py contract: de-dupes against a Stop that already ran
# ---------------------------------------------------------------------------

def test_session_end_py_uses_dedupe_guard():
    """SessionEnd must skip the teardown when a Stop already ran it this
    session — otherwise SessionEnd + Stop double-run."""
    text = (REPO_ROOT / "hooks" / "scripts" / "session_end.py").read_text()
    assert "already_ran_this_session" in text, (
        "session_end.py must consult already_ran_this_session() to de-dupe "
        "against a Stop that already carried the teardown."
    )


def test_session_end_py_exists_and_imports():
    p = REPO_ROOT / "hooks" / "scripts" / "session_end.py"
    assert p.exists(), f"SessionEnd script missing at {p}"
    import session_end  # noqa: F401


# ---------------------------------------------------------------------------
# hooks.json: both terminal events are wired to the teardown carriers
# ---------------------------------------------------------------------------

def test_hooks_json_wires_sessionend_and_stop():
    """Both SessionEnd and Stop must be wired — Stop is now a reliable
    co-primary carrier, not just a rare fallback."""
    h = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    events = h["hooks"]
    assert "SessionEnd" in events
    assert "Stop" in events
    se_cmd = events["SessionEnd"][0]["hooks"][0]["command"]
    assert "session_end" in se_cmd, f"SessionEnd does not invoke session_end: {se_cmd}"
    stop_cmd = events["Stop"][0]["hooks"][0]["command"]
    assert "stop" in stop_cmd, f"Stop does not invoke stop: {stop_cmd}"
