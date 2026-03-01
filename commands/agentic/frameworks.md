---
description: Research, compare, and select agentic frameworks with interactive guidance and latest updates
argument-hint: "[--compare fw1,fw2,...] [--language python|typescript] [--use-case TYPE]"
---

# /wicked-garden:agentic:frameworks

Interactive framework research and comparison tool. Get recommendations based on your requirements, compare frameworks side-by-side, and access the latest ecosystem updates.

## Instructions

### 1. Parse Arguments

Extract parameters:
- `--compare fw1,fw2,...`: Compare specific frameworks (e.g., `--compare langchain,crewai,autogen`)
- `--language LANG`: Filter by language (python, typescript, java, go)
- `--use-case TYPE`: Filter by use case (research, customer-support, code-generation, data-analysis, etc.)

### 2. Spawn Framework Researcher

```
Task(
  subagent_type="wicked-garden:agentic:framework-researcher",
  prompt="Mode: {comparison | selection | overview}\n\nParameters:\n- Compare: {framework_list if --compare}\n- Language: {language if --language}\n- Use case: {use_case if --use-case}\n\nInstructions:\nLoad skill wicked-garden:agentic:frameworks\n\n{Behavior based on mode}"
)
```

### 3. Framework Comparison Mode

If `--compare` specified:

```
Task(
  subagent_type="wicked-garden:agentic:framework-researcher",
  prompt="Mode: comparison\nFrameworks: {fw1, fw2, fw3}\n\nInstructions:\nFor each framework, research:\n1. Core architecture and patterns\n2. Strengths and weaknesses\n3. Ecosystem and community\n4. Learning curve\n5. Performance characteristics\n6. Cost implications\n7. Production readiness\n\nUse WebSearch to get latest information.\n\nPresent comparison table and recommendation."
)
```

Framework researcher produces:

```markdown
# Framework Comparison: {fw1} vs {fw2} vs {fw3}

## Quick Comparison

| Aspect | {fw1} | {fw2} | {fw3} |
|--------|-------|-------|-------|
| **Language** | {lang} | {lang} | {lang} |
| **Pattern Focus** | {pattern} | {pattern} | {pattern} |
| **Learning Curve** | {level} | {level} | {level} |
| **Community** | {size} | {size} | {size} |
| **Production Ready** | {yes/no} | {yes/no} | {yes/no} |
| **Best For** | {use_case} | {use_case} | {use_case} |

## Detailed Comparison

### Architecture

**{fw1}**: {architecture description}

**{fw2}**: {architecture description}

**{fw3}**: {architecture description}

### Strengths & Weaknesses

#### {fw1}
**Strengths**:
- {strength}

**Weaknesses**:
- {weakness}

#### {fw2}
**Strengths**:
- {strength}

**Weaknesses**:
- {weakness}

### Code Comparison

**{fw1}** - Simple agent example:
```python
{code example}
```

**{fw2}** - Same task:
```python
{code example}
```

### Performance

| Metric | {fw1} | {fw2} | {fw3} |
|--------|-------|-------|-------|
| **Avg Latency** | {latency} | {latency} | {latency} |
| **Token Efficiency** | {efficiency} | {efficiency} | {efficiency} |
| **Cost** | {cost} | {cost} | {cost} |

### Ecosystem

**{fw1}**:
- Integrations: {count}
- Plugins: {count}
- Community: {size}

**{fw2}**:
- Integrations: {count}
- Plugins: {count}
- Community: {size}

### Latest Updates (2026)

**{fw1}**:
- {recent feature or update}

**{fw2}**:
- {recent feature or update}

## Recommendation

**For your use case**: {recommendation with reasoning}

**Alternative**: {when to use alternative}

## Migration Path

If switching from {fw1} to {fw2}:
1. {migration step}

Estimated effort: {timeframe}

## Decision Matrix

| If you need... | Choose |
|----------------|--------|
| Maximum flexibility | {framework} |
| Rapid prototyping | {framework} |
| Multi-agent teams | {framework} |
| Production stability | {framework} |
| Lowest cost | {framework} |

## Next Steps

1. {immediate action}
2. {follow-up}
```

### 4. Interactive Selection Mode

If no `--compare` but filters provided:

```
Task(
  subagent_type="wicked-garden:agentic:framework-researcher",
  prompt="Mode: selection\n\nFilters:\n- Language: {language}\n- Use case: {use_case}\n\nInstructions:\nBased on filters, recommend top 3-5 frameworks.\n\nFor each, provide:\n1. Name and description\n2. Why it fits the criteria\n3. Quick start guide\n4. When to choose it vs alternatives\n\nFormat as decision guide."
)
```

### 5. Selection Wizard Mode

If no arguments provided, run interactive wizard:

```
Task(
  subagent_type="wicked-garden:agentic:framework-researcher",
  prompt="Mode: wizard\n\nInstructions:\nAsk user 4-5 questions to understand requirements:\n1. Language preference: Python, TypeScript, other?\n2. Use case: What are you building?\n3. Experience level: Beginner, intermediate, expert?\n4. Scale: Prototype, production, enterprise?\n5. Priority: Speed of development, flexibility, cost, performance?\n\nBased on answers, recommend framework with rationale."
)
```

Wizard interaction:

```markdown
I'll help you select the right agentic framework. A few quick questions:

## 1. Language Preference
What language are you using?
- Python
- TypeScript/JavaScript
- Java
- Go
- Other

## 2. Use Case
What are you building?
- Research/analysis assistant
- Customer support bot
- Code generation tool
- Data processing pipeline
- Multi-agent simulation
- Other

## 3. Experience Level
How familiar are you with LLM applications?
- Beginner (first agent project)
- Intermediate (built 2-3 projects)
- Expert (production experience)

## 4. Scale
What's your target?
- Prototype/MVP
- Production (1k-10k req/day)
- Enterprise (>10k req/day)

## 5. Priority
What matters most?
- Speed of development
- Flexibility/customization
- Cost optimization
- Performance/latency
- Community/support
```

After user answers:

```markdown
## Recommendation: {Framework}

Based on your answers:
- Language: {language}
- Use case: {use_case}
- Experience: {level}
- Scale: {scale}
- Priority: {priority}

I recommend **{framework}** because:
1. {reason based on requirements}
2. {reason}
3. {reason}

### Quick Start

1. Install:
```bash
{installation command}
```

2. Hello World:
```python
{minimal example}
```

3. Your use case pattern:
```python
{relevant example for their use case}
```

### Resources
- Documentation: {url}
- Examples: {url}
- Community: {url}

### Alternative
If {condition}, consider **{alternative_framework}** instead.

Would you like me to:
- Compare this with another framework? `/wicked-garden:agentic:frameworks --compare`
- Design an architecture using this framework? `/wicked-garden:agentic:design`
```

### 6. Use WebSearch for Latest Info

For any framework research, use WebSearch to get current information:

```
WebSearch: "{framework_name} 2026 latest features"
WebSearch: "{framework_name} production best practices"
WebSearch: "{framework_name} vs {alternative} comparison"
```

Extract:
- Latest version and release notes
- New features and improvements
- Community sentiment
- Production case studies

### 7. Include Getting Started

For recommended frameworks, provide quick start:

```markdown
## Getting Started with {Framework}

### Installation
```bash
pip install {framework}
# or
npm install {framework}
```

### Minimal Example
```python
{5-10 line hello world}
```

### Common Patterns

#### Sequential Workflow
```python
{example}
```

#### Multi-Agent Team
```python
{example}
```

#### Tool Integration
```python
{example}
```

### Configuration

Required environment variables:
```bash
export OPENAI_API_KEY="..."
export {OTHER_VARS}="..."
```

### Best Practices
1. {practice}
2. {practice}

### Debugging
```python
{how to enable debug logging}
```

### Resources
- Docs: {url}
- Examples: {url}
- Discord/Slack: {url}
```

## Examples

### Compare Specific Frameworks

```
User: /wicked-garden:agentic:frameworks --compare langchain,crewai,autogen

Claude: I'll compare LangChain, CrewAI, and AutoGen.

[Uses WebSearch for latest 2026 updates]

# Framework Comparison: LangChain vs CrewAI vs AutoGen

## Quick Comparison

| Aspect | LangChain | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| **Language** | Python, TS | Python | Python |
| **Pattern Focus** | Flexible chains | Agent teams | Conversations |
| **Learning Curve** | Medium | Low | Medium |
| **Community** | Very Large | Growing | Large |
| **Production Ready** | Yes | Yes | Yes |
| **Best For** | Custom workflows | Collaborative agents | Multi-agent chat |

## Detailed Comparison

### Architecture

**LangChain**: Component-based, LCEL (LangChain Expression Language) for composing chains. LangGraph for stateful workflows.

**CrewAI**: Role-based agents with built-in collaboration patterns. Hierarchical and sequential execution.

**AutoGen**: Conversation-driven, agents communicate through messages. Supports code execution and human-in-the-loop.

[Full comparison table...]

### Code Comparison - Research Task

**LangChain**:
```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

llm = ChatOpenAI(model="gpt-4")
agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

result = executor.invoke({"input": "Research AI safety"})
```

**CrewAI**:
```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role="Researcher",
    goal="Find accurate information",
    tools=[search_tool]
)

task = Task(description="Research AI safety", agent=researcher)
crew = Crew(agents=[researcher], tasks=[task])

result = crew.kickoff()
```

**AutoGen**:
```python
from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent("assistant", llm_config={"model": "gpt-4"})
user = UserProxyAgent("user", code_execution_config={"work_dir": "coding"})

user.initiate_chat(assistant, message="Research AI safety")
```

## Recommendation

**For rapid prototyping of agent teams**: Use **CrewAI**
- Clean API, built-in patterns, fast to start
- Best for hierarchical/collaborative workflows

**For maximum flexibility**: Use **LangChain**
- Most mature ecosystem, extensive integrations
- LangGraph for complex stateful workflows

**For conversation-based agents**: Use **AutoGen**
- Natural multi-agent dialogues
- Built-in code execution and human oversight

## Next Steps
Would you like me to design an architecture using one of these? Run `/wicked-garden:agentic:design`
```

### Filter by Language and Use Case

```
User: /wicked-garden:agentic:frameworks --language typescript --use-case customer-support

Claude: I'll find TypeScript frameworks suitable for customer support.

[Searches and filters frameworks]

# TypeScript Frameworks for Customer Support

## Top Recommendations

### 1. LangChain.js
**Best for**: Production-ready customer support with extensive integrations

**Why**:
- Mature TypeScript support
- Built-in RAG for knowledge bases
- Vercel AI SDK integration
- Active community

**Quick Start**:
```typescript
import { ChatOpenAI } from "@langchain/openai";
import { AgentExecutor, createOpenAIToolsAgent } from "langchain/agents";

const llm = new ChatOpenAI({ temperature: 0 });
const agent = await createOpenAIToolsAgent({ llm, tools, prompt });
const executor = new AgentExecutor({ agent, tools });

const result = await executor.invoke({
  input: "Customer wants to return an item"
});
```

### 2. Vercel AI SDK
**Best for**: Next.js applications, streaming responses

**Why**:
- First-class TypeScript support
- Built-in UI components
- Streaming by default (great for chat)
- Excellent Next.js integration

**Quick Start**:
```typescript
import { openai } from '@ai-sdk/openai';
import { generateText } from 'ai';

const { text } = await generateText({
  model: openai('gpt-4'),
  messages: [
    { role: 'system', content: 'You are a helpful support agent' },
    { role: 'user', content: 'I need help with my order' }
  ],
});
```

### 3. Semantic Kernel (TypeScript)
**Best for**: Microsoft ecosystem, enterprise support

**Why**:
- Enterprise-ready
- Good Azure OpenAI integration
- Planning and memory built-in

## Comparison

| Feature | LangChain.js | Vercel AI SDK | Semantic Kernel |
|---------|-------------|---------------|-----------------|
| Agent patterns | ✅ Rich | ⚠️ Basic | ✅ Good |
| Streaming | ✅ | ✅ Excellent | ✅ |
| UI components | ❌ | ✅ | ❌ |
| Tool calling | ✅ | ✅ | ✅ |
| Memory | ✅ | ⚠️ Manual | ✅ |

## Recommendation

**For your customer support use case**: **LangChain.js**

Why:
1. Rich agent patterns for intent routing
2. Built-in memory for conversation history
3. Easy integration with ticketing systems
4. Production-ready with strong TypeScript types

**Alternative**: If building in Next.js, consider **Vercel AI SDK** for better DX and streaming UX.

Would you like me to design a customer support architecture? `/wicked-garden:agentic:design`
```

### Interactive Selection Wizard

```
User: /wicked-garden:agentic:frameworks

Claude: I'll help you select the right agentic framework. A few quick questions:

## 1. Language Preference
What language are you using?
- Python
- TypeScript/JavaScript
- Java
- Go
- Other

User: Python

Claude: ## 2. Use Case
What are you building?
- Research/analysis assistant
- Customer support bot
- Code generation tool
- Data processing pipeline
- Multi-agent simulation
- Other

User: Research assistant that can search papers, extract key points, and generate summaries

Claude: ## 3. Experience Level
How familiar are you with LLM applications?
- Beginner (first agent project)
- Intermediate (built 2-3 projects)
- Expert (production experience)

User: Intermediate

Claude: ## 4. Scale
What's your target?
- Prototype/MVP
- Production (1k-10k req/day)
- Enterprise (>10k req/day)

User: Prototype for now, production later

Claude: ## 5. Priority
What matters most?
- Speed of development
- Flexibility/customization
- Cost optimization
- Performance/latency
- Community/support

User: Speed of development, but need flexibility for later

Claude:

## Recommendation: LangGraph

Based on your answers:
- Language: Python ✓
- Use case: Research assistant with multiple steps
- Experience: Intermediate
- Scale: Prototype → Production
- Priority: Speed + Flexibility

I recommend **LangGraph** (part of LangChain ecosystem) because:

1. **Perfect for research workflows**: Your research → extract → summarize flow is a natural graph
2. **Speed of development**: High-level abstractions for common patterns
3. **Flexibility**: Can customize any part as you scale
4. **Production-ready**: Used by companies like Elastic, Robocorp

### Quick Start

1. Install:
```bash
pip install langgraph langchain-openai
```

2. Research Assistant Example:
```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# Define workflow states
class ResearchState(TypedDict):
    query: str
    papers: list
    key_points: list
    summary: str

# Build graph
workflow = StateGraph(ResearchState)

workflow.add_node("search", search_papers)
workflow.add_node("extract", extract_key_points)
workflow.add_node("summarize", generate_summary)

workflow.add_edge("search", "extract")
workflow.add_edge("extract", "summarize")
workflow.add_edge("summarize", END)

workflow.set_entry_point("search")

app = workflow.compile()

# Run
result = app.invoke({"query": "AI safety research"})
```

### Why LangGraph vs CrewAI?

CrewAI is simpler but less flexible. For research workflows with complex state, LangGraph's graph structure is clearer.

### Resources
- Docs: https://langchain-ai.github.io/langgraph/
- Examples: https://github.com/langchain-ai/langgraph/tree/main/examples
- Discord: https://discord.gg/langchain

### Next Steps
Would you like me to design a detailed architecture for your research assistant? Run:
```
/wicked-garden:agentic:design "Research assistant that searches papers, extracts findings, and generates summaries"
```
```
