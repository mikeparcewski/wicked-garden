# Statistical Testing Methods

Detailed statistical methods for analyzing experiment results.

## Z-Test for Proportions

Used for binary outcomes (conversion, click, signup).

### Formula

```
z = (p₁ - p₂) / SE

Where:
- p₁, p₂ = sample proportions
- SE = √(p(1-p)(1/n₁ + 1/n₂))
- p = pooled proportion = (x₁ + x₂) / (n₁ + n₂)
```

### Example

```
Control: 120 / 1200 = 10.0%
Treatment: 138 / 1200 = 11.5%

Pooled: (120 + 138) / 2400 = 10.75%
SE = √(0.1075 × 0.8925 × (1/1200 + 1/1200)) = 0.0126

z = (0.115 - 0.100) / 0.0126 = 1.19

p-value = 0.234 (not significant at α=0.05)
```

### When to Use

- Binary outcomes (yes/no, click/no-click)
- Large sample sizes (n > 30)
- Independent observations

## T-Test for Means

Used for continuous outcomes (revenue, time, ratings).

### Formula

```
t = (x̄₁ - x̄₂) / SE

Where:
- x̄₁, x̄₂ = sample means
- SE = √(s₁²/n₁ + s₂²/n₂)
- s₁², s₂² = sample variances
```

### Example

```
Control: mean = $50, SD = $15, n = 1200
Treatment: mean = $52, SD = $16, n = 1200

SE = √(15²/1200 + 16²/1200) = 0.635

t = (52 - 50) / 0.635 = 3.15

p-value = 0.002 (significant at α=0.05)
```

### When to Use

- Continuous outcomes
- Normally distributed data (or large samples)
- Independent observations

## Chi-Square Test

Used for categorical outcomes with multiple categories.

### Formula

```
χ² = Σ (Observed - Expected)² / Expected
```

### Example

```
Control: Category A=300, B=400, C=500
Treatment: Category A=350, B=380, C=470

Calculate expected counts, compute χ²
Compare to critical value at df=(rows-1)×(cols-1)
```

### When to Use

- Multiple categories (not just binary)
- Testing independence or goodness-of-fit
- Large expected counts (all cells > 5)

## Confidence Intervals

### For Proportions

```
CI = p ± Z × √(p(1-p)/n)

For 95% confidence: Z = 1.96
For 90% confidence: Z = 1.645
For 99% confidence: Z = 2.576
```

### For Means

```
CI = x̄ ± t × (s/√n)

Where t is from t-distribution with df=n-1
```

### Interpretation

95% CI: [0.05, 0.25] means:
- We're 95% confident the true lift is between 5% and 25%
- If interval doesn't include 0, result is significant

## Bayesian Analysis

Alternative to frequentist methods.

### Beta Distribution (for proportions)

**Prior**: Beta(α, β)
- Uniform: Beta(1, 1)
- Informative: Beta(α=conversions, β=non-conversions from historical data

**Posterior**: Beta(α + conversions, β + non-conversions)

### Calculating Probability Treatment Beats Control

Monte Carlo simulation:
1. Sample 10,000 values from control posterior
2. Sample 10,000 values from treatment posterior
3. P(treatment > control) = % of samples where treatment > control

### Example Output

```
Probability treatment beats control: 94.2%
Expected lift: 12.5% (credible interval: 8.1% to 16.9%)
```

### When to Use

- Want direct probability statements
- Need to monitor continuously
- Have informative prior knowledge
- Early-stage rapid iteration

## Multiple Testing Correction

### Bonferroni Correction

```
Adjusted α = α / number_of_tests

For 3 metrics with α=0.05:
Adjusted α = 0.05 / 3 = 0.017
```

**Problem**: Very conservative, reduces power.

### False Discovery Rate (FDR)

More powerful alternative to Bonferroni.

**Benjamini-Hochberg procedure**:
1. Sort p-values: p₁ ≤ p₂ ≤ ... ≤ pₘ
2. Find largest i where pᵢ ≤ (i/m)α
3. Reject H₀ for p₁, ..., pᵢ

**Interpretation**: Controls proportion of false discoveries among rejections.

### Best Practice

**Designate ONE primary metric** before experiment starts.
- No correction needed for single primary
- Secondary/guardrail metrics are exploratory

## Sequential Testing

For continuous monitoring without inflated Type I error.

### Group Sequential Design

Pre-define interim analysis points:
- After 25% of data
- After 50% of data
- After 75% of data
- Final analysis at 100%

Adjust critical values at each stage (e.g., O'Brien-Fleming boundaries).

### Sequential Probability Ratio Test (SPRT)

Continuous monitoring with stopping boundaries:
- Upper boundary: strong evidence for treatment
- Lower boundary: strong evidence for control
- Continue: insufficient evidence

**Advantage**: Can stop early if clear winner.
**Disadvantage**: Requires pre-specification of boundaries.

## Effect Size Measures

Beyond statistical significance.

### Cohen's d

Standardized mean difference:
```
d = (x̄₁ - x̄₂) / pooled_SD

Interpretation:
- 0.2 = small effect
- 0.5 = medium effect
- 0.8 = large effect
```

### Relative vs Absolute

**Absolute**: 10% → 11% = +1 percentage point
**Relative**: 10% → 11% = +10% relative lift

Both matter:
- Absolute for business impact (1% of 1M users = 10k users)
- Relative for understanding magnitude (10% improvement)

## Statistical Power Analysis

Post-hoc power calculation.

```
Power = P(reject H₀ | H₁ is true)

Calculate from:
- Achieved sample size
- Observed effect size
- Significance level
```

**Interpretation**:
- Power = 85%: If true effect exists, 85% chance we'd detect it
- Low power + non-significant result = inconclusive (not "no effect")

## Data Quality Checks

### Sample Ratio Mismatch (SRM)

**Test**: Chi-square test on allocation ratios

```
Expected: 50/50 split
Observed: 1250 control, 1150 treatment

χ² = (1250-1200)²/1200 + (1150-1200)²/1200 = 4.17
p-value = 0.041 (SRM detected!)
```

**Causes**: Bot traffic, client-side bucketing issues, selection bias

### Variance Ratio Test

Check if variances are similar:

```
F = s₁² / s₂²

If F is far from 1, variances differ significantly
```

**Implication**: May need Welch's t-test instead of standard t-test.

### Novelty Effect Detection

Compare first week vs. subsequent weeks:
- Week 1 lift: +25%
- Weeks 2-4 lift: +10%

**Interpretation**: 15% of lift may be novelty, true long-term effect is +10%.

## Reporting Standards

### Minimum Reporting Requirements

1. **Sample sizes**: Per variant
2. **Metrics**: All primary, secondary, guardrail
3. **Statistical tests**: Which tests used
4. **P-values**: For all metrics
5. **Confidence intervals**: For primary metric
6. **Effect sizes**: Absolute and relative
7. **Data quality**: SRM check, duration, anomalies

### Visualization Best Practices

**Forest plot**: Effect sizes with confidence intervals
**Time series**: Metric over time per variant
**Segment analysis**: Heatmap of lift by segment

## Resources

- **Online calculators**:
  - Z-test: https://www.evanmiller.org/ab-testing/z-test.html
  - T-test: Standard statistical software

- **Software**:
  - Python: scipy.stats, statsmodels
  - R: base stats, pwr package
  - JavaScript: jStat library

- **Books**:
  - "Trustworthy Online Controlled Experiments" (Kohavi et al.)
  - "Statistical Methods in Online A/B Testing" (Georgiev)
