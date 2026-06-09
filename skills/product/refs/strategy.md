# Strategic Analysis Rubric (ROI · market · competitive · value)

Apply this inline. Strategic business analysis across two lenses: **market**
(ROI / TAM-SAM-SOM / SWOT / Five Forces — the market-strategist rubric) and
**value** (value proposition / JTBD / differentiation — the value-strategist rubric).
`--focus roi|market|competitive` -> market lens; `--focus value` -> value lens;
`--quick` = go/no-go signal only.

> **Dispatch only for `--focus all`.** When both lenses run, dispatch the two
> specialist agents in parallel (market-strategist + value-strategist) — genuine
> concurrent multi-lens analysis. For a single `--focus`, apply that lens inline.
> Always render the final synthesis verdict inline (Proceed / Caution / Defer /
> Do-Not-Proceed + confidence + assumptions + metrics); never delegate the synthesis.

## Market lens — business case

**Costs**: development (eng time x loaded rate, design, QA, deploy); ongoing (infra,
maintenance, support, tech debt); opportunity cost.
**Benefits**: revenue (new streams, churn reduction, pricing power); cost savings
(automation, efficiency, error reduction); strategic value (positioning, platform
effects); risk mitigation (security, compliance, reliability).
**Math**:
```
Total Investment = Dev + Ongoing (3yr)
Annual Benefit   = Revenue + Savings + Risk Value
ROI    = (Total Benefits - Total Investment) / Total Investment x 100%
Payback = Total Investment / Annual Benefit
3-Year NPV = discounted benefits - investment
```
**Decision**: APPROVE (positive ROI, strong fit, manageable risk) / CONDITIONAL
(positive with conditions, phase it) / REJECT (negative-or-unclear ROI, poor fit).
**Confidence**: HIGH / MEDIUM / LOW.

## Market lens — competitive

- **Competitive set**: direct / indirect / substitutes (incl. do-nothing).
- **Porter's Five Forces**: rivalry, supplier power, buyer power, threat of
  substitutes, threat of new entrants -> overall attractiveness.
- **SWOT**: Strengths/Weaknesses (internal), Opportunities/Threats (external).
- **Positioning & white space**: plot on axes (price vs performance, ease vs power);
  find underserved segments.
- **Strategic stance**: head-to-head / differentiation / niche / blue ocean.
- **Market timing**: maturity (emerging/growing/mature/declining) + TAM/SAM/SOM ->
  TOO EARLY / RIGHT TIME / TOO LATE.

## Value lens — value proposition

- **JTBD**: functional (tasks), emotional (feelings), social (perception).
- **Current solutions + pains**: what they use today; what's broken.
- **Value Proposition Canvas**: customer profile (jobs/pains/gains) ↔ value map
  (products, pain relievers, gain creators).
- **Value statement**: `For {customer} who {need}, our {product} is a {category}
  that {benefit}; unlike {alternative} we {differentiation}`.
- **Differentiation axes**: performance / experience / price / niche / innovation.
- **Defensibility (moats)**: network effects, switching costs, proprietary data, brand, ecosystem.
- **Score /25**: clarity + relevance + differentiation + credibility + defensibility
  (each 1-5). 20-25 Strong · 15-19 Solid · 10-14 Weak · <10 Not viable.

## Pitfalls to avoid

Sunk-cost fallacy; optimism bias (use conservative estimates); ignoring opportunity
cost; inflated TAM ("everyone is a customer"); over-focus on direct competitors
(substitutes/new entrants often matter more); vague benefits; cherry-picked data.

## Output (synthesis, inline)

```markdown
## Strategy Analysis: {project}
### Verdict: PROCEED | CAUTION | DEFER | DO-NOT-PROCEED   Confidence: HIGH|MED|LOW
### Business Case — Investment ${…} · Annual Benefit ${…} · ROI {…}% · Payback {…}mo · 3yr NPV ${…}
### Competitive — Position {LEADER|CHALLENGER|FOLLOWER|NICHE} · Stance {…} · Timing {…}
### SWOT — S/W/O/T
### Value — Score {X}/25 · Statement · Differentiation · Defensibility
### Key Assumptions · Metrics to Track · Top Risks (risk/prob/impact/mitigation)
### Immediate Actions
1. {action} — {why}
```
