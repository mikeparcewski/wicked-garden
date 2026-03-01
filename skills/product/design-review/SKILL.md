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

**Full review criteria**: See [refs/review-criteria.md](refs/review-criteria.md)

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

**Scoring guide**: See [refs/scoring-guide.md](refs/scoring-guide.md)

## Common Issues

```markdown
❌ Hardcoded colors: `color: #3b82f6` vs `color: var(--primary)`
❌ Magic numbers: `margin: 17px` vs `margin: var(--space-4)`
❌ Missing states: No `:hover` or `:focus` styles
❌ Non-responsive: Fixed widths without media queries
❌ Component duplication: Multiple similar button implementations
❌ Inaccessible contrast: Light gray on white
```

**Fix examples**: See refs/common-issues-*.md

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

**Full report template**: See [refs/report-template.md](refs/report-template.md)

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

**Design system guide**: See [refs/design-systems.md](refs/design-systems.md)

## Quick Wins

Fast improvements with high impact:

1. Extract hardcoded colors to CSS variables
2. Standardize spacing values
3. Add missing hover/focus states
4. Consolidate duplicate components
5. Fix color contrast violations
6. Add loading/empty state handling

**Implementation guide**: See [refs/quick-wins.md](refs/quick-wins.md)

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

## Resources

- **Refactoring UI**: Book on visual design
- **Design Systems Handbook**: Build design systems
- **Component Gallery**: component.gallery
- **Examples**: Material, Ant, Chakra, Tailwind

**Detailed guides in refs/:**
- [review-criteria.md](refs/review-criteria.md) - Full review checklist
- [scoring-guide.md](refs/scoring-guide.md) - How to score consistency
- common-issues-*.md - Issue patterns and fixes (3 files)
- [report-template.md](refs/report-template.md) - Comprehensive report format
- [design-systems.md](refs/design-systems.md) - Design system guide
- [quick-wins.md](refs/quick-wins.md) - Fast improvement implementations
- responsive-guide-*.md - Responsive design patterns (3 files)
