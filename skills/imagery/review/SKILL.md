---
name: review
description: |
  Multi-dimensional visual analysis and quality review of images.
  No external provider required — reads image files directly.

  Use when: "review image", "analyze image", "visual review", "brand check",
  "accessibility review", "production readiness", "image quality"
portability: portable
---

# Image Review & Analysis

Visual analysis and quality review of images. No external provider or CLI tool required — just read the image file directly.

## When To Use This Skill

- Analyzing what an image contains (subjects, scene, context)
- Extracting technical design details from mockups or diagrams
- Evaluating style, color palette, mood, and lighting
- Reviewing layout composition and visual hierarchy
- Running quality gates before delivery (brand, a11y, production, sensitivity)

## Multi-Dimensional Analysis Framework

Four analysis lenses, each with a dedicated reference:

| Lens | Purpose | Reference |
|------|---------|-----------|
| **General** | Subject, scene, context summary | [refs/analysis_lenses.md](refs/analysis_lenses.md) |
| **Technical** | Components, hierarchy, interactivity | [refs/analysis_lenses.md](refs/analysis_lenses.md) |
| **Style** | Palette, mood, lighting, texture | [refs/analysis_lenses.md](refs/analysis_lenses.md) |
| **Layout** | Focal points, composition, visual weight | [refs/analysis_lenses.md](refs/analysis_lenses.md) |

### Quick Analysis

For most tasks, start with General analysis. Add Technical for UI mockups, Style for creative assets, or Layout for marketing materials.

```
1. Read the image file
2. Apply the relevant analysis lens(es)
3. Produce a structured report
```

## Quality Gates

Four review gates ensure assets are "Business Ready" before delivery:

| Gate | Purpose | Reference |
|------|---------|-----------|
| **Brand Compliance** | Logo, palette, typography, tone alignment | [refs/quality_gates.md](refs/quality_gates.md) |
| **Accessibility** | Contrast ratios, color-blind safety, readability | [refs/quality_gates.md](refs/quality_gates.md) |
| **Production Readiness** | Artifacts, resolution, format, cleanliness | [refs/quality_gates.md](refs/quality_gates.md) |
| **Sensitivity** | Cultural appropriateness, inclusivity, bias | [refs/quality_gates.md](refs/quality_gates.md) |

### Gate Selection

Not every asset needs all four gates. Use this guide:

- **Internal draft**: Production Readiness only
- **External marketing**: All four gates
- **UI component**: Brand + Accessibility + Production
- **Social media**: Brand + Sensitivity + Production

## Workflow: Analyze, Assess, Report

```
Step 1: ANALYZE — Read the image, apply relevant lenses
Step 2: ASSESS  — Run applicable quality gates
Step 3: REPORT  — Structured findings with pass/fail per gate
```

### Report Format

```markdown
## Image Review: {filename}

### Analysis
- **Subject:** ...
- **Style:** ...
- **Composition:** ...

### Quality Gates
| Gate | Status | Notes |
|------|--------|-------|
| Brand | PASS/FAIL | ... |
| a11y  | PASS/FAIL | ... |
| Production | PASS/FAIL | ... |
| Sensitivity | PASS/FAIL | ... |

### Recommendations
- ...
```

## Integration With Other Sub-Skills

- After **create** or **alter** generates an image, use **review** to validate
- Review findings feed back into the Analyze-Execute-Review-Refine loop
- Quality gate failures should include actionable fix suggestions for the next iteration
