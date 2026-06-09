---
description: Incident response and triage
argument-hint: "<error message, alert, or symptom description>"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:incident

Rapid incident triage with root cause correlation, blast radius assessment, and remediation guidance.

> **Scope**: `platform:incident` is for **rapid active triage** — root cause, blast radius, remediation steps.
> To **log** an incident against a crew project with traceability, use `/wicked-garden:crew:incident` instead.

## Run it inline (no dispatch)

1. Collect incident context from `$ARGUMENTS`: error/alert description, start time if given, affected scope.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/incident/refs/incident.md")` — the 5-phase rubric
   (triage → stabilize → investigate → resolve → follow-up), severity classification, common patterns,
   output format, and communication templates.
3. Apply the rubric directly: discover observability sources via `ListMcpResourcesTool`, correlate with
   recent git changes, classify severity (SEV1–SEV4), and produce the incident report with blast radius,
   mitigation actions, and rollback decision.
