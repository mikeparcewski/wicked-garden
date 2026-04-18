---
name: 08-ambiguous-ask
title: Facilitator Rubric — Ambiguous Ask ("Feel Faster")
description: Verify the facilitator invokes deliberate + jam:quick BEFORE planning when ambiguity is high, and emits clarifying questions.
type: rubric
difficulty: intermediate
estimated_minutes: 3
---

# "Make the Dashboard Feel Faster"

## Input

> Make the dashboard feel faster.

## Expected facilitator behavior

Ambiguity triggers fire: two plausible reads (perceived perf? actual perf? backend?
frontend? network? caching?), missing scope boundary (which dashboard? which users?),
and the word "feel" signals UX perception, not raw numbers. The facilitator STOPS
and emits clarifying questions BEFORE creating a full task chain. A provisional
plan MAY be emitted as DRAFT, but the first task in the chain must be a clarify task.

Expected invocations: `/wicked-garden:deliberate` + `/wicked-garden:jam:quick`
recommended in the process-plan (not auto-executed by the facilitator; they're the
NEXT step).

## Expected outcome

```yaml
specialists:
  - requirements-analyst       # to own the clarification
  - ux-designer                # "feel faster" is a UX concept
  - product-manager
  # additional specialists deferred until clarify completes
phases:
  - clarify                   # ONLY phase emitted confidently
  # remainder is provisional / pending clarification
evidence_required: []          # cannot commit evidence until scope is clear
test_types: []
complexity: 4             # ±2 tolerance — too early to score tightly
rigor_tier: standard        # floor; may escalate to full after clarify
factors:
  reversibility: UNKNOWN
  blast_radius: UNKNOWN
  compliance_scope: LOW
  user_facing_impact: HIGH
  novelty: MEDIUM
  scope_effort: UNKNOWN
  state_complexity: UNKNOWN
  operational_risk: UNKNOWN
  coordination_cost: UNKNOWN
open_questions:
  - "Which dashboard — admin, customer, internal?"
  - "By 'faster', do you mean initial paint, time-to-interactive, or perceived responsiveness after an interaction?"
  - "Is there a specific user complaint, a metric regressing, or a visible slowdown you want to address?"
  - "What's the rollout appetite — feature-flag experiment, or ship to everyone?"
re_evaluation: not-applicable
requires_jam_quick_or_deliberate: true
ambiguity_stop: true
```

## Success criteria

- [ ] `open_questions` has at least 2 entries
- [ ] `ambiguity_stop: true` or a single-phase `clarify` emitted, NOT a full chain
- [ ] process-plan recommends `/wicked-garden:deliberate` and/or `/wicked-garden:jam:quick`
- [ ] `requirements-analyst` and `ux-designer` are picked (or equivalent)
- [ ] evidence_required is empty (or only on the clarify task itself)
- [ ] complexity tolerance is ±2 (too early to score tightly)
