# ARIA Patterns - Interactive Widgets

Tabs, modal dialogs, and dropdown menus.

## Complex Widget Patterns

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
