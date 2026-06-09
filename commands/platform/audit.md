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

Collect audit evidence, verify controls, and generate compliance artifacts for SOC2/HIPAA/GDPR/PCI.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: `<framework> [control_id]` (framework = `soc2|hipaa|gdpr|pci`; control_id or `all`).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/audit/refs/audit.md")` — full collection rubric,
   control-testing checklist, SOC2/HIPAA control matrix, gap analysis, bus emit, and output format.
3. For framework-specific checklists: `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/audit/refs/checklists-soc2-hipaa.md")`
   or `refs/checklists-gdpr-pci-evidence.md`. For evidence scripts and organization: `refs/checklists-evidence-operations.md`.
4. Apply the rubric directly: collect evidence via code search, verify each control, document
   Pass/Partial/Fail with file:line refs, then emit the bus event and produce the audit report.
