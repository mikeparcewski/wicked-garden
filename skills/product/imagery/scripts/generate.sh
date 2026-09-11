#!/bin/bash
# generate.sh - Delegates to provider.py for multi-provider image generation.
# provider.py is stdlib-only and lives next to this script, so the skill's own
# base directory is all that is needed — no plugin root, works on every install
# layout (Claude Code plugin, flat skills-only copies, crew snapshots).
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

PROMPT="$1"
OUT_FILE="${2:-./output.png}"

if [ -z "$PROMPT" ]; then
  echo "Usage: $0 <prompt> [output_file]"
  exit 1
fi

python3 "${SKILL_DIR}/scripts/provider.py" generate --prompt "$PROMPT" --output "$OUT_FILE"
