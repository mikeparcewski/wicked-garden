"""wicked-garden#1537: a review item about a domain pick reached the rework cap and landed carried.

On CardDemo (run 37e5f9da) page 1 proposed four business areas from the batch programs the request
named. Later pages held sign-on, menu, user-administration and transaction-browse screens; the
seat said "the catalog needs a fifth area (access and administration)", but a stored catalog
could not change, so those rules were picked into the nearest area. The page's review failed the
picks three rounds running, and the page landed with the item carried.

A later page may now ADD an area the stored catalog lacks, grounded like a proposal; the stored
domains never change. `catalog_carddemo_37e5f9da.json` is that run's stored catalog as
extract-prepare published it (its `_from` says where it was read).
"""

import json
from pathlib import Path

from domain import _rule_extractor, business_domains, extract_loop, prepare_worklist, rules_file
from tests.domain.test_business_domains import _apply, _domain_of, _fixture, _write
from tests.domain.test_extraction_files import _rule, _wt

STORED = json.loads((Path(__file__).resolve().parent / "fixtures" /
                     "catalog_carddemo_37e5f9da.json").read_text(encoding="utf-8"))["catalog"]
ACCESS = {"id": "access-and-administration", "name": "Access and administration",
          "purpose": "Signs users on, routes them through the menus and administers user accounts.",
          "evidence": [{"kind": "entry-point", "file": "f.py", "symbol": "route"}]}


def test_a_later_page_adds_the_missing_area_and_its_rules_pick_it(tmp_path):
    """Falsifier: a page's business_domains beside a stored catalog is refused whole, and the
    sign-on rule can only be forced into an area or left without one."""
    db, repo, wt, estate, core = _fixture(tmp_path)
    business_domains.save_catalog(db, STORED, "run-37e5f9da")
    _write(wt, [{**_rule("s::route"), "domain": "access-and-administration",
                 "domain_confidence": 0.85},
                {**_rule("s::core"), "domain": "transaction-posting", "domain_confidence": 0.8}],
           business_domains=[ACCESS])
    report = _apply(wt, db, repo, estate, core)
    bd = report["business_domains"]
    assert bd["catalog"] == "stored, 1 added" and bd["picked"] == 2 and bd["refused"] == [], bd
    assert _domain_of(estate, "s::route") == ("access-and-administration", 0.85)
    assert _domain_of(estate, "s::core") == ("transaction-posting", 0.8)
    stored = business_domains.load_catalog(db)
    assert stored == [*STORED, ACCESS], "the stored areas are kept as they were"
    # the next page is offered the five areas, and room for four more
    block, _ = business_domains.worklist_block(db, set(), extract_loop.RESOLVE_THRESHOLD,
                                               business_domains.not_product)
    assert [d["id"] for d in block["catalog"]][-1] == "access-and-administration"
    assert block["propose"] is False and block["add"] == 4


def test_an_addition_never_changes_a_stored_area(tmp_path):
    db, repo, wt, estate, core = _fixture(tmp_path)
    business_domains.save_catalog(db, STORED)
    renamed = {**STORED[0], "purpose": "Screens and posting, all of it.",
               "evidence": ACCESS["evidence"]}
    _write(wt, [{**_rule("s::route"), "domain": "transaction-posting", "domain_confidence": 0.9}],
           business_domains=[renamed])
    report = _apply(wt, db, repo, estate, core)
    whys = " | ".join(r["why"] for r in report["business_domains"]["refused"])
    assert "'transaction-posting' is already a domain of the stored catalog" in whys, whys
    assert business_domains.load_catalog(db) == STORED
    # the pick of a stored area still applies
    assert _domain_of(estate, "s::route") == ("transaction-posting", 0.9)


def test_an_ungrounded_addition_is_dropped_and_its_picks_are_refused(tmp_path):
    db, repo, wt, estate, core = _fixture(tmp_path)
    business_domains.save_catalog(db, STORED)
    invented = {**ACCESS, "evidence": [{"kind": "entry-point", "file": "app/cbl/COSGN00C.cbl",
                                        "symbol": "COSGN00C"}]}
    _write(wt, [{**_rule("s::route"), "domain": "access-and-administration",
                 "domain_confidence": 0.85}], business_domains=[invented])
    report = _apply(wt, db, repo, estate, core)
    bd = report["business_domains"]
    assert bd["catalog"] == "stored" and bd["dropped_evidence_count"] == 2, bd
    assert _domain_of(estate, "s::route") is None
    assert business_domains.load_catalog(db) == STORED


def test_a_full_catalog_takes_no_more_areas():
    full = [{**ACCESS, "id": f"area-{c}", "name": f"Area {c} work"} for c in "abcdefghi"]
    try:
        business_domains.check_additions(full, [ACCESS])
    except business_domains.CatalogRefused as e:
        assert "already has 9 domains" in str(e)
    else:
        raise AssertionError("a tenth area was accepted")
    try:
        business_domains.check_additions(STORED, [ACCESS] * 6)
    except business_domains.CatalogRefused as e:
        assert "add to the stored catalog 1 to 5" in str(e)
    else:
        raise AssertionError("more areas than the catalog has room for were accepted")


def test_extend_keeps_an_area_another_page_added_first(tmp_path):
    db = str(tmp_path / "estate.db")
    assert business_domains.extend_catalog(db, [ACCESS]) == [], "no catalog file to extend"
    business_domains.save_catalog(db, STORED)
    first = business_domains.extend_catalog(db, [ACCESS], "run-a")
    again = business_domains.extend_catalog(db, [{**ACCESS, "purpose": "Another page's take."}],
                                            "run-b")
    assert first == again == [*STORED, ACCESS]
    assert list(business_domains.catalog_path(db).parent.glob(".catalog-*")) == []


def _worklist(wt):
    (wt / "f.py").write_text("def route(): ...\n", encoding="utf-8")
    units = [{"symbol_id": f"s::u{i}", "name": f"u{i}", "file": "f.py", "source": "def u(): ..."}
             for i in range(2)]
    rules_file.write_json_file(wt, rules_file.WORKLIST_REL, {
        "schema": rules_file.WORKLIST_SCHEMA, "units": units,
        "business_domains": {"propose": False, "catalog": STORED, "add": 5,
                             "directory_names": ["app", "cbl"]}, "assign": []})


def test_the_harness_offers_the_added_area_and_the_seats_check_accepts_it(tmp_path, monkeypatch):
    wt = _wt(tmp_path)
    _worklist(wt)
    _write(wt, [], business_domains=[ACCESS])
    prompts = []

    def model(batch, argv, **kw):
        prompts.append(_rule_extractor._build_prompt(batch))
        return [{**_rule(u["symbol_id"]), "domain": "access-and-administration",
                 "domain_confidence": 0.8} for u in batch]
    monkeypatch.setattr(_rule_extractor, "extract_rules", model)
    monkeypatch.setattr(extract_loop._clients, "rule_model_argv", lambda base: ["model"])
    assert extract_loop.run_files(wt, rules_file.WORKLIST_REL, rules_file.RULES_REL,
                                  time_budget=60, limit=0, batch=8, dry_run=False) == 0
    assert "access-and-administration: Access and administration" in prompts[0]
    assert "transaction-posting: Transaction posting" in prompts[0]
    doc = rules_file.read_json_file(wt, rules_file.RULES_REL)
    assert {e.get("domain") for e in doc["rules"]} == {"access-and-administration"}
    assert extract_loop.check_rules(wt, rules_file.RULES_REL, rules_file.WORKLIST_REL) == 0


def test_the_seats_check_names_an_addition_that_changes_a_stored_area(tmp_path, capsys):
    wt = _wt(tmp_path)
    _worklist(wt)
    _write(wt, [_rule("s::u0")], business_domains=[{**ACCESS, "name": "Transaction posting"}])
    assert extract_loop.check_rules(wt, rules_file.RULES_REL, rules_file.WORKLIST_REL) == 1
    err = capsys.readouterr().err
    assert "repeats a domain of the stored catalog" in err and "list only areas it lacks" in err
