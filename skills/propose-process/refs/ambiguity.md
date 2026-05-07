---
phase_relevance: ["bootstrap", "clarify"]
archetype_relevance: ["*"]
---
# Ambiguity — when to stop and ask

The facilitator's worst failure mode is confidently planning the wrong thing. When the
description leaves too much unknown, STOP and ask BEFORE emitting tasks.

---

## Triggers for "ambiguity is high"

Any of:

1. **Two plausible reads** of the user-facing outcome. E.g. "make the dashboard feel
   faster" — caching? perceived perf? actual perf? UX polish?
2. **Missing scope boundary**. E.g. "add saved searches" — per user? per team?
   across sessions? exportable?
3. **Conflicting constraints**. E.g. "no downtime" + "rename this column."
4. **Priors disagree with the description**. E.g. description says "small change" but
   priors show 2 rollbacks on the same surface.
5. **Novelty HIGH + no prior art**. E.g. a pattern not yet in this codebase AND no
   memory entries from similar projects.
6. **Compliance implied but not stated**. E.g. "let users download their data" — GDPR
   scope is implied but the user may not realize it.
7. **Scope creep / project-sized addition** (Issue #847). The plan absorbs an item
   the user did not name in the original ask, AND that item is materially larger
   than the median item in the planned scope. Concrete heuristics — any one trips
   the trigger:
   - A single new GitHub issue, file path, or task is **3× or more the size** of
     the median item already in scope (LOC, files touched, or sub-task count).
   - Total LOC / file-count delta from baseline plan to proposed plan exceeds
     **2× the original**.
   - A new GitHub issue is labeled `epic`, `project`, or appears in another active
     project — it is its own project and should not be silently bundled.
   - User said "small change" or "fix" but the plan now spans **>3 phases** or
     **>10 tasks**.

   This catches the failure where the facilitator silently expanded a 24-issue
   wave plan to absorb a 1M-insertion sibling project. **Use the
   `scripts/crew/scope_delta.py` helper** to compute the numbers when wave
   planning so the trigger fires on data, not vibes.

Two or more triggers → mandatory stop. One trigger → facilitator judgment (lean toward
stopping when rigor_tier would be `full`).

---

## How to stop

1. Emit the "read the description" summary (Step 1 output) so the user sees what you
   heard.
2. Emit 2-5 numbered clarifying questions, max. Each should be answerable in one line.
3. Do NOT create any TaskCreate calls.
4. Do NOT emit a provisional plan as though it were the final plan.
5. Under `AskUserQuestion Fallback (Dangerous Mode)` — use plain text questions, wait
   for the user to reply; do not use the `AskUserQuestion` tool in dangerous mode.

---

## Provisional plan mode

When ambiguity is MEDIUM (one trigger, non-full-rigor work), you may emit a provisional
plan as a clearly-labeled DRAFT:

```
# Process Plan (DRAFT — pending clarification)

## Open questions
1. ...
2. ...

## Provisional plan (assumes defaults: X, Y, Z)
- phases: clarify → design → build → test → review
- specialists: ...

The `clarify` phase's first task is explicitly to resolve the open questions.
```

Ensure the FIRST task in the chain is a `clarify`-phase task titled "Resolve open
questions: [list]" so the next agent in the chain handles the disambiguation.

---

## Delegating the disambiguation

When ambiguity is HIGH and the user is available, the facilitator may invoke in its
place:

- `/wicked-garden:deliberate` — for critical-thinking decomposition of the ask.
- `/wicked-garden:jam:quick` — for a one-round brainstorm when the problem is
  genuinely open-ended.
- `/wicked-garden:product:elicit` — for requirements extraction with a
  requirements-analyst.

The facilitator does NOT do the clarify work itself; it sets up the task that will.

---

## What the questions should target

Good clarifying questions:

- Name the ambiguity. ("When you say 'faster', do you mean initial paint time, time to
  interactive, or perceived responsiveness after interaction?")
- Offer 2-3 concrete options. ("Should saved searches sync across the user's devices
  (A) by default, (B) opt-in, or (C) not at all in v1?")
- Surface compliance implications. ("This endpoint returns user data in JSON. Is this
  scoped as a GDPR data-export endpoint? If so, we'll need audit logging and a 30-day
  retention review.")
- Probe reversibility. ("If we ship this and want to undo it, is a feature-flag
  rollback acceptable, or does the data schema need to be reversible too?")

Bad questions (don't ask these):

- Open-ended "tell me more about X." — gives no decision structure.
- Yes/no questions that don't reveal intent. — "Do you want this to be good?"
- Implementation questions that the design phase should answer. — "Should we use
  Redis or Memcached?" (that's for the design phase, not clarification.)
