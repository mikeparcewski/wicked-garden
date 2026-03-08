---
name: alter
description: |
  AI-powered image modification: img2img editing and mask-based inpainting.
  Requires a provider that supports editing operations.

  Use when: "edit image", "modify image", "change image", "inpaint", "img2img"
---

# Image Alteration

AI-powered modification of existing images through two primary modes: image-to-image editing (global changes) and mask-based inpainting (local changes).

## When To Use This Skill

- Modifying style, lighting, or mood of an existing image
- Replacing or adding specific elements within an image
- Iterating on generated images to reach desired output
- Making targeted local edits while preserving the rest

## Modification Modes

### Image-to-Image (Global Edits)

Changes the overall style or adds global elements while preserving core composition.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" edit \
  --image ./source.png \
  --prompt "Same scene but with a dramatic sunset sky" \
  --output ./v2.png
```

**Key control**: The strength parameter determines how much the model deviates from the original.
- `--strength 0.2-0.3` — Subtle changes (color grading, minor adjustments)
- `--strength 0.4-0.6` — Moderate changes (style transfer, lighting shifts)
- `--strength 0.7-0.9` — Dramatic changes (major style overhaul)

### Inpainting (Local Edits)

Precise edits to specific regions using a binary mask (white = edit area, black = preserve).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" inpaint \
  --image ./source.png \
  --mask ./mask.png \
  --prompt "Replace with floating lanterns" \
  --output ./v2_inpaint.png
```

**Best practices for masks:**
- Clean edges — avoid feathered or anti-aliased mask boundaries
- Include enough context area around the edit target
- For complex shapes, create the mask programmatically or use a drawing tool

## Iterative Refinement Loop

When the output is close but not quite right:

```
1. DIAGNOSE  — What specifically is wrong? (color, composition, detail, artifact)
2. ADJUST    — Modify the right parameter for the issue:
   - Wrong elements → refine prompt, add negative prompt
   - Wrong style → adjust strength parameter
   - Wrong detail → fix seed, tweak guidance scale
   - Local issue → switch to inpainting with a targeted mask
3. REGENERATE — Run with adjusted parameters
4. REVIEW     — Use the review sub-skill to validate
```

### Refinement Strategies

| Problem | Solution |
|---------|----------|
| Missing element | Increase weight in prompt with specific adjectives |
| Unwanted artifact | Add to `--negative-prompt` |
| Good composition, bad detail | Fix `--seed`, adjust `--guidance-scale` |
| Almost perfect, one area wrong | Switch to inpainting for that region |
| Too different from original | Lower `--strength` value |
| Not different enough | Raise `--strength` value |

### Final Polish

Use upscaling as the last step to bring a draft to production quality:

```bash
# Upscaling (cstudio only — other providers may not support this)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" generate \
  --provider cstudio \
  --prompt "upscale" \
  --output ./final_hires.png
```

## Detailed References

- **Editing techniques, provider commands, and refinement strategies**: [refs/editing_reference.md](refs/editing_reference.md)

## Integration With Other Sub-Skills

- Use **review** before altering to understand what needs to change
- Use **review** after altering to validate the changes
- If starting from scratch is better than editing, hand off to **create**
- Alteration is the "Execute" and "Refine" steps of the Analyze-Execute-Review-Refine loop
