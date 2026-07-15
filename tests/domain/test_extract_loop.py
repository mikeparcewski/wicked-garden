"""The deterministic extraction harness (scripts/domain/extract_loop.py) — hermetic.

Proves the vault-pattern invariants WITHOUT live CLIs, by faking the estate + core
clients: (a) the worklist is the coverage authority's `unaccounted_nodes`, (b) every
node terminates RESOLVED-or-RISK, (c) a model that returns nothing RISK-floors the
batch (never a gap), (d) validate_rule gates a model output before it counts,
(e) total_node_community singleton-assigns so it is TOTAL.
"""

import pytest

from domain import _clients, _rule_extractor, extract_loop


# --- validate_rule (the model-output gate) -----------------------------------

def _good(sid):
    return {"symbol_id": sid, "statement": "amount must be positive", "confidence": 0.9,
            "provenance": {"source": "m", "ref": sid, "source_kinds": ["code-body"]}}


def test_validate_rule_accepts_a_well_formed_rule():
    ok, _ = _rule_extractor.validate_rule(_good("a::b"), {"a::b"})
    assert ok


@pytest.mark.parametrize("mut,reason", [
    (lambda r: r.update(symbol_id="other::x"), "hallucinated"),
    (lambda r: r.update(statement=""), "empty statement"),
    (lambda r: r.update(confidence="high"), "not a number"),
    (lambda r: r.update(confidence=1.5), "not a number"),
    (lambda r: r.update(provenance={"source": "m"}), "provenance"),
    (lambda r: r.update(provenance={"source": "m", "ref": "a::b", "source_kinds": []}), "source_kinds"),
])
def test_validate_rule_rejects_and_says_why(mut, reason):
    r = _good("a::b"); mut(r)
    ok, why = _rule_extractor.validate_rule(r, {"a::b"})
    assert not ok and reason in why


def test_validate_rule_rejects_a_true_bool_confidence():
    r = _good("a::b"); r["confidence"] = True  # bool is not a valid number here
    ok, _ = _rule_extractor.validate_rule(r, {"a::b"})
    assert not ok


# --- total_node_community (singleton-assign → TOTAL) -------------------------

def test_total_node_community_singleton_assigns_omitted_nodes():
    clusters = [{"members": ["x::1", "x::2"]}]
    all_nodes = [{"symbol_id": "x::1"}, {"symbol_id": "x::2"}, {"symbol_id": "x::3"}]
    nc = _clients.total_node_community(clusters, all_nodes)
    assert nc["x::1"] == nc["x::2"] == "x::1"  # community keeps its label
    assert nc["x::3"] == "x::3"               # engine-omitted node → singleton
    assert set(nc) == {"x::1", "x::2", "x::3"}  # TOTAL over every node


def test_unaccounted_nodes_fails_loud_when_absent():
    assert _clients.unaccounted_nodes({"unaccounted_nodes": [{"symbol_id": "a::b"}]})
    with pytest.raises(RuntimeError, match="no `unaccounted_nodes`"):
        _clients.unaccounted_nodes({"coverage": 1.0})


# --- the loop: RISK-floor + coverage-driven worklist -------------------------

class _FakeEstate:
    def __init__(self):
        self.writes = {}
    def read_clusters(self):
        return []
    def list_nodes(self):
        return []
    def source(self, name):
        return f"source of {name}"
    def annotate(self, symbol_id, **kw):
        self.writes.setdefault(symbol_id, {})["ann"] = kw
    def set_requirement(self, symbol_id, requirement, validated):
        self.writes.setdefault(symbol_id, {})["req"] = (requirement, validated)
    def read_annotations(self, symbol_id):
        # honor the harness read-back: echo the key it just wrote
        kw = self.writes.get(symbol_id, {}).get("ann", {})
        return [{"key": kw.get("key")}] if kw else []


class _FakeCore:
    """Coverage authority: unaccounted = every node NOT yet given a requirement."""
    def __init__(self, estate, all_ids):
        self.estate, self.all_ids = estate, all_ids
    def coverage(self, db, out):
        done = {sid for sid, w in self.estate.writes.items() if "req" in w}
        remaining = [{"symbol_id": s, "name": s.split("::")[-1]} for s in self.all_ids if s not in done]
        return {"coverage": 0.0 if remaining else 1.0, "unaccounted_nodes": remaining}


def test_loop_risk_floors_every_node_and_reaches_coverage_1(monkeypatch):
    ids = ["a::f1", "a::f2", "a::f3"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)
    # The model returns NOTHING → the RISK-floor must still settle every node.
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["fake-model"])
    monkeypatch.setattr(_rule_extractor, "extract_rules", lambda batch, argv: [])

    rc = extract_loop.run("x.db", time_budget=30, limit=0, batch=12, dry_run=False)
    assert rc == 0
    # every node got a requirement (RISK-floored, validated=False) → coverage 1.0.
    assert set(estate.writes) == set(ids)
    for sid in ids:
        req, validated = estate.writes[sid]["req"]
        assert req and validated is False  # RISK: non-blank requirement, not validated


def test_loop_dry_run_resolves_every_node(monkeypatch):
    ids = ["a::f1", "a::f2"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)

    rc = extract_loop.run("x.db", time_budget=30, limit=0, batch=12, dry_run=True)
    assert rc == 0
    for sid in ids:
        req, validated = estate.writes[sid]["req"]
        assert validated is True  # the deterministic stub is a confident, valid rule
