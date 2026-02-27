# Anti-Patterns in Agentic Systems

Comprehensive guide to common mistakes and how to fix them.

## 1. God Agent

### Description
Single agent attempting to handle all responsibilities. Agent has too many tools, too much context, and too many decision points. Becomes a monolithic, unmaintainable system.

### Symptoms
- Agent has access to 20+ tools
- Single system prompt is 5000+ tokens
- Agent handles unrelated tasks (e.g., both code review and deployment)
- Difficult to debug when things go wrong
- High token costs due to large context

### Why It Happens
- Starting simple and accumulating features
- Lack of clear separation of concerns
- Fear of coordination complexity

### How to Fix

**Before:**
```python
god_agent = Agent(
    tools=[
        code_analysis, security_scan, performance_test,
        deploy, rollback, monitoring, alerting,
        documentation, ticket_creation, email_notification
    ],
    instructions="You are a DevOps agent that does everything..."
)
```

**After:**
```python
# Specialized agents with clear responsibilities
code_quality_agent = Agent(
    tools=[code_analysis, security_scan, performance_test],
    instructions="You review code quality, security, and performance."
)

deployment_agent = Agent(
    tools=[deploy, rollback, monitoring],
    instructions="You handle deployments and monitor health."
)

communication_agent = Agent(
    tools=[documentation, ticket_creation, email_notification],
    instructions="You handle documentation and notifications."
)

# Coordinator orchestrates specialists
coordinator = HierarchicalAgent(
    specialists={
        "review": code_quality_agent,
        "deploy": deployment_agent,
        "communicate": communication_agent
    }
)
```

### Prevention
- Each agent should have single, clear responsibility
- Limit agents to 5-10 tools maximum
- When adding a feature, ask: "Does this fit agent's core purpose?"

## 2. Tight Coupling

### Description
Agents depend on internal implementation details of other agents. Changes to one agent break others. Hard to evolve or replace agents independently.

### Symptoms
- Agent A parses the exact output format of Agent B
- Agents share global state without interfaces
- Can't swap out an agent without updating all callers
- Fragile to prompt engineering changes

### Why It Happens
- Quick prototyping without interfaces
- Lack of abstraction layer
- Direct access to other agents' internals

### How to Fix

**Before:**
```python
# Agent B tightly coupled to Agent A's output format
class AgentB:
    async def process(self, agent_a_output):
        # Fragile: depends on exact string format
        if "APPROVED:" in agent_a_output:
            decision = agent_a_output.split("APPROVED:")[1].strip()
            return self.proceed(decision)
```

**After:**
```python
# Define interface/contract
class ReviewDecision:
    approved: bool
    reasoning: str
    confidence: float

# Agent A returns structured data
class AgentA:
    async def review(self, code) -> ReviewDecision:
        result = await self.llm.generate(...)
        return ReviewDecision(
            approved=result["approved"],
            reasoning=result["reasoning"],
            confidence=result["confidence"]
        )

# Agent B depends on interface, not implementation
class AgentB:
    async def process(self, decision: ReviewDecision):
        if decision.approved and decision.confidence > 0.8:
            return self.proceed(decision.reasoning)
```

### Prevention
- Define contracts/interfaces between agents
- Use structured output formats (JSON, Pydantic models)
- Version your interfaces
- Validate inputs and outputs at boundaries

## 3. Missing Guardrails

### Description
Agents can take any action without constraints. No validation, limits, or safety checks. High risk of unintended consequences.

### Symptoms
- Agents can delete production data
- No human approval for high-stakes actions
- Agents can run indefinitely
- No rate limiting or resource constraints
- Sensitive operations have no extra checks

### Why It Happens
- Focus on functionality over safety
- Assuming LLM will "do the right thing"
- Lack of production experience with agents

### How to Fix

**Before:**
```python
class DeploymentAgent:
    async def execute(self, command):
        # No guardrails!
        return await self.shell.run(command)
```

**After:**
```python
class DeploymentAgent:
    def __init__(self, max_runtime=300, require_approval=True):
        self.max_runtime = max_runtime
        self.require_approval = require_approval
        self.allowed_commands = ["deploy", "status", "logs"]
        self.forbidden_patterns = ["rm -rf", "DROP TABLE", "delete"]

    async def execute(self, command):
        # Validate command
        if not self._is_safe_command(command):
            raise SecurityError(f"Unsafe command: {command}")

        # Require approval for production
        if self.require_approval and self.is_production():
            approval = await self.request_human_approval(command)
            if not approval:
                raise AbortedError("Human rejected command")

        # Execute with timeout
        try:
            return await asyncio.wait_for(
                self.shell.run(command),
                timeout=self.max_runtime
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Command exceeded {self.max_runtime}s")

    def _is_safe_command(self, command):
        # Whitelist approach
        if not any(cmd in command for cmd in self.allowed_commands):
            return False
        # Blacklist dangerous patterns
        if any(pattern in command for pattern in self.forbidden_patterns):
            return False
        return True
```

### Prevention
- Start with least privilege (minimal permissions)
- Add human-in-the-loop for high-stakes actions
- Implement timeouts and resource limits
- Whitelist allowed actions
- Validate all inputs and outputs
- Add audit logging

## 4. Deep Nesting

### Description
Agents calling agents calling agents, creating deep hierarchies. Hard to debug, trace, and reason about. High latency and token costs.

### Symptoms
- 4+ levels of agent nesting
- Difficult to trace execution flow
- High latency due to serial delegation
- Token costs grow exponentially with depth
- Hard to determine which agent made which decision

### Why It Happens
- Recursive decomposition without limits
- Each agent delegates instead of doing work
- Lack of architectural planning

### How to Fix

**Before:**
```
CEO Agent
  → VP Agent
    → Manager Agent
      → Team Lead Agent
        → Worker Agent (finally does work!)
```

**After:**
```
Coordinator Agent
  → Specialist A (does work)
  → Specialist B (does work)
  → Specialist C (does work)
```

### Prevention
- Limit hierarchy to 2-3 levels maximum
- Favor flat, wide hierarchies over deep, narrow ones
- Ensure agents at each level do meaningful work, not just delegate
- Use sequential or collaborative patterns when hierarchy isn't needed

## 5. No Observability

### Description
Can't see what agents are doing, why they made decisions, or where failures occur. Debugging is impossible. No metrics or monitoring.

### Symptoms
- "It didn't work" is the only error message
- Can't replay failed executions
- No visibility into agent reasoning
- Can't measure performance or costs
- Silent failures

### Why It Happens
- Focus on happy path
- Treating agents as black boxes
- Lack of production monitoring practices

### How to Fix

```python
class ObservableAgent:
    def __init__(self, logger, tracer):
        self.logger = logger
        self.tracer = tracer

    async def process(self, input):
        # Create trace span
        with self.tracer.span("agent.process") as span:
            span.set_attribute("input", input)

            # Log reasoning
            self.logger.info("Agent reasoning about task", extra={
                "task": input,
                "agent_id": self.id
            })

            # Execute with instrumentation
            start_time = time.time()
            try:
                result = await self._execute(input)
                span.set_attribute("success", True)
                self.logger.info("Agent completed task", extra={
                    "duration": time.time() - start_time,
                    "tokens_used": result.tokens
                })
                return result
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                self.logger.error("Agent failed", extra={
                    "error": str(e),
                    "input": input
                }, exc_info=True)
                raise
```

### What to Observe
- Agent decisions and reasoning
- Token usage per agent
- Latency per agent and per operation
- Success/failure rates
- Input/output at each stage
- Cost attribution

### Prevention
- Structured logging from day one
- Distributed tracing across agents
- Metrics and dashboards
- Ability to replay executions
- Save agent reasoning/thoughts

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
