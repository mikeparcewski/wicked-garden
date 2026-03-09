# Accessibility Audit Report: Findings Template

Template for executive summary, methodology, and detailed findings sections of an accessibility audit.

## Executive Summary

**Project**: [Project name]
**Audit Date**: [YYYY-MM-DD]
**Auditor**: [Name/Team]
**WCAG Target**: [Level AA | Level AAA]
**Pages Tested**: [List or count]

### Overall Result

**Compliance Status**: [✓ Compliant | ⚠ Partial Compliance | ✗ Non-Compliant]

**WCAG 2.1 Principles:**
- Perceivable: [✓ | ⚠ | ✗]
- Operable: [✓ | ⚠ | ✗]
- Understandable: [✓ | ⚠ | ✗]
- Robust: [✓ | ⚠ | ✗]

### Summary Metrics

| Severity | Count | % Fixed |
|----------|-------|---------|
| Critical (Level A) | X | 0% |
| Major (Level AA) | X | 0% |
| Minor (AAA/Best Practice) | X | 0% |
| **Total** | **X** | **0%** |

### Key Findings

**Top 3 Issues:**
1. [Most impactful issue]
2. [Second most impactful]
3. [Third most impactful]

**Positive Observations:**
- [Good practice found]
- [Another good practice]

---

## Methodology

### Testing Approach

**Automated Tools:**
- axe DevTools [version]
- Lighthouse [version]
- WAVE
- Pa11y

**Manual Testing:**
- Keyboard navigation (Chrome, Safari)
- Screen readers:
  - VoiceOver + Safari (macOS)
  - NVDA + Firefox (Windows)
- Color contrast analyzer
- Code review

**User Flows Tested:**
1. [Primary user flow]
2. [Secondary flow]
3. [Form submission flow]

**Browsers Tested:**
- Chrome [version]
- Firefox [version]
- Safari [version]
- Edge [version]

**Devices:**
- Desktop (1920x1080)
- Tablet (iPad)
- Mobile (iPhone)

---

## Detailed Findings

### Critical Issues (Level A)

Blocking issues that prevent access for users with disabilities.

#### 1. [Issue Title]

**WCAG Criterion**: [e.g., 1.1.1 Non-text Content (Level A)]

**Impact**: [High | Medium | Low]
**Affected Users**: [Screen reader users | Keyboard users | Low vision users | etc.]
**Frequency**: [How often this occurs - e.g., "All pages" | "Form pages only"]

**Description:**
[Detailed description of the issue and why it's a problem]

**Location:**
```
File: src/components/Header.tsx
Line: 45-52
URL: /dashboard
Element: <img src="logo.png">
```

**Current State:**
```html
<img src="logo.png">
```

**Expected State (WCAG):**
```html
<img src="logo.png" alt="Company Name - Home">
```

**How to Reproduce:**
1. Navigate to /dashboard
2. Turn on screen reader
3. Tab to logo image
4. Image announced as "logo.png" instead of company name

**Recommendation:**
Add descriptive alt text to the logo image. The alt text should identify the company and indicate that it's a link to the homepage.

**Code Fix:**
```html
<a href="/">
  <img src="logo.png" alt="Company Name - Home">
</a>
```

**Resources:**
- [WebAIM: Alternative Text](https://webaim.org/techniques/alttext/)
- [WCAG 1.1.1 Understanding Doc](https://www.w3.org/WAI/WCAG21/Understanding/non-text-content.html)

**Priority**: P0 (Must fix before release)
**Estimated Effort**: 1 hour

---

#### 2. [Next Critical Issue]

[Repeat structure above for each critical issue]

---

### Major Issues (Level AA)

Significant barriers that impact usability for many users.

#### 3. [Issue Title]

**WCAG Criterion**: [e.g., 1.4.3 Contrast (Minimum) (Level AA)]

**Impact**: [High | Medium | Low]
**Affected Users**: [Low vision users | Color blind users | etc.]
**Frequency**: [Throughout site | Specific components]

**Description:**
[Detailed description]

**Location:**
```
File: src/styles/theme.css
Line: 23
Components: Buttons, Links
```

**Current State:**
```css
.button-secondary {
  color: #999999;
  background: #ffffff;
}
```
Contrast ratio: 2.8:1 (Fails - needs 4.5:1)

**Expected State:**
```css
.button-secondary {
  color: #666666;
  background: #ffffff;
}
```
Contrast ratio: 4.7:1 (Passes)

**Recommendation:**
Darken the text color to meet WCAG AA contrast requirements. Test with a contrast checker tool.

**Tool to Verify:**
```bash
python3 scripts/contrast-check.py "#666666" "#ffffff"
# Output: 4.7:1 - PASS (AA)
```

**Priority**: P1 (Fix before public release)
**Estimated Effort**: 2 hours (update theme + test all instances)

---

### Minor Issues (AAA / Best Practices)

Enhancements that improve accessibility beyond minimum compliance.

#### [Issue Number]. [Issue Title]

**WCAG Criterion**: [e.g., 2.4.8 Location (Level AAA)] or [Best Practice]

**Impact**: Low
**Affected Users**: [All users benefit]

**Description:**
[Brief description]

**Recommendation:**
[Quick fix suggestion]

**Priority**: P3 (Nice to have)
**Estimated Effort**: [Time estimate]

---

## Test Results by Page

### Homepage (/)

**Status**: [✓ Pass | ⚠ Issues | ✗ Fail]

**Issues Found**: [Count]
- Critical: [Count]
- Major: [Count]
- Minor: [Count]

**Detailed Issues:**
- Issue #1: [Brief description]
- Issue #3: [Brief description]

**Keyboard Navigation**: [✓ Pass | ✗ Fail]
**Screen Reader**: [✓ Pass | ✗ Fail]
**Color Contrast**: [✓ Pass | ✗ Fail]

---

### Dashboard (/dashboard)

[Repeat structure for each tested page]
