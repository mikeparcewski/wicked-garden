---
name: context-engineering
description: |
  Context window management, token optimization, and memory patterns for efficient multi-agent systems.

  Use when: optimizing token usage in an agentic pipeline, designing memory
  scope for short / long-term / episodic state, or applying a context-loading
  strategy (anticipatory / JIT / hybrid).
portability: portable
---

# Context Engineering

Techniques for managing context windows, optimizing token usage, and designing efficient memory systems for agentic applications.

## Context Window Fundamentals

**Context Window:** Maximum tokens an LLM can process in a single request (input + output).

Limits vary by provider and model. Check the active model's documentation for
the exact value.

**Token Efficiency Matters:**
- Cost: Charged per token (input + output)
- Latency: More tokens = slower response
- Quality: Irrelevant context can confuse model

## State Management Patterns

| Pattern | Use when | Pros | Cons |
|---------|----------|------|------|
| **Shared** | Agents need synchronized view | Consistency, simple coordination | Contention, single point of failure |
| **Isolated** | Agents operate independently | No contention, parallel execution | Inconsistency possible, harder to coordinate |
| **Checkpointed** | Long-running processes, need recovery | Fault tolerance, replayability | Storage overhead, consistency complexity |

## Token Optimization Techniques

### 1. Aggressive Summarization
Compress old context into summaries to reduce token usage.

### 2. Selective Context Loading
Only load relevant context based on the current task.

### 3. Structured Compression
Use JSON/structured formats instead of prose to reduce tokens.

**Example:**
- Before: "The user's name is John Smith..." (verbose)
- After: `{"name": "John Smith", ...}` (compact)

### 4. Lazy Loading
Load details only when explicitly needed.

### 5. Reference Instead of Embedding
Reference external documents instead of embedding full text.

See `refs/selective-loading.md` and `refs/caching-and-optimization.md` for code examples and detailed strategies.

## Memory Patterns

| Memory | Scope | Size | Retention |
|--------|-------|------|-----------|
| **Short-term (working)** | Current session/task | 1K-10K tokens | Minutes to hours |
| **Long-term** | Cross-session, permanent | Unbounded (vector DB) | Days to forever |
| **Episodic** | Historical events | Summaries stored | Varies by importance |

See `refs/compression-techniques.md` for implementation patterns.

## Prompt Engineering for Agents

### Role Definition
Be specific about agent's role and boundaries.

**Example:**
```
You are a Python code reviewer specializing in security.
Your job is to identify security vulnerabilities.
You do NOT review style or performance.
```

### Task Specification
Clear, actionable instructions with explicit format.

**Bad:** "Review this code."
**Good:** "Review for security: 1) SQL injection 2) Input validation 3) Secrets. Output: JSON with vulnerabilities."

### Format Control
Specify exact output format to reduce tokens.

### Few-Shot Examples
Show examples for complex tasks.

See `refs/selective-loading.md` for detailed prompting patterns.

## Context Loading Strategies

| Strategy | Pros | Cons |
|----------|------|------|
| **Anticipatory** | Faster response time (load before needed) | May load unnecessary data |
| **Just-in-Time (JIT)** | Minimal token usage (load only when needed) | Latency on each request |
| **Hybrid** | Balanced (core context + JIT for task-specific) | More complex implementation |

## Cost Modeling

### Token Cost Calculation
Track input and output tokens separately. Rates vary by model (typically $0.003-0.075 per 1K tokens).

### Budget Enforcement
Set hard token limits per agent/session to prevent runaway costs.

### Multi-Agent Cost Attribution
Track costs per agent to identify expensive components.

See `refs/cost-calculation-budget.md` and `refs/cost-optimization-reporting.md` for detailed cost strategies.

## Context Window Strategies by Agent Pattern

**Sequential Pattern:** Pass only output of previous agent, not entire chain.

**Hierarchical Pattern:** Parent gets summaries from children, children get only relevant task context.

**Collaborative Pattern:** Shared context (compressed), each agent adds only delta.

**Autonomous Pattern:** Minimal shared context, isolated context per agent.

## Quick Wins

1. **Compress old messages:** Summarize history > 20 messages
2. **Use structured outputs:** JSON instead of prose
3. **Lazy load details:** Only when needed
4. **Set token budgets:** Hard limits per agent/session
5. **Monitor token usage:** Track and optimize high-cost agents

## References

- `refs/compression-techniques.md` - Conversation summarization, deduplication, entity compression
- `refs/selective-loading.md` - Relevance filtering, time decay, token-budgeted retrieval
- `refs/caching-and-optimization.md` - Prompt caching, semantic caching, batching, cost-aware model selection
- `refs/cost-calculation-budget.md` - Token pricing, cost calculation, budget management
- `refs/cost-optimization-reporting.md` - Cost estimation, optimization strategies, reporting
