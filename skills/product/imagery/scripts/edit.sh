#!/bin/bash
# edit.sh - Delegates to provider.py for multi-provider image editing.
# provider.py is stdlib-only and lives next to this script, so the skill's own
# base directory is all that is needed — no plugin root, works on every install
# layout (Claude Code plugin, flat skills-only copies, crew snapshots).
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

IMAGE="$1"
PROMPT="$2"
OUT_FILE="${3:-./output_edit.png}"

if [ -z "$IMAGE" ] || [ -z "$PROMPT" ]; then
  echo "Usage: $0 <source_image> <prompt> [output_file]"
  exit 1
fi

python3 "${SKILL_DIR}/scripts/provider.py" edit --image "$IMAGE" --prompt "$PROMPT" --output "$OUT_FILE"
