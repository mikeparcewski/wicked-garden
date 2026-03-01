---
name: context-engineering
description: |
  Context window management, token optimization, and memory patterns for efficient multi-agent systems.
  Use when: "context window", "token optimization", "agent memory", "reduce token usage", "context engineering"
---

# Context Engineering

Techniques for managing context windows, optimizing token usage, and designing efficient memory systems for agentic applications.

## Context Window Fundamentals

**Context Window:** Maximum tokens an LLM can process in a single request (input + output).

**Common Limits:**
- Claude Opus 4.6: 200K tokens
- Claude Sonnet 4.5: 200K tokens
- GPT-4 Turbo: 128K tokens
- GPT-4: 8K-32K tokens

**Token Efficiency Matters:**
- Cost: Charged per token (input + output)
- Latency: More tokens = slower response
- Quality: Irrelevant context can confuse model

## State Management Patterns

### Shared State
All agents access common state store.

**Use when:** Agents need synchronized view of world.
**Pros:** Consistency, simple coordination
**Cons:** Contention, single point of failure

### Isolated State
Each agent maintains its own private state.

**Use when:** Agents operate independently, no coordination needed.
**Pros:** No contention, parallel execution
**Cons:** Inconsistency possible, harder to coordinate

### Checkpointed State
Periodically save state snapshots for recovery.

**Use when:** Long-running processes, need recovery from failures.
**Pros:** Fault tolerance, replayability
**Cons:** Storage overhead, consistency complexity

See `refs/compression-techniques.md` for implementation details.

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

### Short-Term (Working) Memory
Recent conversation, current task state.

**Scope:** Current session/task
**Size:** 1K-10K tokens
**Retention:** Minutes to hours

### Long-Term Memory
Persistent knowledge, learned facts.

**Scope:** Cross-session, permanent
**Size:** Unbounded (stored externally via vector DB)
**Retention:** Days to forever

### Episodic Memory
Specific past events/experiences.

**Scope:** Historical episodes
**Size:** Summaries stored
**Retention:** Varies by importance

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

### Anticipatory Loading
Load context before it's needed (if predictable).
**Pros:** Faster response time
**Cons:** May load unnecessary data

### Just-in-Time (JIT) Loading
Load context only when explicitly needed.
**Pros:** Minimal token usage
**Cons:** Latency on each request

### Hybrid Approach
Combine both: Always load core context + JIT load task-specific context.

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

## When to Use

Trigger phrases indicating you need this skill:
- "Token costs are too high"
- "Running into context limits"
- "Responses are slow"
- "How do I manage conversation history?"
- "What should agents remember?"
- "How to optimize for cost?"

## References

- `refs/compression-techniques.md` - Conversation summarization, deduplication, entity compression
- `refs/selective-loading.md` - Relevance filtering, time decay, token-budgeted retrieval
- `refs/caching-and-optimization.md` - Prompt caching, semantic caching, batching, cost-aware model selection
- `refs/cost-calculation-budget.md` - Token pricing, cost calculation, budget management
- `refs/cost-optimization-reporting.md` - Cost estimation, optimization strategies, reporting
