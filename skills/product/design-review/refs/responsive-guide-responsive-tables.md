# Responsive Design Guide: Responsive Tables

## Responsive Tables

### Approach 1: Horizontal Scroll

```css
.table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

table {
  min-width: 600px;
  width: 100%;
}
```

### Approach 2: Stacked Cards

```css
/* Mobile: Stack as cards */
@media (max-width: 767px) {
  table, thead, tbody, th, td, tr {
    display: block;
  }

  thead {
    display: none;
  }

  tr {
    margin-bottom: 16px;
    border: 1px solid #ddd;
    padding: 16px;
  }

  td {
    padding: 8px 0;
    border: none;
  }

  td::before {
    content: attr(data-label);
    font-weight: bold;
    display: block;
    margin-bottom: 4px;
  }
}
```

```html
<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Email</th>
      <th>Role</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td data-label="Name">Jane Doe</td>
      <td data-label="Email">jane@example.com</td>
      <td data-label="Role">Admin</td>
    </tr>
  </tbody>
</table>
```

---

## Responsive Forms

```css
/* Mobile: Full width inputs */
.form-group {
  margin-bottom: 16px;
}

.form-control {
  width: 100%;
  padding: 12px;
  font-size: 16px;  /* Prevents zoom on iOS */
}

/* Desktop: Grid layout for multi-column forms */
@media (min-width: 768px) {
  .form-row {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .form-group-full {
    grid-column: 1 / -1;
  }
}
```

---

## Hiding/Showing Content

### Display Utilities

```css
/* Hide on mobile, show on desktop */
.hide-mobile {
  display: none;
}

@media (min-width: 1024px) {
  .hide-mobile {
    display: block;
  }
}

/* Show on mobile, hide on desktop */
.show-mobile {
  display: block;
}

@media (min-width: 1024px) {
  .show-mobile {
    display: none;
  }
}
```

**Use sparingly** - hiding content hurts mobile users.

---

## Testing Responsive Design

### Browser DevTools

1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Test common devices:
   - iPhone SE (375px)
   - iPhone 12 Pro (390px)
   - iPad (768px)
   - Desktop (1280px)

### Real Device Testing

**Essential devices:**
- Small phone (iPhone SE, 375px)
- Large phone (iPhone 12 Pro, 390px)
- Tablet (iPad, 768px)
- Desktop (1280px+)

### Responsive Checklist

```
□ Layout doesn't break at any width
□ Text readable without zooming
□ Touch targets ≥48x48px
□ No horizontal scroll (unless intentional)
□ Images scale properly
□ Navigation accessible
□ Forms usable on mobile
□ Tables handle overflow
□ Performance good on mobile
```

---

## Common Responsive Patterns

### 1. Stack to Row

```css
.stack-to-row {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 768px) {
  .stack-to-row {
    flex-direction: row;
  }
}
```

### 2. Collapsing Columns

```css
.columns {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 768px) {
  .columns {
    grid-template-columns: 1fr 1fr;
  }
}

@media (min-width: 1024px) {
  .columns {
    grid-template-columns: 2fr 1fr;
  }
}
```

### 3. Reordering Content

```css
.content {
  display: flex;
  flex-direction: column;
}

.sidebar {
  order: 1;  /* Sidebar first on mobile */
}

.main {
  order: 2;
}

@media (min-width: 1024px) {
  .content {
    flex-direction: row;
  }

  .sidebar {
    order: 2;  /* Sidebar last on desktop */
  }

  .main {
    order: 1;
  }
}
```

---

## Responsive Best Practices

### Do's
- ✓ Design mobile-first
- ✓ Use relative units (rem, em, %)
- ✓ Test on real devices
- ✓ Optimize touch targets
- ✓ Use semantic HTML
- ✓ Progressive enhancement

### Don'ts
- ✗ Desktop-first with max-width media queries
- ✗ Fixed pixel widths
- ✗ Tiny touch targets
- ✗ Hide important content on mobile
- ✗ Different content mobile vs desktop
- ✗ Rely on hover (doesn't exist on touch)

---

## Performance Considerations

```html
<!-- Load smaller images on mobile -->
<picture>
  <source
    media="(min-width: 1024px)"
    srcset="large.jpg"
  >
  <source
    media="(min-width: 768px)"
    srcset="medium.jpg"
  >
  <img src="small.jpg" alt="">
</picture>

<!-- Lazy load off-screen images -->
<img src="image.jpg" loading="lazy" alt="">
```

---

## Key Takeaways

1. **Mobile-first** - Design for small screens, enhance for large
2. **Flexible layouts** - Use relative units and flexbox/grid
3. **Touch targets** - Minimum 48x48px
4. **Test on devices** - DevTools + real devices
5. **Performance** - Optimize images and assets for mobile
6. **Content parity** - Don't hide important content on mobile

Responsive design isn't just about making things fit - it's about optimizing the experience for each device.
