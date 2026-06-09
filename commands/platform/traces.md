---
description: Distributed tracing analysis for latency and dependencies
argument-hint: "[service name, trace ID, or 'slow' for latency investigation]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:traces

Analyze distributed traces for latency investigation, service dependencies, and bottleneck detection.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: service name, trace ID, or `slow` for p99 latency investigation.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/traces/refs/traces.md")` — tracing source discovery,
   investigation checklist, fallback code-pattern analysis, common patterns (N+1, sequential fan-out,
   cold-start), and output format.
3. Apply the rubric directly: discover tracing sources via `ListMcpResourcesTool`, query the target,
   and produce the trace analysis with latency breakdown, service dependencies, bottlenecks, and
   optimization recommendations with expected impact.
