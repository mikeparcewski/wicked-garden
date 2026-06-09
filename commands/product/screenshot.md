---
description: Screenshot-based UI review using Claude's multimodal vision — analyze layout, color, typography, and consistency from image files
argument-hint: "<image-path> [<reference-path>]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:screenshot

Review UI design from screenshot images using Claude's multimodal vision — layout,
spacing, color, typography, visual consistency — without source code. Formats: PNG,
JPG, JPEG, WEBP, GIF.

## Run it inline (no dispatch)

1. Parse `<image-path>` (required) and optional `<reference-path>`.
2. `Read(file_path="{image-path}")` (and the reference if provided) — the Read tool renders images visually.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/screenshot.md")` — the evaluation rubric (layout/color/typography/components), comparison mode, and output format.
4. Apply the rubric directly to the rendered image(s) and emit the review. Flag contrast issues for `product:a11y`; compare against a `product:mockup` spec when relevant.
