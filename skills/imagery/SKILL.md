---
name: imagery
description: |
  Visual asset lifecycle management — analysis, generation, modification, and review.
  Three sub-skills cover the full creative pipeline with provider abstraction.

  Use when: "image", "visual", "generate", "review image", "edit image",
  "create image", "analyze image", "brand check", "accessibility review"
---

# Imagery: Visual Asset Lifecycle

Manage the full lifecycle of visual assets through three specialized sub-skills. Each sub-skill handles a distinct phase of creative work, from analysis through generation to iterative refinement.

## Sub-Skills

| Sub-Skill | Purpose | Provider Required |
|-----------|---------|-------------------|
| [**review**](review/SKILL.md) | Image analysis and quality review | None (reads image files directly) |
| [**create**](create/SKILL.md) | Text-to-image generation | cstudio or vertex-curl |
| [**alter**](alter/SKILL.md) | Image modification (img2img, inpainting) | cstudio or vertex-curl |

### When To Use Each

- **"What is in this image?"** — review
- **"Generate a new image of..."** — create
- **"Change this image to..."** — alter
- **"Is this image ready for production?"** — review (quality gates)
- **"Make the sky more dramatic"** — alter (img2img or inpainting)

## The Creative Loop: Analyze-Execute-Review-Refine

Every visual task follows this iterative cycle until the output matches requirements:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ ANALYZE │────>│ EXECUTE │────>│ REVIEW  │────>│ REFINE  │
│ (review)│     │(create/ │     │(review) │     │ (alter) │
│         │     │ alter)  │     │         │     │         │
└─────────┘     └─────────┘     └─────────┘     └────┬────┘
     ^                                                │
     └────────────────────────────────────────────────┘
```

1. **Analyze** — Understand the visual context, reference images, or requirements (review sub-skill)
2. **Execute** — Generate new assets (create) or modify existing ones (alter)
3. **Review** — Run quality gates: brand, accessibility, production, sensitivity (review sub-skill)
4. **Refine** — Adjust prompts, parameters, or masks based on review findings (alter sub-skill)

## Provider Status

The imagery skill uses a provider abstraction layer. Review works without any provider. Create and alter require at least one:

```bash
# Check available providers
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" detect
```

| Provider | How to Enable |
|----------|---------------|
| **cstudio** | Install CLI binary, set `GOOGLE_CLOUD_PROJECT` |
| **vertex-curl** | `gcloud auth login`, set `GOOGLE_CLOUD_PROJECT` |

## Quick Start

### Analyze an existing image
```
Read the image file → apply review sub-skill analysis lenses
```

### Generate a new image
```
Describe requirements → create sub-skill generates → review sub-skill validates
```

### Modify an existing image
```
Review identifies issues → alter sub-skill applies changes → review validates
```

## Reference Map

### Review References
- `review/refs/analysis_general.md` — General scene description
- `review/refs/analysis_technical.md` — Technical/UI extraction
- `review/refs/analysis_style.md` — Style, palette, mood
- `review/refs/analysis_layout.md` — Composition and layout
- `review/refs/review_brand.md` — Brand compliance gate
- `review/refs/review_accessibility.md` — Accessibility gate
- `review/refs/review_production.md` — Production readiness gate
- `review/refs/review_sensitivity.md` — Cultural sensitivity gate

### Create References
- `create/refs/provider_reference.md` — Provider APIs and configuration
- `create/refs/prompt_engineering.md` — Crafting effective prompts

### Alter References
- `alter/refs/modifications.md` — Img2img and inpainting patterns
- `alter/refs/cstudio_usage.md` — CLI command reference
