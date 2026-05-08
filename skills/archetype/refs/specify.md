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

## HITL

`discrete:validate-gate` — the validate phase is a hard checkpoint. Don't
proceed past validate without explicit user agreement on the AC set.

## How to run

### elicit

1. Use `/wicked-garden:product:elicit` if requirements analysis is needed,
   or jump in directly when the surface is small.
2. Ask 3–5 questions. Each should be answerable in one line and target a
   specific dimension: scope, success metric, failure mode, edge case,
   non-goal.
3. **Don't ask open-ended "tell me more about X".** Force the user to pick
   between concrete options.

### structure

1. Convert each elicited fact into one acceptance criterion: `AC-N: when
   <trigger>, then <observable>`.
2. Add invariants for things that should NOT change: `INV-N: <thing> must
   stay under <threshold>`.
3. Keep ACs minimal — 3–7 is the sweet spot. More than 10 means you're
   treating ACs as design.

### validate

1. Show the user the AC list.
2. Ask: "is anything missing? is anything wrong? is anything overspecified?"
3. **Hard gate**: do not exit specify until the user explicitly approves the
   AC set. "Looks good" is enough; silence is not.
4. If they want changes, loop back to elicit or structure as appropriate.

## When to stop

Specify is done when the user has signed off on the AC list. Hand off to
`build` (when the next step is implementation), `decide` (when you've
uncovered competing options), or `explore` (when the act of writing ACs
revealed the problem isn't well understood).

## Anti-patterns

- **Don't write design inside ACs.** "AC-1: implementation uses Redis"
  is a design choice, not an acceptance criterion. Use `decide` for that.
- **Don't merge multiple criteria into one.** Split them so each is
  individually testable.
- **Don't auto-pass the validate gate.** The whole point is the user
  agrees this is what they wanted.
