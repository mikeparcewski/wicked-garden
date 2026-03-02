# ARIA Patterns - Dynamic Content and Best Practices

Combobox, alerts, tooltips, live regions, and best practices.

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
<!-- GOOD - Multiple ways to provide names -->
<button>Save</button>
<button aria-label="Save document">&#128190;</button>
<button aria-labelledby="save-label">
  <span id="save-label">Save</span>
</button>
```

### 2. Use Semantic HTML First

```html
<!-- AVOID -->
<div role="button" tabindex="0">Click</div>

<!-- PREFER -->
<button>Click</button>
```

### 3. Manage Focus Properly

```javascript
// Move focus to important updates
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
