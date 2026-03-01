# Responsive Design Guide: Responsive Typography

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

