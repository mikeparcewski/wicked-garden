# wicked-agentic

Architecture review built specifically for AI agent systems. Auto-detects 12 agentic frameworks -- LangChain, CrewAI, AutoGen, Semantic Kernel, DSPy, Pydantic AI, and more -- analyzes agent topologies, scores patterns against a five-layer maturity model, and generates trust and safety audit reports with prioritized remediation roadmaps. Whether you are designing a new multi-agent system or hardening an existing one for production, wicked-agentic gives you the specialized review that generic code tools miss.

## Quick Start

```bash
# Install
claude plugin install wicked-agentic@wicked-garden

# Review an agentic codebase
/wicked-agentic:review ./my-agent-project

# Design a new agentic system
/wicked-agentic:design

# Compare frameworks
/wicked-agentic:frameworks --compare langgraph,crewai,autogen

# Ask about patterns
/wicked-agentic:ask "Best orchestration pattern for a research pipeline?"

# Deep safety audit
/wicked-agentic:audit ./my-agent-project
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-agentic:review` | Full architecture review with safety + performance analysis | `/wicked-agentic:review ./my-agent --quick` |
| `/wicked-agentic:design` | Interactive design guidance for new systems | `/wicked-agentic:design` |
| `/wicked-agentic:frameworks` | Framework comparison and selection | `/wicked-agentic:frameworks --compare langgraph,crewai` |
| `/wicked-agentic:ask` | Q&A about agentic patterns and architectures | `/wicked-agentic:ask "When to use ReAct vs Plan-Execute?"` |
| `/wicked-agentic:audit` | Deep trust and safety audit for production | `/wicked-agentic:audit ./my-agent` |

## Supported Frameworks

Anthropic ADK (Google ADK), LangGraph, CrewAI, AutoGen, Semantic Kernel, DSPy, Pydantic AI, OpenAI Agents SDK, Llama Index, Haystack, Mastra, Vercel AI SDK

## Review Output

The `/review` command produces:
1. **Executive Summary** - Risk score, maturity level, top priorities
2. **Issue Inventory** - Categorized findings with severity and evidence
3. **Remediation Roadmap** - Prioritized action items with effort/impact
4. **Maturity Assessment** - Current level and steps to advance

## Agents

| Agent | Focus |
|-------|-------|
| `architect` | System design, topology, orchestration patterns |
| `safety-reviewer` | Guardrails, prompt injection, PII, human-in-the-loop |
| `performance-analyst` | Token optimization, latency, cost, parallelization |
| `framework-researcher` | Framework comparison, migration, ecosystem assessment |
| `pattern-advisor` | Anti-patterns, refactoring, code quality |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `agentic-patterns` | ReAct, Plan-Execute, and other core patterns |
| `five-layer-architecture` | Cognition, Context, Interaction, Runtime, Governance |
| `trust-and-safety` | Guardrails, prompt injection, PII defense |
| `context-engineering` | Token optimization, state management, cost models |
| `maturity-model` | 5-level assessment framework |
| `frameworks` | 12 framework profiles with comparison criteria |
| `review-methodology` | 4-phase review process with issue taxonomy |

## Configuration

Create `.wicked-agentic.yaml` in your project root:

```yaml
detection:
  confidence_threshold: 0.6
  exclude_patterns: ["node_modules/**", "venv/**"]
reporting:
  min_severity: medium  # critical, high, medium, low, info
```

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged in design/build/review for agentic codebases | Use commands directly |
| wicked-engineering | Combined code + architecture review | Agentic-only perspective |
| wicked-mem | Cross-session learning | Session-only context |

## License

MIT
