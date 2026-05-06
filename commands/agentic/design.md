---
description: Interactive agentic architecture design guidance with pattern recommendations and safety validation
argument-hint: "[problem description] [--output FILE]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:design

Interactive design session for a new agentic system: requirements → pattern + five-layer architecture → safety validation → design doc. Greenfield design; use `agentic:review` to assess existing code, `agentic:audit` for compliance evidence.

## 1. Dispatch architect (design mode)

```
Task(subagent_type="wicked-garden:agentic:architect",
     prompt="""Mode: design
Problem: {problem_statement or 'gather via 3-5 clarifying questions'}
Output: {output_file or 'inline'}
Load skill wicked-garden:agentic:agentic-patterns. Pick the agentic pattern, render
five-layer architecture (mermaid), agent breakdown, control flow, state mgmt, error
handling, and framework recommendation.""")
```

## 2. Dispatch safety reviewer (design validation)

```
Task(subagent_type="wicked-garden:agentic:safety-reviewer",
     prompt="""Mode: design_validation
Architecture: {architect_output}
Load skill wicked-garden:agentic:trust-and-safety. Add safety section: tool risk, HITL,
PII, input validation, rate limits, failure modes, compliance, testing recs. Merge into
the design doc. Write to {output_file} if set, else inline.""")
```
