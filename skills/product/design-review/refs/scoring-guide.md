# Design Review Scoring Guide

How to score design consistency and determine readiness.

## Overview

This guide explains how to evaluate design consistency and provide actionable scores. Scores are **not just numbers** - they're diagnostic tools to identify specific improvement areas.

## Scoring Framework

### Three-Tier System

```
✓ Ship it      90-100%   Minor or no issues
⚠ Minor issues 70-89%    Good with some inconsistencies
✗ Needs work   <70%      Significant problems
```

**Why not numeric scores?**
- Forces honest assessment
- Avoids false precision
- Focuses on actionable feedback

## Category Breakdown

### 1. Color Consistency

**What to measure:**
- % of colors from design tokens vs hardcoded
- Semantic color usage (primary, secondary, success, error)
- Color accessibility (contrast ratios)

**How to score:**

```bash
# Find hardcoded colors
wicked-search "#[0-9a-fA-F]{3,6}" --type css --output-mode count

# Find RGB values
wicked-search "rgb\(" --type css --output-mode count

# Find design token usage
wicked-search "var\(--color" --type css --output-mode count
```

**Calculation:**
```
Token Usage % = (Token Uses / (Token Uses + Hardcoded)) * 100

✓ ≥95%  All colors from system (allowance for rare exceptions)
⚠ 80-94% Mostly consistent, some hardcoded colors
✗ <80%  Many hardcoded colors, weak system adherence
```

**Example:**
```
Token uses: 450
Hardcoded hex: 50
Total: 500

Score: (450/500) * 100 = 90% ⚠

Notes: "Secondary buttons use hardcoded colors.
Extract to design tokens."
```

---

### 2. Typography Consistency

**What to measure:**
- Font size consistency (using type scale)
- Font family usage (should be 1-2 families)
- Line height proportions
- Font weight consistency

**How to score:**

```bash
# Find custom font sizes
wicked-search "font-size:\s*[0-9]+(px|rem)" --type css

# Find type scale usage
wicked-search "var\(--font-size" --type css --output-mode count

# Find font family declarations
wicked-search "font-family:" --type css
```

**Calculation:**
```
Type Scale Usage % = (Scale Uses / Total Font Declarations) * 100

✓ ≥90%  Comprehensive type scale usage
⚠ 75-89% Mostly scale-based, some custom sizes
✗ <75%  Many magic number sizes
```

**Common issues:**
- One-off font sizes (14.5px, 17px)
- Too many font families (>2)
- Inconsistent line heights
- Hardcoded font weights

---

### 3. Spacing Consistency

**What to measure:**
- % using spacing scale vs magic numbers
- Vertical rhythm consistency
- Padding/margin patterns

**How to score:**

```bash
# Find magic number spacing
wicked-search "(padding|margin):\s*[0-9]+(px|rem)" --type css

# Find spacing scale usage
wicked-search "var\(--space" --type css --output-mode count
```

**Calculation:**
```
Spacing Scale % = (Scale Uses / (Scale Uses + Magic Numbers)) * 100

✓ ≥85%  Strong spacing system adherence
⚠ 65-84% Decent consistency, some magic numbers
✗ <65%  Lots of arbitrary spacing
```

**Watch for:**
- Non-standard values (17px, 23px, 13px)
- Inconsistent component padding
- Broken vertical rhythm

---

### 4. Component Patterns

**What to measure:**
- Component duplication
- State coverage (hover, focus, disabled, etc.)
- Component reuse

**How to score:**

**Component Duplication:**
```
# Run component inventory
python3 scripts/component-inventory.py src/

# Analyze output
Similar buttons: 5 variants found
Similar cards: 3 variants found
Similar inputs: 4 variants found

Duplication Score = Similar Components / Total Components

✓ <10%  Minimal duplication, strong reuse
⚠ 10-25% Some duplication, consolidation opportunity
✗ >25%  Heavy duplication, needs component library
```

**State Coverage:**
```
For each component, check:
□ Default state
□ Hover state
□ Focus state
□ Active/pressed state
□ Disabled state
□ Loading state (if applicable)
□ Error state (if applicable)

State Coverage % = (Implemented States / Required States) * 100

✓ ≥90%  All major states covered
⚠ 70-89% Most states, some gaps
✗ <70%  Missing critical states
```

---

### 5. Responsive Design

**What to measure:**
- Breakpoint consistency
- Mobile-first approach
- Touch target sizing
- Responsive typography

**How to score:**

```bash
# Find media queries
wicked-search "@media" --type css

# Check for consistent breakpoints
wicked-search "min-width:\s*[0-9]+(px|em|rem)" --type css
```

**Breakpoint Consistency:**
```
# Extract all breakpoint values
# Count unique breakpoints
# Compare to design system

✓ 2-4 breakpoints, all from design system
⚠ 5-6 breakpoints, mostly consistent
✗ Many custom breakpoints, no clear system
```

**Touch Target Sizing:**
```
# Measure interactive elements
# Minimum: 44x44px (iOS) or 48x48px (Material)

✓ All interactive elements ≥44px minimum
⚠ Most elements adequate, some too small
✗ Many elements below minimum size
```

---

## Overall Score Calculation

### Weighted Average

Assign weights based on project priorities:

```
Default Weights:
- Color: 20%
- Typography: 20%
- Spacing: 20%
- Components: 25%
- Responsive: 15%

Example:
Color: 90% × 0.20 = 18
Typography: 85% × 0.20 = 17
Spacing: 95% × 0.20 = 19
Components: 75% × 0.25 = 18.75
Responsive: 80% × 0.15 = 12

Overall: 84.75% → ⚠ Minor issues
```

### Alternative: Weakest Link

For critical projects, use lowest category score:

```
Color: 90%
Typography: 85%
Spacing: 95%
Components: 75%  ← Lowest
Responsive: 80%

Overall: 75% → ⚠ Minor issues

Rationale: "A design system is only as strong as
its weakest category."
```

---

## Qualitative Assessment

Numbers don't tell the whole story. Include qualitative observations:

### Design System Maturity

**Level 1: Ad-hoc (✗)**
- No design tokens
- Styles scattered across files
- Heavy duplication
- No component library

**Level 2: Emerging (⚠)**
- Some design tokens defined
- Basic component library
- Inconsistent usage
- Some documentation

**Level 3: Established (✓)**
- Comprehensive design tokens
- Well-documented components
- Consistent usage
- Active maintenance

**Level 4: Mature (✓✓)**
- Enforced design tokens
- Composable components
- Automated testing
- Version control and governance

### User Impact Assessment

**Critical Issues:**
- Accessibility violations (color contrast, focus states)
- Broken functionality (missing states)
- Confusing patterns (inconsistent buttons)

**Medium Issues:**
- Inconsistent spacing
- Design token violations
- Duplicate components

**Low Issues:**
- Minor polish opportunities
- Edge case states
- Optimization potential

---

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
