"""tests/smaht/test_brain_adapter.py — S4 adapter contract.

The smaht knowledge-layer adapter now queries the routed context backend
(scripts/_context_backend.py) instead of the brain HTTP API directly. This
suite pins:

  * ContextItem mapping from the router's normalized result dicts, including
    the #96 source/scope attribution in metadata and the answering backend in
    ContextItem.source;
  * per-source-file deduplication (many chunks → one item per source);
  * memory items titled by their first content line;
  * fail-open: router returns [] ⇒ adapter returns [] (no raise).

Hermetic: the router is monkeypatched — no estate binary, no brain server.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SMAHT = str(_REPO / "scripts" / "smaht")
if _SMAHT not in sys.path:
    sys.path.insert(0, _SMAHT)

import _context_backend  # noqa: E402  (scripts/ is on sys.path via conftest)
from adapters import brain_adapter  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def _fake_results():
    return [
        {
            "id": "kchunk 1",
            "kind": "chunk",
            "title": "specialist routing",
            "snippet": "the crew workflow routes specialists by archetype",
            "score": 0.03,
            "raw_score": 0.7,
            "source": "wicked-brain://wicked-garden/chunks/extracted/"
                      "skills-crew-workflow-refs-specialist-routing-rules.md/chunk-001.md",
            "scope": "",
            "backend": "estate",
        },
        {
            "id": "kchunk 2",
            "kind": "chunk",
            "title": "specialist routing (cont)",
            "snippet": "crew workflow specialist routing continued",
            "score": 0.02,
            "raw_score": 0.5,
            "source": "wicked-brain://wicked-garden/chunks/extracted/"
                      "skills-crew-workflow-refs-specialist-routing-rules.md/chunk-002.md",
            "scope": "",
            "backend": "estate",
        },
        {
            "id": "mem 9",
            "kind": "memory",
            "title": "Decision: crew workflow gates are fail-closed",
            "snippet": "Decision: crew workflow gates are fail-closed\n\ndetails",
            "score": 0.01,
            "raw_score": 0.4,
            "source": "brain:wicked-garden/doc:mem-abc.md",
            "scope": "brain:wicked-garden/doc:mem-abc.md",
            "backend": "estate",
        },
    ]


def test_query_maps_router_results_to_context_items(monkeypatch):
    monkeypatch.setattr(_context_backend, "search", lambda q, limit=10: _fake_results())
    items = _run(brain_adapter.query("explain the crew workflow specialist routing"))
    assert items, "expected ContextItems from fake router results"
    assert all(i.source == "estate" for i in items)
    # #96 attribution survives into metadata
    chunk_items = [i for i in items if i.metadata.get("type") == "chunk"]
    assert chunk_items
    assert chunk_items[0].metadata["source"].startswith("wicked-brain://wicked-garden/chunks/")
    assert chunk_items[0].metadata["backend"] == "estate"


def test_query_dedupes_chunks_by_source_file(monkeypatch):
    """Two chunks of the same source file collapse to one ContextItem."""
    monkeypatch.setattr(_context_backend, "search", lambda q, limit=10: _fake_results())
    items = _run(brain_adapter.query("crew workflow specialist routing"))
    chunk_items = [i for i in items if i.metadata.get("type") == "chunk"]
    assert len(chunk_items) == 1


def test_query_titles_memories_by_first_content_line(monkeypatch):
    monkeypatch.setattr(_context_backend, "search", lambda q, limit=10: _fake_results())
    items = _run(brain_adapter.query("crew workflow specialist routing"))
    memory_items = [i for i in items if i.metadata.get("type") == "memory"]
    assert len(memory_items) == 1
    assert memory_items[0].title.startswith("Decision: crew workflow gates")
    assert memory_items[0].metadata["scope"] == "brain:wicked-garden/doc:mem-abc.md"


def test_query_titles_chunks_from_source_file(monkeypatch):
    monkeypatch.setattr(_context_backend, "search", lambda q, limit=10: _fake_results())
    items = _run(brain_adapter.query("crew workflow specialist routing"))
    chunk_items = [i for i in items if i.metadata.get("type") == "chunk"]
    assert chunk_items[0].title == "crew / workflow-specialist-routing-rules"


def test_query_returns_empty_when_router_is_empty(monkeypatch):
    monkeypatch.setattr(_context_backend, "search", lambda q, limit=10: [])
    assert _run(brain_adapter.query("anything")) == []


def test_query_fails_open_when_router_raises(monkeypatch):
    def boom(q, limit=10):
        raise RuntimeError("router exploded")

    monkeypatch.setattr(_context_backend, "search", boom)
    assert _run(brain_adapter.query("anything")) == []


def test_query_skips_stop_word_only_prompts(monkeypatch):
    called = {"n": 0}

    def spy(q, limit=10):
        called["n"] += 1
        return []

    monkeypatch.setattr(_context_backend, "search", spy)
    assert _run(brain_adapter.query("the a an is to")) == []
    assert called["n"] == 0  # no keywords → no backend call


def test_extract_keywords_preserves_prompt_order():
    kw = brain_adapter._extract_keywords("explain the crew workflow specialist routing")
    assert kw == "explain crew workflow"
