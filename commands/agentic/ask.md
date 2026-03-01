---
description: Ask questions about agentic patterns, frameworks, architectures, and best practices
argument-hint: <question>
---

# /wicked-garden:agentic:ask

Get expert answers about agentic concepts, design patterns, framework selection, safety considerations, and optimization strategies.

## Instructions

### 1. Classify Question Topic

Analyze the user's question to determine the primary topic:

- **Architecture**: System design, patterns, layers, control flow
- **Safety**: Security, trust, human-in-the-loop, compliance, risk
- **Performance**: Optimization, cost, latency, token usage
- **Frameworks**: Tool selection, comparison, best practices
- **Patterns**: Design patterns, anti-patterns, use cases
- **Implementation**: Code examples, debugging, troubleshooting

### 2. Route to Appropriate Agent

Based on topic classification, spawn the relevant expert agent:

#### Architecture Questions
```
Task: wicked-garden:agentic:architect

Question: {user_question}

Instructions:
Load skills:
- wicked-garden:agentic:five-layer-architecture
- wicked-garden:agentic:agentic-patterns

Answer the question with:
1. Clear explanation
2. Relevant patterns or principles
3. Concrete example
4. When to apply vs avoid
5. Trade-offs to consider

Keep answer concise but thorough.
```

#### Safety Questions
```
Task: wicked-garden:agentic:safety-reviewer

Question: {user_question}

Instructions:
Load skill wicked-garden:agentic:trust-and-safety

Answer focusing on:
1. Security implications
2. Risk assessment
3. Mitigation strategies
4. Compliance considerations
5. Best practices

Provide actionable guidance.
```

#### Performance Questions
```
Task: wicked-garden:agentic:performance-analyst

Question: {user_question}

Instructions:
Load skill wicked-garden:agentic:agentic-patterns

Answer covering:
1. Performance impact
2. Optimization techniques
3. Cost implications
4. Benchmarking approach
5. Trade-offs

Include quantitative estimates where possible.
```

#### Framework Questions
```
Task: wicked-garden:agentic:framework-researcher

Question: {user_question}

Instructions:
Load skill wicked-garden:agentic:frameworks

Provide:
1. Framework overview
2. Use case fit
3. Strengths and weaknesses
4. Ecosystem and community
5. Getting started guidance

Use WebSearch for latest information if needed.
```

#### Pattern Questions
```
Task: wicked-garden:agentic:pattern-advisor

Question: {user_question}

Instructions:
Load skill wicked-garden:agentic:agentic-patterns

Explain:
1. Pattern definition
2. When to use
3. Implementation approach
4. Common pitfalls
5. Real-world examples

Compare with related patterns.
```

### 3. Load Relevant Skills

Agent loads appropriate skills based on question context:

- **wicked-garden:agentic:five-layer-architecture**: For architecture questions
- **wicked-garden:agentic:agentic-patterns**: For pattern and performance questions
- **wicked-garden:agentic:trust-and-safety**: For safety and security questions
- **wicked-garden:agentic:frameworks**: For framework selection and comparison
- **wicked-garden:agentic:maturity-model**: For readiness and capability assessment

### 4. Provide Answer

Structure answer as:

```markdown
## {Question}

### Answer

{Clear, concise explanation}

### Example

{Concrete code or architecture example}

### When to Use

{Appropriate scenarios}

### When to Avoid

{Inappropriate scenarios or anti-patterns}

### Trade-offs

- **Pro**: {benefit}
- **Con**: {limitation}

### Related Concepts

- {related pattern or concept}

### Further Reading

- {resource or skill to explore}
```

### 5. Offer Follow-up

If the answer suggests next steps, offer to help:
- Run a review: `/wicked-garden:agentic:review`
- Design an architecture: `/wicked-garden:agentic:design`
- Compare frameworks: `/wicked-garden:agentic:frameworks --compare`
- Run safety audit: `/wicked-garden:agentic:audit`

## Examples

### Architecture Question

```
User: /wicked-garden:agentic:ask What's the difference between hierarchical and sequential patterns?

Claude: [Routes to architect agent]

## What's the difference between hierarchical and sequential patterns?

### Answer

**Sequential Pattern**: Agents execute in a linear chain, where each agent's output becomes the next agent's input. Think of it as a pipeline.

**Hierarchical Pattern**: A coordinator agent delegates tasks to specialized sub-agents and synthesizes their results. Think of it as a manager with a team.

### Example

**Sequential Pattern**:
```python
# Research workflow: search → extract → summarize
result = (
    search_agent(query)
    | extract_agent()
    | summarize_agent()
)
```

**Hierarchical Pattern**:
```python
# Coordinator delegates to specialists
coordinator = Agent(
    role="Research Coordinator",
    delegates_to=[search_agent, extract_agent, summarize_agent]
)

result = coordinator.run(query)  # Coordinator orchestrates sub-agents
```

### When to Use Sequential

- Simple, linear workflows
- Clear dependencies between steps
- Each step needs previous step's full output
- Example: ETL pipelines, document processing

### When to Use Hierarchical

- Complex workflows with multiple independent tasks
- Parallel execution needed
- Different specialists required
- Example: research assistants, multi-source analysis

### Trade-offs

**Sequential**:
- **Pro**: Simple, predictable, easy to debug
- **Con**: Can't parallelize, latency = sum of all steps

**Hierarchical**:
- **Pro**: Can parallelize, clear separation of concerns
- **Con**: More complex coordination, overhead of delegation

### Related Concepts

- **Parallel Pattern**: Execute multiple agents concurrently without coordination
- **Conditional Routing**: Route to different agents based on input classification

### Further Reading

- Load skill `wicked-garden:agentic:agentic-patterns` for 12 common patterns
- Run `/wicked-garden:agentic:design` to see these patterns applied to your use case
```

### Safety Question

```
User: /wicked-garden:agentic:ask How do I handle PII in agent systems?

Claude: [Routes to safety-reviewer agent]

## How do I handle PII in agent systems?

### Answer

PII (Personally Identifiable Information) in agentic systems requires careful handling to prevent leaks through logs, prompts, or external API calls. Key strategies:

1. **Redaction**: Strip PII before sending to LLM
2. **Synthetic data**: Replace real PII with fake data for testing
3. **Access controls**: Limit which agents can access PII
4. **Audit logging**: Track all PII access (but don't log the PII itself)

### Example

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Detect and redact PII
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def sanitize_input(text: str) -> tuple[str, dict]:
    """Remove PII, return sanitized text + mapping for restoration."""
    results = analyzer.analyze(text, language='en')
    anonymized = anonymizer.anonymize(text, results)
    return anonymized.text, anonymized.items

# In your agent
user_input = "My email is john@example.com and SSN is 123-45-6789"
safe_input, pii_map = sanitize_input(user_input)
# safe_input = "My email is <EMAIL> and SSN is <SSN>"

# Send safe_input to LLM, not original
response = agent.run(safe_input)
```

### When to Redact

- Before logging
- Before sending to external APIs
- Before storing in databases
- Before passing to LLM prompts

### When NOT to Redact

- If PII is essential for the task (e.g., email sending agent needs real email)
- Solution: Use secure credential store, don't pass through prompts

### Trade-offs

- **Pro**: Prevents leaks, compliance-friendly
- **Con**: Agent may need PII for context (e.g., personalization)
- **Mitigation**: Use references/IDs instead of raw PII

### Required Safeguards

1. **Redaction library**: Presidio (Python) or similar
2. **Audit logging**: Log when PII is accessed, not the PII itself
3. **Access controls**: Only authorized agents can access PII
4. **Testing**: Verify no PII in logs or prompt traces

### Related Concepts

- **Data minimization**: Only collect PII you actually need
- **Encryption**: Encrypt PII at rest and in transit
- **Compliance**: GDPR, CCPA, HIPAA requirements

### Further Reading

- Load skill `wicked-garden:agentic:trust-and-safety` for comprehensive safety guidance
- Run `/wicked-garden:agentic:audit` to check your system for PII handling issues
```

### Framework Question

```
User: /wicked-garden:agentic:ask Should I use LangChain or CrewAI?

Claude: [Routes to framework-researcher agent]

## Should I use LangChain or CrewAI?

### Answer

**LangChain**: Flexible, low-level building blocks for LLM applications. Great for custom workflows and experimentation.

**CrewAI**: Opinionated, high-level framework for multi-agent collaboration. Great for team-based agent patterns.

**Choose LangChain if**:
- You need fine-grained control
- Building custom agentic patterns
- Want flexibility to use any LLM or tool
- Have complex state management needs

**Choose CrewAI if**:
- Building multi-agent teams
- Want rapid prototyping
- Need role-based agent collaboration
- Prefer conventions over configuration

### Example

**LangChain** (Sequential chain):
```python
from langchain.chains import LLMChain

chain = (
    research_chain
    | analysis_chain
    | summary_chain
)
result = chain.invoke({"topic": "AI safety"})
```

**CrewAI** (Collaborative team):
```python
from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", goal="Find information")
analyst = Agent(role="Analyst", goal="Analyze findings")
writer = Agent(role="Writer", goal="Summarize results")

crew = Crew(agents=[researcher, analyst, writer])
result = crew.kickoff({"topic": "AI safety"})
```

### When to Use LangChain

- Custom agentic architectures
- Need LangGraph for complex state machines
- Want to mix multiple LLM providers
- Building low-latency systems (more control)

### When to Use CrewAI

- Multi-agent teams with defined roles
- Hierarchical or collaborative patterns
- Want built-in memory and context sharing
- Rapid prototyping of agent teams

### Trade-offs

**LangChain**:
- **Pro**: Maximum flexibility, large ecosystem, active development
- **Con**: More boilerplate, steeper learning curve

**CrewAI**:
- **Pro**: Fast to build agent teams, opinionated patterns, clean API
- **Con**: Less flexible, newer (smaller ecosystem)

### Hybrid Approach

You can use both! LangChain for tools and chains, CrewAI for agent orchestration:
```python
from crewai import Agent
from langchain.tools import Tool

# LangChain tool
search_tool = Tool.from_langchain(langchain_search_tool)

# CrewAI agent using LangChain tool
agent = Agent(
    role="Researcher",
    tools=[search_tool]
)
```

### Related Concepts

- **LangGraph**: LangChain's library for stateful agent workflows
- **AutoGen**: Microsoft's multi-agent conversation framework
- **Semantic Kernel**: Microsoft's LLM orchestration SDK

### Further Reading

- Run `/wicked-garden:agentic:frameworks --compare langchain,crewai` for detailed comparison
- Load skill `wicked-garden:agentic:frameworks` for framework selection guide
```

### Pattern Question

```
User: /wicked-garden:agentic:ask What are anti-patterns in agentic systems?

Claude: [Routes to pattern-advisor agent]

## What are anti-patterns in agentic systems?

### Answer

Anti-patterns are common design mistakes that seem reasonable but lead to problems. In agentic systems, these often involve poor control flow, missing error handling, or inappropriate tool usage.

### Common Anti-Patterns

#### 1. God Agent
**Problem**: Single agent doing everything.
```python
# BAD: One agent with 20 different tools
agent = Agent(
    role="Do Everything",
    tools=[search, scrape, analyze, write, email, database, api, ...]
)
```

**Fix**: Decompose into specialized agents.
```python
# GOOD: Specialized agents
research_agent = Agent(role="Researcher", tools=[search, scrape])
analysis_agent = Agent(role="Analyst", tools=[analyze])
writer_agent = Agent(role="Writer", tools=[write])
```

#### 2. Circular Dependencies
**Problem**: Agents calling each other infinitely.
```python
# BAD: Agent A calls Agent B calls Agent A
agent_a.delegate_to(agent_b)
agent_b.delegate_to(agent_a)  # Infinite loop!
```

**Fix**: Use hierarchical pattern with clear coordinator.

#### 3. Missing Error Handling
**Problem**: No fallback when tools fail.
```python
# BAD: Assume tool always works
result = expensive_api_call()
return result  # What if API is down?
```

**Fix**: Add retries, fallbacks, and graceful degradation.
```python
# GOOD: Handle failures
try:
    result = expensive_api_call()
except APIError:
    result = use_fallback_method()
```

#### 4. Unbounded Tool Calls
**Problem**: No limit on how many times agent can use expensive tools.
```python
# BAD: Agent can call API 1000 times
while not satisfied:
    result = call_expensive_api()
```

**Fix**: Set iteration limits and budgets.
```python
# GOOD: Bounded execution
max_iterations = 5
for i in range(max_iterations):
    result = call_expensive_api()
    if is_good_enough(result):
        break
```

#### 5. Context Stuffing
**Problem**: Passing entire conversation history to every agent.
```python
# BAD: 50,000 token context for simple task
agent.run(full_conversation_history)  # Slow + expensive
```

**Fix**: Pass only relevant context.
```python
# GOOD: Minimal context
agent.run(last_n_messages + task_description)
```

### Detection

Run `/wicked-garden:agentic:review` to automatically detect these anti-patterns in your codebase.

### Related Concepts

- **Five-layer architecture**: Prevents God Agent by enforcing separation
- **Circuit breaker pattern**: Prevents unbounded retries
- **Context pruning**: Manages context stuffing

### Further Reading

- Load skill `wicked-garden:agentic:agentic-patterns` for correct pattern implementations
- Run `/wicked-garden:agentic:design` for anti-pattern-free architecture
```

### Performance Question

```
User: /wicked-garden:agentic:ask How can I reduce latency in my agent system?

Claude: [Routes to performance-analyst agent]

## How can I reduce latency in my agent system?

### Answer

Latency in agentic systems comes from sequential execution, LLM calls, and tool usage. Key optimization strategies:

1. **Parallelize independent operations**
2. **Cache expensive computations**
3. **Use smaller/faster models where possible**
4. **Reduce token usage**
5. **Optimize tool execution**

### Example Optimizations

#### Before: Sequential (5-10s total)
```python
# Each step waits for previous step
search_results = search_agent(query)          # 2s
analysis = analysis_agent(search_results)     # 3s
summary = summary_agent(analysis)             # 2s
```

#### After: Parallel where possible (3-4s total)
```python
# Independent operations in parallel
results = await asyncio.gather(
    search_agent(query),           # 2s
    context_agent(query),          # 2s
)

# Then dependent operations
analysis = analysis_agent(results)  # 3s (can't parallelize)
```

#### Caching (100ms for cache hits)
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def search_tool(query: str):
    return expensive_search(query)

# First call: 2s
result1 = search_tool("AI safety")

# Cache hit: <1ms
result2 = search_tool("AI safety")
```

#### Model Selection
```python
# Expensive: GPT-4 for everything (3s per call)
result = gpt4_agent(simple_task)

# Optimized: Use smaller models for simple tasks (0.5s per call)
if is_simple(task):
    result = gpt3_5_agent(task)  # 6x faster, 10x cheaper
else:
    result = gpt4_agent(task)
```

### Latency Budget Analysis

Measure where time goes:
```python
import time

start = time.time()
search_results = search_agent(query)
print(f"Search: {time.time() - start:.2f}s")

start = time.time()
analysis = analysis_agent(search_results)
print(f"Analysis: {time.time() - start:.2f}s")
```

### When to Optimize

- **User-facing**: Target <2s for simple queries, <10s for complex
- **Batch processing**: Latency less critical, focus on throughput
- **Real-time**: May need specialized architectures (streaming, edge deployment)

### Trade-offs

- **Parallelization**: Faster but more complex, harder to debug
- **Caching**: Faster but may serve stale data
- **Smaller models**: Faster but potentially lower quality

### Related Concepts

- **Streaming**: Return partial results while processing continues
- **Async execution**: Non-blocking I/O for tool calls
- **Edge deployment**: Run smaller models closer to users

### Further Reading

- Run `/wicked-garden:agentic:review . --quick` for latency bottleneck analysis
- Load skill `wicked-garden:agentic:agentic-patterns` for performance patterns
```
