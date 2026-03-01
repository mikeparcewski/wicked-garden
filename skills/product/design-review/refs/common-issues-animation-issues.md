# Common Design Issues and Fixes: Animation Issues

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
