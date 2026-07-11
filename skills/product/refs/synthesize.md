# Feedback Synthesis Rubric (synthesize — pipeline 3/3)

Apply this inline. Translate feedback analysis into prioritized, evidence-backed
action items. Pipeline: listen -> analyze -> **synthesize**. Run after
`/wicked-garden-product analyze` has produced themes/sentiment/trends.
(Shared customer-voice rubric: `refs/analyze.md`.)

## 1. Locate analysis input

```bash
PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
ls "${PRODUCT_ROOT}/voice/analysis/"
```
If empty, tell the user to run `/wicked-garden-product analyze` first and stop.

## Prioritization model

Rank each recommendation by **impact x frequency x trend x effort x
risk-of-inaction**. Levels: critical / high / medium / low.

- **Critical** — blocking customer work, churn risk
- **High** — significant friction, competitive gap
- **Medium** — enhancement, efficiency gain
- **Low** — nice-to-have, edge case

## For each recommendation

Action · evidence (verbatim quotes + numbers + affected segment) · expected outcome
· risk of inaction · effort (S/M/L/XL) · dependencies.

Also identify: **quick wins** (low effort / high impact), **strategic initiatives**
(high effort / high impact), and **metrics to track**.

Apply filters: `--priority`, `--feature` scope, `--format brief|detailed`.

## Output

```markdown
## Recommendations from Customer Voice

### Priority Recommendations
| Priority | Recommendation | Customer Impact | Evidence | Effort |
|----------|----------------|-----------------|----------|--------|
| Critical | {action} | {impact} | N={count}, Q="{quote}" | {S/M/L/XL} |

### Quick Wins
- {low-effort high-impact action}

### Strategic Initiatives
- {high-effort high-impact action} — dependencies: …

### Metrics to Track
- {metric} — current {…} -> target {…}
```
