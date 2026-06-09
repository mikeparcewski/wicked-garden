---
description: Generate actionable recommendations from customer feedback insights
argument-hint: "[--priority high|medium|low|critical] [--feature X] [--format brief|detailed]"
next-step: null
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:synthesize

Translate customer-feedback analysis into prioritized, evidence-backed action items.
Pipeline step 3 of 3: listen -> analyze -> **synthesize**.

## Run it inline (no dispatch)

1. Locate analysis input:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/analysis/"
   ```
   If empty, tell the user to run `/wicked-garden:product:analyze` first and stop.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/synthesize.md")` — the impact x frequency x trend x effort x risk-of-inaction prioritization model, per-recommendation fields, and output format.
3. Apply the rubric directly, honoring `--priority`/`--feature`/`--format`. Emit prioritized recommendations, quick wins, strategic initiatives, and metrics to track.
