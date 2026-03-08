---
name: create
description: |
  AI-powered image generation from text prompts using multiple providers.
  Supports 5 providers: cstudio, vertex-curl, OpenAI, Stability AI, Replicate.

  Use when: "generate image", "create image", "text to image", "new visual"
    - REPLICATE_API_TOKEN (Replicate Flux models)
---

# Image Creation

AI-powered image generation from text prompts. Supports multiple providers through a unified abstraction layer.

## When To Use This Skill

- Generating new images from text descriptions
- Creating visual assets for marketing, UI, presentations
- Producing multiple variations of a concept
- Building visual prototypes from written specifications

## Supported Providers

| Provider | Interface | Auth | Best For |
|----------|-----------|------|----------|
| **cstudio** | CLI binary | `GOOGLE_CLOUD_PROJECT` | Interactive use, rapid iteration |
| **vertex-curl** | gcloud + curl | `gcloud auth` | CI/CD, scripted pipelines |
| **openai** | REST API | `OPENAI_API_KEY` | Existing OpenAI subscription |
| **stability** | REST API | `STABILITY_API_KEY` | Stable Diffusion 3.5 |
| **replicate** | REST API | `REPLICATE_API_TOKEN` | Flux models, pay-per-use |

### Provider Detection

```bash
# Check which providers are available
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" detect
```

The provider abstraction selects the best available provider automatically. A specific provider can be forced when needed.

## Generation Workflow

```
1. UNDERSTAND — Clarify the visual intent and requirements
2. CRAFT     — Build a high-quality prompt with style and constraints
3. GENERATE  — Execute via the provider abstraction
4. REVIEW    — Use the review sub-skill to validate output
5. REFINE    — Iterate on prompt, parameters, or provider settings
```

### Step 1: Understand Requirements

Before generating, gather:
- **Subject**: What is the image of?
- **Style**: Photorealistic, illustration, abstract, etc.
- **Dimensions**: Aspect ratio (16:9, 1:1, 9:16, etc.)
- **Context**: Where will this image be used?
- **Constraints**: Brand colors, no text, specific mood

### Step 2: Craft the Prompt

Effective prompts follow this structure:

```
[Subject] + [Style/Medium] + [Lighting/Mood] + [Composition] + [Details]
```

Example: "A minimalist office workspace with a single monitor, soft natural side lighting, centered composition, matte finish, neutral color palette"

For detailed prompt engineering techniques, see [refs/prompt_engineering.md](refs/prompt_engineering.md).

### Step 3: Generate

```bash
# Basic generation (auto-detects best available provider)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" generate \
  --prompt "Your crafted prompt" \
  --output ./output/v1.png

# Use a specific provider
python3 "${CLAUDE_PLUGIN_ROOT}/skills/imagery/scripts/provider.py" generate \
  --prompt "Your crafted prompt" \
  --provider openai \
  --output ./output/v1.png
```

### Key Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `--prompt` | Text description | "A gothic garden at dusk" |
| `--aspect-ratio` | Output dimensions | "16:9", "1:1", "9:16" |
| `--negative-prompt` | Elements to exclude | "text, watermarks, blur" |
| `--sample-count` | Number of variations | 1-4 |
| `--seed` | Reproducible results | Any integer |
| `--guidance-scale` | Prompt adherence | Higher = more literal |
| `--model` | Model selection | "imagen-3.0-generate-001" |

## Detailed References

- **Provider APIs and configuration**: [refs/provider_reference.md](refs/provider_reference.md)
- **Prompt engineering techniques**: [refs/prompt_engineering.md](refs/prompt_engineering.md)

## Integration With Other Sub-Skills

- Use **review** after generation to validate quality and run gates
- If modifications are needed, hand off to **alter** for targeted edits
- Generation output feeds into the Analyze-Execute-Review-Refine loop
