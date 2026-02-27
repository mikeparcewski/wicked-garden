# WCAG 2.1 Level AA Complete Checklist

Comprehensive checklist for WCAG 2.1 Level AA compliance.

## Perceivable

### 1.1 Text Alternatives

**1.1.1 Non-text Content (Level A)**
- [ ] All images have appropriate `alt` attributes
- [ ] Decorative images use `alt=""`
- [ ] Complex images have detailed descriptions
- [ ] Form controls have associated labels
- [ ] CAPTCHA has text alternative

### 1.2 Time-based Media

**1.2.1 Audio-only and Video-only (Level A)**
- [ ] Audio-only has transcript
- [ ] Video-only has audio track or text description

**1.2.2 Captions (Level A)**
- [ ] Pre-recorded video has captions

**1.2.3 Audio Description or Media Alternative (Level A)**
- [ ] Pre-recorded video has audio description or transcript

**1.2.4 Captions (Live) (Level AA)**
- [ ] Live video has captions

**1.2.5 Audio Description (Level AA)**
- [ ] Pre-recorded video has audio description

### 1.3 Adaptable

**1.3.1 Info and Relationships (Level A)**
- [ ] Semantic HTML used (`<header>`, `<nav>`, `<main>`, etc.)
- [ ] Heading hierarchy correct (h1 → h2 → h3, no skips)
- [ ] Lists use `<ul>`, `<ol>`, `<dl>`
- [ ] Tables use `<th>` for headers
- [ ] Form labels associated with inputs

**1.3.2 Meaningful Sequence (Level A)**
- [ ] Reading order matches visual order
- [ ] Tab order is logical

**1.3.3 Sensory Characteristics (Level A)**
- [ ] Instructions don't rely solely on shape, size, location, or sound
- [ ] "Click the round button" → "Click the Submit button"

**1.3.4 Orientation (Level AA)**
- [ ] Content not restricted to single orientation (portrait/landscape)
- [ ] Unless specific orientation essential

**1.3.5 Identify Input Purpose (Level AA)**
- [ ] Autocomplete attributes used where appropriate
- [ ] `autocomplete="email"`, `autocomplete="name"`, etc.

### 1.4 Distinguishable

**1.4.1 Use of Color (Level A)**
- [ ] Color not only means of conveying information
- [ ] Links distinguishable from text (underline, bold, etc.)
- [ ] Error states have icon + color

**1.4.2 Audio Control (Level A)**
- [ ] Auto-playing audio can be paused/stopped/controlled

**1.4.3 Contrast (Minimum) (Level AA)**
- [ ] Normal text: 4.5:1 contrast ratio
- [ ] Large text (18pt+ or 14pt+ bold): 3:1 contrast ratio
- [ ] UI components: 3:1 contrast ratio

**1.4.4 Resize Text (Level AA)**
- [ ] Text can be resized to 200% without loss of functionality
- [ ] No horizontal scrolling at 200% zoom

**1.4.5 Images of Text (Level AA)**
- [ ] Actual text used instead of images of text
- [ ] Exceptions: logos, essential presentation

**1.4.10 Reflow (Level AA)**
- [ ] Content reflows at 320px width
- [ ] No two-dimensional scrolling
- [ ] Exceptions: complex data tables, maps

**1.4.11 Non-text Contrast (Level AA)**
- [ ] UI components: 3:1 contrast against adjacent colors
- [ ] Focus indicators: 3:1 contrast
- [ ] Graphical objects: 3:1 contrast

**1.4.12 Text Spacing (Level AA)**
- [ ] No loss of content when:
  - Line height 1.5x font size
  - Paragraph spacing 2x font size
  - Letter spacing 0.12x font size
  - Word spacing 0.16x font size

**1.4.13 Content on Hover or Focus (Level AA)**
- [ ] Hover/focus content dismissible (Escape)
- [ ] Hover/focus content hoverable (can move pointer to it)
- [ ] Hover/focus content persistent (doesn't disappear)

## Operable

### 2.1 Keyboard Accessible

**2.1.1 Keyboard (Level A)**
- [ ] All functionality available via keyboard
- [ ] No keyboard-only exceptions

**2.1.2 No Keyboard Trap (Level A)**
- [ ] Focus can move away from all components
- [ ] Standard navigation (Tab, arrow keys, Escape)

**2.1.4 Character Key Shortcuts (Level A)**
- [ ] Single key shortcuts can be turned off, remapped, or only active on focus

### 2.2 Enough Time

**2.2.1 Timing Adjustable (Level A)**
- [ ] Time limits can be turned off, adjusted, or extended
- [ ] Warning before timeout with option to extend

**2.2.2 Pause, Stop, Hide (Level A)**
- [ ] Moving, blinking, scrolling content can be paused
- [ ] Auto-updating content can be paused/hidden

### 2.3 Seizures and Physical Reactions

**2.3.1 Three Flashes or Below Threshold (Level A)**
- [ ] No content flashes more than 3 times per second
- [ ] Or below flash threshold

### 2.4 Navigable

**2.4.1 Bypass Blocks (Level A)**
- [ ] Skip to main content link
- [ ] Landmark regions defined
- [ ] Headings structure content

**2.4.2 Page Titled (Level A)**
- [ ] Every page has descriptive `<title>`

**2.4.3 Focus Order (Level A)**
- [ ] Focus order matches visual order
- [ ] Logical tab sequence

**2.4.4 Link Purpose (Level A)**
- [ ] Link text describes destination
- [ ] Avoid "click here", "read more" without context

**2.4.5 Multiple Ways (Level AA)**
- [ ] Multiple ways to find pages (search, sitemap, nav, etc.)
- [ ] Exception: process steps

**2.4.6 Headings and Labels (Level AA)**
- [ ] Headings describe topic/purpose
- [ ] Labels describe purpose

**2.4.7 Focus Visible (Level AA)**
- [ ] Focus indicator always visible
- [ ] Clear visual indication of focused element

### 2.5 Input Modalities

**2.5.1 Pointer Gestures (Level A)**
- [ ] Multi-point or path-based gestures have single-pointer alternative
- [ ] Exception: essential gestures (e.g., drawing)

**2.5.2 Pointer Cancellation (Level A)**
- [ ] Click actions on up event (not down)
- [ ] Or can be aborted/undone

**2.5.3 Label in Name (Level A)**
- [ ] Accessible name contains visible label text
- [ ] `aria-label` should include visible text

**2.5.4 Motion Actuation (Level A)**
- [ ] Motion-triggered actions have UI alternative
- [ ] Can disable motion triggering

## Understandable

### 3.1 Readable

**3.1.1 Language of Page (Level A)**
- [ ] `<html lang="en">` attribute set

**3.1.2 Language of Parts (Level AA)**
- [ ] Language changes marked with `lang` attribute
- [ ] `<span lang="es">Hola</span>`

### 3.2 Predictable

**3.2.1 On Focus (Level A)**
- [ ] Focus doesn't trigger unexpected context changes
- [ ] No automatic form submission on focus

**3.2.2 On Input (Level A)**
- [ ] Input doesn't trigger unexpected context changes
- [ ] Changes happen on button click, not automatic

**3.2.3 Consistent Navigation (Level AA)**
- [ ] Navigation menus in consistent order across pages

**3.2.4 Consistent Identification (Level AA)**
- [ ] Same functionality labeled consistently
- [ ] Search icon always means search

### 3.3 Input Assistance

**3.3.1 Error Identification (Level A)**
- [ ] Errors identified in text
- [ ] Location of error indicated
- [ ] Error description provided

**3.3.2 Labels or Instructions (Level A)**
- [ ] Form fields have labels
- [ ] Instructions provided where needed
- [ ] Required fields indicated

**3.3.3 Error Suggestion (Level AA)**
- [ ] Error messages suggest corrections
- [ ] "Invalid email" → "Email must include @"

**3.3.4 Error Prevention (Legal, Financial, Data) (Level AA)**
- [ ] Reversible or reviewable
- [ ] Data checked and user can correct
- [ ] Confirmation page for important actions

## Robust

### 4.1 Compatible

**4.1.1 Parsing (Level A)**
- [ ] No duplicate IDs
- [ ] Proper nesting of elements
- [ ] Complete start/end tags

**4.1.2 Name, Role, Value (Level A)**
- [ ] All UI components have accessible name
- [ ] Role communicated to assistive tech
- [ ] State/properties/values available
- [ ] Proper ARIA implementation

**4.1.3 Status Messages (Level AA)**
- [ ] Status messages announced without focus change
- [ ] Use `role="status"`, `role="alert"`, `aria-live`

## Testing Tools

- **axe DevTools**: Browser extension
- **WAVE**: WebAIM's browser extension
- **Lighthouse**: Chrome DevTools
- **NVDA**: Free screen reader (Windows)
- **VoiceOver**: Built-in screen reader (Mac)
- **Contrast checker**: WebAIM or browser tools
