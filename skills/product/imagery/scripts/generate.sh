#!/bin/bash
# generate.sh - Delegates to provider.py for multi-provider image generation
# skills/product/imagery/scripts/ -> plugin root is four levels up.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../../../.." && pwd)}"

PROMPT="$1"
OUT_FILE="${2:-./output.png}"

if [ -z "$PROMPT" ]; then
  echo "Usage: $0 <prompt> [output_file]"
  exit 1
fi

python3 "${PLUGIN_ROOT}/skills/product/imagery/scripts/provider.py" generate --prompt "$PROMPT" --output "$OUT_FILE"
