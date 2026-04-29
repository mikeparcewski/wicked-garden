---
name: context-engineering
description: "Optimize context window usage, compress conversation history, manage token budgets, and design efficient memory systems for multi-agent workflows. Use when: reducing token consumption, implementing sliding-window context, compressing agent state, designing cross-session memory, or budgeting tokens across agent turns. Not for general prompt engineering or agent orchestration."
---

# Context Engineering

Concrete techniques for managing context windows and token budgets in agentic systems.

## Quick Start — Compress a Long Conversation

When conversation history exceeds a token budget, compress older turns:

```python
def compress_history(messages, max_tokens=4000):
    """Keep recent messages verbatim, summarize older ones."""
    recent = messages[-5:]  # last 5 turns stay intact
    older = messages[:-5]
    if not older:
        return recent
    summary = summarize(older)  # LLM call to compress
    return [{"role": "system", "content": f"Prior context: {summary}"}] + recent
```

## State Management Patterns

### Shared State
All agents access common state store.
**Use when:** Agents need synchronized view. **Trade-off:** Contention risk.

### Isolated State
Each agent maintains private state.
**Use when:** Agents operate independently. **Trade-off:** Inconsistency possible.

### Checkpointed State
Periodic snapshots for recovery.
**Use when:** Long-running processes. **Trade-off:** Storage overhead.

See `refs/compression-techniques.md` for implementation details.

## Token Optimization Techniques

### 1. Structured Compression
Replace prose with compact formats:

```python
# Before (42 tokens):
# "The user's name is John Smith, they work at Acme Corp as a senior engineer"
# After (12 tokens):
context = {"name": "John Smith", "company": "Acme Corp", "role": "senior engineer"}
```

### 2. Selective Context Loading
Load only what the current task needs:

```python
def load_context(task_type, all_context):
    """Load relevant context slices based on task type."""
    relevance_map = {
        "debugging": ["error_logs", "recent_changes", "stack_trace"],
        "implementation": ["requirements", "architecture", "api_specs"],
        "review": ["diff", "test_results", "standards"],
    }
    keys = relevance_map.get(task_type, list(all_context.keys())[:3])
    return {k: all_context[k] for k in keys if k in all_context}
```

### 3. Reference Instead of Embed
Point to files rather than inlining full content.

### 4. Lazy Loading
Defer detail loading until explicitly needed — load summaries first.

See `refs/selective-loading.md` and `refs/caching-and-optimization.md` for detailed strategies.

## Memory Patterns

| Pattern | Scope | Size | Retention | Implementation |
|---------|-------|------|-----------|----------------|
| Working | Current task | 1K-10K tokens | Session | In-context messages |
| Long-term | Cross-session | Unbounded | Permanent | Vector DB / FTS5 |
| Episodic | Historical | Summaries | Varies | Compressed snapshots |

See `refs/compression-techniques.md` for implementation patterns.

## Context Budget Workflow

1. **Set budget** — Define max tokens per agent and per session
2. **Measure** — Track input/output tokens per call
3. **Compress** — When approaching limit, summarize older context
4. **Validate** — Confirm critical information survived compression
5. **Report** — Log token usage for cost attribution

```python
class TokenBudget:
    def __init__(self, limit=8000):
        self.limit = limit
        self.used = 0

    def can_add(self, tokens):
        return self.used + tokens <= self.limit

    def add(self, tokens):
        if not self.can_add(tokens):
            raise TokenBudgetExceeded(f"{self.used + tokens} > {self.limit}")
        self.used += tokens
```

See `refs/cost-calculation-budget.md` and `refs/cost-optimization-reporting.md` for detailed cost strategies.

## Context Strategies by Agent Pattern

| Pattern | Strategy | Key rule |
|---------|----------|----------|
| Sequential | Pass only previous agent's output, not entire chain | Avoid token accumulation |
| Hierarchical | Parent gets summaries; children get task-specific context | Minimize parent bloat |
| Collaborative | Shared compressed context; each agent adds delta only | Control growth rate |
| Autonomous | Minimal shared context; isolated per agent | Maximize independence |

## References

- `refs/compression-techniques.md` — Conversation summarization, deduplication, entity compression
- `refs/selective-loading.md` — Relevance filtering, time decay, token-budgeted retrieval
- `refs/caching-and-optimization.md` — Prompt caching, semantic caching, batching, cost-aware model selection
- `refs/cost-calculation-budget.md` — Token pricing, cost calculation, budget management
- `refs/cost-optimization-reporting.md` — Cost estimation, optimization strategies, reporting
