"""tests/mem/test_auto_memorize.py — the estate auto-memorize loop (task #76).

Brain's server ran the auto-memorize subscriber; garden runs it now:
``scripts/mem/auto_memorize.py`` drains ``wicked.garden.fact.extracted`` from
wicked-bus (durable cursor, native delivery_attempts/dead_letters tables) and
persists promoted facts to wicked-estate via the mem backend. The emitter side
(``scripts/_brain_ingest/session_fact_extractor.py``) gains the transcript
source that fixes the starvation (zero fact events ever emitted — native task
records exist for almost no session).

Layers:

  * Hermetic unit tests (always run): the promoteFact policy port (skip
    rules, importance→tier, fact-type→estate-kind), brain-compatible content
    hashing, transcript extraction, and the per-session emitted ledger.

  * Live e2e tests (``slow``; skipped without npx/wicked-bus/estate): the
    full loop on temp bus + scratch estate stores — emit→drain→estate,
    dedup (same content twice → ONE memory), retry budget → native DLQ, and
    operator ``dlq replay`` → estate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import _estate_client  # noqa: E402
from _brain_ingest import session_fact_extractor as sfe  # noqa: E402
from mem import auto_memorize  # noqa: E402

_AUTO = _REPO_ROOT / "scripts" / "mem" / "auto_memorize.py"
_BACKEND = _REPO_ROOT / "scripts" / "mem" / "estate_memory.py"


# ── promoteFact policy (pure port of brain's memory-promoter.mjs) ────────────

def _event(payload, event_type="wicked.garden.fact.extracted", **kw):
    base = {"event_id": 1, "event_type": event_type, "domain": "wicked-garden",
            "subdomain": "", "payload": json.dumps(payload),
            "emitted_at": 1700000000000}
    base.update(kw)
    return base


def test_promote_decision_maps_to_semantic_fact():
    memory, err = auto_memorize.promote_fact(_event({
        "type": "decision",
        "content": "we decided to rebuild auto-memorize on estate",
        "entities": ["wicked-estate"],
        "session_id": "s1",
    }))
    assert err is None
    assert memory["kind"] == "fact" and memory["tier"] == "semantic"
    assert "wicked-estate" in memory["about"] and "decision" in memory["about"]
    assert memory["content_hash"]


def test_promote_discovery_maps_to_episodic_episode():
    memory, err = auto_memorize.promote_fact(_event({
        "type": "discovery", "content": "turns out the cursor was never registered",
    }))
    assert err is None
    assert memory["kind"] == "episode" and memory["tier"] == "episodic"


@pytest.mark.parametrize("payload,reason_part", [
    ({"type": "context", "content": "the system uses sqlite everywhere"}, "not auto-promoted"),
    ({"type": "decision"}, "missing payload.content"),
    ({"type": "decision", "content": "too short"}, "too short"),
])
def test_promote_skip_rules(payload, reason_part):
    memory, reason = auto_memorize.promote_fact(_event(payload))
    assert memory is None and reason_part in reason


def test_promote_rejects_wrong_event_type():
    memory, reason = auto_memorize.promote_fact(
        _event({"type": "decision", "content": "x" * 30}, event_type="wicked.other.thing.done"))
    assert memory is None and "event_type" in reason


def test_content_hash_is_normalization_stable():
    a = auto_memorize.content_hash("We Decided   to USE\n estate")
    b = auto_memorize.content_hash("we decided to use estate")
    assert a == b
    assert a != auto_memorize.content_hash("we decided to use brain")


# ── transcript extraction (the starvation fix) ───────────────────────────────

def _write_transcript(path: Path, texts):
    lines = []
    for i, text in enumerate(texts):
        role = "assistant" if i % 2 else "user"
        lines.append(json.dumps({
            "type": role,
            "message": {"content": [{"type": "text", "text": text}]},
        }))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_transcript_facts_extracted(tmp_path):
    t = tmp_path / "transcript.jsonl"
    _write_transcript(t, [
        "let's think about storage options",
        "We decided to use the estate memory store for all session facts.",
        "anything else?",
        "Turns out the emitter was starved because no task files ever existed.",
    ])
    facts = sfe.extract_transcript_facts(str(t), limit=10)
    types = {f.type for f in facts}
    assert "decision" in types and "discovery" in types
    assert all(f.source == "transcript" for f in facts)


def test_extract_session_facts_merges_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))  # no task records
    t = tmp_path / "tr.jsonl"
    _write_transcript(t, ["We decided to use transcripts as the fact source."])
    facts = sfe.extract_session_facts("sess-x", limit=10, transcript_path=str(t))
    assert facts and facts[0].source == "transcript"


def test_transcript_missing_file_fails_open(tmp_path):
    assert sfe.extract_transcript_facts(str(tmp_path / "nope.jsonl"), 10) == []


def test_emitted_ledger_filters_per_session(tmp_path, monkeypatch):
    monkeypatch.setenv("WICKED_MEM_LEDGER_DIR", str(tmp_path))
    fact = sfe.SessionFact(id="", type="decision", content="we decided on X for Y reasons")
    assert sfe.filter_unemitted([fact], "sess-1") == [fact]
    sfe.mark_emitted([fact], "sess-1")
    assert sfe.filter_unemitted([fact], "sess-1") == []          # same session: filtered
    assert sfe.filter_unemitted([fact], "sess-2") == [fact]      # other session: passes


# ── dedup ledger ─────────────────────────────────────────────────────────────

def test_dedup_ledger_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("WICKED_MEM_LEDGER_DIR", str(tmp_path))
    assert auto_memorize._load_ledger() == {}
    auto_memorize._save_ledger({"abc": "mem-1"})
    assert auto_memorize._load_ledger() == {"abc": "mem-1"}


# ── live e2e (slow) ──────────────────────────────────────────────────────────

_ESTATE_PRESENT = _estate_client.resolve_mcp_bin() is not None
_NPX_PRESENT = shutil.which("npx") is not None


def _env(tmp: Path):
    env = dict(os.environ)
    env.update({
        "WICKED_BUS_DATA_DIR": str(tmp / "bus"),
        "WICKED_MEM_LEDGER_DIR": str(tmp / "ledger"),
        "WICKED_MEMORY_DB": str(tmp / "estate" / "memory.db"),
        "WICKED_KNOWLEDGE_DB": str(tmp / "estate" / "knowledge.db"),
        "WICKED_XEDGE_DB": str(tmp / "estate" / "xedge.db"),
        "WICKED_ESTATE_DB": ":memory:",
        "WICKED_ESTATE_PERSISTENT": "0",
    })
    (tmp / "estate").mkdir(parents=True, exist_ok=True)
    return env


def _run_py(env, script, *args):
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _emit_fact(env, payload):
    proc = subprocess.run(
        ["npx", "--yes", "wicked-bus", "emit",
         "--type", "wicked.garden.fact.extracted",
         "--domain", "wicked-garden",
         "--payload", json.dumps(payload)],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.slow
@pytest.mark.skipif(not (_ESTATE_PRESENT and _NPX_PRESENT),
                    reason="needs wicked-estate-mcp and npx/wicked-bus")
def test_live_emit_drain_store_and_dedup(tmp_path):
    env = _env(tmp_path)

    # First drain registers the cursor at 'latest' — no history replay.
    first = _run_py(env, _AUTO, "drain", "{}")
    assert first["ok"] is True and first["drained"] == 0

    _emit_fact(env, {"type": "decision",
                     "content": "we decided to rebuild the auto-memorize loop on estate",
                     "entities": ["wicked-estate"], "session_id": "e2e"})
    result = _run_py(env, _AUTO, "drain", "{}")
    assert result["stored"] == 1 and result["pending_retry"] is False

    recalled = _run_py(env, _BACKEND, "recall",
                       json.dumps({"query": "rebuild auto-memorize loop"}))
    assert any("auto-memorize" in i.get("content", "") for i in recalled["items"])

    # Same content again (different whitespace/case) + a non-promotable type.
    _emit_fact(env, {"type": "decision",
                     "content": "We DECIDED to rebuild   the auto-memorize loop on estate",
                     "session_id": "e2e-2"})
    _emit_fact(env, {"type": "context", "content": "the system uses sqlite everywhere"})
    result = _run_py(env, _AUTO, "drain", "{}")
    assert result["deduped"] == 1 and result["skipped"] == 1 and result["stored"] == 0

    # Dedup proven at the store: exactly ONE memory exists.
    coverage = _run_py(env, _BACKEND, "review", "{}")
    assert coverage["coverage"]["total"] == 1


@pytest.mark.slow
@pytest.mark.skipif(not (_ESTATE_PRESENT and _NPX_PRESENT),
                    reason="needs wicked-estate-mcp and npx/wicked-bus")
def test_live_retry_budget_dead_letters_then_operator_replay(tmp_path):
    env = _env(tmp_path)
    _run_py(env, _AUTO, "drain", "{}")  # register cursor

    _emit_fact(env, {"type": "discovery",
                     "content": "turns out estate can be down when the drain runs",
                     "session_id": "e2e-dlq"})

    # Break estate: a real file that is not an MCP server → handshake fails.
    broken = dict(env, WICKED_ESTATE_MCP_BIN="/usr/bin/false" if os.name != "nt" else env["COMSPEC"])
    for attempt in (1, 2):
        result = _run_py(broken, _AUTO, "drain", "{}")
        assert result["pending_retry"] is True, f"attempt {attempt} should retry"
        assert result["dead_lettered"] == 0
    result = _run_py(broken, _AUTO, "drain", "{}")
    assert result["dead_lettered"] == 1 and result["pending_retry"] is False

    # Native DLQ visibility: wicked-bus dlq list sees the row.
    proc = subprocess.run(
        ["npx", "--yes", "wicked-bus", "dlq", "list", "--json"],
        capture_output=True, text=True, timeout=120, env=env,
    )
    dlq = json.loads(proc.stdout.strip().splitlines()[-1])
    assert dlq["count"] == 1
    dl = dlq["dead_letters"][0]
    assert dl["event_type"] == "wicked.garden.fact.extracted"
    assert dl["attempts"] == 3

    # Operator replay with estate healthy → memory lands, DLQ empties.
    proc = subprocess.run(
        ["npx", "--yes", "wicked-bus", "dlq", "replay", "--dl-id", str(dl["dl_id"])],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    result = _run_py(env, _AUTO, "drain", "{}")
    assert result["replayed"] == 1 and result["replay_failed"] == 0

    recalled = _run_py(env, _BACKEND, "recall",
                       json.dumps({"query": "estate can be down when the drain runs"}))
    assert any("estate can be down" in i.get("content", "") for i in recalled["items"])
    proc = subprocess.run(
        ["npx", "--yes", "wicked-bus", "dlq", "list", "--json"],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert json.loads(proc.stdout.strip().splitlines()[-1])["count"] == 0
