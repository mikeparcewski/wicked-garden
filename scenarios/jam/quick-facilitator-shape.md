---
name: quick-facilitator-shape
title: jam:quick dispatches quick-facilitator and produces correct synthesis shape
description: Verify jam:quick dispatches the lightweight quick-facilitator (not brainstorm-facilitator) and emits the canonical 3-section synthesis shape (Key Insights / Action Items / Open Questions) shared with brainstorm-facilitator.
type: workflow
difficulty: basic
estimated_minutes: 3
tags: [jam, quick, synthesis-shape, context-budget]
complexity: 2
---

# Scenario: jam:quick Facilitator Shape

Verify that `jam:quick` dispatches `wicked-garden:jam:quick-facilitator` (not `brainstorm-facilitator`)
and that the output synthesis block has the required fields at lower token cost.

## Setup

No special setup required. This scenario runs against the live plugin.

## Steps

### Step 1 — Dispatch jam:quick

Run:
```
/wicked-garden:jam:quick "Should we use SQLite or a flat JSON file for local plugin state?"
```

### Step 2 — Assert: correct agent dispatched

The Task tool call must use `subagent_type="wicked-garden:jam:quick-facilitator"`.

**FAIL** if `brainstorm-facilitator` appears in the dispatch.

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

The synthesis block must include the same three section headings that
`brainstorm-facilitator` produces — the heading vocabulary is the contract:

| Field | quick-facilitator | brainstorm-facilitator |
|-------|-------------------|------------------------|
| Key Insights | required | required |
| Action Items | required | required |
| Open Questions | required | required |

Heading parity (#669 fix): callers consuming either agent read the same field
names without branching. **FAIL** if any section heading is absent or renamed.

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

Record start time before dispatch. Synthesis must arrive within 60 seconds —
the documented "60-second flow" budget for `jam:quick` (#669 fix; the prior
30-second threshold was a self-inflicted false-FAIL risk because real-world
single-pass model latency can spike past 30s without indicating a regression).

**WARN** if between 30-60s. **FAIL** if > 60s.

### Step 9 — Token cost comparison (rough check)

Run the same topic through `brainstorm-facilitator` with 1 forced round as a baseline.
Compare total output character count (proxy for token cost):

- quick-facilitator output chars: `N_quick`
- brainstorm-facilitator output chars: `N_full`

**PASS** if `N_quick < N_full * 0.5` (quick costs less than 50% of brainstorm).
**WARN** if between 50-70%.
**FAIL** if quick output is larger than brainstorm output.

## Expected Outcome

```
PASS: correct agent dispatched
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
| Wrong agent dispatched | commands/jam/quick.md still references brainstorm-facilitator |
| Missing synthesis heading | quick-facilitator output format diverged from spec |
| Round 2 present | Agent ignored the single-round constraint |
| Storage calls present | Agent carried over brainstorm-facilitator behavior |
| Token cost > 50% | Agent loaded too much context or added rounds |
