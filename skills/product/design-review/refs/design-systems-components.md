# Design Systems - Components and Documentation

Component library patterns, component anatomy, and documentation standards.

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
