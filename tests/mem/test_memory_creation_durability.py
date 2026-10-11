"""tests/mem/test_memory_creation_durability.py — stores hold learnings, not narration.

One fixture transcript (``fixtures/narration_transcript.jsonl``) carries three
narration lines ("I'll retry", "shipped 0.7.26 today", "going to guess a sixth
time") and one stated gotcha. Every memory-creating path a session drives is
run over it, hermetically (estate and the bus are faked, HOME is a tmp dir):

1. the Stop hook, handed the transcript exactly as Claude Code hands it;
2. the capture path (``estate_memory.py capture-batch``), handed every
   assistant statement as a candidate, as an agent that skipped the skill's
   judgment would.

The whole session must yield exactly one memory: the gotcha.
"""

import io
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS = _REPO_ROOT / "hooks" / "scripts"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "narration_transcript.jsonl"
for p in (str(_REPO_ROOT / "scripts"), str(_HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _bus  # noqa: E402
import _estate_client  # noqa: E402
from mem import estate_memory  # noqa: E402

GOTCHA_KEY = "re-sign it with codesign"


def _assistant_statements():
    out = []
    for line in _FIXTURE.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("type") == "assistant":
            out.extend(b["text"] for b in entry["message"]["content"] if b.get("type") == "text")
    return out


def _isolate_session_state(monkeypatch, tmp_path):
    """SessionState lives under TMPDIR keyed by CLAUDE_SESSION_ID: pin both."""
    tmp = tmp_path / "tmp"
    tmp.mkdir(exist_ok=True)
    monkeypatch.setenv("TMPDIR", str(tmp))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "w9-fixture")


@pytest.fixture
def session(monkeypatch, tmp_path):
    """Hermetic session: fake estate + bus; every would-be memory is recorded."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("CLAUDE_CWD", str(tmp_path))
    monkeypatch.setenv("WICKED_MEM_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("WG_OUTGOV", "off")
    _isolate_session_state(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)

    memories = []

    def fake_call(tool, arguments=None, timeout=8.0, **_kw):
        if tool == "memory.capture":
            memories.append(("estate", (arguments or {}).get("content", "")))
            return {"memory_id": f"mem-{len(memories)}"}
        return None

    def fake_emit(event_type, payload=None, *a, **kw):
        # A fact event is a memory: the auto-memorize drain stores each one.
        if event_type == "wicked.garden.fact.extracted":
            memories.append(("fact-event", (payload or {}).get("content", "")))
        return True

    monkeypatch.setattr(_estate_client, "call", fake_call)
    monkeypatch.setattr(_bus, "emit_event", fake_emit)
    monkeypatch.setattr(_bus, "_check_available", lambda: False)
    return memories


def _run_stop_hook(monkeypatch, capsys):
    import stop

    stdin = json.dumps({"session_id": "w9-fixture", "transcript_path": str(_FIXTURE)})
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    stop.main()
    capsys.readouterr()


def test_session_yields_only_the_stated_gotcha(session, monkeypatch, capsys):
    _run_stop_hook(monkeypatch, capsys)

    batch = {"memories": [{"content": s, "kind": "fact"} for s in _assistant_statements()]}
    estate_memory.do_capture_batch(batch)
    report = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    stored = [content for _src, content in session]
    narration = [c for c in stored if GOTCHA_KEY not in c]
    assert narration == [], f"narration became memory: {session}"
    assert len(stored) == 1 and GOTCHA_KEY in stored[0], session
    assert report["stored"] == 1 and report["failed"] == 3, report


@pytest.mark.parametrize("content", [
    "I'll retry the push with the pinned token and check the result.",
    "We shipped 0.7.26 today and the release notes are up.",
    "No luck on the port yet, so I'm going to guess a sixth time and try 8086.",
    "Fixed in 3e7f2539ab: the deliver gate no longer double-pushes the branch.",
    "PR #880 pins estate for the core main branch; merge it after CI is green.",
    "The rig daemon restarted as pid 48668 and the health check is green again.",
    "Too short.",
    "   ",
])
def test_store_rejects_mechanical_non_learnings(session, capsys, content):
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False, out
    assert session == []


def test_store_keeps_a_stated_rule(session, capsys):
    content = _assistant_statements()[-1]
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True, out
    assert [c for _s, c in session] == [content]


# ── pre_compact: real in-progress state only, always project-scoped ──────────

def _run_pre_compact(monkeypatch, capsys, tasks):
    import pre_compact
    from crew import _task_reader

    monkeypatch.setattr(_task_reader, "list_in_progress_tasks", lambda sid, limit=10: list(tasks))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "w9-fixture"})))
    pre_compact.main()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_pre_compact_writes_nothing_without_in_progress_tasks(session, monkeypatch, capsys):
    """A turn count alone is not state (it wrote 147 "WIP snapshot … Turn Count 4")."""
    from _session import SessionState

    state = SessionState.load()
    state.update(turn_count=4)
    state.save()
    out = _run_pre_compact(monkeypatch, capsys, [])
    assert session == []
    assert out["continue"] is True and "was saved" not in out["systemMessage"]


def test_pre_compact_saves_in_progress_tasks_under_the_project_scope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    _isolate_session_state(monkeypatch, tmp_path)
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    proj = tmp_path / "demo-repo"
    proj.mkdir()
    monkeypatch.chdir(proj)
    calls = []
    monkeypatch.setattr(_estate_client, "call",
                        lambda tool, arguments=None, timeout=8.0, **kw: calls.append((tool, arguments))
                        or {"memory_id": "m1"})
    out = _run_pre_compact(monkeypatch, capsys, ["Wire the recall scope default"])
    assert [t for t, _a in calls] == ["memory.capture"]
    args = calls[0][1]
    assert args["scope"] == "project:demo-repo" and args["tier"] == "working"
    assert "Wire the recall scope default" in args["content"]
    assert "Turn Count" not in args["content"]
    assert "was saved" in out["systemMessage"]
