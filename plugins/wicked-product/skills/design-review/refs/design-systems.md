# Design Systems Guide

Complete guide to building, maintaining, and governing design systems.

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

---

## Component Library

### Core Components

**Essential components every design system needs:**

1. **Button** - Primary action trigger
2. **Input** - Text entry
3. **Select** - Choice selection
4. **Checkbox** - Multiple selection
5. **Radio** - Single selection
6. **Toggle/Switch** - Binary choice
7. **Card** - Content container
8. **Modal/Dialog** - Focused interaction
9. **Alert/Notification** - System feedback
10. **Badge** - Status indicator

### Component Anatomy

**Example: Button Component**

```tsx
interface ButtonProps {
  /** Visual style variant */
  variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';

  /** Size */
  size?: 'sm' | 'md' | 'lg';

  /** Full width */
  fullWidth?: boolean;

  /** Disabled state */
  disabled?: boolean;

  /** Loading state */
  loading?: boolean;

  /** Icon before text */
  iconBefore?: React.ReactNode;

  /** Icon after text */
  iconAfter?: React.ReactNode;

  /** Click handler */
  onClick?: () => void;

  /** Children */
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  disabled = false,
  loading = false,
  iconBefore,
  iconAfter,
  onClick,
  children,
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'button',
        `button-${variant}`,
        `button-${size}`,
        fullWidth && 'button-full',
        loading && 'button-loading'
      )}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading && <Spinner size="sm" />}
      {!loading && iconBefore}
      <span>{children}</span>
      {!loading && iconAfter}
    </button>
  );
}
```

**CSS:**

```css
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-medium);
  border-radius: var(--border-radius-base);
  border: var(--border-width-base) solid transparent;
  cursor: pointer;
  transition: all var(--duration-base) var(--easing-standard);
  white-space: nowrap;
}

.button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.button:disabled {
  opacity: var(--opacity-disabled);
  cursor: not-allowed;
}

/* Variants */
.button-primary {
  background: var(--color-primary);
  color: white;
}

.button-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.button-secondary {
  background: var(--color-gray-100);
  color: var(--color-gray-900);
}

.button-tertiary {
  background: transparent;
  color: var(--color-primary);
  border-color: var(--color-primary);
}

/* Sizes */
.button-sm {
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-sm);
}

.button-md {
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-base);
}

.button-lg {
  padding: var(--space-3) var(--space-6);
  font-size: var(--font-size-lg);
}

/* Full width */
.button-full {
  width: 100%;
}

/* Loading */
.button-loading {
  position: relative;
  color: transparent;
}
```

---

## Component Documentation

**For each component, document:**

1. **Purpose**: What is this component for?
2. **When to use**: Appropriate use cases
3. **When not to use**: Inappropriate uses
4. **Props/API**: All available options
5. **Variants**: Different visual styles
6. **States**: All possible states
7. **Accessibility**: ARIA attributes, keyboard behavior
8. **Examples**: Code examples for common uses
9. **Do's and Don'ts**: Visual examples

**Example Documentation:**

```markdown
# Button

Primary action trigger for user interactions.

## When to use
- Submit forms
- Trigger actions
- Navigate to new pages
- Confirm dialogs

## When not to use
- Navigation within page (use Link)
- Toggling state (use Toggle/Switch)

## Variants
- **Primary**: Main call to action (limit to 1-2 per page)
- **Secondary**: Secondary actions
- **Tertiary**: Low-emphasis actions
- **Ghost**: Minimal visual weight
- **Danger**: Destructive actions

## Examples

### Basic usage
```tsx
<Button>Click me</Button>
```

### With icon
```tsx
<Button iconBefore={<SaveIcon />}>
  Save changes
</Button>
```

### Loading state
```tsx
<Button loading={isSubmitting}>
  Submit
</Button>
```

## Accessibility
- Uses semantic `<button>` element
- Keyboard: Space and Enter activate
- Focus indicator visible
- Disabled state prevents interaction
```

---

## Design System Governance

### Contribution Process

**1. Propose Change**
- Use RFC (Request for Comments) template
- Explain problem and proposed solution
- Include visual examples
- Tag relevant stakeholders

**2. Review**
- Design review: Visual consistency
- Eng review: Technical feasibility
- A11y review: Accessibility compliance

**3. Approval**
- Requires 2 approvals (design + eng)
- A11y approval for new patterns

**4. Implementation**
- Update design files (Figma/Sketch)
- Update component code
- Update documentation
- Add to changelog

**5. Announcement**
- Announce in team channels
- Update migration guide if breaking change
- Schedule office hours for questions

---

### Versioning

Use semantic versioning:

```
MAJOR.MINOR.PATCH

1.0.0 → 1.0.1 (patch: bug fix)
1.0.1 → 1.1.0 (minor: new feature, backward compatible)
1.1.0 → 2.0.0 (major: breaking change)
```

**Examples:**
- Add new component variant: Minor (1.0.0 → 1.1.0)
- Fix button hover state: Patch (1.0.0 → 1.0.1)
- Change component API: Major (1.0.0 → 2.0.0)

---

### Deprecation Policy

**When deprecating:**

1. **Announce** with version and timeline
2. **Document** migration path
3. **Provide** backward compatibility (1-2 major versions)
4. **Console warn** in deprecated component
5. **Remove** in next major version

**Example:**

```tsx
/** @deprecated Use Button variant="tertiary" instead. Will be removed in v3.0 */
export function OutlineButton(props) {
  console.warn('OutlineButton is deprecated. Use <Button variant="tertiary"> instead.');
  return <Button variant="tertiary" {...props} />;
}
```

---

## Design System Checklist

### Foundation
```
□ Design tokens defined (color, typography, spacing)
□ Tokens documented
□ Tokens versioned
□ Dark mode support (if needed)
```

### Components
```
□ Core components implemented
□ All states covered (hover, focus, disabled, loading, error)
□ Variants defined
□ Responsive behavior
□ Accessibility baseline met
□ Keyboard navigation
□ Screen reader support
```

### Documentation
```
□ Component API documented
□ Usage examples
□ Do's and don'ts
□ Accessibility notes
□ Migration guides
```

### Governance
```
□ Contribution process defined
□ Review process established
□ Versioning policy
□ Deprecation policy
□ Changelog maintained
```

### Tools
```
□ Component library (React/Vue/etc.)
□ Design files (Figma/Sketch)
□ Documentation site
□ Linting rules
□ Automated tests
```

---

## Maturity Model

### Level 1: Ad-hoc
- No design system
- Designers/developers create as needed
- Lots of duplication
- Hard to maintain

### Level 2: Emerging
- Some tokens defined
- Basic component library
- Minimal documentation
- Inconsistent usage

### Level 3: Established
- Comprehensive token system
- Well-documented components
- Governance process
- Wide adoption

### Level 4: Mature
- Tokens enforced via tooling
- Composable components
- Automated testing
- Active community
- Regular updates

---

## Success Metrics

Track these to measure design system health:

1. **Adoption rate**: % of product using design system
2. **Token usage**: % design tokens vs hardcoded values
3. **Component duplication**: # of similar components
4. **Contribution**: # contributions from team
5. **Satisfaction**: Team satisfaction score
6. **Time to ship**: Time to ship new features
7. **Design debt**: # design inconsistencies

---

## Tools and Resources

### Design Tools
- **Figma**: Component libraries, variants
- **Sketch**: Symbols, libraries
- **Adobe XD**: Components, design systems

### Development
- **Storybook**: Component explorer
- **Style Dictionary**: Transform design tokens
- **CSS-in-JS**: styled-components, Emotion
- **Tailwind**: Utility-first CSS

### Documentation
- **Docusaurus**: Documentation sites
- **Storybook Docs**: Component documentation
- **Notion**: Living documentation

### Inspiration
- **Material Design**: Google
- **Polaris**: Shopify
- **Lightning**: Salesforce
- **Primer**: GitHub
- **Ant Design**: Alibaba
- **Chakra UI**: Community

---

## Common Pitfalls

1. **Too early**: Building before you understand patterns
2. **Too complex**: Over-engineering with too many options
3. **No governance**: System diverges without process
4. **No adoption**: Team doesn't use it
5. **No evolution**: Becomes outdated
6. **Designer-developer gap**: Tools not in sync

---

## Key Takeaways

1. **Start small**: Core tokens + essential components
2. **Document as you go**: No docs = no adoption
3. **Govern actively**: Systems need maintenance
4. **Measure impact**: Track adoption and satisfaction
5. **Evolve continuously**: Regular updates and improvements

A design system is never "done" - it's a living product that grows with your team.
