---
description: Aggregate customer feedback from available sources
argument-hint: "[--capability type] [--days N] [--tags x,y]"
next-step: "product:analyze"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:listen

Aggregate customer feedback from discovered sources (support, surveys, social,
direct). Pipeline step 1 of 3: **listen -> analyze -> synthesize**.

## Run it inline (no dispatch)

1. Discover sources:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/feedback/" 2>/dev/null
   find . -name "*feedback*" -o -name "*survey*" -o -name "*tickets*" 2>/dev/null | head -10
   gh issue list --label "customer-reported" 2>/dev/null | head -5
   ```
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/listen.md")` — normalization, tagging, prioritization, storage, and output format.
3. Apply the rubric directly: extract + normalize + tag + prioritize feedback, honoring `--days`/`--since`/`--tags`/`--capability`/`--limit`. Emit the listening report, then point to `/wicked-garden:product:analyze`.
