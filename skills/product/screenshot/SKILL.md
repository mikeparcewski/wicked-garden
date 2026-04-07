---
name: screenshot
description: |
  Screenshot-based UI review using Claude's multimodal capabilities.
  Analyzes visual design from image files — layout, spacing, color, typography,
  responsiveness — and compares against design system rules.

  Use when: "screenshot review", "UI screenshot", "visual analysis from image",
  "design from screenshot", "review PNG", "review JPG", "image-based review"
portability: portable
---

# Screenshot Skill

Analyze UI design directly from screenshot images using Claude's multimodal
vision capabilities. No code needed — review what users actually see.

## How to Use Read on Images

Claude can read PNG, JPG, WEBP, and GIF files directly with the Read tool:

```
Read(file_path="/path/to/screenshot.png")
```

The image is presented visually. Analyze it for design quality, consistency,
and usability issues without requiring access to source code.

## What to Analyze

### Layout and Spacing

- Is whitespace consistent and intentional?
- Do elements align to a visible grid?
- Are margins/padding proportional and balanced?
- Is content grouped logically (proximity principle)?
- Does the layout breathe, or feel cramped?

### Color and Contrast

- Is the color palette cohesive (limited, intentional palette)?
- Do text and background combinations have sufficient contrast?
- Are colors used semantically (red for errors, green for success)?
- Is there visual hierarchy through color weight?

### Typography

- Is there a clear heading hierarchy (H1 > H2 > body)?
- Are font sizes proportional and readable?
- Is line spacing comfortable (not too tight or loose)?
- Consistent font family usage — not too many typefaces?

### Component Consistency

- Do similar elements look the same (all buttons styled identically)?
- Are interactive elements visually distinguishable from static ones?
- Are states (active, selected) visually distinct?

### Responsiveness Clues

- Does the layout look designed for this viewport size?
- Are there elements that appear truncated or overflowing?
- Would this layout adapt to mobile without breaking?

## Comparison with Reference Designs

When a reference image is provided:

```
Read(file_path="/path/to/reference.png")   # design spec or comp
Read(file_path="/path/to/implementation.png")  # built UI
```

Compare:
- Spacing fidelity (does built match spec proportions?)
- Color accuracy (same palette?)
- Typography match (weights, sizes, hierarchy)
- Component faithfulness (icons, buttons, inputs)
- Missing or added elements

## Screenshot Capture

Use the **Read** tool on a screenshot file, or capture via browser automation if available (e.g., Playwright, Puppeteer, or an MCP browser tool). Place captured images in a local path and then read them for analysis.

## Multi-View Analysis

Review the same page at multiple viewports:

```
1. Capture desktop (1440px)
2. Capture tablet (768px)
3. Capture mobile (375px)
4. Compare: layout adapts correctly?
5. Check: no content hidden or truncated?
6. Check: touch targets large enough on mobile?
```

## Output Format

```markdown
## Screenshot Review: {filename or URL}

**Viewport**: {desktop/tablet/mobile/unknown}
**Overall**: {Polished | Minor Issues | Needs Work | Major Problems}

### Visual Design

**Spacing**: {✓ Balanced | ⚠ Inconsistent | ✗ Cramped/Sparse}
- {finding}

**Color**: {✓ Cohesive | ⚠ Minor issues | ✗ Inconsistent}
- {finding}

**Typography**: {✓ Clear hierarchy | ⚠ Minor issues | ✗ Unclear}
- {finding}

**Components**: {✓ Consistent | ⚠ Variations | ✗ Inconsistent}
- {finding}

### Issues Found

#### Critical
- {issue visible in screenshot, with description of location}

#### Minor
- {polish item}

### Comparison with Reference {if provided}
- Spacing: {matches/off by approximately X}
- Color: {matches/discrepancy}
- Missing: {elements in spec not in implementation}
- Added: {elements in implementation not in spec}

### Recommendations
1. {highest priority fix}
2. {second fix}
```

## Integration

- **visual-review skill**: Use for code-based analysis; screenshot for image-based
- **accessibility skill**: Color contrast visible in screenshots
- **mockup skill**: Screenshots of implementations vs mockup specs
- **Browser automation**: Capture screenshots from live URLs via Playwright, Puppeteer, or an MCP browser tool if available
- **imagery/review skill**: For AI-powered visual analysis of screenshots, see the `imagery/review` skill
