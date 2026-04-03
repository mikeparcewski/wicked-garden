---
description: Quick exploration with fewer personas and one round
argument-hint: "<idea or question>"
---

# /wicked-garden:jam:quick

Quick 60-second exploration with 4 personas and 1 round. Still gathers available evidence and stores a lightweight decision record after synthesis.

This command uses forced fast convergence: exactly 1 round, then immediately synthesize. Do NOT run additional rounds regardless of topic complexity. The point is speed to outcome.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam:facilitator",
     prompt="Run a quick jam session on: {topic}. Use 4 personas, EXACTLY 1 round, then synthesize IMMEDIATELY. Do not run a second round under any circumstances — this is fast convergence mode. Brief synthesis with 2-3 insights max. Still gather evidence if available (but keep it fast — 2 sources max). Store a lightweight decision record after synthesis.

Kanban tracking (skip silently if kanban unavailable):
1. Session start: /wicked-garden:kanban:new-task 'Jam: {topic}' --metadata '{\"type\":\"jam-session\",\"status\":\"brainstorming\"}'
2. After synthesis: /wicked-garden:kanban:comment {task_id} 'Synthesis: {summary}'
3. On decision: /wicked-garden:kanban:comment {task_id} 'Decision: {decision_record}'

kanban = process, wicked-mem = outcome.")
```
