"""garden#989 — the CLI-backed un-mock clients (``scripts/domain/_clients.py``).

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

from domain import _clients


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
    from domain._mocks import EstateClient
    assert isinstance(client, EstateClient), "no binary -> the fixture-backed mock"


def test_estate_client_needs_both_a_binary_and_a_db(monkeypatch):
    monkeypatch.setenv("WICKED_ESTATE_BIN", "/opt/wicked-estate")
    # A binary but no db -> still the mock (a CLI op without a store is meaningless).
    from domain._mocks import EstateClient
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
        {"symbol_id": "sym synthetic billing::A::a1:", "name": "A"},
        {"symbol_id": "sym synthetic billing::B::a2:", "name": "B"},
        {"name": "no-id"},  # ignored
    ])
    ids = est.resolve("charge", file="src/billing/charge.py", kind="Function")
    assert ids == ["sym synthetic billing::A::a1:", "sym synthetic billing::B::a2:"]
    argv = cap.calls[0]
    assert argv[:2] == ["wicked-estate", "resolve"]
    assert "charge" in argv and "--json" in argv
    assert argv[argv.index("--file") + 1] == "src/billing/charge.py"  # EXACT path
    assert argv[argv.index("--kind") + 1] == "Function"
    assert argv[argv.index("--db") + 1] == "/tmp/estate.db"


def test_annotate_forces_symbol_and_replace(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    est.annotate("sym synthetic billing::A::a1:", "business_rule", "RULE-001",
                 "amount must be positive", confidence=0.9, provenance="code-graph")
    argv = cap.calls[0]
    assert argv[argv.index("--symbol") + 1] == "sym synthetic billing::A::a1:"  # never a bare name
    assert "--replace" in argv, "must upsert (the CLI defaults to APPEND)"
    assert argv[argv.index("--type") + 1] == "business_rule"
    assert argv[argv.index("--key") + 1] == "RULE-001"
    assert argv[argv.index("--value") + 1] == "amount must be positive"
    assert argv[argv.index("--db") + 1] == "/tmp/estate.db"


def test_set_requirement_routes_to_semantics(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    est.set_requirement("sym synthetic billing::A::a1:", "REQ text", validated=True)
    argv = cap.calls[0]
    assert argv[:2] == ["wicked-estate", "semantics"], "requirement -> node_semantics, not annotate"
    assert "sym synthetic billing::A::a1:" in argv
    assert argv[argv.index("--requirement") + 1] == "REQ text"
    assert argv[argv.index("--validated") + 1] == "true"
    # estate >= 0.30 refuses --validated without --validated-by: every write names its validator.
    assert argv[argv.index("--validated-by") + 1] == "extract-loop"
    est.set_requirement("sym synthetic billing::A::a1:", "[RISK] x", validated=False, validated_by="extract-loop:codex")
    argv = cap.calls[1]
    assert argv[argv.index("--validated") + 1] == "false"
    assert argv[argv.index("--validated-by") + 1] == "extract-loop:codex"


def test_annotate_names_its_author_when_given(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    est.annotate("sym synthetic billing::A::a1:", "business_rule", "k", "v", author="extract-loop:claude")
    argv = cap.calls[0]
    assert argv[argv.index("--author") + 1] == "extract-loop:claude"
    est.annotate("sym synthetic billing::A::a1:", "business_rule", "k", "v")
    assert "--author" not in cap.calls[1]


def test_the_harness_writes_name_the_seat(monkeypatch):
    from domain import extract_loop
    monkeypatch.setenv("WICKED_RUN_AGENT", "codex")
    assert extract_loop._seat() == "extract-loop:codex"
    monkeypatch.delenv("WICKED_RUN_AGENT")
    assert extract_loop._seat() == "extract-loop"


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


def test_resolve_fails_loud_on_non_list_shape(monkeypatch):
    # A dict/None where the CLI contract is a JSON array must RAISE, not fail-open
    # to [] (which would look like "zero hits" and hide a broken resolve contract).
    est, _ = _cli_estate(monkeypatch, json_return={"unexpected": "shape"})
    with pytest.raises(RuntimeError, match="expected a JSON array of hit objects"):
        est.resolve("charge")


def test_read_clusters_fails_loud_on_non_list_shape(monkeypatch):
    est, _ = _cli_estate(monkeypatch, json_return={"clusters": []})
    with pytest.raises(RuntimeError, match="expected a JSON array of community objects"):
        est.read_clusters()


def test_read_output_json_fails_loud_on_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="wrote no output file"):
        _clients._read_output_json(str(tmp_path / "absent.json"), "wicked-core coverage")


def test_read_annotations_uses_symbol_flag_not_positional(monkeypatch):
    est, cap = _cli_estate(monkeypatch, json_return={"symbol": "sym synthetic b::A::a1:",
                                                     "annotations": [{"key": "RULE-1"}]})
    anns = est.read_annotations("sym synthetic b::A::a1:")
    assert anns == [{"key": "RULE-1"}]
    argv = cap.calls[0]
    # `--symbol` (single-object shape), NOT the positional name-search form.
    assert argv[argv.index("--symbol") + 1] == "sym synthetic b::A::a1:"
    assert "sym synthetic b::A::a1:" not in argv[:argv.index("--symbol")], "id must not also be a positional"


def test_read_annotations_rejects_unexpected_array_shape(monkeypatch):
    est, _ = _cli_estate(monkeypatch, json_return=[{"symbol": "x", "annotations": []}])
    with pytest.raises(RuntimeError, match="expected the single-symbol object"):
        est.read_annotations("sym synthetic b::A::a1:")


def test_read_annotations_rejects_non_list_annotations_field(monkeypatch):
    est, _ = _cli_estate(monkeypatch, json_return={"symbol": "x", "annotations": None})
    with pytest.raises(RuntimeError, match="'annotations' is NoneType, expected a list"):
        est.read_annotations("sym synthetic b::A::a1:")


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
    # Mirror _resolve_bin's kill-switch: a set-but-empty env var forces "no
    # binary" (skip the integration lane), NOT a PATH fallback.
    if env in os.environ:
        return os.environ[env].strip() or None
    return shutil.which(package)


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


def test_two_seats_keep_two_rules_and_a_seat_replaces_only_its_own(monkeypatch):
    """xreview on #1361: estate's --replace is per (symbol, type, key) whatever the author, so the
    key is per seat — two seats agreeing leave two author records; a repeat replaces its own."""
    from domain import extract_loop

    class _Est:
        def __init__(self):
            self.rows = {}  # (sid, type, key) -> author, the store's replace semantics
        def annotate(self, symbol_id, type, key, value, confidence=None, provenance=None,
                     replace=True, author=None):
            self.rows[(symbol_id, type, key)] = author
        def set_requirement(self, *a, **k):
            pass
        def read_annotations(self, symbol_id):
            return [{"key": k} for (s, _t, k) in self.rows if s == symbol_id]
    est = _Est()
    rule = {"statement": "amount must be positive", "confidence": 0.9,
            "provenance": {"source": "m"}}
    for agent in ("claude", "codex", "claude"):
        monkeypatch.setenv("WICKED_RUN_AGENT", agent)
        extract_loop._write_node(est, "sym synthetic a:", "a", rule, True, "")
    authors = sorted(a for (s, t, _k), a in est.rows.items() if t == "business_rule")
    assert authors == ["extract-loop:claude", "extract-loop:codex"]


_ADR002_IDS = [
    "db2 synthetic CARDDEMO.AUTHFRDS:",
    "cobol-copybook synthetic CVACT01Y:",
    "file . README.md:",
    "ts-python local src/main.py#binding",
    "ts-cobol . . . app/cbl/CBTRN02C/CBTRN02C#1500-VALIDATE-TRAN().",
    # Descriptor names are rendered verbatim and may carry punctuation and spaces:
    # the client passes every id through unchanged.
    "ts-ruby . . . lib/account/Account#save!().",
    "ts-ruby . . . lib/account/Account#[]().",
    "ts-typescript . . . src/account/Account##balance.",
    "ts-python . . . my app/main/run().",
    "scip-python pip pkg 1.0 main().",
    "scip-python pip pkg 1.0 namespace/",
    "scip-python pip pkg 1.0 Type#",
    "scip-python pip pkg 1.0 term.",
    "scip-python pip pkg 1.0 method(overload).",
    "scip-python pip pkg 1.0 [TypeParameter]",
    "scip-python pip pkg 1.0 (parameter)",
    "scip-python pip pkg 1.0 metadata:",
    "scip-python pip pkg 1.0 macro!",
    "scip-python pip pkg 1.0 namespace/Type#method(overload).[T](arg)",
    # Global ids whose second token looks like another form's marker also pass through.
    "file . . . src/main/run().",
    "scip-x local pkg 1.0 a/b().",
    "scip-x synthetic pkg 1.0 a/b().",
    # Local ids may have more than one ``#`` in their id part.
    "ts-ruby local lib/account.rb#save#",
    "ts-ruby local lib/a#b.rb#run",
    # Synthetic/Local SCHEMES may contain spaces (node_scheme or an unset rule
    # name is the Synthetic scheme, not restricted to one token).
    "event bus synthetic topic/orders:",
    "event bus synthetic orders:",
    "my scheme local src/a.py#x",
    # estate's CSS extractor writes a multi-line selector list verbatim into a
    # Global descriptor, so a real id may carry an internal newline.
    "ts-css . . . site/src/styles/global/::view-transition-old(root),\n::view-transition-new(root)#",
    "ts-css . . . src/a.css/.a,\n.b#",
]


@pytest.mark.parametrize("sid", _ADR002_IDS)
def test_adr002_symbol_ids_are_accepted(monkeypatch, sid):
    annotations = [{"key": "RULE-001", "value": "x"}]
    est, cap = _cli_estate(monkeypatch, json_return={"symbol": sid,
                                                   "annotations": annotations})
    est.annotate(sid, "business_rule", "RULE-001", "x", confidence=0.9)
    est.set_requirement(sid, "REQ", validated=True)
    assert est.read_annotations(sid) == annotations
    assert cap.calls[0][cap.calls[0].index("--symbol") + 1] == sid
    assert sid in cap.calls[1]
    assert cap.calls[2][cap.calls[2].index("--symbol") + 1] == sid


def test_write_batch_sends_exact_ndjson_and_one_command(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    rows = [
        {"op": "annotate", "symbol": "opaque", "type": "business_rule", "key": "r1",
         "value": "amount > 0", "replace": True, "confidence": 0.9,
         "provenance": "code", "author": "seat"},
        {"op": "annotate", "symbol": "opaque", "type": "risk", "key": "r2",
         "value": "unknown", "replace": False},
        {"op": "semantics", "symbol": "opaque", "requirement": "amount > 0",
         "validated": True, "validated_by": "extract-loop"},
    ]
    paths = []
    reply = {"rows": 3, "annotations": 2, "replaced": 0, "semantics": 1}

    def invoke(argv):
        import subprocess
        cap.calls.append(argv)
        path = Path(argv[2])
        paths.append(path)
        assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == rows
        return subprocess.CompletedProcess(argv, 0, json.dumps(reply), "")

    monkeypatch.setattr(_clients, "_invoke", invoke)
    assert est.write_batch(rows) == reply
    assert cap.calls == [["wicked-estate", "write-batch", str(paths[0]),
                          "--json", "--db", "/tmp/estate.db"]]
    assert not paths[0].exists()


@pytest.mark.parametrize("stdout", [json.dumps({"rows": 0}), json.dumps({"rows": 2}), "{}", "[]",
                                    "null", "", '{"rows": 1', "Error: something else"])
def test_write_batch_reply_that_is_not_its_count_has_an_unknown_outcome(monkeypatch, stdout):
    import subprocess
    monkeypatch.setattr(_clients, "_invoke",
                        lambda argv: subprocess.CompletedProcess(argv, 0, stdout, ""))
    est = _clients.CliEstateClient(["wicked-estate"], "estate.db")
    # write-batch ran and exited 0: without its count, the page may have committed.
    with pytest.raises(_clients.BatchOutcomeUnknown, match="did not report 1 written row"):
        est.write_batch([{"op": "semantics", "symbol": "opaque"}])


def test_write_batch_rejects_a_non_json_usage_banner(monkeypatch):
    import subprocess
    monkeypatch.setattr(_clients, "_invoke", lambda argv: subprocess.CompletedProcess(
        argv, 0, "wicked-estate 0.35.8 \u2014 usage:\n  wicked-estate --version\n", ""))
    est = _clients.CliEstateClient(["wicked-estate"], "estate.db")
    with pytest.raises(RuntimeError, match="has no write-batch") as raised:
        est.write_batch([{"op": "semantics", "symbol": "opaque"}])
    assert not isinstance(raised.value, _clients.BatchOutcomeUnknown)


def test_write_batch_surfaces_estate_refusal_naming_the_row(monkeypatch):
    import subprocess
    monkeypatch.setattr(_clients, "_invoke", lambda argv: subprocess.CompletedProcess(
        argv, 1, "", "Error: write-batch refused: row 2: unknown symbol x; nothing was written"))
    est = _clients.CliEstateClient(["wicked-estate"], "estate.db")
    with pytest.raises(RuntimeError, match="row 2: unknown symbol x"):
        est.write_batch([{"op": "semantics", "symbol": "x"}])


def test_write_batch_with_no_rows_does_not_call_estate(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    assert est.write_batch([]) == {"rows": 0, "annotations": 0, "replaced": 0, "semantics": 0}
    assert cap.calls == []


def test_page_writes_queues_rows_and_checks_expectations_after_commit(monkeypatch):
    est, cap = _cli_estate(monkeypatch)
    batches, checked = [], []
    monkeypatch.setattr(est, "write_batch", lambda rows: batches.append(list(rows)), raising=False)
    page = _clients.PageWrites(est)
    page.annotate("opaque", "rule", "k", "v", confidence=0.0, provenance="code", author="seat")
    page.annotate("opaque", "risk", "k2", "v2", replace=False, provenance="", author="")
    page.set_requirement("opaque", "req", False, validated_by="")
    assert page.expect("opaque", "k", "v") is True
    assert page.expect("opaque", "k2") is True
    assert not page.written and batches == [] and cap.calls == []
    assert page._db == est._db

    def check(*args):
        assert page.written and len(batches) == 1
        checked.append(args)
        return True

    page.flush(check)
    assert checked == [("opaque", "k", "v"), ("opaque", "k2", None)]
    assert batches == [[
        {"op": "annotate", "symbol": "opaque", "type": "rule", "key": "k", "value": "v",
         "replace": True, "confidence": 0.0, "provenance": "code", "author": "seat"},
        {"op": "annotate", "symbol": "opaque", "type": "risk", "key": "k2", "value": "v2",
         "replace": False},
        {"op": "semantics", "symbol": "opaque", "requirement": "req", "validated": False,
         "validated_by": "extract-loop"},
    ]]


@pytest.mark.parametrize("operation", ["annotate", "set_requirement", "read_annotations"])
def test_cli_passes_ids_through_and_surfaces_estate_refusal(monkeypatch, operation):
    import subprocess
    calls = []

    def invoke(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "unknown node: Charge")

    monkeypatch.setattr(_clients, "_invoke", invoke)
    est = _clients.CliEstateClient(["wicked-estate"], "estate.db")
    args = {"annotate": ("Charge", "rule", "k", "v"),
            "set_requirement": ("Charge", "req", True), "read_annotations": ("Charge",)}
    with pytest.raises(RuntimeError, match="exited 1: unknown node: Charge"):
        getattr(est, operation)(*args[operation])
    assert len(calls) == 1 and "Charge" in calls[0]


# --- estate write-batch: the recorded contract ------------------------------------------------
# garden CI installs no wicked-estate, so a real estate's write-batch answers are recorded in
# fixtures/estate_write_batch_contract.json and replayed here. With wicked-estate installed, the
# live test re-runs the recording against it (WICKED_RECORD_ESTATE_CONTRACT=1 re-records it).

_CONTRACT_PATH = Path(__file__).parent / "fixtures" / "estate_write_batch_contract.json"
_CONTRACT = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))


def _queued(estate, calls):
    page = _clients.PageWrites(estate)
    for op, kwargs in calls:
        getattr(page, op)(**kwargs)
    return page


def _replay(monkeypatch, recorded):
    import subprocess
    calls = []

    def invoke(argv):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, recorded["exit"], recorded.get("stdout", ""),
                                           recorded.get("stderr", ""))

    monkeypatch.setattr(_clients, "_invoke", invoke)
    return calls


def test_a_page_queues_exactly_the_rows_estate_accepted():
    assert _queued(None, _CONTRACT["page"]).rows == _CONTRACT["page_rows"]


def test_the_recorded_commit_writes_the_whole_page_in_one_call(monkeypatch, tmp_path):
    calls = _replay(monkeypatch, _CONTRACT["committed"])
    page = _queued(_clients.CliEstateClient(["wicked-estate"], str(tmp_path / "e.db")),
                   _CONTRACT["page"])
    page.expect(_CONTRACT["page"][0][1]["symbol_id"], _CONTRACT["page"][0][1]["key"])
    checked = []
    page.flush(lambda *args: checked.append(args) or True)
    assert page.written and len(checked) == 1
    assert [argv[1] for argv in calls] == ["write-batch"]


def test_the_recorded_refusal_fails_the_page_with_nothing_written(monkeypatch, tmp_path):
    _replay(monkeypatch, _CONTRACT["refused"])
    page = _queued(_clients.CliEstateClient(["wicked-estate"], str(tmp_path / "e.db")),
                   _CONTRACT["refused_page"])
    page.expect(_CONTRACT["refused_page"][0][1]["symbol_id"], "never-read")
    with pytest.raises(RuntimeError, match=r"exited 1: .*row 2: .*not a node.*nothing was written"):
        page.flush(lambda *args: pytest.fail("no read-back after a refused batch"))
    assert not page.written
    assert _CONTRACT["refused_left_annotations"] == []  # the good row 1 did not land either


def test_an_estate_without_write_batch_fails_on_its_recorded_usage_banner(monkeypatch, tmp_path):
    banner = _CONTRACT["without_write_batch"]
    _replay(monkeypatch, {"exit": banner["exit"],
                          "stdout": banner["stdout_first_line"] + "\n  wicked-estate --version\n"})
    page = _queued(_clients.CliEstateClient(["wicked-estate"], str(tmp_path / "e.db")),
                   _CONTRACT["page"])
    with pytest.raises(RuntimeError, match="has no write-batch"):
        page.flush(lambda *args: pytest.fail("no read-back without a commit"))
    assert not page.written and not page.uncertain


def _live_estate():
    import os
    import subprocess
    exe = (os.environ["WICKED_ESTATE_BIN"].strip() if "WICKED_ESTATE_BIN" in os.environ
           else shutil.which("wicked-estate"))
    if not exe:
        return None
    try:  # a stale or missing override skips the live test; it never breaks collection
        usage = subprocess.run([exe, "--help"], capture_output=True, text=True, encoding="utf-8",
                               timeout=30)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return exe if "write-batch" in usage.stdout + usage.stderr else None


_LIVE_ESTATE = _live_estate()


@pytest.mark.skipif(_LIVE_ESTATE is None,
                    reason="no wicked-estate with write-batch installed (garden CI has none)")
def test_live_estate_answers_the_recorded_contract(tmp_path):
    import os
    import subprocess
    exe = _LIVE_ESTATE
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in _CONTRACT["repo_files"].items():
        (repo / name).write_text(text, encoding="utf-8")
    db = str(tmp_path / "estate.db")
    subprocess.run([exe, "index", str(repo), "--db", db], check=True, capture_output=True)

    def run(*args):
        p = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8")
        return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}

    def batch(calls):
        path = tmp_path / "page.ndjson"
        path.write_text("".join(json.dumps(r) + "\n" for r in _queued(None, calls).rows),
                        encoding="utf-8")
        return run("write-batch", str(path), "--json", "--db", db)

    first = _CONTRACT["page"][0][1]["symbol_id"]
    refused = batch(_CONTRACT["refused_page"])
    left = json.loads(run("annotations", "--symbol", first, "--json", "--db", db)["stdout"])
    committed = batch(_CONTRACT["page"])
    banner = run("no-such-command", "--json", "--db", db)
    observed = dict(_CONTRACT, estate=run("--version")["stdout"].strip(),
                    page_rows=_queued(None, _CONTRACT["page"]).rows, committed=committed,
                    refused=refused, refused_left_annotations=left["annotations"],
                    without_write_batch={"exit": banner["exit"],
                                         "stdout_first_line": banner["stdout"].splitlines()[0]})
    if os.environ.get("WICKED_RECORD_ESTATE_CONTRACT") == "1":
        _CONTRACT_PATH.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    version = lambda line: line.replace(observed["estate"], _CONTRACT["estate"])  # noqa: E731
    observed["without_write_batch"]["stdout_first_line"] = version(
        observed["without_write_batch"]["stdout_first_line"])
    assert {k: v for k, v in observed.items() if k != "estate"} == \
        {k: v for k, v in _CONTRACT.items() if k != "estate"}

    # The same page again through garden's own client: one call replaces the page's own
    # replace=True rows, and every annotation reads back.
    est = _clients.CliEstateClient([exe], db)
    page = _queued(est, _CONTRACT["page"])
    again = page.estate.write_batch(page.rows)
    assert again["rows"] == len(page.rows) and again["replaced"] >= 1
    keys = {(a["key"], a["value"]) for a in est.read_annotations(first)}
    assert (_CONTRACT["page"][0][1]["key"], _CONTRACT["page"][0][1]["value"]) in keys


# --- review r1 (codex): a batch whose outcome is unknown is never reported as unwritten -----------

def test_a_write_batch_that_times_out_has_an_unknown_outcome(monkeypatch):
    import subprocess

    def run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 120)

    monkeypatch.setattr(_clients.subprocess, "run", run)
    page = _clients.PageWrites(_clients.CliEstateClient(["wicked-estate"], "estate.db"))
    page.annotate("opaque", "rule", "k", "v")
    with pytest.raises(_clients.BatchOutcomeUnknown, match="exceeded"):
        page.flush(lambda *args: pytest.fail("no read-back without a reply"))
    assert page.uncertain and not page.written


def test_a_write_batch_reply_with_a_wrong_count_has_an_unknown_outcome(monkeypatch):
    import subprocess
    monkeypatch.setattr(_clients, "_invoke", lambda argv: subprocess.CompletedProcess(
        argv, 0, json.dumps({"rows": 1}), ""))
    page = _clients.PageWrites(_clients.CliEstateClient(["wicked-estate"], "estate.db"))
    page.annotate("opaque", "rule", "k", "v")
    page.annotate("opaque", "rule", "k2", "v")
    with pytest.raises(_clients.BatchOutcomeUnknown, match="did not report 2 written row"):
        page.flush(lambda *args: True)
    assert page.uncertain and not page.written


def test_a_refused_batch_is_known_unwritten(monkeypatch, tmp_path):
    _replay(monkeypatch, _CONTRACT["refused"])
    page = _queued(_clients.CliEstateClient(["wicked-estate"], str(tmp_path / "e.db")),
                   _CONTRACT["refused_page"])
    with pytest.raises(RuntimeError) as raised:
        page.flush(lambda *args: True)
    assert not isinstance(raised.value, _clients.BatchOutcomeUnknown)
    assert not page.uncertain and not page.written


@pytest.mark.parametrize("returncode", [-9, -15])
def test_a_write_batch_killed_by_a_signal_has_an_unknown_outcome(monkeypatch, returncode):
    import subprocess
    monkeypatch.setattr(_clients, "_invoke",
                        lambda argv: subprocess.CompletedProcess(argv, returncode, "", ""))
    page = _clients.PageWrites(_clients.CliEstateClient(["wicked-estate"], "estate.db"))
    page.annotate("opaque", "rule", "k", "v")
    with pytest.raises(_clients.BatchOutcomeUnknown, match="killed by signal"):
        page.flush(lambda *args: True)
    assert page.uncertain and not page.written


def test_a_write_batch_with_undecodable_output_has_an_unknown_outcome(monkeypatch):
    def run(argv, **kwargs):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(_clients.subprocess, "run", run)
    page = _clients.PageWrites(_clients.CliEstateClient(["wicked-estate"], "estate.db"))
    page.annotate("opaque", "rule", "k", "v")
    with pytest.raises(_clients.BatchOutcomeUnknown, match="undecodable"):
        page.flush(lambda *args: True)
    assert page.uncertain


@pytest.mark.parametrize("override", ["wicked-estate-not-installed", "/nonexistent/wicked-estate"])
def test_a_missing_estate_override_skips_the_live_test(monkeypatch, override):
    monkeypatch.setenv("WICKED_ESTATE_BIN", override)
    assert _live_estate() is None
