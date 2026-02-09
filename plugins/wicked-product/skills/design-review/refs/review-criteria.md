# Design Review Criteria

Comprehensive checklist for visual design and UI consistency review.

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

---

## Component Patterns

### Component Inventory

**What to Check:**
- [ ] Identify all unique components
- [ ] Count duplicate/similar components
- [ ] Check for component reuse opportunities
- [ ] Verify component composition

**Components to Inventory:**
- Buttons (primary, secondary, tertiary, icon)
- Inputs (text, select, textarea, checkbox, radio)
- Cards
- Modals/dialogs
- Navigation (nav, tabs, breadcrumbs)
- Alerts/notifications
- Tables
- Forms
- Loading states
- Empty states

**Scoring:**
- ✓ Pass: Clear component library, minimal duplication
- ⚠ Warning: Some duplicate components (consolidation opportunity)
- ✗ Fail: Many duplicate components, no clear library

---

### Button Consistency

**What to Check:**
- [ ] Button variants defined (primary, secondary, tertiary, ghost, link)
- [ ] Button sizes consistent (sm, md, lg)
- [ ] Button states implemented (default, hover, focus, active, disabled)
- [ ] Icon buttons have accessible labels
- [ ] Loading states handled

**Example:**

```css
/* Button variants */
.button-primary { /* High emphasis */ }
.button-secondary { /* Medium emphasis */ }
.button-tertiary { /* Low emphasis */ }
.button-ghost { /* Minimal emphasis */ }
.button-link { /* Link-style */ }

/* Button sizes */
.button-sm { padding: var(--space-1) var(--space-3); font-size: var(--font-size-sm); }
.button-md { padding: var(--space-2) var(--space-4); font-size: var(--font-size-base); }
.button-lg { padding: var(--space-3) var(--space-6); font-size: var(--font-size-lg); }

/* Button states */
.button:hover { /* ... */ }
.button:focus-visible { /* ... */ }
.button:active { /* ... */ }
.button:disabled { /* ... */ }
```

---

### Form Consistency

**What to Check:**
- [ ] Input styles consistent
- [ ] Label positioning consistent
- [ ] Error states consistent
- [ ] Validation feedback consistent
- [ ] Help text styling consistent

**Form Patterns:**

```css
/* Input states */
.input { /* Default */ }
.input:focus { /* Focus */ }
.input:disabled { /* Disabled */ }
.input.error { /* Error */ }
.input.success { /* Success */ }

/* Consistent spacing */
.form-field {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-weight: 500;
}
```

---

### State Handling

**What to Check:**
- [ ] Hover states defined for interactive elements
- [ ] Focus states visible and consistent
- [ ] Active/pressed states defined
- [ ] Disabled states consistent
- [ ] Loading states implemented
- [ ] Empty states designed
- [ ] Error states designed

**Critical States:**

```css
/* Hover */
.button:hover {
  background: var(--color-primary-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

/* Focus */
.button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Disabled */
.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading */
.button.loading {
  position: relative;
  color: transparent;
}
.button.loading::after {
  content: '';
  /* spinner styles */
}
```

---

## Responsive Design

### Breakpoint Consistency

**What to Check:**
- [ ] Breakpoints defined and documented
- [ ] Mobile-first approach used
- [ ] Consistent breakpoint usage across components
- [ ] Responsive typography
- [ ] Responsive spacing

**Breakpoint System:**

```css
:root {
  --breakpoint-sm: 640px;   /* Mobile landscape */
  --breakpoint-md: 768px;   /* Tablet */
  --breakpoint-lg: 1024px;  /* Desktop */
  --breakpoint-xl: 1280px;  /* Large desktop */
  --breakpoint-2xl: 1536px; /* Extra large */
}

/* Mobile-first approach */
.container {
  padding: var(--space-4);
}

@media (min-width: 768px) {
  .container {
    padding: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .container {
    padding: var(--space-8);
  }
}
```

---

### Touch Targets

**What to Check:**
- [ ] Interactive elements minimum 44x44px (iOS) or 48x48px (Material)
- [ ] Adequate spacing between touch targets
- [ ] Mobile-friendly controls

**Example:**

```css
/* ✗ BAD - Too small for touch */
.icon-button {
  width: 24px;
  height: 24px;
}

/* ✓ GOOD - Adequate touch target */
.icon-button {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon-button svg {
  width: 24px;
  height: 24px;
}
```

---

### Layout Patterns

**What to Check:**
- [ ] Grid system defined
- [ ] Flexbox patterns consistent
- [ ] Container max-widths consistent
- [ ] Responsive images implemented

---

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

✓ 90-100%: Excellent - Ship it
⚠ 70-89%: Good - Minor improvements needed
✗ <70%: Needs work - Significant inconsistencies
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
- ✓ All checkpoints evaluated
- ✓ Issues documented with severity
- ✓ Recommendations provided
- ✓ Action plan created
- ✓ Score calculated

**Design system is healthy when:**
- ✓ >90% compliance with design tokens
- ✓ No duplicate components
- ✓ All states implemented
- ✓ Responsive across breakpoints
- ✓ Accessibility baseline met
