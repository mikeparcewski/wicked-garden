# Keyboard Testing Guide: Patterns & Tools

Testing workflows, common violations with fixes, tools, and quick reference.

## Testing Workflow

### Basic Test (5 minutes)
1. Close your mouse/trackpad
2. Tab through the page
3. Try to complete primary user action
4. Can you do everything without a mouse?

### Comprehensive Test (20 minutes)
1. Test all checklist items from keyboard-testing-basics.md
2. Try each interactive element
3. Test modal/overlay interactions
4. Test form submission flow
5. Test error states and recovery

### Advanced Test (Browser DevTools)
```javascript
// Find all tabbable elements
document.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')

// Highlight focus order
let tabIndex = 0;
document.addEventListener('focus', (e) => {
  e.target.dataset.tabOrder = ++tabIndex;
  console.log(`Tab ${tabIndex}:`, e.target);
}, true);
```

## Common Violations and Fixes

### 1. Missing Tabindex on Custom Controls

```html
<!-- BAD: Not keyboard accessible -->
<div onclick="handleClick()">Click me</div>

<!-- GOOD: Keyboard accessible -->
<button onclick="handleClick()">Click me</button>

<!-- If div required, add role and tabindex -->
<div role="button" tabindex="0" onclick="handleClick()"
     onkeydown="if(event.key==='Enter'||event.key===' ')handleClick()">
  Click me
</div>
```

### 2. Invisible Focus Indicator

```css
/* BAD */
*:focus { outline: none; }

/* GOOD */
*:focus-visible {
  outline: 2px solid var(--focus-color);
  outline-offset: 2px;
}
```

### 3. Keyboard Trap in Modal

```javascript
// BAD - Focus escapes modal
<div class="modal">...</div>

// GOOD - Focus trapped in modal
function trapFocus(modal) {
  const focusable = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  modal.addEventListener('keydown', (e) => {
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

  first.focus();
}
```

### 4. Incorrect Tab Order

```html
<!-- BAD - Positive tabindex -->
<button tabindex="3">Third</button>
<button tabindex="1">First</button>
<button tabindex="2">Second</button>

<!-- GOOD - Natural DOM order -->
<button>First</button>
<button>Second</button>
<button>Third</button>

<!-- ACCEPTABLE - Only 0 and -1 -->
<div tabindex="0">Focusable</div>
<div tabindex="-1">Programmatically focusable</div>
```

## Testing Tools

### Browser Extensions
- **Tab Order Viewer**: Visualize tab sequence
- **Accessibility Insights**: Automated and guided tests
- **axe DevTools**: Keyboard accessibility checks

### Manual Testing
- Disconnect mouse/trackpad
- Use browser without extensions
- Test on actual keyboard (not just Tab)

### Automated Checks
```bash
# axe-core includes keyboard checks
npx @axe-core/cli https://example.com

# pa11y
npx pa11y https://example.com
```

## Quick Reference Card

```
Action                  | Keys
------------------------|------------------------
Navigate forward        | Tab
Navigate backward       | Shift+Tab
Activate button/link    | Enter (or Space for buttons)
Toggle checkbox         | Space
Select radio button     | Arrow keys
Open dropdown           | Space or Enter
Navigate menu           | Arrow keys
Close modal/menu        | Escape
Submit form             | Enter (in text input)
Scroll page             | Space, Arrow keys, Page Up/Down
```

## Success Criteria

**Pass if:**
- All interactive elements reachable via Tab
- Focus always visible
- No keyboard traps
- All functionality works via keyboard
- Tab order is logical
- Enter/Space activate elements appropriately

**Fail if:**
- Any interactive element unreachable
- Focus invisible at any point
- User gets stuck anywhere
- Primary action requires mouse
- Tab order confusing or broken
