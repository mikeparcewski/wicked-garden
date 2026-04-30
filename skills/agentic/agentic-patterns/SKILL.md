---
name: agentic-patterns
description: |
  Use when designing or analyzing multi-agent architectures — covers core patterns (sequential, hierarchical,
  parallel, event-driven), anti-patterns, and the five-layer model (Cognition → Context → Interaction →
  Runtime → Governance) for separating concerns in production-grade agentic systems.
  NOT for reviewing existing agentic code (use review-methodology) or framework selection (use the frameworks skill).
portability: portable
---

# Agentic Patterns

Reference guide for proven agentic architecture patterns and common anti-patterns to avoid.

## Core Patterns

| Pattern | Use when | Example | Tradeoffs |
|---------|----------|---------|-----------|
| **Sequential** | Linear workflow, clear dependencies, predictable stages | Research → Analyze → Draft → Review | Simple coordination; bottlenecks if any agent is slow |
| **Hierarchical** | Complex task decomposable into subtasks; central coordination | PM agent delegates to designer / dev / QA | Clear accountability, scales; single point of failure at parent |
| **Collaborative** | Diverse perspectives matter; no clear lead | Multiple reviewers collaborating on code review | Rich outputs; needs conflict resolution + consensus |
| **Autonomous** | Tasks are fully independent; parallel execution | Multiple monitoring agents checking different services | Max parallelism; no shared learning or coordination |
| **Human-in-the-Loop** | High-stakes decisions, regulatory gates, human feedback | Agent drafts report; human approves before sending | Adds latency; ensures safety and quality |
| **ReAct** | Dynamic environments; need adaptive behavior on feedback | Debug agent: try fix → observe tests → adapt | Flexible; high token/latency cost for reasoning |
| **Plan-Execute** | Predictable environment; planning overhead justified | Multi-step pipeline with known transformations | Efficient; brittle if environment changes |
| **Reflection** | Quality > speed; self-improvement valuable | Writer drafts → critiques → refines | Higher quality; more tokens and latency |

See `refs/pattern-catalog.md` for full descriptions and implementation notes per pattern.

## Anti-Patterns Quick Reference

1. **God Agent:** Single agent doing everything. Split responsibilities.
2. **Tight Coupling:** Agents depend on internal implementation details. Use interfaces.
3. **Missing Guardrails:** No constraints on agent actions. Add validation and limits.
4. **Deep Nesting:** Agents calling agents calling agents. Flatten hierarchy.
5. **No Observability:** Can't see what agents are doing. Add logging and tracing.
6. **Sequential Bottleneck:** Everything waits for slowest agent. Add parallelism.
7. **Context Bloat:** Passing entire history to every agent. Compress and filter.
8. **Redundant Agents:** Multiple agents doing same thing. Consolidate.
9. **Hardcoded Prompts:** Prompts baked into code. Externalize and version.
10. **Missing Timeouts:** Agents can run forever. Add time and resource limits.

## Pattern Selection Decision Tree

```
Is task decomposable into subtasks?
├─ YES: Is there a clear lead/coordinator role?
│   ├─ YES: Use Hierarchical
│   └─ NO: Use Collaborative
└─ NO: Does task require adaptation based on results?
    ├─ YES: Can you plan all steps upfront?
    │   ├─ YES: Use Plan-Execute
    │   └─ NO: Use ReAct
    └─ NO: Do you have multiple independent tasks?
        ├─ YES: Use Autonomous
        └─ NO: Use Sequential
```

Add Human-in-the-Loop gates for any high-stakes decisions.
Add Reflection layer when quality is critical.

## Combining Patterns

Patterns are composable:
- **Hierarchical + ReAct:** Parent plans, children adapt execution
- **Sequential + Reflection:** Each stage includes self-review
- **Collaborative + Human-in-Loop:** Peer review with human arbitration
- **Autonomous + Hierarchical:** Independent teams with team leads

## Pattern Anti-Affinities

Avoid these combinations:
- **Plan-Execute + ReAct:** Contradictory - either plan upfront or adapt dynamically
- **Autonomous + Tight Coordination:** Defeats the purpose of autonomy
- **Deep Hierarchies + Reflection:** Exponential token cost

## Quick Start

1. Identify if task is decomposable (subtasks?) or atomic
2. Identify if execution is predictable (plan?) or dynamic (adapt?)
3. Identify if agents should coordinate (hierarchy/collaboration) or work independently
4. Check anti-patterns list against current design
5. See refs/pattern-catalog.md for detailed examples

## References

- `refs/pattern-catalog.md` - Detailed pattern descriptions with implementation examples
- `refs/anti-patterns-design.md` - Design anti-patterns (God Agent, Tight Coupling, Missing Guardrails, Deep Nesting, No Observability)
- `refs/anti-patterns-operational.md` - Operational anti-patterns (Sequential Bottleneck, Context Bloat, Redundant Agents, Hardcoded Prompts, Missing Timeouts)
