---
codebook: decision-report
version: 1
block: wicked-decisions
---
# Decision report

Read the operator's message together with your previous reply: the pair is the unit. A short go-ahead
approves what you proposed. End your reply with one block, nothing after it:

```wicked-decisions
{"items": [{"quote": "ship it, but skip the docs page", "decision_text": "Release the cache fix without the docs page.", "type": "confirmation", "codify": false, "ambiguous": false, "steering_type": "operations", "approves_proposal": true, "same_as": null}]}
```

One item per decision. A message with no decision gets `{"items": []}`.

- `quote`: the operator's words, copied exactly. Unmatched quotes are dropped.
- `decision_text`: the decision in one sentence. When the operator approves or picks from your proposal,
  write it from your approved proposal plus any amendment, never from the operator's short wording.
- `type`: `confirmation` (go-ahead, with or without an amendment) ·
  `choice` (picks one of options) · `rule` (holds from now on) ·
  `correction` (you got it wrong) · `scope` (defer, skip, bound) · `exception` (one-off). `none` is
  crew's label for no decision: never emit an item with it.
- `codify`: true only for a standing rule in the operator's own words that is durable, general and
  checkable. Approving a plan is not.
- `ambiguous`: true when you cannot tell.
- `steering_type`: `architecture` · `development` · `security` · `testing` · `operations` ·
  `compliance` · `design-ux`.
- `approves_proposal`: true when it approves or picks from your previous reply.
- `same_as`: the id of an in-force rule it restates (from the list you were given), else null.

Label only the operator's words, never a worker's or a tool's. Labels are suggestions: crew decides
what is remembered.
