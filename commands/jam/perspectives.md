---
description: Get multiple perspectives on a decision without synthesis
argument-hint: <decision or question>
---

# /wicked-garden:jam:perspectives

Get raw viewpoints from 4-6 personas on a decision or question — no synthesis, no recommendation. Each persona provides their position, key concern, and what would change their mind. Use this for self-directed thinking and discussion prep.

Delegate to the facilitator agent:

```
Task(subagent_type="wicked-garden:jam/facilitator",
     prompt="Run a perspectives-only session on: {topic}. Use 4-6 personas, 1 round only. Each persona must state: (1) their position, (2) their key concern, (3) what evidence would change their mind. Do NOT synthesize or recommend — just present raw perspectives. Do NOT store a decision record. Keep it fast (~60 seconds).")
```
