---
description: Quick exploration with fewer personas and one round
argument-hint: "<idea or question>"
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:quick

Quick 60-second exploration with 4 personas and 1 round.

> **Progression**: `quick` (60s gut-check, ephemeral) → `brainstorm` (full session with evidence + decision storage) → `council` (structured verdict with external LLMs).
> See also: `/wicked-garden:jam:brainstorm`, `/wicked-garden:jam:council`

This command uses forced fast convergence: exactly 1 round, then immediately synthesize. Do NOT run additional rounds regardless of topic complexity. The point is speed to outcome.

Delegate to the quick facilitator agent:

```
Task(subagent_type="wicked-garden:jam:quick-facilitator",
     prompt="Run a quick jam session on: {topic}")
```
