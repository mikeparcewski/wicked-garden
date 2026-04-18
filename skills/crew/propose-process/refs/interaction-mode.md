# Interaction mode — yolo / `/wicked-garden:crew:just-finish`

**Interaction mode is orthogonal to phase plan, specialist selection, rigor tier, and
evidence requirements.** Those are determined by the work itself via the facilitator
rubric, regardless of whether the user wants interactive or autonomous completion.

Interaction mode controls ONLY whether the user is prompted at gate boundaries:

- **normal** (default): user confirms the plan before task creation; reviewer verdicts
  at each gate surface to the user for approval.
- **yolo** / `auto_proceed=true` / `/wicked-garden:crew:just-finish`:
  - Skip user confirmation on the initial plan when `rigor_tier` is `minimal` or `standard`.
  - Auto-approve gates whose reviewer verdict is APPROVE.
  - Silently accept CONDITIONAL gates when the conditions are self-resolving spec gaps.
  - Escalate to user on REJECT verdicts with no clear fix, or CONDITIONAL requiring
    intent changes.
  - NEVER operate in yolo when `rigor_tier` is `full` — escalate to user with the plan.

"Just-finish" means **run to the end autonomously**, NOT "skip phases" or "do less
work." The facilitator already picked the phase plan based on the factors; yolo mode
does not change it. If the work genuinely needs only build + review, the facilitator
chose `minimal` rigor — not because yolo was passed.

## Banned source_agent values

`just-finish-auto`, `fast-pass`, and anything starting with `auto-approve-` remain
banned even in yolo. Use `facilitator` for all facilitator-emitted tasks regardless of
interaction mode — the enforcement lives in `scripts/_event_schema.py`.

## Relationship to rigor_tier

| rigor_tier | normal           | yolo                                 |
|------------|------------------|--------------------------------------|
| minimal    | light confirm    | auto-proceed end-to-end              |
| standard   | confirm + gates  | auto-proceed; escalate on REJECT     |
| full       | confirm + gates  | REFUSE yolo — escalate plan to user  |

The `full` tier's refusal is load-bearing: compliance and auth-rewrite work cannot be
run unsupervised. Surface the plan and a short "why full rigor" note, then wait for
the user to hand back control (which becomes `normal` mode from that point on).
