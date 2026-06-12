# Persona LIFT eval cases (model-graded — user-gated)

These cases measure the **behavioral lift** a methodology persona provides over
the base model on a representative task. They are the complement to the
deterministic suite in `tests/persona/test_persona_methodology_lift.py`:

| Half | What it proves | Cost | When it runs |
|------|----------------|------|--------------|
| `test_persona_methodology_lift.py` | The persona *carries* a named failure-mode defense + scope guard, the dispatch template *surfaces* it, the define mechanism *round-trips* it | free, deterministic | every `pytest` run |
| `eval_cases/*.json` (this dir) | The persona *changes the model's output* — it raises the specific failure mode the base model omits | paid Claude API calls | user-triggered only |

## Why this design (re-derive, don't assert)

This family's thesis is "measure the lift, don't assert it." A persona only
earns its keep if it produces something the base model does not. So each case
runs the SAME task twice — once with no persona (the `baseline` arm) and once
through `persona:as <name>` (the `persona` arm) — and scores whether the
**persona arm raises a specific failure mode the baseline arm omits**. If the
baseline already raises it, the lift is ~0 and the persona adds little durable
value (a finding worth knowing).

## Schema

Each `*.json` case:

```jsonc
{
  "case_id": "platform-secret-leak-lift",     // unique id
  "persona": "platform",                       // methodology persona under test
  "task": "Review this code: <snippet>",       // identical prompt for both arms
  "arms": {
    "baseline": { "system": null },             // base model, no persona
    "persona":  { "system": "via persona:as platform" }
  },
  "lift_assertions": [                          // what the PERSONA arm must do
    {
      "id": "raises-secret-leak",
      "must_mention_any": ["secret", "credential", "token", "API key", "leak"],
      "rationale": "the planted bug logs an API key; platform must catch it"
    }
  ],
  "baseline_expectation": "may_omit",           // we EXPECT the baseline to omit ≥1 lift assertion
  "scoring": "model_graded",                    // a grader model judges each arm's output
  "grader_rubric": "For each lift_assertion, does the output address it? yes/no."
}
```

`lift_score = (# lift_assertions met by persona arm) - (# met by baseline arm)`.
A case PASSES when `lift_score >= 1` (the persona raised at least one failure
mode the baseline missed). `lift_score <= 0` is a real signal: the persona is
not pulling its weight on this task.

## Running (paid — user must opt in)

These are NOT run by `pytest` (no `test_` prefix, and they require API calls).
To execute the full model-graded eval, a human runs:

```bash
# Pseudocode — wire to your preferred runner (Claude API / wicked-testing evals).
# Each arm is one Claude call; the grader is one more. ~3 calls/case.
python3 tests/persona/eval_cases/run_lift_eval.py        # (not provided — user-gated)
```

Until a runner is wired, the cases stand as an executable SPEC of what lift to
measure. The deterministic suite already gates that the lift can structurally
exist; these cases gate that it behaviorally does.
