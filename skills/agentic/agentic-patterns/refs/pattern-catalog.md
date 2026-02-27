# Pattern Catalog

Detailed reference for agentic architecture patterns with implementation guidance.

## Sequential Pattern

### Description
Agents execute in a fixed linear order. Each agent receives the output of the previous agent and produces input for the next agent. The simplest coordination pattern.

### When to Use
- Workflow has clear stages that must happen in order
- Each stage depends on completion of previous stage
- Task naturally decomposes into pipeline steps
- Predictable, repeatable process

### When NOT to Use
- Stages are independent and could run in parallel
- Need adaptive routing based on intermediate results
- Any stage might need to loop back to previous stages

### Implementation Example

```python
class SequentialPipeline:
    def __init__(self, agents):
        self.agents = agents

    async def execute(self, initial_input):
        current_output = initial_input
        for agent in self.agents:
            current_output = await agent.process(current_output)
        return current_output

# Usage
pipeline = SequentialPipeline([
    ResearchAgent(),
    AnalysisAgent(),
    DraftAgent(),
    ReviewAgent()
])
result = await pipeline.execute({"topic": "AI Safety"})
```

### Variations
- **With Checkpoints:** Save state after each agent for resume/replay
- **With Validation:** Add validation gates between agents
- **With Parallel Stages:** Allow some stages to fan out and merge back

### Observability
Track: stage completion, stage duration, inter-stage data size, failure points.

## Hierarchical Pattern

### Description
A parent agent decomposes work and delegates to specialized child agents. Parent is responsible for task decomposition, delegation, and result aggregation.

### When to Use
- Complex task naturally decomposes into subtasks
- Subtasks require different specializations
- Need centralized coordination and monitoring
- Want to scale by adding more specialized agents

### When NOT to Use
- Task is not decomposable
- Overhead of delegation exceeds benefits
- Need flat peer collaboration without hierarchy

### Implementation Example

```python
class HierarchicalAgent:
    def __init__(self, specialists):
        self.specialists = specialists

    async def execute(self, task):
        # Parent agent plans decomposition
        plan = await self.decompose_task(task)

        # Delegate to specialists
        subtask_results = []
        for subtask in plan.subtasks:
            specialist = self.specialists[subtask.type]
            result = await specialist.execute(subtask)
            subtask_results.append(result)

        # Aggregate results
        return await self.aggregate(subtask_results)

    async def decompose_task(self, task):
        # Parent agent reasons about task decomposition
        prompt = f"""Break down this task into subtasks:
        {task}

        Available specialists: {list(self.specialists.keys())}
        Return JSON plan."""
        return await self.llm.generate(prompt)
```

### Variations
- **Dynamic Delegation:** Parent adapts plan based on subtask results
- **Multi-Level Hierarchy:** Specialists can themselves be hierarchical agents
- **Load Balancing:** Parent distributes work across multiple instances of same specialist

### Common Pitfalls
- **Deep Nesting:** More than 3 levels becomes hard to debug and reason about
- **Micromanagement:** Parent specifying too much detail, limiting specialist autonomy
- **Bottleneck:** Parent becomes single point of failure or performance bottleneck

## Collaborative Pattern

### Description
Multiple peer agents work together on a shared problem without fixed hierarchy. Agents contribute their perspectives and a consensus or synthesis mechanism combines results.

### When to Use
- Problem benefits from diverse expert viewpoints
- No single agent has complete information
- Quality improves with multiple perspectives (e.g., review, evaluation)
- Need checks and balances

### When NOT to Use
- Clear hierarchy exists or is desirable
- Problem has single correct answer
- Coordination overhead exceeds benefits
- Need fast, decisive action

### Implementation Example

```python
class CollaborativeSystem:
    def __init__(self, agents, consensus_fn):
        self.agents = agents
        self.consensus_fn = consensus_fn

    async def solve(self, problem):
        # All agents work on problem independently
        proposals = []
        for agent in self.agents:
            proposal = await agent.propose_solution(problem)
            proposals.append(proposal)

        # Reach consensus
        return await self.consensus_fn(proposals)

# Consensus strategies
async def voting_consensus(proposals):
    # Simple majority vote
    return max(set(proposals), key=proposals.count)

async def synthesis_consensus(proposals):
    # LLM synthesizes proposals into unified solution
    prompt = f"""Given these expert proposals:
    {proposals}

    Synthesize the best elements into a unified solution."""
    return await llm.generate(prompt)
```

### Variations
- **With Debate:** Agents critique each other's proposals iteratively
- **With Facilitator:** Add a non-voting facilitator agent to guide discussion
- **Weighted Voting:** Different agents have different vote weights

### Consensus Mechanisms
- **Majority Vote:** Simple, but may ignore minority insights
- **Synthesis:** Rich output, but expensive and can be unpredictable
- **First-to-N:** Fast, but may miss better solutions
- **Veto-Based:** Any agent can veto unsafe proposals

## Autonomous Pattern

### Description
Agents operate independently with minimal or no coordination. Each agent has its own goals and operates on its own schedule.

### When to Use
- Tasks are truly independent
- Need maximum parallelism and throughput
- Agents monitor different domains
- Loose coupling is desired

### When NOT to Use
- Agents need to share information or coordinate
- Tasks have dependencies
- Need consistent global state
- Resource contention is an issue

### Implementation Example

```python
class AutonomousAgentPool:
    def __init__(self, agents):
        self.agents = agents

    async def run(self):
        # Launch all agents independently
        tasks = [agent.run() for agent in self.agents]
        await asyncio.gather(*tasks)

# Each agent runs its own loop
class MonitoringAgent:
    async def run(self):
        while True:
            status = await self.check_service()
            if status.is_unhealthy():
                await self.alert(status)
            await asyncio.sleep(self.interval)
```

### Coordination Patterns
Even autonomous agents may need minimal coordination:
- **Shared Event Bus:** Publish events, subscribe to relevant ones
- **Shared State Store:** Read/write shared state with optimistic locking
- **Rate Limiting:** Coordinate to stay under global rate limits

## ReAct Pattern

### Description
Agent follows Reason → Act → Observe cycle. Agent reasons about what to do next, executes an action, observes the result, and repeats until task is complete.

### When to Use
- Environment is dynamic or partially observable
- Need adaptive behavior based on feedback
- Can't plan all steps upfront
- Debugging, exploration, or research tasks

### When NOT to Use
- Environment is fully predictable
- Planning overhead is too high
- Need guaranteed completion time
- Token budget is constrained

### Implementation Example

```python
class ReActAgent:
    async def solve(self, task):
        context = {"task": task, "observations": []}

        while not self.is_complete(context):
            # Reason about next action
            thought = await self.reason(context)

            # Execute action
            action = thought.action
            result = await self.execute_action(action)

            # Observe result
            observation = self.observe(result)
            context["observations"].append(observation)

        return self.extract_answer(context)

    async def reason(self, context):
        prompt = f"""Task: {context['task']}

        Previous observations:
        {context['observations']}

        What should I do next?
        Think step-by-step, then specify an action."""
        return await self.llm.generate(prompt)
```

### Variations
- **With Memory:** Maintain long-term memory of successful strategies
- **With Planning:** Create rough plan but adapt based on observations
- **With Reflection:** Periodically reflect on strategy effectiveness

## Plan-Execute Pattern

### Description
Agent creates a complete execution plan upfront, then executes all steps. Planning and execution are separate phases.

### When to Use
- Environment is predictable and stable
- Planning cost is justified (complex dependencies, resource optimization)
- Need to validate plan before execution
- Can estimate all required steps in advance

### When NOT to Use
- Environment changes during execution
- Can't predict what steps will be needed
- Planning overhead exceeds execution savings
- Need to start execution quickly

### Implementation Example

```python
class PlanExecuteAgent:
    async def solve(self, task):
        # Planning phase
        plan = await self.create_plan(task)

        # Optional: validate plan
        if not self.validate_plan(plan):
            raise ValueError("Invalid plan")

        # Execution phase
        results = []
        for step in plan.steps:
            result = await self.execute_step(step)
            results.append(result)

        return self.aggregate_results(results)

    async def create_plan(self, task):
        prompt = f"""Create a detailed execution plan for:
        {task}

        Available actions: {self.available_actions}
        Return JSON with steps."""
        return await self.llm.generate(prompt)
```

### Planning Strategies
- **Forward Planning:** Start from initial state, plan steps to goal
- **Backward Planning:** Start from goal, plan steps back to initial state
- **Hierarchical Planning:** Plan high-level strategy, then detailed tactics

## Reflection Pattern

### Description
Agent reviews its own outputs and iteratively improves them through self-critique and refinement.

### When to Use
- Quality matters more than speed
- Initial output is expected to be imperfect
- Cost of iteration is acceptable
- Clear quality criteria exist

### When NOT to Use
- Latency is critical
- Token budget is tight
- Output quality is already sufficient
- No clear improvement criteria

### Implementation Example

```python
class ReflectiveAgent:
    async def produce(self, task, max_iterations=3):
        output = await self.initial_draft(task)

        for i in range(max_iterations):
            critique = await self.critique(output, task)

            if critique.is_satisfactory:
                break

            output = await self.refine(output, critique)

        return output

    async def critique(self, output, original_task):
        prompt = f"""Review this output:
        {output}

        Original task: {original_task}

        Does it fully satisfy requirements?
        What could be improved?"""
        return await self.llm.generate(prompt)
```

### Variations
- **With External Critic:** Separate critic agent reviews producer's output
- **With Multiple Critics:** Different critics focus on different quality dimensions
- **With Human Feedback:** Human reviews and guides refinement

### Termination Conditions
- **Fixed Iterations:** Stop after N iterations
- **Quality Threshold:** Stop when quality score exceeds threshold
- **Diminishing Returns:** Stop when improvements become marginal
- **Token Budget:** Stop when token budget is exhausted
