# Responsive Design Guide

Complete guide to building responsive, mobile-first interfaces.

## Mobile-First Philosophy

**Mobile-first** means designing for mobile screens first, then progressively enhancing for larger screens.

**Why mobile-first?**
- Forces prioritization of content
- Easier to scale up than down
- Better performance (load less, enhance more)
- Majority of traffic is mobile

### Mobile-First CSS

```css
/* ✗ BAD - Desktop-first (requires overriding) */
.container {
  padding: 48px;        /* Desktop */
  font-size: 18px;
}

@media (max-width: 768px) {
  .container {
    padding: 16px;      /* Override for mobile */
    font-size: 16px;
  }
}

/* ✓ GOOD - Mobile-first (progressive enhancement) */
.container {
  padding: 16px;        /* Mobile */
  font-size: 16px;
}

@media (min-width: 768px) {
  .container {
    padding: 32px;      /* Tablet */
  }
}

@media (min-width: 1024px) {
  .container {
    padding: 48px;      /* Desktop */
    font-size: 18px;
  }
}
```

---

## Breakpoint System

### Standard Breakpoints

```css
:root {
  /* Mobile: 0-639px (default, no media query) */
  --breakpoint-sm: 640px;   /* Mobile landscape / Large phone */
  --breakpoint-md: 768px;   /* Tablet */
  --breakpoint-lg: 1024px;  /* Desktop */
  --breakpoint-xl: 1280px;  /* Large desktop */
  --breakpoint-2xl: 1536px; /* Extra large desktop */
}
```

**Device targeting:**
- **0-639px**: Mobile portrait
- **640-767px**: Mobile landscape
- **768-1023px**: Tablet
- **1024-1279px**: Desktop
- **1280+px**: Large desktop

### Using Breakpoints

```css
/* Mobile (default) */
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

/* Tablet */
@media (min-width: 768px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 24px;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 32px;
  }
}

/* Large desktop */
@media (min-width: 1280px) {
  .grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

---

## Layout Patterns

### 1. Container System

**Purpose**: Constrain content width for readability

```css
.container {
  width: 100%;
  padding-left: 16px;
  padding-right: 16px;
  margin-left: auto;
  margin-right: auto;
}

@media (min-width: 640px) {
  .container {
    max-width: 640px;
  }
}

@media (min-width: 768px) {
  .container {
    max-width: 768px;
    padding-left: 24px;
    padding-right: 24px;
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: 1024px;
    padding-left: 32px;
    padding-right: 32px;
  }
}

@media (min-width: 1280px) {
  .container {
    max-width: 1280px;
  }
}
```

---

### 2. Responsive Grid

**CSS Grid for complex layouts:**

```css
.grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
}

/* More control with breakpoints */
.grid-controlled {
  display: grid;
  grid-template-columns: 1fr;  /* Mobile: 1 column */
  gap: 16px;
}

@media (min-width: 768px) {
  .grid-controlled {
    grid-template-columns: repeat(2, 1fr);  /* Tablet: 2 columns */
    gap: 24px;
  }
}

@media (min-width: 1024px) {
  .grid-controlled {
    grid-template-columns: repeat(3, 1fr);  /* Desktop: 3 columns */
    gap: 32px;
  }
}
```

**Flexbox for simple layouts:**

```css
.flex-layout {
  display: flex;
  flex-direction: column;  /* Mobile: stack */
  gap: 16px;
}

@media (min-width: 768px) {
  .flex-layout {
    flex-direction: row;   /* Tablet+: side-by-side */
    gap: 24px;
  }
}
```

---

### 3. Sidebar Layout

**Collapsing sidebar pattern:**

```css
.layout {
  display: flex;
  flex-direction: column;
}

.sidebar {
  width: 100%;
  border-bottom: 1px solid var(--border-color);
}

.main {
  width: 100%;
  padding: 16px;
}

@media (min-width: 1024px) {
  .layout {
    flex-direction: row;
  }

  .sidebar {
    width: 280px;
    border-bottom: none;
    border-right: 1px solid var(--border-color);
  }

  .main {
    flex: 1;
    padding: 32px;
  }
}
```

---

### 4. Card Grid

**Responsive card layout:**

```css
.card-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;  /* Mobile: 1 per row */
}

@media (min-width: 640px) {
  .card-grid {
    grid-template-columns: repeat(2, 1fr);  /* 2 per row */
  }
}

@media (min-width: 1024px) {
  .card-grid {
    grid-template-columns: repeat(3, 1fr);  /* 3 per row */
    gap: 24px;
  }
}

@media (min-width: 1280px) {
  .card-grid {
    grid-template-columns: repeat(4, 1fr);  /* 4 per row */
  }
}
```

---

## Responsive Typography

### Fluid Typography

**Approach 1: Breakpoint-based**

```css
body {
  font-size: 16px;      /* Mobile */
  line-height: 1.5;
}

@media (min-width: 768px) {
  body {
    font-size: 17px;    /* Tablet */
  }
}

@media (min-width: 1024px) {
  body {
    font-size: 18px;    /* Desktop */
  }
}

h1 {
  font-size: 2rem;      /* 32px mobile */
}

@media (min-width: 768px) {
  h1 {
    font-size: 2.5rem;  /* 42.5px tablet */
  }
}

@media (min-width: 1024px) {
  h1 {
    font-size: 3rem;    /* 54px desktop */
  }
}
```

**Approach 2: Fluid with clamp()**

```css
/* Scales smoothly between min and max */
h1 {
  font-size: clamp(2rem, 1rem + 3vw, 3rem);
  /* min: 32px, max: 48px, scales with viewport */
}

h2 {
  font-size: clamp(1.5rem, 0.875rem + 2vw, 2.25rem);
}

body {
  font-size: clamp(1rem, 0.875rem + 0.5vw, 1.125rem);
}
```

---

## Responsive Spacing

```css
.section {
  padding: 32px 16px;   /* Mobile: smaller spacing */
}

@media (min-width: 768px) {
  .section {
    padding: 48px 24px; /* Tablet: medium spacing */
  }
}

@media (min-width: 1024px) {
  .section {
    padding: 64px 32px; /* Desktop: larger spacing */
  }
}

/* Responsive margin utilities */
.mb-responsive {
  margin-bottom: 16px;
}

@media (min-width: 768px) {
  .mb-responsive {
    margin-bottom: 24px;
  }
}

@media (min-width: 1024px) {
  .mb-responsive {
    margin-bottom: 32px;
  }
}
```

---

## Touch Targets

### Minimum Touch Target Size

**Guidelines:**
- iOS: 44x44px minimum
- Material Design: 48x48px minimum
- W3C: 44x44px minimum

**Implementation:**

```css
/* ✗ BAD - Too small for touch */
.icon-button {
  width: 24px;
  height: 24px;
  padding: 0;
}

/* ✓ GOOD - Adequate touch target */
.icon-button {
  /* Visual icon is 24px, but touch area is 48px */
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

### Touch Target Spacing

```css
/* Minimum 8px spacing between touch targets */
.button-group {
  display: flex;
  gap: 8px;
}

/* Better: 16px for easier tapping */
.button-group-comfortable {
  display: flex;
  gap: 16px;
}
```

---

## Responsive Images

### Approach 1: CSS max-width

```css
img {
  max-width: 100%;
  height: auto;
}
```

### Approach 2: srcset for resolution

```html
<img
  src="image-800w.jpg"
  srcset="
    image-400w.jpg 400w,
    image-800w.jpg 800w,
    image-1200w.jpg 1200w
  "
  sizes="
    (min-width: 1024px) 800px,
    (min-width: 768px) 600px,
    100vw
  "
  alt="Description"
>
```

### Approach 3: Picture element

```html
<picture>
  <!-- Desktop: landscape image -->
  <source
    media="(min-width: 1024px)"
    srcset="hero-desktop.jpg"
  >
  <!-- Tablet: square image -->
  <source
    media="(min-width: 768px)"
    srcset="hero-tablet.jpg"
  >
  <!-- Mobile: portrait image -->
  <img src="hero-mobile.jpg" alt="Hero">
</picture>
```

---

## Responsive Navigation

### Hamburger Menu Pattern

```html
<nav class="navbar">
  <div class="navbar-brand">Logo</div>

  <button class="navbar-toggle" aria-label="Toggle menu">
    ☰
  </button>

  <div class="navbar-menu">
    <a href="/home">Home</a>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
  </div>
</nav>
```

```css
/* Mobile: hidden menu */
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
}

.navbar-menu {
  display: none;
  flex-direction: column;
  position: absolute;
  top: 60px;
  left: 0;
  right: 0;
  background: white;
  padding: 16px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.navbar-menu.is-active {
  display: flex;
}

.navbar-toggle {
  display: block;
}

/* Desktop: always visible menu */
@media (min-width: 1024px) {
  .navbar-menu {
    display: flex;
    flex-direction: row;
    position: static;
    box-shadow: none;
    gap: 24px;
  }

  .navbar-toggle {
    display: none;
  }
}
```

---

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
