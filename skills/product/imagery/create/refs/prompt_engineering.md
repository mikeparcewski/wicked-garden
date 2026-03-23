# Prompt Engineering for Image Generation

Guidance on crafting effective prompts that produce high-quality, predictable image outputs.

## Prompt Structure

The most effective prompts follow a layered structure:

```
[Subject] + [Style/Medium] + [Lighting/Mood] + [Composition] + [Details]
```

### Layer Breakdown

| Layer | Purpose | Examples |
|-------|---------|---------|
| **Subject** | What is in the image | "A solitary lighthouse on a cliff" |
| **Style/Medium** | Artistic approach | "Oil painting", "Photorealistic", "Flat vector" |
| **Lighting/Mood** | Atmosphere | "Warm golden hour", "Dramatic noir shadows" |
| **Composition** | Framing and layout | "Centered", "Rule of thirds", "Bird's eye view" |
| **Details** | Specifics and texture | "Weathered stone", "Matte finish", "4K resolution" |

## Prompt Quality Tiers

### Tier 1: Basic (Low Predictability)
```
"A cat sitting on a chair"
```
Produces generic results with high variance.

### Tier 2: Descriptive (Medium Predictability)
```
"A tabby cat sitting on a vintage wooden chair, soft natural lighting"
```
Better results but still leaves many decisions to the model.

### Tier 3: Precision (High Predictability)
```
"A tabby cat with green eyes sitting on a weathered oak rocking chair,
soft diffused window light from the left, warm color palette with
cream and amber tones, shallow depth of field, photorealistic style"
```
Produces consistent, predictable results.

## Negative Prompts

Use `--negative-prompt` to exclude unwanted elements:

```bash
--negative-prompt "text, watermarks, blurry, low quality, distorted, extra limbs"
```

### Common Negative Prompt Categories

| Category | Terms |
|----------|-------|
| **Quality** | "blurry, pixelated, low resolution, jpeg artifacts" |
| **Text** | "text, words, letters, watermarks, signatures" |
| **Anatomy** | "extra limbs, deformed hands, extra fingers" |
| **Style** | "cartoon, anime, sketch" (when photorealism is wanted) |

## Style Keywords

### Photographic Styles
- Photorealistic, DSLR quality, bokeh, shallow depth of field
- Studio lighting, natural lighting, golden hour, blue hour
- Macro photography, aerial photography, portrait photography

### Artistic Styles
- Oil painting, watercolor, digital art, concept art
- Minimalist, maximalist, abstract, surrealist
- Flat design, isometric, low poly, pixel art

### Mood Keywords
- Ethereal, moody, dramatic, serene, vibrant
- Dark and gritty, light and airy, warm and inviting
- Clinical, futuristic, nostalgic, whimsical

## Aspect Ratio Guidelines

| Ratio | Use Case |
|-------|----------|
| `1:1` | Social media posts, profile images, icons |
| `16:9` | Presentations, hero banners, video thumbnails |
| `9:16` | Mobile stories, vertical banners |
| `4:3` | Blog images, product shots |
| `3:2` | Photography standard, print media |

## Iteration Strategies

### When results miss the mark:

1. **Too generic** — Add more specific adjectives and details
2. **Wrong style** — Be more explicit about the medium ("oil on canvas" vs "painting")
3. **Wrong mood** — Add lighting and atmosphere keywords
4. **Unwanted elements** — Add them to the negative prompt
5. **Good but not great** — Lock the seed, adjust guidance scale up/down
6. **Inconsistent** — Reduce sample count to 1, increase guidance scale

### Guidance Scale Tuning

| Value | Behavior |
|-------|----------|
| Low (1-5) | Creative, loose interpretation of prompt |
| Medium (7-10) | Balanced adherence and creativity |
| High (12-20) | Strict adherence, can reduce quality at extremes |

Start at the default and adjust based on results. If outputs are too "safe", lower it. If they ignore your prompt, raise it.
