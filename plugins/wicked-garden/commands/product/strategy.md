---
description: Strategic analysis - ROI, value proposition, market, competitive
argument-hint: "<target> [--focus roi|value|market|competitive|all]"
---

# /wicked-garden:product-strategy

Strategic business analysis covering ROI calculation, value proposition design, market analysis, and competitive assessment.

## Usage

```bash
# Full strategic analysis
/wicked-garden:product-strategy feature-proposal.md

# Specific focus areas
/wicked-garden:product-strategy feature.md --focus roi
/wicked-garden:product-strategy feature.md --focus value
/wicked-garden:product-strategy feature.md --focus market
/wicked-garden:product-strategy feature.md --focus competitive

# Comprehensive analysis
/wicked-garden:product-strategy initiative.md --focus all

# Quick assessment
/wicked-garden:product-strategy idea.md --quick
```

## Focus Areas

| Focus | Expert | What It Analyzes |
|-------|--------|------------------|
| `roi` | Business Strategist | Costs, benefits, payback period |
| `value` | Value Analyst | Value proposition, differentiation |
| `market` | Market Analyst | Market size, trends, timing |
| `competitive` | Competitive Analyst | SWOT, alternatives, positioning |
| `all` | All experts | Comprehensive strategic view |

## Instructions

### 1. Parse Arguments and Read Context

Parse the `--focus` flag (roi, value, market, competitive, all) and read the target document or feature description to understand:
- What is being proposed?
- What problem does it solve?
- Who is the target audience?
- What resources are needed?

### 2. Dispatch Strategic Experts

Based on the `--focus` flag, dispatch to the appropriate expert(s) in parallel. If `--focus all`, dispatch to all four experts.

**For roi focus**:
```
Task(
  subagent_type="wicked-garden:product/business-strategist",
  prompt="""Calculate ROI for the following feature/initiative:

{feature/initiative description}

## Analysis Required

1. Implementation costs (engineering, design, ops)
2. Expected benefits (revenue, efficiency, retention)
3. Payback period
4. Risk-adjusted returns
5. Opportunity cost of not doing

## Return Format

Provide:
- Investment Required (breakdown by category, one-time + ongoing)
- Expected Returns (breakdown by benefit, years 1-3)
- Financial Summary (payback period, 3-year ROI, NPV, risk level)
- Key assumptions to validate
"""
)
```

**For value focus**:
```
Task(
  subagent_type="wicked-garden:product/value-analyst",
  prompt="""Design value proposition for the following feature/initiative:

{feature/initiative description}

## Analysis Required

1. Customer benefits (functional, emotional, social)
2. Pain points addressed
3. Differentiation from alternatives
4. Unique value elements
5. Value communication strategy

## Return Format

Provide:
- Customer Value Map (benefit type, description, importance)
- Pain Points Addressed (how we solve them)
- Differentiation (comparison with competitors)
- Value Statement (for X who Y, our Z provides A unlike B because C)
"""
)
```

**For market focus**:
```
Task(
  subagent_type="wicked-garden:product/market-analyst",
  prompt="""Analyze market for the following feature/initiative:

{feature/initiative description}

## Analysis Required

1. Total addressable market (TAM)
2. Serviceable addressable market (SAM)
3. Target market segment
4. Market trends and timing
5. Growth trajectory

## Return Format

Provide:
- Market Sizing (TAM, SAM, SOM with sources)
- Market Trends (with implications)
- Timing Assessment (market readiness, our timing)
"""
)
```

**For competitive focus**:
```
Task(
  subagent_type="wicked-garden:product/competitive-analyst",
  prompt="""Assess competitive landscape for the following feature/initiative:

{feature/initiative description}

## Analysis Required

1. Direct competitors
2. Indirect alternatives
3. SWOT analysis
4. Competitive positioning
5. Sustainable advantages

## Return Format

Provide:
- SWOT Matrix (strengths, weaknesses, opportunities, threats)
- Competitive Positioning (competitor vs us vs our advantage)
- Sustainable Advantages (why hard to copy)
"""
)
```

### 3. Present Analysis

```markdown
## Strategic Analysis: {target}

### Executive Summary
**Recommendation**: {Proceed|Proceed with Caution|Defer|Do Not Proceed}
**Confidence**: {High|Medium|Low}
**Key Insight**: {one-line strategic insight}

### ROI Analysis {if reviewed}

#### Investment Required
| Category | One-Time | Ongoing/Year |
|----------|----------|--------------|
| Engineering | ${X} | ${Y} |
| Design | ${X} | ${Y} |
| Operations | ${X} | ${Y} |
| **Total** | **${X}** | **${Y}** |

#### Expected Returns
| Benefit | Year 1 | Year 2 | Year 3 |
|---------|--------|--------|--------|
| Revenue | ${X} | ${X} | ${X} |
| Cost Savings | ${X} | ${X} | ${X} |
| **Total** | **${X}** | **${X}** | **${X}** |

#### Financial Summary
- **Payback Period**: {months}
- **3-Year ROI**: {percentage}
- **NPV**: ${value}
- **Risk Level**: {Low|Medium|High}

### Value Proposition {if reviewed}

#### Customer Value Map
| Benefit Type | Description | Importance |
|--------------|-------------|------------|
| Functional | {benefit} | {High|Med|Low} |
| Emotional | {benefit} | {High|Med|Low} |
| Social | {benefit} | {High|Med|Low} |

#### Pain Points Addressed
1. **{Pain Point}**: {How we solve it}

#### Differentiation
| Factor | Us | Competitor A | Competitor B |
|--------|------|--------------|--------------|
| {factor} | {value} | {value} | {value} |

#### Value Statement
> For {target customer} who {need}, our {product/feature}
> provides {benefit} unlike {alternative} because {differentiator}.

### Market Analysis {if reviewed}

#### Market Sizing
| Metric | Value | Source |
|--------|-------|--------|
| TAM | ${X}B | {source} |
| SAM | ${X}M | {source} |
| SOM | ${X}M | {source} |

#### Market Trends
- **{Trend}**: {implication for us}

#### Timing Assessment
**Market Readiness**: {Early|Growing|Mature|Declining}
**Our Timing**: {Too Early|Right Time|Late|Too Late}

### Competitive Analysis {if reviewed}

#### SWOT Matrix
| Strengths | Weaknesses |
|-----------|------------|
| {strength} | {weakness} |

| Opportunities | Threats |
|---------------|---------|
| {opportunity} | {threat} |

#### Competitive Positioning
| Competitor | Positioning | Our Advantage |
|------------|-------------|---------------|
| {name} | {their position} | {our edge} |

#### Sustainable Advantages
1. **{Advantage}**: {why hard to copy}

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {risk} | {H|M|L} | {H|M|L} | {strategy} |

### Recommendations

#### If Proceed
1. {First action}
2. {Second action}

#### Success Metrics
| Metric | Target | Timeframe |
|--------|--------|-----------|
| {metric} | {value} | {when} |

#### Key Assumptions to Validate
- [ ] {assumption that must be true}
```

## Quick Mode

With `--quick` flag:
- High-level assessment only
- Skip detailed calculations
- Focus on go/no-go signals

```markdown
## Quick Strategic Assessment: {target}

### Verdict: {Go|Caution|No-Go}

**For**:
- {key reason to proceed}

**Against**:
- {key risk or concern}

**Key Question**: {most important thing to validate}

Run `/wicked-garden:product-strategy {target} --focus all` for complete analysis.
```

## Integration

- **wicked-garden:product-elicit**: Feed requirements into strategy
- **wicked-crew**: Strategic analysis in clarify phase
- **wicked-kanban**: Track strategic decisions
- **wicked-mem**: Store decisions for future reference

## Example

```
User: /wicked-garden:product-strategy mobile-app-proposal.md --focus roi

Claude: I'll analyze the ROI for the mobile app proposal.

[Reads proposal document]
[Dispatches to business-strategist agent]
[Agent calculates costs, benefits, payback]

## Strategic Analysis: Mobile App Proposal

### Executive Summary
**Recommendation**: Proceed with Caution
**Confidence**: Medium
**Key Insight**: Strong revenue potential but high upfront cost requires phased approach

### ROI Analysis

#### Investment Required
| Category | One-Time | Ongoing/Year |
|----------|----------|--------------|
| Engineering | $180,000 | $60,000 |
| Design | $40,000 | $15,000 |
| Operations | $10,000 | $25,000 |
| **Total** | **$230,000** | **$100,000** |

#### Expected Returns
| Benefit | Year 1 | Year 2 | Year 3 |
|---------|--------|--------|--------|
| New Revenue | $50,000 | $200,000 | $400,000 |
| Reduced Churn | $30,000 | $60,000 | $90,000 |
| **Total** | **$80,000** | **$260,000** | **$490,000** |

#### Financial Summary
- **Payback Period**: 18 months
- **3-Year ROI**: 186%
- **NPV**: $412,000
- **Risk Level**: Medium

### Recommendations

#### If Proceed
1. Start with MVP (iOS only) to reduce initial investment to $120k
2. Validate retention metrics before Android investment
3. Set 6-month checkpoint for go/no-go on full rollout

#### Key Assumptions to Validate
- [ ] 15% of web users will adopt mobile (based on competitor data)
- [ ] Mobile users have 20% higher retention (needs A/B validation)
```
