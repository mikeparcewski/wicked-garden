# Framework Migration Patterns

Common migration paths between agentic frameworks with strategies and gotchas.

## Why Migrate?

Common reasons for framework migration:
1. **Outgrowing current framework** (prototype → production)
2. **Better state management** (need checkpointing, workflows)
3. **Production requirements** (observability, error handling)
4. **Team preferences** (language, ecosystem)
5. **Cost optimization** (framework overhead, licensing)
6. **Feature needs** (specific capabilities missing)

## General Migration Strategy

### Phase 1: Assessment
1. Document current architecture
2. List all agents and their roles
3. Map dependencies and workflows
4. Identify framework-specific features in use
5. Estimate migration effort

### Phase 2: Planning
1. Choose target framework
2. Design target architecture
3. Identify abstraction layers
4. Plan incremental migration path
5. Define success criteria

### Phase 3: Implementation
1. Set up new framework
2. Build adapters/bridges if needed
3. Migrate one agent/workflow at a time
4. Run both systems in parallel (if possible)
5. Validate equivalence

### Phase 4: Cutover
1. Route production traffic gradually
2. Monitor metrics closely
3. Keep rollback plan ready
4. Complete migration
5. Remove old framework

## Common Migration Paths

### 1. Custom Code → Framework

**Scenario:** Built agents from scratch, want framework benefits.

**Motivation:**
- Need production-ready features (observability, error handling)
- Want faster development
- Reduce maintenance burden

**Strategy:**

**Step 1:** Identify Abstraction Points
```python
# Current custom code
class CustomAgent:
    def __init__(self, llm_client, tools):
        self.llm = llm_client
        self.tools = tools

    async def process(self, input):
        # Custom orchestration logic
        pass
```

**Step 2:** Choose Framework Based on Patterns
- Sequential workflows → Pydantic AI, CrewAI
- Complex state → LangGraph
- TypeScript codebase → ADK
- RAG-heavy → LlamaIndex

**Step 3:** Incremental Migration
```python
# Wrap custom agent in framework
from crewai import Agent

def custom_tool_wrapper(input):
    return custom_agent.process(input)

framework_agent = Agent(
    role="Custom Agent",
    tools=[custom_tool_wrapper]
)
```

**Gotchas:**
- Framework may have different error handling semantics
- State management may need refactoring
- Tool signatures may need adaptation

**Effort:** Medium-High (2-4 weeks for typical system)

### 2. LangChain → LangGraph

**Scenario:** Using LangChain chains, need better state management.

**Motivation:**
- Need checkpointing for long workflows
- Want human-in-the-loop approval gates
- Better error recovery
- More complex control flow

**Strategy:**

**Step 1:** Map Chains to Graphs
```python
# Before: LangChain
from langchain.chains import SequentialChain

chain = SequentialChain(
    chains=[research_chain, analyze_chain, write_chain]
)

# After: LangGraph
from langgraph.graph import StateGraph

workflow = StateGraph(StateSchema)
workflow.add_node("research", research_agent)
workflow.add_node("analyze", analyze_agent)
workflow.add_node("write", write_agent)
workflow.add_edge("research", "analyze")
workflow.add_edge("analyze", "write")
app = workflow.compile()
```

**Step 2:** Add State Schema
```python
from typing import TypedDict

class WorkflowState(TypedDict):
    research_results: str
    analysis: str
    draft: str
    revisions: int
```

**Step 3:** Add Checkpointing
```python
from langgraph.checkpoint import MemorySaver

app = workflow.compile(checkpointer=MemorySaver())
```

**Gotchas:**
- Need to define state schema (wasn't explicit in LangChain)
- Different error handling model
- Checkpointing changes deployment (need persistence)

**Effort:** Low-Medium (1-2 weeks)

### 3. CrewAI → LangGraph

**Scenario:** Using CrewAI for simple workflows, need more control.

**Motivation:**
- Need conditional branching
- Want fine-grained state management
- Need to handle complex dependencies

**Strategy:**

**Step 1:** Map Agents and Tasks
```python
# Before: CrewAI
researcher = Agent(role='Researcher', tools=[search])
writer = Agent(role='Writer', tools=[grammar])

research_task = Task(description='Research topic', agent=researcher)
write_task = Task(description='Write article', agent=writer)

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task])

# After: LangGraph
def research_node(state):
    result = researcher.run(state['topic'])
    return {"research": result}

def write_node(state):
    result = writer.run(state['research'])
    return {"article": result}

workflow = StateGraph(StateSchema)
workflow.add_node("research", research_node)
workflow.add_node("write", write_node)
workflow.add_edge("research", "write")
```

**Step 2:** Add Conditional Logic (New Capability)
```python
def should_revise(state):
    if state['revisions'] < 3 and not state['approved']:
        return "write"
    return END

workflow.add_conditional_edge("review", should_revise, {
    "write": "write",
    END: END
})
```

**Gotchas:**
- CrewAI's process abstraction vs LangGraph's explicit graph
- Tool integration may need adaptation
- Different agent initialization patterns

**Effort:** Medium (2-3 weeks)

### 4. AutoGen → LangGraph

**Scenario:** Using AutoGen for conversations, need structured workflows.

**Motivation:**
- Conversations becoming unmanageable
- Need deterministic control flow
- Want state checkpointing

**Strategy:**

**Step 1:** Identify Conversation Patterns
```python
# Before: AutoGen conversation
user_proxy.initiate_chat(assistant, message="Task description")

# After: Structured workflow
def assistant_node(state):
    response = assistant.run(state['task'])
    return {"response": response}
```

**Step 2:** Replace Group Chat with Graph
```python
# Before: AutoGen group chat
group_chat = GroupChat(
    agents=[agent1, agent2, agent3],
    messages=[],
    max_round=10
)

# After: LangGraph with explicit orchestration
workflow = StateGraph(StateSchema)
workflow.add_node("agent1", agent1_node)
workflow.add_node("agent2", agent2_node)
workflow.add_node("agent3", agent3_node)

# Define explicit conversation flow
workflow.add_edge("agent1", "agent2")
workflow.add_conditional_edge("agent2", should_continue, {
    True: "agent3",
    False: END
})
```

**Gotchas:**
- Lose flexibility of open conversations
- Need to define all conversation paths
- Different mental model (graph vs messages)

**Effort:** Medium-High (3-4 weeks)

### 5. Python Framework → ADK (TypeScript)

**Scenario:** Migrating Python codebase to TypeScript.

**Motivation:**
- Team transitioning to TypeScript
- Want ADK's production features
- Building on Claude exclusively

**Strategy:**

**Step 1:** Port Agent Logic
```python
# Before: Python (any framework)
class ReviewAgent:
    def review(self, code):
        return llm.generate(f"Review: {code}")

# After: TypeScript (ADK)
const reviewAgent = new Agent({
    name: 'reviewer',
    instructions: 'You review code.',
    model: 'claude-opus-4-6'
});
```

**Step 2:** Port Tools
```python
# Before: Python
def analyze_code(code: str) -> dict:
    return {"issues": [...]}

# After: TypeScript
const analyzeCodeTool = {
    name: 'analyze_code',
    description: 'Analyze code for issues',
    parameters: {
        type: 'object',
        properties: {
            code: { type: 'string' }
        }
    },
    handler: async (params: { code: string }) => {
        return { issues: [...] };
    }
};
```

**Gotchas:**
- Async patterns differ (promises vs async/await)
- Type systems differ
- Tool definitions have different formats
- Testing frameworks differ

**Effort:** High (4-8 weeks for large codebase)

### 6. Single-Provider → Multi-Provider

**Scenario:** Locked into one LLM provider, want flexibility.

**Motivation:**
- Want to A/B test providers
- Cost optimization
- Failover capability

**Strategy:**

**Step 1:** Abstract LLM Client
```python
# Before: Direct provider calls
response = anthropic.messages.create(...)

# After: Abstracted
class LLMClient:
    def generate(self, messages, model):
        if model.startswith('claude'):
            return self._call_anthropic(messages, model)
        elif model.startswith('gpt'):
            return self._call_openai(messages, model)
```

**Step 2:** Use Multi-Provider Framework
```python
# LangChain/LangGraph support multiple providers
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

llm = ChatAnthropic(model="claude-opus-4")
# Or
llm = ChatOpenAI(model="gpt-4-turbo")
```

**Gotchas:**
- Different providers have different features
- Output formats may vary
- Cost per token differs
- Rate limits differ

**Effort:** Low-Medium (1-2 weeks)

## Migration Testing Strategy

### 1. Equivalence Testing

Run both old and new system in parallel, compare outputs:

```python
async def equivalence_test(input):
    old_result = await old_agent.process(input)
    new_result = await new_agent.process(input)

    similarity = compare_outputs(old_result, new_result)
    if similarity < 0.9:
        log_discrepancy(input, old_result, new_result)

    return similarity
```

### 2. Shadow Testing

Route production traffic to both, use old result:

```python
async def shadow_process(input):
    # Production (old)
    result = await old_agent.process(input)

    # Shadow (new) - don't await
    asyncio.create_task(new_agent.process(input))

    return result
```

### 3. Gradual Rollout

Slowly increase traffic to new system:

```python
async def gradual_rollout(input, percentage=10):
    if random.random() * 100 < percentage:
        return await new_agent.process(input)
    else:
        return await old_agent.process(input)
```

## Rollback Planning

Always have a rollback plan:

1. **Feature Flags:** Quick disable of new system
2. **Version Routing:** Route to old version instantly
3. **Database Compatibility:** Ensure schemas compatible
4. **Monitoring:** Alert on regressions immediately

```python
class FeatureFlag:
    def __init__(self):
        self.use_new_agent = False

    async def process(self, input):
        if self.use_new_agent:
            return await new_agent.process(input)
        else:
            return await old_agent.process(input)
```

## Migration Effort Estimates

| Migration Path | Typical Effort | Risk Level |
|----------------|----------------|------------|
| Custom → Framework | 2-4 weeks | Medium |
| LangChain → LangGraph | 1-2 weeks | Low |
| CrewAI → LangGraph | 2-3 weeks | Medium |
| AutoGen → LangGraph | 3-4 weeks | Medium |
| Python → TypeScript (ADK) | 4-8 weeks | High |
| Single → Multi-Provider | 1-2 weeks | Low |

## Post-Migration Checklist

- [ ] All tests passing
- [ ] Equivalence testing shows >95% similarity
- [ ] Performance metrics maintained or improved
- [ ] Cost per request unchanged or improved
- [ ] Monitoring and alerting migrated
- [ ] Documentation updated
- [ ] Team trained on new framework
- [ ] Old code removed or archived
- [ ] Rollback plan tested

## When NOT to Migrate

Don't migrate if:
- Current system is stable and meets needs
- Migration cost exceeds benefits
- Team lacks expertise in target framework
- No clear improvement in capabilities
- Close to sunsetting the product
- Migration would delay critical features
