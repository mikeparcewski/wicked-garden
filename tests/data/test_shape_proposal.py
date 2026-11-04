"""DES-KNOWLEDGE-DATA-001 §10.1 — the data skill's `shapes` pass builds INERT `knowledge` proposals
(``scripts/data/shape_proposal.py``): ids as estate derives them, no declared deps, a closed spec, one joins edge per
related table, no loop edge, one repo, estate's evidence bound, endpoints that exist in the source's catalog, and a
shape that refuses to look like a value. The live lane (skipped without ``WICKED_ESTATE_MCP_EXE``) submits and
APPROVES the built proposal against a real wicked-estate-mcp: what the script accepts, estate approves.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "data" / "shape_proposal.py"
_spec = importlib.util.spec_from_file_location("shape_proposal", SCRIPT)
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

SID = "3f0c9a1e-0000-4000-8000-00000000b401"
CATALOG = [{"sourceId": SID, "generation": 7, "page": 0, "pages": 1,
            "docs": [{"key": k} for k in ("support.sla_events", "support.tickets", "support.users", "sales.order items")]}]
RULE = "rule synthetic support/REQ-002/RULE-001:"


def spec(**over):
    base = {
        "sourceId": SID,
        "source": "support-pg",
        "relation": "support.sla_events",
        "summary": "Each row is one SLA event of a ticket: when it was opened, breached or met.",
        "joins": [{"to": "support.tickets", "columns": ["ticket_id"], "references": ["id"], "basis": "fk"}],
        "governed_by": [{"code_id": RULE, "repo": "escalations", "label": "tickets are answered within their region's SLA hours"}],
    }
    base.update(over)
    return base


def payload(**over):
    return sp.build(spec(**over), CATALOG)["arguments"]["payload"]


def test_ids_match_estate():
    assert sp.encode_key("support.tickets") == "support.tickets"
    assert sp.encode_key("a b/é:") == "a%20b%2F%C3%A9%3A"
    assert sp.catalog_doc_id(SID, "sales.order items") == "kdoc synthetic source:%s/sales.order%%20items:" % SID


def test_builds_the_estate_call_for_an_inert_knowledge_proposal_with_no_deps():
    out = sp.build(spec(), CATALOG)
    assert out["tool"] == "proposal.submit" and out["arguments"]["kind_type"] == "knowledge"
    p = out["arguments"]["payload"]
    assert p["class"] == "concept" and p["scope"] == "source:" + SID and "deps" not in p
    assert p["relate"] == [
        {"rel": "derived_from", "to": sp.catalog_doc_id(SID, "support.sla_events"), "confidence": 1},
        {"rel": "joins", "from": sp.catalog_doc_id(SID, "support.sla_events"), "to": sp.catalog_doc_id(SID, "support.tickets"),
         "confidence": 0.95, "evidence": {"basis": "fk", "on": [{"columns": ["ticket_id"], "references": ["id"], "basis": "fk"}]}},
    ]
    assert p["relate_code"] == [{
        "rel": "governed_by", "from": sp.catalog_doc_id(SID, "support.sla_events"), "code_id": RULE, "repo": "escalations",
        "confidence": 0.7, "evidence": {"basis": "judgment", "label": "tickets are answered within their region's SLA hours"},
    }]
    assert p["content"].startswith("support.sla_events in data source support-pg: Each row is one SLA event")


def test_one_joins_edge_per_related_table_and_no_loop_edge():
    p = payload(relation="support.tickets", joins=[
        {"to": "support.users", "columns": ["reporter_id"], "references": ["id"], "basis": "fk"},
        {"to": "support.users", "columns": ["assignee_id"], "references": ["id"], "basis": "name_type"},
        {"to": "support.tickets", "columns": ["parent_id"], "references": ["id"], "basis": "fk"},
    ], governed_by=[])
    joins = [r for r in p["relate"] if r["rel"] == "joins"]
    assert len(joins) == 1 and len(joins[0]["evidence"]["on"]) == 2
    assert all(r["to"] != r.get("from") for r in p["relate"])
    assert "It joins itself on parent_id = id." in p["content"]


@pytest.mark.parametrize("over, why", [
    ({"deps": ["source:x"]}, "unknown field"),
    ({"governed_byy": []}, "unknown field"),
    ({"relation": "support.ticket"}, "not a table of the source's catalog"),
    ({"joins": [{"to": "support.nope"}]}, "not a table of the source's catalog"),
    ({"joins": [{"to": "support.tickets", "columns": "ticket_id", "references": "id"}]}, "list of column names"),
    ({"joins": [{"to": "support.tickets", "columns": ["a", "b"], "references": ["id"]}]}, "same length"),
    ({"joins": [{"to": "support.tickets", "basis": "guess"}]}, "basis"),
    ({"joins": [{"to": "support.tickets", "via": "x"}]}, "unknown field"),
    ({"describes": [{"code_id": "x", "repo": "other"}]}, "ONE repo"),
    ({"describes": [{"code_id": "x", "repo": "bad repo"}]}, "repo's id"),
    ({"describes": [{"code_id": "x", "repo": "escalations", "label": "y" * 900}]}, "at most 200 bytes"),
    ({"sourceId": "has space"}, "registry id"),
    ({"summary": "The status is 'escalated' for most rows."}, "looks like it holds a value"),
    ({"summary": "Ticket 1234 is the oldest."}, "looks like it holds a value"),
    ({"summary": "Opened on 2026-11-01 by alice@example.com."}, "looks like it holds a value"),
])
def test_refuses_what_estate_would_refuse_at_approve_or_what_looks_like_a_value(over, why):
    with pytest.raises(sp.SpecError, match=why):
        sp.build(spec(**over), CATALOG)


def test_possessives_are_prose_not_quoted_values():
    assert "customer's region" in payload(summary="A ticket's SLA follows the customer's region.")["content"]


def test_evidence_bound_is_measured_as_estate_does_utf8_and_refused_when_over():
    # Three conditions on CJK column names: about 900 bytes as UTF-8 (estate's measure), over 1,500 with \\u escapes.
    cjk = [{"to": "support.users", "columns": [ch * 80], "references": ["id"], "basis": "fk"} for ch in "列栏行"]
    p = payload(relation="support.tickets", joins=cjk, governed_by=[])
    assert len(p["relate"][1]["evidence"]["on"]) == 3
    many = [{"to": "support.tickets", "columns": ["c%02d_%s" % (i, "x" * 40)], "references": ["id"], "basis": "fk"} for i in range(20)]
    with pytest.raises(sp.SpecError, match="evidence bound"):
        sp.build(spec(joins=many), CATALOG)


def test_a_catalog_of_mixed_generations_or_another_source_is_refused():
    with pytest.raises(sp.SpecError, match="different generations"):
        sp.build(spec(), CATALOG + [{"sourceId": SID, "generation": 8, "docs": []}])
    with pytest.raises(sp.SpecError, match="not source"):
        sp.build(spec(), [{"sourceId": "other", "docs": []}])


def test_the_cli_prints_the_call_and_exits_2_on_a_bad_spec(tmp_path):
    good, cat = tmp_path / "good.json", tmp_path / "catalog.json"
    good.write_text(json.dumps(spec()), encoding="utf-8")
    cat.write_text(json.dumps(CATALOG), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), str(good), "--catalog", str(cat)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["tool"] == "proposal.submit"
    r = subprocess.run([sys.executable, str(SCRIPT), "-", "--catalog", str(cat)], input=json.dumps(spec(deps=[])), capture_output=True, text=True, check=False)
    assert r.returncode == 2 and "unknown field" in r.stderr
    r = subprocess.run([sys.executable, str(SCRIPT), str(good)], capture_output=True, text=True, check=False)
    assert r.returncode == 2


# --- the live lane: what the script builds, a real estate approves -------------------------------------------

EXE = os.environ.get("WICKED_ESTATE_MCP_EXE", "")


def _estate(home, calls):
    """Run tools/call requests against a fresh wicked-estate-mcp over stdio; one response per call, in order."""
    lines = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    lines += [{"jsonrpc": "2.0", "id": i + 1, "method": "tools/call", "params": {"name": t, "arguments": a}} for i, (t, a) in enumerate(calls)]
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "WICKED_HOME": home, "WICKED_ESTATE_DB": os.path.join(home, "estate.db"),
           "WICKED_MEMORY_DB": os.path.join(home, "memory.db"), "WICKED_KNOWLEDGE_DB": os.path.join(home, "knowledge.db"), "WICKED_XEDGE_DB": os.path.join(home, "xedge.db")}
    r = subprocess.run([EXE], input="".join(json.dumps(x) + "\n" for x in lines), capture_output=True, text=True, env=env, timeout=60, check=False)
    out = {}
    for line in r.stdout.splitlines():
        msg = json.loads(line)
        if isinstance(msg.get("id"), int) and msg["id"] > 0:
            res = msg.get("result") or {}
            text = (res.get("content") or [{}])[0].get("text", "")
            out[msg["id"]] = {"error": msg.get("error") or (text if res.get("isError") else None), "value": None if res.get("isError") else (json.loads(text) if text.startswith(("{", "[")) else text)}
    return [out.get(i + 1) for i in range(len(calls))]


@pytest.mark.skipif(not EXE, reason="needs WICKED_ESTATE_MCP_EXE (a wicked-estate-mcp at or after e6b1f9a)")
def test_live_what_the_script_builds_estate_approves():
    with tempfile.TemporaryDirectory() as home:
        docs = [{"key": k, "title": k, "entry": {}, "sections": [{"key": "columns", "text": k + ": columns"}]} for k in ("support.sla_events", "support.tickets", "support.users")]
        call = sp.build(spec(relation="support.tickets", joins=[
            {"to": "support.users", "columns": ["reporter_id"], "references": ["id"], "basis": "fk"},
            {"to": "support.users", "columns": ["assignee_id"], "references": ["id"], "basis": "fk"},
            {"to": "support.tickets", "columns": ["parent_id"], "references": ["id"], "basis": "fk"},
        ]), CATALOG)
        rs = _estate(home, [("knowledge.replace_source", {"sourceId": SID, "generation": 1, "label": "support-pg", "docs": docs}), (call["tool"], call["arguments"])])
        assert rs[0]["error"] is None, rs[0]
        assert rs[1]["error"] is None, rs[1]
        pid = rs[1]["value"]["id"]
        approved = _estate(home, [("proposal.approve", {"id": pid})])[0]
        assert approved["error"] is None, approved
        assert approved["value"]["outcome"] == "promoted"
