---
description: Address mechanical CONDITIONAL findings via specialist dispatch (no verdict mutation, #717)
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:crew:resolve

Walks the active phase's `conditions-manifest.json`, classifies each
unverified finding, and surfaces a one-action handoff for the
`mechanical` ones. The gate verdict on `gate-result.json` is **never**
mutated by this command — the honest CONDITIONAL signal is preserved.
Phase advancement still requires `crew:approve`.

This is the reframed implementation of [issue #717][issue-717]
(classify-don't-retry path). It deliberately omits any verdict-flipping
behaviour. See the [reframe comment][reframe-comment] for rationale.

[issue-717]: https://github.com/mikeparcewski/wicked-garden/issues/717
[reframe-comment]: https://github.com/mikeparcewski/wicked-garden/issues/717#issuecomment-4363961150

## When to use

- A gate emitted `CONDITIONAL` and the manifest has multiple findings
- You want to know which findings are mechanical (typos, AC numbering,
  missing evidence references) vs which need your judgment
- You want to dispatch the originating specialist to fix the mechanical
  ones without flipping the verdict yourself

## When NOT to use

- For phase advancement — use `crew:approve` (the verdict stays
  CONDITIONAL until you do)
- For escalation findings (security, council-level disagreement) — they
  are deliberately refused here; surface to `crew:swarm` or council mode

## Usage

```bash
# Preview classification + diff. No files written, no events emitted.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resolve.py" \
  ${project_dir} ${phase}

# Accept all mechanical clusters. Writes resolution sidecars + emits
# wicked.gate.condition.resolved per cluster. NO --yes-all shortcut by
# design — each invocation requires explicit --accept.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resolve.py" \
  ${project_dir} ${phase} --accept

# Resolve a single cluster by condition id.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resolve.py" \
  ${project_dir} ${phase} --accept --cluster-id ${condition_id}
```

## What gets written

- **`phases/{phase}/conditions-manifest.{condition_id}.resolution.json`**
  — one sidecar per accepted resolution. Records `applied_rule`,
  `resolution_ref`, `note`, `written_at`, `verdict_unchanged: true`.
- Bus event **`wicked.gate.condition.resolved`** (chain
  `{project_id}.{phase}`) — one per accepted resolution.

## What does NOT get written

- `gate-result.json` — never touched
- `conditions-manifest.json` — verified flag stays as-is until
  `crew:approve` runs
- Phase status / amendments — unchanged

## Classification rules

Defaults live at `.claude-plugin/finding-classification.json`. Project
overrides at `.wicked-garden/finding-classification.json` (ids replace
defaults; new ids append).

| classification | examples                                                | resolve behaviour |
|----------------|---------------------------------------------------------|-------------------|
| `mechanical`   | AC numbering, missing evidence ref, simple spec gap     | dispatch + sidecar on `--accept` |
| `judgment`     | unknown findings, scope ambiguity                       | surfaced; user must address |
| `escalation`   | security finding, reviewer disagreement >0.3 score gap  | refused with pointer to swarm/council |

Unknown findings default to `judgment` — never auto-classified as
`mechanical`. The classifier is conservative on purpose.

## Telemetry

Per-rule acceptance + rejection rates land in delivery process-health
under `crew.condition.resolution`. Rules with >95% acceptance over 50
invocations trigger an SPC flag (rule may be over-broad). Rules with
>20% rejection over 20 invocations trigger an SPC flag (rule may be
misclassifying).

## Example

```bash
$ /wicked-garden:crew:resolve myproj design

# crew:resolve preview — phase=design
mechanical: 2
  - cond-ac-3 [ac-numbering] AC-3 not found in clarify/acceptance-criteria.json
  - cond-ev-7 [missing-evidence-ref] evidence file not found: phases/design/diagram.png
judgment:   1
  - cond-scope-1 [no-rule-matched] outcome statement could be interpreted two ways
escalation: 0

# user reviews, decides AC-3 fix is right and the diagram path is right
$ /wicked-garden:crew:resolve myproj design --accept

# crew:resolve preview — phase=design
mechanical: 2
  ...
resolved:   2
  - cond-ac-3 → .../conditions-manifest.cond-ac-3.resolution.json (emit=emitted)
  - cond-ev-7 → .../conditions-manifest.cond-ev-7.resolution.json (emit=emitted)

# verdict on gate-result.json is unchanged. Phase still requires:
$ /wicked-garden:crew:approve myproj --phase design
```
