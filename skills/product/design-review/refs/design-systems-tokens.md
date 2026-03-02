# Design Systems - Tokens and Foundations

Design token system foundations: what design systems are, why they matter, and comprehensive token definitions.

## What is a Design System?

A design system is a collection of reusable components, design tokens, and guidelines that enable consistent, scalable product development.

**Components:**
1. **Design Tokens**: Named design decisions (colors, spacing, typography)
2. **Component Library**: Reusable UI components
3. **Documentation**: Usage guidelines and patterns
4. **Governance**: Process for maintaining and evolving the system

## Why Design Systems Matter

**For Designers:**
- Faster design iterations
- Consistency across products
- More time for complex problems

**For Developers:**
- Faster implementation
- Reduced decision fatigue
- Easier maintenance

**For Business:**
- Reduced design debt
- Faster time to market
- Consistent brand experience

**For Users:**
- Predictable interfaces
- Better accessibility
- Cohesive experience

## Design Token System

Design tokens are the foundation of a design system.

### Color Tokens

```css
:root {
  /* Brand colors */
  --color-brand-primary: #0066cc;
  --color-brand-secondary: #6366f1;

  /* Neutral palette */
  --color-gray-50: #f9fafb;
  --color-gray-100: #f3f4f6;
  --color-gray-200: #e5e7eb;
  --color-gray-300: #d1d5db;
  --color-gray-400: #9ca3af;
  --color-gray-500: #6b7280;
  --color-gray-600: #4b5563;
  --color-gray-700: #374151;
  --color-gray-800: #1f2937;
  --color-gray-900: #111827;

  /* Semantic colors */
  --color-primary: var(--color-brand-primary);
  --color-secondary: var(--color-brand-secondary);
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;

  /* Text colors */
  --color-text-primary: var(--color-gray-900);
  --color-text-secondary: var(--color-gray-600);
  --color-text-tertiary: var(--color-gray-500);
  --color-text-disabled: var(--color-gray-400);

  /* Background colors */
  --color-bg-primary: #ffffff;
  --color-bg-secondary: var(--color-gray-50);
  --color-bg-tertiary: var(--color-gray-100);

  /* Border colors */
  --color-border-light: var(--color-gray-200);
  --color-border-medium: var(--color-gray-300);
  --color-border-dark: var(--color-gray-400);
}
```

**Naming conventions:**
- Palette: `--color-{name}-{shade}` (e.g., `--color-blue-500`)
- Semantic: `--color-{purpose}` (e.g., `--color-primary`)
- Contextual: `--color-{element}-{state}` (e.g., `--color-button-hover`)

---

### Typography Tokens

```css
:root {
  /* Font families */
  --font-family-base: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-family-mono: 'Fira Code', 'Courier New', monospace;
  --font-family-display: 'Playfair Display', Georgia, serif;

  /* Font sizes - Modular scale (1.25 ratio) */
  --font-size-xs: 0.64rem;    /* 10px */
  --font-size-sm: 0.8rem;     /* 13px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.25rem;    /* 20px */
  --font-size-xl: 1.563rem;   /* 25px */
  --font-size-2xl: 1.953rem;  /* 31px */
  --font-size-3xl: 2.441rem;  /* 39px */
  --font-size-4xl: 3.052rem;  /* 49px */

  /* Font weights */
  --font-weight-light: 300;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* Line heights */
  --line-height-tight: 1.25;
  --line-height-base: 1.5;
  --line-height-loose: 1.75;

  /* Letter spacing */
  --letter-spacing-tight: -0.02em;
  --letter-spacing-normal: 0;
  --letter-spacing-wide: 0.02em;
}
```

---

### Spacing Tokens

```css
:root {
  /* Spacing scale - 8px base */
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
  --space-16: 8rem;     /* 128px */

  /* Semantic spacing */
  --space-xs: var(--space-1);
  --space-sm: var(--space-2);
  --space-md: var(--space-4);
  --space-lg: var(--space-6);
  --space-xl: var(--space-8);
}
```

**Spacing guidelines:**
- Components: 8px, 16px, 24px
- Sections: 32px, 48px, 64px
- Page margins: 16px (mobile), 24px (tablet), 32px (desktop)

---

### Layout Tokens

```css
:root {
  /* Breakpoints */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;

  /* Container widths */
  --container-sm: 640px;
  --container-md: 768px;
  --container-lg: 1024px;
  --container-xl: 1280px;

  /* Z-index scale */
  --z-index-dropdown: 1000;
  --z-index-sticky: 1020;
  --z-index-fixed: 1030;
  --z-index-modal-backdrop: 1040;
  --z-index-modal: 1050;
  --z-index-popover: 1060;
  --z-index-tooltip: 1070;
}
```

---

### Visual Effect Tokens

```css
:root {
  /* Border radius */
  --border-radius-none: 0;
  --border-radius-sm: 0.25rem;   /* 4px */
  --border-radius-base: 0.5rem;  /* 8px */
  --border-radius-lg: 1rem;      /* 16px */
  --border-radius-xl: 1.5rem;    /* 24px */
  --border-radius-full: 9999px;

  /* Border widths */
  --border-width-thin: 1px;
  --border-width-base: 2px;
  --border-width-thick: 4px;

  /* Shadows - Material Design inspired */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-base: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04);
  --shadow-xl: 0 25px 50px rgba(0, 0, 0, 0.25);

  /* Transitions */
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-slow: 350ms;

  --easing-standard: cubic-bezier(0.4, 0.0, 0.2, 1);
  --easing-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1);
  --easing-accelerate: cubic-bezier(0.4, 0.0, 1, 1);

  /* Opacity */
  --opacity-disabled: 0.5;
  --opacity-hover: 0.8;
  --opacity-backdrop: 0.6;
}
```
