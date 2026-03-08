# Provider Reference

Detailed documentation for each supported image generation provider.

## Provider: cstudio (Vertex AI Creative Studio CLI)

### Overview
A CLI binary that wraps the Vertex AI Imagen API with a developer-friendly interface.

### Authentication
```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"  # default region
```

Requires an active `gcloud auth` session with appropriate IAM permissions:
- `aiplatform.endpoints.predict` on the Imagen endpoint

### Detection
```bash
# Check if cstudio is available
which cstudio || echo "${CSTUDIO_PATH}/cstudio"
```

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| Text-to-image | Yes | `cstudio generate image` |
| Image-to-image | Yes | `cstudio edit image` |
| Inpainting | Yes | `cstudio inpaint image` |
| Upscaling | Yes | `cstudio upscale image` |
| Analysis | Yes | `cstudio analyze image` |
| Batch generation | Yes | `--sample-count 1-4` |

### Models
- `imagen-3.0-generate-001` — Latest generation model (default)
- Check `cstudio models list` for available models in your project

---

## Provider: vertex-curl (Vertex AI via gcloud + curl)

### Overview
Direct REST API access to Vertex AI Imagen endpoints using `gcloud` for auth and `curl` for requests. No additional binary required.

### Authentication
```bash
# Ensure gcloud is configured
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

### API Endpoint
```
https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${LOCATION}/publishers/google/models/${MODEL}:predict
```

### Request Format
```bash
# Generate an image
ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${ENDPOINT}" \
  -d '{
    "instances": [{"prompt": "Your prompt here"}],
    "parameters": {
      "sampleCount": 1,
      "aspectRatio": "16:9",
      "negativePrompt": "text, watermarks"
    }
  }'
```

### Response Format
The response contains base64-encoded image data:
```json
{
  "predictions": [
    {
      "bytesBase64Encoded": "...",
      "mimeType": "image/png"
    }
  ]
}
```

Decode with: `echo "${BASE64_DATA}" | base64 -d > output.png`

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| Text-to-image | Yes | Standard predict endpoint |
| Image-to-image | Yes | Include base image in request |
| Inpainting | Yes | Include image + mask in request |
| Upscaling | Limited | Separate endpoint if available |
| Analysis | No | Read the image file directly instead |
| Batch generation | Yes | `sampleCount` parameter |

---

## Provider: openai (OpenAI Image API)

### Overview
OpenAI's image generation and editing API. Uses `gpt-image-1` for generation and editing.

### Authentication
```bash
export OPENAI_API_KEY="sk-..."
```

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| Text-to-image | Yes | `POST /v1/images/generations` (JSON) |
| Image-to-image | Yes | `POST /v1/images/edits` (multipart) |
| Inpainting | Yes | `POST /v1/images/edits` with mask (multipart) |
| Upscaling | No | Not available via API |
| Analysis | No | Read the image file directly instead |
| Batch generation | Yes | `n` parameter (1-10) |

### Models
- `gpt-image-1` — Latest generation and editing model

### Notes
- Generation uses JSON API with `b64_json` response format
- Edit and inpaint use multipart/form-data uploads
- Supports `size`, `quality`, and `style` parameters for generation

---

## Provider: stability (Stability AI)

### Overview
Stability AI's Stable Diffusion 3.5 API for image generation and editing.

### Authentication
```bash
export STABILITY_API_KEY="sk-..."
```

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| Text-to-image | Yes | `POST /v2beta/stable-image/generate/sd3` |
| Image-to-image | Yes | Same endpoint with `mode: image-to-image` |
| Inpainting | Yes | `POST /v2beta/stable-image/edit/inpaint` |
| Upscaling | Yes | Separate upscale endpoint available |
| Analysis | No | Read the image file directly instead |
| Negative prompts | Yes | `negative_prompt` field |

### Models
- `sd3.5-large` — Stable Diffusion 3.5 Large (default)

### Notes
- All requests use multipart/form-data
- Image-to-image uses `strength` parameter (0.0-1.0) to control deviation
- Returns base64-encoded image in JSON response

---

## Provider: replicate (Replicate API)

### Overview
Replicate's model hosting platform. Uses Flux models from Black Forest Labs for image generation and editing.

### Authentication
```bash
export REPLICATE_API_TOKEN="r8_..."
```

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| Text-to-image | Yes | Flux 1.1 Pro |
| Image-to-image | Yes | Flux Fill Pro (data URI input) |
| Inpainting | Yes | Flux Fill Pro with mask (data URI input) |
| Upscaling | No | Use a separate upscale model |
| Analysis | No | Read the image file directly instead |
| Aspect ratio | Yes | `aspect_ratio` parameter |

### Models
- `black-forest-labs/flux-1.1-pro` — Generation (default)
- `black-forest-labs/flux-fill-pro` — Editing and inpainting

### Notes
- Uses `Prefer: wait` header for synchronous predictions (no polling)
- Images are passed as `data:image/png;base64,...` data URIs
- Output is a URL that gets downloaded automatically
- Pay-per-prediction pricing — uses existing Replicate subscription

---

## Provider Selection Logic

```
Priority order (first available wins):
1. cstudio — best developer experience (CLI binary)
2. vertex-curl — no extra binary needed (gcloud + curl)
3. openai — OPENAI_API_KEY set
4. stability — STABILITY_API_KEY set
5. replicate — REPLICATE_API_TOKEN set

If none available:
  → Review sub-skill still works (reads image files directly)
  → Create and alter sub-skills are unavailable
```

## Adding New Providers

To add a new provider, implement the `BaseProvider` class in `scripts/provider.py`:
1. Subclass `BaseProvider` with `detect()`, `generate()`, `edit()`, `inpaint()`
2. Register in the `PROVIDERS` dict and `PRIORITY_ORDER` list
3. Update this reference document
