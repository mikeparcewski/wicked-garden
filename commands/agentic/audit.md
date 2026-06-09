---
description: Deep trust and safety audit for agentic systems with risk classification and compliance validation
argument-hint: "[path] [--output FILE] [--standard GDPR|HIPAA|SOC2|NIST] [--scenarios]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:audit

Deep trust+safety audit: classifies tool risks, verifies HITL gates, checks PII
handling, optionally emits compliance evidence + wicked-scenarios.

Use `agentic:review` for the broader architecture+perf+safety sweep.

## Run it inline (no dispatch)

1. Parse `[path]`, `--standard`, `--output`, `--scenarios`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/agentic/refs/audit.md")` — the 8-layer rubric,
   checklist, compliance extensions, and output format.
3. Apply the rubric directly to the target path. For each layer, assess findings,
   classify severity, and build the risk matrix.
4. If `--standard` is given, append the matching compliance checklist from the ref.
5. If `--scenarios`, emit a `wicked-scenarios` block per CRITICAL/HIGH finding.
6. Write to `--output` file when set; otherwise return inline.
