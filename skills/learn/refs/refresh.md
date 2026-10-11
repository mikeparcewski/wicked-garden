# Refresh: re-research, propose only changes

A refresh is a `learn` run on a topic that already exists. The scope step names it, because
`.wicked/knowledge/<slug>/` is already in the tree. A scheduled refresh is launched by wicked-crew's
learn schedule, and its intent says so. A refresh changes only what the evidence changes.

## Synthesize: the diff

Classify every **active** claim, and then every new candidate, into exactly one bucket:

| Bucket | When | What the author does |
|---|---|---|
| confirmed | A fresh fetch of a source still supports the claim. | Set `last_verified` to now. The text and id stay the same. |
| superseded | A newer source states it differently, for example a new version or a changed default. | Add the new claim, with its own id and sources. On the old claim, set `status: superseded`, `superseded_by`, `reason` and `evidence`. |
| contradicted | A credible source says the claim is wrong. | Set `status: contradicted`, with `reason` and `evidence`. If a corrected claim exists, add it. |
| retired | The claim no longer applies: the feature was removed, or the event is over and no longer matters. Also use this when the claim is **unverifiable**: no source supports it now, and its `last_verified` is more than two refresh intervals old. | Set `status: retired`, with `reason` (`unverifiable` is a valid reason). For `evidence`, cite the fetch that failed or the page that shows the change. |
| new | A candidate that matches no existing claim. | Add it. |

Put the diff in your output as a table with one row per claim id, then counts per bucket. The
walkthrough teaches the diff first: "what changed since <refreshed_at>".

## Author: the pull request is the proposal

- Never delete a line from `claims.jsonl`. A removal is a status change with its reason and evidence.
- Remove each non-active claim from README.md and from every skill that cites it. Rewrite the
  sentence around the replacing claim, if there is one.
- Set `refreshed_at` on topic.json and add this run's id to `run_ids`.
- A refresh with no material change still bumps `last_verified` on each claim it re-saw. That makes
  the pull request a small "verified, nothing changed" record. The operator may decline it at the
  deliver gate.

## Review: the evaluator checks the removals

- Re-fetch the evidence for every status change.
- A retirement that is not supported by evidence is a FAIL.
- So is a contradiction with no credible source, or a claim silently dropped from the ledger.

## Afterwards

- **Merging is the approval.** Once the pull request is merged, `wicked-garden run scripts/learn/index.py --repo <checkout>`,
  run by the operator or by the crew schedule tick, replaces the topic's estate scope.
- **Recall follows the merged ledger.** A claim that is no longer active leaves knowledge recall.
- **History stays in the repository.**
