---
name: wicked-garden-ground
context: fork
description: |
  Grounding / assumption-check: pull deeper context from the knowledge layer
  (wicked-estate memory + knowledge) and the bus when uncertain, before acting.
  Use when: getting mixed signals from the codebase, about to commit to a
  non-obvious decision, prior decisions might exist for this exact problem, or you want to
  verify an assumption before action ("am I sure about this?", "have we decided this
  before?"). Returns relevant memories, knowledge chunks, recent bus events, and linked
  priors ranked by relevance — not a wall of text. Aliases: grounding, sanity-check,
  verify-assumption.

  NOT for: routine "what does this code do" questions (use Read or Grep), broad
  codebase exploration (use Agent(Explore)), or fetching specific symbols (use
  the wicked-estate MCP SearchEntity tool directly).
portability: portable
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden:ground — Steer Yourself

You are uncertain. Pull what's known into focus.

## When to use

- Getting mixed signals from the codebase — two things contradict each other
- About to commit to a non-obvious decision — want to know if it's been tried before
- Prior decisions might exist for this exact problem — avoid re-deriving what was deliberated
- Want to verify an assumption before taking action — gut feel needs grounding
- Picking back up on a topic after context has shifted — "let me get my bearings"
- Asking "wait, did we already decide this?" — stored memory is the answer

## When NOT to use

- Routine "what does this code do" questions — use Read or Grep, they're faster
- Broad codebase exploration without a specific question — use Agent(Explore)
- Fetching a specific symbol you already know exists — use the estate MCP
  `SearchEntity` tool directly
- During flow when you already have enough context — don't interrupt to re-ground

## Mechanism

1. Take the `question` argument (free text from the user / Claude's internal state)
2. **Parallel query** — run both simultaneously:
   - `wicked-garden-mem` recall — memories + knowledge (decisions, patterns,
     gotchas; estate fuses both stores, results carry source attribution)
   - `wicked-bus:query` — recent bus events matching the question (last 50, filter by
     relevance to question terms)
3. **Synthesize** — rank by relevance, dedupe overlap, cap at top 5–10 signals total.
   Priority order: memories > knowledge chunks > bus events.
4. **Output** — dense, structured. For each hit:
   - Source type: `memory`, `knowledge`, or `bus/event`
   - One-line relevance statement (why this signal matters to the question)
   - Source attribution / scope / event-id for follow-up
   - Suggested follow-up (e.g., Read the cited source file)
5. **Closing pointer**: "If you need more depth, open `{most relevant cited
   source}` with Read, or run `wicked-garden-mem` answer for a cited synthesis."
6. **DO NOT** dump full file content — this is a focusing tool, not a firehose.
   The output should be skimmable in under 30 seconds.

## Implementation

When invoked with a `question`:

**Step 1 — Decompose the question into 3–5 search terms.** Extract noun phrases,
named entities, and technical terms. Example: "v8 daemon projection model" →
`["daemon", "projection", "v8 architecture", "state machine"]`.

**Step 2 — Parallel execution.** Invoke in a single parallel batch:

```bash
# Knowledge-layer recall (repeat per term if ≥2 terms)
Skill(skill="wicked-garden-mem", args="recall \"{term1}\"")
Skill(skill="wicked-garden-mem", args="recall \"{term2}\"")

# Bus recent events
Skill(wicked-bus:query, query="{question}", limit=50)
```

**Step 3 — Rank and dedupe.** Collect all results. Score by:
- Source priority (memory > knowledge chunk > bus event)
- Recency for bus events (newer = higher)
- Overlap with question terms (more term matches = higher)

Keep the top 5–10 unique signals. Drop results where two sources say the same
thing — keep the higher-priority source.

**Step 4 — Format output.** Use this shape:

```
## Grounding: {question}

### What the record knows

1. [memory] {one-line relevance} — scope `{scope}`
2. [knowledge] {one-line relevance} — `{source attribution}`
3. [knowledge] {one-line relevance} — `{source attribution}`

### Recent bus activity

4. [bus/event] {event_type} @ {timestamp} — {one-line relevance}
5. [bus/event] {event_type} @ {timestamp} — {one-line relevance}

### If you need more depth
Read `{most relevant cited source}`, or `wicked-garden-mem` answer "{question}"
```

**Step 5 — If zero results from both the knowledge layer and bus**, say so explicitly:
"No prior decisions or recent events found for this question. Proceeding without
grounding — consider storing the decision you reach with `wicked-garden-mem` (store action)."

## Graceful degradation

- Knowledge layer unavailable → skip recall steps, surface bus events only, note degradation
- Bus unavailable → skip bus step, surface knowledge-layer results only, note degradation
- Both unavailable → emit: "Ground returned no context (knowledge layer and bus both
  unreachable). Proceeding on codebase signals only."

Never block progress. Ground is a focusing tool — absence of prior context is
itself a useful signal.

## After grounding

If you reach a decision that others should know about:
- Store it: `wicked-garden-mem` (store action)
- Emit it: `wicked-bus:emit` with the relevant event type

The value of grounding compounds when decisions are written back.
