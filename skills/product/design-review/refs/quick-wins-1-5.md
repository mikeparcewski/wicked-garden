# Quick Wins 1-5: Colors, Focus, Contrast, Buttons, Loading

Fast design improvements with high visual impact. First five quick wins covering foundational visual polish.

## What are Quick Wins?

Quick wins are design improvements that:
- **Take 1-3 hours** to implement
- **High visual impact** - users notice immediately
- **Low risk** - unlikely to break anything
- **Build momentum** - motivate team to tackle bigger issues

## 1. Extract Hardcoded Colors (1-2 hours)

**Impact**: Immediate visual consistency, easier theming

**How to do it:**

```bash
# Find all hardcoded colors
wicked-garden:search "#[0-9a-fA-F]{3,6}" --type css -A 2

# Create design tokens
```

**Before:**
```css
.button { background: #3b82f6; }
.link { color: #3b82f6; }
.badge { background: #ef4444; }
.alert { color: #ef4444; }
```

**After:**
```css
:root {
  --color-primary: #3b82f6;
  --color-error: #ef4444;
}

.button { background: var(--color-primary); }
.link { color: var(--color-primary); }
.badge { background: var(--color-error); }
.alert { color: var(--color-error); }
```

**Steps:**
1. Find all unique colors (5-10 minutes)
2. Create CSS variables (10 minutes)
3. Replace hardcoded values (30-60 minutes)
4. Test (10 minutes)

**Bonus**: Instant dark mode capability

---

## 2. Add Missing Focus States (1 hour)

**Impact**: Accessibility win, better keyboard UX

**Before:**
```css
.button {
  background: var(--color-primary);
}

.button:hover {
  background: var(--color-primary-dark);
}

/* No focus state! */
```

**After:**
```css
.button {
  background: var(--color-primary);
}

.button:hover {
  background: var(--color-primary-dark);
}

.button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

**Steps:**
1. Find all interactive elements (10 minutes)
2. Add focus-visible styles (30 minutes)
3. Test with keyboard navigation (20 minutes)

**Checklist:**
```
[] Buttons
[] Links
[] Inputs
[] Custom controls
[] Cards (if clickable)
```

---

## 3. Fix Color Contrast (30 min - 1 hour)

**Impact**: Accessibility compliance, readability

**Before:**
```css
.text-muted {
  color: #999;  /* 2.8:1 - fails WCAG */
}

.button-secondary {
  color: #aaa;  /* 2.3:1 - fails badly */
}
```

**After:**
```css
.text-muted {
  color: #666;  /* 4.6:1 - passes WCAG AA */
}

.button-secondary {
  color: #555;  /* 7.5:1 - passes WCAG AAA */
}
```

**Steps:**
1. Run contrast checker on all text (10 minutes)
   ```bash
   python3 scripts/contrast-check.py "#999" "#fff"
   ```
2. Darken insufficient colors (15 minutes)
3. Update design tokens (5 minutes)
4. Visual QA (10 minutes)

**Tools:**
- WebAIM Contrast Checker
- Browser DevTools
- Automated scanners (axe, Lighthouse)

---

## 4. Standardize Button Padding (1 hour)

**Impact**: Visual polish, clear hierarchy

**Before:**
```css
.button-primary { padding: 10px 20px; }
.button-secondary { padding: 8px 16px; }
.button-tertiary { padding: 12px 24px; }
.button-icon { padding: 6px; }
```

**After:**
```css
.button-sm { padding: var(--space-1) var(--space-3); }  /* 4px 12px */
.button-md { padding: var(--space-2) var(--space-4); }  /* 8px 16px */
.button-lg { padding: var(--space-3) var(--space-6); }  /* 12px 32px */
```

**Steps:**
1. Identify all button padding values (10 minutes)
2. Define 2-3 sizes (5 minutes)
3. Update all buttons (30 minutes)
4. Visual QA (15 minutes)

---

## 5. Add Loading States (1-2 hours)

**Impact**: Better perceived performance, user feedback

**Before:**
```jsx
<button onClick={handleSubmit}>
  Submit
</button>
```

**After:**
```jsx
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

**Steps:**
1. Identify async actions (15 minutes)
2. Add loading state variable (15 minutes)
3. Create spinner component (30 minutes)
4. Update button/form components (30 minutes)
5. Test (15 minutes)

**Bonus**: Add skeleton screens for content loading
