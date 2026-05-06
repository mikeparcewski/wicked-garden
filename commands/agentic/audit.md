---
description: Deep trust and safety audit for agentic systems with risk classification and compliance validation
argument-hint: "[path] [--output FILE] [--standard GDPR|HIPAA|SOC2|NIST] [--scenarios]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:audit

Deep trust+safety audit: classifies tool risks, verifies HITL gates, checks PII handling, optionally emits compliance evidence + wicked-scenarios. Use for compliance-grade evidence; use `agentic:review` for the broader architecture+perf+safety sweep.

## 1. Detect framework + topology

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/detect_framework.py --path "$TARGET_PATH"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/analyze_agents.py --path "$TARGET_PATH" --framework "$DETECTED_FRAMEWORK"
```

## 2. Dispatch safety reviewer (deep audit mode)

```
Task(subagent_type="wicked-garden:agentic:safety-reviewer",
     prompt="""Mode: deep_audit
Path: {path}  Framework: {fw}  Topology: {topology_json}
Standard: {standard or 'none'}  Output: {output_file or 'inline'}  Scenarios: {true/false}
Load skill wicked-garden:agentic:trust-and-safety. Run the 8-layer audit (tool risk, HITL,
PII, injection, authn/authz, rate limits, observability, failure modes). If --standard given,
add the matching compliance checklist. If --scenarios, emit a wicked-scenarios block per
CRITICAL/HIGH finding. Write to {output_file} when set, else return inline.""")
```
