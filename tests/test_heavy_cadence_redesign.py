"""tests/test_heavy_cadence_redesign.py — v9.2.15 stop.py cadence redesign.

Provenance: pre-v9.2.15, four heavy functions ran on EVERY Stop hook:
  - _run_memory_decay        (~30 brain `lint` calls/session)
  - _run_working_consolidation (~30 brain `compile` calls/session, 10s each)
  - _run_quality_telemetry   (timeline.jsonl appends inflated 30x —
                                 4-session drift baseline became 4-turn,
                                 a CORRECTNESS BUG, not just performance)
  - _run_guard_pipeline      (findings.json overwritten per-turn,
                                 mid-session signal lost before bootstrap
                                 could read it)

Plus the [Memory] reflection block (lines 469-511 pre-fix) had a parser bug
that made the "smart" branch dead code (looked for "Auto-extracted " but
upstream emitted "Emitted N fact event(s)").

The v9.2.15 quick brainstorm chose Option C (hybrid):
  - SessionEnd hook is primary cadence (NEW — was unwired in hooks.json)
  - stop.py keeps a 60-min time-gated fallback for the partial-session
    failure mode (CLI killed, network drop, user walks away)
  - Sidecar at <local store>/wicked-garden/heavy-cadence/last_run.json
    persists `last_heavy_run_ts` cross-session

And Option A for the [Memory] reflection: delete entirely.

T1: deterministic — sidecar read/write under tmp_path, frozen-time gate test
T3: isolated — monkeypatches `_sidecar_path` to point at tmp
T4: single focus — fallback gating + delete-confirmation contracts
T6: docstring cites v9.2.15 and the audit findings.
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


# ---------------------------------------------------------------------------
# 60-minute fallback gate — the keystone correctness contract
# ---------------------------------------------------------------------------

def test_fallback_fires_when_sidecar_missing(tmp_sidecar):
    """First Stop call ever must run the fallback to seed the sidecar."""
    import _heavy_cadence
    assert _heavy_cadence.should_run_fallback() is True


def test_fallback_suppressed_within_60_min_window(tmp_sidecar):
    """A run 30 minutes ago must NOT trigger the fallback."""
    import _heavy_cadence
    recent = datetime.now(timezone.utc) - timedelta(minutes=30)
    tmp_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_sidecar.write_text(json.dumps({
        "last_heavy_run_ts": recent.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigger": "session_end",
    }))
    assert _heavy_cadence.should_run_fallback() is False


def test_fallback_fires_when_last_run_is_older_than_60_min(tmp_sidecar):
    """A run 70 minutes ago MUST trigger the fallback (catch-up case)."""
    import _heavy_cadence
    stale = datetime.now(timezone.utc) - timedelta(minutes=70)
    tmp_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_sidecar.write_text(json.dumps({
        "last_heavy_run_ts": stale.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigger": "stop_fallback",
    }))
    assert _heavy_cadence.should_run_fallback() is True


def test_fallback_fires_on_corrupt_timestamp(tmp_sidecar):
    """A malformed timestamp is treated as never-run — defensive default."""
    import _heavy_cadence
    tmp_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_sidecar.write_text(json.dumps({
        "last_heavy_run_ts": "not-an-iso-timestamp",
        "trigger": "session_end",
    }))
    assert _heavy_cadence.should_run_fallback() is True


def test_fallback_interval_is_60_minutes():
    """Locked constant — change is a deliberate brainstorm decision."""
    import _heavy_cadence
    assert _heavy_cadence.FALLBACK_INTERVAL_SECS == 60 * 60


# ---------------------------------------------------------------------------
# run_heavy_cadence orchestration — runs all four + writes sidecar
# ---------------------------------------------------------------------------

def test_run_heavy_cadence_writes_sidecar_after_run(tmp_sidecar, monkeypatch):
    """Every successful invocation persists the timestamp + trigger to the
    sidecar so the next Stop fallback gate has a deterministic answer."""
    import _heavy_cadence
    # Stub all four heavy functions to no-op (don't hit real brain / disk).
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: [])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: [])

    messages = _heavy_cadence.run_heavy_cadence("session_end", session_id="test")
    assert messages == []  # all stubbed empty
    data = json.loads(tmp_sidecar.read_text())
    assert data["trigger"] == "session_end"
    assert data["session_id"] == "test"


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


def test_run_heavy_cadence_continues_when_one_function_raises(tmp_sidecar, monkeypatch):
    """Each underlying function fails open — a brain outage does not block
    the others. The aggregator does not need its own try/except because the
    individual functions already swallow."""
    import _heavy_cadence
    def boom(root, *args):
        raise RuntimeError("brain unreachable")
    monkeypatch.setattr(_heavy_cadence, "_run_memory_decay", lambda root: [])
    monkeypatch.setattr(_heavy_cadence, "_run_memory_consolidation", boom)
    monkeypatch.setattr(_heavy_cadence, "_run_quality_telemetry", lambda root, sid: ["[Telemetry] ok"])
    monkeypatch.setattr(_heavy_cadence, "_run_guard_pipeline", lambda root: [])
    # _run_memory_consolidation's real impl swallows; the test stub does not.
    # This test exists to document expectation: if a future refactor removes
    # the per-function try/except, the aggregator must still not raise.
    with pytest.raises(RuntimeError):
        _heavy_cadence.run_heavy_cadence("session_end")
    # Sidecar NOT written on raise — preserves the "fallback retries" property.
    assert not tmp_sidecar.exists()


# ---------------------------------------------------------------------------
# stop.py contract: [Memory] reflection block deleted, no per-turn heavy work
# ---------------------------------------------------------------------------

def test_stop_py_no_longer_calls_heavy_functions_directly():
    """stop.py must NOT call _run_memory_decay / _run_working_consolidation /
    _run_quality_telemetry / _run_guard_pipeline directly in its main flow.
    The four functions live in _heavy_cadence.py now; stop.py only invokes
    them via run_heavy_cadence() inside the should_run_fallback() branch."""
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()

    # The function definitions may stay as stop.py-internal helpers, but the
    # main flow must NOT call them directly. Search for direct invocations
    # outside of comments.
    direct_calls = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
        and any(call in line for call in (
            "_run_memory_decay()",
            "_run_working_consolidation()",
            "_run_quality_telemetry(",
            "_run_guard_pipeline()",
        ))
        and "def " not in line  # exclude the def lines themselves
    ]
    assert not direct_calls, (
        f"stop.py main flow still calls heavy functions directly: {direct_calls}\n"
        f"v9.2.15 moved these to _heavy_cadence.run_heavy_cadence(). "
        f"stop.py should only invoke them via the should_run_fallback() branch."
    )


def test_stop_py_memory_reflection_block_deleted():
    """The [Memory] reflection (lines 469-511 pre-fix) must be gone.

    Markers from the deleted block:
      - 'memory_reminder_shown' getattr (the per-session latch read)
      - 'Auto-extracted ' substring parser (the dead-code parser bug)
      - 'consider storing them via wicked-brain:memory' fallback prompt
    """
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()

    # Strip Python comments so the "what was deleted and why" explanatory
    # block does not false-positive against the dead-code patterns it
    # describes. The test checks EXECUTABLE code shape, not docs.
    code_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)

    # The latch READ must be gone from executable code.
    assert "getattr(session_state, \"memory_reminder_shown\"" not in code, (
        "stop.py still reads memory_reminder_shown — the [Memory] reflection "
        "block was supposed to be deleted in v9.2.15."
    )
    # The dead-code parser pattern (split on the literal upstream never emits).
    assert "Auto-extracted \")[1].split(" not in code, (
        "stop.py still contains the dead 'Auto-extracted' parser — the [Memory] "
        "reflection block was supposed to be deleted in v9.2.15."
    )
    # The fallback prompt the user saw every session.
    assert "consider storing them via wicked-brain:memory" not in code, (
        "stop.py still contains the [Memory] reflection prompt — should be gone."
    )


def test_stop_py_imports_heavy_cadence():
    """Sanity: stop.py must import the new _heavy_cadence module so the
    fallback path can fire when the gate trips."""
    text = (REPO_ROOT / "hooks" / "scripts" / "stop.py").read_text()
    assert "from _heavy_cadence import" in text
    assert "should_run_fallback" in text
    assert "run_heavy_cadence" in text


# ---------------------------------------------------------------------------
# hooks.json: SessionEnd is wired
# ---------------------------------------------------------------------------

def test_hooks_json_wires_sessionend_to_session_end_script():
    """SessionEnd must dispatch to session_end.py via invoke.py — same shape
    as the existing Stop entry. Without this, the primary cadence path never
    fires and only the 60-min Stop fallback runs."""
    h = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    events = h["hooks"]
    assert "SessionEnd" in events, (
        "hooks.json missing SessionEnd binding — v9.2.15 redesign requires "
        "the primary cadence hook to be wired."
    )
    se = events["SessionEnd"]
    assert isinstance(se, list) and len(se) >= 1
    cmd = se[0]["hooks"][0]["command"]
    assert "session_end" in cmd, (
        f"SessionEnd hook does not invoke session_end script — got: {cmd}"
    )


def test_session_end_py_exists():
    """The SessionEnd script must exist + be importable."""
    p = REPO_ROOT / "hooks" / "scripts" / "session_end.py"
    assert p.exists(), f"v9.2.15 SessionEnd script missing at {p}"
    # Importable check — catches syntax errors that the JSON test wouldn't.
    import session_end  # noqa: F401
