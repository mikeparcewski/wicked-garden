---
description: Quick exploration with fewer personas and one round
argument-hint: "<idea or question>"
---

# /wicked-garden:jam:quick

Quick 60-second exploration with 4 personas and 1 round.

> **Progression**: `quick` (60s gut-check) → `brainstorm` (full session with evidence) → `council` (structured verdict with external LLMs).
> See also: `/wicked-garden:jam:brainstorm`, `/wicked-garden:jam:council` Still gathers available evidence and stores a lightweight decision record after synthesis.

This command uses forced fast convergence: exactly 1 round, then immediately synthesize. Do NOT run additional rounds regardless of topic complexity. The point is speed to outcome.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam:brainstorm-facilitator",
     prompt="Run a quick jam session on: {topic}. Use 4 personas, EXACTLY 1 round, then synthesize IMMEDIATELY. Do not run a second round under any circumstances — this is fast convergence mode. Brief synthesis with 2-3 insights max. Still gather evidence if available (but keep it fast — 2 sources max). Store a lightweight decision record after synthesis.

Native-task tracking (fail open on any tool errors):
1. Session start: TaskCreate(subject='Jam: {topic}', metadata={'event_type':'task','chain_id':'jam-{topic-slug}.root','source_agent':'jam-facilitator','initiative':'{topic-slug}'})
2. After synthesis and on decision: TaskUpdate(taskId, description='append: Synthesis: {summary}' / 'Decision: {decision_record}')

native task = process, wicked-brain:memory = outcome.")
```
