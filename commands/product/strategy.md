---
description: Strategic analysis - ROI, value proposition, market, competitive
argument-hint: "<target> [--focus roi|value|market|competitive|all] [--quick]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:strategy

Strategic business analysis: ROI, value proposition, market sizing/timing, competitive landscape. Use `--focus roi|market|competitive` for market-strategist, `--focus value` for value-strategist, `--focus all` for the full panel. Use `--quick` for a go/no-go signal only. Use `product:strategy` for evaluating an idea; use `product:elicit` to convert a chosen direction into requirements.

## 1. Read target + parse flags

Read `<target>` (proposal/feature doc). Determine focus(es) from `--focus` (default `all`).

## 2. Dispatch (parallel when multiple)

```
Task(subagent_type="wicked-garden:product:market-strategist",
     prompt="""Target: {target_content}  Quick: {--quick}
Run modes: {roi, market, competitive — whichever apply from --focus}.
Return investment/returns/payback for roi, TAM/SAM/SOM/timing for market, SWOT/positioning for competitive.""")

Task(subagent_type="wicked-garden:product:value-strategist",   # only if value or all
     prompt="""Target: {target_content}  Quick: {--quick}
Design value proposition: customer JTBD, pain relievers, gain creators, differentiation, value statement.""")
```

After dispatches return, render the synthesis inline (Proceed / Caution / Defer / Do-Not-Proceed verdict + confidence + assumptions + metrics) — same as the pre-slim behavior; not delegated to a third agent.
