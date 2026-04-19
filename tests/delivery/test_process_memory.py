"""Tests for scripts/delivery/process_memory.py (issue #447).

Coverage:
- Kaizen CRUD (create, list, update, lifecycle transitions)
- Action-item CRUD (create, touch, resolve)
- Aging detection with >= 2-session threshold
- Uncertainty gate pass/fail with mocked drift.classify responses
- Uncertainty gate fail-open when drift module is absent
- Facilitator context one-shot read
- Markdown rendering
- Path-traversal protection on project names

Tests run against an isolated tmp-path sandbox so no global state leaks.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Callable

import pytest

# Add scripts/ to sys.path so `from delivery import process_memory` works.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect get_local_path so process memory lives inside tmp_path.

    We patch `_domain_store.get_local_path` AND the copy that
    process_memory.py imported at module load (via `from _domain_store
    import get_local_path`). Both names are re-bound so all paths stay
    inside the sandbox for the duration of the test.
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

    # Re-import process_memory fresh so it picks up the patched helper.
    # Using reload keeps the module's internal state isolated per test.
    import importlib
    from delivery import process_memory as pm

    importlib.reload(pm)
    monkeypatch.setattr(pm, "get_local_path", _fake_get_local_path)
    return pm, tmp_path


# ---------------------------------------------------------------------------
# Kaizen CRUD
# ---------------------------------------------------------------------------


def test_add_kaizen_assigns_stable_id_and_timestamps(sandbox):
    pm, _ = sandbox
    item = pm.add_kaizen(
        "proj-a",
        title="Reduce review churn",
        hypothesis="Pairing during design reduces rework",
        waste_type="defects",
        source_session="sess-1",
    )
    assert item["id"] == "KZN-001"
    assert item["status"] == "proposed"
    assert item["waste_type"] == "defects"
    assert item["created_at"]
    assert item["updated_at"]

    second = pm.add_kaizen(
        "proj-a",
        title="Cut build-phase waiting",
        hypothesis="Async gates unblock",
        waste_type="waiting",
    )
    assert second["id"] == "KZN-002", "IDs must be monotonic within a project"


def test_add_kaizen_rejects_invalid_waste_type(sandbox):
    pm, _ = sandbox
    with pytest.raises(ValueError):
        pm.add_kaizen(
            "proj-a",
            title="bogus",
            hypothesis="none",
            waste_type="not-a-real-waste",
        )


def test_add_kaizen_rejects_invalid_uncertainty(sandbox):
    pm, _ = sandbox
    with pytest.raises(ValueError):
        pm.add_kaizen(
            "proj-a",
            title="bogus",
            hypothesis="none",
            waste_type="waiting",
            uncertainty="mystical",
        )


def test_update_kaizen_transitions_status(sandbox):
    pm, _ = sandbox
    item = pm.add_kaizen(
        "proj-a",
        title="t",
        hypothesis="h",
        waste_type="waiting",
    )
    updated = pm.update_kaizen("proj-a", item["id"], status="trialing")
    assert updated["status"] == "trialing"
    assert updated["updated_at"] >= item["updated_at"]


def test_update_kaizen_rejects_unknown_status(sandbox):
    pm, _ = sandbox
    item = pm.add_kaizen(
        "proj-a", title="t", hypothesis="h", waste_type="waiting"
    )
    with pytest.raises(ValueError):
        pm.update_kaizen("proj-a", item["id"], status="frozen")


def test_list_kaizen_filters_by_status(sandbox):
    pm, _ = sandbox
    a = pm.add_kaizen("proj-a", title="a", hypothesis="h", waste_type="waiting")
    b = pm.add_kaizen("proj-a", title="b", hypothesis="h", waste_type="defects")
    pm.update_kaizen("proj-a", b["id"], status="adopted")

    proposed = pm.list_kaizen("proj-a", status="proposed")
    adopted = pm.list_kaizen("proj-a", status="adopted")
    assert [i["id"] for i in proposed] == [a["id"]]
    assert [i["id"] for i in adopted] == [b["id"]]


# ---------------------------------------------------------------------------
# Action-item CRUD + aging
# ---------------------------------------------------------------------------


def test_add_action_item_assigns_monotonic_ids(sandbox):
    pm, _ = sandbox
    a = pm.add_action_item("proj-a", title="A", source_session="sess-1")
    b = pm.add_action_item("proj-a", title="B", source_session="sess-1")
    assert a["id"] == "AI-001"
    assert b["id"] == "AI-002"
    assert a["age_sessions"] == 1


def test_touch_action_item_increments_age_on_new_session(sandbox):
    pm, _ = sandbox
    ai = pm.add_action_item("proj-a", title="A", source_session="sess-1")
    # Same session — no increment
    t1 = pm.touch_action_item("proj-a", ai["id"], "sess-1")
    assert t1["age_sessions"] == 1
    # New session — increment
    t2 = pm.touch_action_item("proj-a", ai["id"], "sess-2")
    assert t2["age_sessions"] == 2
    # Another new session — increment again
    t3 = pm.touch_action_item("proj-a", ai["id"], "sess-3")
    assert t3["age_sessions"] == 3


def test_touch_action_item_unknown_id_returns_none(sandbox):
    pm, _ = sandbox
    assert pm.touch_action_item("proj-a", "AI-999", "sess-1") is None


def test_resolve_action_item_sets_resolved_at(sandbox):
    pm, _ = sandbox
    ai = pm.add_action_item("proj-a", title="A", source_session="sess-1")
    resolved = pm.resolve_action_item("proj-a", ai["id"])
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"]


def test_aging_action_items_surfaces_multi_session_items(sandbox):
    """Issue #447 acceptance: items >= 2 sessions old surface at planning."""
    pm, _ = sandbox
    # Fresh item — should NOT appear
    pm.add_action_item("proj-a", title="Fresh", source_session="sess-1")
    # Aging item — touched across two later sessions
    ai = pm.add_action_item("proj-a", title="Stale", source_session="sess-1")
    pm.touch_action_item("proj-a", ai["id"], "sess-2")

    aging = pm.aging_action_items("proj-a")
    ids = [a["id"] for a in aging]
    assert ai["id"] in ids, "age=2 item must appear in aging list"
    assert len(aging) == 1, "age=1 item must NOT appear"


def test_aging_action_items_excludes_resolved(sandbox):
    pm, _ = sandbox
    ai = pm.add_action_item("proj-a", title="A", source_session="sess-1")
    pm.touch_action_item("proj-a", ai["id"], "sess-2")
    pm.touch_action_item("proj-a", ai["id"], "sess-3")
    assert len(pm.aging_action_items("proj-a")) == 1

    pm.resolve_action_item("proj-a", ai["id"])
    assert pm.aging_action_items("proj-a") == []


def test_aging_honors_custom_threshold(sandbox):
    pm, _ = sandbox
    ai = pm.add_action_item("proj-a", title="A")
    pm.touch_action_item("proj-a", ai["id"], "sess-2")
    pm.touch_action_item("proj-a", ai["id"], "sess-3")
    # age=3 — under threshold=4, so nothing surfaces
    assert pm.aging_action_items("proj-a", threshold=4) == []
    # age=3 — at threshold=3, surfaces
    assert len(pm.aging_action_items("proj-a", threshold=3)) == 1


# ---------------------------------------------------------------------------
# Pass-rate timeline
# ---------------------------------------------------------------------------


def test_record_pass_rate_appends_and_bounds_timeline(sandbox):
    pm, _ = sandbox
    # Push 60 samples; internal cap is 50.
    for i in range(60):
        pm.record_pass_rate("proj-a", 0.5 + (i % 10) / 20.0, session_id=f"s{i}")
    memory = pm.load_memory("proj-a")
    assert len(memory["pass_rate_timeline"]) == 50


def test_record_pass_rate_rejects_out_of_range(sandbox):
    pm, _ = sandbox
    with pytest.raises(ValueError):
        pm.record_pass_rate("proj-a", 1.5)
    with pytest.raises(ValueError):
        pm.record_pass_rate("proj-a", -0.1)


# ---------------------------------------------------------------------------
# Uncertainty gate
# ---------------------------------------------------------------------------


def _install_fake_drift(
    monkeypatch: pytest.MonkeyPatch, classify: Callable[[list[float]], dict]
) -> None:
    """Inject a synthetic delivery.drift module for the uncertainty-gate tests.

    We don't have the real drift module in this branch (PR #452 pending),
    so the test shapes the response directly by installing a stub in
    sys.modules. The stub matches the documented contract.
    """
    fake = types.ModuleType("delivery.drift")
    fake.classify = classify  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "delivery.drift", fake)


def test_uncertainty_gate_passes_on_actionable_drift(sandbox, monkeypatch):
    """Special-cause drift signal → gate passes regardless of uncertainty flag."""
    pm, _ = sandbox

    def fake_classify(timeline: list[float]) -> dict:
        return {
            "zone": "special-cause",
            "drift": True,
            "drop_pct": 0.25,
            "is_actionable": True,
        }

    _install_fake_drift(monkeypatch, fake_classify)
    pm.record_pass_rate("proj-a", 0.9, session_id="s1")
    pm.record_pass_rate("proj-a", 0.6, session_id="s2")

    decision = pm.evaluate_uncertainty_gate(
        "proj-a",
        proposed_gate_name="extra-design-review",
        uncertainty="aleatoric",  # even aleatoric passes when drift is actionable
        session_id="sess-now",
    )
    assert decision["passed"] is True
    assert decision["drift_available"] is True
    assert decision["drift_zone"] == "special-cause"
    # A passing gate is recorded as a proposed kaizen (not rejected).
    kz = pm.list_kaizen("proj-a")
    assert kz, "decision must record a kaizen item"
    assert kz[-1]["status"] == "proposed"


def test_uncertainty_gate_blocks_common_cause_aleatoric(sandbox, monkeypatch):
    """Common-cause + aleatoric = BLOCK. This is the gate's whole point."""
    pm, _ = sandbox

    def fake_classify(timeline: list[float]) -> dict:
        return {
            "zone": "within-control",
            "drift": False,
            "drop_pct": 0.02,
            "is_actionable": False,
        }

    _install_fake_drift(monkeypatch, fake_classify)
    pm.record_pass_rate("proj-a", 0.91, session_id="s1")
    pm.record_pass_rate("proj-a", 0.89, session_id="s2")

    decision = pm.evaluate_uncertainty_gate(
        "proj-a",
        proposed_gate_name="extra-design-review",
        uncertainty="aleatoric",
        session_id="sess-now",
    )
    assert decision["passed"] is False
    assert "aleatoric" in decision["reason"].lower()
    # Blocked proposals are auto-marked rejected in the kaizen backlog.
    kz = pm.list_kaizen("proj-a")
    assert kz[-1]["status"] == "rejected"


def test_uncertainty_gate_passes_on_epistemic_without_drift(sandbox, monkeypatch):
    """Epistemic uncertainty alone is sufficient — we don't know enough yet."""
    pm, _ = sandbox

    def fake_classify(timeline: list[float]) -> dict:
        return {
            "zone": "within-control",
            "drift": False,
            "drop_pct": 0.0,
            "is_actionable": False,
        }

    _install_fake_drift(monkeypatch, fake_classify)
    decision = pm.evaluate_uncertainty_gate(
        "proj-a",
        proposed_gate_name="probe-gate",
        uncertainty="epistemic",
        session_id="sess-now",
    )
    assert decision["passed"] is True
    assert decision["uncertainty"] == "epistemic"


def test_uncertainty_gate_fail_open_when_drift_module_absent(sandbox, monkeypatch):
    """PR #452 not merged yet — gate must not crash; decides on uncertainty."""
    pm, _ = sandbox
    # Ensure the module really is absent.
    monkeypatch.delitem(sys.modules, "delivery.drift", raising=False)

    # Even without drift, epistemic still passes.
    d1 = pm.evaluate_uncertainty_gate(
        "proj-a",
        proposed_gate_name="probe",
        uncertainty="epistemic",
        session_id="sess-x",
    )
    assert d1["passed"] is True
    assert d1["drift_available"] is False

    # And aleatoric alone still blocks — drift absence doesn't flip the semantics.
    d2 = pm.evaluate_uncertainty_gate(
        "proj-a",
        proposed_gate_name="probe-2",
        uncertainty="aleatoric",
        session_id="sess-x",
    )
    assert d2["passed"] is False
    assert d2["drift_available"] is False


# ---------------------------------------------------------------------------
# Facilitator context
# ---------------------------------------------------------------------------


def test_facilitator_context_surfaces_aging_ais(sandbox):
    """Acceptance #447: opening session N surfaces unresolved items from N-1, N-2."""
    pm, _ = sandbox
    ai = pm.add_action_item("proj-a", title="Flaky test", source_session="sess-N-2")
    pm.touch_action_item("proj-a", ai["id"], "sess-N-1")
    # Now session N — what does the facilitator see?
    ctx = pm.facilitator_context("proj-a")
    assert ctx["aging_count"] == 1
    assert ctx["aging_action_items"][0]["title"] == "Flaky test"
    assert ctx["markdown_path"].endswith("process-memory.md")


def test_facilitator_context_empty_project(sandbox):
    pm, _ = sandbox
    ctx = pm.facilitator_context("fresh-proj")
    assert ctx["aging_count"] == 0
    assert ctx["kaizen_backlog_size"] == 0
    assert ctx["pass_rate_timeline_length"] == 0


# ---------------------------------------------------------------------------
# Markdown rendering + persistence
# ---------------------------------------------------------------------------


def test_markdown_rendered_on_every_save(sandbox):
    pm, _ = sandbox
    pm.add_kaizen(
        "proj-a",
        title="Parallelize reviews",
        hypothesis="Parallel gate reviewers cut cycle time",
        waste_type="waiting",
    )
    md_path = pm._memory_md_path("proj-a")
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "Parallelize reviews" in content
    assert "Kaizen Backlog" in content


def test_aging_section_rendered_only_when_items_exist(sandbox):
    pm, _ = sandbox
    # Fresh AI — no aging section
    pm.add_action_item("proj-a", title="Fresh", source_session="s1")
    md = pm._memory_md_path("proj-a").read_text(encoding="utf-8")
    assert "Aging Action Items" not in md

    # Age it up
    ai = pm.list_action_items("proj-a")[0]
    pm.touch_action_item("proj-a", ai["id"], "s2")
    md = pm._memory_md_path("proj-a").read_text(encoding="utf-8")
    assert "Aging Action Items" in md


def test_load_memory_backfills_missing_fields(sandbox):
    """Older memory files missing new keys must load without error."""
    pm, _ = sandbox
    path = pm._memory_json_path("proj-old")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal older shape — only project + kaizen
    path.write_text(
        json.dumps({"project": "proj-old", "kaizen": []}),
        encoding="utf-8",
    )
    mem = pm.load_memory("proj-old")
    # Backfilled defaults must be present.
    assert mem["action_items"] == []
    assert mem["pass_rate_timeline"] == []
    assert mem["next_kaizen_seq"] == 1


def test_load_memory_recovers_from_corruption(sandbox):
    pm, _ = sandbox
    path = pm._memory_json_path("proj-bad")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    # Must not raise — must return a fresh shell.
    mem = pm.load_memory("proj-bad")
    assert mem["kaizen"] == []


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def test_invalid_project_name_is_rejected(sandbox):
    pm, _ = sandbox
    with pytest.raises(ValueError):
        pm.add_kaizen(
            "../escape",
            title="t",
            hypothesis="h",
            waste_type="waiting",
        )
    with pytest.raises(ValueError):
        pm.add_action_item("has spaces", title="t")


def test_empty_project_name_is_rejected(sandbox):
    pm, _ = sandbox
    with pytest.raises(ValueError):
        pm.add_kaizen("", title="t", hypothesis="h", waste_type="waiting")
