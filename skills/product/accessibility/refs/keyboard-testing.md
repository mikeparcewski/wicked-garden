# Keyboard Testing Guide

Complete keyboard navigation testing for WCAG 2.1 compliance.

## Core Keyboard Requirements

All interactive functionality must be operable through keyboard alone (WCAG 2.1.1).

### Essential Keys

- **Tab**: Move forward through interactive elements
- **Shift+Tab**: Move backward through interactive elements
- **Enter**: Activate buttons, links, form submissions
- **Space**: Toggle checkboxes, activate buttons, scroll page
- **Arrow Keys**: Navigate within menus, radio groups, sliders, tabs
- **Escape**: Close modals, cancel operations, dismiss popovers
- **Home/End**: Jump to first/last item in lists or text inputs

## Comprehensive Testing Checklist

### 1. Tab Order Test

**Goal**: Verify logical tab sequence and no missing interactive elements.

```
□ Tab through entire page from top to bottom
□ Tab order matches visual layout (left-to-right, top-to-bottom)
□ All interactive elements are reachable
□ No unexpected tab stops on non-interactive elements
□ Skip links (if present) appear first
□ Tab order within complex components is logical
□ Form fields follow a natural sequence
```

### 2. Focus Visibility Test

**Goal**: Ensure focus is always clearly visible (WCAG 2.4.7).

```
□ Focus indicator visible on ALL interactive elements
□ Focus ring contrast meets 3:1 minimum
□ Focus indicator not obscured by other elements
□ Focus indicator clearly distinguishable from hover state
□ Focus visible in both light and dark modes
□ Custom focus styles meet visibility standards
□ Focus visible on all form controls
□ Focus visible on custom components
```

**Common Issues:**
```css
/* ✗ BAD - Removes focus indicator */
button:focus { outline: none; }

/* ✓ GOOD - Custom accessible focus */
button:focus-visible {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}
```

### 3. Keyboard Trap Test

**Goal**: Ensure users can always move focus away (WCAG 2.1.2).

```
□ Can exit all modals with Escape
□ Can tab out of custom widgets
□ No infinite tab loops
□ Can exit autocomplete/dropdown menus
□ Can leave embedded iframes
□ Modal focus management returns to trigger element
□ No focus lost into hidden elements
```

### 4. Interactive Element Test

**Goal**: All interactive elements work with keyboard.

#### Buttons
```
□ Activate with Enter
□ Activate with Space
□ Both <button> and role="button" work
```

#### Links
```
□ Activate with Enter
□ Space scrolls page (doesn't activate)
□ Fragment links (#) work correctly
```

#### Form Controls
```
□ Text inputs: Type, navigate with arrows
□ Checkboxes: Toggle with Space
□ Radio buttons: Select with Arrow keys
□ Select dropdowns: Open with Space/Enter, navigate with Arrows
□ Textareas: Enter creates new line (doesn't submit form)
```

#### Custom Components
```
□ Tabs: Arrow keys navigate, Enter/Space activate
□ Accordions: Enter/Space toggle, Arrow keys navigate
□ Carousels: Arrow keys navigate slides
□ Sliders: Arrow keys adjust value
□ Menus: Arrow keys navigate, Enter selects, Escape closes
```

### 5. Modal and Dialog Test

**Goal**: Proper focus management in overlay interfaces.

```
□ Focus moves to modal when opened
□ Tab cycles within modal only (focus trap)
□ First focusable element receives focus on open
□ Escape closes modal
□ Focus returns to trigger element on close
□ Background content is inert (can't tab to it)
□ Modal can be operated entirely by keyboard
```

**Example Implementation:**
```javascript
// Focus trap in modal
modal.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();

  if (e.key === 'Tab') {
    const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      last.focus();
      e.preventDefault();
    } else if (!e.shiftKey && document.activeElement === last) {
      first.focus();
      e.preventDefault();
    }
  }
});
```

### 6. Dropdown and Menu Test

**Goal**: Keyboard-accessible menu navigation.

```
□ Open with Enter or Space
□ Arrow Down: Move to next item
□ Arrow Up: Move to previous item
□ Home: Jump to first item
□ End: Jump to last item
□ Type to search/filter items
□ Enter: Select item and close
□ Escape: Close without selecting
□ Tab: Close and move to next element
```

### 7. Skip Links Test

**Goal**: Efficient navigation for keyboard users.

```
□ "Skip to main content" link is first tab stop
□ Skip link becomes visible on focus
□ Skip link actually moves focus to main content
□ Additional skip links for repetitive navigation
```

**Example:**
```html
<a href="#main-content" class="skip-link">Skip to main content</a>

<style>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: #000;
  color: #fff;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
</style>
```

### 8. Form Validation Test

**Goal**: Keyboard users can identify and fix errors.

```
□ Error messages appear without requiring mouse
□ Focus moves to first error on submit
□ Inline validation doesn't break keyboard flow
□ Error messages are keyboard-accessible
□ Success messages are announced
```

### 9. Dynamic Content Test

**Goal**: Keyboard users aren't lost when content changes.

```
□ Focus maintained when content updates
□ Loading states don't trap focus
□ Infinite scroll accessible via keyboard
□ Lazy-loaded content is reachable
□ AJAX updates don't break tab order
```

## Testing Workflow

### Basic Test (5 minutes)
1. Close your mouse/trackpad
2. Tab through the page
3. Try to complete primary user action
4. Can you do everything without a mouse?

### Comprehensive Test (20 minutes)
1. Test all checklist items above
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
<!-- ✗ Not keyboard accessible -->
<div onclick="handleClick()">Click me</div>

<!-- ✓ Keyboard accessible -->
<button onclick="handleClick()">Click me</button>

<!-- ✓ If div required, add role and tabindex -->
<div role="button" tabindex="0" onclick="handleClick()"
     onkeydown="if(event.key==='Enter'||event.key===' ')handleClick()">
  Click me
</div>
```

### 2. Invisible Focus Indicator

```css
/* ✗ BAD */
*:focus { outline: none; }

/* ✓ GOOD */
*:focus-visible {
  outline: 2px solid var(--focus-color);
  outline-offset: 2px;
}
```

### 3. Keyboard Trap in Modal

```javascript
// ✗ BAD - Focus escapes modal
<div class="modal">...</div>

// ✓ GOOD - Focus trapped in modal
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
<!-- ✗ BAD - Positive tabindex -->
<button tabindex="3">Third</button>
<button tabindex="1">First</button>
<button tabindex="2">Second</button>

<!-- ✓ GOOD - Natural DOM order -->
<button>First</button>
<button>Second</button>
<button>Third</button>

<!-- ✓ ACCEPTABLE - Only 0 and -1 -->
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
