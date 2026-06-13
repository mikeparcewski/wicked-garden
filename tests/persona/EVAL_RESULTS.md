# Persona lift eval — executed result (committed evidence, not assertion)

`define.md` says: *"Don't claim a persona is better by assertion — if you want proof it lifts
behaviour, add an eval."* This file records the eval actually being **run**, so the built-in
personas' value rests on measured evidence, not a maintainer's say-so.

## Protocol
Fair two-arm, blinded. Per case: a **baseline** arm (no persona) and a **persona** arm (the exact
built-in methodology) reviewed the same task. Outputs were written to randomized A/B filenames and an
**independent** grader (wrote neither arm; blind to the mapping) scored each output yes/no against the
case's failure-mode assertions. `lift = persona_yes − baseline_yes`; PASS if ≥ 1.

## Result (run 2026-06-12, base model: a current strong frontier model)
| Case | persona_yes | baseline_yes | lift | result |
|---|:-:|:-:|:-:|---|
| agentic (runaway loop / ungated delete / over-broad access) | 3/3 | 3/3 | **0** | FAIL |
| platform (secret-in-logs / blast-radius) | 2/2 | 2/2 | **0** | FAIL |
| qe (self-graded done / untested recovery) | 2/2 | 2/2 | **0** | FAIL |

**No measurable lift.** The base model already flagged every targeted failure mode unprompted; the
persona arm matched but did not exceed it. The personas did not regress anything.

## Honest reading
- On a **strong base model**, for these **textbook-egregious** cases, the built-in personas are
  **redundant** — empirically. This supports the recommendation to treat the built-ins as ILLUSTRATIVE
  exemplars and the **`persona:define` mechanism as the actual product** (it lets you inject HOUSE
  methodology the base model cannot know — which is where lift should live).
- **Limits:** N=3 is weak; tasks are obvious; the grader scored binary "addressed?" not depth. Lift may
  still exist on subtler cases, weaker models, or domain-specific house personas — none tested here.
- **Do not** re-assert that the built-ins improve output without re-running (and strengthening) this eval.
