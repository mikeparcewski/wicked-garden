---
description: Screenshot-based UI review using Claude's multimodal vision — analyze layout, color, typography, and consistency from image files
argument-hint: "<image-path> [<reference-path>]"
---

# /wicked-garden:design:screenshot

Review UI design from screenshot images using Claude's multimodal capabilities.
Analyzes layout, spacing, color, typography, and visual consistency without
requiring access to source code.

## Usage

```bash
# Review a single screenshot
/wicked-garden:design:screenshot /tmp/dashboard.png

# Compare implementation against a design reference
/wicked-garden:design:screenshot /tmp/built-ui.png /tmp/design-spec.png

# Review screenshots in a directory
/wicked-garden:design:screenshot ./screenshots/
```

## Supported Formats

PNG, JPG, JPEG, WEBP, GIF

## Instructions

### 1. Parse Arguments

Extract `<image-path>` (required) and optional `<reference-path>` for comparison.

### 2. Read the Image(s)

```
Read(file_path="{image-path}")
```

If a reference is provided, read it too:

```
Read(file_path="{reference-path}")
```

Claude can read image files directly and analyze them visually.

### 3. Analyze the Screenshot

Evaluate the visual design for:

**Layout and Spacing**
- Is whitespace consistent and intentional?
- Do elements align to a visible grid?
- Is content grouped logically?

**Color and Contrast**
- Cohesive, limited color palette?
- Sufficient text/background contrast?
- Semantic color usage (errors, success, warnings)?

**Typography**
- Clear heading hierarchy?
- Readable font sizes and line spacing?
- Consistent font family usage?

**Component Consistency**
- Similar elements styled identically?
- Interactive elements visually distinct?
- States (selected, active) clearly shown?

### 4. Comparison Mode

If a reference image is provided, compare:
- Spacing fidelity (does built match spec proportions?)
- Color accuracy (same palette?)
- Typography match (weights, sizes, hierarchy)
- Missing or added elements

### 5. Present Findings

```markdown
## Screenshot Review: {filename}

**Viewport**: {desktop/tablet/mobile/unknown}
**Overall**: {Polished | Minor Issues | Needs Work | Major Problems}

### Visual Design
**Spacing**: {assessment}
**Color**: {assessment}
**Typography**: {assessment}
**Components**: {assessment}

### Issues
{findings with location descriptions}

### Comparison {if reference provided}
{fidelity assessment}

### Recommendations
{prioritized fixes}
```

## Capturing Screenshots

If you need to capture from a URL first:

```bash
# If wicked-browse is available
wicked-browse screenshot {url} --output /tmp/review.png
wicked-browse screenshot {url} --width 375 --output /tmp/mobile.png
```

## Integration

- **wicked-design:review**: Code-based analysis complements image-based review
- **wicked-design:a11y**: Flag contrast issues for accessibility follow-up
- **wicked-design:mockup**: Compare mockup spec against implementation screenshot
