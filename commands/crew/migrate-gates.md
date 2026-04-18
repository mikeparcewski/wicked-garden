---
description: Guide for migrating in-flight projects to strict gate enforcement
argument-hint: "[project-name]"
---

# /wicked-garden:crew:migrate-gates

Migration reference for moving in-flight projects to strict gate enforcement.

## v6.0 Breaking Change

The legacy gate-bypass env var was removed in v6.0 (D3 — clean break). There is no
env-var escape hatch in v6.0. Projects that relied on the legacy bypass must be upgraded
using `/wicked-garden:crew:adopt-legacy`.

## For In-Flight Beta Projects (beta.3 → 6.0)

If you have a project started on v6.0-beta.3 that fails gate checks due to missing
artifacts, use the adopt-legacy skill to inspect and upgrade it:

```bash
/wicked-garden:crew:adopt-legacy <project-dir>
```

This detects three legacy markers and offers to transform them:

1. Missing `phase_plan_mode` key in project state
2. Markdown `## Re-evaluation YYYY-MM-DD` addendum headers in `process-plan.md`
3. Legacy gate-bypass env-var references in project files

Run with `--dry-run` (default) to preview changes, then `--apply` to execute.

## Retroactive Artifact Creation

If gate checks fail because required artifacts are missing, create them manually:

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

Strict enforcement is the default — no action needed. v6.0 projects are always strict.

## Override Reference

| Override | Usage | Notes |
|----------|-------|-------|
| `--skip-reeval --reason "..."` | On `crew:approve` | Bypasses re-eval addendum check; reason required; logged to skip-reeval-log.json |
| `--override-reviewer` | On `crew:approve` | Skips independent reviewer check; audit logged |
| `--override-deliverables --reason "..."` | On `crew:approve` | Skips deliverable checks; reason required |
