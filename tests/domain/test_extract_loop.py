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


# --- structural path (_DirectStore, density batching, cluster offsets) -------

def _fixture_db(tmp_path, n_files=1):
    """Minimal estate-schema sqlite the structural path reads: two clusters —
    'hot' (h::a called by h::b, h::c) and 'cold' (c::x → c::y, lower leverage)."""
    import json as J, sqlite3
    db = tmp_path / "estate.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE symbols (sid INTEGER PRIMARY KEY, sym TEXT);
        CREATE TABLE nodes (symbol INTEGER, name TEXT, file TEXT, data TEXT, requirement TEXT);
        CREATE TABLE edges (source INTEGER, target INTEGER, kind TEXT);
        CREATE TABLE files (path TEXT, git_sha TEXT);
        CREATE TABLE content (git_sha TEXT, blob BLOB);
    """)
    syms = ["h::a", "h::b", "h::c", "c::x", "c::y"]
    for i, s in enumerate(syms, start=1):
        c.execute("INSERT INTO symbols VALUES (?, ?)", (i, s))
        data = J.dumps({"location": {"span": {"start_byte": 0, "end_byte": 9}}})
        c.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, NULL)", (i, s.split("::")[-1], f"f{i}.py", data))
    # both kind spellings must count (stores differ on JSON-quoting)
    c.execute("INSERT INTO edges VALUES (2, 1, 'calls')")
    c.execute("INSERT INTO edges VALUES (3, 1, '\"calls\"')")
    c.execute("INSERT INTO edges VALUES (4, 5, '\"calls\"')")
    for i in range(1, 6):
        c.execute("INSERT INTO files VALUES (?, ?)", (f"f{i}.py", f"sha{i}"))
        c.execute("INSERT INTO content VALUES (?, ?)", (f"sha{i}", b"def body(): pass"))
    c.commit(); c.close()
    return str(db)


def test_direct_store_reads_both_edge_kind_spellings(tmp_path):
    store = extract_loop._DirectStore(_fixture_db(tmp_path))
    assert store.leverage("h::a") == 2          # two callers, both spellings counted
    names = store.blast_neighbors("h::a")
    assert "caller:b" in names and "caller:c" in names
    assert store.leverage("c::y") == 1


def test_direct_store_source_slice_uses_byte_span(tmp_path):
    store = extract_loop._DirectStore(_fixture_db(tmp_path))
    assert store.source_slice("h::a") == "def body("  # bytes [0, 9)


def test_direct_store_file_cache_is_bounded(tmp_path):
    import json as J, sqlite3
    db = _fixture_db(tmp_path)
    c = sqlite3.connect(db)
    data = J.dumps({"location": {"span": {"start_byte": 0, "end_byte": 5}}})
    for i in range(140):
        sid = 100 + i
        c.execute("INSERT INTO symbols VALUES (?, ?)", (sid, f"m::f{i}"))
        c.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, NULL)", (sid, f"f{i}", f"many{i}.py", data))
        c.execute("INSERT INTO files VALUES (?, ?)", (f"many{i}.py", f"msha{i}"))
        c.execute("INSERT INTO content VALUES (?, ?)", (f"msha{i}", b"hello world"))
    c.commit(); c.close()
    store = extract_loop._DirectStore(db)
    for i in range(140):
        assert store.source_slice(f"m::f{i}") == "hello"
    assert len(store._file_text) <= 128  # eviction happened inside source_slice


class _SliceStore:
    def __init__(self, size):
        self.size = size
    def source_slice(self, sid, cap=2000):
        return "x" * self.size


@pytest.mark.parametrize("size,base,expect", [
    (50, 20, 32),    # sparse → ×1.6
    (2000, 20, 12),  # dense → ×0.6
    (800, 20, 20),   # mid → ×1.0
    (2000, 4, 4),    # clamp floor
    (50, 60, 64),    # clamp ceiling
])
def test_density_batch_adapts_and_clamps(size, base, expect):
    members = [{"symbol_id": f"s{i}"} for i in range(12)]
    assert extract_loop._density_batch(members, _SliceStore(size), base) == expect


def _run_structural(tmp_path, monkeypatch, cluster_offset):
    """Full run() through the structural branch against the fixture db; returns
    the order nodes settled (estate write order)."""
    db = _fixture_db(tmp_path)
    ids = ["h::a", "h::b", "h::c", "c::x", "c::y"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)
    monkeypatch.setattr(_clients, "total_node_community",
                        lambda clusters, nodes: {s: s.split("::")[0] for s in ids})
    rc = extract_loop.run(db, time_budget=30, limit=2, batch=2, dry_run=True,
                          cluster_offset=cluster_offset)
    assert rc == 0
    return list(estate.writes)


def test_offset_zero_takes_highest_leverage_cluster_first(tmp_path, monkeypatch):
    first = _run_structural(tmp_path, monkeypatch, cluster_offset=0)[0]
    assert first.startswith("h::")


def test_offset_wraps_beyond_cluster_count(tmp_path, monkeypatch):
    # 2 clusters, offset 5 → 5 % 2 = 1 → the SECOND-ranked cluster, not the tail pile-up
    first = _run_structural(tmp_path, monkeypatch, cluster_offset=5)[0]
    assert first.startswith("c::")


def test_negative_offset_clamps_to_head(tmp_path, monkeypatch):
    first = _run_structural(tmp_path, monkeypatch, cluster_offset=-3)[0]
    assert first.startswith("h::")


# --- infra failures abort the pass (outage ≠ judgment) ------------------------

def _run_with_model_error(monkeypatch, message):
    ids = ["a::f1", "a::f2"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["fake-model"])
    def boom(batch, argv):
        raise RuntimeError(message)
    monkeypatch.setattr(_rule_extractor, "extract_rules", boom)
    rc = extract_loop.run("x.db", time_budget=30, limit=0, batch=12, dry_run=False)
    return rc, estate


def test_session_limit_aborts_pass_and_floors_nothing(monkeypatch):
    rc, estate = _run_with_model_error(
        monkeypatch, "rule model exited 1: You've hit your session limit · resets 9:30pm")
    assert rc == 75          # EX_TEMPFAIL — resume later, don't gate on it
    assert estate.writes == {}  # the outage burned NOTHING into the store


def test_rate_limit_aborts_pass(monkeypatch):
    rc, estate = _run_with_model_error(monkeypatch, "429 rate limit exceeded")
    assert rc == 75 and estate.writes == {}


def test_plain_timeout_still_risk_floors(monkeypatch):
    # a per-batch timeout IS a judgment (batch too hard) — floor and continue
    rc, estate = _run_with_model_error(monkeypatch, "rule model exceeded 180s")
    assert rc == 0
    for sid in ("a::f1", "a::f2"):
        req, validated = estate.writes[sid]["req"]
        assert req.startswith("[RISK]") and validated is False


# --- zero-yield abort + floor monotonicity ------------------------------------

def _run_with_model_yield(monkeypatch, rules, ids=None, db="x.db"):
    ids = ids or ["a::f1", "a::f2", "a::f3", "a::f4"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["fake-model"])
    monkeypatch.setattr(_rule_extractor, "extract_rules", lambda batch, argv: rules)
    rc = extract_loop.run(db, time_budget=30, limit=0, batch=12, dry_run=False)
    return rc, estate


def test_zero_rules_for_a_real_batch_aborts(monkeypatch):
    rc, estate = _run_with_model_yield(monkeypatch, [])
    assert rc == 75 and estate.writes == {}


def test_empty_statement_shells_for_a_real_batch_abort(monkeypatch):
    # a degraded CLI can emit rule shells with blank statements — same outage signature
    shells = [{"symbol_id": f"a::f{i}", "statement": "", "confidence": 0.9,
               "provenance": {"source": "m", "ref": f"a::f{i}", "source_kinds": ["code-body"]}}
              for i in range(1, 5)]
    rc, estate = _run_with_model_yield(monkeypatch, shells)
    assert rc == 75 and estate.writes == {}


def test_partial_yield_still_floors_the_misses(monkeypatch):
    # one substantive rule → the batch is judged normally: hit resolves, misses floor
    rules = [_good("a::f1")]
    rc, estate = _run_with_model_yield(monkeypatch, rules)
    assert rc == 0
    assert estate.writes["a::f1"]["req"][1] is True
    for sid in ("a::f2", "a::f3", "a::f4"):
        req, validated = estate.writes[sid]["req"]
        assert req.startswith("[RISK]") and validated is False


def test_floor_never_overwrites_existing_statement(tmp_path, monkeypatch):
    # fixture store: give h::a an existing substantive statement, then run a pass whose
    # model yields ONE substantive rule (so the batch isn't zero-yield) but nothing for
    # h::a — its floor must be SKIPPED, content is monotonic.
    import json as J, sqlite3
    db = _fixture_db(tmp_path)
    c = sqlite3.connect(db)
    c.execute("UPDATE nodes SET requirement = 'callers must pass a validated payload' WHERE name = 'a'")
    c.commit(); c.close()
    ids = ["h::a", "h::b", "h::c", "c::x"]
    estate = _FakeEstate()
    core = _FakeCore(estate, ids)
    monkeypatch.setattr(_clients, "estate_client", lambda db=None, project_dir=None: estate)
    monkeypatch.setattr(_clients, "core_client", lambda project_dir=None: core)
    monkeypatch.setattr(_clients, "rule_model_argv", lambda project_dir=None: ["fake-model"])
    monkeypatch.setattr(_clients, "total_node_community", lambda clusters, nodes: {s: "one" for s in ids})
    monkeypatch.setattr(_rule_extractor, "extract_rules", lambda batch, argv: [_good("h::b")])
    rc = extract_loop.run(db, time_budget=30, limit=0, batch=12, dry_run=False)
    assert rc == 0
    assert "h::a" not in estate.writes          # kept its existing statement — no floor write
    assert estate.writes["h::b"]["req"][1] is True
    assert estate.writes["h::c"]["req"][0].startswith("[RISK]")  # blank node still floors


# --- compressed content blobs -------------------------------------------------

def test_source_slice_decompresses_zstd_blobs(tmp_path):
    import json as J, sqlite3
    from compression import zstd
    db = tmp_path / "estate-z.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE symbols (sid INTEGER PRIMARY KEY, sym TEXT);
        CREATE TABLE nodes (symbol INTEGER, name TEXT, file TEXT, data TEXT, requirement TEXT);
        CREATE TABLE edges (source INTEGER, target INTEGER, kind TEXT);
        CREATE TABLE files (path TEXT, git_sha TEXT);
        CREATE TABLE content (git_sha TEXT, blob BLOB);
    """)
    src = b"def guarded(x):\n    return x > 0\n"
    data = J.dumps({"location": {"span": {"start_byte": 0, "end_byte": len(src)}}})
    c.execute("INSERT INTO symbols VALUES (1, 'z::guarded')")
    c.execute("INSERT INTO nodes VALUES (1, 'guarded', 'z.py', ?, NULL)", (data,))
    c.execute("INSERT INTO files VALUES ('z.py', 'zsha')")
    c.execute("INSERT INTO content VALUES ('zsha', ?)", (zstd.compress(src),))
    c.commit(); c.close()
    store = extract_loop._DirectStore(str(db))
    assert store.source_slice("z::guarded") == src.decode()


def test_maybe_decompress_passes_plain_bytes_through():
    assert extract_loop._maybe_decompress(b"plain text") == b"plain text"
