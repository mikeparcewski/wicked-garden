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
| Analysis | No | Use Claude Read tool instead |
| Batch generation | Yes | `sampleCount` parameter |

---

## Provider Selection Logic

```
1. Check for cstudio binary (PATH or CSTUDIO_PATH)
   → If found: use cstudio (best developer experience)
2. Check for gcloud + GOOGLE_CLOUD_PROJECT
   → If found: use vertex-curl (no extra binary needed)
3. Neither available:
   → Review sub-skill still works (uses Claude Read tool)
   → Create and alter sub-skills are unavailable
```

## Adding New Providers

To add a new provider, implement the provider interface in `scripts/provider.py`:
1. Add a detection function (`detect_{provider}`)
2. Add generation/edit/inpaint wrappers
3. Register in the provider registry
4. Update this reference document
