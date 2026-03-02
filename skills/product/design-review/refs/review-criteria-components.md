# Design Review Criteria - Components and Responsive

Component patterns, responsive design, and layout guidelines.

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
- Pass: Clear component library, minimal duplication
- Warning: Some duplicate components (consolidation opportunity)
- Fail: Many duplicate components, no clear library

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
/* BAD - Too small for touch */
.icon-button {
  width: 24px;
  height: 24px;
}

/* GOOD - Adequate touch target */
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
