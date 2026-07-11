---
name: quick-facilitator-shape
title: jam quick runs inline (no dispatch) and produces correct synthesis shape
description: Verify jam quick runs INLINE via skills/jam/refs/quick.md — dispatching no facilitator subagent (neither the retired quick-facilitator nor brainstorm-facilitator) — and still emits the canonical 3-section synthesis shape (Key Insights / Action Items / Open Questions) shared with brainstorm-facilitator.
type: workflow
difficulty: basic
estimated_minutes: 3
tags: [jam, quick, synthesis-shape, context-budget, inline]
complexity: 2
execution: manual
---

# Scenario: jam quick Inline Shape

Verify that `jam quick` runs **inline** — applying `skills/jam/refs/quick.md`
directly in the parent context with **no facilitator dispatch** — and that the
output synthesis block has the required fields at lower token cost.

> **Conversion note.** In the skills-only model the `quick-facilitator` agent was
> retired; `skills/jam/SKILL.md` routes the `quick` sub-action inline via
> `refs/quick.md` (the sole, up-to-date rubric). This scenario guards that the
> quick path stays inline and does NOT regress into dispatching a facilitator
> (the retired `quick-facilitator`, or `brainstorm-facilitator`).

## Setup

No special setup required. This scenario runs against the live plugin.

## Steps

### Step 1 — Invoke jam quick

Run:
```
jam quick "Should we use SQLite or a flat JSON file for local plugin state?"
```

(This routes to the `quick` sub-action of the `wicked-garden-jam` skill.)

### Step 2 — Assert: runs inline, no facilitator dispatched

`jam quick` must produce its synthesis **inline** — by reading
`skills/jam/refs/quick.md` and applying the rubric directly. There must be **no**
`Task(...)` or `Skill(skill=...)` dispatch to any facilitator worker.

**FAIL** if a dispatch to `quick-facilitator` appears (that agent was retired).
**FAIL** if a dispatch to `brainstorm-facilitator` appears (the quick path must
not escalate to the full brainstorm worker).

### Step 3 — Assert: synthesis block present

The output must contain a section matching:

```markdown
## Quick Jam: {topic}

### Key Insights
### Action Items
### Open Questions
```

All three headings must be present. **FAIL** if any heading is missing.

### Step 4 — Assert: field shape matches brainstorm-facilitator

The inline synthesis block must include the same three section headings that
`brainstorm-facilitator` produces — the heading vocabulary is the contract, and
`refs/quick.md` is authored to preserve it:

| Field | jam quick (inline) | brainstorm-facilitator |
|-------|--------------------|------------------------|
| Key Insights | required | required |
| Action Items | required | required |
| Open Questions | required | required |

Heading parity (#669 fix): callers consuming either the inline quick output or
the brainstorm-facilitator output read the same field names without branching.
**FAIL** if any section heading is absent or renamed.

### Step 5 — Assert: exactly 4 personas

Count `**[Name]** ({archetype})` patterns in the output. Must equal 4. **FAIL** if fewer or more.

### Step 6 — Assert: single round only

The output must NOT contain any of these markers:
- `Round 2`
- `Building & Responding`
- `Second round`
- `Convergence check`

**FAIL** if any multi-round marker is present.

### Step 7 — Assert: no storage calls

The output must NOT contain:
- `save_transcript.py`
- `wicked-brain:memory` store calls
- `EventStore.append`
- `wicked-bus emit`

**FAIL** if any storage or event emission appears.

### Step 8 — Assert: wall time < 60s

Record start time before invocation. Synthesis must arrive within 60 seconds —
the documented "60-second flow" budget for `jam quick` (#669 fix; the prior
30-second threshold was a self-inflicted false-FAIL risk because real-world
single-pass model latency can spike past 30s without indicating a regression).

**WARN** if between 30-60s. **FAIL** if > 60s.

### Step 9 — Token cost comparison (rough check)

Run the same topic through `jam brainstorm` with 1 forced round as a baseline
(brainstorm still dispatches the `wicked-garden-jam-brainstorm-facilitator` fork
skill). Compare total output character count (proxy for token cost):

- inline quick output chars: `N_quick`
- brainstorm-facilitator output chars: `N_full`

**PASS** if `N_quick < N_full * 0.5` (quick costs less than 50% of brainstorm).
**WARN** if between 50-70%.
**FAIL** if quick output is larger than brainstorm output.

## Expected Outcome

```
PASS: runs inline, no facilitator dispatch
PASS: synthesis block present with all 3 headings
PASS: field shape matches brainstorm-facilitator contract
PASS: exactly 4 personas
PASS: single round only
PASS: no storage calls
PASS: wall time < 60s
PASS: token cost < 50% of brainstorm-facilitator
```

## Failure Modes

| Failure | Diagnosis |
|---------|-----------|
| A facilitator was dispatched | `skills/jam/SKILL.md` quick routing regressed — quick must run inline via `refs/quick.md`, not dispatch |
| Missing synthesis heading | `skills/jam/refs/quick.md` output format diverged from the shared 3-heading contract |
| Round 2 present | Inline rubric ignored the single-round constraint |
| Storage calls present | Inline rubric carried over brainstorm-facilitator persistence behavior |
| Token cost > 50% | Inline rubric loaded too much context or added rounds |
