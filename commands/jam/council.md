---
description: Structured multi-model evaluation using external LLM CLIs for independent perspectives
argument-hint: "<topic>" --options "A, B, C" [--criteria "perf, cost, risk"]
---

# /wicked-garden:jam:council

Structured evaluation tool that uses real external LLM CLIs (Codex, Gemini, OpenCode, Pi) to get genuinely independent model perspectives. Unlike brainstorm (free-form creative exploration), council is a **rigid evaluation tool** for when you have defined options and need a verdict.

**Key distinction**: brainstorm = generation (explore), jam = quick gut-check, council = evaluation (decide).

Natural workflow: `brainstorm → identify candidates → council → decide`

Delegate to the council agent:

```
Task(subagent_type="wicked-garden:jam/council",
     prompt="Run a council evaluation on: {topic}. Options: {options}. Criteria: {criteria}.")
```
