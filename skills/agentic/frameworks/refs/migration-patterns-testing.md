# Framework Migration Patterns: Testing, Rollback & Advanced Paths

Migration testing strategy, rollback planning, advanced migration paths, effort estimates, and when not to migrate.

## Advanced Migration Paths

### 5. Python Framework -> ADK (TypeScript)

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

### 6. Single-Provider -> Multi-Provider

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
| Custom -> Framework | 2-4 weeks | Medium |
| LangChain -> LangGraph | 1-2 weeks | Low |
| CrewAI -> LangGraph | 2-3 weeks | Medium |
| AutoGen -> LangGraph | 3-4 weeks | Medium |
| Python -> TypeScript (ADK) | 4-8 weeks | High |
| Single -> Multi-Provider | 1-2 weeks | Low |

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
