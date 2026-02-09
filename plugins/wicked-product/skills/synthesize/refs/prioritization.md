# Prioritization Framework

Detailed framework for translating customer voice into feature priorities.

## Priority Scoring Formula

```
Priority Score = (Customer_Impact × Urgency × Frequency) / Effort

Where:
- Customer_Impact: 1-5 (how much it matters to customers)
- Urgency: 1-5 (time sensitivity)
- Frequency: 1-5 (how often mentioned)
- Effort: 1-5 (implementation complexity)
```

## Customer Impact Scale

**5 - Critical**: Blocking work, causing churn
- "Can't complete my job without this"
- Active cancellations mentioned
- Security or data loss issues

**4 - High**: Major friction, competitive disadvantage
- "This is very frustrating"
- Competitors have it, we don't
- Workarounds are painful

**3 - Medium**: Clear improvement, efficiency gain
- "Would make my work easier"
- Multiple steps could be one
- Quality of life improvement

**2 - Low**: Nice to have, minor convenience
- "Would be cool if..."
- Edge case enhancement
- Aesthetic preference

**1 - Minimal**: Vanity feature, individual preference
- Single user request
- Already have workaround
- No clear benefit

## Urgency Scale

**5 - Immediate**: Losing customers now
- Churn happening
- Escalations from leadership
- Legal/compliance risk

**4 - High**: Competitive pressure
- Competitors launched similar
- Market expectation
- Sales blocker

**3 - Medium**: Growing concern
- Increasing frequency
- Multiple segments affected
- Strategic alignment

**2 - Low**: Future consideration
- On roadmap
- Nice strategic fit
- Minor competitive gap

**1 - None**: No time pressure
- Evergreen request
- No external forcing function
- Can wait indefinitely

## Frequency Scale

**5 - Very High**: >100 mentions
**4 - High**: 50-100 mentions
**3 - Medium**: 20-49 mentions
**2 - Low**: 5-19 mentions
**1 - Minimal**: <5 mentions

Adjust based on total feedback volume (normalize).

## Effort Scale

**5 - Very High**: Major system change, >1 quarter
**4 - High**: Significant work, 4-8 weeks
**3 - Medium**: Standard feature, 2-4 weeks
**2 - Low**: Small enhancement, 1-2 weeks
**1 - Minimal**: Quick fix, <1 week

## Example Calculations

### Example 1: Mobile Performance Issues

```
Customer_Impact: 5 (users can't complete tasks)
Urgency: 4 (competitors have better mobile)
Frequency: 4 (65 mentions in Q1)
Effort: 3 (requires optimization work, not rebuild)

Score = (5 × 4 × 4) / 3 = 26.7

Priority: P0 (Critical)
```

### Example 2: Dark Mode Request

```
Customer_Impact: 2 (aesthetic preference)
Urgency: 1 (no time pressure)
Frequency: 3 (25 mentions over 6 months)
Effort: 2 (CSS changes, relatively quick)

Score = (2 × 1 × 3) / 2 = 3.0

Priority: P3 (Low)
```

### Example 3: Bulk Actions Feature

```
Customer_Impact: 4 (significant time savings for power users)
Urgency: 3 (productivity enhancement)
Frequency: 3 (30 mentions from enterprise segment)
Effort: 3 (new UI, backend changes)

Score = (4 × 3 × 3) / 3 = 12.0

Priority: P1 (High)
```

## Priority Levels

**P0 - Critical**: Score >20, or any churn risk
- Address immediately
- Communicate timeline to customers
- Fast-track through development

**P1 - High**: Score 10-20
- Next 1-2 sprints
- Include in quarterly roadmap
- Update requesting customers

**P2 - Medium**: Score 5-10
- Roadmap consideration
- Batch with similar work
- Acknowledge to customers

**P3 - Low**: Score <5
- Backlog item
- Revisit if frequency increases
- Polite decline or defer

## Segment Weighting

Adjust impact based on customer segment:

```
Enterprise: 2× multiplier (higher revenue, strategic)
Growth: 1.5× multiplier (expansion potential)
SMB: 1× multiplier (baseline)
Free/Trial: 0.5× multiplier (not yet revenue)
```

## Quick Win Identification

Quick wins have:
- Score >8 (meaningful impact)
- Effort ≤2 (quick implementation)
- Clear customer benefit

These should be called out separately for morale and momentum.

## Validation Questions

Before finalizing recommendation:

1. **Is this a real need or symptom?**
   - Feature request might mask underlying UX issue

2. **Will this solve the actual problem?**
   - Validate with customer examples

3. **Are we building for the vocal minority?**
   - Check segment distribution

4. **What's the opportunity cost?**
   - What else could we build instead?

5. **Is there a simpler solution?**
   - Configuration change, documentation, existing feature
