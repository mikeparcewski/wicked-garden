# Implementation Guide - Layers 1-3

Step-by-step guide to implementing Layer 1 (Cognition), Layer 2 (Context), and Layer 3 (Interaction).

## Starting Point: Choose Your Foundation

Before building layers, choose your base framework:

**Option A: Framework-Based** (LangGraph, ADK, CrewAI, AutoGen)
- Layers 1-4 partially implemented
- Focus on customizing and extending
- Faster to prototype

**Option B: From Scratch** (Build on LLM API directly)
- Full control over all layers
- More implementation work
- Better for custom requirements

This guide covers building from scratch. Framework-based approaches follow similar principles but use framework abstractions.

## Phase 1: Layer 1 - Cognition

### Step 1.1: Set Up LLM Client

```python
from anthropic import Anthropic

class LLMClient:
    def __init__(self, api_key, model="claude-opus-4-6"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    async def generate(self, messages, max_tokens=4000):
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        return {
            "content": response.content[0].text,
            "tokens": response.usage.input_tokens + response.usage.output_tokens
        }
```

### Step 1.2: Create Basic Agent

```python
class Agent:
    def __init__(self, name, instructions, llm_client):
        self.name = name
        self.instructions = instructions
        self.llm = llm_client

    async def process(self, task):
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": task}
        ]

        response = await self.llm.generate(messages)
        return response["content"]
```

### Step 1.3: Add Reasoning Patterns

```python
class ReActAgent(Agent):
    async def solve(self, task):
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": f"Task: {task}\n\nThink step by step."}
        ]

        max_iterations = 10
        for i in range(max_iterations):
            # Reason
            response = await self.llm.generate(messages)

            # Check if done
            if self.is_complete(response["content"]):
                return self.extract_answer(response["content"])

            # Act and observe
            action = self.extract_action(response["content"])
            observation = await self.execute_action(action)

            # Add to conversation
            messages.append({"role": "assistant", "content": response["content"]})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        raise MaxIterationsError()
```

### Testing Layer 1

```python
# Test basic reasoning
agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
    llm_client=LLMClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
)

result = await agent.process("What is 2+2?")
assert "4" in result
```

## Phase 2: Layer 2 - Context

### Step 2.1: Implement Session State

```python
class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(self, session_id):
        self.sessions[session_id] = {
            "messages": [],
            "metadata": {},
            "created_at": datetime.now()
        }

    def add_message(self, session_id, role, content):
        if session_id not in self.sessions:
            self.create_session(session_id)

        self.sessions[session_id]["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })

    def get_messages(self, session_id, last_n=None):
        messages = self.sessions.get(session_id, {}).get("messages", [])
        return messages[-last_n:] if last_n else messages
```

### Step 2.2: Add Vector Memory

```python
# Using ChromaDB for vector storage
import chromadb
from sentence_transformers import SentenceTransformer

class VectorMemory:
    def __init__(self, collection_name="agent_memory"):
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(collection_name)
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')

    def store(self, content, metadata=None):
        embedding = self.encoder.encode(content).tolist()
        self.collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}],
            ids=[str(uuid.uuid4())]
        )

    def search(self, query, top_k=5):
        query_embedding = self.encoder.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        return results["documents"][0] if results["documents"] else []
```

### Step 2.3: Integrate Context with Agent

```python
class ContextAwareAgent(Agent):
    def __init__(self, name, instructions, llm_client, session_manager, memory):
        super().__init__(name, instructions, llm_client)
        self.session_manager = session_manager
        self.memory = memory

    async def process(self, task, session_id):
        # Retrieve relevant memories
        relevant_context = self.memory.search(task, top_k=3)

        # Build messages with context
        messages = [{"role": "system", "content": self.instructions}]

        if relevant_context:
            messages.append({
                "role": "system",
                "content": f"Relevant context:\n{'\n'.join(relevant_context)}"
            })

        # Add session history
        session_messages = self.session_manager.get_messages(session_id, last_n=10)
        messages.extend(session_messages)

        # Add current task
        messages.append({"role": "user", "content": task})

        # Generate response
        response = await self.llm.generate(messages)

        # Update session
        self.session_manager.add_message(session_id, "user", task)
        self.session_manager.add_message(session_id, "assistant", response["content"])

        # Store in long-term memory
        self.memory.store(f"Q: {task}\nA: {response['content']}")

        return response["content"]
```

### Testing Layer 2

```python
# Test memory retrieval
memory = VectorMemory()
memory.store("The user prefers Python")
memory.store("The user works on web applications")

results = memory.search("What language does the user like?")
assert "Python" in results[0]
```

## Phase 3: Layer 3 - Interaction

### Step 3.1: Create Tool System

```python
from typing import Callable, Dict, Any
from pydantic import BaseModel

class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def get_tool_descriptions(self):
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self.tools.values()
        ]

    async def execute(self, tool_name: str, **kwargs):
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]
        return await tool.function(**kwargs)
```

### Step 3.2: Define Sample Tools

```python
async def web_search(query: str) -> str:
    # Implement actual web search
    return f"Search results for: {query}"

async def calculate(expression: str) -> str:
    try:
        result = eval(expression)  # In production, use safe eval
        return str(result)
    except Exception as e:
        return f"Error: {e}"

# Register tools
registry = ToolRegistry()
registry.register(Tool(
    name="web_search",
    description="Search the web for information",
    parameters={"query": "string"},
    function=web_search
))
registry.register(Tool(
    name="calculate",
    description="Perform mathematical calculations",
    parameters={"expression": "string"},
    function=calculate
))
```

### Step 3.3: Enable Tool Use in Agent

```python
import json

class ToolUsingAgent(ContextAwareAgent):
    def __init__(self, name, instructions, llm_client, session_manager, memory, tools):
        super().__init__(name, instructions, llm_client, session_manager, memory)
        self.tools = tools

    async def process(self, task, session_id):
        messages = self._build_messages(task, session_id)

        # Add tool descriptions
        tool_desc = self.tools.get_tool_descriptions()
        messages[0]["content"] += f"\n\nAvailable tools:\n{json.dumps(tool_desc, indent=2)}"

        max_iterations = 5
        for i in range(max_iterations):
            response = await self.llm.generate(messages)
            content = response["content"]

            # Check if agent wants to use a tool
            if "USE_TOOL:" in content:
                tool_call = self.parse_tool_call(content)
                result = await self.tools.execute(
                    tool_call["name"],
                    **tool_call["args"]
                )
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Tool result: {result}"})
                continue

            # Agent provided final answer
            return content

    def parse_tool_call(self, content):
        # Simple parsing - in production use structured outputs
        # Expected format: USE_TOOL: {"name": "web_search", "args": {"query": "..."}}
        tool_line = [line for line in content.split("\n") if "USE_TOOL:" in line][0]
        tool_json = tool_line.split("USE_TOOL:")[1].strip()
        return json.loads(tool_json)
```

### Testing Layer 3

```python
# Test tool execution
agent = ToolUsingAgent(
    name="assistant",
    instructions="You can use tools. To use a tool, output: USE_TOOL: {json}",
    llm_client=llm,
    session_manager=sessions,
    memory=memory,
    tools=registry
)

result = await agent.process("What is 15 * 23?", session_id="test")
assert "345" in result
```
