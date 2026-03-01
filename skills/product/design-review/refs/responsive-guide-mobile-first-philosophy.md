# Responsive Design Guide: Mobile-First Philosophy

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

