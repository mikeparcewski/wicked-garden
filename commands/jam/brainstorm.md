---
description: Start a new brainstorm session with dynamic focus groups
argument-hint: "<topic> [--personas list] [--rounds n]"
---

# /wicked-garden:jam:brainstorm

Start a full brainstorm with evidence-backed perspectives. The facilitator gathers evidence from the ecosystem (past decisions, code context, brainstorm outcomes) before assembling personas, so they argue from data — not just opinions. After synthesis, a structured decision record is automatically stored in wicked-mem for organizational memory.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam:facilitator",
     prompt="Run a full brainstorm session on: {topic}. Options: {personas}, {rounds}. Follow the full session structure including evidence gathering, persona assembly, discussion rounds, multi-AI perspective (if available), synthesis, and decision record storage.

Kanban tracking (skip silently if kanban unavailable):
1. Session start: /wicked-garden:kanban:new-task 'Jam: {topic}' --metadata '{\"type\":\"jam-session\",\"personas\":[...],\"status\":\"brainstorming\"}'
2. After each persona contributes: /wicked-garden:kanban:comment {task_id} '{persona_name}: {key_insight}'
3. After synthesis: /wicked-garden:kanban:comment {task_id} 'Synthesis: {summary}'
4. On decision: /wicked-garden:kanban:comment {task_id} 'Decision: {decision_record}'

Continue storing outcomes in wicked-mem as before (kanban = process, mem = outcome).")
```
