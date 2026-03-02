# Implementation Guide - Layers 4-5 and Integration

Step-by-step guide to implementing Layer 4 (Runtime), Layer 5 (Governance), and assembling the complete system.

## Phase 4: Layer 4 - Runtime

### Step 4.1: Add Observability

```python
import logging
from datetime import datetime

class ObservableAgent:
    def __init__(self, agent, logger=None):
        self.agent = agent
        self.logger = logger or logging.getLogger(__name__)

    async def process(self, task, session_id):
        start_time = datetime.now()
        self.logger.info(f"Agent {self.agent.name} processing task", extra={
            "task": task,
            "session_id": session_id
        })

        try:
            result = await self.agent.process(task, session_id)

            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Agent {self.agent.name} completed task", extra={
                "duration": duration,
                "success": True
            })

            return result
        except Exception as e:
            self.logger.error(f"Agent {self.agent.name} failed", extra={
                "error": str(e),
                "task": task
            }, exc_info=True)
            raise
```

### Step 4.2: Add Resource Management

```python
class ResourceManager:
    def __init__(self, max_tokens=100000, max_cost=10.0):
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.tokens_used = 0
        self.cost_incurred = 0.0

    def track_usage(self, tokens, cost):
        self.tokens_used += tokens
        self.cost_incurred += cost

        if self.tokens_used > self.max_tokens:
            raise ResourceLimitError(f"Token limit exceeded: {self.tokens_used}/{self.max_tokens}")

        if self.cost_incurred > self.max_cost:
            raise ResourceLimitError(f"Cost limit exceeded: ${self.cost_incurred}/${self.max_cost}")

    def get_stats(self):
        return {
            "tokens_used": self.tokens_used,
            "tokens_remaining": self.max_tokens - self.tokens_used,
            "cost_incurred": self.cost_incurred,
            "cost_remaining": self.max_cost - self.cost_incurred
        }

class ResourceTrackedAgent:
    def __init__(self, agent, resource_manager):
        self.agent = agent
        self.resources = resource_manager

    async def process(self, task, session_id):
        result = await self.agent.process(task, session_id)

        # Track usage (assumes result contains token count)
        tokens = result.get("tokens", 0)
        cost = self.calculate_cost(tokens)
        self.resources.track_usage(tokens, cost)

        return result

    def calculate_cost(self, tokens):
        # Approximate cost calculation
        return tokens * 0.00001  # Adjust based on actual pricing
```

### Step 4.3: Concurrent Execution

```python
import asyncio

class AgentPool:
    def __init__(self, agent_factory, pool_size=3):
        self.agents = [agent_factory() for _ in range(pool_size)]
        self.semaphore = asyncio.Semaphore(pool_size)

    async def process(self, task, session_id):
        async with self.semaphore:
            # Get available agent (simple round-robin)
            agent = self.agents[hash(session_id) % len(self.agents)]
            return await agent.process(task, session_id)

# Parallel task execution
class ParallelExecutor:
    async def execute_all(self, tasks):
        return await asyncio.gather(*[
            self.execute_task(task) for task in tasks
        ])

    async def execute_task(self, task):
        # Execute individual task
        pass
```

## Phase 5: Layer 5 - Governance

### Step 5.1: Safety Validation

```python
class SafetyPolicy:
    def __init__(self, name):
        self.name = name

    async def evaluate(self, action):
        raise NotImplementedError()

class NoProductionDeletePolicy(SafetyPolicy):
    async def evaluate(self, action):
        if action.get("type") == "delete" and action.get("env") == "production":
            return {"allowed": False, "reason": "Production deletes forbidden"}
        return {"allowed": True}

class SafetyValidator:
    def __init__(self, policies):
        self.policies = policies

    async def validate(self, action):
        for policy in self.policies:
            result = await policy.evaluate(action)
            if not result["allowed"]:
                raise SafetyViolation(f"Blocked by {policy.name}: {result['reason']}")
```

### Step 5.2: Approval Workflow

```python
class ApprovalWorkflow:
    def __init__(self, notification_service):
        self.notification_service = notification_service
        self.pending_approvals = {}

    async def request_approval(self, action, approvers):
        approval_id = str(uuid.uuid4())
        self.pending_approvals[approval_id] = {
            "action": action,
            "approvers": approvers,
            "status": "pending",
            "created_at": datetime.now()
        }

        # Notify approvers
        await self.notification_service.notify(
            approvers,
            f"Approval requested for: {action}"
        )

        return approval_id

    async def approve(self, approval_id, approver):
        if approval_id not in self.pending_approvals:
            raise ValueError("Unknown approval request")

        self.pending_approvals[approval_id]["status"] = "approved"
        self.pending_approvals[approval_id]["approved_by"] = approver
        self.pending_approvals[approval_id]["approved_at"] = datetime.now()

    async def wait_for_approval(self, approval_id, timeout=3600):
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            if self.pending_approvals[approval_id]["status"] == "approved":
                return True
            await asyncio.sleep(1)
        return False
```

### Step 5.3: Audit Logging

```python
class AuditLog:
    def __init__(self, storage_path):
        self.storage_path = storage_path

    async def log_event(self, event_type, data):
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }

        async with aiofiles.open(self.storage_path, "a") as f:
            await f.write(json.dumps(event) + "\n")

    async def log_decision(self, agent_id, decision, reasoning):
        await self.log_event("decision", {
            "agent_id": agent_id,
            "decision": decision,
            "reasoning": reasoning
        })

    async def log_action(self, agent_id, action, outcome):
        await self.log_event("action", {
            "agent_id": agent_id,
            "action": action,
            "outcome": outcome
        })
```

## Putting It All Together

```python
class ProductionAgenticSystem:
    def __init__(self):
        # Layer 1: Cognition
        self.llm = LLMClient(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Layer 2: Context
        self.sessions = SessionManager()
        self.memory = VectorMemory()

        # Layer 3: Interaction
        self.tools = ToolRegistry()
        self._register_tools()

        # Layer 4: Runtime
        self.resources = ResourceManager()
        self.logger = logging.getLogger(__name__)

        # Layer 5: Governance
        self.safety = SafetyValidator(policies=[NoProductionDeletePolicy("no-prod-delete")])
        self.audit = AuditLog("/var/log/agent-audit.log")

        # Create base agent
        base_agent = ToolUsingAgent(
            name="assistant",
            instructions="You are a helpful assistant.",
            llm_client=self.llm,
            session_manager=self.sessions,
            memory=self.memory,
            tools=self.tools
        )

        # Wrap with runtime features
        self.agent = ObservableAgent(
            ResourceTrackedAgent(base_agent, self.resources),
            self.logger
        )

    async def process_request(self, request, session_id, user_id):
        # Log request
        await self.audit.log_event("request", {
            "user_id": user_id,
            "request": request
        })

        # Process through agent
        response = await self.agent.process(request, session_id)

        # Log response
        await self.audit.log_event("response", {
            "user_id": user_id,
            "response": response
        })

        return response
```

## Testing the Complete System

```python
async def test_system():
    system = ProductionAgenticSystem()

    # Test basic request
    response = await system.process_request(
        request="What is the weather like?",
        session_id="test-session",
        user_id="user-123"
    )

    print(f"Response: {response}")

    # Check resource usage
    stats = system.resources.get_stats()
    print(f"Resources used: {stats}")

asyncio.run(test_system())
```
