# Screen Reader Testing Guide

Comprehensive guide to testing with screen readers for WCAG 2.1 compliance.

## Why Screen Reader Testing Matters

- **15% of web users** rely on assistive technology
- **Legal requirement** for ADA/Section 508 compliance
- **Automated tools miss 70%** of accessibility issues
- **Screen readers = SEO bots** (similar parsing logic)

## Primary Screen Readers

### macOS: VoiceOver (Built-in)

**Turn On/Off:**
- `Cmd + F5` (or Touch ID 3x)

**Essential Commands:**
```
VO = Control + Option

Navigate:
  VO + Right Arrow    Next element
  VO + Left Arrow     Previous element
  VO + Shift + ↓      Enter element (like <div>)
  VO + Shift + ↑      Exit element

Interact:
  VO + Space          Activate button/link
  VO + Shift + Space  Open context menu

Read:
  VO + A              Read page from current position
  Control             Stop reading

Navigate by element type:
  VO + Cmd + H        Next heading
  VO + Cmd + L        Next link
  VO + Cmd + J        Next form control
  VO + Cmd + G        Next graphic/image
  VO + Cmd + X        Next list
  VO + Cmd + T        Next table
```

**Rotor (element list):**
- `VO + U` - Open rotor
- Arrow keys to navigate categories (headings, links, forms, etc.)
- Type to search
- Enter to jump to element

### Windows: NVDA (Free)

**Download:** https://www.nvaccess.org/download/

**Essential Commands:**
```
NVDA = Insert (or Caps Lock if configured)

Navigate:
  Down Arrow          Next line
  Up Arrow            Previous line
  Tab                 Next focusable element
  H                   Next heading
  1-6                 Next heading level 1-6
  K                   Next link
  F                   Next form field
  B                   Next button
  G                   Next graphic

Interact:
  Enter               Activate link/button
  Space               Toggle checkbox, activate button
  NVDA + Space        Toggle focus/browse mode

Read:
  NVDA + Down Arrow   Read current line
  NVDA + ↓ (repeat)   Read from here
  Control             Stop reading

Lists:
  NVDA + F7           Elements list (headings, links, etc.)
```

### Windows: JAWS (Commercial)

**Most used enterprise screen reader.** Commands similar to NVDA.

### Mobile: iOS VoiceOver

```
Settings > Accessibility > VoiceOver

Triple-click home button (or side button) to toggle

Single tap           Speak element
Double tap           Activate
Swipe right          Next element
Swipe left           Previous element
Two-finger swipe up  Read from top
Rotor                Rotate two fingers to change navigation mode
```

### Mobile: Android TalkBack

```
Settings > Accessibility > TalkBack

Swipe right          Next element
Swipe left           Previous element
Double tap           Activate
Swipe up then right  Read from top
```

## Essential Testing Checklist

### 1. Semantic Structure Test

**Goal**: Proper HTML structure for screen reader navigation.

```
□ Page has single <h1>
□ Headings in correct order (h1 → h2 → h3, no skips)
□ Landmarks present: <header>, <nav>, <main>, <footer>
□ Lists use <ul>/<ol>, not just <br> tags
□ Tables use proper <table> structure
□ Forms use <form> and <fieldset>
```

**Test:**
- Use heading navigation (VO+Cmd+H or H key)
- Use landmark navigation (VO+U in VoiceOver, D in NVDA)
- Can you quickly jump to main content?

### 2. Alternative Text Test

**Goal**: All non-text content has text alternative (WCAG 1.1.1).

```
□ Images have alt text
□ Decorative images have alt=""
□ Complex images have detailed descriptions
□ Icons have accessible labels
□ SVGs have <title> or aria-label
□ Background images with content have ARIA labels
```

**Test:**
- Navigate to each image (VO+Cmd+G or G key)
- Is the purpose clearly announced?
- Are decorative images skipped?

**Examples:**
```html
<!-- ✓ Informative image -->
<img src="chart.png" alt="Sales increased 40% in Q4">

<!-- ✓ Decorative image -->
<img src="divider.png" alt="">

<!-- ✓ Complex image -->
<img src="diagram.png" alt="System architecture"
     aria-describedby="diagram-desc">
<div id="diagram-desc">
  The system consists of three layers:
  presentation (React), API (Node.js), and database (PostgreSQL).
</div>

<!-- ✓ Icon button -->
<button aria-label="Close">
  <svg>...</svg>
</button>
```

### 3. Link and Button Test

**Goal**: Link/button purpose clear from announcement (WCAG 2.4.4).

```
□ Link text describes destination
□ No "click here" or "read more" alone
□ Button text describes action
□ Icon-only controls have labels
□ Links and buttons distinguishable
```

**Test:**
- Use link navigation (VO+Cmd+L or K key)
- Listen to each link out of context
- Is it clear where the link goes?

**Examples:**
```html
<!-- ✗ BAD - Unclear out of context -->
<a href="/report.pdf">Click here</a>

<!-- ✓ GOOD - Clear purpose -->
<a href="/report.pdf">Download Q4 Sales Report (PDF, 2MB)</a>

<!-- ✗ BAD - Generic -->
<button>Submit</button>

<!-- ✓ GOOD - Specific -->
<button>Submit Payment</button>

<!-- ✓ Icon with label -->
<button aria-label="Delete item">
  <TrashIcon />
</button>
```

### 4. Form Test

**Goal**: All form controls have accessible labels (WCAG 1.3.1, 3.3.2).

```
□ All inputs have associated <label>
□ Fieldsets for related groups (radio buttons)
□ Required fields indicated accessibly
□ Error messages linked to fields
□ Placeholder is not the only label
□ Instructions announced before input
```

**Test:**
- Navigate to each form field (VO+Cmd+J or F key)
- Is the label and purpose announced?
- Are required fields clearly indicated?
- Are error messages read when field receives focus?

**Examples:**
```html
<!-- ✓ Proper label association -->
<label for="email">Email address (required)</label>
<input type="email" id="email" required aria-required="true">

<!-- ✓ Fieldset for radio group -->
<fieldset>
  <legend>Shipping method</legend>
  <label><input type="radio" name="ship" value="standard"> Standard</label>
  <label><input type="radio" name="ship" value="express"> Express</label>
</fieldset>

<!-- ✓ Error message -->
<label for="username">Username</label>
<input type="text" id="username" aria-describedby="username-error"
       aria-invalid="true">
<div id="username-error" role="alert">
  Username must be at least 3 characters
</div>
```

### 5. ARIA Test

**Goal**: ARIA attributes enhance accessibility, not break it.

```
□ ARIA roles appropriate (button, dialog, alert, etc.)
□ aria-label/aria-labelledby on unlabeled controls
□ aria-describedby for additional context
□ aria-live for dynamic updates
□ aria-expanded for collapsible content
□ aria-hidden used correctly (not on focusable elements)
□ Custom controls have proper ARIA states
```

**Test:**
- Navigate to custom components
- Are roles and states announced?
- Do state changes get announced?

**Examples:**
```html
<!-- ✓ Custom button -->
<div role="button" tabindex="0" aria-pressed="false">
  Toggle feature
</div>

<!-- ✓ Live region for updates -->
<div aria-live="polite" aria-atomic="true">
  3 items in cart
</div>

<!-- ✓ Accordion -->
<button aria-expanded="false" aria-controls="panel1">
  Section 1
</button>
<div id="panel1" hidden>
  Content...
</div>

<!-- ✓ Modal -->
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Confirm Action</h2>
  ...
</div>
```

### 6. Navigation Test

**Goal**: Efficient page navigation for screen reader users.

```
□ Skip links present ("Skip to main content")
□ Landmarks define page regions
□ Heading structure enables outline navigation
□ Table of contents for long pages
□ Breadcrumbs properly marked up
```

**Test:**
- Can you quickly jump to main content?
- Use landmark navigation (VO+U, landmarks)
- Use heading navigation to browse page structure

### 7. Table Test

**Goal**: Data tables are navigable and understandable.

```
□ Data tables use <table>, not divs with CSS grid
□ Headers use <th> with scope attribute
□ Complex tables use id/headers association
□ Table has <caption> or aria-label
```

**Test:**
- Navigate into table (VO+Shift+Down)
- Are column/row headers announced with each cell?

**Examples:**
```html
<!-- ✓ Simple table -->
<table>
  <caption>Sales by Region</caption>
  <thead>
    <tr>
      <th scope="col">Region</th>
      <th scope="col">Q1</th>
      <th scope="col">Q2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">North</th>
      <td>$100K</td>
      <td>$120K</td>
    </tr>
  </tbody>
</table>
```

### 8. Dynamic Content Test

**Goal**: Content changes announced to screen reader users.

```
□ Loading states announced
□ Success/error messages use role="alert"
□ Form validation errors announced
□ Content updates use aria-live
□ Infinite scroll announces new content
□ Client-side routing announces page changes
```

**Test:**
- Trigger dynamic updates
- Are changes announced without needing to navigate?

**Examples:**
```html
<!-- ✓ Alert -->
<div role="alert">
  Form submitted successfully
</div>

<!-- ✓ Status update -->
<div role="status" aria-live="polite">
  Saving... Saved.
</div>

<!-- ✓ Loading indicator -->
<div role="status" aria-live="polite" aria-atomic="true">
  <span aria-live="assertive" aria-busy="true">Loading data...</span>
</div>
```

### 9. Focus Management Test

**Goal**: Focus behavior logical for screen reader users.

```
□ Focus moves to modal when opened
□ Focus returns to trigger when modal closed
□ Tab navigation within modal only
□ No focus on hidden elements
□ Focus visible (screen reader and sighted keyboard users)
```

**Test:**
- Open modal - does focus move to modal?
- Close modal - does focus return to trigger button?
- Tab within modal - does focus stay trapped?

## Common Screen Reader Issues

### 1. Missing Labels

```html
<!-- ✗ BAD -->
<input type="text" placeholder="Search">

<!-- ✓ GOOD -->
<label for="search">Search</label>
<input type="text" id="search" placeholder="e.g., product name">
```

### 2. Inaccessible Icons

```html
<!-- ✗ BAD -->
<button><i class="icon-delete"></i></button>

<!-- ✓ GOOD -->
<button aria-label="Delete item">
  <i class="icon-delete" aria-hidden="true"></i>
</button>
```

### 3. Meaningless Link Text

```html
<!-- ✗ BAD -->
<a href="/article1">Read more</a>
<a href="/article2">Read more</a>

<!-- ✓ GOOD -->
<a href="/article1">Read more about quarterly results</a>
<!-- OR -->
<h3 id="article1-title">Quarterly Results</h3>
<a href="/article1" aria-labelledby="article1-title read-more">
  <span id="read-more">Read more</span>
</a>
```

### 4. Unlabeled Regions

```html
<!-- ✗ BAD -->
<div class="sidebar">...</div>

<!-- ✓ GOOD -->
<aside aria-label="Related articles">...</aside>
<!-- OR -->
<nav aria-labelledby="sidebar-title">
  <h2 id="sidebar-title">Related Articles</h2>
  ...
</nav>
```

### 5. Missing Live Regions

```javascript
// ✗ BAD - Update not announced
document.getElementById('status').textContent = 'Saved';

// ✓ GOOD - Update announced
<div id="status" role="status" aria-live="polite"></div>
document.getElementById('status').textContent = 'Saved';
```

## Testing Workflow

### Quick Test (10 minutes)
1. Turn on screen reader
2. Close your eyes or turn off monitor
3. Navigate through the page
4. Can you complete the primary action?

### Comprehensive Test (30 minutes)
1. Test all checklist items above
2. Navigate by headings
3. Navigate by landmarks
4. Navigate by links
5. Navigate by form fields
6. Test all interactive components
7. Test form submission and error handling

### User Flows to Test
- Homepage to product to checkout
- Login flow
- Search and filter results
- Complete a form
- Read an article
- Error recovery

## Reporting Issues

When documenting screen reader issues:

```markdown
**Issue**: Unlabeled search button

**Screen Reader**: VoiceOver + Safari
**Announcement**: "Button" (should be "Search button")
**Location**: Header navigation
**Code**: `<button><SearchIcon /></button>`
**Fix**: Add aria-label
  ```html
  <button aria-label="Search">
    <SearchIcon aria-hidden="true" />
  </button>
  ```
**Priority**: High (primary navigation control)
```

## Success Criteria

**Pass if:**
- All content accessible via screen reader
- Purpose of all elements clear from announcement
- User can complete all tasks without seeing screen
- No confusion or dead ends
- Dynamic updates announced appropriately

**Fail if:**
- Any interactive element unlabeled
- User gets lost or confused
- Primary action not achievable
- Content missing from screen reader
- Unclear or misleading announcements

## Resources

- **WebAIM Screen Reader Survey**: Usage stats and preferences
- **Deque University**: Detailed screen reader guides
- **A11ycasts**: Video tutorials on screen reader usage
- **Screen Reader User Survey**: https://webaim.org/projects/screenreadersurvey9/
