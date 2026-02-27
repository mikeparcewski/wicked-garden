---
description: Quick exploration with fewer personas and one round
argument-hint: <idea or question>
---

# /wicked-garden:jam:quick

Quick 60-second exploration with 4 personas and 1 round. Still gathers available evidence and stores a lightweight decision record after synthesis.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam/facilitator",
     prompt="Run a quick jam session on: {topic}. Use 4 personas, 1 round, brief synthesis. Still gather evidence if available (but keep it fast — 2 sources max). Store a lightweight decision record after synthesis.")
```
