# cstudio CLI Reference

The **Vertex AI Creative Studio CLI (`cstudio`)** is the primary interface for high-fidelity visual generation and modification.

## Configuration

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

## Image Generation

```bash
cstudio generate image \
  --prompt "A detailed painting of a gothic garden" \
  --aspect-ratio "16:9" \
  --model "imagen-3.0-generate-001" \
  --output ./v1.png
```

## Image Modification (Image-to-Image)

Modify an existing image by providing a source file and a new prompt:
```bash
cstudio edit image \
  --image ./v1.png \
  --prompt "A detailed painting of a gothic garden with purple roses" \
  --output ./v2.png
```

## Image Inpainting (Masking)

Selectively change parts of an image:
```bash
cstudio inpaint image \
  --image ./v1.png \
  --mask ./mask.png \
  --prompt "Replace the statues with floating lanterns" \
  --output ./v1_inpaint.png
```

## Visual Analysis

Obtain a detailed description of an image for creative context:
```bash
cstudio analyze image --image ./ref.png
```

## Advanced Controls

- `--sample-count`: Generate multiple variations (e.g., `--sample-count 4`).
- `--negative-prompt`: Exclude specific elements (e.g., `--negative-prompt "text, watermarks"`).
- `--seed`: For deterministic/reproducible results.
- `--guidance-scale`: Influence the model's adherence to the prompt.
