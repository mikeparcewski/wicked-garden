---
description: |
  Use when checking system health, aggregating error patterns, or diagnosing service reliability —
  covers health probes, error pattern detection, and multi-service observability in one command.
  NOT for plugin-level diagnostics (use platform:plugin-health) or distributed tracing (use platform:traces).
argument-hint: "[service name or 'all' for full assessment]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:health

Assess system health, aggregate observability data, and provide reliability recommendations.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: service name, or `all` for full assessment.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/health/refs/health.md")` — discovery checklist,
   per-source assessment steps, fallback code-analysis approach, common patterns, and output format.
3. Apply the rubric directly: discover observability sources via `ListMcpResourcesTool`, query each,
   correlate with recent deployments, and produce the health report with severity classification
   (HEALTHY / DEGRADED / CRITICAL) and prioritized recommendations.
