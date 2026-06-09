---
description: Generate multi-perspective delivery reports from project data
argument-hint: "<file> [--personas <list>] [--all] [--output <dir>]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:delivery:report

Generate multi-perspective stakeholder reports from project data.

## Arguments

- `file`: Input file (outcome.md, project brief, or crew phase data)
- `--personas <list>`: Comma-separated perspectives (default: all three default personas)
  - Options: `delivery`, `engineering`, `product`, `qe`, `architecture`, `devsecops`
- `--all`: Include all six perspectives
- `--output <dir>`: Write report to directory (default: stdout)

## Run it inline (no dispatch)

1. Parse `file`, `--personas`, `--all`, and `--output` from arguments. If no file, collect context from the active crew project via `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" status`.
2. Read the input file or active project context.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/delivery/refs/report.md")` — six persona lenses, base metrics, persona section template, cross-synthesis, executive summary, and output format rules.
4. Apply the rubric directly, filter to requested personas, and emit the stakeholder report.
