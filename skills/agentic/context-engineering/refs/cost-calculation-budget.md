# Token Cost Models and Budgeting

Comprehensive guide to calculating, tracking, and optimizing token costs in agentic systems.

## Pricing Overview (2026 Estimates)

```python
PRICING = {
    # Anthropic Claude
    'claude-opus-4-6': {
        'input': 0.015,   # $ per 1K tokens
        'output': 0.075,
        'context_window': 200000,
        'output_limit': 16000
    },
    'claude-sonnet-4-5': {
        'input': 0.003,
        'output': 0.015,
        'context_window': 200000,
        'output_limit': 16000
    },
    'claude-haiku-4': {
        'input': 0.0008,
        'output': 0.004,
        'context_window': 200000,
        'output_limit': 8000
    },

    # OpenAI GPT
    'gpt-4-turbo': {
        'input': 0.01,
        'output': 0.03,
        'context_window': 128000,
        'output_limit': 4096
    },
    'gpt-4': {
        'input': 0.03,
        'output': 0.06,
        'context_window': 8192,
        'output_limit': 4096
    },
    'gpt-3.5-turbo': {
        'input': 0.001,
        'output': 0.002,
        'context_window': 16384,
        'output_limit': 4096
    },
}
```

Note: These are approximate rates. Always check current pricing from providers.

## Cost Calculation

### Basic Cost Calculator

```python
class CostCalculator:
    def __init__(self, pricing=PRICING):
        self.pricing = pricing

    def calculate(self, model, input_tokens, output_tokens):
        """Calculate cost for a single LLM call."""
        if model not in self.pricing:
            raise ValueError(f"Unknown model: {model}")

        rates = self.pricing[model]

        input_cost = (input_tokens / 1000) * rates['input']
        output_cost = (output_tokens / 1000) * rates['output']

        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': input_cost + output_cost,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

# Example
calc = CostCalculator()
cost = calc.calculate('claude-opus-4-6', input_tokens=10000, output_tokens=2000)
print(f"Total cost: ${cost['total_cost']:.4f}")  # $0.30
```

### Multi-Agent Cost Tracking

```python
class MultiAgentCostTracker:
    def __init__(self):
        self.calls = []  # All LLM calls
        self.costs_by_agent = defaultdict(float)
        self.costs_by_model = defaultdict(float)

    def record_call(self, agent_id, model, input_tokens, output_tokens):
        """Record a single LLM call."""
        calc = CostCalculator()
        cost_info = calc.calculate(model, input_tokens, output_tokens)

        # Store call details
        self.calls.append({
            'timestamp': datetime.now(),
            'agent_id': agent_id,
            'model': model,
            **cost_info
        })

        # Update aggregates
        self.costs_by_agent[agent_id] += cost_info['total_cost']
        self.costs_by_model[model] += cost_info['total_cost']

    def get_total_cost(self):
        """Get total cost across all calls."""
        return sum(call['total_cost'] for call in self.calls)

    def get_agent_costs(self):
        """Get cost breakdown by agent."""
        return dict(sorted(
            self.costs_by_agent.items(),
            key=lambda x: x[1],
            reverse=True
        ))

    def get_model_costs(self):
        """Get cost breakdown by model."""
        return dict(sorted(
            self.costs_by_model.items(),
            key=lambda x: x[1],
            reverse=True
        ))

    def get_stats(self):
        """Get comprehensive statistics."""
        total_tokens = sum(
            call['input_tokens'] + call['output_tokens']
            for call in self.calls
        )

        return {
            'total_cost': self.get_total_cost(),
            'total_calls': len(self.calls),
            'total_tokens': total_tokens,
            'avg_cost_per_call': self.get_total_cost() / len(self.calls) if self.calls else 0,
            'avg_tokens_per_call': total_tokens / len(self.calls) if self.calls else 0,
            'by_agent': self.get_agent_costs(),
            'by_model': self.get_model_costs()
        }
```

## Budget Management

### Session Budget

```python
class SessionBudget:
    def __init__(self, max_cost=5.0):
        self.max_cost = max_cost
        self.spent = 0.0
        self.calls = []

    def check_and_reserve(self, estimated_cost):
        """Check if we can afford this call."""
        if self.spent + estimated_cost > self.max_cost:
            raise BudgetExceededError(
                f"Would exceed budget: ${self.spent + estimated_cost:.4f} > ${self.max_cost:.4f}"
            )

    def record_actual(self, actual_cost):
        """Record actual cost after call."""
        self.spent += actual_cost
        self.calls.append({
            'timestamp': datetime.now(),
            'cost': actual_cost
        })

    def get_remaining(self):
        """Get remaining budget."""
        return self.max_cost - self.spent

    def get_utilization(self):
        """Get budget utilization percentage."""
        return (self.spent / self.max_cost) * 100

# Usage
budget = SessionBudget(max_cost=1.0)

# Before each call
estimated_cost = estimate_cost(model, estimated_input, estimated_output)
budget.check_and_reserve(estimated_cost)

# After call
actual_cost = calculate_actual_cost(model, actual_input, actual_output)
budget.record_actual(actual_cost)
```

### Tiered Budget System

```python
class TieredBudget:
    """Different budget limits for different user tiers."""

    TIERS = {
        'free': {'daily': 0.10, 'monthly': 2.0},
        'pro': {'daily': 1.0, 'monthly': 25.0},
        'enterprise': {'daily': 10.0, 'monthly': 500.0}
    }

    def __init__(self, user_tier):
        self.tier = user_tier
        self.limits = self.TIERS[user_tier]
        self.daily_spent = 0.0
        self.monthly_spent = 0.0
        self.last_reset = datetime.now()

    def check_budget(self, estimated_cost):
        """Check both daily and monthly budgets."""
        self._reset_if_needed()

        if self.daily_spent + estimated_cost > self.limits['daily']:
            raise DailyBudgetExceeded(
                f"Daily limit: ${self.limits['daily']}"
            )

        if self.monthly_spent + estimated_cost > self.limits['monthly']:
            raise MonthlyBudgetExceeded(
                f"Monthly limit: ${self.limits['monthly']}"
            )

    def record_usage(self, cost):
        self._reset_if_needed()
        self.daily_spent += cost
        self.monthly_spent += cost

    def _reset_if_needed(self):
        now = datetime.now()

        # Reset daily budget
        if now.date() > self.last_reset.date():
            self.daily_spent = 0.0

        # Reset monthly budget
        if now.month != self.last_reset.month:
            self.monthly_spent = 0.0

        self.last_reset = now
```
