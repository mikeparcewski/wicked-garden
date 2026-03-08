#!/bin/bash
# analyze.sh - Image analysis uses Claude's native Read tool (multimodal vision)
#
# This script is intentionally minimal. The imagery/review sub-skill
# performs image analysis by reading image files directly via Claude's
# Read tool — no external CLI or API is needed.
#
# For programmatic analysis via a provider, use:
#   cstudio analyze image --image <path>

IMAGE=$1

if [ -z "$IMAGE" ]; then
  echo "Usage: $0 <image_path>"
  echo ""
  echo "Image analysis is performed by Claude's native Read tool."
  echo "Use the imagery/review skill for multi-dimensional visual analysis."
  exit 1
fi

echo "Image analysis for '$IMAGE' should be performed using Claude's Read tool."
echo "See: skills/imagery/review/SKILL.md"
exit 0
