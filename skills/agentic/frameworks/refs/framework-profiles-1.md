# Framework Detailed Profiles

In-depth analysis of top 6 agentic frameworks.

## 1. Anthropic Agent Developer Kit (ADK)

### Overview
TypeScript framework optimized for building production Claude applications with delegated workflows.

### Architecture
- Agents can delegate to sub-agents
- Context automatically managed
- TypeScript-first with excellent type safety

### Code Example
```typescript
import { Agent } from '@anthropic-ai/agent-developer-kit';

const agent = new Agent({
  name: 'code-reviewer',
  instructions: 'You review code for security issues.',
  tools: [securityScanTool, lintTool],
  model: 'claude-opus-4-6'
});

const result = await agent.run({
  input: 'Review this code: ...'
});
```

### Strengths
- **Production-Ready:** Built-in error handling, retries, timeouts
- **Type Safety:** Full TypeScript support
- **Context Management:** Automatic context window management
- **Delegated Workflows:** Agents can call other agents naturally
- **Observability:** Built-in integration with Braintrust

### Weaknesses
- **Claude-Only:** No multi-provider support
- **TypeScript-Only:** No Python version
- **Newer Framework:** Smaller community

### Best Use Cases
- Production Claude applications
- TypeScript/Node.js projects
- Complex agent hierarchies
- Enterprise applications requiring type safety

### Not Ideal For
- Python-first teams
- Need for multiple LLM providers
- Quick prototyping (if unfamiliar with TypeScript)

### Pricing Considerations
- Framework is free
- Only pay for Claude API usage
- No framework overhead costs

### Learning Resources
- Official docs: anthropic.com/adk
- Examples: github.com/anthropics/adk-examples
- Discord: Anthropic Developer Discord

## 2. LangGraph

### Overview
Python framework for building stateful multi-agent applications using a graph abstraction.

### Architecture
- Workflow defined as directed graph
- Nodes are agents/functions
- Edges are control flow
- Built-in state management and checkpointing

### Code Example
```python
from langgraph.graph import StateGraph

workflow = StateGraph(state_schema)

workflow.add_node("researcher", research_agent)
workflow.add_node("writer", writer_agent)
workflow.add_node("reviewer", review_agent)

workflow.add_edge("researcher", "writer")
workflow.add_conditional_edge("reviewer", should_revise, {
    True: "writer",
    False: END
})

app = workflow.compile(checkpointer=MemorySaver())
result = app.invoke({"topic": "AI Safety"})
```

### Strengths
- **State Management:** Best-in-class state management
- **Checkpointing:** Built-in persistence for long-running workflows
- **Human-in-the-Loop:** Native support for approval gates
- **Time-Travel:** Debug by replaying state
- **Multi-Provider:** Works with any LLM

### Weaknesses
- **Learning Curve:** Graph abstraction takes time to learn
- **Verbosity:** More boilerplate than simpler frameworks
- **Complexity:** Can be overkill for simple use cases

### Best Use Cases
- Complex workflows with branches and loops
- Long-running processes needing checkpoints
- Applications requiring human approval gates
- State-heavy applications

### Not Ideal For
- Simple linear workflows
- Quick prototypes
- Teams new to graph abstractions

### Pricing Considerations
- LangSmith (observability): ~$99-$399/month
- Framework itself is free
- Pay for LLM API costs

### Learning Resources
- Official docs: python.langchain.com/docs/langgraph
- Course: langchain.com/academy
- Examples: github.com/langchain-ai/langgraph-examples

## 3. CrewAI

### Overview
Python framework for orchestrating role-based AI agent teams with clear task delegation.

### Architecture
- Agents have roles (researcher, writer, etc.)
- Tasks assigned to agents
- Hierarchical or sequential processes
- Simple, intuitive API

### Code Example
```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role='Researcher',
    goal='Find accurate information',
    tools=[search_tool, scrape_tool]
)

writer = Agent(
    role='Writer',
    goal='Write engaging content',
    tools=[grammar_tool]
)

research_task = Task(
    description='Research AI safety',
    agent=researcher
)

write_task = Task(
    description='Write article on findings',
    agent=writer,
    dependencies=[research_task]
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=sequential
)

result = crew.kickoff()
```

### Strengths
- **Intuitive API:** Easy to learn and use
- **Role-Based:** Natural abstraction for team workflows
- **Quick Start:** Fastest time to first agent
- **Good Docs:** Clear documentation and examples

### Weaknesses
- **Less Mature:** Newer than LangChain/LangGraph
- **Limited State:** Basic state management
- **Fewer Features:** Less production-ready than ADK/LangGraph

### Best Use Cases
- Team-based workflows (research → write → review)
- Quick prototyping
- Straightforward delegation patterns
- Educational projects

### Not Ideal For
- Complex state management needs
- Production critical systems (yet)
- Applications needing advanced orchestration

### Pricing Considerations
- Framework is free
- Pay for LLM API costs
- No additional services required

### Learning Resources
- Official docs: docs.crewai.com
- Examples: github.com/joaomdmoura/crewAI-examples
- Discord: CrewAI Discord
