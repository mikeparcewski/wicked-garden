# Common Design Issues and Fixes: Color Issues

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

