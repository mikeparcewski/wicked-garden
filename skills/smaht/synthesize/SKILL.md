---
name: smaht-synthesize
description: |
  Internal context synthesis engine. Triggered by UserPromptSubmit hook when complexity
  or risk is above threshold. Runs agentic exploration — facilitator + fan-out subagents —
  to produce a complete turn directive grounded in project knowledge.

  NOT user-invokeable. Called automatically by the hook via skill directive injection.
user-invocable: false
model: sonnet
allowed-tools: Bash, Read, Glob, Agent
---

# Context Synthesis

You received this skill because the hook determined this prompt needs deep context assembly.

## Arguments (from hook)

Parse from the `args` string:
- `prompt`: the user's original prompt
- `complexity`: float 0–1 (hook scoring)
- `risk`: bool — high-risk keywords detected
- `turns`: recent session turns summary (condensed)

## Budget (based on complexity + risk)

| complexity | risk | rounds | parallel agents |
|-----------|------|--------|----------------|
| < 0.5     | no   | 1      | 2              |
| 0.5–0.7   | no   | 1      | 3              |
| > 0.7     | any  | 2      | 4              |
| any       | yes  | 2      | 3              |

## Step 1: Facilitator — What do I need to know?

Read the user's prompt and recent turns. Identify 3–5 specific questions:
- What concept, file, or system is the user asking about?
- What past decisions are relevant?
- What recent changes (events) might affect the answer?
- What constraints apply?

Do NOT search yet. Just list the questions.

## Step 2: Fan-out — Parallel exploration

Spawn parallel Agent calls (one per search question). Each agent should:

**Brain wiki search** (synthesized knowledge — try this first):
```bash
find ~/.wicked-brain/wiki -name "*.md" 2>/dev/null | head -20
# Read any wiki article whose name matches the topic
```

**Brain FTS search** (raw chunks — for specifics):
```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"QUERY_TERMS","limit":5}}'
```

**Recent events** (what changed recently):
```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"QUERY_TERMS event created","limit":3}}'
```

Each agent returns: what it found (or "nothing relevant").

## Step 3: Facilitator — Is this sufficient?

Review all agent outputs. Ask:
- Do I have specific, factual answers to the user's questions?
- Is anything critical missing?

If missing AND rounds remaining: identify the gap, spawn 1–2 targeted follow-up agents.
If sufficient OR no rounds left: proceed to synthesis.

## Step 4: Synthesize — Complete turn directive

Output ONLY the following block (200–300 words). This replaces Claude's own context assembly.

```
CONTEXT BRIEFING [smaht-synthesized | complexity={X} | risk={Y}]

**The user is asking**: {one sentence — actual intent, not a restatement}

**What is true** (verified from project knowledge):
- {specific fact 1 with source reference}
- {specific fact 2 with source reference}
- {specific fact 3 with source reference}
[add up to 2 more only if directly relevant]

**Active constraints**: {from session turns — user-stated rules that apply}

**Recommended approach**: {1–2 sentences — what to do and how, based on what was found}

**What was NOT found**: {if any critical info was missing — be explicit}
```

After outputting the briefing, tell Claude: "Proceed with this context. Answer the original prompt: {prompt}"
