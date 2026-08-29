# specify — turn an ask into testable acceptance criteria

When the implementation path is clear-ish but the success criteria are
fuzzy. Produces SMART acceptance criteria — Specific, Measurable,
Achievable, Relevant, Time-bound — that downstream `build` can verify.

## Phase shape

| Phase    | Goal                                                       |
|----------|------------------------------------------------------------|
| elicit   | Surface the user's intent through targeted questions.      |
| structure | Convert intent into REQ-/AC- numbered acceptance criteria.|
| validate | Confirm with the user that the ACs match their intent.    |

## Produces

- **SMART acceptance criteria** in the form `AC-N: when X, then Y`.
- One-line invariants: "A response time over 500ms is a regression".
- Optional: a `requirements.md` artifact in the project dir.

The validate gate **re-derives** this via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the recorded `smart-acceptance-criteria`
artifact is re-hashed and its structural verifier re-run, never trusting
a self-asserted "the ACs are testable". wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden-core setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather
than claiming a PASS. `--no-require` opts a throwaway/low-rigor run back
to the doctrine-light claim-only path. This is a discrete (light) gate —
the deterministic check proves *shape* (each AC is measurable); if the
AC *quality* needs an independent sign-off, the judgment tier
(`wicked-vault analyze-evidence` / `--with-attestations`) is available.

## HITL

`discrete:validate-gate` — the validate phase is a hard checkpoint. Don't
proceed past validate without explicit user agreement on the AC set.

## How to run

### elicit

1. Use `/wicked-garden-product elicit` if requirements analysis is needed,
   or jump in directly when the surface is small.
2. Ask 3–5 questions. Each should be answerable in one line and target a
   specific dimension: scope, success metric, failure mode, edge case,
   non-goal.
3. **Don't ask open-ended "tell me more about X".** Force the user to pick
   between concrete options.

### structure

1. If a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`), declare the
   re-derivable contract for this phase so the validate gate has a bar to
   check against: `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase specify --spec contract.json`
   — `required_evidence` should pin `smart-acceptance-criteria`
   (kind `spec-doc`) to a `regex_match` verifier proving the criteria are
   testable/measurable (e.g. each AC carries a measurable assertion or a
   Given/When/Then shape). Skip silently if no vault.
2. Convert each elicited fact into one acceptance criterion: `AC-N: when
   <trigger>, then <observable>`.
3. Add invariants for things that should NOT change: `INV-N: <thing> must
   stay under <threshold>`.
4. Keep ACs minimal — 3–7 is the sweet spot. More than 10 means you're
   treating ACs as design.
5. Record the AC artifact as re-derivable evidence (vault present;
   **wicked-vault ≥ 0.4.0**):
   `wicked-vault record --scope <scope> --phase specify
   --claim smart-acceptance-criteria --kind spec-doc
   --artifact <path/to/requirements.md>
   --criteria "<the testability bar>"
   --verifier regex_match:'(?im)^(AC|INV)-\d+:'
   --actor "${WICKED_VAULT_ACTOR:-garden-prove}" --run`. The **`--actor`**
   records under an explicit identity so that if AC quality needs an
   independent sign-off (the optional `--with-attestations` judgment tier
   above), vault ≥ 0.4.0 will let that attestation through instead of
   refusing it as a weak/ambient identity. The verifier re-runs against
   the artifact later — a claim you can't re-derive is not evidence. No
   vault → fall back to the claim-only path.

### validate

1. Show the user the AC list.
2. Ask: "is anything missing? is anything wrong? is anything overspecified?"
3. **Hard gate**: do not exit specify until the user explicitly approves the
   AC set. "Looks good" is enough; silence is not.
4. If they want changes, loop back to elicit or structure as appropriate.

## When to stop

Specify is done when the user has signed off on the AC list AND the
produces-gate is satisfied. Check the gate — don't self-assert it:
`scripts/qe/prove.py <claim> --by "<command>" --scope <scope> --phase specify` (frictionless, single claim — re-derive, don't assert) — or the full multi-claim contract via `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase specify`
(exit 0 = satisfied). This is a re-derived PASS over the declared
contract: the AC artifact is re-hashed and its structural verifier
re-run. A REJECT means the recorded ACs don't clear the testability bar —
fix the criteria, not the claim. An `unavailable` verdict means the
required vault isn't installed — run `/wicked-garden-core setup`. Then hand off
to `build` (when the next step is implementation), `decide` (when you've
uncovered competing options), or `explore` (when the act of writing ACs
revealed the problem isn't well understood).

## Anti-patterns

- **Don't write design inside ACs.** "AC-1: implementation uses Redis"
  is a design choice, not an acceptance criterion. Use `decide` for that.
- **Don't merge multiple criteria into one.** Split them so each is
  individually testable.
- **Don't auto-pass the validate gate.** The whole point is the user
  agrees this is what they wanted.
