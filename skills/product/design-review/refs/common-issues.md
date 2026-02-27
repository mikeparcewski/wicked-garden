# Common Design Issues and Fixes

Catalog of frequently encountered design inconsistencies with before/after examples.

## Color Issues

### 1. Hardcoded Colors

**Issue:** Colors defined inline instead of using design tokens.

```css
/* ✗ BAD - Hardcoded hex values */
.button-primary {
  background: #3b82f6;
  color: #ffffff;
}

.button-primary:hover {
  background: #2563eb;
}

/* ✓ GOOD - Design tokens */
.button-primary {
  background: var(--color-primary);
  color: var(--color-on-primary);
}

.button-primary:hover {
  background: var(--color-primary-dark);
}
```

**How to Find:**
```bash
wicked-search "#[0-9a-fA-F]{3,6}" --type css
wicked-search "rgb\(" --type css
```

**Fix Strategy:**
1. Extract all unique colors
2. Create design token for each
3. Replace hardcoded values
4. Document color palette

---

### 2. Insufficient Color Contrast

**Issue:** Text doesn't meet WCAG contrast requirements.

```css
/* ✗ BAD - 2.8:1 contrast (fails WCAG AA) */
.text-muted {
  color: #999999;
  background: #ffffff;
}

/* ✓ GOOD - 4.6:1 contrast (passes WCAG AA) */
.text-muted {
  color: #666666;
  background: #ffffff;
}
```

**How to Find:**
```bash
python3 scripts/contrast-check.py "#999999" "#ffffff"
# Output: 2.8:1 - FAIL (AA)

python3 scripts/contrast-check.py "#666666" "#ffffff"
# Output: 4.6:1 - PASS (AA)
```

**Common Violations:**
- Light gray on white: #aaa on #fff (2.9:1)
- Placeholder text: Often too light
- Disabled text: Can be too light
- Link colors: Blue may fail on some backgrounds

**WCAG Requirements:**
- Normal text: 4.5:1 minimum
- Large text (18pt+ or 14pt+ bold): 3:1 minimum
- UI components: 3:1 minimum

---

### 3. Color as Only Indicator

**Issue:** Information conveyed by color alone.

```html
<!-- ✗ BAD - Only color indicates state -->
<button class="success">Submit</button>
<style>
  .success { color: green; }
  .error { color: red; }
</style>

<!-- ✓ GOOD - Icon + color -->
<button class="success">
  <svg aria-hidden="true">✓</svg>
  Submit
</button>
<button class="error">
  <svg aria-hidden="true">✗</svg>
  Error
</button>
```

---

## Typography Issues

### 1. Magic Number Font Sizes

**Issue:** Custom font sizes instead of type scale.

```css
/* ✗ BAD - Random sizes */
h1 { font-size: 34px; }
h2 { font-size: 27px; }
.subtitle { font-size: 19px; }
.small-text { font-size: 13.5px; }

/* ✓ GOOD - Type scale */
h1 { font-size: var(--font-size-3xl); }    /* 2.441rem / 39px */
h2 { font-size: var(--font-size-2xl); }    /* 1.953rem / 31px */
.subtitle { font-size: var(--font-size-lg); }  /* 1.25rem / 20px */
.small-text { font-size: var(--font-size-sm); } /* 0.8rem / 13px */
```

**Type Scale Ratios:**
- Minor Third: 1.2
- Major Third: 1.25 ✓ (recommended)
- Perfect Fourth: 1.333
- Golden Ratio: 1.618

---

### 2. Inconsistent Line Heights

**Issue:** Line heights don't scale with font size.

```css
/* ✗ BAD - Fixed line height */
h1 { font-size: 2rem; line-height: 1.5; }
p { font-size: 1rem; line-height: 1.5; }

/* ✓ GOOD - Proportional line heights */
h1 {
  font-size: var(--font-size-3xl);
  line-height: var(--line-height-tight);  /* 1.25 */
}

p {
  font-size: var(--font-size-base);
  line-height: var(--line-height-base);   /* 1.5 */
}

small {
  font-size: var(--font-size-sm);
  line-height: var(--line-height-loose);  /* 1.75 */
}
```

**Guidelines:**
- Headings: 1.2 - 1.3 (tighter)
- Body text: 1.5 - 1.6 (comfortable)
- Small text: 1.6 - 1.8 (more space)

---

### 3. Too Many Font Families

**Issue:** Using multiple font families inconsistently.

```css
/* ✗ BAD - Font soup */
body { font-family: 'Roboto', sans-serif; }
h1 { font-family: 'Playfair Display', serif; }
.nav { font-family: 'Montserrat', sans-serif; }
code { font-family: 'Courier New', monospace; }
.special { font-family: 'Pacifico', cursive; }

/* ✓ GOOD - 1-2 families */
body {
  font-family: var(--font-family-base);  /* Inter */
}

code, pre {
  font-family: var(--font-family-mono);  /* Fira Code */
}
```

**Best Practice:**
- 1 font family: Safest, most consistent
- 2 font families: Base + monospace, or Base + display

---

## Spacing Issues

### 1. Magic Number Spacing

**Issue:** Arbitrary padding/margin values.

```css
/* ✗ BAD - Random spacing */
.card {
  padding: 17px 23px;
  margin-bottom: 19px;
}

.section {
  padding: 47px 31px;
}

/* ✓ GOOD - Spacing scale */
.card {
  padding: var(--space-4) var(--space-5);  /* 16px 24px */
  margin-bottom: var(--space-4);            /* 16px */
}

.section {
  padding: var(--space-10) var(--space-6);  /* 64px 32px */
}
```

**How to Find:**
```bash
wicked-search "(padding|margin):\s*[0-9]+(px|rem)" --type css
```

---

### 2. Inconsistent Component Spacing

**Issue:** Same component with different spacing.

```css
/* ✗ BAD - Inconsistent button padding */
.button-primary {
  padding: 8px 16px;
}

.button-secondary {
  padding: 10px 20px;
}

.button-tertiary {
  padding: 6px 12px;
}

/* ✓ GOOD - Consistent sizes */
.button {
  padding: var(--space-2) var(--space-4);  /* Base: 8px 16px */
}

.button-sm {
  padding: var(--space-1) var(--space-3);  /* 4px 12px */
}

.button-lg {
  padding: var(--space-3) var(--space-6);  /* 12px 32px */
}
```

---

### 3. Broken Vertical Rhythm

**Issue:** Inconsistent spacing between sections/elements.

```css
/* ✗ BAD - Random spacing */
.section:not(:last-child) { margin-bottom: 35px; }
.paragraph { margin-bottom: 14px; }
.heading { margin-bottom: 11px; }

/* ✓ GOOD - Rhythmic spacing */
.section:not(:last-child) {
  margin-bottom: var(--space-10);  /* 64px */
}

.paragraph {
  margin-bottom: var(--space-4);   /* 16px */
}

.heading {
  margin-bottom: var(--space-3);   /* 12px */
}
```

**Vertical Rhythm Guidelines:**
- Sections: 48-64px
- Paragraphs: 16-24px
- Headings to content: 8-12px
- List items: 8px

---

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

## Animation Issues

### 1. Inconsistent Transition Durations

**Issue:** Random animation speeds.

```css
/* ✗ BAD */
.button { transition: all 0.2s; }
.modal { transition: all 0.35s; }
.dropdown { transition: all 0.15s; }

/* ✓ GOOD */
.button {
  transition: background var(--duration-base);  /* 250ms */
}

.modal {
  transition: opacity var(--duration-slow);     /* 350ms */
}

.dropdown {
  transition: opacity var(--duration-fast);     /* 150ms */
}
```

**Duration Guidelines:**
- Fast (150ms): Hover states, dropdowns
- Base (250ms): Buttons, simple transitions
- Slow (350ms): Modals, page transitions

---

### 2. Missing Reduced Motion Support

**Issue:** Animations can cause motion sickness.

```css
/* ✗ BAD - Always animates */
.animated {
  animation: slide-in 0.5s ease;
}

/* ✓ GOOD - Respects user preference */
.animated {
  animation: slide-in 0.5s ease;
}

@media (prefers-reduced-motion: reduce) {
  .animated {
    animation: none;
  }
}
```

---

## Focus and Accessibility Issues

### 1. Missing Focus Indicators

**Issue:** Focus state invisible or removed.

```css
/* ✗ BAD - Removes focus */
*:focus {
  outline: none;
}

/* ✓ GOOD - Visible focus */
*:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

---

### 2. Non-Semantic HTML

**Issue:** Divs/spans instead of semantic elements.

```html
<!-- ✗ BAD -->
<div class="button" onclick="submit()">Submit</div>

<!-- ✓ GOOD -->
<button onclick="submit()">Submit</button>
```

---

## Quick Reference: Common Fixes

### Color
- Extract to design tokens
- Check contrast (4.5:1 for text)
- Add non-color indicators

### Typography
- Use type scale (not magic numbers)
- Limit font families (1-2)
- Proportional line heights

### Spacing
- Use spacing scale (8px grid)
- Consistent component spacing
- Maintain vertical rhythm

### Components
- Consolidate duplicates
- Implement all states
- Standardize patterns

### Responsive
- Use design system breakpoints
- 48x48px touch targets
- Responsive typography

### States
- Add loading states
- Design empty states
- Specific error messages

### Animation
- Consistent durations
- Reduced motion support
- Use CSS variables

### Accessibility
- Visible focus indicators
- Semantic HTML
- Color contrast

---

## Automated Detection

```bash
# Colors
wicked-search "#[0-9a-fA-F]{3,6}" --type css

# Spacing
wicked-search "(padding|margin):\s*[0-9]+(px|rem)" --type css

# Typography
wicked-search "font-size:\s*[0-9]+(px|rem)" --type css

# Breakpoints
wicked-search "@media.*min-width" --type css

# Focus removal (danger!)
wicked-search "outline:\s*(none|0)" --type css
```

---

## Success Metrics

**Issues are fixed when:**
- Design tokens replace hardcoded values
- Type scale eliminates magic numbers
- Components consolidated
- All states implemented
- Accessibility baseline met
- Automated checks pass
