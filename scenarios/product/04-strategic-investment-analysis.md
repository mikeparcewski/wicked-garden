---
name: strategic-investment-analysis
title: ROI Analysis for Technical Investment
description: Evaluate business case for a major technical initiative with multi-perspective analysis
type: strategy
difficulty: advanced
estimated_minutes: 15
---

# ROI Analysis for Technical Investment

This scenario tests wicked-product's strategic analysis capabilities: calculating ROI, assessing value proposition, analyzing competitive landscape, and providing investment recommendations.

## Setup

Create a realistic technical initiative proposal:

```bash
# Create test project
mkdir -p ~/test-wicked-product/strategy-analysis
cd ~/test-wicked-product/strategy-analysis

# Create initiative proposal
cat > platform-rewrite.md <<'EOF'
# Technical Initiative: Platform Modernization

## Executive Summary
Rewrite our legacy PHP monolith to a modern microservices architecture using Go and React.

## Current State
- 8-year-old PHP codebase (Laravel)
- 500K lines of code
- 15 developers struggle with velocity
- Average feature delivery: 6 weeks
- Deployment frequency: 2x/month
- Critical bug rate: 8/month

## Proposed State
- Microservices in Go
- React frontend with TypeScript
- CI/CD pipeline with daily deployments
- Feature delivery target: 2 weeks

## Investment Required
- 18-month project
- 8 senior engineers full-time
- 2 DevOps engineers
- External consulting: $200K
- Infrastructure migration: $150K

## Expected Benefits
- 3x faster feature delivery
- Reduced maintenance costs
- Improved developer retention
- Scale to 10x current traffic
- Enable mobile app development

## Risks
- Business disruption during migration
- Knowledge transfer from legacy team
- Scope creep (common in rewrites)
- Opportunity cost of not building features

## Request
Approve $2.5M investment over 18 months
EOF

# Create context about company situation
cat > company-context.md <<'EOF'
# Company Context

## Business Metrics
- ARR: $15M
- Growth: 25% YoY
- Gross margin: 70%
- Customer count: 500 (B2B SaaS)
- Churn: 8% annually

## Competition
- Market leader has modern platform
- Two competitors released mobile apps last year
- We're seen as "reliable but slow"

## Team
- 25 engineers total
- 5 in legacy codebase
- High turnover in legacy team (40%)
- Difficult to hire PHP developers

## Recent History
- Failed microservices attempt 3 years ago
- CEO publicly committed to "platform modernization"
- Board asking about technical debt
EOF
```

## Steps

1. **Run Full Strategic Analysis**
   ```bash
   /wicked-product:strategy platform-rewrite.md --focus all
   ```

   **Expected**: Analysis from multiple perspectives:
   - ROI calculation with payback period
   - Value proposition assessment
   - Competitive positioning analysis
   - Market timing evaluation
   - Risk assessment with mitigations

2. **Verify ROI Calculation**

   Check for realistic financial analysis:
   ```
   Investment: $2.5M over 18 months

   Quantified benefits:
   - Engineering efficiency (3x velocity = X dollars)
   - Reduced turnover costs (40% -> Y% = Z savings)
   - Maintenance cost reduction

   ROI = (Benefits - Costs) / Costs
   Payback Period = Investment / Annual Benefit
   ```

   Should flag what can and cannot be quantified.

3. **Check Value Proposition Analysis**

   The value-analyst should evaluate:
   - What's the real problem being solved?
   - Is "modern architecture" the solution or the goal?
   - Alternative approaches (incremental modernization?)
   - Differentiation: Does this create competitive advantage?

4. **Verify Competitive Assessment**

   The competitive-analyst should note:
   - Competitors with modern platforms
   - Mobile app gap
   - "Reliable but slow" perception
   - Risk of falling further behind

5. **Check Risk Analysis**

   Should identify:
   - Second-system effect (rewrite scope creep)
   - Previous failed attempt
   - 18-month projects rarely finish on time
   - Opportunity cost calculation

6. **Verify Recommendation Quality**

   The recommendation should be:
   - Clear: PROCEED / CONDITIONAL / REJECT
   - Confidence-rated
   - With specific conditions if CONDITIONAL
   - Alternative approaches if REJECT

## Expected Outcome

- Comprehensive analysis covering ROI, value, competitive, and market
- Quantified where possible, qualified where not
- Honest about assumptions and uncertainties
- Clear recommendation with reasoning
- Alternative approaches considered

## Success Criteria

- [ ] ROI calculation attempts to quantify developer productivity gains
- [ ] Payback period estimated (even with uncertainty range)
- [ ] Previous failed attempt mentioned as risk factor
- [ ] Incremental modernization suggested as alternative
- [ ] Opportunity cost of 18-month feature freeze addressed
- [ ] Competitive pressure acknowledged (mobile gap, perception)
- [ ] Recommendation has confidence level
- [ ] Key assumptions listed for stakeholder validation
- [ ] Analysis distinguishes facts vs assumptions
- [ ] Output includes risk mitigation strategies

## Value Demonstrated

**Real-world value**: Major technical investments often get approved (or rejected) based on vibes rather than analysis. Engineers say "we need to rewrite" while finance asks "what's the ROI?" and neither speaks the other's language.

wicked-product's `/strategy` command bridges this gap by providing:
- Financial analysis that engineering teams don't typically produce
- Technical context that finance teams don't typically understand
- Multi-perspective view that avoids confirmation bias
- Honest uncertainty acknowledgment (not fake precision)

This replaces expensive consulting engagements for investment analysis, while providing the structured business case that leadership needs to make informed decisions. The conditional recommendations with specific criteria help move from "should we do this?" to "under what conditions should we proceed?"

For teams that have been burned by failed rewrites or underfunded modernization efforts, this analysis framework helps set realistic expectations and success criteria upfront.
