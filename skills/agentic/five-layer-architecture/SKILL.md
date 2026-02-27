---
name: five-layer-architecture
description: Five-layer architectural model for building production-grade agentic systems with clear separation of concerns
---

# Five-Layer Architecture

A layered architecture model for agentic systems that separates concerns and enables scalable, maintainable, production-ready systems.

## The Five Layers

```
┌─────────────────────────────────────┐
│  Layer 5: Governance                │  Safety, compliance, audit
├─────────────────────────────────────┤
│  Layer 4: Runtime                   │  Execution, monitoring, scaling
├─────────────────────────────────────┤
│  Layer 3: Interaction               │  Tools, APIs, communication
├─────────────────────────────────────┤
│  Layer 2: Context                   │  Memory, state, knowledge
├─────────────────────────────────────┤
│  Layer 1: Cognition                 │  Reasoning, planning, decisions
└─────────────────────────────────────┘
```

## Layer 1: Cognition

Core intelligence - reasoning, planning, and decision-making.

- Task understanding and decomposition
- Planning and strategy formulation
- Reasoning patterns (ReAct, Chain-of-Thought)
- Meta-cognition and self-reflection
- **Anti-pattern**: Mixing business logic into prompts, no separation between reasoning and action

## Layer 2: Context

Memory, state, and knowledge management.

- Short-term working memory (conversation history)
- Long-term memory (persistent knowledge, vector search)
- State management and checkpointing
- Context window optimization and compression
- **Anti-pattern**: Passing entire history to every agent (context bloat)

## Layer 3: Interaction

Tools, APIs, and communication channels.

- Tool/function registry and execution
- External API integration with error handling
- Multi-agent communication protocols
- Rate limiting, retry logic, serialization
- **Anti-pattern**: Tight coupling, no retry/timeout, missing input validation

## Layer 4: Runtime

Execution environment, monitoring, and scaling.

- Agent lifecycle management (start, stop, restart)
- Concurrent execution and orchestration
- Observability (logging, tracing, metrics)
- Resource quotas, health checks, circuit breakers
- **Anti-pattern**: No observability, no resource limits, synchronous bottlenecks

## Layer 5: Governance

Safety, compliance, and audit.

- Safety guardrails and action constraints
- Human-in-the-loop approval gates
- Audit logging, traceability, compliance
- PII detection, access control, rollback
- **Anti-pattern**: No approval gates, missing audit trails, no rollback

## Layer Interaction Patterns

**Bottom-Up Flow**: Cognition decides → Context provides info → Interaction executes → Runtime monitors → Governance validates

**Top-Down Constraints**: Governance sets policies → Runtime enforces limits → Interaction restricts tools → Context filters sensitive data → Cognition operates within constraints

**Cross-Layer**: Observability, security, error handling, and performance optimization span all layers.

## Designing a New System

1. Start with **Cognition**: What reasoning/planning capability do you need?
2. Add **Context**: What information must agents remember?
3. Define **Interaction**: What tools/APIs do agents need?
4. Build **Runtime**: How will you execute, monitor, scale?
5. Implement **Governance**: What safety/compliance is required?

## Quick Reference

| Layer | Focus | Key Question | Example Component |
|-------|-------|--------------|-------------------|
| 1. Cognition | Intelligence | "What should I do?" | LLM reasoning |
| 2. Context | Memory | "What do I know?" | Vector database |
| 3. Interaction | Tools | "How do I act?" | API clients |
| 4. Runtime | Execution | "Is it working?" | Monitoring |
| 5. Governance | Safety | "Is it safe?" | Approval gates |

## When to Use

- "How should I architect my agentic system?"
- "Where does [component] belong in the architecture?"
- "My system is getting messy and hard to maintain"
- "How do I separate concerns in my agent system?"

## References

- `refs/layers-deep-dive.md` - Detailed responsibilities, components, and anti-patterns per layer
- `refs/implementation-guide.md` - Step-by-step guide to building each layer
