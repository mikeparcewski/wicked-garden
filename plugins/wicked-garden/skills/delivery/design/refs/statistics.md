# Statistical Concepts for Experiments

Deep dive into the statistical foundations of A/B testing.

## Sample Size Calculation

### Basic Formula

For comparing two proportions (e.g., conversion rates):

```
n = (Z_α/2 + Z_β)² × (p₁(1-p₁) + p₂(1-p₂)) / (p₁ - p₂)²

Where:
- n = sample size per variant
- Z_α/2 = critical value for significance level (1.96 for α=0.05)
- Z_β = critical value for power (0.84 for 80% power)
- p₁ = baseline conversion rate
- p₂ = expected conversion rate after treatment
```

### Simplified Formula

```
n ≈ 16 × p(1-p) / (MDE)²

Where:
- p = baseline proportion
- MDE = minimum detectable effect (as decimal)
```

### Example

Baseline conversion: 10%
Desired lift: 10% relative (1% absolute)
MDE = 0.01

```
n ≈ 16 × 0.10 × 0.90 / (0.01)²
n ≈ 16 × 0.09 / 0.0001
n ≈ 14,400 per variant
```

## Rules of Thumb

| MDE (relative) | Sample Size per Variant |
|----------------|------------------------|
| 5% | ~3,200 |
| 10% | ~800 |
| 15% | ~350 |
| 20% | ~200 |
| 30% | ~90 |

Assumes:
- Baseline conversion ~10%
- 95% confidence (α = 0.05)
- 80% power (β = 0.20)

## Statistical Significance

### P-Value

Probability of observing results at least as extreme as those measured, assuming null hypothesis is true.

**Interpretation**:
- p < 0.05: Reject null hypothesis (result is "significant")
- p ≥ 0.05: Fail to reject null (not enough evidence)

**Common mistake**: p-value is NOT the probability the null hypothesis is true.

### Confidence Interval

Range of plausible values for the true effect.

**Example**:
```
Treatment conversion: 11.5%
Control conversion: 10.0%
Lift: 1.5% ± 0.8% (95% CI)
```

**Interpretation**:
- We're 95% confident the true lift is between 0.7% and 2.3%
- Since interval doesn't include 0, result is significant

### Effect Size

Magnitude of the difference, independent of sample size.

**Cohen's d** (standardized effect size):
```
d = (mean₁ - mean₂) / pooled_standard_deviation

Interpretation:
- 0.2 = small effect
- 0.5 = medium effect
- 0.8 = large effect
```

## Common Pitfalls

### 1. Peeking Problem

**Issue**: Checking results early and stopping when significant inflates false positive rate.

**Solution**:
- Pre-define sample size and duration
- Use sequential testing methods
- Apply multiple testing corrections

### 2. Multiple Testing

**Issue**: Testing multiple metrics or variants increases chance of false positives.

**Bonferroni correction**:
```
Adjusted α = α / number_of_tests

For 3 metrics: α = 0.05 / 3 = 0.017
```

**Better approach**: Designate ONE primary metric pre-experiment.

### 3. Simpson's Paradox

**Issue**: Aggregate results show opposite trend from subgroups.

**Example**:
- Overall: Treatment worse
- Desktop: Treatment better
- Mobile: Treatment better

**Cause**: Different sample sizes or baseline rates in segments.

**Solution**: Analyze by segment, weight appropriately.

### 4. Novelty Effect

**Issue**: Users react to newness, not inherent quality.

**Solution**: Run experiment for 2+ weeks to allow novelty to wear off.

### 5. Seasonality

**Issue**: Results affected by time-of-week or seasonal patterns.

**Solution**: Run for complete weeks, avoid major holidays.

## Statistical Power

Probability of detecting an effect when it exists (1 - β).

**Factors affecting power**:
- Sample size (larger = more power)
- Effect size (larger = more power)
- Variance (lower = more power)
- Significance level (higher α = more power, but more false positives)

**Common values**:
- 80% power (β = 0.20): Standard
- 90% power (β = 0.10): High stakes decisions
- 70% power (β = 0.30): Exploratory tests

## Bayesian Approach

Alternative to frequentist (p-value) methods.

**Advantages**:
- Directly answers "What's the probability treatment is better?"
- Can incorporate prior beliefs
- More intuitive interpretation

**Output**:
- Probability treatment beats control: 95%
- Expected lift: 12% (credible interval: 8-16%)

**When to use**:
- Early-stage products (informative priors)
- Rapid iteration (continuous monitoring)
- Business stakeholders prefer direct probabilities

## Minimum Detectable Effect (MDE)

Smallest effect size you can reliably detect.

**Trade-offs**:
- Smaller MDE requires larger sample size
- Smaller MDE means longer experiments
- Smaller MDE costs more resources

**Choosing MDE**:
1. What lift justifies engineering effort?
2. What's the smallest commercially meaningful change?
3. What's feasible given traffic constraints?

**Example**:
- Product decision: "Need 10% lift to justify redesign"
- MDE = 10%
- This is business-driven, not statistical

## Duration Estimation

```
Duration = (Sample Size per Variant × 2) / (Daily Users × Traffic %)

Example:
- Need: 800 per variant (1,600 total)
- Daily users: 10,000
- Traffic: 20% to experiment
- Duration = 1,600 / (10,000 × 0.20) = 0.8 days ≈ 1 day
```

**Minimum duration**: 1 week (to capture weekly patterns)

## A/A Testing

Run experiment with identical variants to validate:
- Randomization works correctly
- No systematic biases
- Statistical framework is sound

**Expected results**:
- No significant differences
- ~5% of metrics may show p < 0.05 by chance
- Confidence intervals should include 0

**When to run**: Before first real experiment, after major instrumentation changes.

## Resources

- **Sample size calculators**:
  - Evan Miller: https://www.evanmiller.org/ab-testing/sample-size.html
  - Online calculators (search "AB test sample size calculator")

- **Statistical testing**:
  - Z-test for proportions
  - T-test for continuous metrics
  - Chi-square for categorical data

- **Books**:
  - "Trustworthy Online Controlled Experiments" (Kohavi et al.)
  - "Statistical Methods in Online A/B Testing" (Georgi Georgiev)
