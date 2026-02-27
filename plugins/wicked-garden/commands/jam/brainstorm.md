---
description: Start a new brainstorm session with dynamic focus groups
argument-hint: <topic> [--personas list] [--rounds n]
---

# /wicked-garden:jam-brainstorm

Start a full brainstorm with evidence-backed perspectives. The facilitator gathers evidence from the ecosystem (past decisions, code context, brainstorm outcomes) before assembling personas, so they argue from data — not just opinions. After synthesis, a structured decision record is automatically stored in wicked-mem for organizational memory.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam/facilitator",
     prompt="Run a full brainstorm session on: {topic}. Options: {personas}, {rounds}. Follow the full session structure including evidence gathering, persona assembly, discussion rounds, multi-AI perspective (if available), synthesis, and decision record storage.")
```
