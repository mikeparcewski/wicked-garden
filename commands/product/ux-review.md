---
description: |
  Use when reviewing UX quality, visual design consistency, or accessibility — covers user flows,
  design system adherence, spacing/typography/color, component patterns, and research quality.
  NOT for generating UX flows (use product:ux) or accessibility code audits (use product:a11y).
argument-hint: "<target> [--focus flows|ui|a11y|research|all] [--quick]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:ux-review

Broad design audit across four lenses — flows, visual consistency (UI), WCAG
accessibility, user-research quality. Each lens returns score 1-5 + findings.
`--quick` = critical-only. Use `ux-review` to evaluate existing UI; use `product:ux`
to generate flows.

## 1. Determine focus

Parse `--focus`. Auto-detect: `.tsx/.jsx/.vue` -> flows+ui+a11y; `.css/.scss` -> ui;
requirements `.md` -> research; directory -> all.

## 2. Single focus -> inline

For one lens, `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/ux-review.md")`, apply
that lens's rubric directly to the target, and emit the score + findings. No dispatch.

## 3. `--focus all` -> dispatch the lenses in parallel

Genuine multi-lens concurrency on a large surface earns the hop. Common preamble:
`Target: {target_content}  Quick: {--quick}`. Each agent returns score 1-5 + findings.

```
Task(subagent_type="wicked-garden:product:ux-designer",
     prompt="""<preamble> Two lenses. (1) Flows: clarity, error/empty/loading states, interaction patterns, IA. (2) Research: personas, journeys, JTBD, validation status. Issues with severity + file:line + impact + fix; plus a research-gap list.""")
Task(subagent_type="wicked-garden:product:ui-reviewer",
     prompt="""<preamble> Eval design-system adherence, color/typography/spacing, component patterns, responsive + visual states. Issues with severity + fix.""")
Task(subagent_type="wicked-garden:product:a11y-expert",
     prompt="""<preamble> Audit WCAG 2.1 AA (POUR): semantic HTML, ARIA, keyboard, screen reader, contrast, focus. Report WCAG level + issues with criterion + fix.""")
```

The research lens (personas / journeys / JTBD) is folded into the ux-designer dispatch — flow and research evaluation share the same artifact and reviewer skill. Merge the three returns into the combined report (`refs/ux-review.md` output format).
