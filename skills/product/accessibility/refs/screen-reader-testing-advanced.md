# Screen Reader Testing: Advanced Tests & Workflow

ARIA testing, navigation, tables, dynamic content, focus management, common issues, and testing workflow.

## 5. ARIA Test

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

## 6. Navigation Test

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

## 7. Table Test

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

## 8. Dynamic Content Test

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

## 9. Focus Management Test

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
