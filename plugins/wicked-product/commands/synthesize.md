---
description: Generate actionable recommendations from customer feedback insights
argument-hint: "[--priority high|medium|low] [--feature X] [--format brief|detailed]"
---

# /wicked-product:synthesize

Generate actionable product recommendations from customer feedback analysis. Translates insights into prioritized action items.

## Usage

```bash
# Synthesize all insights
/wicked-product:synthesize

# Filter by priority
/wicked-product:synthesize --priority high
/wicked-product:synthesize --priority critical

# Focus on specific feature area
/wicked-product:synthesize --feature "mobile-app"
/wicked-product:synthesize --feature "onboarding"

# Output format
/wicked-product:synthesize --format brief
/wicked-product:synthesize --format detailed
```

## Instructions

### 1. Load Analysis Results

Read from recent analyze output or voice data store:

```bash
# Check for analysis results
ls ~/.something-wicked/voice/analysis/
```

If no analysis found, prompt user to run `/wicked-product:analyze` first.

### 2. Dispatch to Customer Advocate for Synthesis

```
Task(
  subagent_type="wicked-product:customer-advocate",
  prompt="""Synthesize customer feedback analysis into actionable recommendations.

## Analysis Data
{themes, sentiment, trends from analyze - include full details}

## Parameters
- Priority filter: {high, medium, low if specified}
- Feature focus: {feature area if specified}

## Task

Generate prioritized recommendations using this framework:

**Prioritization Criteria**:
- Customer Impact: How many customers affected? How severe?
- Frequency: How often is this mentioned?
- Trend: Is this growing or shrinking?
- Effort: Estimated implementation complexity
- Risk: What happens if we don't act?

**Priority Levels**:
- Critical: High impact + growing + churn risk
- High: High impact or many customers affected
- Medium: Moderate impact, stable trend
- Low: Nice-to-have, few mentions

**For Each Recommendation**:
1. Clear action statement
2. Evidence from feedback (quotes, numbers, segments)
3. Expected outcomes (measurable improvements)
4. Risk of inaction
5. Effort estimate (S/M/L/XL)
6. Dependencies

**Also Identify**:
- Quick wins (low effort, high impact)
- Strategic initiatives (high effort, transformative)
- Metrics to track post-implementation

## Return Format

Provide:
- Executive summary (top 3 recommendations)
- Prioritized recommendations by level (critical, high, medium)
- Quick wins table
- Strategic initiatives table
- Metrics to track
- Next steps
"""
)
```

### 3. Present Synthesis

Format the agent's output into the standard synthesis report structure.

```markdown
## Customer Voice Synthesis

### Executive Summary
Based on analysis of {N} feedback items over {period}, we recommend focusing on:

1. **{Critical recommendation}** - {impact statement}
2. **{High priority recommendation}** - {impact statement}
3. **{Medium priority recommendation}** - {impact statement}

### Prioritized Recommendations

#### Critical Priority

##### 1. {Recommendation Title}
**Action**: {Clear, specific action to take}

**Evidence**:
- {N} customers reported this issue
- Sentiment: {score}, trending {direction}
- Segment most affected: {segment}

**Customer Quotes**:
> "{representative quote}"
> "{another quote}"

**Expected Outcome**:
- {Measurable improvement}
- {Customer satisfaction impact}

**Risk of Inaction**:
- {Churn risk, competitive disadvantage, etc.}

**Effort**: {S/M/L/XL}
**Dependencies**: {related work}

#### High Priority

##### 2. {Recommendation Title}
{Same structure as above}

#### Medium Priority

##### 3. {Recommendation Title}
{Same structure as above}

### Quick Wins
Actions that can be taken immediately with low effort:

| Action | Impact | Effort | Timeline |
|--------|--------|--------|----------|
| {action} | {impact} | S | This week |

### Strategic Initiatives
Larger efforts requiring planning:

| Initiative | Impact | Effort | Timeline |
|------------|--------|--------|----------|
| {initiative} | {impact} | XL | Q2 |

### Metrics to Track
After implementing recommendations, measure:

| Metric | Current | Target | Timeframe |
|--------|---------|--------|-----------|
| {metric} | {value} | {target} | {when} |

### Next Steps
1. Review recommendations with stakeholders
2. Prioritize based on roadmap capacity
3. Create tasks in kanban for approved items
4. Set up feedback monitoring for validation
```

## Integration

- **wicked-product:listen**: Aggregates feedback
- **wicked-product:analyze**: Extracts insights
- **wicked-kanban**: Create tasks for approved recommendations
- **wicked-crew**: Feed into planning phases
- **wicked-mem**: Store decisions for future reference

## Example

```
User: /wicked-product:synthesize --priority high

Claude: I'll synthesize high-priority recommendations from customer feedback.

[Loads analysis results]
[Dispatches to customer-advocate agent]
[Agent generates prioritized recommendations]

## Customer Voice Synthesis

### Executive Summary
Based on analysis of 156 feedback items over the last 30 days:

1. **Fix dashboard performance regression** - 45 complaints, 3 churn signals
2. **Improve mobile app stability** - 28 crashes reported, NPS -15 for mobile
3. **Add bulk export feature** - Top feature request, 12 enterprise customers

### Critical Priority

#### 1. Fix Dashboard Performance Regression
**Action**: Investigate and fix dashboard load time regression. Target <2s load time.

**Evidence**:
- 45 customers reported slow dashboard (28% of all feedback)
- Sentiment: -0.6, trending worse (up 40% from last month)
- Segment most affected: Enterprise (avg 5+ users per account)

**Customer Quotes**:
> "Dashboard went from instant to 10+ seconds. What happened?"
> "I can't do my job when I'm staring at a loading spinner."

**Expected Outcome**:
- Reduce load time to <2s (from current 8s)
- Improve NPS by 10+ points for dashboard users
- Reduce support tickets by ~30/month

**Risk of Inaction**:
- 3 enterprise customers mentioned evaluating alternatives
- Support burden increasing unsustainably

**Effort**: M
**Dependencies**: Engineering investigation needed first

---

Stored in kanban: synthesis-001
Ready for stakeholder review
```

## Voice Workflow

Complete customer voice workflow:

```bash
# 1. Aggregate feedback
/wicked-product:listen --days 30

# 2. Analyze for themes and trends
/wicked-product:analyze

# 3. Generate recommendations
/wicked-product:synthesize

# 4. Create tasks for approved items
# (Automatically offered after synthesis)
```
