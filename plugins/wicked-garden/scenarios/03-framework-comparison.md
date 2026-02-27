---
name: framework-comparison
title: Agentic Framework Comparison
description: Research and compare frameworks to select the best fit for a given use case
type: workflow
difficulty: basic
estimated_minutes: 8
---

# Agentic Framework Comparison

This scenario validates that wicked-agentic's frameworks command can compare specific frameworks, run interactive selection, and recommend based on requirements — all with up-to-date information from web search.

## Setup

No project files needed. The frameworks command operates as a research and advisory tool.

## Steps

### 1. Direct Framework Comparison

```bash
/wicked-agentic:frameworks --compare langchain,crewai,autogen
```

**Expected**:
- `wicked-agentic:framework-researcher` agent spawned in comparison mode
- WebSearch used for latest 2026 information on each framework
- Comparison table produced covering key dimensions
- Recommendation section with "best for each use case" guidance

**Expected comparison table**:

```
| Aspect | LangChain | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| Language | Python, TypeScript | Python | Python |
| Pattern Focus | Flexible chains | Agent teams | Conversations |
| Learning Curve | Medium | Low | Medium |
| Production Ready | Yes | Yes | Yes |
```

### 2. Language and Use Case Filtering

```bash
/wicked-agentic:frameworks --language typescript --use-case customer-support
```

**Expected**:
- Framework researcher filters for TypeScript-compatible frameworks
- Returns 3-5 relevant options
- Each includes "why it fits" reasoning for customer support
- Quick start code examples in TypeScript

**Expected top recommendations**:
- LangChain.js (mature, extensive integrations)
- Vercel AI SDK (excellent for Next.js streaming)
- Semantic Kernel (enterprise/Azure use cases)

### 3. Interactive Selection Wizard

```bash
/wicked-agentic:frameworks
```

**Expected**:
- Framework researcher enters wizard mode
- Asks 5 structured questions sequentially:
  1. Language preference
  2. Use case
  3. Experience level
  4. Scale target
  5. Priority (speed/flexibility/cost/performance/community)
- Provides recommendation with rationale after answers
- Includes quick start code example

**Wizard interaction**:

```
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
[next question...]
```

**After providing answers** (Python, data pipeline, intermediate, production, performance):

```
## Recommendation: LangGraph

Based on your answers:
- Language: Python
- Use case: Data processing pipeline
- Experience: Intermediate
- Scale: Production
- Priority: Performance

I recommend LangGraph because:
1. Graph-based state management ideal for pipelines
2. Built-in parallelization for performance
3. Production-ready with Langsmith observability
```

### 4. Framework Recommendation Leads to Design

After getting a recommendation, user should be able to chain to design:

```bash
User: /wicked-agentic:frameworks --language python --use-case data-pipeline
Claude: [Recommends LangGraph]
        Would you like me to design an architecture using LangGraph?
        Run: /wicked-agentic:design "data pipeline using LangGraph"
```

**Expected**: The framework recommendation includes a clear next step pointing to `/wicked-agentic:design`.

## Expected Outcome

**Direct comparison**:
```markdown
# Framework Comparison: LangChain vs CrewAI vs AutoGen

## Quick Comparison
[Table with all dimensions]

## Recommendation
- For collaborative multi-agent teams: CrewAI
- For maximum flexibility: LangChain
- For conversation-based workflows: AutoGen

## Next Steps
Would you like me to design an architecture using one of these?
```

**Wizard recommendation**:
```markdown
## Recommendation: [Framework]

Based on your profile:
[Summary of answers]

I recommend [Framework] because:
1. [Reason 1]
2. [Reason 2]
3. [Reason 3]

### Quick Start
[Installation and hello world example]
```

## Success Criteria

- [ ] `--compare` mode produces side-by-side comparison table
- [ ] Framework researcher agent spawned via Task tool
- [ ] WebSearch used for up-to-date 2026 information
- [ ] `--language` filter returns only language-appropriate frameworks
- [ ] `--use-case` filter returns contextually relevant recommendations
- [ ] Wizard asks all 5 questions in sequence
- [ ] Wizard recommendation includes quick start code
- [ ] Code examples compile/run as shown
- [ ] Each mode ends with `/wicked-agentic:design` as suggested next step
- [ ] Comparison table covers: language, pattern focus, learning curve, production readiness

## Value Demonstrated

**Problem solved**: Teams evaluating agentic frameworks face dozens of options with rapidly changing capabilities. Blog posts are outdated within months. Choosing the wrong framework means rewrites.

**Real-world value**:
- **Current information**: Web search ensures recommendations reflect 2026 state, not 2023
- **Use case matching**: Not just "here's what exists" but "here's what fits your context"
- **Decision velocity**: Framework selection that took days of research takes minutes
- **Low-risk experimentation**: Quick start code lets you validate the recommendation immediately

This replaces research marathons through documentation, outdated blog posts, and YouTube tutorials to understand which framework is best for your situation. The wizard asks the right questions to cut through marketing and give a practical recommendation.
