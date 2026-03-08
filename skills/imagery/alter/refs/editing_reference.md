# Image Editing Reference

Comprehensive reference for image modification techniques, provider-specific commands, and refinement strategies.

---

## Modification Patterns

### Image-to-Image (Img2Img)

**Use case:** Changing the overall style or adding global elements to an existing image while preserving the core composition.

**Strength Parameter:** Controls how much the model deviates from the original:
| Strength | Effect | When to Use |
|----------|--------|-------------|
| 0.1–0.3 | Subtle — color grading, minor adjustments | Fine-tuning a nearly-finished asset |
| 0.4–0.6 | Moderate — style transfer, lighting shifts | Changing mood or atmosphere |
| 0.7–0.9 | Dramatic — major style overhaul | Reimagining the visual entirely |

**Prompting tip:** Focus on the *changes* you want to see, but reiterate the core elements you want to *keep*.

### Inpainting & Masking

**Use case:** Precise local edits (e.g., "Change the color of the car," "Add a person to the bench").

**Mask creation:**
- Binary mask: white = edit area, black = preserve
- Clean edges — avoid feathered or anti-aliased mask boundaries
- Include enough context area around the edit target (10-20% padding)
- For complex shapes, create the mask programmatically or use a drawing tool

**In-place consistency:** Inpainting maintains background and subject consistency while swapping specific details. Works best when the replacement content is stylistically compatible with the surrounding area.

---

## Refinement Strategies

When the output is "almost there" but not quite:

| Problem | Strategy | Implementation |
|---------|----------|----------------|
| Missing element | Increase weight in prompt | Add specific adjectives: "vibrant emerald green" not just "green" |
| Unwanted artifact | Add negative constraints | `--negative-prompt "text, watermarks, blur, distortion"` |
| Good composition, bad detail | Fix seed, tweak guidance | Lock `--seed`, adjust `--guidance-scale` up/down |
| Almost perfect, one area wrong | Switch to inpainting | Create a mask for just that region |
| Too different from original | Lower strength | Decrease `--strength` by 0.1-0.2 |
| Not different enough | Raise strength | Increase `--strength` by 0.1-0.2 |
| Wrong color balance | Adjust prompt specifics | Be explicit about lighting and color temperature |
| Artifacts at edges | Better mask | Add padding around edit area, use cleaner mask edges |

### Iteration Flow
```
1. DIAGNOSE  — What specifically is wrong? (color, composition, detail, artifact)
2. ADJUST    — Modify the right parameter for the issue type
3. REGENERATE — Run with adjusted parameters
4. REVIEW     — Use the review sub-skill to validate
5. REPEAT     — Until quality gates pass
```

---

## Provider-Specific Commands

### Provider-Agnostic (Recommended)

```bash
# Image-to-image edit
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" edit \
  --image ./source.png \
  --prompt "Same scene but with dramatic sunset sky" \
  --output ./v2.png

# Inpainting with mask
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" inpaint \
  --image ./source.png \
  --mask ./mask.png \
  --prompt "Replace with floating lanterns" \
  --output ./v2_inpaint.png

# Use a specific provider
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" edit \
  --provider stability \
  --image ./source.png \
  --prompt "Oil painting style" \
  --output ./v2_oil.png
```

### cstudio CLI (Vertex AI Creative Studio)

```bash
# Configuration
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Image-to-image
cstudio edit image \
  --image ./v1.png \
  --prompt "A gothic garden with purple roses" \
  --output ./v2.png

# Inpainting
cstudio inpaint image \
  --image ./v1.png \
  --mask ./mask.png \
  --prompt "Replace statues with floating lanterns" \
  --output ./v1_inpaint.png

# Upscaling (cstudio only)
cstudio upscale image --image ./draft.png --output ./final_hires.png

# Advanced controls
cstudio edit image \
  --image ./v1.png \
  --prompt "Same scene, golden hour lighting" \
  --negative-prompt "text, watermarks" \
  --seed 42 \
  --guidance-scale 8.5 \
  --output ./v2_golden.png
```

### Advanced Controls (All Providers)

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `--prompt` | What to change/add | "Dramatic sunset sky" |
| `--negative-prompt` | Elements to exclude | "text, watermarks, blur" |
| `--seed` | Reproducible results | Any integer |
| `--guidance-scale` | Prompt adherence | Higher = more literal |
| `--strength` | Deviation from original (img2img) | 0.1–0.9 |
| `--sample-count` | Multiple variations | 1–4 (cstudio only) |

---

## Final Polish

Use upscaling as the last step to bring a draft to production quality. Currently only available via cstudio:

```bash
cstudio upscale image --image ./final_draft.png --output ./final_hires.png
```

For other providers, generate at the highest resolution supported and use external tools for additional upscaling if needed.
