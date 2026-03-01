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
