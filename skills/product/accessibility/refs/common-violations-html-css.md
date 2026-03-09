# Common Accessibility Violations: HTML & CSS

Quick reference for the most frequent WCAG violations with before/after examples. Covers images, forms, contrast, semantics, and focus.

## 1. Missing Alternative Text

**WCAG**: 1.1.1 Non-text Content (Level A)
**Impact**: Screen readers can't describe images

### Images Without Alt

```html
<!-- ✗ VIOLATION -->
<img src="product.jpg">

<!-- ✓ FIX -->
<img src="product.jpg" alt="Red wireless headphones">
```

### Decorative Images

```html
<!-- ✗ VIOLATION - Unnecessary alt text -->
<img src="decorative-border.png" alt="border">

<!-- ✓ FIX - Empty alt for decorative images -->
<img src="decorative-border.png" alt="">
```

### Background Images with Content

```html
<!-- ✗ VIOLATION - Text in background image -->
<div style="background-image: url('hero-with-text.jpg')"></div>

<!-- ✓ FIX - Add ARIA label or visible text -->
<div style="background-image: url('hero-with-text.jpg')"
     role="img"
     aria-label="Welcome to our store - Shop now for 50% off">
</div>
```

### Icon Buttons

```html
<!-- ✗ VIOLATION -->
<button><i class="icon-trash"></i></button>

<!-- ✓ FIX -->
<button aria-label="Delete item">
  <i class="icon-trash" aria-hidden="true"></i>
</button>
```

## 2. Form Controls Without Labels

**WCAG**: 1.3.1 Info and Relationships, 3.3.2 Labels or Instructions (Level A)
**Impact**: Users don't know what to enter

### Missing Label

```html
<!-- ✗ VIOLATION -->
<input type="text" placeholder="Enter email">

<!-- ✓ FIX -->
<label for="email">Email address</label>
<input type="text" id="email" placeholder="e.g., user@example.com">
```

### Visual Label Without Association

```html
<!-- ✗ VIOLATION - Label not programmatically associated -->
<span>Username</span>
<input type="text" name="username">

<!-- ✓ FIX -->
<label for="username">Username</label>
<input type="text" id="username" name="username">
```

### Radio Buttons Without Fieldset

```html
<!-- ✗ VIOLATION - No grouping -->
<label><input type="radio" name="size" value="s"> Small</label>
<label><input type="radio" name="size" value="m"> Medium</label>
<label><input type="radio" name="size" value="l"> Large</label>

<!-- ✓ FIX -->
<fieldset>
  <legend>Select size</legend>
  <label><input type="radio" name="size" value="s"> Small</label>
  <label><input type="radio" name="size" value="m"> Medium</label>
  <label><input type="radio" name="size" value="l"> Large</label>
</fieldset>
```

### Hidden Label (Visual Design)

```html
<!-- ✗ VIOLATION - No label at all -->
<input type="search" placeholder="Search">

<!-- ✓ GOOD - Visible label -->
<label for="search">Search</label>
<input type="search" id="search">

<!-- ✓ ACCEPTABLE - Visually hidden label -->
<label for="search" class="sr-only">Search</label>
<input type="search" id="search" placeholder="Search products">

<style>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
```

## 3. Low Color Contrast

**WCAG**: 1.4.3 Contrast (Minimum) (Level AA)
**Impact**: Text hard to read for low vision users

### Insufficient Contrast

```html
<!-- ✗ VIOLATION - 2.5:1 contrast -->
<p style="color: #999; background: #fff;">Gray text</p>

<!-- ✓ FIX - 4.7:1 contrast -->
<p style="color: #666; background: #fff;">Dark gray text</p>
```

**Minimum ratios:**
- Normal text: 4.5:1
- Large text (18pt+ or 14pt+ bold): 3:1
- UI components and graphics: 3:1

### Common Color Pairs

```css
/* ✗ VIOLATIONS */
color: #777; background: #fff;     /* 4.4:1 - barely fails */
color: #999; background: #fff;     /* 2.8:1 - clear fail */
color: #0066ff; background: #fff;  /* 4.3:1 - fails for normal text */

/* ✓ PASSES */
color: #666; background: #fff;     /* 4.7:1 */
color: #595959; background: #fff;  /* 7:1 */
color: #0052cc; background: #fff;  /* 4.5:1 */
color: #fff; background: #0066ff;  /* 4.5:1 (white on blue) */
```

### Placeholder Contrast

```css
/* ✗ VIOLATION - Default browser placeholders often fail */
::placeholder {
  color: #ccc; /* Too light */
}

/* ✓ FIX */
::placeholder {
  color: #757575; /* 4.6:1 contrast */
}
```

## 4. Non-Semantic HTML

**WCAG**: 4.1.2 Name, Role, Value (Level A)
**Impact**: Screen readers announce incorrect element type

### Div/Span as Button

```html
<!-- ✗ VIOLATION -->
<div onclick="submit()">Submit</div>

<!-- ✓ FIX - Use semantic button -->
<button onclick="submit()">Submit</button>

<!-- ✓ ACCEPTABLE - If div required, add role and keyboard -->
<div role="button" tabindex="0"
     onclick="submit()"
     onkeydown="if(event.key==='Enter'||event.key===' ')submit()">
  Submit
</div>
```

### Non-Semantic Lists

```html
<!-- ✗ VIOLATION -->
<div>Item 1</div>
<div>Item 2</div>
<div>Item 3</div>

<!-- ✓ FIX -->
<ul>
  <li>Item 1</li>
  <li>Item 2</li>
  <li>Item 3</li>
</ul>
```

### Non-Semantic Headings

```html
<!-- ✗ VIOLATION -->
<div class="heading-large">Page Title</div>
<div class="heading-medium">Section Title</div>

<!-- ✓ FIX -->
<h1>Page Title</h1>
<h2>Section Title</h2>
```

## 5. Missing Focus Indicators

**WCAG**: 2.4.7 Focus Visible (Level AA)
**Impact**: Keyboard users can't see where they are

### Removed Outline

```css
/* ✗ VIOLATION */
*:focus {
  outline: none;
}

/* ✓ FIX - Custom accessible focus */
*:focus-visible {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}
```

### Invisible Focus on Custom Components

```css
/* ✗ VIOLATION - Focus blends in */
.button {
  background: #0066cc;
  color: white;
}
.button:focus {
  background: #0052cc; /* Too similar */
}

/* ✓ FIX - Clear focus state */
.button:focus-visible {
  outline: 2px solid white;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px #0066cc;
}
```
