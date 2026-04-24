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
  - At `rigor_tier: full`, yolo is allowed **only when the user explicitly grants it**
    (via `/wicked-garden:crew:auto-approve {project} --approve` or explicit instruction);
    grant is tracked as the `yolo_approved_by_user` state field and appended to
    `yolo-audit.jsonl`. Auto-revoked if a phase-boundary re-eval detects scope
    increase or re-tier-up. Default: refused — escalate plan to user.

"Just-finish" means **run to the end autonomously**, NOT "skip phases" or "do less
work." The facilitator already picked the phase plan based on the factors; yolo mode
does not change it. If the work genuinely needs only build + review, the facilitator
chose `minimal` rigor — not because yolo was passed.

## Banned source_agent values

`just-finish-auto`, `fast-pass`, and anything starting with `auto-approve-` remain
banned even in yolo. Use `facilitator` for all facilitator-emitted tasks regardless of
interaction mode — the enforcement lives in `scripts/_event_schema.py`.

## Relationship to rigor_tier

| rigor_tier | normal           | yolo                                                |
|------------|------------------|-----------------------------------------------------|
| minimal    | light confirm    | auto-proceed end-to-end                             |
| standard   | confirm + gates  | auto-proceed; escalate on REJECT                    |
| full       | confirm + gates  | refused by default; allowed only with explicit user grant (`yolo_approved_by_user`) — auto-revoked on scope increase or re-tier-up at phase boundaries |

The `full` tier default-refusal is load-bearing: compliance and auth-rewrite work
cannot be run unsupervised without affirmative consent. When refused, surface the plan
and a short "why full rigor" note, then wait for the user to hand back control (which
becomes `normal` mode from that point on). When granted, each grant + revocation is
appended to `yolo-audit.jsonl` for audit trail.
