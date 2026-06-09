---
description: Strategic analysis - ROI, value proposition, market, competitive
argument-hint: "<target> [--focus roi|value|market|competitive|all] [--quick]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:strategy

Strategic business analysis: ROI, value proposition, market sizing/timing,
competitive landscape. `--quick` = go/no-go signal only. Use `product:strategy` to
evaluate an idea; `product:elicit` to convert a chosen direction into requirements.

## 1. Read target + parse focus

Read `<target>` (proposal/feature doc). Determine focus(es) from `--focus` (default `all`).

## 2. Single focus -> inline

For one lens, `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/strategy.md")` and apply
that lens's rubric directly — market lens for `roi|market|competitive`, value lens for
`value`. No dispatch.

## 3. `--focus all` -> dispatch both lenses in parallel

Concurrent market + value analysis earns the hop.

```
Task(subagent_type="wicked-garden:product:market-strategist",
     prompt="""Target: {target_content}  Quick: {--quick}
Run modes: {roi, market, competitive — whichever apply from --focus}.
Return investment/returns/payback for roi, TAM/SAM/SOM/timing for market, SWOT/positioning for competitive.""")
Task(subagent_type="wicked-garden:product:value-strategist",
     prompt="""Target: {target_content}  Quick: {--quick}
Design value proposition: customer JTBD, pain relievers, gain creators, differentiation, value statement.""")
```

## 4. Synthesis (always inline)

Render the verdict inline — Proceed / Caution / Defer / Do-Not-Proceed + confidence +
assumptions + metrics (`refs/strategy.md` output format). Never delegate the synthesis.
