# Keyboard Testing Guide: Basics

Core keyboard navigation testing for WCAG 2.1 compliance.

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
[] Tab through entire page from top to bottom
[] Tab order matches visual layout (left-to-right, top-to-bottom)
[] All interactive elements are reachable
[] No unexpected tab stops on non-interactive elements
[] Skip links (if present) appear first
[] Tab order within complex components is logical
[] Form fields follow a natural sequence
```

### 2. Focus Visibility Test

**Goal**: Ensure focus is always clearly visible (WCAG 2.4.7).

```
[] Focus indicator visible on ALL interactive elements
[] Focus ring contrast meets 3:1 minimum
[] Focus indicator not obscured by other elements
[] Focus indicator clearly distinguishable from hover state
[] Focus visible in both light and dark modes
[] Custom focus styles meet visibility standards
[] Focus visible on all form controls
[] Focus visible on custom components
```

**Common Issues:**
```css
/* BAD - Removes focus indicator */
button:focus { outline: none; }

/* GOOD - Custom accessible focus */
button:focus-visible {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}
```

### 3. Keyboard Trap Test

**Goal**: Ensure users can always move focus away (WCAG 2.1.2).

```
[] Can exit all modals with Escape
[] Can tab out of custom widgets
[] No infinite tab loops
[] Can exit autocomplete/dropdown menus
[] Can leave embedded iframes
[] Modal focus management returns to trigger element
[] No focus lost into hidden elements
```

### 4. Interactive Element Test

**Goal**: All interactive elements work with keyboard.

#### Buttons
```
[] Activate with Enter
[] Activate with Space
[] Both <button> and role="button" work
```

#### Links
```
[] Activate with Enter
[] Space scrolls page (doesn't activate)
[] Fragment links (#) work correctly
```

#### Form Controls
```
[] Text inputs: Type, navigate with arrows
[] Checkboxes: Toggle with Space
[] Radio buttons: Select with Arrow keys
[] Select dropdowns: Open with Space/Enter, navigate with Arrows
[] Textareas: Enter creates new line (doesn't submit form)
```

#### Custom Components
```
[] Tabs: Arrow keys navigate, Enter/Space activate
[] Accordions: Enter/Space toggle, Arrow keys navigate
[] Carousels: Arrow keys navigate slides
[] Sliders: Arrow keys adjust value
[] Menus: Arrow keys navigate, Enter selects, Escape closes
```

### 5. Modal and Dialog Test

**Goal**: Proper focus management in overlay interfaces.

```
[] Focus moves to modal when opened
[] Tab cycles within modal only (focus trap)
[] First focusable element receives focus on open
[] Escape closes modal
[] Focus returns to trigger element on close
[] Background content is inert (can't tab to it)
[] Modal can be operated entirely by keyboard
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
[] Open with Enter or Space
[] Arrow Down: Move to next item
[] Arrow Up: Move to previous item
[] Home: Jump to first item
[] End: Jump to last item
[] Type to search/filter items
[] Enter: Select item and close
[] Escape: Close without selecting
[] Tab: Close and move to next element
```

### 7. Skip Links Test

**Goal**: Efficient navigation for keyboard users.

```
[] "Skip to main content" link is first tab stop
[] Skip link becomes visible on focus
[] Skip link actually moves focus to main content
[] Additional skip links for repetitive navigation
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
[] Error messages appear without requiring mouse
[] Focus moves to first error on submit
[] Inline validation doesn't break keyboard flow
[] Error messages are keyboard-accessible
[] Success messages are announced
```

### 9. Dynamic Content Test

**Goal**: Keyboard users aren't lost when content changes.

```
[] Focus maintained when content updates
[] Loading states don't trap focus
[] Infinite scroll accessible via keyboard
[] Lazy-loaded content is reachable
[] AJAX updates don't break tab order
```
