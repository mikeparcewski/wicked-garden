# Caching, Batching & Cost Optimization

Advanced strategies for reducing API costs through caching, batching, and intelligent model selection.

## Caching Strategies

### 10. Prompt Prefix Caching

Cache common prompt prefixes.

```python
class PrefixCache:
    """
    Some LLM providers (like Anthropic) cache prompt prefixes automatically.
    Structure prompts to maximize cache hits.
    """

    def build_cacheable_prompt(self, static_instructions, dynamic_task):
        # Put static content first (will be cached)
        prompt = [
            {
                "role": "system",
                "content": static_instructions,  # This gets cached
                "cache_control": {"type": "ephemeral"}
            },
            {
                "role": "user",
                "content": dynamic_task  # This changes each time
            }
        ]
        return prompt

# Usage: Reuse same system prompt across requests
cache = PrefixCache()
for task in tasks:
    prompt = cache.build_cacheable_prompt(
        static_instructions="You are a helpful assistant...",  # Cached
        dynamic_task=task  # Not cached
    )
```

### 11. Semantic Caching

Cache responses for semantically similar queries.

```python
class SemanticCache:
    def __init__(self, similarity_threshold=0.95):
        self.cache = []  # [(query_embedding, response)]
        self.threshold = similarity_threshold

    async def get(self, query):
        query_embedding = await self.embed(query)

        # Check for similar cached query
        for cached_embedding, cached_response in self.cache:
            similarity = cosine_similarity([query_embedding], [cached_embedding])[0][0]
            if similarity >= self.threshold:
                return cached_response

        return None

    async def set(self, query, response):
        query_embedding = await self.embed(query)
        self.cache.append((query_embedding, response))

# Usage
cache = SemanticCache()

# Try cache first
cached = await cache.get(user_query)
if cached:
    return cached

# If not cached, generate and cache
response = await llm.generate(user_query)
await cache.set(user_query, response)
```

## Batching and Parallelization

### 12. Batch Processing

Process multiple items in single LLM call.

```python
class BatchProcessor:
    async def process_batch(self, items, max_batch_size=10):
        results = []

        for i in range(0, len(items), max_batch_size):
            batch = items[i:i+max_batch_size]

            # Process entire batch in one call
            batch_prompt = "Process each item:\n\n"
            for idx, item in enumerate(batch):
                batch_prompt += f"Item {idx+1}: {item}\n"

            batch_results = await self.llm.generate(batch_prompt)
            results.extend(self.parse_batch_results(batch_results))

        return results
```

### 13. Parallel Context Loading

Load multiple context sources in parallel.

```python
class ParallelContextLoader:
    async def load_context(self, query):
        # Load multiple sources in parallel
        results = await asyncio.gather(
            self.load_vector_search(query),
            self.load_user_preferences(query.user_id),
            self.load_recent_history(query.session_id),
            self.load_domain_knowledge(query.domain)
        )

        vector_results, preferences, history, knowledge = results

        # Combine and trim to budget
        combined = self.combine_context(
            vector_results,
            preferences,
            history,
            knowledge,
            token_budget=8000
        )

        return combined
```

## Cost-Aware Optimization

### 14. Model Selection by Budget

Choose model based on available budget.

```python
class BudgetAwareModelSelector:
    def select_model(self, task_complexity, token_budget, cost_budget):
        # For complex tasks with high budget, use best model
        if task_complexity == 'high' and cost_budget > 1.0:
            return 'claude-opus-4'

        # For medium complexity, use balanced model
        elif task_complexity == 'medium':
            return 'claude-sonnet-4'

        # For simple tasks or tight budget, use efficient model
        else:
            return 'claude-haiku-4'

# Usage
selector = BudgetAwareModelSelector()
model = selector.select_model(
    task_complexity='medium',
    token_budget=10000,
    cost_budget=0.5
)
```

### 15. Progressive Detail Loading

Start with minimal context, add detail if needed.

```python
class ProgressiveLoader:
    async def solve(self, task):
        # Start with minimal context
        context = await self.load_minimal_context(task)
        response = await self.llm.generate(task, context=context)

        # If agent says it needs more info...
        if "need more information" in response.lower():
            # Load medium context
            context = await self.load_medium_context(task)
            response = await self.llm.generate(task, context=context)

            # If still needs more...
            if "need more information" in response.lower():
                # Load full context
                context = await self.load_full_context(task)
                response = await self.llm.generate(task, context=context)

        return response
```

## Monitoring and Analytics

### 16. Token Usage Analytics

Track where tokens are being spent.

```python
class TokenAnalytics:
    def __init__(self):
        self.usage = defaultdict(lambda: {'input': 0, 'output': 0})

    def record(self, component, input_tokens, output_tokens):
        self.usage[component]['input'] += input_tokens
        self.usage[component]['output'] += output_tokens

    def get_report(self):
        total_input = sum(u['input'] for u in self.usage.values())
        total_output = sum(u['output'] for u in self.usage.values())

        report = {
            'total_tokens': total_input + total_output,
            'total_input': total_input,
            'total_output': total_output,
            'by_component': {}
        }

        for component, usage in self.usage.items():
            total = usage['input'] + usage['output']
            report['by_component'][component] = {
                'tokens': total,
                'percentage': (total / report['total_tokens']) * 100
            }

        return report

# Find optimization opportunities
analytics = TokenAnalytics()
report = analytics.get_report()
top_spenders = sorted(
    report['by_component'].items(),
    key=lambda x: x[1]['tokens'],
    reverse=True
)[:5]
print(f"Top 5 token consumers: {top_spenders}")
```

## Best Practices Summary

1. **Compress old context**: Summarize conversations > 20 messages
2. **Load selectively**: Retrieve only relevant context for current task
3. **Use structured formats**: JSON/YAML more efficient than prose
4. **Cache intelligently**: Cache common prompts and similar queries
5. **Batch when possible**: Process multiple items per LLM call
6. **Monitor usage**: Track token usage by component
7. **Progressive loading**: Start minimal, add detail if needed
8. **Deduplicate**: Remove semantically similar context
9. **Time decay**: Weight recent information more heavily
10. **Budget enforcement**: Hard limits on tokens per agent/session
