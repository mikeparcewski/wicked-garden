# Anti-Patterns in Agentic Systems: Operational

Operational anti-patterns including Sequential Bottleneck, Context Bloat, Redundant Agents, Hardcoded Prompts, and Missing Timeouts.

## 6. Sequential Bottleneck

### Description
All work happens sequentially even when tasks are independent. Wastes time and resources through unnecessary serialization.

### Symptoms
- Total execution time is sum of all agent times
- Agents sit idle waiting for others
- No concurrent execution
- Low resource utilization

### Why It Happens
- Sequential pattern is easiest to implement
- Not identifying independent subtasks
- Lack of async/parallel execution

### How to Fix

**Before:**
```python
# Sequential execution: 30 seconds total
result1 = await agent1.process()  # 10 seconds
result2 = await agent2.process()  # 10 seconds
result3 = await agent3.process()  # 10 seconds
```

**After:**
```python
# Parallel execution: 10 seconds total
results = await asyncio.gather(
    agent1.process(),
    agent2.process(),
    agent3.process()
)
```

### Prevention
- Identify independent subtasks
- Use asyncio.gather() or similar for parallel execution
- Consider autonomous or collaborative patterns
- Profile execution to find bottlenecks

## 7. Context Bloat

### Description
Passing entire conversation history to every agent. Wasting tokens on irrelevant context. Slow and expensive.

### Symptoms
- Each agent receives 50k+ token context
- Most context is irrelevant to agent's task
- High costs and latency
- Hitting context window limits

### Why It Happens
- "More context is better" assumption
- Easy to pass everything vs. filtering
- Not understanding what each agent needs

### How to Fix

**Before:**
```python
# Pass entire history to specialist
await specialist.process(entire_conversation_history)
```

**After:**
```python
# Extract only relevant context
relevant_context = self.extract_relevant_context(
    full_history,
    specialist.needs
)
await specialist.process(relevant_context)

def extract_relevant_context(self, history, needs):
    # Only include messages relevant to this specialist
    return [
        msg for msg in history
        if self.is_relevant(msg, needs)
    ]
```

### Prevention
- Give each agent only what it needs
- Compress or summarize old context
- Use retrieval instead of passing everything
- Implement context window budgets per agent

## 8. Redundant Agents

### Description
Multiple agents doing the same thing. Wasted resources and complexity without benefit.

### Symptoms
- Two agents with identical tools and instructions
- Same task being done multiple times
- Agents overriding each other's work

### How to Fix
Consolidate into single agent or use agent pool:

```python
# Instead of redundant agents
agent1 = Agent(tools=[code_review], instructions="Review code")
agent2 = Agent(tools=[code_review], instructions="Review code")

# Use single agent or agent pool
review_agent = Agent(tools=[code_review], instructions="Review code")

# Or if need concurrency, use pool of identical agents
review_pool = AgentPool(
    agent_factory=lambda: Agent(tools=[code_review], instructions="Review code"),
    pool_size=3
)
```

## 9. Hardcoded Prompts

### Description
System prompts and instructions baked into code. Hard to iterate, version, and A/B test.

### Symptoms
- Prompts scattered throughout codebase
- Can't change prompts without code deployment
- No version control for prompts
- Can't A/B test prompt variations

### How to Fix

**Before:**
```python
class Agent:
    def __init__(self):
        self.prompt = "You are a helpful assistant that..."  # Hardcoded
```

**After:**
```python
# Externalize prompts
class Agent:
    def __init__(self, prompt_template_path):
        self.template = self.load_template(prompt_template_path)

    def load_template(self, path):
        # Load from file, database, or config service
        return Template.from_file(path)

# Version control and manage prompts separately
prompts/
  agent-v1.txt
  agent-v2.txt
  agent-v3.txt
```

### Prevention
- Store prompts in separate files or configuration
- Version prompts alongside code
- Use template systems for dynamic prompts
- Enable runtime prompt updates

## 10. Missing Timeouts

### Description
Agents can run forever. No time or resource limits. Can hang indefinitely or consume unlimited resources.

### Symptoms
- Agents occasionally never return
- Resource exhaustion (memory, tokens, API quota)
- No way to detect or recover from hangs

### How to Fix

```python
class Agent:
    def __init__(self, max_runtime=60, max_tokens=10000, max_iterations=10):
        self.max_runtime = max_runtime
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations

    async def process(self, input):
        # Time limit
        timeout = asyncio.timeout(self.max_runtime)

        async with timeout:
            tokens_used = 0
            iterations = 0

            while not done:
                # Iteration limit
                iterations += 1
                if iterations > self.max_iterations:
                    raise MaxIterationsError()

                result = await self.llm.generate(...)

                # Token budget
                tokens_used += result.tokens
                if tokens_used > self.max_tokens:
                    raise TokenBudgetExceededError()
```

### Prevention
- Set timeouts on all async operations
- Implement token budgets
- Limit loop iterations
- Add circuit breakers for external calls
- Monitor resource usage
