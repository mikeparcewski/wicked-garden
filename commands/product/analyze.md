---
description: Analyze customer feedback for themes, sentiment, and trends
argument-hint: "[--theme X] [--sentiment pos|neg] [--trend period]"
next-step: "product:synthesize"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:analyze

Analyze aggregated customer feedback for themes, sentiment patterns, and trends.
Pipeline step 2 of 3: listen -> **analyze** -> synthesize.

## Run it inline (no dispatch)

1. Load feedback data:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/feedback/"
   ```
   If empty, tell the user to run `/wicked-garden:product:listen` first and stop.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/analyze.md")` — sentiment classes, theme extraction, trend detection, segment analysis, techniques, rules, and output format.
3. Apply the rubric directly, honoring `--theme`/`--sentiment`/`--trend`/`--segment`. Emit the analysis report, then point to `/wicked-garden:product:synthesize`.
