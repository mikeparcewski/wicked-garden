# Common Design Issues and Fixes: Component Issues

## Component Issues

### 1. Duplicate Button Components

**Issue:** Multiple button implementations with slight variations.

```jsx
/* ✗ BAD - Separate components */
<PrimaryButton>Submit</PrimaryButton>
<SecondaryButton>Cancel</SecondaryButton>
<TertiaryButton>Learn More</TertiaryButton>
<BlueButton>Submit</BlueButton>

/* ✓ GOOD - Single component with variants */
<Button variant="primary">Submit</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="tertiary">Learn More</Button>
```

**Consolidation Strategy:**
```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
}

function Button({ variant = 'primary', size = 'md', ...props }: ButtonProps) {
  return (
    <button className={`button button-${variant} button-${size}`} {...props} />
  );
}
```

---

### 2. Missing Component States

**Issue:** Interactive elements missing hover, focus, or disabled states.

```css
/* ✗ BAD - Only default state */
.button {
  background: #0066cc;
  color: white;
}

/* ✓ GOOD - All states */
.button {
  background: var(--color-primary);
  color: var(--color-on-primary);
  transition: background var(--duration-base);
}

.button:hover {
  background: var(--color-primary-dark);
}

.button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.button:active {
  transform: translateY(1px);
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button.loading {
  position: relative;
  color: transparent;
}

.button.loading::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
```

**Required States:**
- Default
- Hover
- Focus (keyboard)
- Active/pressed
- Disabled
- Loading (if applicable)

---

### 3. Inconsistent Card Components

**Issue:** Multiple card styles without clear pattern.

```jsx
/* ✗ BAD - Inconsistent cards */
<div className="product-card">...</div>
<div className="article-card">...</div>
<div className="user-card">...</div>

/* All have different:
   - Border radius (8px, 12px, 16px)
   - Shadows (0 2px 4px, 0 4px 8px)
   - Padding (16px, 20px, 24px)
*/

/* ✓ GOOD - Consistent card */
<Card>
  <CardMedia>...</CardMedia>
  <CardContent>...</CardContent>
  <CardActions>...</CardActions>
</Card>

/* Consistent:
   - Border radius: var(--border-radius-lg)
   - Shadow: var(--shadow-md)
   - Padding: var(--space-5)
*/
```

---

## Responsive Issues

### 1. Inconsistent Breakpoints

**Issue:** Custom breakpoints instead of design system values.

```css
/* ✗ BAD - Random breakpoints */
@media (min-width: 600px) { }
@media (min-width: 850px) { }
@media (min-width: 1100px) { }
@media (min-width: 1400px) { }

/* ✓ GOOD - Design system breakpoints */
@media (min-width: 640px) { }   /* sm */
@media (min-width: 768px) { }   /* md */
@media (min-width: 1024px) { }  /* lg */
@media (min-width: 1280px) { }  /* xl */
```

---

### 2. Inadequate Touch Targets

**Issue:** Interactive elements too small for touch.

```css
/* ✗ BAD - Too small */
.icon-button {
  width: 24px;
  height: 24px;
  padding: 0;
}

/* ✓ GOOD - Adequate touch target */
.icon-button {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.icon-button svg {
  width: 24px;
  height: 24px;
}
```

**Touch Target Guidelines:**
- Minimum: 44x44px (iOS)
- Recommended: 48x48px (Material Design)
- Between targets: 8px spacing minimum

---

### 3. Non-Responsive Typography

**Issue:** Fixed font sizes across all screen sizes.

```css
/* ✗ BAD - Fixed size */
h1 {
  font-size: 2.5rem;
}

/* ✓ GOOD - Responsive */
h1 {
  font-size: 2rem;  /* 32px on mobile */
}

@media (min-width: 768px) {
  h1 {
    font-size: 2.5rem;  /* 40px on tablet+ */
  }
}

@media (min-width: 1024px) {
  h1 {
    font-size: 3rem;  /* 48px on desktop */
  }
}

/* ✓ BETTER - Fluid typography */
h1 {
  font-size: clamp(2rem, 1rem + 3vw, 3rem);
}
```

---

## State and Feedback Issues

### 1. Missing Loading States

**Issue:** No indication that action is in progress.

```jsx
/* ✗ BAD - No loading state */
<button onClick={handleSubmit}>
  Submit
</button>

/* ✓ GOOD - Loading state */
<button onClick={handleSubmit} disabled={isLoading}>
  {isLoading ? (
    <>
      <Spinner size="sm" />
      Submitting...
    </>
  ) : (
    'Submit'
  )}
</button>
```

---

### 2. Missing Empty States

**Issue:** No design for empty lists/collections.

```jsx
/* ✗ BAD - Just empty */
{items.length === 0 && null}

/* ✓ GOOD - Helpful empty state */
{items.length === 0 ? (
  <EmptyState
    icon={<InboxIcon />}
    title="No items yet"
    description="Get started by creating your first item"
    action={<Button onClick={handleCreate}>Create Item</Button>}
  />
) : (
  <ItemList items={items} />
)}
```

---

### 3. Poor Error States

**Issue:** Generic or unhelpful error messages.

```jsx
/* ✗ BAD - Generic error */
<div className="error">Error occurred</div>

/* ✓ GOOD - Specific, actionable error */
<Alert severity="error">
  <AlertTitle>Upload Failed</AlertTitle>
  File size exceeds 5MB limit. Please compress your image and try again.
  <Button variant="text" onClick={handleRetry}>
    Retry Upload
  </Button>
</Alert>
```

---

