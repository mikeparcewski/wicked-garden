# Selective Loading & Token-Aware Prompting

Strategies for loading only relevant context and adapting prompts to available token budgets.

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
