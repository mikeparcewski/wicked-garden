---
description: Start a new brainstorm session with dynamic focus groups
argument-hint: "<topic> [--personas list] [--rounds n] [--converge fast]"
---

# /wicked-garden:jam:brainstorm

Start a full brainstorm with evidence-backed perspectives. The facilitator gathers evidence from the ecosystem (past decisions, code context, brainstorm outcomes) before assembling personas, so they argue from data — not just opinions. After synthesis, a structured decision record is automatically stored in wicked-garden:mem for organizational memory.

## Convergence Modes

- **normal** (default): Run all requested rounds (2-3), then synthesize.
- **fast** (`--converge fast`): After each round, assess whether there is enough signal to synthesize. If personas are converging on a clear direction with at least 2 actionable insights and no major unresolved tensions, skip remaining rounds and synthesize immediately. Maximum: 1 round before early synthesis is allowed.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam:facilitator",
     prompt="Run a full brainstorm session on: {topic}. Options: {personas}, {rounds}, convergence_mode={converge|'normal'}.

Convergence mode instructions:
- If convergence_mode is 'fast': After EACH round, perform a convergence check before proceeding. Ask: (1) Are there at least 2 clear, actionable insights? (2) Is there broad directional agreement among personas? (3) Are remaining tensions minor or well-characterized? If all three are YES, skip remaining rounds and proceed directly to synthesis. This is the EXPECTED path in fast mode — do not run extra rounds just because they were planned.
- If convergence_mode is 'normal': Run all planned rounds, but still note in synthesis if convergence happened early.

Follow the full session structure including evidence gathering, persona assembly, discussion rounds, multi-AI perspective (if available), synthesis, and decision record storage.

Native-task tracking (fail open on any tool errors):
1. Session start: TaskCreate(subject='Jam: {topic}', metadata={'event_type':'task','chain_id':'jam-{topic-slug}.root','source_agent':'jam-facilitator','initiative':'{topic-slug}'})
2. After each persona contributes, after synthesis, and on decision: TaskUpdate(taskId, description='append: {persona_name}: {key_insight}' / 'Synthesis: {summary}' / 'Decision: {decision_record}')

Continue storing outcomes in wicked-garden:mem as before (native task = process, mem = outcome).")
```
