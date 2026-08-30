---
phase_relevance: ["clarify", "design", "build", "test"]
archetype_relevance: ["specify", "build", "ship", "review"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-12, ADR 0006). Loaded on
     demand via Read() from the router's `intake` action — not a skill. -->


# qe campaign intake — propose-as-gate (v1)

The human-confirmation leg between § campaign (recon + generation) and
§ execute: the generated scenario set is **proposed as a HITL gate on the
campaign's own governed wicked-crew run**, and the three gate outcomes are
the intake verbs. All three are campaign-proven over **UI + REST** (studio
gate card + `POST /api/v1/runs/:id/gate` — S9 approve+amend PASS, S10 deny
PASS). The MCP `answer_gate` leg is NOT relied on: it was not proven in this
campaign's evidence — re-verify it before building on it.

| Decision | Wire body | Effect |
|---|---|---|
| approve | `{"approve": true}` | the confirmed set runs unchanged |
| amend | `{"approve": true, "amend": "…"}` | approve-with-edits — the amend text is the scenario-edit channel (grammar below) |
| reject | `{"approve": false}` | the run cancels; nothing executes |

Never hand-build the body — `gate_decision_body()` in the glue is the wire
shape (crew's `GateSchema` is strict: an extra key is a 400).

## Flow

1. § campaign produces a validated `campaign-recon.json` (never propose an
   unvalidated plan — the glue refuses).
2. Build the proposal + prompt:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_intake.py" \
     propose .wicked-qe/campaigns/<name>/campaign-recon.json
   ```

   The prompt is what the governed run surfaces at its human gate
   (`GET /runs/:id/gate` → `prompt`; studio renders it on the gate card).
   It embeds the machine payload (`qe.campaign.intake` format 1) as a
   marked, fenced JSON block — `parse_gate_prompt()` recovers it losslessly,
   and amend directives reference the stable rung ids printed in the table.
3. The operator answers the gate (studio UI or REST). Crew hands the amend
   text back to the worker; apply it deterministically:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_intake.py" \
     decide <plan.json> --approve [--amend <amend.txt>] --out <plan.json>
   # or: decide <plan.json> --reject
   ```

   `decision: amended` re-validates fail-closed — an amended plan that no
   longer conforms (dangling deps, laundered pending-review rungs) is
   REFUSED, and the gate answer surfaces the defect instead of executing a
   broken ladder.
4. Approved/amended plans proceed to § execute; proposed rungs that were not
   confirmed at the gate stay `pending-review` and do NOT execute.

## Amend grammar (the scenario-edit channel)

Line-oriented, deterministic. Directive lines edit the plan; **every other
non-empty line is a steer note** — returned to the authoring agent, recorded,
never silently dropped. A malformed directive (e.g. `retitle S2` with no
text) is an ERROR, never demoted to prose.

```
drop S3                      # remove a rung (refuses if others depend on it —
                             #   the honest cascade names every drop explicitly)
retitle S2: <new title>      # rename a rung
defer S4                     # confirmed → proposed (pulled from this execution)
confirm S5                   # proposed → confirmed (refused while any bound
                             #   capability is still proposed — no laundering)
note S1: <text>              # append to the rung's execution notes
anything else                # steer text for the authoring agent
```

## Annotation-anchor input ("point at the app, describe what to verify")

Input format documented from wicked-studio's built-and-tested annotation
model — `FeedbackOverlay.tsx` (FeedbackItem `{wid, text, mode, before}`,
`store/docThread.ts`), the `WidRect` + scroll-state anchoring math proven in
`tests/feedbackAnchoring.test.ts`, and `interactive/instrument-protocol.ts`
(`WidBlock.text` = the normalized innerText snapshot). Studio anchors on
`data-wid`; app-under-test surfaces anchor on `data-testid`.
`screenshot_crop` is optional extra evidence derived from the rect — studio
itself does not capture one.

```json
{
  "anchor": {
    "selector": {"kind": "wid" | "testid" | "css", "value": "new-project-modal"},
    "rect":   {"x":120,"y":64,"width":300,"height":48,"top":64,"left":120,"right":420,"bottom":112},
    "scroll": {"scrollX": 0, "scrollY": 0},
    "before": "normalized innerText snapshot",
    "screenshot_crop": "path/to/crop.png"
  },
  "intent": "what to verify (free text)",
  "mode": "comment" | "change-text"
}
```

`rect`/`scroll`/`before`/`screenshot_crop` are optional; `selector` + `intent`
are required. Convert mechanically:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_intake.py" \
  from-annotations <annotations.json>
```

Output = human-lens capability entries (**always `status: "proposed"`** — a
pointed-at claim flows through the same pending-review gate as doc-derived
claims; the human confirmed the surface exists, not that it behaves) plus
proposed `ui` rungs, ready for `assemble_plan(human_capabilities=…)`. Bind
each annotation to the capability inventory during recon so "test the
checkout flow" resolves to concrete surfaces before the writer runs, and
resolve anchors against the BUILT surface actually served — selector drift
is the proven failure mode.

## Elicitation port (v2, blocked crew-side)

Free-form conversational refinement is NOT v1 — and the block is
**wicked-crew's adapter, not core**: `resolveElicitation` is a deliberate
always-throw stub (crew `packages/crew/src/core/adapter.ts:1225-1240` →
HTTP 501 at `routes.ts:1372`) even though the engine implements it
(`wicked-core/src/lib.rs:686`) and the napi binding ships in the published
wicked-core-ts 0.7.2 crew already pins. Tracked in
[wicked-crew#358](https://github.com/mikeparcewski/wicked-crew/issues/358)
(the engine-side tracker core#234 is CLOSED; design: crew
`.product/DES-002-acp-session-elicitation.md`).

**The proposal payload is designed to port unchanged**: the same
`qe.campaign.intake` block recovered by `parse_gate_prompt()` today becomes
the elicitation prompt body when crew#358 lands — no format change, only the
wire moves (`POST /runs/:id/elicitation`, `{elicitationId, action:
accept|decline|cancel, content.response}` mapping onto approve/amend/reject).
The round-trip test (`tests/qe/test_campaign_intake.py`) pins that contract.

## References

- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_intake.py` — proposal/decision/annotation glue
- [refs/campaign.md](campaign.md) — recon + generation (produces the plan this action proposes)
- [refs/execute.md](execute.md) · [refs/accept.md](accept.md) — what runs after approval
- crew gate wire: `POST/GET /api/v1/runs/:id/gate` (`GateSchema` — approve/amend/reject)
- wicked-crew#358 — elicitation follow-on (v2 unlock)
