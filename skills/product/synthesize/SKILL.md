---
name: synthesize
description: |
  Generate actionable recommendations from customer voice insights. Use when
  you need to translate analyzed feedback into product priorities, feature
  recommendations, or strategic guidance based on customer needs.
---

# Synthesize Skill

Transform customer voice analysis into actionable product recommendations.

## When to Use

- After analyzing customer feedback
- Product planning or roadmap prioritization
- Feature decision support
- User asks "what should we build based on customer feedback"

## Usage

```bash
# Synthesize all recent insights
/wicked-garden:product:synthesize

# Prioritize by impact level
/wicked-garden:product:synthesize --priority high

# Feature-specific synthesis
/wicked-garden:product:synthesize --feature "mobile-app"

# Brief format (for quick decisions)
/wicked-garden:product:synthesize --format brief
```

## Synthesis Framework

### 1. Insight Extraction
Identify: Pain Points, Opportunities, Risks, Strengths

### 2. Recommendation Generation
Score = (Customer_Value × Urgency) / Effort
See [refs/prioritization.md](refs/prioritization.md) for detailed scoring.

### 3. Customer Journey Mapping
Map feedback across: Awareness → Evaluation → Onboarding → Adoption → Retention → Advocacy
See [refs/journey-mapping.md](refs/journey-mapping.md) for stage analysis.

### 4. Priority Levels
- **P0**: Churn risk, blocker, security
- **P1**: Major friction, competitive gap
- **P2**: Enhancement, efficiency
- **P3**: Nice-to-have, edge case

## Output Format

```markdown
## Customer Voice Synthesis: {Context}

### Executive Summary
{2-3 sentences on what customers need most}

### Top Recommendations
1. **{Recommendation}** - {Priority}
   - Impact: {HIGH/MEDIUM/LOW}
   - Evidence: {N} mentions, {sentiment}, {trend}
   - Action: {specific what to do}
   - Effort: {LOW/MEDIUM/HIGH}

{Top 3-5 recommendations}

### Customer Journey Insights
- **Onboarding**: {key pain point or win}
- **Adoption**: {key pain point or win}
- **Retention**: {key pain point or win}

### Strategic Considerations
- **Strengths**: {what to maintain}
- **Risks**: {what threatens retention}
- **Opportunities**: {what could differentiate}

### Quick Wins
{1-3 low-effort, high-impact improvements}

### Long-term Bets
{1-2 strategic investments based on customer needs}
```

## Synthesis Process

1. Load theme and sentiment analysis from `{SM_LOCAL_ROOT}/wicked-product/voice/analysis/`
2. Sort themes by priority score, filter by threshold
3. Generate recommendations: theme → action, score by impact/effort
4. Map to customer journey stages, identify friction points
5. Format output: executive summary first, top 3-5 recommendations

## Integration

**wicked-crew**: Auto-inject synthesis into `product:requirements:started` events
**wicked-mem**: Store high-priority insights as decision memories
**wicked-kanban**: Link recommendations to roadmap tasks

## Rules

- Maximum 5 recommendations (context efficiency)
- Always include effort estimates
- Provide confidence levels (HIGH/MEDIUM/LOW)
- Cite supporting evidence (N mentions, sentiment)
- Distinguish quick wins from strategic bets
- Keep output under 1000 words
- Be honest about unknowns and limitations
