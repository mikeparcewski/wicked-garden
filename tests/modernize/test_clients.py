"""garden#989 — the CLI-backed un-mock clients (``scripts/modernize/_clients.py``).

The UNIT lane runs with NO binaries present: it monkeypatches the subprocess
shims to capture the argv the client would run, proving the four mock/CLI
reconciliations (symbol_id extraction, --symbol+--replace enforcement, semantics
routing, --db threading) and the resolve precedence. The INTEGRATION lane
skips-when-absent and exercises the real ``wicked-estate`` + ``wicked-core``.

Disjoint-build discipline: shells the peer binaries (argv lists, no shell string);
imports NO other-product code.
"""

import json
import shutil
from pathlib import Path

import pytest

from modernize import _clients


# --- resolve precedence (no binary) ------------------------------------------

def test_env_override_wins_and_empty_is_kill_switch(monkeypatch):
    monkeypatch.setenv("WICKED_ESTATE_BIN", "/opt/wicked-estate")
    assert _clients._resolve_bin("WICKED_ESTATE_BIN", "wicked-estate") == ["/opt/wicked-estate"]
    monkeypatch.setenv("WICKED_ESTATE_BIN", "")  # kill-switch
    assert _clients._resolve_bin("WICKED_ESTATE_BIN", "wicked-estate") is None


def test_config_preference_sits_between_env_and_path(monkeypatch):
    monkeypatch.delenv("WICKED_ESTATE_BIN", raising=False)
    monkeypatch.setattr(_clients, "_config_preference",
                        lambda key: "/cfg/wicked-estate" if key == "wicked-estate" else None)
    assert _clients._resolve_bin("WICKED_ESTATE_BIN", "wicked-estate") == ["/cfg/wicked-estate"]
    # Env override still wins over config.
    monkeypatch.setenv("WICKED_ESTATE_BIN", "/env/wicked-estate")
    assert _clients._resolve_bin("WICKED_ESTATE_BIN", "wicked-estate") == ["/env/wicked-estate"]


def test_config_preference_is_none_on_malformed_config(monkeypatch, tmp_path):
    # "None on any error" — a non-object JSON (AttributeError) and a non-UTF-8
    # file (UnicodeDecodeError, a ValueError) must not escape and abort extraction.
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(_clients, "_CONFIG_PATH", cfg)
    cfg.write_text("[1, 2, 3]")  # valid JSON, not an object
    assert _clients._config_preference("wicked-estate") is None
    cfg.write_text('"just-a-string"')
    assert _clients._config_preference("wicked-estate") is None
    cfg.write_bytes(b"\xff\xfe\x00bad-utf8")  # non-UTF-8
    assert _clients._config_preference("wicked-estate") is None
    cfg.write_text('{"tool_preferences": {"wicked-estate": "/x/wicked-estate"}}')
    assert _clients._config_preference("wicked-estate") == "/x/wicked-estate"


def test_invoke_fails_loud_on_unrunnable_binary(monkeypatch):
    # A resolved-but-unrunnable argv must raise a descriptive RuntimeError, not a
    # raw FileNotFoundError traceback.
    with pytest.raises(RuntimeError, match="not found or not executable"):
        _clients._run(["/nonexistent/wicked-estate-xyz", "resolve", "x"])


def test_estate_client_falls_back_to_mock_without_a_binary(monkeypatch):
    monkeypatch.setenv("WICKED_ESTATE_BIN", "")  # force no binary
    client = _clients.estate_client(db="/tmp/x.db")
    from modernize._mocks import EstateClient
    assert isinstance(client, EstateClient), "no binary -> the fixture-backed mock"


def test_estate_client_needs_both_a_binary_and_a_db(monkeypatch):
    monkeypatch.setenv("WICKED_ESTATE_BIN", "/opt/wicked-estate")
    # A binary but no db -> still the mock (a CLI op without a store is meaningless).
    from modernize._mocks import EstateClient
    assert isinstance(_clients.estate_client(db=None), EstateClient)
    assert isinstance(_clients.estate_client(db="/tmp/e.db"), _clients.CliEstateClient)


def test_core_client_is_none_without_a_binary(monkeypatch):
    monkeypatch.setenv("WICKED_CORE_BIN", "")
    assert _clients.core_client() is None


# --- CLI argv construction (no binary — monkeypatch the shims) ---------------

class _Capture:
    def __init__(self, json_return=None):
        self.calls = []
        self._json = json_return

    def run(self, argv):
        self.calls.append(argv)
        return ""

    def run_json(self, argv):
        self.calls.append(argv)
        return self._json


def _cli_estate(monkeypatch, json_return=None):
    cap = _Capture(json_return)
    monkeypatch.setattr(_clients, "_run", cap.run)
    monkeypatch.setattr(_clients, "_run_json", cap.run_json)
    return _clients.CliEstateClient(["wicked-estate"], "/tmp/estate.db"), cap


def test_resolve_extracts_symbol_ids_and_threads_db(monkeypatch):
    est, cap = _cli_estate(monkeypatch, json_return=[
        {"symbol_id": "sym::billing::A::a1", "name": "A"},
        {"symbol_id": "sym::billing::B::a2", "name": "B"},
        {"name": "no-id"},  # ignored
    ])
    ids = est.resolve("charge", file="src/billing/charge.py", kind="Function")
    assert ids == ["sym::billing::A::a1", "sym::billing::B::a2"]
    argv = cap.calls[0]
    assert argv[:2] == ["wicked-estate", "resolve"]
    assert "charge" in argv and "--json" in argv
    assert argv[argv.index("--file") + 1] == "src/billing/charge.py"  # EXACT path
    assert argv[argv.index("--kind") + 1] == "Function"
    assert argv[argv.index("--db") + 1] == "/tmp/estate.db"


def test_annotate_forces_symbol_and_replace(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    est.annotate("sym::billing::A::a1", "business_rule", "RULE-001",
                 "amount must be positive", confidence=0.9, provenance="code-graph")
    argv = cap.calls[0]
    assert argv[argv.index("--symbol") + 1] == "sym::billing::A::a1"  # never a bare name
    assert "--replace" in argv, "must upsert (the CLI defaults to APPEND)"
    assert argv[argv.index("--type") + 1] == "business_rule"
    assert argv[argv.index("--key") + 1] == "RULE-001"
    assert argv[argv.index("--value") + 1] == "amount must be positive"
    assert argv[argv.index("--db") + 1] == "/tmp/estate.db"


def test_annotate_refuses_a_bare_name(monkeypatch):
    est, _ = _cli_estate(monkeypatch)
    with pytest.raises(ValueError, match="non-SymbolId"):
        est.annotate("Charge", "business_rule", "k", "v")


def test_set_requirement_routes_to_semantics(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    est.set_requirement("sym::billing::A::a1", "REQ text", validated=True)
    argv = cap.calls[0]
    assert argv[:2] == ["wicked-estate", "semantics"], "requirement -> node_semantics, not annotate"
    assert "sym::billing::A::a1" in argv
    assert argv[argv.index("--requirement") + 1] == "REQ text"
    assert argv[argv.index("--validated") + 1] == "true"


def test_read_clusters_requests_the_summary_shape(monkeypatch):
    est, cap = _cli_estate(monkeypatch, json_return=[{"id": 0, "size": 2, "members": []}])
    est.read_clusters()
    argv = cap.calls[0]
    assert "--summary" in argv and "--json" in argv, "the object shape needs --summary"
    assert argv[argv.index("--db") + 1] == "/tmp/estate.db"


def test_read_clusters_threads_the_min_filter(monkeypatch):
    est, cap = _cli_estate(monkeypatch, json_return=[])
    est.read_clusters({"min": 5})
    argv = cap.calls[0]
    # `[min]` is a positional right after the subcommand, before the flags.
    assert argv[:3] == ["wicked-estate", "clusters", "5"]


def test_read_annotations_uses_symbol_flag_not_positional(monkeypatch):
    est, cap = _cli_estate(monkeypatch, json_return={"symbol": "sym::b::A::a1",
                                                     "annotations": [{"key": "RULE-1"}]})
    anns = est.read_annotations("sym::b::A::a1")
    assert anns == [{"key": "RULE-1"}]
    argv = cap.calls[0]
    # `--symbol` (single-object shape), NOT the positional name-search form.
    assert argv[argv.index("--symbol") + 1] == "sym::b::A::a1"
    assert "sym::b::A::a1" not in argv[:argv.index("--symbol")], "id must not also be a positional"


def test_read_annotations_refuses_a_bare_name(monkeypatch):
    est, _ = _cli_estate(monkeypatch)
    with pytest.raises(ValueError, match="non-SymbolId"):
        est.read_annotations("Charge")


def test_read_annotations_rejects_unexpected_array_shape(monkeypatch):
    est, _ = _cli_estate(monkeypatch, json_return=[{"symbol": "x", "annotations": []}])
    with pytest.raises(RuntimeError, match="expected the single-symbol object"):
        est.read_annotations("sym::b::A::a1")


def test_find_by_annotation_is_unsupported_on_the_cli(monkeypatch):
    est, _ = _cli_estate(monkeypatch)
    with pytest.raises(NotImplementedError):
        est.find_by_annotation("business_rule")


def test_core_domain_graph_shells_and_returns_the_parsed_doc(monkeypatch, tmp_path):
    out = tmp_path / "requirements_graph.json"
    doc = {"metadata": {"schema_version": "1.0.0", "migration_mode": "functional"}, "domains": {}}

    def fake_run(argv):
        # The CLI would write --out; simulate it.
        out_path = Path(argv[argv.index("--out") + 1])
        out_path.write_text(json.dumps(doc))
        return ""

    monkeypatch.setattr(_clients, "_run", fake_run)
    core = _clients.CliCoreClient(["wicked-core"])
    got = core.domain_graph(db="/tmp/e.db", out=str(out))
    assert got == doc


# --- opt-in real-CLI integration (skip when the peers are absent) ------------

def _bin(env, package):
    import os
    val = os.environ.get(env, "").strip()
    return val or shutil.which(package)


_ESTATE = _bin("WICKED_ESTATE_BIN", "wicked-estate")
_CORE = _bin("WICKED_CORE_BIN", "wicked-core")


@pytest.mark.skipif(
    _ESTATE is None or _CORE is None,
    reason="wicked-estate and/or wicked-core not installed (PATH or WICKED_*_BIN) — real-CLI integration lane",
)
def test_real_cli_selection_resolves_the_binaries():
    # A minimal live assertion that the seam picks the real clients when the peers
    # are present (the full annotate->coverage==1.0->domain-graph flow additionally
    # needs an INDEXED + fully-annotated store — a fixture-seeding step tracked for
    # the end-to-end milestone, core#28).
    est = _clients.estate_client(db="/tmp/does-not-matter.db")
    assert isinstance(est, _clients.CliEstateClient)
    assert _clients.core_client() is not None
