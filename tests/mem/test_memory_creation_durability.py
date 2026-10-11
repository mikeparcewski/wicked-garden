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
    "Too short.",
    "   ",
])
def test_store_rejects_mechanical_non_learnings(session, capsys, content):
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False, out
    assert session == []


@pytest.mark.parametrize("content", [
    "Bind the dev server to 127.0.0.1 rather than localhost, because localhost resolves to ::1 first on macOS.",
    "PID 1 in a container does not get default signal handlers, so the entrypoint must trap SIGTERM itself.",
    "An ill-formed frontmatter block makes the skill loader drop every key, so strict-parse it in CI.",
    "Batching works well only when each item is idempotent, because a retry replays the whole batch.",
    "Run 3 retries at most before dead-lettering, since the fourth attempt has never succeeded in practice.",
])
def test_gate_keeps_durable_rules_that_look_like_ids(content):
    assert estate_memory.durability_rejects(content) == []


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


# ── provenance + answer labels (DES-memory-vs-knowledge G2/G3) ────────────────

def test_store_refuses_a_source_cited_claim_as_knowledge(session, capsys):
    estate_memory.do_store({
        "content": "CoreAdapter arms WICKED_BUS_EXEC before it spawns a worker, so the child inherits the bus.",
        "source": "wicked-crew:packages/crew/src/core/adapter.ts",
    })
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False and "knowledge" in out["reason"] and "`write`" in out["reason"]
    assert session == []


def test_sources_labels_each_side_and_passes_the_repo_intent(monkeypatch, tmp_path, capsys):
    repo = tmp_path / "wicked" / "wicked-bus"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    monkeypatch.delenv("WICKED_RUN_PROJECT", raising=False)
    calls = []

    def fake_call(tool, arguments=None, timeout=8.0, **_kw):
        calls.append((tool, arguments))
        if tool == "knowledge.recall":
            return {"items": [{"body_snippet": "cas gc", "source": "wicked-bus:lib/cas.js"}]}
        return {"items": [{"memory_id": "m1", "content": "fail closed", "kind": "fact",
                           "created_at": 1760054400, "scope": "project:wicked-bus"}]}

    monkeypatch.setattr(_estate_client, "call", fake_call)
    estate_memory.do_sources({"query": "cas gc fail closed"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    m_args = dict(calls)["memory.recall"]
    assert m_args["intent"] == {"repo": "wicked-bus", "project": "wicked"}
    assert m_args["scope"] == "project:wicked-bus"
    assert out["memories"][0]["label"] == "memory · fact · 2025-10-10 · project:wicked-bus"
    assert out["knowledge"][0]["label"] == "knowledge · src wicked-bus:lib/cas.js"


# ── w9-memfix2 (codex post-merge review) ──────────────────────────────────────

@pytest.mark.parametrize("content", [
    "Keep SQLite at 3.35.0 or newer because the insert path needs RETURNING; older builds fail at prepare.",
    "The CRC32 polynomial is edb88320 (reflected), so the hand-rolled table must use it, not 04c11db7.",
    "Overlay scrims use #ff000080 so the warning tint stays 50% transparent over every theme background.",
])
def test_gate_keeps_version_constraints_and_hex_constants(content):
    assert estate_memory.durability_rejects(content) == []


@pytest.mark.parametrize("content", [
    "We released 2.4.1 to npm and the smoke test passed on both runners again.",
])
def test_gate_still_rejects_release_narration(content):
    assert estate_memory.durability_rejects(content) != []


def _git_checkout(root):
    (root / ".git").mkdir(parents=True)
    return root


def test_project_scope_is_the_checkout_not_the_subdirectory(monkeypatch, tmp_path):
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    repo = _git_checkout(tmp_path / "app")
    (repo / "src" / "deep").mkdir(parents=True)
    monkeypatch.chdir(repo / "src" / "deep")
    assert _estate_client.project_scope() == "project:app"


def test_project_scope_of_a_worktree_is_its_main_checkout(monkeypatch, tmp_path):
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    main = _git_checkout(tmp_path / "wicked-estate")
    wt = tmp_path / "worktrees" / "run-1234"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'run-1234'}\n")
    monkeypatch.chdir(wt)
    assert _estate_client.project_scope() == "project:wicked-estate"


def test_configured_project_scope_wins_for_store_and_recall(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WICKED_ESTATE_MEMORY_SCOPE", "project:acme-app")
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(_estate_client, "call",
                        lambda tool, arguments=None, timeout=8.0, **kw: calls.append((tool, arguments))
                        or {"memory_id": "m", "items": []})
    estate_memory.do_store({"content": _assistant_statements()[-1]})
    estate_memory.do_recall({"query": "codesign"})
    capsys.readouterr()
    scopes = [a.get("scope") for _t, a in calls]
    assert scopes == ["project:acme-app", "project:acme-app"], calls


def test_shim_refuses_unapprovable_knowledge_proposals(monkeypatch):
    seen = []
    monkeypatch.setattr(_estate_client, "call_raw", lambda *a, **k: seen.append(a) or {})
    out = _estate_client.propose("knowledge", {"content": "c", "source": "r:p"}, {"project": "wicked"})
    assert out["ok"] is False and out["code"] == -32602 and "not approvable" in out["reason"]
    assert seen == []


# ── w9-memfix3 (codex re-review of #1279): heuristics advise, only the obvious is refused ──

@pytest.mark.parametrize("content", [
    "Keep SQLite >= 3.35.0 because RETURNING is required; deployed instances must use the same minimum.",
    "Use CRC32 polynomial edb88320 when validating a database commit; readers must agree on the checksum.",
])
def test_durable_rules_with_ids_store_with_warnings(session, capsys, content):
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True, out
    assert [c for _s, c in session] == [content]


def test_ids_and_versions_are_advisory_warnings(session, capsys):
    content = "Reverted commit 3e7f2539ab because the deliver gate double-pushed the branch on retry."
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True and out["warnings"], out


@pytest.mark.parametrize("content", [
    "3e7f2539ab1c4d5e6f708192a3b4c5d6e7f80912",
    "v0.29.1",
])
def test_a_bare_id_is_refused(session, capsys, content):
    estate_memory.do_store({"content": content, "kind": "fact"})
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False and session == []


def test_relative_worktree_resolves_to_its_main_checkout(monkeypatch, tmp_path):
    monkeypatch.delenv("WICKED_ESTATE_MEMORY_SCOPE", raising=False)
    main = _git_checkout(tmp_path / "app")
    (main / ".git" / "worktrees" / "run").mkdir(parents=True)
    (main / ".git" / "worktrees" / "run" / "commondir").write_text("../..\n")
    wt = main / "trees" / "run"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/run\n")
    monkeypatch.chdir(wt)
    assert _estate_client.project_scope() == "project:app"


@pytest.mark.parametrize("content", [
    "Fixed in 3e7f2539ab: the deliver gate no longer double-pushes the branch.",
    "PR #880 pins estate for the core main branch; merge it after CI is green.",
    "The rig daemon restarted as pid 48668 and the health check is green again.",
    "Pin moved to 1f3a9c2e7b4d5a6f8e9c0b1a2d3e4f5a6b7c8d9e so main builds against the fix.",
])
def test_ids_inside_a_body_warn_but_do_not_block(content):
    """Operator ruling (do not overcomplicate): id/version/SHA heuristics are advisory;
    the skill's three-month test is the judgment."""
    assert estate_memory.durability_rejects(content) == []
    assert estate_memory.durability_warnings(content)
