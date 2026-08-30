"""qe campaign intake — propose-as-gate (TH-12 / test-R12).

AC: **the generated scenario set is proposed as a crew HITL gate** and all
three campaign-proven outcomes work over the REST wire — approve runs the
set unchanged, amend is the scenario-edit channel, reject cancels. Proven
here against a HERMETIC gate fixture: a real HTTP daemon (stdlib
`http.server`, ephemeral 127.0.0.1 port) that mirrors crew's gate wire
semantics exactly —

- `GET  /api/v1/runs/:id/gate`  → `{runId, ord, prompt, lifecycle, receivedAt}`
  while `awaiting_human`, 404 otherwise (routes.ts:1195);
- `POST /api/v1/runs/:id/gate`  → body `GateSchema = {approve: bool,
  amend?: str}` STRICT (routes.ts:171), 409 when the run is not awaiting a
  human gate (routes.ts:1108-1112), approve:false = reject/cancel
  (routes.ts:1086 comment).

The elicitation port contract is pinned by the round-trip test: the payload
recovered from the gate prompt is byte-identical to the proposal, so it can
ride `POST /runs/:id/elicitation` unchanged when crew#358 lands.

Disjoint-build discipline: stdlib + the campaign glue modules only.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import campaign_intake as ci  # noqa: E402
import campaign_plan as cp  # noqa: E402


# --------------------------------------------------------------------------
# plan fixture — a three-rung ladder with one proposed (doc-derived) rung
# --------------------------------------------------------------------------


def make_plan() -> dict:
    return cp.assemble_plan(
        target={
            "repo": "mikeparcewski/wicked-crew",
            "ref": "deadbeef",
            "surface_url": "http://127.0.0.1:7899/",
        },
        estate_capabilities=[
            {
                "id": "projects-crud",
                "surface": "Projects CRUD — /projects (ProjectsPage)",
                "apis": "POST/GET /projects (client.ts:560-578)",
                "test_shape": "PASS = new project card; wire = 200 {project}",
                "needs": "isolated daemon",
                "citations": ["client.ts:560-578"],
            }
        ],
        docs_capabilities=[
            {
                "id": "export-pdf",
                "surface": "Export as PDF (claimed by README, unverified)",
                "apis": "POST /export (README.md:88 — no route node found)",
                "test_shape": "PASS = downloadable PDF artifact",
                "needs": "unknown",
                "citations": ["README.md:88"],
            }
        ],
        scenarios=[
            {
                "id": "S1",
                "title": "API smoke",
                "category": "api",
                "capability_ids": ["projects-crud"],
                "deps": [],
                "pass_criteria": {
                    "terminal_state": "daemon healthy after CRUD",
                    "artifact": "captured wire JSON",
                    "consumer_state": "project in a later GET",
                },
                "claim_ceiling": "machinery-verified",
            },
            {
                "id": "S2",
                "title": "Projects CRUD through the real UI",
                "category": "ui",
                "capability_ids": ["projects-crud"],
                "deps": ["S1"],
                "pass_criteria": {
                    "terminal_state": "project persisted across reload",
                    "artifact": "screenshot + wire capture",
                    "consumer_state": "dashboard renders the project",
                },
                "claim_ceiling": "certified",
            },
            {
                "id": "S3",
                "title": "Doc-claimed PDF export (unverified)",
                "category": "ui",
                "capability_ids": ["export-pdf"],
                "deps": ["S2"],
                "pass_criteria": {
                    "terminal_state": "export completes",
                    "artifact": "PDF exists and is non-empty",
                    "consumer_state": "download visible",
                },
                "claim_ceiling": "machinery-verified",
            },
        ],
        environment_manifest={"ref": "environment-manifest.json"},
        name="crew-intake-smoke",
        generated_at="2026-08-29T12:00:00Z",
    )


# --------------------------------------------------------------------------
# hermetic gate fixture — crew's gate wire, faithfully
# --------------------------------------------------------------------------


class _GateState:
    """One governed run holding at a human gate."""

    def __init__(self, run_id: str, prompt: str):
        self.run_id = run_id
        self.prompt = prompt
        self.status = "awaiting_human"
        self.decisions: list[dict] = []


class _GateHandler(BaseHTTPRequestHandler):
    state: _GateState  # set by the fixture

    def log_message(self, *args):  # silence
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _gate_path_run_id(self) -> str | None:
        parts = [p for p in self.path.split("/") if p]
        if (
            len(parts) == 5
            and parts[0] == "api"
            and parts[1] == "v1"
            and parts[2] == "runs"
            and parts[4] == "gate"
        ):
            return parts[3]
        return None

    def do_GET(self):  # noqa: N802 (stdlib naming)
        run_id = self._gate_path_run_id()
        if run_id is None:
            return self._send(404, {"error": "Not found"})
        if run_id != self.state.run_id:
            return self._send(404, {"error": "Run not found"})
        if self.state.status != "awaiting_human":
            # routes.ts:1212-1214 — only awaiting_human has an open gate
            return self._send(404, {"error": "No open gate for this run"})
        self._send(
            200,
            {
                "runId": run_id,
                "ord": 0,
                "prompt": self.state.prompt,
                "lifecycle": "open",
                "receivedAt": "2026-08-29T12:00:01Z",
            },
        )

    def do_POST(self):  # noqa: N802
        run_id = self._gate_path_run_id()
        if run_id is None:
            return self._send(404, {"error": "Not found"})
        if run_id != self.state.run_id:
            return self._send(404, {"error": "Run not found"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "Invalid request body"})
        # GateSchema (routes.ts:171): {approve: bool, amend?: str} — STRICT.
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("approve"), bool)
            or not set(body) <= {"approve", "amend"}
            or ("amend" in body and not isinstance(body["amend"], str))
        ):
            return self._send(400, {"error": "Invalid request body"})
        if self.state.status != "awaiting_human":
            # routes.ts:1108-1112
            return self._send(
                409,
                {
                    "error": "Run is not awaiting a human gate "
                    f"(status: {self.state.status})"
                },
            )
        self.state.decisions.append(body)
        # approve+amend = approve-with-steer; approve:false = reject (cancels)
        self.state.status = "running" if body["approve"] else "cancelled"
        self._send(200, {"status": self.state.status})


@pytest.fixture()
def gate_daemon():
    """Open a hermetic gate holding the intake proposal; yield (base, state)."""
    plan = make_plan()
    proposal = ci.build_gate_proposal(plan, plan_path="campaign-recon.json")
    prompt = ci.render_gate_prompt(proposal)
    state = _GateState("run-intake-1", prompt)

    handler = type("Handler", (_GateHandler,), {"state": state})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base, state, plan, proposal
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, dict]:
    try:
        with urlrequest.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urlerror.HTTPError as err:
        return err.code, json.loads(err.read())


def _post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urlrequest.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urlerror.HTTPError as err:
        return err.code, json.loads(err.read())


# --------------------------------------------------------------------------
# AC — the scenario set is proposed as a HITL gate (over the wire)
# --------------------------------------------------------------------------


def test_scenario_set_is_proposed_as_an_open_gate(gate_daemon):
    base, state, plan, proposal = gate_daemon
    code, gate = _get(f"{base}/api/v1/runs/{state.run_id}/gate")
    assert code == 200
    assert gate["lifecycle"] == "open"
    assert gate["runId"] == "run-intake-1"

    # The prompt the operator sees carries the whole scenario set, and the
    # payload parses back out losslessly — the elicitation port contract.
    recovered = ci.parse_gate_prompt(gate["prompt"])
    assert recovered == proposal
    assert recovered["kind"] == "qe.campaign.intake"
    assert recovered["format"] == 1
    assert [r["id"] for r in recovered["scenarios"]] == ["S1", "S2", "S3"]
    # honesty rides to the gate verbatim
    assert recovered["sources"] == plan["sources"]
    assert recovered["counts"]["proposed_rungs"] == 1  # S3 (doc-derived)
    # and the port note names the crew follow-on this payload waits for
    assert "wicked-crew/issues/358" in recovered["port"]["blocked_by"]


def test_approve_runs_the_set_unchanged(gate_daemon):
    base, state, plan, _ = gate_daemon
    code, resp = _post(
        f"{base}/api/v1/runs/{state.run_id}/gate", ci.gate_decision_body(True)
    )
    assert (code, resp["status"]) == (200, "running")
    outcome = ci.apply_gate_decision(plan, True)
    assert outcome["decision"] == "approved"
    assert outcome["plan"] == plan  # unchanged
    assert outcome["ops"] == [] and outcome["steers"] == []


def test_amend_is_the_scenario_edit_channel(gate_daemon):
    base, state, plan, _ = gate_daemon
    amend = "\n".join(
        [
            "drop S3",
            "retitle S2: Projects CRUD through the served UI bundle",
            "note S1: pin the daemon version in the evidence manifest",
            "please keep the whole run under 10 minutes",  # steer, not an op
        ]
    )
    code, resp = _post(
        f"{base}/api/v1/runs/{state.run_id}/gate",
        ci.gate_decision_body(True, amend),
    )
    assert (code, resp["status"]) == (200, "running")
    # crew hands the SAME amend string to the worker; intake applies it:
    outcome = ci.apply_gate_decision(plan, True, state.decisions[0]["amend"])
    assert outcome["decision"] == "amended"
    amended = outcome["plan"]
    ids = [r["id"] for r in amended["scenarios"]]
    assert ids == ["S1", "S2"]  # S3 dropped
    s1, s2 = amended["scenarios"]
    assert s2["title"] == "Projects CRUD through the served UI bundle"
    assert s1["notes"] == "pin the daemon version in the evidence manifest"
    assert outcome["steers"] == ["please keep the whole run under 10 minutes"]
    # the amended plan still conforms — fail-closed by construction
    assert cp.plan_errors(amended) == []
    # the original plan was deep-copied, never mutated
    assert [r["id"] for r in plan["scenarios"]] == ["S1", "S2", "S3"]


def test_reject_cancels_and_the_gate_is_consumed(gate_daemon):
    base, state, plan, _ = gate_daemon
    code, resp = _post(
        f"{base}/api/v1/runs/{state.run_id}/gate", ci.gate_decision_body(False)
    )
    assert (code, resp["status"]) == (200, "cancelled")
    outcome = ci.apply_gate_decision(plan, False, "wrong repo ref")
    assert outcome["decision"] == "rejected"
    assert outcome["plan"] == plan
    assert outcome["steers"] == ["wrong repo ref"]

    # the gate is consumed: a second answer is a 409, a re-read a 404
    code, resp = _post(
        f"{base}/api/v1/runs/{state.run_id}/gate", ci.gate_decision_body(True)
    )
    assert code == 409
    assert "not awaiting a human gate" in resp["error"]
    code, _ = _get(f"{base}/api/v1/runs/{state.run_id}/gate")
    assert code == 404


def test_decision_body_is_exactly_gate_schema_shaped(gate_daemon):
    """A strict-schema wire rejects anything but {approve, amend?}."""
    base, state, _, _ = gate_daemon
    url = f"{base}/api/v1/runs/{state.run_id}/gate"
    assert _post(url, {"approve": True, "extra": 1})[0] == 400
    assert _post(url, {"approve": "yes"})[0] == 400
    assert _post(url, {})[0] == 400
    # the helper's output is accepted (gate still open — 400s consumed nothing)
    assert ci.gate_decision_body(True, "x") == {"approve": True, "amend": "x"}
    assert ci.gate_decision_body(False) == {"approve": False}
    code, _ = _post(url, ci.gate_decision_body(True))
    assert code == 200


# --------------------------------------------------------------------------
# amend grammar — fail-closed, never a silent no-op
# --------------------------------------------------------------------------


def test_amend_refuses_unknown_rung_and_malformed_directives():
    plan = make_plan()
    with pytest.raises(ci.CampaignIntakeError, match="does not name a rung"):
        ci.apply_amendments(plan, "drop S9")
    with pytest.raises(ci.CampaignIntakeError, match="needs ': <text>'"):
        ci.apply_amendments(plan, "retitle S2")
    with pytest.raises(ci.CampaignIntakeError, match="takes no ': <text>'"):
        ci.apply_amendments(plan, "drop S3: because")


def test_amend_drop_refuses_implicit_dependent_cascade():
    plan = make_plan()
    with pytest.raises(ci.CampaignIntakeError, match="S3 depend on it"):
        ci.apply_amendments(plan, "drop S2")
    # the honest cascade is explicit — both drops named
    amended, ops, _ = ci.apply_amendments(plan, "drop S3\ndrop S2")
    assert [r["id"] for r in amended["scenarios"]] == ["S1"]
    assert [op["op"] for op in ops] == ["drop", "drop"]


def test_amend_confirm_cannot_launder_a_proposed_capability():
    """`confirm S3` hits the assembler's own honesty invariant: S3 certifies
    the still-proposed doc-derived capability, so the amended plan is
    rejected — the intake gate cannot be used to skip pending review."""
    plan = make_plan()
    with pytest.raises(
        ci.CampaignIntakeError, match="still 'proposed'"
    ):
        ci.apply_amendments(plan, "confirm S3")


def test_amend_defer_flips_a_rung_to_proposed():
    plan = make_plan()
    amended, _, _ = ci.apply_amendments(plan, "defer S2")
    s2 = next(r for r in amended["scenarios"] if r["id"] == "S2")
    assert s2["status"] == "proposed"
    assert cp.plan_errors(amended) == []


def test_proposal_refuses_a_nonconforming_plan():
    plan = make_plan()
    plan["scenarios"][0]["capability_ids"] = ["ghost-capability"]
    with pytest.raises(ci.CampaignIntakeError, match="refusing to propose"):
        ci.build_gate_proposal(plan)


# --------------------------------------------------------------------------
# annotation intake — studio FeedbackOverlay's anchor shape as input
# --------------------------------------------------------------------------


ANNOTATION = {
    "anchor": {
        "selector": {"kind": "testid", "value": "new-project-modal"},
        "rect": {
            "x": 120, "y": 64, "width": 300, "height": 48,
            "top": 64, "left": 120, "right": 420, "bottom": 112,
        },
        "scroll": {"scrollX": 0, "scrollY": 0},
        "before": "New project",
    },
    "intent": "creating a project from this modal persists across a reload",
    "mode": "comment",
}


def test_annotation_becomes_a_proposed_human_capability_and_rung():
    intake = ci.intake_from_annotations([ANNOTATION])
    cap = intake["capabilities"][0]
    assert cap["source"] == "human"
    assert cap["status"] == "proposed"  # pointed-at ≠ verified — always
    assert "data-testid=new-project-modal" in cap["surface"]
    rung = intake["scenarios"][0]
    assert rung["status"] == "proposed"
    assert rung["capability_ids"] == [cap["id"]]

    # the annotation-derived entries assemble into a CONFORMING plan and the
    # proposal surfaces them as pending review at the gate
    plan = make_plan()
    plan2 = cp.assemble_plan(
        target=plan["target"],
        estate_capabilities=[
            c for c in plan["capabilities"] if c["source"] == "estate"
        ],
        docs_capabilities=[],
        human_capabilities=intake["capabilities"],
        scenarios=[plan["scenarios"][0], *intake["scenarios"]],
        environment_manifest={"ref": "environment-manifest.json"},
        name="annotation-intake",
        generated_at="2026-08-29T12:00:00Z",
    )
    assert cp.plan_errors(plan2) == []
    proposal = ci.build_gate_proposal(plan2)
    assert proposal["counts"]["proposed_rungs"] == 1
    assert proposal["counts"]["proposed_capabilities"] == 1


def test_annotation_requires_anchor_selector_and_intent():
    with pytest.raises(ci.CampaignIntakeError, match="anchor"):
        ci.capability_from_annotation({"intent": "x"})
    with pytest.raises(ci.CampaignIntakeError, match="intent"):
        ci.capability_from_annotation(
            {"anchor": {"selector": {"kind": "wid", "value": "b1"}}}
        )
    with pytest.raises(ci.CampaignIntakeError, match="selector.kind"):
        ci.capability_from_annotation(
            {"anchor": {"selector": {"kind": "xpath", "value": "x"}},
             "intent": "y"}
        )
