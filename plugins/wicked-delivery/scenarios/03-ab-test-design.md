---
name: ab-test-design
title: A/B Test Experiment Design
description: Design a statistically rigorous experiment with hypothesis, metrics, and sample size
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# A/B Test Experiment Design

This scenario validates that wicked-delivery can help product teams design statistically rigorous experiments, from hypothesis formulation through instrumentation planning.

## Setup

Create a context that simulates a product team wanting to test a new checkout feature:

```bash
# Create test project directory
mkdir -p ~/test-wicked-delivery/checkout-experiment
cd ~/test-wicked-delivery/checkout-experiment

# Create a feature spec document
cat > feature-spec.md <<'EOF'
# Feature: One-Click Checkout

## Background
Currently, our checkout flow requires 3 steps:
1. Review cart
2. Enter shipping details
3. Confirm and pay

Hypothesis: Returning customers with saved shipping info could skip steps 1-2.

## Proposed Change
Add "Buy Now" button on product pages for logged-in users with saved payment method.

## Business Context
- Current checkout conversion: 68%
- Cart abandonment rate: 32%
- Average order value: $47
- Monthly checkout attempts: ~50,000

## Questions
- Will this increase conversion?
- Will it decrease average order value (impulse purchases)?
- What's the risk of accidental purchases?
EOF

# Create existing analytics setup file
cat > analytics.json <<'EOF'
{
  "provider": "mixpanel",
  "events": {
    "checkout_started": "User began checkout flow",
    "checkout_completed": "User completed purchase",
    "cart_abandoned": "User left without purchasing"
  },
  "properties": {
    "user_type": "new|returning",
    "has_saved_payment": "boolean",
    "cart_value": "float"
  }
}
EOF

# Create feature flag configuration
cat > feature-flags.yaml <<'EOF'
flags:
  one_click_checkout:
    description: Enable one-click checkout for returning users
    type: boolean
    default: false
    targeting:
      - rule: has_saved_payment
        value: true
EOF

echo "Setup complete. Experiment context created."
```

## Steps

### 1. Formulate Hypothesis

Ask the experiment designer to create a testable hypothesis:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="I want to test one-click checkout for returning customers. Help me formulate a proper hypothesis. Context is in feature-spec.md"
```

**Expected Output**:
- Structured hypothesis following format:
  ```
  "[Action] will [increase/decrease] [Metric] by [Amount] because [Reason]"
  ```
- Example: "Adding one-click checkout for returning customers with saved payment methods will increase checkout conversion by 8% because it reduces friction and abandonment at shipping/payment steps"
- Hypothesis is specific, measurable, and testable

### 2. Select Metrics

Define what success looks like:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="What metrics should we track for this experiment? I need primary, secondary, and guardrail metrics."
```

**Expected Output**:
- **Primary metric**: Checkout conversion rate (the ONE metric determining success)
- **Secondary metrics**:
  - Time to purchase
  - Average order value
  - Return rate / refund rate
- **Guardrail metrics** (must not degrade):
  - Error rate
  - Customer support tickets
  - Accidental purchase complaints
- Rationale for each metric selection

### 3. Calculate Sample Size

Determine statistical requirements:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="Calculate the sample size needed to detect an 8% improvement in conversion. Our baseline conversion is 68%. We want 95% confidence and 80% power."
```

**Expected Output**:
- Sample size calculation with reasoning:
  - Baseline conversion: 68%
  - Target conversion: 73.4% (68% + 8% relative improvement)
  - Minimum detectable effect: 5.4 percentage points
  - Sample size per variant: ~X users
  - Total sample needed: ~2X users
- Duration estimate based on traffic:
  - Monthly checkout attempts: 50,000
  - At 100% traffic: X days
  - At 50% traffic: 2X days (recommended)
- Statistical parameters documented (significance, power)

### 4. Design Variants

Define control and treatment:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="Define the control and treatment variants for this experiment. What exactly will each group see?"
```

**Expected Output**:
- **Control** (50% of eligible users):
  - Standard 3-step checkout flow
  - No "Buy Now" button
  - All existing UI unchanged
- **Treatment** (50% of eligible users):
  - "Buy Now" button on product pages
  - One-click purchase for saved payment users
  - Skip to order confirmation
- Clear distinction between variants
- Mutual exclusivity confirmed

### 5. Plan Instrumentation

Create tracking plan:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="What events do I need to instrument for this experiment? Create a tracking plan."
```

**Expected Output**:
```javascript
// Variant assignment event
trackEvent('experiment_viewed', {
  experiment: 'one_click_checkout_v1',
  variant: 'control' | 'treatment',
  user_id: '...',
  has_saved_payment: true
})

// Primary metric events
trackEvent('buy_now_clicked', {...})  // Treatment only
trackEvent('checkout_completed', {
  experiment: 'one_click_checkout_v1',
  variant: '...',
  order_value: 47.99,
  time_to_purchase_seconds: 45
})

// Guardrail events
trackEvent('accidental_purchase_reported', {...})
trackEvent('support_ticket_opened', {category: 'checkout'})
```

### 6. Generate Full Experiment Design

Request the complete design document:

```
Task tool: subagent_type="wicked-delivery:experiment-designer"
prompt="Generate a complete experiment design document I can share with the team."
```

**Expected Output**:
A comprehensive markdown document including:
- Hypothesis
- Metrics (primary, secondary, guardrail)
- Variants description
- Sample size and duration
- Statistical parameters
- Instrumentation plan
- Success criteria
- Risks and mitigations
- Next steps checklist

## Expected Outcome

- Experiment design follows statistical best practices
- Hypothesis is specific and testable
- Metrics hierarchy (primary/secondary/guardrail) clearly defined
- Sample size calculated with stated assumptions
- Instrumentation plan is implementable
- Risks acknowledged with mitigations
- Document is shareable with stakeholders

## Success Criteria

- [ ] Hypothesis follows "[Action] will [effect] [metric] by [amount] because [reason]" format
- [ ] Primary metric is ONE metric (not multiple)
- [ ] Guardrail metrics protect against unintended consequences
- [ ] Sample size calculation includes confidence level and power
- [ ] Duration estimate based on actual traffic numbers (50,000/month)
- [ ] Control and treatment variants clearly distinguished
- [ ] Instrumentation includes variant assignment tracking
- [ ] Instrumentation includes primary metric measurement
- [ ] Statistical significance threshold stated (typically p < 0.05)
- [ ] Success criteria define what "winning" means (both statistical and practical)

## Value Demonstrated

**Real-world value**: Product teams often run experiments without statistical rigor - "let's try it and see what happens." This leads to:
- Inconclusive results (underpowered tests)
- False positives (stopping too early)
- Wasted engineering time (building features that don't move metrics)
- Missed opportunities (killing features that were actually working)

wicked-delivery's experiment design capabilities provide:

1. **Statistical rigor**: Proper hypothesis formulation prevents vague "we think it's better"
2. **Sample size discipline**: Know upfront how long the test needs to run
3. **Metric hierarchy**: Primary metric prevents gaming and p-hacking
4. **Guardrail protection**: Catch negative side effects before they cause harm
5. **Documentation**: Shareable design document aligns stakeholders before build

For product teams running multiple experiments per quarter, this discipline compounds. Each well-designed experiment produces actionable insights, while poorly designed experiments produce noise. The experiment-designer agent embeds the statistical thinking that senior data scientists bring to experiment reviews.

## Integration Notes

**With wicked-kanban**: Stores experiment design as task comments for tracking
**With wicked-mem**: Recalls past experiment patterns and learnings
**With wicked-product**: Uses product context for hypothesis formation
**Standalone**: Works with provided context documents

## Cleanup

```bash
rm -rf ~/test-wicked-delivery/checkout-experiment
```
