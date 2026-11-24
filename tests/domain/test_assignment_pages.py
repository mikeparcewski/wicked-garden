"""At the minimum, remaining domain assignments get pages without mapping more units."""

import json

import pytest

from domain import business_domains, generation, next_page, prepare_worklist, rules_file
from tests.domain.test_extraction_files import _Estate, _git_repo, _star, _wt
from tests.domain.test_generation import MIN, _Core, _doc, _env, _pt


def test_at_target_assignment_decision_requests_an_assignment_only_page():
    decision = generation.decide(
        _doc(_pt(0, 800, 0), _pt(1, 800, 5)), repo="repo", target=80, now=5 * MIN,
        max_pages=20, max_minutes=240, left_to_map=200, assign_left=3, assign_progress=True)
    assert decision["next"] == "continue"
    assert decision["assign_only"] is True


def test_mapping_page_always_tries_assignments_and_keeps_flag_out_of_marker(
        tmp_path, monkeypatch, capsys):
    db, repo = _star(tmp_path), _git_repo(tmp_path)
    doc = _doc({**_pt(0, 800, 0), "unassigned": 3})
    doc.update(pending=["s::core"], page_open=True)
    generation.save(db, "run-1", doc)
    monkeypatch.setattr(business_domains, "resolved_without_domain", lambda *a: ([], 3))
    decision = next_page.run(db, repo, core=_Core(800),
                             env=_env(WICKED_REPEAT_PASS=1), now=5 * MIN)
    assert decision["next"] == "continue"
    assert generation.load(db, "run-1")["assign_only"] is True
    marker = capsys.readouterr().out.splitlines()[-1]
    assert json.loads(marker.removeprefix("wicked-repeat ")) == decision
    assert set(decision) == {"next", "line"}
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    assign = [{"symbol_id": "s::a", "statement": "amount must be positive"}]
    monkeypatch.setattr(business_domains, "worklist_block", lambda *a, **kw: (
        {"propose": True, "catalog": [], "unassigned_resolved": 3}, assign))
    page = prepare_worklist.prepare(db, repo, _wt(tmp_path), rules_file.WORKLIST_REL, 500,
                                     estate=_Estate(), core=_Core(800, unmapped=[{
                                         "symbol_id": "s::core", "name": "core", "file": "f.py"}]))
    assert page["units"] == [] and page["assign"] == assign


def test_prepare_assignment_page_skips_unit_framing_with_unmapped_units_left(
        tmp_path, monkeypatch, capsys):
    db, repo, wt = _star(tmp_path), _git_repo(tmp_path), _wt(tmp_path)
    doc = _doc(_pt(0, 800, 0))
    doc["assign_only"] = True
    generation.save(db, "run-1", doc)
    monkeypatch.setenv("WICKED_RUN_ID", "run-1")
    assign = [{"symbol_id": "s::a", "statement": "amount must be positive"}]
    monkeypatch.setattr(business_domains, "worklist_block", lambda *a, **kw: (
        {"propose": True, "catalog": [], "unassigned_resolved": 1}, assign))
    def no_unit_framing(*args, **kwargs):
        pytest.fail("assignment pages must skip unit framing entirely")

    monkeypatch.setattr(prepare_worklist.refresh, "changed_units", no_unit_framing)
    monkeypatch.setattr(prepare_worklist.extract_loop, "_DirectStore", no_unit_framing)
    page = prepare_worklist.prepare(db, repo, wt, rules_file.WORKLIST_REL, 500,
                                     estate=_Estate(), core=_Core(800, unmapped=[{
                                         "symbol_id": "s::core", "name": "core", "file": "f.py"}]))
    assert page["units"] == []
    assert page["assign"] == assign
    assert generation.page_in_flight(generation.load(db, "run-1")) == []
    assert "assignment page: 1 to assign" in capsys.readouterr().err


@pytest.mark.parametrize("previous_count", [None, 3])
def test_assignment_page_without_progress_finishes_even_without_previous_count(
        tmp_path, monkeypatch, capsys, previous_count):
    db, repo = _star(tmp_path), _git_repo(tmp_path)
    doc = _doc(_pt(0, 800, 0))
    if previous_count is not None:
        doc["points"][-1]["unassigned"] = previous_count
    doc.update(assign_only=True, pending=[], page_open=True)
    generation.save(db, "run-1", doc)
    monkeypatch.setattr(business_domains, "resolved_without_domain", lambda *a: ([], 3))
    decision = next_page.run(db, repo, core=_Core(800),
                             env=_env(WICKED_REPEAT_PASS=1), now=5 * MIN)
    assert decision["next"] == "done"
    assert "3 requirement(s) left without a business domain" in decision["line"]
    assert "assign_only" not in generation.load(db, "run-1")


@pytest.mark.parametrize("bad", [None, 0, 1, "true", [], {}])
def test_generation_rejects_invalid_assignment_only_flag(bad):
    doc = _doc(_pt(0, 800, 0))
    doc["assign_only"] = bad
    assert generation._valid(doc) is False


def test_assignment_only_accessor_defaults_to_false():
    assert generation.assign_only(None) is False
    assert generation.assign_only({}) is False
    assert generation.assign_only({"assign_only": False}) is False
    assert generation.assign_only({"assign_only": True}) is True
