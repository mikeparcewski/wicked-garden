# Quality Gates Reference

Four review gates ensure visual assets are "Business Ready" before delivery. Each gate produces a PASS/FAIL verdict with actionable feedback.

---

## Gate 1: Brand Compliance

Ensures a visual asset aligns with corporate or project brand guidelines.

### Checklist
- [ ] **Logo placement**: Correct position, size, and clearance zone
- [ ] **Logo integrity**: Not distorted, recolored, or cropped
- [ ] **Primary brand colors**: Dominant and correctly applied
- [ ] **Typography**: Correct fonts, weights, and sizes (if text present)
- [ ] **Tone alignment**: Visual style matches brand archetype (e.g., luxury = refined lighting, tech = clean/modern)
- [ ] **Photography style**: Matches brand guidelines (candid vs. staged, warm vs. cool)

### Review Workflow
1. **Palette Check:** Compare extracted hex codes against the official style guide
2. **Logo Integrity:** Ensure the logo isn't distorted, recolored incorrectly, or placed too close to other elements
3. **Aesthetic Alignment:** Does the image "feel" like the brand?

### Pass Criteria
- Primary brand colors are dominant
- Visual style matches the established brand archetype
- Imagery is appropriate for the target audience
- No unauthorized modifications to brand elements

### Common Failures
| Issue | Fix |
|-------|-----|
| Off-brand color (#2196F3 vs brand #1976D2) | Adjust color values to match brand palette exactly |
| Logo too small or crowded | Increase clearance zone, resize to minimum spec |
| Wrong mood (casual for premium brand) | Adjust lighting, composition, and subject styling |

---

## Gate 2: Accessibility (a11y)

Ensures visual assets are accessible to all users, including those with visual impairments.

### Checklist
- [ ] **Text contrast**: Meets WCAG 2.1 AA (4.5:1 for normal text, 3:1 for large text)
- [ ] **Non-text contrast**: UI components and graphics meet 3:1 ratio
- [ ] **Color independence**: Information not conveyed by color alone
- [ ] **Color-blind safety**: Key elements distinguishable in protanopia/deuteranopia simulation
- [ ] **Text readability**: Legible at intended display size
- [ ] **Visual noise**: No distracting patterns or animations that could trigger seizures

### Review Workflow
1. **Contrast Analysis:** Check contrast between text/icons and their backgrounds
2. **Color-Blind Simulation:** Analyze how the image appears in grayscale or simulated color-blindness modes
3. **Readability Check:** Ensure any text within the image is legible at its intended display size

### Pass Criteria
- Contrast meets WCAG AA or AAA standards
- Users can distinguish between elements without relying on color
- Focal point is clear and undistorted
- All text is legible at intended display size

### WCAG Quick Reference
| Element | AA Minimum | AAA Target |
|---------|-----------|------------|
| Normal text (< 18pt) | 4.5:1 | 7:1 |
| Large text (≥ 18pt or 14pt bold) | 3:1 | 4.5:1 |
| UI components / graphics | 3:1 | 3:1 |

---

## Gate 3: Production Readiness

Final quality gate before a visual asset is delivered for business use.

### Checklist
- [ ] **Resolution**: Meets minimum spec for intended use (web: 72dpi, print: 300dpi)
- [ ] **Aspect ratio**: Matches requested dimensions exactly
- [ ] **File format**: Correct format (PNG for transparency, JPEG for photos, SVG for icons)
- [ ] **File size**: Within acceptable limits for delivery channel
- [ ] **Artifacts**: No blur, pixelation, or AI-generated distortions
- [ ] **Cleanliness**: No unintended text, watermarks, or background clutter
- [ ] **Edge quality**: Clean edges on subjects, no halo effects or fringing

### Review Workflow
1. **Artifact Inspection:** Zoom in on edges and complex textures to check for AI "hallucinations" or blurring
2. **Spec Validation:** Confirm the image matches the requested aspect ratio and resolution
3. **Background Cleanup:** Identify any distracting elements that don't serve the primary subject

### Pass Criteria
- Image is sharp and free of compression artifacts
- Dimensions match the request exactly
- Suitable for intended channel (social media, print, web, presentation)

### Common Specifications
| Channel | Resolution | Aspect Ratio | Format | Max Size |
|---------|-----------|--------------|--------|----------|
| Web hero | 1920x1080 | 16:9 | JPEG/WebP | 500KB |
| Social (Instagram) | 1080x1080 | 1:1 | JPEG/PNG | 8MB |
| Social (Story) | 1080x1920 | 9:16 | JPEG/PNG | 8MB |
| Print A4 | 2480x3508 | ~1:1.41 | PDF/TIFF | - |
| Presentation | 1920x1080 | 16:9 | PNG | 5MB |

---

## Gate 4: Cultural Sensitivity

Ensures visual assets are appropriate for global audiences and free of unintended bias.

### Checklist
- [ ] **Symbols**: No symbols/gestures with unintended cultural meanings
- [ ] **Representation**: Diverse and inclusive (where people are depicted)
- [ ] **Stereotypes**: No reinforcement of cultural stereotypes
- [ ] **Color meanings**: Colors appropriate for target markets (white = purity in West, mourning in parts of Asia)
- [ ] **Religious/political**: No unintended religious or political symbolism
- [ ] **Gender/age**: Balanced representation unless context-specific

### Review Workflow
1. **Symbolic Analysis:** Check for symbols, gestures, or icons with different meanings across cultures
2. **Representation Audit:** Ensure people and settings reflect intended diversity without stereotypes
3. **Global Context:** Consider color and symbol meanings in target markets

### Pass Criteria
- Image is free of culturally insensitive tropes
- Aligns with global inclusivity standards
- Symbols used correctly in their intended context
- Representation is balanced and respectful

### Regional Considerations
| Element | Western | East Asian | Middle Eastern | Latin American |
|---------|---------|-----------|----------------|----------------|
| White | Purity, clean | Mourning | Purity | Peace |
| Red | Danger, love | Luck, prosperity | Danger | Passion |
| Thumbs up | Approval | Approval | Offensive (some regions) | Approval |
| Hand gestures | Varies | Conservative | Very conservative | Expressive |

---

## Gate Selection Guide

Not every asset needs all four gates:

| Asset Type | Brand | a11y | Production | Sensitivity |
|-----------|-------|------|------------|-------------|
| Internal draft | - | - | ✓ | - |
| UI component | ✓ | ✓ | ✓ | - |
| External marketing | ✓ | ✓ | ✓ | ✓ |
| Social media | ✓ | - | ✓ | ✓ |
| Investor presentation | ✓ | - | ✓ | ✓ |
| Documentation screenshot | - | ✓ | ✓ | - |
