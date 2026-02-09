---
name: accessibility
description: |
  WCAG 2.1 Level AA accessibility audit and remediation guidance.
  Keyboard navigation, screen readers, semantic HTML, ARIA patterns.

  Use when: "accessibility", "a11y", "WCAG", "keyboard", "screen reader",
  "semantic HTML", "ARIA", "inclusive design", "disability"
---

# Accessibility Skill

WCAG 2.1 Level AA compliance auditing and inclusive design guidance.

## Core Principle

**Accessibility is not optional.** It's legal compliance, user respect, and better code.

## WCAG 2.1 Four Principles: POUR

### 1. Perceivable
Information must be presentable to users in ways they can perceive.
- Text alternatives for images
- Color contrast 4.5:1 (normal), 3:1 (large)
- No info by color alone

### 2. Operable
Interface components must be operable.
- All functionality via keyboard
- No keyboard traps
- Visible focus indicators

### 3. Understandable
Information and operation must be understandable.
- Form labels associated
- Error messages clear
- Consistent navigation

### 4. Robust
Content must work with assistive technologies.
- Valid HTML (no duplicate IDs)
- Proper ARIA usage
- Status messages announced

**Full WCAG checklists**: See [refs/wcag-checklist.md](refs/wcag-checklist.md)

## Quick Audit Process

### 1. Automated Scan
```bash
# If wicked-browse available
wicked-browse a11y-audit {url_or_file}

# Otherwise use: axe DevTools, Lighthouse, WAVE, pa11y
```

### 2. Keyboard Test (5 minutes)
- Tab through entire page
- Can reach all interactive elements?
- Focus always visible?
- Tab order logical?
- Can escape modals/menus?

**Full keyboard testing guide**: See [refs/keyboard-testing.md](refs/keyboard-testing.md)

### 3. Screen Reader Spot Check
- Turn on VoiceOver (Mac) or NVDA (Windows)
- Are images described?
- Are buttons/links clear?
- Are form labels read?

**Full screen reader guide**: See [refs/screen-reader-testing.md](refs/screen-reader-testing.md)

### 4. Code Review
```bash
# Find potential issues
wicked-search "<div.*onclick" --type html  # Non-semantic buttons
wicked-search "<img(?!.*alt)" --type html  # Missing alt
wicked-search "aria-" --type html          # ARIA usage
```

## Common Quick Fixes

```html
<!-- ✗ Missing alt -->
<img src="profile.jpg">
<!-- ✓ Fixed -->
<img src="profile.jpg" alt="Profile of Jane Doe">

<!-- ✗ Non-semantic button -->
<div onclick="submit()">Submit</div>
<!-- ✓ Fixed -->
<button onclick="submit()">Submit</button>

<!-- ✗ Form without label -->
<input type="text" placeholder="Email">
<!-- ✓ Fixed -->
<label for="email">Email</label>
<input type="text" id="email">

<!-- ✗ Low contrast -->
<p style="color: #999; background: #fff;">Text</p>  /* 2.5:1 */
<!-- ✓ Fixed -->
<p style="color: #666; background: #fff;">Text</p>  /* 4.7:1 */
```

**More examples**: See [refs/common-violations.md](refs/common-violations.md)

## Output Format

```markdown
## A11y Audit

**WCAG**: {✓ Pass | ⚠ Issues | ✗ Fail}
- Perceivable: {✓⚠✗}
- Operable: {✓⚠✗}
- Understandable: {✓⚠✗}
- Robust: {✓⚠✗}

### Critical (Level A)
- Issue: {description}
  - WCAG: {criterion}
  - Fix: {specific code}

### Major (Level AA)
- Issue: {description}
  - WCAG: {criterion}
  - Fix: {recommendation}

### Recommendations
1. {Priority fixes}
```

**Full report template**: See [refs/audit-report.md](refs/audit-report.md)

## Integration

**Tools:**
```bash
# Color contrast check
python3 "${CLAUDE_PLUGIN_ROOT}/wicked-product/scripts/contrast-check.py" "#666" "#fff"

# Track issues
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-kanban/scripts/kanban.py" create-task \
  "A11y" "A11y: {issue}" "todo" --priority P0 --tags "accessibility,wcag"
```

**Collaboration:**
- UX Designer: Ensure accessible patterns in flows
- UI Reviewer: Validate contrast and focus states
- QE: Include keyboard/screen reader testing

## External Integration Discovery

Accessibility auditing can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **A11y testing** | `axe`, `a11y`, `accessibility` | Automated WCAG scanning |
| **Browser testing** | `playwright`, `puppeteer` | Screenshots, DOM snapshots |
| **Performance** | `lighthouse` | Combined a11y + performance audit |

Run `ListMcpResourcesTool` to discover available integrations. Fall back to local contrast-check.py when none available.

## Resources

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Patterns**: https://www.w3.org/WAI/ARIA/apg/
- **WebAIM**: https://webaim.org/articles/
- **Inclusive Components**: https://inclusive-components.design/

**Detailed guides in refs/:**
- [wcag-checklist.md](refs/wcag-checklist.md) - Complete WCAG checklists
- [keyboard-testing.md](refs/keyboard-testing.md) - Keyboard navigation guide
- [screen-reader-testing.md](refs/screen-reader-testing.md) - Screen reader testing
- [aria-patterns.md](refs/aria-patterns.md) - ARIA implementation guide
- [common-violations.md](refs/common-violations.md) - Fix examples
- [audit-report.md](refs/audit-report.md) - Full report template

## When to Audit

- Before major releases
- New UI components
- Form implementations
- Modal/dialog work
- Post-build phase (crew integration)
- User-facing features

## Legal Context

**Why it matters:**
- ADA compliance (US)
- Section 508 (government)
- EAA (Europe)
- 15-20% of users need accessibility
- SEO impact (screen readers = search bots)
