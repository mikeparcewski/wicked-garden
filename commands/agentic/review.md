---
description: Full agentic codebase review with framework detection, agent topology analysis, and remediation roadmap
argument-hint: "[path] [--quick] [--framework NAME] [--output FILE]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:review

Full agentic-codebase review: framework detection → topology → architecture + safety + performance assessments → pattern scoring → unified remediation roadmap. Holistic sweep; use `agentic:audit` for compliance-grade safety evidence, `agentic:design` for greenfield design.

## 1. Detect framework + topology

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/detect_framework.py --path "$TARGET_PATH"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/analyze_agents.py --path "$TARGET_PATH" --framework "${FRAMEWORK_OVERRIDE:-$DETECTED_FRAMEWORK}"
```

`--quick` stops here and returns the structural summary. Otherwise dispatch the 3 reviewers in parallel.

## 2. Dispatch reviewers (parallel) + score patterns + emit taxonomy

```
Task(subagent_type="wicked-garden:agentic:architect",           prompt="Mode: architecture_review\nFramework: {fw}\nTopology: {topo}\nLoad skill wicked-garden:agentic:agentic-patterns. Score layers, control flow, state, error propagation, testability.")
Task(subagent_type="wicked-garden:agentic:safety-reviewer",     prompt="Mode: safety_audit\nFramework: {fw}\nTools: {tools}\nTopology: {topo}\nLoad skill wicked-garden:agentic:trust-and-safety. Risk matrix + HITL + PII + injection + rate limits + fallbacks.")
Task(subagent_type="wicked-garden:agentic:performance-analyst", prompt="Mode: performance_review\nFramework: {fw}\nAgent count: {n}\nPattern: {pattern}\nLoad skill wicked-garden:agentic:agentic-patterns. Latency, token efficiency, parallelism, caching, cost.")
```

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/pattern_scorer.py --agents "$AGENTS_FILE" --framework "$DETECTED_FRAMEWORK"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/agentic/issue_taxonomy.py --findings "$FINDINGS_FILE" --agents "$AGENTS_FILE" --framework "$FRAMEWORK_FILE" --format markdown
```

Merge into one report (executive summary, scores, issue inventory by severity, 4-phase remediation roadmap). Write to `$OUTPUT_FILE` if `--output` set; else inline.
