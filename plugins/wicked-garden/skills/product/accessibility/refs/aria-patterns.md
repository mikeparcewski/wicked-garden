# ARIA Patterns and Implementation Guide

Complete reference for implementing accessible custom components using ARIA.

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

### 5. Tabs

Tab interface for switching between panels.

```html
<div class="tabs">
  <div role="tablist" aria-label="Product details">
    <button role="tab"
            aria-selected="true"
            aria-controls="panel1"
            id="tab1"
            tabindex="0">
      Description
    </button>
    <button role="tab"
            aria-selected="false"
            aria-controls="panel2"
            id="tab2"
            tabindex="-1">
      Specifications
    </button>
    <button role="tab"
            aria-selected="false"
            aria-controls="panel3"
            id="tab3"
            tabindex="-1">
      Reviews
    </button>
  </div>

  <div id="panel1" role="tabpanel" aria-labelledby="tab1">
    <p>Product description...</p>
  </div>
  <div id="panel2" role="tabpanel" aria-labelledby="tab2" hidden>
    <p>Product specifications...</p>
  </div>
  <div id="panel3" role="tabpanel" aria-labelledby="tab3" hidden>
    <p>Product reviews...</p>
  </div>
</div>

<script>
const tablist = document.querySelector('[role="tablist"]');
const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));

tabs.forEach(tab => {
  tab.addEventListener('click', () => selectTab(tab));

  tab.addEventListener('keydown', (e) => {
    const index = tabs.indexOf(tab);
    let nextTab;

    if (e.key === 'ArrowRight') {
      nextTab = tabs[(index + 1) % tabs.length];
    } else if (e.key === 'ArrowLeft') {
      nextTab = tabs[(index - 1 + tabs.length) % tabs.length];
    } else if (e.key === 'Home') {
      nextTab = tabs[0];
    } else if (e.key === 'End') {
      nextTab = tabs[tabs.length - 1];
    }

    if (nextTab) {
      e.preventDefault();
      selectTab(nextTab);
      nextTab.focus();
    }
  });
});

function selectTab(selectedTab) {
  tabs.forEach(tab => {
    const isSelected = tab === selectedTab;
    tab.setAttribute('aria-selected', isSelected);
    tab.tabIndex = isSelected ? 0 : -1;

    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    panel.hidden = !isSelected;
  });
}
</script>
```

**Keyboard:**
- Tab: Move into/out of tab list
- Arrow Left/Right: Navigate between tabs
- Home/End: Jump to first/last tab
- Enter/Space: Activate focused tab (optional - can auto-activate on focus)

### 6. Modal Dialog

```html
<div role="dialog"
     aria-modal="true"
     aria-labelledby="dialog-title"
     aria-describedby="dialog-desc">
  <h2 id="dialog-title">Confirm Delete</h2>
  <p id="dialog-desc">
    Are you sure you want to delete this item? This action cannot be undone.
  </p>
  <button onclick="confirmDelete()">Delete</button>
  <button onclick="closeDialog()">Cancel</button>
</div>

<script>
let previousFocus;

function openDialog(dialog) {
  previousFocus = document.activeElement;
  dialog.style.display = 'block';

  // Trap focus in dialog
  trapFocus(dialog);

  // Focus first focusable element
  const focusable = dialog.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (focusable.length) focusable[0].focus();

  // Close on Escape
  dialog.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDialog(dialog);
  });
}

function closeDialog(dialog) {
  dialog.style.display = 'none';
  if (previousFocus) previousFocus.focus();
}

function trapFocus(element) {
  const focusable = element.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  element.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === first) {
          last.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === last) {
          first.focus();
          e.preventDefault();
        }
      }
    }
  });
}
</script>
```

**Keyboard:**
- Tab: Cycle through focusable elements in dialog only
- Escape: Close dialog
- Focus returns to trigger element on close

### 7. Dropdown Menu

```html
<div class="menu-container">
  <button aria-haspopup="true"
          aria-expanded="false"
          aria-controls="menu"
          id="menubutton">
    Actions
  </button>

  <ul role="menu"
      aria-labelledby="menubutton"
      id="menu"
      hidden>
    <li role="menuitem" tabindex="-1">Edit</li>
    <li role="menuitem" tabindex="-1">Delete</li>
    <li role="menuitem" tabindex="-1">Share</li>
  </ul>
</div>

<script>
const menuButton = document.getElementById('menubutton');
const menu = document.getElementById('menu');
const menuItems = Array.from(menu.querySelectorAll('[role="menuitem"]'));

menuButton.addEventListener('click', () => toggleMenu());

function toggleMenu() {
  const expanded = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', !expanded);
  menu.hidden = expanded;

  if (!expanded && menuItems.length) {
    menuItems[0].focus();
  }
}

menu.addEventListener('keydown', (e) => {
  const currentIndex = menuItems.indexOf(document.activeElement);
  let nextItem;

  if (e.key === 'ArrowDown') {
    nextItem = menuItems[(currentIndex + 1) % menuItems.length];
  } else if (e.key === 'ArrowUp') {
    nextItem = menuItems[(currentIndex - 1 + menuItems.length) % menuItems.length];
  } else if (e.key === 'Home') {
    nextItem = menuItems[0];
  } else if (e.key === 'End') {
    nextItem = menuItems[menuItems.length - 1];
  } else if (e.key === 'Escape') {
    toggleMenu();
    menuButton.focus();
    return;
  }

  if (nextItem) {
    e.preventDefault();
    nextItem.focus();
  }
});

menuItems.forEach(item => {
  item.addEventListener('click', () => {
    // Perform action
    toggleMenu();
    menuButton.focus();
  });
});
</script>
```

**Keyboard:**
- Enter/Space: Open menu
- Arrow Down/Up: Navigate items
- Home/End: Jump to first/last item
- Escape: Close menu
- Enter: Select item and close

### 8. Combobox (Autocomplete)

```html
<label for="country">Country</label>
<input type="text"
       id="country"
       role="combobox"
       aria-autocomplete="list"
       aria-expanded="false"
       aria-controls="country-listbox">

<ul id="country-listbox"
    role="listbox"
    hidden>
  <li role="option" id="option-us">United States</li>
  <li role="option" id="option-ca">Canada</li>
  <li role="option" id="option-mx">Mexico</li>
</ul>

<script>
const combobox = document.getElementById('country');
const listbox = document.getElementById('country-listbox');
const options = Array.from(listbox.querySelectorAll('[role="option"]'));

combobox.addEventListener('input', () => {
  const value = combobox.value.toLowerCase();
  let hasResults = false;

  options.forEach(option => {
    const matches = option.textContent.toLowerCase().includes(value);
    option.hidden = !matches;
    if (matches) hasResults = true;
  });

  listbox.hidden = !hasResults;
  combobox.setAttribute('aria-expanded', hasResults);
});

combobox.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown' && !listbox.hidden) {
    e.preventDefault();
    const firstVisible = options.find(opt => !opt.hidden);
    if (firstVisible) {
      firstVisible.focus();
      combobox.setAttribute('aria-activedescendant', firstVisible.id);
    }
  }
});
</script>
```

### 9. Alert and Status Messages

```html
<!-- Alert: Immediate announcement -->
<div role="alert">
  Error: Form submission failed. Please try again.
</div>

<!-- Status: Polite announcement -->
<div role="status" aria-live="polite">
  Saving... Saved successfully.
</div>

<!-- Timer: Off by default, can be updated -->
<div role="timer" aria-live="off" aria-atomic="true">
  Time remaining: 5:00
</div>
```

### 10. Tooltip

```html
<button aria-describedby="tooltip1">
  Help
  <span id="tooltip1" role="tooltip" hidden>
    Click for more information
  </span>
</button>

<script>
const button = document.querySelector('[aria-describedby]');
const tooltip = document.getElementById('tooltip1');

button.addEventListener('mouseenter', () => tooltip.hidden = false);
button.addEventListener('mouseleave', () => tooltip.hidden = true);
button.addEventListener('focus', () => tooltip.hidden = false);
button.addEventListener('blur', () => tooltip.hidden = true);
</script>
```

## ARIA Live Regions

### Politeness Levels

```html
<!-- Polite: Wait for pause in speech -->
<div aria-live="polite">
  Item added to cart
</div>

<!-- Assertive: Interrupt immediately -->
<div aria-live="assertive">
  Error: Connection lost
</div>

<!-- Off: No announcements (default) -->
<div aria-live="off">
  Decorative content
</div>
```

### Atomic Updates

```html
<!-- aria-atomic="true": Read entire region -->
<div aria-live="polite" aria-atomic="true">
  Page <span id="current-page">3</span> of 10
</div>
<!-- Announces: "Page 3 of 10" when page changes -->

<!-- aria-atomic="false": Read only what changed -->
<div aria-live="polite" aria-atomic="false">
  Page <span id="current-page">3</span> of 10
</div>
<!-- Announces: "3" when page changes -->
```

## Best Practices

### 1. Provide Accessible Names

Every interactive element needs a name:

```html
<!-- ✓ GOOD - Multiple ways to provide names -->
<button>Save</button>
<button aria-label="Save document">💾</button>
<button aria-labelledby="save-label">
  <span id="save-label">Save</span>
</button>
```

### 2. Use Semantic HTML First

```html
<!-- ✗ AVOID -->
<div role="button" tabindex="0">Click</div>

<!-- ✓ PREFER -->
<button>Click</button>
```

### 3. Manage Focus Properly

```javascript
// ✓ Move focus to important updates
function showError(message) {
  const alert = document.createElement('div');
  alert.setAttribute('role', 'alert');
  alert.textContent = message;
  alert.tabIndex = -1;
  document.body.appendChild(alert);
  alert.focus(); // Move focus to error
}
```

### 4. Test with Screen Readers

ARIA is complex. Always test with actual screen readers:
- VoiceOver (Mac)
- NVDA (Windows)
- JAWS (Windows)

## Resources

- **ARIA Authoring Practices Guide**: https://www.w3.org/WAI/ARIA/apg/
- **MDN ARIA**: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA
- **ARIA Spec**: https://www.w3.org/TR/wai-aria-1.2/
