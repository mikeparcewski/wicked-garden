---
name: frameworks
description: |
  Agentic framework landscape, comparison, and selection guide for choosing the right framework for your use case.
  Use when: "which agent framework", "compare frameworks", "LangGraph vs CrewAI", "framework selection"
---

# Agentic Frameworks

Comprehensive guide to agentic frameworks, their strengths, and how to choose the right one.

## Quick Comparison Table

| Framework | Language | Best For | Maturity | Learning Curve |
|-----------|----------|----------|----------|----------------|
| Anthropic ADK | TypeScript | Claude-specific, production | High | Low |
| LangGraph | Python | Complex workflows, state | High | Medium |
| CrewAI | Python | Role-based teams | Medium | Low |
| AutoGen | Python | Multi-agent conversations | Medium | Medium |
| Pydantic AI | Python | Type-safe agents | Medium | Low |
| OpenAI Agents SDK | Python | OpenAI-specific | Low | Low |
| LlamaIndex Agents | Python | RAG-heavy applications | High | Medium |
| Haystack | Python | Production pipelines | High | Medium |
| Semantic Kernel | C#/Python | Microsoft ecosystem | Medium | Medium |
| LangChain | Python | Rapid prototyping | High | Medium-High |
| Agency Swarm | Python | OpenAI Assistants API | Low | Low |
| Dify | Low-code | No-code workflows | Medium | Very Low |

## Selection Criteria

### 1. Orchestration Capabilities

**Simple Sequential:**
- LangChain (chains)
- Haystack (pipelines)
- Pydantic AI

**Complex Workflows:**
- LangGraph (state machines)
- ADK (delegated workflows)
- AutoGen (conversation patterns)

**Team-Based:**
- CrewAI (role-based)
- Agency Swarm (org structure)

### 2. State Management

**No Built-in State:** LangChain, Pydantic AI

**Checkpointed State:** LangGraph (built-in), ADK (context preservation)

**Distributed State:** Custom implementation needed for all

### 3. Tool Integration

**Extensive Tool Libraries:** LangChain (largest ecosystem), LlamaIndex (RAG-focused), Haystack (production tools)

**Easy Tool Definition:** Pydantic AI (type-safe), ADK (TypeScript decorators), OpenAI Agents SDK (function calling)

**Custom Tools:** All frameworks support custom tools

### 4. Error Handling

**Built-in Retry/Fallback:** ADK (comprehensive), LangGraph (error handling nodes), Haystack (pipeline error handling)

**Manual Error Handling:** CrewAI, AutoGen, Pydantic AI

### 5. Observability

**Native Tracing:** LangSmith (for LangChain/LangGraph), Braintrust (for ADK)

**Third-Party Integration:** All support OpenTelemetry, most support LangFuse, Arize

## Framework Profiles

See `refs/framework-profiles-1.md` (ADK, LangGraph, CrewAI) and `refs/framework-profiles-2.md` (AutoGen, Pydantic AI, LlamaIndex) for detailed profiles.

### Anthropic Agent Developer Kit (ADK)
**Best for:** Production Claude applications
**Strengths:** TypeScript with type safety, built-in context management, comprehensive error handling, delegated workflows
**Weaknesses:** Claude-only, TypeScript/Node only, smaller community
**When to choose:** Building on Claude exclusively, TypeScript/Node stack, need production-ready patterns

### LangGraph
**Best for:** Complex stateful workflows
**Strengths:** State machine abstraction, built-in checkpointing, human-in-the-loop support, time-travel debugging
**Weaknesses:** Steeper learning curve, can be overkill, more boilerplate
**When to choose:** Complex workflows with branches/loops, need state persistence, want human approval gates

### CrewAI
**Best for:** Role-based agent teams
**Strengths:** Intuitive role/task abstraction, simple API, good for hierarchical teams
**Weaknesses:** Less mature, limited state management, fewer production features
**When to choose:** Team-based workflows, quick prototyping, straightforward delegation

### AutoGen
**Best for:** Multi-agent conversations
**Strengths:** Flexible conversation patterns, group chat capabilities, human-in-the-loop
**Weaknesses:** Can be verbose, conversation management complexity
**When to choose:** Agents need to debate/collaborate, conversational workflows

### Pydantic AI
**Best for:** Type-safe Python agents
**Strengths:** Type safety via Pydantic, simple clean API, dependency injection, multi-provider
**Weaknesses:** New/less mature, smaller ecosystem, limited orchestration patterns
**When to choose:** Want type safety, simple agent use cases, already using Pydantic

### LlamaIndex Agents
**Best for:** RAG-heavy applications
**Strengths:** Excellent retrieval capabilities, query planning, tool use with data
**Weaknesses:** Best for RAG use cases, heavier framework
**When to choose:** Heavy RAG requirements, complex data retrieval, query planning needs

## Decision Tree

```
Start: What's your primary use case?

├─ Complex stateful workflow with branches/loops
│  └─ Use: LangGraph

├─ Role-based team of agents
│  └─ Use: CrewAI or ADK

├─ RAG-heavy application
│  └─ Use: LlamaIndex Agents

├─ Multi-agent conversations/debates
│  └─ Use: AutoGen

├─ Simple sequential workflow
│  ├─ TypeScript?
│  │  └─ Use: ADK
│  └─ Python?
│     └─ Use: Pydantic AI or LangChain

├─ Production pipeline
│  └─ Use: Haystack or ADK

└─ Maximum flexibility
   └─ Build from scratch or use LangGraph
```

## Language Considerations

**Python Frameworks:** LangChain, LangGraph, CrewAI, AutoGen, Pydantic AI, LlamaIndex
- Largest ecosystem, most tutorials/examples, best for data science/ML integration

**TypeScript Frameworks:** Anthropic ADK
- Better type safety, Node.js ecosystem, good for web applications

**C# Frameworks:** Semantic Kernel
- Microsoft ecosystem, .NET integration

## Multi-Provider vs Single-Provider

**Multi-Provider (LLM-agnostic):** LangChain, LangGraph, CrewAI, AutoGen, Pydantic AI
- Can switch between OpenAI, Anthropic, etc.
- More flexibility but may not leverage provider-specific features

**Single-Provider (Optimized):** ADK (Claude), OpenAI Agents SDK (OpenAI)
- Better integration with specific provider
- Access to provider-specific features but less flexibility

## Production Readiness

**Most Production-Ready:** Anthropic ADK, LangGraph, Haystack, LlamaIndex

**Good for Production:** CrewAI, LangChain, AutoGen

**Early/Experimental:** Pydantic AI, OpenAI Agents SDK, Agency Swarm

## When NOT to Use a Framework

Build from scratch if: very simple use case, specific requirements unmet, want maximum control, or learning exercise. Framework overhead not worth it for single LLM calls, static prompts, or no agent behavior.

## Quick Recommendations

**Just getting started:** CrewAI or Pydantic AI | **State management:** LangGraph | **TypeScript:** ADK | **RAG:** LlamaIndex | **Team-based:** CrewAI or ADK | **Max flexibility:** LangGraph | **Production Claude:** ADK

## When to Use

Trigger phrases indicating you need this skill:
- "What agentic framework should I use?"
- "Should I use LangChain or LangGraph?"
- "What's the difference between CrewAI and AutoGen?"
- "Is [framework] good for [use case]?"
- "Should I build from scratch or use a framework?"

## References

- `refs/framework-profiles-1.md` - ADK, LangGraph, CrewAI detailed profiles
- `refs/framework-profiles-2.md` - AutoGen, Pydantic AI, LlamaIndex profiles + comparison matrix
- `refs/migration-patterns.md` - Common migration paths between frameworks
