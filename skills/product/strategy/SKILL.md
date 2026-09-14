---
name: wicked-garden-product-strategy
description: |
  Strategic business analysis for technical investments. Evaluates ROI, value proposition,
  competitive positioning, and market alignment. Provides decision support with business justification.

  Use when: building a business case for a technical investment, evaluating
  ROI or value proposition, or doing competitive positioning analysis.
metadata:
  role: module
  phases: "clarify,design,review"
  archetypes: "*"
---

# Strategy Skill

Multi-perspective business analysis to guide technical investment decisions.

## When to Use

- User needs business justification for a project
- Decision requires ROI or value assessment
- Need competitive landscape analysis
- Evaluating strategic alignment
- User says "should we build this", "what's the ROI", "business value", "market research"

## Analysis Modes

### Full Strategic Analysis (`wicked-garden-product-strategy`)

- Business impact & ROI
- Value proposition & differentiation
- Competitive landscape
- Market alignment
- Decision recommendation with confidence

Best for: Major investments, strategic decisions, go/no-go evaluations

### ROI Analysis

- Cost vs benefit analysis
- Payback period
- Break-even analysis
- Quick financial assessment

Best for: Budget justification, fast approvals, comparative costs

### Value Scoring

- Value proposition strength
- Differentiation assessment
- Customer benefit mapping
- Pricing guidance

Best for: Product positioning, feature prioritization, marketing alignment

## Analysis Framework

### 1. Business Impact Assessment

**Questions to Answer**:
- What problem does this solve?
- Who benefits and how much?
- What's the cost of NOT doing this?
- How does it align with strategic goals?

**Output**: Impact score (HIGH/MEDIUM/LOW) with justification

### 2. ROI Analysis

**Financial Model**:
```
ROI = (Benefits - Costs) / Costs × 100%
Payback Period = Investment / Annual Benefit
```

**Costs Include**:
- Development time
- Infrastructure
- Maintenance
- Opportunity cost

**Benefits Include**:
- Revenue gain
- Cost savings
- Risk reduction
- Efficiency gains

### 3. Value Proposition

**Framework**: Jobs-to-be-Done
- Functional jobs (what tasks)
- Emotional jobs (how they feel)
- Social jobs (how they're perceived)

**Differentiation**:
- What makes this unique?
- Why choose this over alternatives?
- What's the defensible advantage?

### 4. Competitive Analysis

**5 Forces Analysis**:
- Competitive rivalry
- Supplier power
- Buyer power
- Threat of substitutes
- Threat of new entrants

**SWOT**:
- Strengths (internal, positive)
- Weaknesses (internal, negative)
- Opportunities (external, positive)
- Threats (external, negative)

### 5. Market Alignment

**Market Assessment**:
- Market size & growth
- Target segments
- Adoption barriers
- Timing considerations

## Decision Framework

| Score | Confidence | Recommendation |
|-------|-----------|----------------|
| APPROVE | HIGH | Strong business case, proceed |
| APPROVE | MEDIUM | Solid case with caveats, proceed with monitoring |
| CONDITIONAL | MEDIUM | Viable if conditions met, address concerns first |
| REJECT | HIGH | Weak case, recommend alternative |
| REJECT | MEDIUM | Insufficient evidence, gather more data |

## Integration

### With the memory layer (wicked-garden-mem)

**Hand-off** — open the `wicked-garden-mem` skill and run its `store` action with `ROI analysis: {project}` (kind=fact) to keep the strategic insight, and its `recall` action with `strategic analysis {domain}` as the query to recall past analysis; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

### With wicked-crew

Called during clarify phase for value assessment:
- Validates project justification
- Provides business perspective
- Informs go/no-go decisions

### With the harness's task list

Attach the analysis as evidence by appending `## Strategy Analysis` + `{analysis_summary}` to the task description — the harness's task list where it has one (the `wicked-garden-workflow` skill's `refs/integration.md` carries the field list and the harness-specific Hand-off), else your working notes.

## Output Structure

```markdown
## Strategic Analysis: {Project}

### Decision: APPROVE | CONDITIONAL | REJECT
**Confidence**: HIGH | MEDIUM | LOW

### Executive Summary
{3-5 sentence business case}

### ROI Analysis
- **Investment**: ${cost}
- **Annual Benefit**: ${benefit}
- **ROI**: {percentage}
- **Payback Period**: {months}

### Value Proposition
{Why this matters to customers/stakeholders}

### Competitive Position
{How this compares to alternatives}

### Risks & Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|

### Recommendation
{Action items with priorities}
```

## Quality Checks

- Quantify costs and benefits (no hand-waving)
- Be honest about uncertainties
- Consider alternatives
- Provide clear recommendation with reasoning

Discover available analytics/market integrations via capability detection. Fall back to qualitative analysis when no data sources available.
