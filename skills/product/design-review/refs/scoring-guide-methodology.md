# Design Review Scoring Guide: Methodology

How to score design consistency across categories: colors, typography, spacing, components, and responsive design.

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

| Level | Characteristics |
|---|---|
| 1 Ad-hoc (✗) | No tokens, scattered styles, heavy duplication |
| 2 Emerging (⚠) | Some tokens, basic components, inconsistent usage |
| 3 Established (✓) | Comprehensive tokens, documented components, active maintenance |
| 4 Mature (✓✓) | Enforced tokens, composable components, automated testing + governance |

### User Impact Assessment

**Critical**: Accessibility violations, broken states, confusing interaction patterns
**Medium**: Inconsistent spacing, token violations, duplicate components
**Low**: Polish, edge case states, optimization
