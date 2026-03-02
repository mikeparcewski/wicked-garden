# ARIA Patterns - Basics and Attributes

ARIA fundamentals, common attributes, labeling, states, relationships, and live regions.

## ARIA Basics

**First Rule of ARIA**: Don't use ARIA if you can use native HTML.

```html
<!-- ✓ BEST - Native HTML -->
<button>Click me</button>

<!-- ⚠ ACCEPTABLE - When native HTML not available -->
<div role="button" tabindex="0">Click me</div>

<!-- ✗ UNNECESSARY - Don't add ARIA to semantic HTML -->
<button role="button">Click me</button>
```

**Five Rules of ARIA:**
1. Use native HTML when possible
2. Don't change native semantics (unless you really have to)
3. All interactive ARIA controls must be keyboard accessible
4. Don't use `role="presentation"` or `aria-hidden="true"` on focusable elements
5. All interactive elements must have an accessible name

## Common ARIA Attributes

### Labeling

```html
<!-- aria-label: Direct label -->
<button aria-label="Close dialog">
  <svg>...</svg>
</button>

<!-- aria-labelledby: Reference to visible label -->
<h2 id="dialog-title">Delete Account</h2>
<div role="dialog" aria-labelledby="dialog-title">
  ...
</div>

<!-- aria-describedby: Additional description -->
<input type="password"
       id="password"
       aria-describedby="password-requirements">
<div id="password-requirements">
  Must be at least 8 characters
</div>
```

### States

```html
<!-- aria-expanded: Collapsible content -->
<button aria-expanded="false" aria-controls="menu">
  Menu
</button>

<!-- aria-pressed: Toggle button -->
<button aria-pressed="false">
  Mute
</button>

<!-- aria-checked: Checkbox/radio (when not using native) -->
<div role="checkbox" aria-checked="false">
  Accept terms
</div>

<!-- aria-selected: Selected item in list -->
<div role="option" aria-selected="true">
  Option 1
</div>

<!-- aria-hidden: Hidden from screen readers -->
<span aria-hidden="true">★</span>
<span class="sr-only">Rating: 4 out of 5 stars</span>
```

### Relationships

```html
<!-- aria-controls: Element controls another -->
<button aria-controls="panel" aria-expanded="false">
  Toggle panel
</button>
<div id="panel" hidden>...</div>

<!-- aria-owns: Parent-child relationship -->
<div role="listbox" aria-owns="option1 option2 option3">
  <div role="option" id="option1">Option 1</div>
</div>

<!-- aria-activedescendant: Active child in composite widget -->
<div role="listbox" aria-activedescendant="option2">
  <div role="option" id="option1">Option 1</div>
  <div role="option" id="option2">Option 2</div>
</div>
```

### Live Regions

```html
<!-- aria-live: Announce updates -->
<div aria-live="polite">
  Item added to cart
</div>

<!-- role="alert": Immediate announcement (aria-live="assertive") -->
<div role="alert">
  Error: Form submission failed
</div>

<!-- role="status": Polite announcement (aria-live="polite") -->
<div role="status">
  Saving... Saved.
</div>

<!-- aria-atomic: Announce entire region or just changes -->
<div aria-live="polite" aria-atomic="true">
  Page 3 of 10
</div>
```

## Common Widget Patterns

### 1. Button

Use native `<button>` when possible. Use ARIA when absolutely necessary.

```html
<!-- ✓ Native button -->
<button>Click me</button>

<!-- ⚠ ARIA button (if div required) -->
<div role="button"
     tabindex="0"
     onclick="handleClick()"
     onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();handleClick();}">
  Click me
</div>
```

**Keyboard:** Enter and Space activate

### 2. Toggle Button

Button that switches between two states.

```html
<button type="button"
        aria-pressed="false"
        onclick="toggleMute(this)">
  <span aria-hidden="true">🔊</span>
  <span class="sr-only">Mute</span>
</button>

<script>
function toggleMute(button) {
  const pressed = button.getAttribute('aria-pressed') === 'true';
  button.setAttribute('aria-pressed', !pressed);
  // Update icon
  button.querySelector('[aria-hidden]').textContent = pressed ? '🔊' : '🔇';
  // Update label
  button.querySelector('.sr-only').textContent = pressed ? 'Mute' : 'Unmute';
}
</script>
```

**Keyboard:** Space toggles state

### 3. Checkbox (Custom)

```html
<div role="checkbox"
     aria-checked="false"
     tabindex="0"
     onclick="toggleCheckbox(this)"
     onkeydown="if(event.key===' '){event.preventDefault();toggleCheckbox(this);}">
  <span class="checkbox-icon" aria-hidden="true">☐</span>
  Accept terms and conditions
</div>

<script>
function toggleCheckbox(element) {
  const checked = element.getAttribute('aria-checked') === 'true';
  element.setAttribute('aria-checked', !checked);
  element.querySelector('.checkbox-icon').textContent = checked ? '☐' : '☑';
}
</script>
```

**Keyboard:** Space toggles state

### 4. Accordion

Collapsible sections.

```html
<div class="accordion">
  <!-- Section 1 -->
  <h3>
    <button aria-expanded="false"
            aria-controls="section1"
            id="accordion1">
      Section 1
    </button>
  </h3>
  <div id="section1"
       role="region"
       aria-labelledby="accordion1"
       hidden>
    <p>Content for section 1</p>
  </div>

  <!-- Section 2 -->
  <h3>
    <button aria-expanded="false"
            aria-controls="section2"
            id="accordion2">
      Section 2
    </button>
  </h3>
  <div id="section2"
       role="region"
       aria-labelledby="accordion2"
       hidden>
    <p>Content for section 2</p>
  </div>
</div>

<script>
document.querySelectorAll('[aria-controls]').forEach(button => {
  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', !expanded);
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    panel.hidden = expanded;
  });
});
</script>
```

**Keyboard:**
- Enter/Space: Toggle section
- Tab: Move between section headers
