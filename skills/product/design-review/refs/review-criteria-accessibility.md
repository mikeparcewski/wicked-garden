# Design Review Criteria - Accessibility, Polish, and Scoring

Visual polish, accessibility integration, maturity model, scoring, review process, tools, and success criteria.

## Visual Polish

### Transitions and Animations

**What to Check:**
- [ ] Transition durations consistent
- [ ] Easing functions defined
- [ ] Animations enhance UX (not distract)
- [ ] Reduced motion support
- [ ] Performance (GPU-accelerated properties)

**Animation System:**

```css
:root {
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-slow: 350ms;

  --easing-standard: cubic-bezier(0.4, 0.0, 0.2, 1);
  --easing-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1);
  --easing-accelerate: cubic-bezier(0.4, 0.0, 1, 1);
}

.button {
  transition: background var(--duration-base) var(--easing-standard);
}

/* Respect user preferences */
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

### Loading States

**What to Check:**
- [ ] Loading indicators consistent
- [ ] Skeleton screens for content
- [ ] Spinner sizes match context
- [ ] Loading text provides context

---

### Empty States

**What to Check:**
- [ ] Empty states designed for all lists/collections
- [ ] Clear messaging about why empty
- [ ] Actionable next steps provided
- [ ] Illustrations/icons appropriate

---

### Error States

**What to Check:**
- [ ] Error styling consistent
- [ ] Error messages helpful and specific
- [ ] Error recovery actions provided
- [ ] Form validation errors inline

---

## Accessibility Integration

**What to Check:**
- [ ] Color contrast meets WCAG AA (4.5:1 for text, 3:1 for UI)
- [ ] Focus indicators visible
- [ ] Interactive elements keyboard accessible
- [ ] Text resizable to 200% without breaking layout
- [ ] No information conveyed by color alone

---

## Design System Maturity

### Level 1: Ad-hoc
- No defined system
- Inconsistent patterns
- Lots of one-off styles

### Level 2: Emerging
- Some tokens defined
- Basic component library
- Inconsistent usage

### Level 3: Established
- Comprehensive design tokens
- Component library used consistently
- Documentation exists

### Level 4: Mature
- Design tokens enforced
- Components composable
- Automated testing
- Active governance

---

## Scoring Guide

### Overall Consistency Score

Calculate percentage compliance:

```
Total Checkpoints: X
Passed: Y
Score: (Y / X) * 100%

90-100%: Excellent - Ship it
70-89%: Good - Minor improvements needed
<70%: Needs work - Significant inconsistencies
```

### Category Scores

Score each category independently:
- Visual Consistency (Colors, Typography, Spacing)
- Component Patterns (Buttons, Forms, States)
- Responsive Design (Breakpoints, Touch Targets)
- Visual Polish (Animations, States)

### Prioritization

**P0 (Critical):**
- Accessibility violations
- Broken functionality
- Major inconsistencies blocking users

**P1 (High):**
- Inconsistent component patterns
- Missing states (hover, focus)
- Responsive issues

**P2 (Medium):**
- Design token violations
- Minor inconsistencies
- Missing polish

**P3 (Low):**
- Optimization opportunities
- Nice-to-have improvements

---

## Review Process

### 1. Automated Scan
- Find hardcoded colors: `wicked-search "#[0-9a-fA-F]{3,6}" --type css`
- Find magic numbers: `wicked-search "[0-9]+px" --type css`
- Component inventory: `python3 scripts/component-inventory.py`

### 2. Manual Review
- Check color usage visually
- Test responsive breakpoints
- Review component states
- Test interactions

### 3. Document Findings
- List violations with locations
- Provide fix recommendations
- Prioritize issues
- Track in kanban

### 4. Create Action Plan
- Group similar issues
- Estimate effort
- Assign owners
- Set deadlines

---

## Tools

**Browser DevTools:**
- Inspect computed styles
- Check responsive breakpoints
- Measure spacing/sizing

**Design Tools:**
- Figma Inspect for design tokens
- Sketch Measure
- Zeplin

**Automated:**
- CSS Stats (analyze CSS)
- Contrast checkers
- Component crawlers

---

## Success Criteria

**Review is complete when:**
- All checkpoints evaluated
- Issues documented with severity
- Recommendations provided
- Action plan created
- Score calculated

**Design system is healthy when:**
- >90% compliance with design tokens
- No duplicate components
- All states implemented
- Responsive across breakpoints
- Accessibility baseline met
