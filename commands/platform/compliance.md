---
description: Regulatory compliance check (SOC2, HIPAA, GDPR, PCI)
argument-hint: "<framework: soc2|hipaa|gdpr|pci> [path]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:compliance

Check code and architecture against regulatory compliance frameworks.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: `<framework> [path]` (framework = `soc2|hipaa|gdpr|pci`).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/compliance/refs/compliance.md")` — data-classification
   scan commands, per-framework control matrix (SOC2/HIPAA/GDPR/PCI), gap checklist, bus emit, output format.
3. For detailed per-framework checklists: `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/compliance/refs/checklists.md")`.
   For framework-specific patterns: `refs/frameworks.md`.
4. Apply the rubric directly: scan for sensitive data, verify each control, classify gaps P0/P1/P2,
   emit the bus event, and produce the compliance assessment report.
