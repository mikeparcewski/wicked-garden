# UX / Design Review Rubric (4 lenses)

Apply this inline. A broad design audit across four lenses: **flows · ui · a11y ·
research**. Each lens returns a score 1-5 + findings (severity + file:line + impact
+ fix). Scope with `--focus`; `--quick` = critical-only.

> **Dispatch only for `--focus all`.** When all four lenses run, dispatch the four
> specialist agents in parallel (ux-designer, ui-reviewer, a11y-expert,
> user-researcher) — real concurrency on a large surface earns the hop. For a
> single `--focus`, apply that lens's rubric inline; do not dispatch.

Auto-detect focus when absent: `.tsx/.jsx/.vue` -> flows+ui+a11y; `.css/.scss` ->
ui; requirements `.md` -> research; directory -> all.

## Lens: flows (ux-designer)

Evaluate flow clarity, error/empty/loading states, interaction patterns, IA.
Happy path <=7 steps; every decision mapped; recovery on errors; back nav at every
step; confirmation on destructive actions. Nielsen's 10 heuristics. (Full rubric:
`refs/ux.md`.)

## Lens: ui (ui-reviewer)

Establish the design-system baseline (tokens file, component library, grid). Then:
- **Consistency**: color palette, typography scale, spacing (4px/8px grid), radius,
  elevation, icon style.
- **Component patterns**: button variants; input states (default/focus/error/disabled);
  card/modal/list patterns.
- **Code violations**: hardcoded hex outside token files, magic-number spacing
  (`12px`/`15px`), inline styles, duplicate components, missing interactive states.
- **Responsive**: mobile-first breakpoints (~640/768/1024/1280), no fixed widths that
  break narrow, touch targets >=44x44px, fluid sizing (clamp/min/max).
- **Polish**: transitions (200-300ms), loading skeletons, empty/error styling, overflow/truncation.

Score 1-5; verdict Ship it / Minor polish / Needs work / Significant issues.

## Lens: a11y (a11y-expert)

Audit WCAG 2.1 AA via POUR: semantic HTML, ARIA, keyboard reachability + order,
screen-reader announcements, contrast (4.5:1 / 3:1), visible focus. Report WCAG
level + issues with criterion + fix. (Full rubric: `refs/a11y.md`.)

## Lens: research (user-researcher)

Assess personas (evidence-based, 3-5 distinct), user journeys (phases, pain points,
opportunities), Jobs-to-be-Done (`When {situation}, I want {motivation}, so I can
{outcome}`), and validation status (Validated / Assumed / Unknown). Return a gap list.

## Output

```markdown
## UX/Design Review: {target}   (focus: {flows|ui|a11y|research|all})

| Lens | Score 1-5 | Verdict |
|------|-----------|---------|
| Flows | {n} | {…} |
| UI | {n} | {…} |
| A11y | {n} | {WCAG level} |
| Research | {n} | {…} |

### Findings (by severity)
#### Critical — {issue} — {file:line} — Impact: {who} — Fix: {change}
#### Major / Minor — …

### Top Fixes
1. … 2. … 3. …
```
