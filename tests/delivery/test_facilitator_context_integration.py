"""Integration tests for the issue #461 facilitator-context wiring.

Covers the two additive wiring edits that connect
``scripts/delivery/process_memory.py`` to:

1. The session bootstrap (``hooks/scripts/bootstrap.py``) — unresolved
   action items aged >= 2 sessions should surface as a ``[ProcessMemory]``
   briefing line.
2. The retro command's action-item scanner
   (``scripts/crew/retro_action_items.py``) — action-item bullets in the
   retro markdown should be appended to ``process-memory.json`` via
   ``add_action_item``.

Acceptance criteria mapping:

- **AC-1**: ``test_bootstrap_facilitator_context_surfaces_aged_ai``
- **AC-2**: ``test_retro_action_items_populate_process_memory``
- **AC-3**: ``test_bootstrap_facilitator_context_silent_when_no_aging_ai``
- **AC-4**: ``test_retro_action_items_leaves_markdown_untouched``

Each test redirects ``get_local_path`` into an isolated ``tmp_path`` so
no global state leaks between tests.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "delivery"))
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "scripts"))


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect get_local_path so process-memory writes stay in tmp_path.

    Mirrors the sandbox fixture in ``test_process_memory.py``. Both the
    source ``_domain_store.get_local_path`` and the copy imported into
    ``delivery.process_memory`` at module load are re-bound.
    """
    root = tmp_path / "local"

    def _fake_get_local_path(domain: str, *subpath: str) -> Path:
        p = root / domain
        for part in subpath:
            p = p / part
        p.mkdir(parents=True, exist_ok=True)
        return p

    import _domain_store

    monkeypatch.setattr(_domain_store, "get_local_path", _fake_get_local_path)

    from delivery import process_memory as pm

    importlib.reload(pm)
    monkeypatch.setattr(pm, "get_local_path", _fake_get_local_path)
    return pm, tmp_path


# ---------------------------------------------------------------------------
# AC-1 / AC-3: bootstrap facilitator context
# ---------------------------------------------------------------------------


def _import_bootstrap(monkeypatch: pytest.MonkeyPatch):
    """Import hooks/scripts/bootstrap.py as a module for direct function calls."""
    import importlib.util

    path = _REPO_ROOT / "hooks" / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("bootstrap_under_test", path)
    assert spec and spec.loader, "bootstrap.py must be importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_facilitator_context_surfaces_aged_ai(
    sandbox, monkeypatch: pytest.MonkeyPatch
):
    """AC-1: a project with unresolved AI-001 (age >= 2) produces a briefing
    line that mentions AI-001."""
    pm, _ = sandbox

    # Seed process_memory with an AI that is >= 2 sessions old. The first
    # add_action_item creates AI-001 with age_sessions=1. A subsequent
    # touch_action_item with a different session_id increments the counter.
    project = "demo-project"
    pm.add_action_item(
        project,
        title="Wire PagerDuty alerts",
        description="Follow-up from retro",
        source_session="sess-initial",
    )
    pm.touch_action_item(project, "AI-001", "sess-later")

    # AI should now qualify as aging.
    aging = pm.aging_action_items(project)
    assert aging, "precondition: AI-001 should be aging after touch"
    assert aging[0]["id"] == "AI-001"

    bootstrap = _import_bootstrap(monkeypatch)

    # Ensure the bootstrap's lazy import picks up our sandboxed process_memory.
    # The helper inserts scripts/delivery into sys.path and imports
    # `process_memory`; we just need to make sure no stale copy is cached.
    sys.modules.pop("process_memory", None)

    note = bootstrap._check_facilitator_context(project)
    assert note is not None, "AC-1: bootstrap should surface aging AIs"
    assert "[ProcessMemory]" in note
    assert "AI-001" in note
    assert "Wire PagerDuty alerts" in note


def test_bootstrap_facilitator_context_silent_when_no_aging_ai(
    sandbox, monkeypatch: pytest.MonkeyPatch
):
    """AC-3: with no aging AIs, the helper returns None (fail-open) so the
    existing briefing format is unchanged."""
    pm, _ = sandbox
    project = "quiet-project"
    # Fresh action item — age_sessions is 1, below the >=2 threshold.
    pm.add_action_item(
        project, title="Should not surface", source_session="sess-1"
    )
    bootstrap = _import_bootstrap(monkeypatch)
    sys.modules.pop("process_memory", None)
    assert bootstrap._check_facilitator_context(project) is None


def test_bootstrap_facilitator_context_no_project(sandbox, monkeypatch: pytest.MonkeyPatch):
    """Helper must no-op when no active project is passed."""
    bootstrap = _import_bootstrap(monkeypatch)
    assert bootstrap._check_facilitator_context(None) is None
    assert bootstrap._check_facilitator_context("") is None


def test_bootstrap_facilitator_context_missing_process_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """AC-3 fail-open: when process_memory cannot be imported, the helper
    returns None rather than propagating the ImportError."""
    bootstrap = _import_bootstrap(monkeypatch)

    # Pretend the delivery module disappeared. Blocking the import at
    # sys.modules AND raising from the underlying import hook exercises
    # both branches of the lazy-import guard.
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "process_memory":
            raise ImportError("simulated missing module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    sys.modules.pop("process_memory", None)
    assert bootstrap._check_facilitator_context("any-project") is None


# ---------------------------------------------------------------------------
# AC-2 / AC-4: retro action-item auto-population
# ---------------------------------------------------------------------------


def _import_retro_scanner():
    """Import the retro action-items backing script."""
    import importlib.util

    path = _REPO_ROOT / "scripts" / "crew" / "retro_action_items.py"
    spec = importlib.util.spec_from_file_location("retro_action_items_under_test", path)
    assert spec and spec.loader, "retro_action_items.py must be importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retro_action_items_populate_process_memory(sandbox, tmp_path: Path):
    """AC-2: running the retro backing script with markdown containing
    ``## Action Items\\n- [ ] test AI`` causes process_memory.json to gain a
    new AI-NNN entry."""
    pm, _ = sandbox
    scanner = _import_retro_scanner()

    retro_md = tmp_path / "retro.md"
    retro_md.write_text(
        "# Retrospective: demo\n"
        "\n"
        "## Action Items\n"
        "- [ ] test AI\n"
        "- [ ] second item with more detail\n"
        "\n"
        "## Other Section\n"
        "- [ ] not an action item\n",
        encoding="utf-8",
    )

    project = "demo-project"
    summary = scanner.populate_action_items(
        project, retro_md, session_id="sess-retro"
    )

    assert summary["items_found"] == 2, (
        "scanner should find exactly the two bullets under Action Items, "
        "not the bullet under Other Section"
    )
    assert len(summary["items_added"]) == 2
    assert summary["process_memory_available"] is True
    assert summary["errors"] == []

    items = pm.list_action_items(project)
    titles = [i["title"] for i in items]
    assert "test AI" in titles
    assert "second item with more detail" in titles
    # Every new AI starts at AI-001 and walks forward.
    ids = sorted(i["id"] for i in items)
    assert ids == ["AI-001", "AI-002"]
    # source_session must be stamped.
    assert all(i["source_session"] == "sess-retro" for i in items)


def test_retro_action_items_leaves_markdown_untouched(sandbox, tmp_path: Path):
    """AC-4: scanning a retro markdown file must not modify it."""
    scanner = _import_retro_scanner()
    retro_md = tmp_path / "retro.md"
    original = (
        "# Retrospective\n"
        "\n"
        "## Action Items\n"
        "- [ ] audit the gate policy\n"
    )
    retro_md.write_text(original, encoding="utf-8")
    mtime_before = retro_md.stat().st_mtime

    scanner.populate_action_items("demo", retro_md, session_id="sess-1")

    assert retro_md.read_text(encoding="utf-8") == original
    assert retro_md.stat().st_mtime == mtime_before


def test_retro_action_items_no_section_is_noop(sandbox, tmp_path: Path):
    """A retro with no Action Items heading adds nothing (and does not error)."""
    pm, _ = sandbox
    scanner = _import_retro_scanner()
    retro_md = tmp_path / "retro.md"
    retro_md.write_text(
        "# Retrospective\n\n## Summary\n\n- just a bullet\n", encoding="utf-8"
    )
    summary = scanner.populate_action_items("demo", retro_md, session_id="s")
    assert summary["items_found"] == 0
    assert summary["items_added"] == []
    assert pm.list_action_items("demo") == []


def test_retro_action_items_missing_file_fails_open(sandbox, tmp_path: Path):
    """Missing retro markdown surfaces an error but does not raise."""
    pm, _ = sandbox
    scanner = _import_retro_scanner()
    summary = scanner.populate_action_items(
        "demo", tmp_path / "nope.md", session_id="s"
    )
    assert summary["items_found"] == 0
    assert summary["items_added"] == []
    assert any("not found" in err for err in summary["errors"])


def test_retro_action_items_fails_open_without_process_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When delivery.process_memory cannot be imported, the scanner must
    still report items_found but skip the add_action_item calls."""
    scanner = _import_retro_scanner()
    monkeypatch.setattr(scanner, "_load_process_memory", lambda: None)

    retro_md = tmp_path / "retro.md"
    retro_md.write_text(
        "## Action Items\n- [ ] ensure fail-open works\n", encoding="utf-8"
    )
    summary = scanner.populate_action_items(
        "demo", retro_md, session_id="s"
    )
    assert summary["items_found"] == 1
    assert summary["items_added"] == []
    assert summary["process_memory_available"] is False
    assert summary["errors"] == []


# ---------------------------------------------------------------------------
# Parser unit coverage — supports AC-2 via the extractor
# ---------------------------------------------------------------------------


def test_scan_action_items_handles_mixed_bullets():
    scanner = _import_retro_scanner()
    md = (
        "## Action Items\n"
        "- [ ] open checkbox\n"
        "- [x] closed checkbox\n"
        "* plain star bullet\n"
        "- plain dash bullet\n"
        "\n"
        "Not a bullet, should be ignored.\n"
        "## Follow-up Items\n"
        "- [ ] not collected — different section\n"
    )
    items = scanner.scan_action_items(md)
    titles = [i["title"] for i in items]
    assert titles == [
        "open checkbox",
        "closed checkbox",
        "plain star bullet",
        "plain dash bullet",
    ]


def test_scan_action_items_handles_no_heading():
    scanner = _import_retro_scanner()
    assert scanner.scan_action_items("# Just a doc\n- nothing here\n") == []
