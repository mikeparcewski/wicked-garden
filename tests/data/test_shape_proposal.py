"""DES-KNOWLEDGE-DATA-001 §10.1 — the data skill's `shapes` pass builds INERT `knowledge` proposals
(``scripts/data/shape_proposal.py``): ids as estate derives them, no declared deps, a closed set of typed links,
estate's evidence bound, and a summary that refuses to carry a value.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "data" / "shape_proposal.py"
_spec = importlib.util.spec_from_file_location("shape_proposal", SCRIPT)
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

SID = "3f0c9a1e-0000-4000-8000-00000000b401"


def spec(**over):
    base = {
        "sourceId": SID,
        "source": "support-pg",
        "relation": "support.sla_events",
        "summary": "Each row is one SLA event of a ticket: when it was opened, breached or met.",
        "joins": [{"to": "support.tickets", "columns": ["ticket_id"], "references": ["id"], "basis": "fk"}],
        "governed_by": [{"code_id": "rule synthetic support/REQ-002/RULE-001:", "repo": "escalations", "label": "tickets are answered within their region's SLA hours"}],
    }
    base.update(over)
    return base


def test_ids_match_estate():
    assert sp.encode_key("support.tickets") == "support.tickets"
    assert sp.encode_key("a b/é:") == "a%20b%2F%C3%A9%3A"
    assert sp.catalog_doc_id(SID, "support.tickets") == "kdoc synthetic source:%s/support.tickets:" % SID


def test_builds_an_inert_knowledge_proposal_with_typed_links_and_no_deps():
    out = sp.build(spec())
    assert out["kind_type"] == "knowledge"
    p = out["payload"]
    assert p["class"] == "concept" and p["scope"] == "source:" + SID and "deps" not in p
    assert p["relate"][0] == {"rel": "derived_from", "to": sp.catalog_doc_id(SID, "support.sla_events"), "confidence": 1}
    assert p["relate"][1]["rel"] == "joins" and p["relate"][1]["to"] == sp.catalog_doc_id(SID, "support.tickets")
    assert p["relate"][1]["confidence"] == 0.95
    assert p["relate_code"] == [{
        "rel": "governed_by", "from": sp.catalog_doc_id(SID, "support.sla_events"),
        "code_id": "rule synthetic support/REQ-002/RULE-001:", "repo": "escalations", "confidence": 0.7,
        "evidence": {"basis": "judgment", "label": "tickets are answered within their region's SLA hours"},
    }]
    assert p["content"].startswith("support.sla_events in data source support-pg: Each row is one SLA event")
    assert "Governed by tickets are answered" in p["content"]


@pytest.mark.parametrize("bad, why", [
    ({"deps": ["source:x"]}, "never declare deps"),
    ({"summary": "The status is 'escalated' for most rows."}, "looks like it holds a value"),
    ({"summary": "Ticket 1234567 is the oldest."}, "looks like it holds a value"),
    ({"sourceId": "has space"}, "registry id"),
    ({"joins": [{"to": "support.tickets", "basis": "guess"}]}, "basis"),
    ({"describes": [{"code_id": "x", "repo": "bad repo"}]}, "repo"),
    ({"describes": [{"code_id": "x", "repo": "r", "label": "y" * 900}]}, "at most 200"),
])
def test_refuses_what_estate_would_refuse_or_what_would_leak_a_value(bad, why):
    with pytest.raises(sp.SpecError, match=why):
        sp.build(spec(**bad))


def test_the_cli_prints_the_submit_arguments_and_exits_2_on_a_bad_spec(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(spec()), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), str(good)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["payload"]["relate"][0]["rel"] == "derived_from"
    r = subprocess.run([sys.executable, str(SCRIPT), "-"], input=json.dumps(spec(deps=[])), capture_output=True, text=True, check=False)
    assert r.returncode == 2 and "never declare deps" in r.stderr
