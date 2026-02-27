# Context Optimization Techniques

Advanced strategies for minimizing token usage while maximizing context quality.

## Compression Techniques

### 1. Conversation Summarization

Progressive summarization of conversation history.

```python
class ConversationCompressor:
    def __init__(self, llm, max_full_messages=10, summary_length=500):
        self.llm = llm
        self.max_full_messages = max_full_messages
        self.summary_length = summary_length

    async def compress(self, messages):
        if len(messages) <= self.max_full_messages:
            return messages

        # Split into old (to summarize) and recent (keep full)
        old_messages = messages[:-self.max_full_messages]
        recent_messages = messages[-self.max_full_messages:]

        # Create summary of old messages
        summary_prompt = f"""Summarize this conversation in {self.summary_length} words or less.
        Focus on:
        - Key decisions made
        - Important facts established
        - Current task state

        Conversation:
        {self.format_messages(old_messages)}
        """

        summary = await self.llm.generate(summary_prompt, max_tokens=self.summary_length * 2)

        # Return summary + recent messages
        return [
            {"role": "system", "content": f"Previous conversation summary:\n{summary}"}
        ] + recent_messages

    def format_messages(self, messages):
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)
```

### 2. Semantic Deduplication

Remove redundant information.

```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class SemanticDeduplicator:
    def __init__(self, similarity_threshold=0.9):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.threshold = similarity_threshold

    def deduplicate(self, texts):
        if not texts:
            return texts

        # Encode all texts
        embeddings = self.encoder.encode(texts)

        # Keep track of which to keep
        keep_indices = [0]  # Always keep first

        for i in range(1, len(texts)):
            # Compare to all kept texts
            similarities = cosine_similarity(
                [embeddings[i]],
                embeddings[keep_indices]
            )[0]

            # Only keep if not too similar to existing
            if max(similarities) < self.threshold:
                keep_indices.append(i)

        return [texts[i] for i in keep_indices]

# Usage
deduper = SemanticDeduplicator()
unique_contexts = deduper.deduplicate([
    "The user prefers Python",
    "User likes Python programming",  # Very similar - would be removed
    "The user works at Acme Corp"      # Different - would be kept
])
```

### 3. Hierarchical Summarization

Summarize at multiple levels of detail.

```python
class HierarchicalSummarizer:
    async def summarize(self, text, levels=3):
        summaries = {}

        # Level 0: Full text
        summaries['full'] = text

        # Level 1: Detailed summary (50% reduction)
        summaries['detailed'] = await self.llm.generate(
            f"Summarize in half the length:\n{text}"
        )

        # Level 2: Brief summary (80% reduction)
        summaries['brief'] = await self.llm.generate(
            f"Summarize in 1-2 paragraphs:\n{summaries['detailed']}"
        )

        # Level 3: Ultra-brief (95% reduction)
        summaries['headline'] = await self.llm.generate(
            f"Summarize in one sentence:\n{summaries['brief']}"
        )

        return summaries

# Usage: Choose appropriate level based on available tokens
summaries = await summarizer.summarize(long_document)
if tokens_available > 5000:
    context = summaries['detailed']
elif tokens_available > 1000:
    context = summaries['brief']
else:
    context = summaries['headline']
```

### 4. Entity-Based Compression

Extract and store only key entities and relationships.

```python
class EntityCompressor:
    async def compress(self, text):
        # Extract entities
        entities_prompt = f"""Extract key entities and relationships from this text.
        Format as JSON: {{"entities": [...], "relationships": [...]}}

        Text: {text}
        """

        entities = await self.llm.generate(entities_prompt)

        # Store compressed representation
        return {
            'entities': entities['entities'],
            'relationships': entities['relationships'],
            'original_length': len(text),
            'compressed_length': len(str(entities))
        }

    def reconstruct_context(self, compressed):
        # Build minimal context from entities
        context = "Key facts:\n"
        for entity in compressed['entities']:
            context += f"- {entity}\n"

        context += "\nRelationships:\n"
        for rel in compressed['relationships']:
            context += f"- {rel}\n"

        return context
```

## Selective Loading Strategies

### 5. Relevance-Based Filtering

Load only context relevant to current task.

```python
class RelevanceFilter:
    def __init__(self, vector_db):
        self.vector_db = vector_db

    async def filter_context(self, all_context, current_task, top_k=5):
        # Embed current task
        task_embedding = await self.embed(current_task)

        # Score all context items by relevance
        scored_items = []
        for item in all_context:
            item_embedding = await self.embed(item)
            similarity = cosine_similarity([task_embedding], [item_embedding])[0][0]
            scored_items.append((item, similarity))

        # Sort by relevance and take top K
        scored_items.sort(key=lambda x: x[1], reverse=True)
        relevant_items = [item for item, score in scored_items[:top_k]]

        return relevant_items

# Usage
filter = RelevanceFilter(vector_db)
relevant = await filter.filter_context(
    all_context=user.full_history,
    current_task="Write a Python function",
    top_k=3
)
```

### 6. Time-Based Decay

Weight recent context more heavily.

```python
from datetime import datetime, timedelta

class TimeDecayFilter:
    def score_by_recency(self, items, decay_factor=0.5):
        """Score items with exponential time decay."""
        now = datetime.now()
        scored_items = []

        for item in items:
            age = (now - item.timestamp).total_seconds() / 3600  # hours
            decay = decay_factor ** (age / 24)  # Half-life of 24 hours
            scored_items.append((item, decay))

        return sorted(scored_items, key=lambda x: x[1], reverse=True)

# Combine with relevance
class HybridFilter:
    def score(self, item, task_embedding):
        # Relevance score
        relevance = cosine_similarity(
            [task_embedding],
            [item.embedding]
        )[0][0]

        # Recency score
        age_hours = (datetime.now() - item.timestamp).total_seconds() / 3600
        recency = 0.5 ** (age_hours / 24)

        # Weighted combination
        return 0.7 * relevance + 0.3 * recency
```

### 7. Query-Specific Pruning

Remove context not needed for specific query type.

```python
class QuerySpecificPruner:
    def prune(self, context, query_type):
        if query_type == 'factual':
            # Keep facts, remove opinions/summaries
            return [c for c in context if c.type == 'fact']

        elif query_type == 'code_generation':
            # Keep code examples, remove general discussion
            return [c for c in context if c.type in ['code', 'api_doc']]

        elif query_type == 'decision':
            # Keep past decisions and outcomes
            return [c for c in context if c.type in ['decision', 'outcome']]

        else:
            # Default: keep all
            return context
```

## Token-Aware Prompting

### 8. Dynamic Prompt Sizing

Adjust prompt detail based on available tokens.

```python
class DynamicPrompt:
    def __init__(self, max_tokens):
        self.max_tokens = max_tokens

    def build_prompt(self, task, available_tokens):
        # Base prompt (always include)
        base = f"Task: {task}\n\n"
        base_tokens = self.count_tokens(base)

        remaining = available_tokens - base_tokens - 1000  # Reserve for output

        if remaining > 5000:
            # Verbose mode
            return base + self.get_detailed_instructions()

        elif remaining > 2000:
            # Standard mode
            return base + self.get_standard_instructions()

        else:
            # Minimal mode
            return base + self.get_minimal_instructions()

    def get_detailed_instructions(self):
        return """Detailed instructions with examples:
        1. First step with example...
        2. Second step with example...
        ...
        """

    def get_standard_instructions(self):
        return """Standard instructions:
        1. First step
        2. Second step
        ...
        """

    def get_minimal_instructions(self):
        return "Follow standard procedure."
```

### 9. Token-Budgeted Retrieval

Retrieve as much as token budget allows.

```python
class BudgetedRetriever:
    async def retrieve(self, query, token_budget):
        # Get candidates
        candidates = await self.vector_db.search(query, limit=100)

        # Add candidates until budget exhausted
        selected = []
        tokens_used = 0

        for candidate in candidates:
            candidate_tokens = self.count_tokens(candidate.content)

            if tokens_used + candidate_tokens <= token_budget:
                selected.append(candidate)
                tokens_used += candidate_tokens
            else:
                break

        return selected, tokens_used
```

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
