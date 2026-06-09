---
description: GitHub Actions workflow generation and optimization
argument-hint: "<generate|optimize|troubleshoot> [workflow file]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:actions

Generate, optimize, and troubleshoot GitHub Actions workflows.

## Run it inline (no dispatch)

1. Parse `<mode>` from `$ARGUMENTS`: `generate`, `optimize`, or `troubleshoot`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/actions/refs/actions.md")` — workflow rubric,
   security/performance checklists, stack detection, and output format.
3. Apply the rubric directly:
   - **generate**: detect project stack (`ls package.json pyproject.toml ...`), produce complete workflow YAML.
   - **optimize**: read the target workflow file, apply the optimization checklist, return annotated diff.
   - **troubleshoot**: run `gh run list --status failure --limit 1`, fetch logs, diagnose root cause inline.
