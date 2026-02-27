# Common Accessibility Violations and Fixes

Quick reference for the most frequent WCAG violations with before/after examples.

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

## 6. Inaccessible Custom Components

### Modal Without Proper ARIA

```html
<!-- ✗ VIOLATION -->
<div class="modal">
  <div class="modal-content">
    <h2>Confirm</h2>
    <button>OK</button>
  </div>
</div>

<!-- ✓ FIX -->
<div class="modal"
     role="dialog"
     aria-modal="true"
     aria-labelledby="modal-title">
  <div class="modal-content">
    <h2 id="modal-title">Confirm</h2>
    <button>OK</button>
  </div>
</div>
```

### Dropdown Menu

```html
<!-- ✗ VIOLATION -->
<button onclick="toggleMenu()">Menu</button>
<div id="menu" style="display:none">
  <a href="/home">Home</a>
  <a href="/about">About</a>
</div>

<!-- ✓ FIX -->
<button onclick="toggleMenu()"
        aria-expanded="false"
        aria-controls="menu">
  Menu
</button>
<div id="menu" hidden>
  <a href="/home">Home</a>
  <a href="/about">About</a>
</div>

<script>
function toggleMenu() {
  const button = document.querySelector('[aria-controls="menu"]');
  const menu = document.getElementById('menu');
  const isExpanded = button.getAttribute('aria-expanded') === 'true';

  button.setAttribute('aria-expanded', !isExpanded);
  menu.hidden = isExpanded;
}
</script>
```

### Tabs Without ARIA

```html
<!-- ✗ VIOLATION -->
<div class="tabs">
  <button onclick="showTab(1)">Tab 1</button>
  <button onclick="showTab(2)">Tab 2</button>
</div>
<div id="panel1">Content 1</div>
<div id="panel2" hidden>Content 2</div>

<!-- ✓ FIX -->
<div class="tabs" role="tablist">
  <button role="tab"
          aria-selected="true"
          aria-controls="panel1"
          id="tab1">
    Tab 1
  </button>
  <button role="tab"
          aria-selected="false"
          aria-controls="panel2"
          id="tab2">
    Tab 2
  </button>
</div>
<div id="panel1" role="tabpanel" aria-labelledby="tab1">
  Content 1
</div>
<div id="panel2" role="tabpanel" aria-labelledby="tab2" hidden>
  Content 2
</div>
```

## 7. Form Validation Errors

**WCAG**: 3.3.1 Error Identification, 3.3.3 Error Suggestion (Level A, AA)
**Impact**: Users don't know what's wrong or how to fix it

### Error Not Announced

```html
<!-- ✗ VIOLATION - Error shown visually only -->
<input type="email" id="email">
<span class="error" style="display:none;">Invalid email</span>

<!-- ✓ FIX -->
<label for="email">Email</label>
<input type="email"
       id="email"
       aria-describedby="email-error"
       aria-invalid="true">
<span id="email-error" role="alert" class="error">
  Please enter a valid email address
</span>
```

### Inline Validation

```javascript
// ✗ VIOLATION - No ARIA update
input.addEventListener('blur', () => {
  if (!isValid(input.value)) {
    errorDiv.style.display = 'block';
  }
});

// ✓ FIX - ARIA attributes + live region
input.addEventListener('blur', () => {
  if (!isValid(input.value)) {
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', 'error-id');
    errorDiv.setAttribute('role', 'alert');
    errorDiv.textContent = 'Please enter a valid value';
  }
});
```

## 8. Keyboard Navigation Issues

### Keyboard Trap

```javascript
// ✗ VIOLATION - Can't exit modal with keyboard
function openModal() {
  modal.style.display = 'block';
  modal.querySelector('button').focus();
}

// ✓ FIX - Escape key closes modal
modal.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
  }
});
```

### Missing Tab Index

```html
<!-- ✗ VIOLATION - Custom control not focusable -->
<div onclick="toggle()">Toggle</div>

<!-- ✓ FIX -->
<div tabindex="0"
     role="button"
     onclick="toggle()"
     onkeydown="if(event.key==='Enter'||event.key===' ')toggle()">
  Toggle
</div>
```

## 9. Dynamic Content Not Announced

**WCAG**: 4.1.3 Status Messages (Level AA)
**Impact**: Screen reader users miss important updates

### Loading State

```javascript
// ✗ VIOLATION - Visual spinner only
button.innerHTML = '<span class="spinner"></span>';

// ✓ FIX - Announce loading state
button.innerHTML = '<span role="status" aria-live="polite">Loading...</span>';
```

### Success Message

```javascript
// ✗ VIOLATION - Not announced
document.getElementById('message').textContent = 'Saved successfully';

// ✓ FIX - Use alert role
const message = document.getElementById('message');
message.setAttribute('role', 'alert');
message.textContent = 'Saved successfully';
```

### Live Region for Updates

```html
<!-- ✗ VIOLATION -->
<div id="results">
  <!-- Results updated via JS, but not announced -->
</div>

<!-- ✓ FIX -->
<div id="results" role="region" aria-live="polite" aria-atomic="true">
  <!-- Results announced when updated -->
</div>
```

## 10. Heading Structure Issues

**WCAG**: 2.4.6 Headings and Labels (Level AA)
**Impact**: Screen reader users can't navigate page structure

### Skipped Heading Levels

```html
<!-- ✗ VIOLATION - Skips from h1 to h3 -->
<h1>Page Title</h1>
<h3>Section Title</h3>

<!-- ✓ FIX -->
<h1>Page Title</h1>
<h2>Section Title</h2>
```

### Multiple H1s

```html
<!-- ✗ VIOLATION - Multiple h1s confuse page structure -->
<h1>Site Name</h1>
<h1>Page Title</h1>

<!-- ✓ FIX - Single h1 per page -->
<div class="site-name">Site Name</div>
<h1>Page Title</h1>
```

### Non-Descriptive Headings

```html
<!-- ✗ VIOLATION -->
<h2>Click Here</h2>

<!-- ✓ FIX -->
<h2>Download Annual Report</h2>
```

## Quick Testing Checklist

Use this checklist to catch most violations:

```
□ All images have alt text (or alt="" if decorative)
□ All form inputs have associated labels
□ Color contrast meets 4.5:1 (normal text) or 3:1 (large text)
□ All interactive elements use semantic HTML or ARIA
□ Focus indicators visible on all focusable elements
□ Custom components have proper ARIA roles and states
□ Form errors announced and linked to fields
□ No keyboard traps (can Tab through and Escape modals)
□ Dynamic updates use role="alert" or aria-live
□ Heading structure logical (single h1, no skipped levels)
```

## Automated Tools

Catch many of these violations automatically:

```bash
# Browser extensions
- axe DevTools
- WAVE
- Lighthouse

# CLI tools
npx @axe-core/cli https://example.com
npx pa11y https://example.com
```

## Priority Fixes

If you have limited time, fix these first:

1. **Missing alt text** - Screen readers completely miss content
2. **Form labels** - Users can't complete tasks
3. **Color contrast** - Text unreadable for many users
4. **Keyboard access** - Blocks keyboard-only users
5. **Focus indicators** - Users get lost

## Resources

- **WebAIM WCAG Checklist**: https://webaim.org/standards/wcag/checklist
- **A11Y Style Guide**: https://a11y-style-guide.com/
- **Inclusive Components**: https://inclusive-components.design/
