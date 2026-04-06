---
description: Guide for migrating in-flight projects to strict gate enforcement
argument-hint: "[project-name]"
---

# /wicked-garden:crew:migrate-gates

Migration reference for moving in-flight projects to strict gate enforcement.

## For In-Flight Projects

Projects started before strict enforcement may fail Tier 1 gate checks due to missing artifacts. To complete the current phase without disruption:

1. Set `CREW_GATE_ENFORCEMENT=legacy` before running any crew command
2. Complete the current phase normally — all gate checks are bypassed
3. At the next phase boundary, unset the env var — new phases get strict enforcement by default

```bash
CREW_GATE_ENFORCEMENT=legacy /wicked-garden:crew:approve design
```

## Retroactive Artifact Creation

If strict enforcement is required mid-flight, create the missing artifacts manually:

**`specialist-engagement.json`** — list specialists engaged during the phase:
```json
{
  "phase": "design",
  "engaged": ["engineering", "qe"],
  "engagement_type": "sequential"
}
```
Place in `phases/design/specialist-engagement.json`.

**`reviewer-report.md`** — run the gate command to generate a report for review:
```
/wicked-garden:crew:gate design
```
This creates `phases/design/reviewer-report.md` with gate analysis results.

**`case_count` frontmatter in `test-plan.md`** — add to the YAML block at the top of the file:
```yaml
---
case_count: 12
coverage: unit,integration,e2e
---
```

## New Projects

Strict enforcement is the default — no action needed. `phase_manager.py` reads `CREW_GATE_ENFORCEMENT` at runtime. Only set it to `"legacy"` if you have a specific reason to bypass enforcement.

## Override Reference

| Override | Usage | Notes |
|----------|-------|-------|
| `CREW_GATE_ENFORCEMENT=legacy` | Env var before any crew command | Bypasses all Tier 1 checks |
| `--override-reviewer` | On `crew:approve` | Skips independent reviewer check; audit logged |
| `--override-deliverables --reason "..."` | On `crew:approve` | Skips deliverable checks; reason required |
