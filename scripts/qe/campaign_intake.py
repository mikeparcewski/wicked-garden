#!/usr/bin/env python3
"""qe campaign intake — propose-as-gate glue (TH-12, test-R12).

Deterministic helpers behind the `intake` action of the `wicked-garden-qe`
router (`skills/qe/refs/intake.md`). Interactive intake v1 is
**propose-as-gate**: the campaign action proposes its generated scenario set
as a human (HITL) gate on its own governed wicked-crew run, and the three
gate outcomes are the intake verbs — all campaign-proven over UI + REST
(`POST /api/v1/runs/:id/gate`, body `{approve: bool, amend?: str}`):

- **approve** (`{approve: true}`) — the confirmed set runs unchanged;
- **amend**  (`{approve: true, amend: "..."}`) — the amend text is the
  scenario-edit channel: directive lines edit the plan deterministically
  (see AMEND GRAMMAR below), everything else is steer text for the
  authoring agent — recorded, never silently dropped;
- **reject** (`{approve: false}`) — the run cancels; nothing executes.

The proposal payload (`qe.campaign.intake` format 1) is embedded in the
human-readable gate prompt as a marked, fenced JSON block and parses back
out losslessly (`parse_gate_prompt`). That round-trip is the port contract:
the SAME payload is designed to ride the elicitation wire unchanged
(`POST /runs/:id/elicitation`) once crew's adapter stops stubbing it out.

TODO(crew#358): free-form conversational refinement is blocked by
wicked-crew's adapter — `resolveElicitation` is a deliberate always-throw
stub (crew `packages/crew/src/core/adapter.ts:1225-1240` → 501 at
`routes.ts:1372`) even though the engine implements it
(`wicked-core/src/lib.rs:686`) and the napi binding ships in the published
wicked-core-ts 0.7.2 crew already pins. core#234 (the engine tracker) is
CLOSED; https://github.com/mikeparcewski/wicked-crew/issues/358 tracks the
crew wiring. When it lands, `build_gate_proposal`'s output becomes the
elicitation prompt body with no format change.

Cross-platform: pure stdlib (json/re/argparse/copy), no shell.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QE_SCRIPTS = Path(__file__).resolve().parent
for _p in (_REPO_ROOT / "scripts", _QE_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import campaign_plan as cp  # noqa: E402

PROPOSAL_KIND = "qe.campaign.intake"
PROPOSAL_FORMAT = 1

#: The crew follow-on this payload is designed to port onto (see module
#: docstring). Keep in sync with skills/qe/refs/intake.md.
CREW_ELICITATION_ISSUE = "https://github.com/mikeparcewski/wicked-crew/issues/358"

#: Marker line preceding the fenced payload in the rendered gate prompt.
#: `parse_gate_prompt` keys on it, so the prompt stays human-editable prose
#: everywhere else without breaking the round-trip.
PAYLOAD_MARKER = "<!-- qe-campaign-intake:1 -->"

_FENCE_RE = re.compile(
    re.escape(PAYLOAD_MARKER) + r"\s*```json\s*\n(.*?)\n```",
    re.DOTALL,
)


class CampaignIntakeError(ValueError):
    """An intake proposal or gate decision violated the contract."""


# --------------------------------------------------------------------------
# proposal — the scenario set as a gate payload
# --------------------------------------------------------------------------

def build_gate_proposal(plan: dict, *, plan_path: str | None = None) -> dict:
    """The machine-readable half of the gate prompt (fail-closed).

    Refuses a nonconforming plan — a gate must never propose a scenario set
    the validator would reject after approval. The `sources` block rides
    verbatim (honesty: an unindexed plan says so at the gate, not buried),
    and every rung carries the fields the human decides on.
    """
    errors = cp.plan_errors(plan)
    if errors:
        raise CampaignIntakeError(
            "refusing to propose a nonconforming plan:\n" + "\n".join(errors)
        )

    rungs = []
    proposed_rungs = 0
    for rung in plan["scenarios"]:
        if rung.get("status", "confirmed") == "proposed":
            proposed_rungs += 1
        entry = {
            "id": rung["id"],
            "title": rung.get("title", rung["id"]),
            "category": rung["category"],
            "status": rung.get("status", "confirmed"),
            "deps": list(rung.get("deps", []) or []),
            "capability_ids": list(rung.get("capability_ids", []) or []),
            "claim_ceiling": rung["claim_ceiling"],
        }
        if rung.get("scenario_path"):
            entry["scenario_path"] = rung["scenario_path"]
        rungs.append(entry)

    proposed_caps = sum(
        1 for c in plan["capabilities"] if c.get("status") == "proposed"
    )

    proposal: dict = {
        "kind": PROPOSAL_KIND,
        "format": PROPOSAL_FORMAT,
        "campaign": plan.get("name") or "campaign",
        "target": dict(plan["target"]),
        "sources": dict(plan["sources"]),
        "counts": {
            "scenarios": len(rungs),
            "proposed_rungs": proposed_rungs,
            "proposed_capabilities": proposed_caps,
        },
        "scenarios": rungs,
        "decision_contract": {
            "wire": "POST /api/v1/runs/:id/gate {approve: bool, amend?: str}",
            "approve": "run the confirmed scenario set unchanged",
            "amend": (
                "approve with edits: directive lines (drop/retitle/defer/"
                "confirm/note <rung-id>) edit the plan deterministically; "
                "other lines are steer notes for the authoring agent"
            ),
            "reject": "cancel the run; nothing executes",
        },
        "port": {
            "design": (
                "this payload rides the elicitation wire unchanged when "
                "crew's adapter wiring lands"
            ),
            "blocked_by": CREW_ELICITATION_ISSUE,
        },
    }
    if plan_path:
        proposal["plan_path"] = plan_path
    return proposal


def render_gate_prompt(proposal: dict) -> str:
    """The human-readable gate prompt with the payload embedded.

    What the operator sees on the campaign-proven surfaces (studio's gate
    card, `GET /runs/:id/gate` → `prompt`). The fenced payload after
    `PAYLOAD_MARKER` keeps the prompt machine-recoverable: amend directives
    reference the stable rung ids printed in the table.
    """
    counts = proposal["counts"]
    sources = proposal["sources"]
    lines = [
        f"## qe campaign intake — {proposal['campaign']}",
        "",
        f"Proposing {counts['scenarios']} scenario(s) against "
        f"`{proposal['target'].get('repo', '?')}`.",
        f"Sources: estate={sources.get('estate')}, "
        f"docs_recall={json.dumps(sources.get('docs_recall'))}, "
        f"live_probe={json.dumps(sources.get('live_probe'))}.",
    ]
    if counts["proposed_rungs"] or counts["proposed_capabilities"]:
        lines.append(
            f"Pending review: {counts['proposed_rungs']} proposed rung(s), "
            f"{counts['proposed_capabilities']} proposed capability claim(s) "
            "— these do NOT execute unless confirmed."
        )
    lines += [
        "",
        "| id | title | category | status | ceiling | deps |",
        "|---|---|---|---|---|---|",
    ]
    for rung in proposal["scenarios"]:
        deps = ", ".join(rung["deps"]) or "—"
        lines.append(
            f"| {rung['id']} | {rung['title']} | {rung['category']} | "
            f"{rung['status']} | {rung['claim_ceiling']} | {deps} |"
        )
    lines += [
        "",
        "**approve** — run the confirmed set unchanged. "
        "**reject** — cancel; nothing executes. "
        "**amend** — approve with edits; directive lines "
        "(`drop S3`, `retitle S2: new title`, `defer S4`, `confirm S5`, "
        "`note S1: text`) edit the plan deterministically, all other lines "
        "steer the authoring agent.",
        "",
        PAYLOAD_MARKER,
        "```json",
        json.dumps(proposal, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return "\n".join(lines)


def parse_gate_prompt(prompt: str) -> dict:
    """Recover the proposal payload from a rendered gate prompt (lossless).

    This round-trip is the elicitation port contract — the payload a future
    elicitation prompt carries is exactly what this returns today.
    """
    match = _FENCE_RE.search(prompt)
    if not match:
        raise CampaignIntakeError(
            f"no {PAYLOAD_MARKER} payload block found in the gate prompt"
        )
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise CampaignIntakeError(f"payload block is not valid JSON: {exc}")
    if payload.get("kind") != PROPOSAL_KIND:
        raise CampaignIntakeError(
            f"payload kind {payload.get('kind')!r} is not {PROPOSAL_KIND!r}"
        )
    if payload.get("format") != PROPOSAL_FORMAT:
        raise CampaignIntakeError(
            f"payload format {payload.get('format')!r} is not "
            f"{PROPOSAL_FORMAT} — refuse rather than misread"
        )
    return payload


# --------------------------------------------------------------------------
# amend — the scenario-edit channel
# --------------------------------------------------------------------------

_DIRECTIVE_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(drop|retitle|defer|confirm|note)\s+"
    r"([A-Za-z0-9][A-Za-z0-9_-]*)\s*(?::\s*(.*))?\s*$"
)

#: Directives that require trailing `: text`, and those that must not have it.
_NEEDS_TEXT = {"retitle", "note"}
_NO_TEXT = {"drop", "defer", "confirm"}


def parse_amendments(amend_text: str) -> tuple[list[dict], list[str]]:
    """Split amend text into directive ops and freeform steer notes.

    Line-oriented and deterministic. A line that starts like a directive but
    is malformed (missing/forbidden `: text`) is an ERROR, not a steer note —
    a typo must never silently downgrade an edit into prose. Anything that
    does not look like a directive at all is a steer note: recorded and
    returned for the authoring agent, never silently dropped.
    """
    ops: list[dict] = []
    steers: list[str] = []
    for raw in (amend_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _DIRECTIVE_RE.match(line)
        if not match:
            steers.append(line)
            continue
        verb, rung_id, text = match.group(1), match.group(2), match.group(3)
        if verb in _NEEDS_TEXT and not (text and text.strip()):
            raise CampaignIntakeError(
                f"amend directive {verb!r} needs ': <text>' — got {line!r}"
            )
        if verb in _NO_TEXT and text is not None:
            raise CampaignIntakeError(
                f"amend directive {verb!r} takes no ': <text>' — got {line!r}"
            )
        op: dict = {"op": verb, "rung_id": rung_id}
        if text is not None:
            op["text"] = text.strip()
        ops.append(op)
    return ops, steers


def apply_amendments(plan: dict, amend_text: str) -> tuple[dict, list[dict], list[str]]:
    """Apply amend directives to a (deep-copied) plan, fail-closed.

    - unknown rung id → error (never a silent no-op);
    - `drop` refuses when a surviving rung still depends on the dropped one
      (an explicit extra `drop` is the honest cascade, never an implicit one);
    - the amended plan must STILL pass `campaign_plan.plan_errors` — e.g.
      `confirm` on a rung certifying a still-proposed capability is rejected
      by the same honesty invariant that guards assembly.
    """
    ops, steers = parse_amendments(amend_text)
    amended = copy.deepcopy(plan)
    rungs: list[dict] = amended.get("scenarios", []) or []
    by_id = {r.get("id"): r for r in rungs}

    dropped: set[str] = set()
    for op in ops:
        rid = op["rung_id"]
        if rid not in by_id or rid in dropped:
            raise CampaignIntakeError(
                f"amend {op['op']!r}: rung {rid!r} does not name a rung in "
                "the proposed plan"
            )
        rung = by_id[rid]
        if op["op"] == "drop":
            dependents = [
                r["id"]
                for r in rungs
                if r["id"] not in dropped
                and r["id"] != rid
                and rid in (r.get("deps") or [])
            ]
            if dependents:
                raise CampaignIntakeError(
                    f"amend 'drop {rid}': rung(s) {', '.join(dependents)} "
                    f"depend on it — drop those too (explicitly) or keep it"
                )
            dropped.add(rid)
        elif op["op"] == "retitle":
            rung["title"] = op["text"]
        elif op["op"] == "defer":
            rung["status"] = "proposed"
        elif op["op"] == "confirm":
            rung["status"] = "confirmed"
        elif op["op"] == "note":
            existing = rung.get("notes")
            rung["notes"] = f"{existing}\n{op['text']}" if existing else op["text"]

    if dropped:
        amended["scenarios"] = [r for r in rungs if r["id"] not in dropped]

    errors = cp.plan_errors(amended)
    if errors:
        raise CampaignIntakeError(
            "amended plan does not conform to campaign-recon format v1:\n"
            + "\n".join(errors)
        )
    return amended, ops, steers


def gate_decision_body(approve: bool, amend: str | None = None) -> dict:
    """The exact `POST /api/v1/runs/:id/gate` request body for a decision.

    crew's `GateSchema` is `{approve: bool, amend?: str}` and STRICT — an
    extra key is a 400. This helper is the wire shape in one place so intake
    callers never hand-build it.
    """
    body: dict = {"approve": bool(approve)}
    if amend is not None:
        body["amend"] = amend
    return body


def apply_gate_decision(
    plan: dict, approve: bool, amend: str | None = None
) -> dict:
    """Map one crew gate decision (`{approve, amend?}`) onto the plan.

    Returns `{decision, plan, ops, steers}`:

    - `rejected`  — approve:false; the plan is untouched, nothing executes
      (the governed run cancels). Any amend text rides back as the reason.
    - `approved`  — approve:true, no amend; the plan runs unchanged.
    - `amended`   — approve:true + amend; directives are applied fail-closed
      and steer notes surface for the authoring agent.
    """
    if not approve:
        return {
            "decision": "rejected",
            "plan": plan,
            "ops": [],
            "steers": [amend.strip()] if amend and amend.strip() else [],
        }
    if amend is None or not amend.strip():
        return {"decision": "approved", "plan": plan, "ops": [], "steers": []}
    amended, ops, steers = apply_amendments(plan, amend)
    return {"decision": "amended", "plan": amended, "ops": ops, "steers": steers}


# --------------------------------------------------------------------------
# annotation intake — "point at the app, describe what to verify"
# --------------------------------------------------------------------------
#
# Input format documented from wicked-studio's built-and-tested annotation
# anchor model (FeedbackOverlay.tsx + tests/feedbackAnchoring.test.ts):
# an anchor is a stable element selector — studio uses `data-wid` (FeedbackItem
# `{wid, text, mode, before}` in store/docThread.ts); app-under-test surfaces
# use `data-testid` — plus the measured `WidRect` and scroll state at
# measurement time (interactive/instrument-protocol.ts), with `before` as the
# normalized innerText snapshot. `screenshot_crop` is OPTIONAL extra evidence
# derived from the rect — studio itself does not capture one.
#
# {
#   "anchor": {
#     "selector": {"kind": "wid" | "testid" | "css", "value": "..."},
#     "rect":   {x, y, width, height, top, left, right, bottom},   # optional
#     "scroll": {"scrollX": n, "scrollY": n},                       # optional
#     "before": "normalized innerText snapshot",                    # optional
#     "screenshot_crop": "path/to/crop.png"                         # optional
#   },
#   "intent": "what to verify (free text)",
#   "mode": "comment" | "change-text"                               # optional
# }

_SELECTOR_KINDS = {"wid", "testid", "css"}
_SELECTOR_ATTR = {"wid": "data-wid", "testid": "data-testid", "css": "css"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _check_annotation(annotation: dict) -> tuple[dict, str]:
    anchor = annotation.get("anchor")
    if not isinstance(anchor, dict):
        raise CampaignIntakeError("annotation: missing anchor object")
    selector = anchor.get("selector")
    if not isinstance(selector, dict):
        raise CampaignIntakeError("annotation: anchor.selector is required")
    kind, value = selector.get("kind"), selector.get("value")
    if kind not in _SELECTOR_KINDS:
        raise CampaignIntakeError(
            f"annotation: selector.kind {kind!r} is not one of "
            f"{sorted(_SELECTOR_KINDS)}"
        )
    if not (isinstance(value, str) and value.strip()):
        raise CampaignIntakeError("annotation: selector.value is required")
    intent = annotation.get("intent")
    if not (isinstance(intent, str) and intent.strip()):
        raise CampaignIntakeError("annotation: intent text is required")
    return anchor, intent.strip()


def capability_from_annotation(annotation: dict) -> dict:
    """A human-lens capability inventory entry from one annotation.

    ALWAYS `status: "proposed"` — a pointed-at claim flows through the same
    pending-review intake gate as doc-derived claims; a human confirmed the
    surface exists, not that the capability behaves.
    """
    anchor, intent = _check_annotation(annotation)
    selector = anchor["selector"]
    attr = _SELECTOR_ATTR[selector["kind"]]
    where = f"{attr}={selector['value']}"
    rect = anchor.get("rect")
    if isinstance(rect, dict):
        where += (
            f" (rect {rect.get('width')}x{rect.get('height')}"
            f"@{rect.get('left')},{rect.get('top')} at measurement)"
        )
    before = anchor.get("before")
    surface = f"Annotated surface — {where}"
    if isinstance(before, str) and before.strip():
        surface += f'; text at annotation: "{before.strip()[:120]}"'
    entry = {
        "id": f"annot-{_slug(selector['value'])}",
        "surface": surface,
        "apis": (
            "unresolved — bind to the capability inventory during recon "
            f"(annotation anchored at {where})"
        ),
        "test_shape": f"PASS = {intent}",
        "needs": (
            "resolve the anchor against the BUILT surface actually served "
            "(selector drift is the proven failure mode)"
        ),
        "source": "human",
        "status": "proposed",
    }
    crop = anchor.get("screenshot_crop")
    if isinstance(crop, str) and crop.strip():
        entry["needs"] += f"; screenshot crop: {crop.strip()}"
    return entry


def rung_from_annotation(
    annotation: dict,
    capability_id: str,
    *,
    rung_id: str | None = None,
    deps: list[str] | None = None,
) -> dict:
    """A PROPOSED ui rung certifying one annotation-derived capability.

    Proposed (pending review) by construction — the assembler's honesty
    invariant then refuses to confirm it while the capability stays
    proposed, which is exactly the intake gate's job to resolve.
    """
    _, intent = _check_annotation(annotation)
    return {
        "id": rung_id or f"A-{_slug(capability_id)}",
        "title": intent[:100],
        "category": "ui",
        "capability_ids": [capability_id],
        "deps": list(deps or []),
        "pass_criteria": {
            "terminal_state": f"annotated intent holds: {intent}",
            "artifact": (
                "screenshot of the anchored surface + wire capture for the "
                "interaction"
            ),
            "consumer_state": (
                "the anchored element reflects the verified state in the "
                "served DOM (re-queried, not cached)"
            ),
        },
        "claim_ceiling": "certified",
        "status": "proposed",
    }


def intake_from_annotations(annotations: list[dict]) -> dict:
    """Capabilities + rungs for `assemble_plan(human_capabilities=…)`."""
    capabilities: list[dict] = []
    rungs: list[dict] = []
    seen: set[str] = set()
    for i, annotation in enumerate(annotations):
        cap = capability_from_annotation(annotation)
        if cap["id"] in seen:
            cap["id"] = f"{cap['id']}-{i}"
        seen.add(cap["id"])
        capabilities.append(cap)
        rungs.append(
            rung_from_annotation(annotation, cap["id"], rung_id=f"A{i + 1}")
        )
    return {"capabilities": capabilities, "scenarios": rungs}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="campaign_intake",
        description="qe campaign intake: propose-as-gate / decide / annotations",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prop = sub.add_parser(
        "propose", help="render a plan's scenario set as a gate prompt"
    )
    p_prop.add_argument("plan", type=Path)
    p_prop.add_argument(
        "--json", action="store_true", help="emit the payload, not the prompt"
    )

    p_dec = sub.add_parser(
        "decide", help="apply a gate decision {approve, amend?} to a plan"
    )
    p_dec.add_argument("plan", type=Path)
    group = p_dec.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true")
    group.add_argument("--reject", action="store_true")
    p_dec.add_argument(
        "--amend", type=Path, help="file with amend text (directives + steers)"
    )
    p_dec.add_argument(
        "--out", type=Path, help="write the resulting plan JSON here"
    )

    p_ann = sub.add_parser(
        "from-annotations",
        help="human-lens capabilities + proposed rungs from annotation JSON",
    )
    p_ann.add_argument("annotations", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.cmd == "propose":
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            proposal = build_gate_proposal(plan, plan_path=str(args.plan))
            if args.json:
                print(json.dumps(proposal, indent=2, ensure_ascii=False))
            else:
                print(render_gate_prompt(proposal))
            return 0

        if args.cmd == "decide":
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            amend = (
                args.amend.read_text(encoding="utf-8") if args.amend else None
            )
            outcome = apply_gate_decision(plan, bool(args.approve), amend)
            if args.out:
                args.out.write_text(
                    json.dumps(outcome["plan"], indent=2, ensure_ascii=False)
                    + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "decision": outcome["decision"],
                        "ops": outcome["ops"],
                        "steers": outcome["steers"],
                        **(
                            {"plan_written": str(args.out)}
                            if args.out
                            else {}
                        ),
                    },
                    indent=2,
                )
            )
            return 0

        if args.cmd == "from-annotations":
            annotations = json.loads(
                args.annotations.read_text(encoding="utf-8")
            )
            if not isinstance(annotations, list):
                raise CampaignIntakeError(
                    "annotations file must be a JSON array"
                )
            print(
                json.dumps(
                    intake_from_annotations(annotations),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
    except (CampaignIntakeError, cp.CampaignPlanError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
