# Cost Optimization & Reporting

Strategies for estimating, optimizing, and reporting on token costs in agentic systems.

## Cost Estimation

### Estimating Token Count

```python
class TokenEstimator:
    """Estimate tokens before making API call."""

    @staticmethod
    def estimate_tokens(text):
        """Rough estimate: ~4 characters per token for English."""
        return len(text) // 4

    @staticmethod
    def estimate_cost(model, prompt, estimated_output_tokens=500):
        """Estimate cost before API call."""
        input_tokens = TokenEstimator.estimate_tokens(prompt)
        output_tokens = estimated_output_tokens

        calc = CostCalculator()
        return calc.calculate(model, input_tokens, output_tokens)

# More accurate estimation using tiktoken (for OpenAI models)
import tiktoken

class AccurateTokenEstimator:
    def __init__(self, model):
        self.encoding = tiktoken.encoding_for_model(model)

    def count_tokens(self, text):
        return len(self.encoding.encode(text))

    def estimate_cost(self, model, prompt, estimated_output_tokens=500):
        input_tokens = self.count_tokens(prompt)
        calc = CostCalculator()
        return calc.calculate(model, input_tokens, estimated_output_tokens)
```

### Predictive Cost Modeling

```python
class CostPredictor:
    """Predict costs based on historical data."""

    def __init__(self):
        self.history = []

    def record_actual(self, task_type, model, actual_tokens, actual_cost):
        self.history.append({
            'task_type': task_type,
            'model': model,
            'tokens': actual_tokens,
            'cost': actual_cost
        })

    def predict_cost(self, task_type, model):
        """Predict cost for task based on historical similar tasks."""
        similar_tasks = [
            h for h in self.history
            if h['task_type'] == task_type and h['model'] == model
        ]

        if not similar_tasks:
            # No history - use conservative estimate
            return {
                'estimated_tokens': 5000,
                'estimated_cost': CostCalculator().calculate(model, 5000, 1000)['total_cost']
            }

        # Use average of similar tasks
        avg_tokens = np.mean([t['tokens'] for t in similar_tasks])
        avg_cost = np.mean([t['cost'] for t in similar_tasks])

        # Add 20% buffer for safety
        return {
            'estimated_tokens': int(avg_tokens * 1.2),
            'estimated_cost': avg_cost * 1.2
        }
```

## Cost Optimization Strategies

### Model Selection for Cost

```python
class CostOptimizer:
    def select_model_for_task(self, task, quality_threshold=0.8, max_cost=0.10):
        """Select cheapest model that meets quality threshold."""

        # Models ordered by cost (cheapest first)
        models_by_cost = [
            'claude-haiku-4',
            'gpt-3.5-turbo',
            'claude-sonnet-4-5',
            'gpt-4-turbo',
            'claude-opus-4-6',
            'gpt-4'
        ]

        for model in models_by_cost:
            # Estimate cost for this model
            est_cost = self.estimate_task_cost(task, model)

            if est_cost > max_cost:
                continue

            # Check if quality is sufficient (would need ML model for real impl)
            expected_quality = self.predict_quality(task, model)

            if expected_quality >= quality_threshold:
                return {
                    'model': model,
                    'estimated_cost': est_cost,
                    'expected_quality': expected_quality
                }

        raise NoSuitableModelError("No model meets quality/cost requirements")
```

### Batch Processing for Cost Savings

```python
class BatchCostOptimizer:
    """Process multiple items in batches to save on API overhead."""

    async def process_items(self, items, model):
        # Processing individually
        individual_cost = 0
        for item in items:
            cost = await self.process_one(item, model)
            individual_cost += cost

        # Processing as batch
        batch_cost = await self.process_batch(items, model)

        savings = individual_cost - batch_cost
        savings_pct = (savings / individual_cost) * 100

        print(f"Batch processing saved ${savings:.4f} ({savings_pct:.1f}%)")

        return batch_cost

    async def process_batch(self, items, model):
        """Process all items in one API call."""
        batch_prompt = "Process each item:\n\n"
        for i, item in enumerate(items):
            batch_prompt += f"Item {i+1}: {item}\n"

        input_tokens = self.count_tokens(batch_prompt)
        # Single output with all results
        output_tokens = len(items) * 100  # Estimate

        calc = CostCalculator()
        return calc.calculate(model, input_tokens, output_tokens)['total_cost']
```

### Caching for Cost Reduction

```python
class CostAwareCache:
    """Cache expensive LLM calls."""

    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0
        self.savings = 0.0

    async def get_or_generate(self, prompt, model, cost_calculator):
        cache_key = hashlib.md5(f"{prompt}{model}".encode()).hexdigest()

        if cache_key in self.cache:
            # Cache hit
            self.hits += 1

            # Calculate cost saved
            estimated_cost = cost_calculator.estimate(prompt, model)
            self.savings += estimated_cost

            return self.cache[cache_key]['response']

        # Cache miss
        self.misses += 1
        response, actual_cost = await self.generate_with_cost(prompt, model)

        # Store in cache
        self.cache[cache_key] = {
            'response': response,
            'cost': actual_cost,
            'timestamp': datetime.now()
        }

        return response

    def get_cache_stats(self):
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'savings': self.savings
        }
```

## Cost Reporting

### Comprehensive Cost Report

```python
class CostReporter:
    def __init__(self, tracker):
        self.tracker = tracker

    def generate_report(self, period='daily'):
        stats = self.tracker.get_stats()

        report = f"""
Cost Report - {period}
{'='*50}

Summary:
- Total Cost: ${stats['total_cost']:.4f}
- Total Calls: {stats['total_calls']}
- Total Tokens: {stats['total_tokens']:,}
- Avg Cost/Call: ${stats['avg_cost_per_call']:.4f}
- Avg Tokens/Call: {stats['avg_tokens_per_call']:.0f}

By Agent:
"""
        for agent_id, cost in stats['by_agent'].items():
            pct = (cost / stats['total_cost']) * 100
            report += f"  {agent_id}: ${cost:.4f} ({pct:.1f}%)\n"

        report += "\nBy Model:\n"
        for model, cost in stats['by_model'].items():
            pct = (cost / stats['total_cost']) * 100
            report += f"  {model}: ${cost:.4f} ({pct:.1f}%)\n"

        return report

    def identify_optimization_opportunities(self):
        """Find cost optimization opportunities."""
        stats = self.tracker.get_stats()
        opportunities = []

        # Check for expensive agents
        for agent_id, cost in stats['by_agent'].items():
            if cost > stats['total_cost'] * 0.3:  # Agent using >30% of budget
                opportunities.append({
                    'type': 'expensive_agent',
                    'agent': agent_id,
                    'cost': cost,
                    'recommendation': f"Optimize {agent_id} - using {(cost/stats['total_cost']*100):.1f}% of budget"
                })

        # Check for expensive models
        for model, cost in stats['by_model'].items():
            if model in ['claude-opus-4-6', 'gpt-4']:
                # Check if cheaper model could work
                opportunities.append({
                    'type': 'expensive_model',
                    'model': model,
                    'cost': cost,
                    'recommendation': f"Consider using cheaper model instead of {model}"
                })

        return opportunities
```

## Real-World Cost Examples

### Example 1: Code Review System

```python
# Scenario: Review 100 files/day
files_per_day = 100
avg_file_size = 500  # lines
chars_per_line = 80

# Calculate tokens
input_per_file = (avg_file_size * chars_per_line) // 4  # ~10K tokens
output_per_file = 500  # Review comments

# Using Claude Opus
calc = CostCalculator()
cost_opus = calc.calculate('claude-opus-4-6', input_per_file, output_per_file)
daily_cost_opus = cost_opus['total_cost'] * files_per_day

# Using Claude Sonnet (cheaper)
cost_sonnet = calc.calculate('claude-sonnet-4-5', input_per_file, output_per_file)
daily_cost_sonnet = cost_sonnet['total_cost'] * files_per_day

print(f"Daily cost with Opus: ${daily_cost_opus:.2f}")  # ~$18.75
print(f"Daily cost with Sonnet: ${daily_cost_sonnet:.2f}")  # ~$3.75
print(f"Monthly savings with Sonnet: ${(daily_cost_opus - daily_cost_sonnet) * 30:.2f}")  # ~$450
```

### Example 2: Customer Support Bot

```python
# Scenario: 1000 conversations/day, avg 10 messages each
conversations_per_day = 1000
messages_per_conversation = 10
tokens_per_message = 100  # Short messages

total_tokens_per_day = conversations_per_day * messages_per_conversation * tokens_per_message

# Cost calculation
calc = CostCalculator()
cost = calc.calculate('claude-haiku-4', total_tokens_per_day, total_tokens_per_day)

print(f"Daily cost: ${cost['total_cost']:.2f}")  # ~$1.60
print(f"Monthly cost: ${cost['total_cost'] * 30:.2f}")  # ~$48
print(f"Annual cost: ${cost['total_cost'] * 365:.2f}")  # ~$584
```

## Best Practices

1. **Track Everything**: Record all LLM calls with model, tokens, cost
2. **Set Budgets**: Per session, daily, monthly limits
3. **Estimate First**: Predict cost before expensive calls
4. **Cache Aggressively**: Avoid redundant API calls
5. **Batch When Possible**: Combine multiple items per call
6. **Right-Size Models**: Use cheapest model that meets quality bar
7. **Monitor Trends**: Watch for cost increases over time
8. **Optimize Hot Paths**: Focus on highest-cost agents/operations
9. **User Limits**: Prevent abuse with per-user budgets
10. **Alert on Spikes**: Get notified of unusual cost patterns
