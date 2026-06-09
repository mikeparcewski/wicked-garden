# Customer Feedback Analysis Rubric (analyze — pipeline 2/3)

Apply this inline. Analyze aggregated feedback for themes, sentiment, and trends.
Pipeline: listen -> **analyze** -> synthesize. This is the shared customer-voice
signal-analysis rubric (also referenced by `listen`/`synthesize`).

## 1. Load input

```bash
PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
ls "${PRODUCT_ROOT}/voice/feedback/"
```
If no data, tell the user to run `/wicked-garden:product:listen` first and stop.

## Sentiment

Classes: Positive, Negative, Neutral, Mixed. Intensity: STRONG / MODERATE / MILD.
Keyword anchors — strong+: love, amazing, perfect; moderate+: good, helpful, useful;
strong-: hate, terrible, broken, unusable; moderate-: frustrating, confusing, slow.

## Theme extraction

Cluster into themes — Product (features, bugs, performance, UX) · Experience
(onboarding, support, docs) · Business (pricing, packaging, competition). Rank by
**frequency x impact**. Keep to the top 3-5 (more is overload).

## Trend detection

Emerging (new) · Growing (increasing) · Stable · Declining · Resolved (was a
problem, now fixed). Use time-series + growth direction.

## Segment analysis

Enterprise vs SMB · new vs power users · industry · geography. Note who is hurting most.

## Priority signals

What indicates urgency — churn risk, blockers, competitive gaps.

## Techniques

```bash
# keyword clustering
grep -i "frustrat\|annoying\|broken" "${PRODUCT_ROOT}/voice/feedback"/* | grep -oE '\w{4,}' | sort | uniq -c | sort -rn | head -20
# time-series
ls "${PRODUCT_ROOT}/voice/feedback" | grep -oE '[0-9]{4}-[0-9]{2}' | sort | uniq -c
```

## Rules

Objective + data-driven; cite sample sizes (N=X); distinguish correlation from
causation; acknowledge data limits; confidence HIGH/MED/LOW; include representative
verbatim quotes; cite sources (ticket IDs, survey dates); distinguish frequency from severity.

## Output

```markdown
## Feedback Analysis Report
### Summary — Period {…} · Items {count} · Overall Sentiment {score} ({trend})

### Top Themes
| Theme | Frequency | Sentiment | Trend |
|-------|-----------|-----------|-------|

### Theme Deep Dive
#### {Theme} — {count} ({%}) · Sentiment {…} · Trend {…}
> "{quote 1}" / "{quote 2}"
Key drivers: … · Recommendation: …

### Sentiment Drivers — positive: … / negative: …
### Trends — | Metric | This | Last | Change |
### Segment Insights — | Segment | Sentiment | Top Theme | Notable |
### Recommendations — {priority}: {action} (evidence, impact)

### Next Steps
Run `/wicked-garden:product:synthesize` to generate prioritized recommendations.
```
