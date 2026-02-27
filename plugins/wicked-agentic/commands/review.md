---
description: Full agentic codebase review with framework detection, agent topology analysis, and remediation roadmap
argument-hint: "[path] [--quick] [--framework NAME] [--output FILE]"
---

# /wicked-agentic:review

Comprehensive agentic architecture review that identifies frameworks, analyzes agent interactions, scores patterns, and produces actionable recommendations.

## Instructions

### 1. Parse Arguments

Extract parameters:
- `path`: Target directory (default: current directory)
- `--quick`: Skip deep analysis, structural review only
- `--framework NAME`: Override auto-detection (langchain, crewai, autogen, etc.)
- `--output FILE`: Write report to file instead of stdout

### 2. Detect Framework

Run framework detection:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_framework.py" --path "$TARGET_PATH"
```

Expected output:
```json
{
  "primary_framework": "langchain",
  "confidence": 0.95,
  "evidence": ["langchain imports", "LCEL chains"],
  "all_frameworks": [
    {"name": "langchain", "confidence": 0.95},
    {"name": "openai", "confidence": 0.30}
  ],
  "stats": {
    "total_files": 45,
    "agent_files": 12
  }
}
```

If `--framework` specified, skip detection and use provided value.

### 3. Analyze Agent Topology

Map agent interactions and dependencies:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/analyze_agents.py" --path "$TARGET_PATH" \
  --framework "$DETECTED_FRAMEWORK"
```

Expected output:
```json
{
  "agents": [
    {
      "name": "research_agent",
      "file": "src/agents/research.py",
      "type": "tool_calling",
      "tools": ["search", "scrape"],
      "dependencies": []
    }
  ],
  "agent_count": 5,
  "communication": {
    "pattern": "hierarchical",
    "edges": [
      {"from": "orchestrator", "to": "research_agent", "type": "delegates"}
    ]
  },
  "shared_tools": ["search"],
  "role_distribution": {
    "orchestrator": 1,
    "worker": 4
  },
  "stats": {
    "max_depth": 3,
    "avg_tools_per_agent": 2.4
  }
}
```

### 4. Architecture Assessment

Spawn architect agent for design review:

```
Task(
  subagent_type="wicked-agentic:architect",
  prompt="Mode: architecture_review\n\nContext:\n- Framework: {detected_framework}\n- Agent topology: {topology_summary}\n- Entry points: {entry_agents}\n\nInstructions:\nLoad skill wicked-agentic:five-layer-architecture\n\nAnalyze architecture:\n1. Layer separation (Cognition, Context, Interaction, Runtime, Governance)\n2. Control flow clarity\n3. State management approach\n4. Error propagation\n5. Testing strategy\n\nOutput assessment with:\n- Architecture diagram (mermaid)\n- Pattern alignment score\n- Structural issues\n- Refactoring opportunities"
)
```

### 5. Safety Audit

Spawn safety reviewer for security analysis:

```
Task(
  subagent_type="wicked-agentic:safety-reviewer",
  prompt="Mode: safety_audit\n\nContext:\n- Framework: {detected_framework}\n- Tools used: {tool_list}\n- Agent interactions: {topology}\n\nInstructions:\nLoad skill wicked-agentic:trust-and-safety\n\nReview safety posture:\n1. Tool risk classification\n2. Human-in-the-loop gates\n3. PII handling\n4. Prompt injection vulnerabilities\n5. Rate limiting and quotas\n6. Fallback mechanisms\n\nOutput safety report with:\n- Risk matrix\n- Critical vulnerabilities\n- Required mitigations\n- Compliance gaps"
)
```

### 6. Performance Analysis

Spawn performance analyst for optimization review:

```
Task(
  subagent_type="wicked-agentic:performance-analyst",
  prompt="Mode: performance_review\n\nContext:\n- Framework: {detected_framework}\n- Agent count: {agent_count}\n- Topology pattern: {pattern}\n\nInstructions:\nLoad skill wicked-agentic:agentic-patterns\n\nAnalyze performance:\n1. Latency bottlenecks\n2. Token usage efficiency\n3. Parallelization opportunities\n4. Caching strategy\n5. Context window management\n6. Cost optimization\n\nOutput performance report with:\n- Bottleneck analysis\n- Cost estimation\n- Optimization recommendations\n- Benchmarking suggestions"
)
```

### 7. Pattern Scoring

Run pattern analysis on agent topology:
```bash
# Save agents JSON to temp file first
AGENTS_FILE=$(mktemp)
echo "$AGENTS_JSON" > "$AGENTS_FILE"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pattern_scorer.py" \
  --agents "$AGENTS_FILE" \
  --framework "$DETECTED_FRAMEWORK"
```

Expected output:
```json
{
  "findings": [
    {
      "pattern": "hierarchical_orchestration",
      "severity": "info",
      "description": "Agents organized in clear hierarchy",
      "recommendation": "Consider adding error recovery at orchestrator level"
    },
    {
      "pattern": "circular_dependencies",
      "severity": "high",
      "description": "Agent A and Agent B call each other",
      "recommendation": "Refactor to unidirectional flow"
    }
  ],
  "summary": {
    "total_patterns": 5,
    "anti_patterns": 2,
    "critical_issues": 0,
    "warnings": 3
  }
}
```

### 8. Issue Taxonomy

Generate final structured report:
```bash
# Save findings JSON to temp file
FINDINGS_FILE=$(mktemp)
echo "$FINDINGS_JSON" > "$FINDINGS_FILE"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/issue_taxonomy.py" \
  --findings "$FINDINGS_FILE" \
  --agents "$AGENTS_FILE" \
  --framework "$DETECTED_FRAMEWORK" \
  --format markdown
```

Creates taxonomy in markdown format:
```markdown
# Issue Taxonomy

## Critical

(none)

## High

### SAFE-001: Missing input validation on web_search tool
**Category**: safety
**Impact**: Potential SSRF vulnerability
**Remediation**: Add URL validation and allowlist
**Location**: src/tools/search.py:45

## Medium

(issues...)

## Low

(issues...)
```

### 9. Present Unified Report

Combine all analyses into markdown report:

```markdown
# Agentic Architecture Review

**Project**: {project_name}
**Framework**: {detected_framework} v{version}
**Reviewed**: {timestamp}
**Overall Score**: {score}/10

## Executive Summary

{1-2 paragraph overview of findings}

Key metrics:
- Agent count: {count}
- Architecture pattern: {pattern}
- Critical issues: {critical_count}
- Estimated monthly cost: {cost_estimate}

## Framework Detection

**Primary**: {framework} (confidence: {confidence}%)
**Secondary**: {secondary_frameworks}

## Agent Topology

{mermaid diagram}

Pattern: {topology_pattern}
Depth: {max_depth}
Total agents: {agent_count}

## Architecture Assessment

Score: {arch_score}/10

### Layer Separation
{findings}

### Control Flow
{findings}

### State Management
{findings}

### Issues
| Severity | Issue | Location | Remediation |
|----------|-------|----------|-------------|
| {severity} | {issue} | {file:line} | {fix} |

## Safety Audit

Score: {safety_score}/10

### Risk Matrix
| Tool | Risk Level | Mitigations | Status |
|------|------------|-------------|--------|
| {tool} | {level} | {mitigations} | {status} |

### Critical Vulnerabilities
1. {vulnerability with remediation}

### Compliance
- [ ] Human-in-the-loop for high-risk actions
- [ ] PII handling compliant
- [ ] Rate limiting implemented

## Performance Analysis

Score: {perf_score}/10

### Bottlenecks
1. {bottleneck with impact and fix}

### Cost Optimization
- Current estimated cost: {current}
- Optimized cost: {optimized}
- Savings: {savings} ({percentage}%)

### Recommendations
1. {optimization with expected impact}

## Pattern Analysis

**Detected Patterns**:
- {pattern}: {description}

**Anti-Patterns**:
- {anti_pattern}: {description and fix}

## Issue Inventory

### Critical ({count})
{issues}

### High ({count})
{issues}

### Medium ({count})
{issues}

### Low ({count})
{issues}

## Remediation Roadmap

**Phase 1: Critical Fixes** (1-2 days)
1. {issue and fix}

**Phase 2: Safety Hardening** (3-5 days)
1. {issue and fix}

**Phase 3: Performance Optimization** (1 week)
1. {issue and fix}

**Phase 4: Architecture Improvements** (2-3 weeks)
1. {issue and fix}

## Next Steps

1. {immediate action}
2. {short-term improvement}
3. {long-term enhancement}
```

If `--output` specified, write to file:
```bash
echo "$REPORT" > "$OUTPUT_FILE"
echo "Report written to $OUTPUT_FILE"
```

## Examples

### Basic Review
```
User: /wicked-agentic:review ./src

Claude: I'll perform a comprehensive agentic architecture review.

[Runs detection scripts]
[Spawns architect, safety-reviewer, performance-analyst agents]
[Generates pattern scores and issue taxonomy]

# Agentic Architecture Review

**Project**: customer-support-bot
**Framework**: LangGraph v0.0.40
**Reviewed**: 2026-02-05 14:30:00 UTC
**Overall Score**: 7.2/10

## Executive Summary

Your customer support agent system follows a hierarchical orchestration pattern with 5 specialized agents. Architecture is well-layered but has safety gaps around PII handling and missing rate limits on external API calls.

Key metrics:
- Agent count: 5
- Architecture pattern: Hierarchical orchestration
- Critical issues: 0
- High severity issues: 3
- Estimated monthly cost: $245 (optimizable to $180)

[Full report follows...]
```

### Quick Review
```
User: /wicked-agentic:review . --quick

Claude: Running quick structural review (skipping deep analysis).

[Runs framework detection and topology analysis only]

# Quick Agentic Review

**Framework**: LangChain v0.1.0
**Agents**: 3
**Pattern**: Sequential chain

Structure looks reasonable. Run full review for detailed analysis.
```

### Save to File
```
User: /wicked-agentic:review . --output reports/agentic-review.md

Claude: [Performs full review]

Report written to reports/agentic-review.md

Summary:
- Overall score: 7.2/10
- 3 high-severity issues
- 8 optimization opportunities
- Estimated savings: $65/month
```
