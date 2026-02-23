# wicked-agentic

Architecture review built specifically for AI agent systems — auto-detects which of 14 frameworks your codebase uses, maps the agent topology, scores patterns against a five-layer maturity model, and produces a prioritized remediation roadmap that generic code review tools miss entirely.

## Quick Start

```bash
# Install
claude plugin install wicked-agentic@wicked-garden

# Review an existing agentic codebase
/wicked-agentic:review ./my-agent-project

# Compare frameworks before committing
/wicked-agentic:frameworks --compare langgraph,crewai,autogen
```

## Workflows

### Review an existing agentic codebase

Running `/wicked-agentic:review ./my-agent-project` begins with automatic framework detection:

```json
{
  "primary_framework": "langchain",
  "confidence": 0.95,
  "evidence": ["langchain imports", "LCEL chains", "ChatOpenAI usage"],
  "all_frameworks": [
    {"name": "langchain", "confidence": 0.95},
    {"name": "openai",    "confidence": 0.30}
  ],
  "stats": {
    "total_files": 45,
    "agent_files": 12
  }
}
```

Then five specialist agents analyze in parallel — architect, safety-reviewer, performance-analyst, framework-researcher, and pattern-advisor — producing a structured report:

```
AGENTIC ARCHITECTURE REVIEW
════════════════════════════

Executive Summary
  Risk Score:      HIGH (62/100)
  Maturity Level:  2 — Structured (target: 3 — Governed)
  Top Priority:    Missing human-in-the-loop gates on tool execution

Issue Inventory (12 findings)
  CRITICAL  No confirmation gate before database writes (3 agents affected)
  CRITICAL  Prompt injection risk: user input passed directly to tool args
  HIGH      No token budget enforcement — unbounded LLM calls possible
  HIGH      Agent retry logic can loop indefinitely on transient errors
  MEDIUM    PII in intermediate state not cleared between runs
  ...

Remediation Roadmap
  Week 1:  Add HITL gates to write-path tools (effort: M, impact: CRITICAL)
  Week 1:  Sanitize user input before tool arg interpolation (effort: S, impact: CRITICAL)
  Week 2:  Implement token budget per agent invocation (effort: M, impact: HIGH)
  ...

Maturity Assessment
  Current: Level 2 — agents coordinate but lack governance
  Next:    Level 3 — requires audit logging + HITL gates + cost controls
```

### Run a deep safety audit for production readiness

```bash
/wicked-agentic:audit ./my-agent-project --standard SOC2
```

The safety-reviewer agent audits tool risk classifications, validates human-in-the-loop placement, checks PII handling across agent state, and maps findings to compliance controls (GDPR, HIPAA, SOC2, NIST).

### Compare frameworks before choosing one

```bash
/wicked-agentic:frameworks --compare langgraph,crewai,autogen --use-case research-pipeline
```

The framework-researcher agent produces a side-by-side comparison on orchestration model, safety features, observability, Python vs TypeScript support, and ecosystem maturity — with a ranked recommendation for your specific use case.

### Design a new system interactively

```bash
/wicked-agentic:design "I need a pipeline that researches topics, synthesizes findings, and drafts reports"
```

The architect agent asks clarifying questions about success criteria, latency requirements, and human oversight needs, then recommends a topology (ReAct, Plan-Execute, or parallel specialist pattern) with safety validation built into the design.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-agentic:review` | Full architecture review: framework detection, topology analysis, issue inventory, maturity score, remediation roadmap | `/wicked-agentic:review ./my-agent --quick` |
| `/wicked-agentic:audit` | Deep trust and safety audit with compliance mapping | `/wicked-agentic:audit ./my-agent --standard HIPAA` |
| `/wicked-agentic:design` | Interactive design guidance for new systems with safety validation | `/wicked-agentic:design "research pipeline"` |
| `/wicked-agentic:frameworks` | Framework comparison and selection for your use case | `/wicked-agentic:frameworks --compare langgraph,crewai` |
| `/wicked-agentic:ask` | Q&A on agentic patterns, architectures, and trade-offs | `/wicked-agentic:ask "When to use ReAct vs Plan-Execute?"` |

## When to Use What

| Situation | Use |
|-----------|-----|
| Existing codebase, first look | `/wicked-agentic:review` |
| Pre-production hardening | `/wicked-agentic:audit` |
| Net-new system, blank page | `/wicked-agentic:design` |
| Evaluating frameworks | `/wicked-agentic:frameworks` |
| Specific pattern question | `/wicked-agentic:ask` |

## Supported Frameworks

Auto-detected with confidence scoring:

Anthropic ADK, Google ADK, LangGraph, LangChain, CrewAI, AutoGen, Semantic Kernel, DSPy, Pydantic AI, OpenAI Agents SDK, LlamaIndex, Haystack, Mastra, Vercel AI SDK

## Agents

| Agent | Focus |
|-------|-------|
| `architect` | System topology, orchestration patterns, dependency mapping, design recommendations |
| `safety-reviewer` | Guardrail placement, prompt injection vectors, PII handling, HITL gate validation |
| `performance-analyst` | Token budget enforcement, latency profiling, cost modeling, parallelization opportunities |
| `framework-researcher` | Framework comparison, migration planning, ecosystem health, version compatibility |
| `pattern-advisor` | Anti-pattern identification, refactoring guidance, code quality for agentic systems |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `agentic-patterns` | ReAct, Plan-Execute, Orchestrator-Subagent, Reflection, and when to use each |
| `five-layer-architecture` | Cognition, Context, Interaction, Runtime, and Governance layers with examples |
| `trust-and-safety` | Guardrail taxonomy, prompt injection defense, PII handling, HITL placement criteria |
| `context-engineering` | Token budget models, state compression, cost attribution, memory tiers |
| `maturity-model` | 5-level assessment rubric with concrete criteria and advancement checklist |
| `frameworks` | 12+ framework profiles with trade-off matrices and migration notes |
| `review-methodology` | 4-phase review process, issue taxonomy, severity classification, evidence standards |

## Configuration

Create `.wicked-agentic.yaml` in your project root to customize detection and reporting:

```yaml
detection:
  confidence_threshold: 0.6        # Minimum confidence for framework detection
  exclude_patterns:
    - "node_modules/**"
    - "venv/**"
reporting:
  min_severity: medium             # Filter output: critical | high | medium | low | info
```

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged during design, build, and review phases when agentic signals are detected | Use commands directly; no automatic engagement |
| wicked-engineering | Combined code architecture + agentic pattern review in one pass | Agentic-only perspective; no general code quality view |
| wicked-mem | Cross-session learning from past reviews — pattern findings and anti-patterns remembered | Session-only context; each review starts from scratch |

## License

MIT
