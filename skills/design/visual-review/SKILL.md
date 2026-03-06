---
name: visual-review
description: |
  Systematic visual design analysis for UI consistency, design system adherence,
  spacing, typography, color, and component patterns.

  Use when: "visual review", "UI consistency", "design system check", "spacing audit",
  "typography review", "color palette", "component patterns", "visual analysis"
---

# Visual Review Skill

Systematic, evidence-based visual design analysis. Complements `product/design-review`
(which focuses on critique) by providing structured checklists and scoring.

## What This Evaluates

### Spacing and Alignment

- Grid system adherence (4px/8px grid)
- Consistent padding/margin within and between components
- Alignment: elements on a shared baseline or grid column
- Gutters and whitespace proportions

### Typography Hierarchy

- Type scale (heading levels, body, caption, label)
- Font weight usage (bold for emphasis, not decoration)
- Line height and letter spacing consistency
- Responsive type scaling

### Color Consistency

- All colors sourced from design tokens or CSS variables
- No hardcoded hex values outside token definitions
- Semantic color usage (error = red, success = green, etc.)
- Dark mode / theme variant coverage

### Component Patterns

- Reuse of existing components before creating new ones
- Consistent state handling: default, hover, focus, active, disabled, error
- Variant naming follows design system conventions
- No one-off component duplications

### Responsive Layout

- Mobile-first breakpoint structure
- No fixed widths that break at narrow viewports
- Touch targets ≥44×44px
- Images and media have max-width constraints

## Review Checklist

| Category | Check | Result |
|----------|-------|--------|
| Spacing | 4/8px grid used | ✓ / ⚠ / ✗ |
| Spacing | No magic number values | ✓ / ⚠ / ✗ |
| Typography | Heading levels sequential | ✓ / ⚠ / ✗ |
| Typography | Font stack from tokens | ✓ / ⚠ / ✗ |
| Color | No hardcoded hex | ✓ / ⚠ / ✗ |
| Color | Semantic tokens used | ✓ / ⚠ / ✗ |
| Components | States defined | ✓ / ⚠ / ✗ |
| Components | No duplicates | ✓ / ⚠ / ✗ |
| Responsive | Mobile-first media queries | ✓ / ⚠ / ✗ |
| Responsive | Touch targets sized | ✓ / ⚠ / ✗ |

## Common Violations

```
Spacing violations:
  margin: 17px          → margin: var(--space-4)
  padding: 12px 20px    → padding: var(--space-3) var(--space-5)

Color violations:
  color: #3b82f6        → color: var(--color-primary)
  background: #f9fafb   → background: var(--color-surface)

Typography violations:
  font-size: 13px       → font-size: var(--text-sm)
  font-weight: 600      → font-weight: var(--font-semibold)
```

## Scoring

| Score | Meaning |
|-------|---------|
| 5 — Ship it | All tokens used, consistent patterns, no violations |
| 4 — Minor polish | 1–3 minor violations, no systematic issues |
| 3 — Needs work | Inconsistent token usage, some components non-conforming |
| 2 — Significant issues | Systematic violations across multiple categories |
| 1 — Redesign needed | No design system adherence, inconsistent throughout |

## Output Format

```markdown
## Visual Review: {target}

**Score**: {1–5}
**Verdict**: {Ship it | Minor polish | Needs work | Significant issues | Redesign}

### Findings by Category

#### Spacing
- {finding with file:line and fix}

#### Typography
- {finding with file:line and fix}

#### Color
- {finding with file:line and fix}

#### Components
- {finding with file:line and fix}

#### Responsive
- {finding with file:line and fix}

### Top 3 Fixes
1. {highest impact fix}
2. {second fix}
3. {third fix}
```

## Integration

- **screenshot skill**: Capture visuals for before/after comparison
- **accessibility skill**: Color contrast overlaps with a11y
- **product/design-review**: Shares criteria; this provides the checklist structure
- **wicked-search**: `wicked-search "#[0-9a-fA-F]{3,6}"` finds hardcoded colors
