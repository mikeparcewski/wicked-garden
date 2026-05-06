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

Broad design audit: user flows, visual consistency, WCAG accessibility, and user research quality across a surface. Use `--focus flows|ui|a11y|research` to scope; `--focus all` runs the full panel; `--quick` returns critical-only triage. Use `ux-review` to evaluate existing UI; use `product:ux` to generate flows from requirements.

## 1. Determine focus

Parse `--focus`. If absent, auto-detect: `.tsx/.jsx/.vue` → flows+ui+a11y; `.css/.scss` → ui; requirements `.md` → research; directory → all.

## 2. Dispatch (parallel where multiple)

Common preamble for every dispatch: `Target: {target_content}  Quick: {--quick}`. Each agent returns score 1-5 + findings.

```
Task(subagent_type="wicked-garden:product:ux-designer",      # flows | all
     prompt="""<preamble> Eval flow clarity, error/empty/loading states, interaction patterns, IA. Issues with severity + file:line + impact + fix.""")
Task(subagent_type="wicked-garden:product:ui-reviewer",      # ui | all
     prompt="""<preamble> Eval design-system adherence, color/typography/spacing, component patterns, responsive + visual states. Issues with severity + fix.""")
Task(subagent_type="wicked-garden:product:a11y-expert",      # a11y | all
     prompt="""<preamble> Audit WCAG 2.1 AA (POUR): semantic HTML, ARIA, keyboard, screen reader, contrast, focus. Report WCAG level + issues with criterion + fix.""")
Task(subagent_type="wicked-garden:product:user-researcher",  # research | all
     prompt="""<preamble> Assess personas, journeys, JTBD, validation status. Return gap list.""")
```
