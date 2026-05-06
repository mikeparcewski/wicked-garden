---
description: |
  Use when gathering audit evidence for a compliance framework (SOC2, HIPAA, GDPR, PCI) — collects control
  artifacts, verifies state, and generates compliance reports. NOT for defining compliance policies
  (use platform:compliance) or ad hoc security checks (use platform:security).
argument-hint: "<framework: soc2|hipaa|gdpr|pci> [control ID]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:audit

Collect audit evidence, verify controls, and generate compliance artifacts for a target framework. Use for SOC2/HIPAA/GDPR/PCI evidence packages. NOT for policy definition (use platform:compliance) or vulnerability scans (use platform:security).

## 1. Dispatch

```
Task(subagent_type="wicked-garden:platform:auditor",
     prompt="""Collect audit evidence.

Args: $ARGUMENTS  (framework [control_id])
Framework: soc2 | hipaa | gdpr | pci
Control: specific control ID if given, else 'all' in framework.

Gather control implementation, configuration artifacts, access-control docs, log samples, policies.
Return per-control evidence with file:line refs, code/config snippets, verification checklist
(implemented/configured/enforced/documented), Pass/Partial/Fail status, gaps, auditor notes.""")
```
