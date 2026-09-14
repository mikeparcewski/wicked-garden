# Performance analysis — the process and the optimization template

Loaded on demand by the `wicked-garden-agentic-performance-analyst` worker skill (its `SKILL.md` points here). Eight steps, then the per-strategy optimization template.

## Performance Analysis Process

### 1. Baseline Measurement

Establish the agent landscape baseline. The analyzer prints JSON to stdout —
redirect it to a file (there are no `--metrics`/`--output` flags):

```bash
# Map agents, dependencies, and communication patterns
wicked-garden run scripts/agentic/analyze_agents.py \
  --path /path/to/codebase > performance-baseline.json
```

Derive execution-pattern findings by reading the dependency graph and
communication patterns in the output, plus code inspection (grep for
sequential awaits, tool-call sites, prompt construction).

**Key Metrics to Track**:
- Total token usage (prompt + completion)
- Latency (p50, p95, p99)
- Cost per request
- Cache hit rate
- Agent execution time
- Tool call duration

### 2. Token Analysis

#### Identify Token Hotspots

```bash
# Search for large prompts
grep -r "system_prompt\|system_message" --include="*.py" /path/to/codebase

# Find repeated context patterns
grep -r "context.*=" --include="*.py" /path/to/codebase
```

#### Token Budget Allocation

Calculate token usage per agent:

```
Total Context Window: 200k tokens (Claude Opus 4.6)

Recommended Allocation:
- System Prompt: 2,000 tokens (1%)
- Agent Instructions: 3,000 tokens (1.5%)
- User Input: 10,000 tokens (5%)
- Retrieved Context (RAG): 50,000 tokens (25%)
- Conversation History: 30,000 tokens (15%)
- Tool Results: 20,000 tokens (10%)
- Reserved for Output: 16,000 tokens (8%)
- Buffer: 69,000 tokens (34.5%)
```

#### Token Optimization Checklist

- [ ] **System Prompts**: Cacheable, reused across requests
- [ ] **Few-Shot Examples**: Minimal but effective
- [ ] **Tool Descriptions**: Concise, not verbose
- [ ] **Context**: Pruned to relevant information only
- [ ] **History**: Summarized after N turns
- [ ] **Output**: Bounded by max_tokens parameter

### 3. Latency Analysis

#### Identify Sequential Bottlenecks

```bash
# Look for sequential agent calls
grep -r "await.*agent\|agent\.run\|agent\.execute" \
  --include="*.py" /path/to/codebase -A 5
```

**Sequential Pattern (SLOW)**:
```python
# BAD: Sequential execution
result1 = await agent1.run(input)
result2 = await agent2.run(input)
result3 = await agent3.run(input)
# Total time: T1 + T2 + T3
```

**Parallel Pattern (FAST)**:
```python
# GOOD: Parallel execution
results = await asyncio.gather(
    agent1.run(input),
    agent2.run(input),
    agent3.run(input),
)
# Total time: max(T1, T2, T3)
```

#### Latency Budget

Define acceptable latencies:

| Operation | Target | Acceptable | Critical |
|-----------|--------|------------|----------|
| Simple query | < 2s | < 5s | > 10s |
| Complex reasoning | < 5s | < 15s | > 30s |
| Multi-agent workflow | < 10s | < 30s | > 60s |
| Background task | < 60s | < 300s | > 600s |

#### Optimization Opportunities

- [ ] **Streaming**: Enable for user-facing agents
- [ ] **Parallel**: Independent agents run concurrently
- [ ] **Caching**: Cache frequent queries
- [ ] **Batching**: Group small requests
- [ ] **Timeouts**: Set aggressive timeouts for fast-fail

### 4. Cost Analysis

#### Cost Calculation

```python
# Example cost calculation (anthropic claude-sonnet-4.5)
INPUT_COST_PER_1M = 3.00   # USD per 1M tokens
OUTPUT_COST_PER_1M = 15.00  # USD per 1M tokens

def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost per request."""
    prompt_cost = (prompt_tokens / 1_000_000) * INPUT_COST_PER_1M
    completion_cost = (completion_tokens / 1_000_000) * OUTPUT_COST_PER_1M
    return prompt_cost + completion_cost

# Example request
cost = calculate_cost(10_000, 1_000)
# prompt: 10k tokens * $3/1M = $0.03
# completion: 1k tokens * $15/1M = $0.015
# total: $0.045 per request
```

#### Cost Optimization Strategies

| Strategy | Savings | Complexity | Trade-off |
|----------|---------|------------|-----------|
| Prompt caching | 50-90% | Low | None |
| Model downgrade | 50-80% | Low | Quality |
| Response caching | 80-99% | Medium | Freshness |
| Shorter prompts | 10-30% | Medium | Completeness |
| Smaller max_tokens | 5-20% | Low | Truncation risk |
| Batching requests | 10-20% | High | Latency |

#### ROI Analysis Template

```markdown

## Optimization: {strategy name}

**Current State**:
- Cost per request: ${amount}
- Requests per day: {count}
- Monthly cost: ${amount}

**Proposed State**:
- Cost per request: ${amount}
- Savings per request: ${amount} ({percent}%)
- Monthly savings: ${amount}

**Implementation**:
- Effort: {LOW/MEDIUM/HIGH}
- Risk: {LOW/MEDIUM/HIGH}
- Timeline: {duration}

**Trade-offs**:
- {trade-off description}

**Recommendation**: {IMPLEMENT/DEFER/REJECT}
```

### 5. Parallelization Assessment

#### Identify Independent Operations

Use the agent analyzer's dependency graph to find parallelizable paths
(no `--analysis` flag — the parallelization read is yours to derive):

```bash
wicked-garden run scripts/agentic/analyze_agents.py \
  --path /path/to/codebase > parallel-opportunities.json
```

Agents with no shared dependencies and no data flow between them in the
dependency graph are candidates for concurrent execution.

#### Parallelization Checklist

- [ ] **Independent Agents**: No shared mutable state
- [ ] **Tool Calls**: Multiple tools called concurrently
- [ ] **RAG Retrieval**: Query multiple sources in parallel
- [ ] **Validation**: Run validators concurrently
- [ ] **Multi-Provider**: Query multiple LLMs for consensus

#### Parallelization Patterns

**Pattern 1: Scatter-Gather**
```python
# Parallel execution with aggregation
async def scatter_gather(query: str):
    tasks = [
        agent1.run(query),
        agent2.run(query),
        agent3.run(query),
    ]
    results = await asyncio.gather(*tasks)
    return aggregate(results)
```

**Pattern 2: Pipeline with Parallel Stages**
```python
# Stage 1: Parallel
stage1_results = await asyncio.gather(
    preprocess_a(input),
    preprocess_b(input),
)

# Stage 2: Sequential (depends on stage 1)
stage2_result = await process(stage1_results)

# Stage 3: Parallel
final_results = await asyncio.gather(
    postprocess_a(stage2_result),
    postprocess_b(stage2_result),
)
```

**Pattern 3: Race Condition**
```python
# Return first successful result
result = await asyncio.wait_for(
    asyncio.wait([agent1.run(query), agent2.run(query)],
                 return_when=asyncio.FIRST_COMPLETED),
    timeout=5.0
)
```

### 6. Caching Strategy Assessment

#### Cache Opportunity Analysis

```bash
# Find repeated prompt patterns
grep -r "def.*prompt\|system_prompt\|PROMPT" \
  --include="*.py" /path/to/codebase
```

#### Caching Layers

**L1: Prompt Cache (System Prompt)**
- **What**: System instructions, few-shot examples
- **TTL**: Hours to days
- **Savings**: 50-90% on prompt tokens
- **Best for**: Stable system prompts

**L2: Response Cache (Deterministic Queries)**
- **What**: Exact query matches
- **TTL**: Minutes to hours
- **Savings**: 100% on both prompt and completion
- **Best for**: FAQ, documentation lookup

**L3: Semantic Cache (Similar Queries)**
- **What**: Semantically similar queries
- **TTL**: Minutes to hours
- **Savings**: 100% on both prompt and completion
- **Best for**: Repetitive user queries with variations

**L4: Intermediate Result Cache**
- **What**: Tool results, RAG retrieval, preprocessed data
- **TTL**: Minutes to hours
- **Savings**: Reduces tool call latency and cost
- **Best for**: Expensive operations

#### Caching Implementation Checklist

- [ ] System prompts are cached (prompt caching feature)
- [ ] Frequently asked queries are cached
- [ ] Expensive tool results are cached
- [ ] Cache invalidation strategy exists
- [ ] Cache hit rate is monitored

#### Cache Invalidation Strategy

```python
# Time-based expiration
cache.set(key, value, ttl=3600)  # 1 hour

# Event-based invalidation
@on_data_update
def invalidate_cache():
    cache.delete_pattern("rag:*")

# Version-based invalidation
cache_key = f"response:{query_hash}:v{schema_version}"
```

### 7. Context Window Management

#### Context Overflow Strategies

**Strategy 1: Sliding Window**
```python
MAX_CONTEXT_TOKENS = 100_000

def sliding_window(history: list[Message]) -> list[Message]:
    """Keep most recent messages within token budget."""
    total_tokens = 0
    kept_messages = []

    for msg in reversed(history):
        msg_tokens = count_tokens(msg)
        if total_tokens + msg_tokens > MAX_CONTEXT_TOKENS:
            break
        kept_messages.insert(0, msg)
        total_tokens += msg_tokens

    return kept_messages
```

**Strategy 2: Importance-Based Pruning**
```python
def importance_pruning(history: list[Message]) -> list[Message]:
    """Keep important messages, prune filler."""
    # Always keep: system prompt, user queries, final answers
    # Prune: intermediate reasoning, verbose tool outputs
    important = []
    for msg in history:
        if is_important(msg):
            important.append(msg)
        elif should_summarize(msg):
            important.append(summarize(msg))
    return important
```

**Strategy 3: Summarization**
```python
def summarize_history(history: list[Message], max_tokens: int) -> list[Message]:
    """Summarize old history, keep recent verbatim."""
    if count_tokens(history) <= max_tokens:
        return history

    # Keep recent N messages verbatim
    recent = history[-10:]
    old = history[:-10]

    # Summarize old history
    summary_msg = Message(
        role="system",
        content=f"Previous conversation summary: {summarize(old)}"
    )

    return [summary_msg] + recent
```

#### Context Management Checklist

- [ ] Context window limits are defined
- [ ] Overflow strategy is implemented
- [ ] Important context is prioritized
- [ ] Summaries are generated for old context
- [ ] Context usage is monitored

### 8. Update Task

Append the performance findings to the current task's description — the harness's task list where it has one (the `wicked-garden-workflow` skill's `refs/integration.md` carries the field list and the harness-specific Hand-off), else your working notes:

```markdown
[performance-analyst] Performance Assessment Complete

**Current Performance**:
- Avg latency: {p50}ms (p95: {p95}ms)
- Avg cost: ${cost}/request
- Token usage: {tokens}/request
- Cache hit rate: {rate}%

**Optimization Opportunities**:
1. {opportunity} - Est. savings: {savings}
2. {opportunity} - Est. speedup: {improvement}

**Recommendations**:
1. {recommendation}

**Next Steps**: {action needed}
```
