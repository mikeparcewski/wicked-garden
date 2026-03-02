# Design Review Criteria - Visual Consistency

Detailed criteria for evaluating visual design consistency: colors, typography, spacing, borders, shadows, and icons.

## Overview

This document provides detailed criteria for evaluating visual design consistency, component quality, and design system adherence.

## Visual Consistency

### Color System

**What to Check:**
- [ ] All colors defined in design tokens/variables
- [ ] No hardcoded hex/RGB values in component styles
- [ ] Color palette limited to defined set
- [ ] Consistent color usage across components
- [ ] Semantic color naming (primary, secondary, success, error, etc.)

**Examples:**

```css
/* ✗ BAD - Hardcoded colors */
.button {
  background: #3b82f6;
  color: #ffffff;
}

/* ✓ GOOD - Design tokens */
.button {
  background: var(--color-primary);
  color: var(--color-on-primary);
}
```

**Scoring:**
- ✓ Pass: All colors from design system
- ⚠ Warning: <10% hardcoded colors
- ✗ Fail: >10% hardcoded colors or no color system

---

### Typography System

**What to Check:**
- [ ] Type scale defined (h1-h6, body, small, etc.)
- [ ] Font families limited to 1-2 (readability)
- [ ] Font weights defined (regular, medium, bold)
- [ ] Line heights proportional to font size
- [ ] Consistent letter spacing
- [ ] No magic number font sizes

**Type Scale Example:**

```css
/* ✓ GOOD - Defined type scale */
:root {
  --font-family-base: 'Inter', sans-serif;
  --font-family-mono: 'Fira Code', monospace;

  /* Type scale (1.25 ratio) */
  --font-size-xs: 0.64rem;    /* 10px */
  --font-size-sm: 0.8rem;     /* 13px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.25rem;    /* 20px */
  --font-size-xl: 1.563rem;   /* 25px */
  --font-size-2xl: 1.953rem;  /* 31px */
  --font-size-3xl: 2.441rem;  /* 39px */

  --line-height-tight: 1.25;
  --line-height-base: 1.5;
  --line-height-loose: 1.75;
}

h1 { font-size: var(--font-size-3xl); }
h2 { font-size: var(--font-size-2xl); }
body { font-size: var(--font-size-base); }
```

**Scoring:**
- ✓ Pass: All text uses type scale
- ⚠ Warning: <10% custom sizes
- ✗ Fail: No type scale or many custom sizes

---

### Spacing System

**What to Check:**
- [ ] Spacing based on scale (4px, 8px, 16px, etc.)
- [ ] Consistent padding/margin values
- [ ] No magic number spacing
- [ ] Vertical rhythm maintained
- [ ] White space used intentionally

**Spacing Scale Example:**

```css
/* ✓ GOOD - 8px base scale */
:root {
  --space-0: 0;
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.5rem;    /* 24px */
  --space-6: 2rem;      /* 32px */
  --space-8: 3rem;      /* 48px */
  --space-10: 4rem;     /* 64px */
  --space-12: 6rem;     /* 96px */
}

/* ✗ BAD - Magic numbers */
.card {
  padding: 17px 23px;
  margin-bottom: 19px;
}

/* ✓ GOOD - Design tokens */
.card {
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-4);
}
```

**Scoring:**
- ✓ Pass: All spacing from system
- ⚠ Warning: <15% magic numbers
- ✗ Fail: No spacing system or many magic numbers

---

### Borders and Radii

**What to Check:**
- [ ] Border widths consistent (1px, 2px, 4px)
- [ ] Border radius scale defined
- [ ] Border colors from color system
- [ ] Consistent border usage

**Examples:**

```css
:root {
  --border-width-thin: 1px;
  --border-width-medium: 2px;
  --border-width-thick: 4px;

  --border-radius-none: 0;
  --border-radius-sm: 0.25rem;   /* 4px */
  --border-radius-base: 0.5rem;  /* 8px */
  --border-radius-lg: 1rem;      /* 16px */
  --border-radius-full: 9999px;

  --border-color: var(--color-gray-300);
}
```

---

### Shadows and Elevation

**What to Check:**
- [ ] Shadow scale defined (none, sm, md, lg, xl)
- [ ] Shadows used consistently for elevation
- [ ] Shadow colors match theme

**Shadow Scale Example:**

```css
:root {
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.1);
  --shadow-2xl: 0 25px 50px rgba(0, 0, 0, 0.25);
}

.card { box-shadow: var(--shadow-md); }
.modal { box-shadow: var(--shadow-xl); }
```

---

### Icons

**What to Check:**
- [ ] Icon library consistent (one source)
- [ ] Icon sizes defined (16px, 20px, 24px)
- [ ] Icon colors from color system
- [ ] Icons aligned with text baseline
- [ ] Accessible icon implementation
