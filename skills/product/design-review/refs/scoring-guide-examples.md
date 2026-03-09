# Design Review Scoring Guide: Examples & Application

Scoring examples, reporting format, decision making, continuous improvement, and tools.

## Scoring Examples

### Example 1: E-commerce Site

**Category Scores:**
- Color: 95% ✓ (Well-defined palette, rare hardcoded values)
- Typography: 88% ⚠ (Type scale used, but some custom sizes in legacy components)
- Spacing: 92% ✓ (8px grid mostly followed)
- Components: 70% ⚠ (3 button variants, some duplication in cards)
- Responsive: 85% ⚠ (Mobile-first, but inconsistent breakpoints)

**Overall: 86% ⚠ Minor issues**

**Key Findings:**
1. Consolidate button variants (3 → 1 with props)
2. Standardize card components
3. Document breakpoint system
4. Migrate legacy components to type scale

**Recommendation:** Ship with minor cleanup. Schedule tech debt sprint for component consolidation.

---

### Example 2: Dashboard Application

**Category Scores:**
- Color: 75% ⚠ (Design tokens exist but often bypassed)
- Typography: 65% ✗ (No clear type scale)
- Spacing: 60% ✗ (Magic numbers everywhere)
- Components: 55% ✗ (Heavy duplication, missing states)
- Responsive: 70% ⚠ (Desktop-focused, mobile needs work)

**Overall: 65% ✗ Needs work**

**Key Findings:**
1. Establish and enforce design token usage
2. Create type scale and apply consistently
3. Define spacing system (8px grid recommended)
4. Build component library to reduce duplication
5. Implement mobile-first responsive approach

**Recommendation:** Do not ship. Invest in design system foundation before adding new features.

---

### Example 3: Marketing Site

**Category Scores:**
- Color: 98% ✓ (Strict brand colors, all tokenized)
- Typography: 95% ✓ (Clear type scale, well-documented)
- Spacing: 90% ✓ (4px base grid, consistently applied)
- Components: 92% ✓ (Component library, minimal duplication)
- Responsive: 95% ✓ (Mobile-first, 3 breakpoints)

**Overall: 94% ✓ Ship it**

**Key Findings:**
1. Excellent design system adherence
2. Minor opportunities in animation consistency
3. Consider adding empty state designs

**Recommendation:** Ship. Strong foundation for growth. Continue maintaining design system.

---

## Reporting Format

### Summary Dashboard

```markdown
## Design Consistency Score: ⚠ 84% (Minor Issues)

| Category    | Score | Status |
|-------------|-------|--------|
| Color       | 90%   | ✓      |
| Typography  | 85%   | ⚠      |
| Spacing     | 95%   | ✓      |
| Components  | 75%   | ⚠      |
| Responsive  | 80%   | ⚠      |

### Top Issues
1. Button component duplication (5 variants)
2. Inconsistent focus states
3. Magic number font sizes in headers

### Recommendation
Good foundation with consolidation opportunities.
Ship with plan to address component duplication in next sprint.
```

---

## Using Scores for Decision Making

### Release Decisions

```
✓ 90%+    → Ship with confidence
⚠ 70-89%  → Ship with documented tech debt
✗ <70%    → Block until critical issues resolved
```

### Sprint Planning

```
Use scores to prioritize work:
- Lowest scoring category = highest priority
- Focus on ✗ categories before ⚠
- ✓ categories: maintain, don't regress
```

### Team Communication

```
Avoid: "Design consistency is 84%"
Better: "Design system is strong (color, spacing) but
        component duplication needs attention (5 button
        variants). Let's consolidate before next feature."
```

---

## Continuous Improvement

### Set Targets

```
Current:  ⚠ 84%
Q2 Goal:  ✓ 90%

Action Plan:
1. Consolidate button components → +3%
2. Apply type scale to headers → +2%
3. Standardize breakpoints → +1%
```

### Track Over Time

```
| Date       | Score | Status |
|------------|-------|--------|
| 2026-01-01 | 84%   | ⚠      |
| 2026-04-01 | 90%   | ✓      | (Goal)
```

### Prevent Regression

```
- Add design system linting to CI
- Review new components against system
- Regular design reviews
- Document decisions
```

---

## Tools for Scoring

### Automated
- CSS Stats: Analyze CSS complexity
- Design Token Validator: Check token usage
- Component Inventory Scripts: Find duplication

### Manual
- Browser DevTools: Inspect styles
- Contrast Checkers: Verify accessibility
- Responsive Testing: Check breakpoints

---

## Key Takeaways

1. **Scores are diagnostic**, not judgmental
2. **Context matters** - a 70% for a startup MVP may be fine, but not for a enterprise product
3. **Trends matter more than absolute scores** - improving from 60% to 75% is great
4. **Always include qualitative assessment** - numbers alone don't capture full picture
5. **Use scores to drive action** - every score should lead to specific next steps

---

## Success Criteria

**Scoring is effective when:**
- ✓ Teams understand what score means
- ✓ Scores lead to specific action items
- ✓ Progress tracked over time
- ✓ Scores inform release decisions
- ✓ Design system health visible at a glance
