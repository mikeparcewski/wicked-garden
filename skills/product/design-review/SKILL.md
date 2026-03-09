---
name: design-review
description: |
  Visual design and UI consistency review process.
  Component patterns, design system adherence, responsive design, and visual polish.

  Use when: "design review", "UI review", "visual consistency", "design system",
  "component review", "polish", "responsive design"
---

# Design Review Skill

Deep visual design and UI implementation review.

## What This Reviews

**Visual Consistency:**
- Color palette adherence
- Typography scale compliance
- Spacing system usage (4px/8px grid)
- Border radius, shadows, icons

**Component Patterns:**
- Component reuse
- State handling (hover, focus, disabled)
- Design system integration

**Responsive Design:**
- Mobile-first approach
- Breakpoint consistency
- Touch target sizing

**Visual Polish:**
- Transitions, loading/empty/error states
- Edge case handling

**Full review criteria**: See [Visual Consistency](refs/review-criteria-visual.md), [Components & Responsive](refs/review-criteria-components.md), and [Accessibility & Scoring](refs/review-criteria-accessibility.md)

## Quick Review Process

### 1. Component Inventory

```bash
# Scan for components
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/product/component-inventory.py" src/

# Find patterns
wicked-search "className=" --type jsx
wicked-search "styled\." --type ts
```

### 2. Design Token Check

```bash
# Find hardcoded colors (violations)
wicked-search "#[0-9a-fA-F]{3,6}" --type css

# Find magic number spacing
wicked-search "[0-9]+px" --type css
```

### 3. Consistency Scoring

| Category | Score | Notes |
|----------|-------|-------|
| Colors | {✓⚠✗} | {brief note} |
| Typography | {✓⚠✗} | {brief note} |
| Spacing | {✓⚠✗} | {brief note} |
| Components | {✓⚠✗} | {brief note} |
| Responsive | {✓⚠✗} | {brief note} |

**Scoring guide**: See [refs/scoring-guide-methodology.md](refs/scoring-guide-methodology.md) and [refs/scoring-guide-examples.md](refs/scoring-guide-examples.md)

## Common Issues

```markdown
❌ Hardcoded colors: `color: #3b82f6` vs `color: var(--primary)`
❌ Magic numbers: `margin: 17px` vs `margin: var(--space-4)`
❌ Missing states: No `:hover` or `:focus` styles
❌ Non-responsive: Fixed widths without media queries
❌ Component duplication: Multiple similar button implementations
❌ Inaccessible contrast: Light gray on white
```

**Fix examples**: See [Color Issues](refs/common-issues-color-issues.md), [Component Issues](refs/common-issues-component-issues.md), [Animation Issues](refs/common-issues-animation-issues.md)

## Output Format

```markdown
## Design Review

**Consistency**: {✓ Ship it | ⚠ Minor issues | ✗ Needs work}

### Component Inventory
- Buttons: {count}
- Inputs: {count}
- Cards: {count}

### Issues

#### Critical
- {Issue breaking design}
  - Location: {file:line}
  - Fix: {code change}

#### Major
- {Inconsistency}
  - Location: {file:line}
  - Recommendation: {improvement}

### Recommendations
1. {High-priority fix}
2. {Design system improvement}
```

**Full report template**: See [refs/report-template-findings.md](refs/report-template-findings.md) and [refs/report-template-actions.md](refs/report-template-actions.md)

## Design System Checklist

If project has a design system:
- [ ] All colors from design tokens
- [ ] Typography follows type scale
- [ ] Spacing uses defined system
- [ ] Components from library
- [ ] Proper component props used
- [ ] No inline style overrides

If no design system:
- [ ] Recommend creating one
- [ ] Document existing patterns
- [ ] Extract common values as tokens
- [ ] Propose scales
- [ ] Identify component candidates

**Design system guide**: See [Tokens & Foundations](refs/design-systems-tokens.md), [Components](refs/design-systems-components.md), [Governance](refs/design-systems-governance.md)

## Quick Wins

Fast improvements with high impact:

1. Extract hardcoded colors to CSS variables
2. Standardize spacing values
3. Add missing hover/focus states
4. Consolidate duplicate components
5. Fix color contrast violations
6. Add loading/empty state handling

**Implementation guide**: See [Top 10 Quick Wins](refs/quick-wins-top-10.md) and [Workflow & Planning](refs/quick-wins-workflow.md)

## Integration

**Tools:**
```bash
# Screenshots for comparison
wicked-browse screenshot {url} --output design-review/

# Color contrast
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/product/contrast-check.py" "#666" "#fff"

# Track design debt
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" create-task \
  "Design Review" "UI: {issue}" "todo" --priority P2 --tags "design,ui"
```

**Collaboration:**
- UX Designer: Validate visuals support user flows
- A11y Expert: Color contrast and affordances
- Developer: Implement design system improvements

## When to Review

- New UI components added
- Design system updated
- Before major releases
- Post-build phase (crew integration)
- Design handoff to dev
- Multiple devs touching UI

**Detailed guides in refs/:**
- [review-criteria-visual.md](refs/review-criteria-visual.md) - Visual consistency
- [review-criteria-components.md](refs/review-criteria-components.md) - Components and responsive
- [review-criteria-accessibility.md](refs/review-criteria-accessibility.md) - Accessibility and scoring
- [scoring-guide-methodology.md](refs/scoring-guide-methodology.md) - Scoring methodology
- [scoring-guide-examples.md](refs/scoring-guide-examples.md) - Scoring examples and application
- Common issues: [color](refs/common-issues-color-issues.md), [component](refs/common-issues-component-issues.md), [animation](refs/common-issues-animation-issues.md)
- [report-template-findings.md](refs/report-template-findings.md) - Report findings template
- [report-template-actions.md](refs/report-template-actions.md) - Report actions and tracking
- Design systems: [tokens](refs/design-systems-tokens.md), [components](refs/design-systems-components.md), [governance](refs/design-systems-governance.md)
- Quick wins: [top 10](refs/quick-wins-top-10.md), [workflow](refs/quick-wins-workflow.md)
- Responsive: [mobile-first](refs/responsive-guide-mobile-first-philosophy.md), [typography](refs/responsive-guide-responsive-typography.md), [tables](refs/responsive-guide-responsive-tables.md)
