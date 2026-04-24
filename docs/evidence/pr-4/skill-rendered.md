---
name: ground
description: |
  Pull deeper context from brain + bus when uncertain. Use when: getting mixed signals
  from the codebase, about to commit to a non-obvious decision, prior decisions might
  exist for this exact problem, or you want to verify an assumption before action.
  Returns relevant brain memories, recent bus events, and linked priors ranked by
  relevance — not a wall of text.

  NOT for: routine "what does this code do" questions (use Read or Grep), broad
  codebase exploration (use Agent(Explore)), or fetching specific symbols (use
  wicked-brain:search directly).
portability: portable
---

# wicked-garden:ground — Steer Yourself

You are uncertain. Pull what's known into focus.

## When to use

- Getting mixed signals from the codebase — two things contradict each other
- About to commit to a non-obvious decision — want to know if it's been tried before
- Prior decisions might exist for this exact problem — avoid re-deriving what was deliberated
- Want to verify an assumption before taking action — gut feel needs grounding
- Picking back up on a topic after context has shifted — "let me get my bearings"
- Asking "wait, did we already decide this?" — brain memory is the answer

## When NOT to use

- Routine "what does this code do" questions — use Read or Grep, they're faster
- Broad codebase exploration without a specific question — use Agent(Explore)
- Fetching a specific symbol you already know exists — use wicked-brain:search directly
- During flow when you already have enough context — don't interrupt to re-ground

## Mechanism

1. Take the `question` argument (free text from the user / Claude's internal state)
2. **Parallel query** — run all three simultaneously:
   - `wicked-brain:query` — conceptual grounding ("what do we know about X")
   - `wicked-brain:search` — specific decisions, patterns, gotchas (top 5 results)
   - `wicked-bus:query` — recent bus events matching the question (last 50, filter by
     relevance to question terms)
3. **Synthesize** — rank by relevance, dedupe overlap, cap at top 5–10 signals total.
   Priority order: brain memories > brain wiki > brain chunks > bus events.
4. **Output** — dense, structured. For each hit:
   - Source type: `brain/memory`, `brain/wiki`, `brain/chunk`, or `bus/event`
   - One-line relevance statement (why this signal matters to the question)
   - Path or event-id for follow-up
   - Suggested follow-up tool (e.g., `wicked-brain:read {path} depth=2`)
5. **Closing pointer**: "If you need more depth on `{most relevant path}`, use
   `wicked-brain:read {path} depth=2`"
6. **DO NOT** dump full file content — this is a focusing tool, not a firehose.
   The output should be skimmable in under 30 seconds.

## Implementation

When invoked with a `question`:

**Step 1 — Decompose the question into 3–5 search terms.** Extract noun phrases,
named entities, and technical terms. Example: "v8 daemon projection model" →
`["daemon", "projection", "v8 architecture", "state machine"]`.

**Step 2 — Parallel execution.** Invoke all three in a single parallel batch:

```bash
# Brain conceptual query
Skill(wicked-brain:query, question="{question}", session_id="{session}")

# Brain symbol/decision search (repeat per term if ≥2 terms)
Skill(wicked-brain:search, query="{term1}", limit=5, session_id="{session}")
Skill(wicked-brain:search, query="{term2}", limit=5, session_id="{session}")

# Bus recent events
Skill(wicked-bus:query, query="{question}", limit=50)
```

**Step 3 — Rank and dedupe.** Collect all results. Score by:
- Source priority (memory > wiki > chunk > bus event)
- Recency for bus events (newer = higher)
- Overlap with question terms (more term matches = higher)

Keep the top 5–10 unique signals. Drop results where two sources say the same
thing — keep the higher-priority source.

**Step 4 — Format output.** Use this shape:

```
## Grounding: {question}

### What the brain knows

1. [brain/memory] {one-line relevance} — `{path}` → suggest: wicked-brain:read {path}
2. [brain/wiki] {one-line relevance} — `{path}`
3. [brain/chunk] {one-line relevance} — `{path}`

### Recent bus activity

4. [bus/event] {event_type} @ {timestamp} — {one-line relevance}
5. [bus/event] {event_type} @ {timestamp} — {one-line relevance}

### If you need more depth
`wicked-brain:read {most relevant path} depth=2`
```

**Step 5 — If zero results from both brain and bus**, say so explicitly:
"No prior decisions or recent events found for this question. Proceeding without
grounding — consider storing the decision you reach with `wicked-brain:memory`."

## Graceful degradation

- Brain unavailable → skip brain steps, surface bus events only, note degradation
- Bus unavailable → skip bus step, surface brain results only, note degradation
- Both unavailable → emit: "Ground returned no context (brain and bus both unreachable).
  Proceeding on codebase signals only."

Never block progress. Ground is a focusing tool — absence of prior context is
itself a useful signal.

## After grounding

If you reach a decision that others should know about:
- Store it: `wicked-brain:memory` (store mode)
- Emit it: `wicked-bus:emit` with the relevant event type

The value of grounding compounds when decisions are written back.
