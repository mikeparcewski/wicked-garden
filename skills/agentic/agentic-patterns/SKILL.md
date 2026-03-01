---
name: agentic-patterns
description: |
  Core agentic architecture patterns and anti-patterns for building robust multi-agent systems.
  Use when: "agent pattern", "multi-agent design", "how should I structure agents", "agentic anti-pattern"
---

# Agentic Patterns

Reference guide for proven agentic architecture patterns and common anti-patterns to avoid.

## Core Patterns

### Sequential Pattern
Agents execute in fixed order. Each agent's output feeds the next.

**Use when:** Linear workflow, clear dependencies, predictable stages.

**Example:** Research → Analyze → Draft → Review

**Tradeoffs:** Simple coordination, but bottlenecks if any agent is slow.

### Hierarchical Pattern
Parent agent delegates to specialized child agents. Parent aggregates results.

**Use when:** Complex tasks decomposable into subtasks, need centralized coordination.

**Example:** Project manager agent delegates to designer, developer, QA agents.

**Tradeoffs:** Clear accountability, scales well, but single point of failure at parent.

### Collaborative Pattern
Peer agents work together on shared problem. No fixed hierarchy.

**Use when:** Problem benefits from diverse perspectives, no clear lead agent.

**Example:** Multiple specialized reviewers collaborating on code review.

**Tradeoffs:** Rich outputs, but requires conflict resolution and consensus mechanisms.

### Autonomous Pattern
Agents operate independently with minimal coordination.

**Use when:** Tasks are fully independent, parallel execution needed.

**Example:** Multiple monitoring agents checking different services.

**Tradeoffs:** Maximum parallelism, but no shared learning or coordination.

### Human-in-the-Loop Pattern
Human approval gates at critical decision points.

**Use when:** High-stakes decisions, regulatory requirements, learning from human feedback.

**Example:** Agent drafts report, human approves before sending.

**Tradeoffs:** Adds latency, but ensures safety and quality.

### ReAct Pattern
Reason → Act → Observe cycle. Agent reasons about next action, executes it, observes result, repeats.

**Use when:** Dynamic environments, need adaptive behavior based on feedback.

**Example:** Debugging agent tries fixes, observes test results, adapts approach.

**Tradeoffs:** Flexible and adaptive, but can be inefficient if reasoning is expensive.

### Plan-Execute Pattern
Agent creates full plan upfront, then executes all steps.

**Use when:** Environment is predictable, planning overhead is justified.

**Example:** Multi-step data pipeline with known transformations.

**Tradeoffs:** Efficient execution, but brittle if environment changes.

### Reflection Pattern
Agent reviews its own outputs and iteratively improves them.

**Use when:** Quality matters more than speed, self-improvement is valuable.

**Example:** Writer agent drafts, critiques, and refines output.

**Tradeoffs:** Higher quality outputs, but increased token usage and latency.

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

## When to Use

Trigger phrases indicating you need this skill:
- "How should I structure my multi-agent system?"
- "What architecture pattern fits my use case?"
- "Why is my agent system slow/buggy/expensive?"
- "Should agents work independently or together?"
- "How do I coordinate multiple agents?"

## Quick Start

1. Identify if task is decomposable (subtasks?) or atomic
2. Identify if execution is predictable (plan?) or dynamic (adapt?)
3. Identify if agents should coordinate (hierarchy/collaboration) or work independently
4. Check anti-patterns list against current design
5. See refs/pattern-catalog.md for detailed examples

## References

- `refs/pattern-catalog.md` - Detailed pattern descriptions with implementation examples
- `refs/anti-patterns.md` - Deep dive on anti-patterns with refactoring strategies
