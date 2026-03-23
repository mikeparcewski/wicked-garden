#!/bin/bash
# edit.sh - Delegates to provider.py for multi-provider image editing
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"

IMAGE="$1"
PROMPT="$2"
OUT_FILE="${3:-./output_edit.png}"

if [ -z "$IMAGE" ] || [ -z "$PROMPT" ]; then
  echo "Usage: $0 <source_image> <prompt> [output_file]"
  exit 1
fi

python3 "${PLUGIN_ROOT}/skills/imagery/scripts/provider.py" edit --image "$IMAGE" --prompt "$PROMPT" --output "$OUT_FILE"
