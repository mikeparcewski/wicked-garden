# Anti-Patterns in Agentic Systems: Design

Common design mistakes in agentic systems and how to fix them. Covers God Agent, Tight Coupling, Missing Guardrails, Deep Nesting, and No Observability.

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

Wrap every agent in an `ObservableAgent` decorator that: opens a trace span, logs the task and agent ID before execution, records success/failure + duration + tokens_used after execution, and re-raises exceptions with full context.

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
