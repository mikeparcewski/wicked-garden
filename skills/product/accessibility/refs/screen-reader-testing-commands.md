# Screen Reader Testing: Commands & Setup

Comprehensive guide to screen reader commands and setup for WCAG 2.1 compliance.

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
