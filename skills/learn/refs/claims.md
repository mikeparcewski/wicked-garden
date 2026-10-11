# The claims ledger

`claims.jsonl` holds one JSON object per line. The ledger is the record. README.md and the skills
are views over it, and both cite claims by id.

## The record

```json
{"id":"c-1f3a9b2e",
 "text":"In WAL mode, readers do not block writers and a writer does not block readers.",
 "sources":[{"url":"https://sqlite.org/wal.html","title":"Write-Ahead Logging","published_at":null,"observed_at":"2026-10-11T04:10:00Z"}],
 "status":"active",
 "first_seen":"2026-10-11T04:10:00Z",
 "last_verified":"2026-10-11T04:10:00Z"}
```

| Field | Rule |
|---|---|
| `id` | `c-` followed by the first 8 hex characters of the sha256 of the claim text, lowercased with whitespace collapsed, taken at first sight. The id never changes. A reworded claim is a new claim, and the old one becomes `superseded`. Compute it with `wicked-garden run scripts/learn/check.py --claim-id "<text>"`. |
| `text` | One atomic, checkable statement, at least 40 characters. An `event` topic's claim states its date. |
| `sources` | At least one `{url, title, published_at, observed_at}`. `url` is `http(s)`. `observed_at` is the UTC time you fetched it, in ISO-8601. |
| `status` | `active`, `superseded`, `contradicted` or `retired`. |
| `reason`, `evidence` | Required when the status is not `active`. `evidence` is `[{url, observed_at}]`, the source that shows the change. |
| `superseded_by` | Required for `superseded`: the id of the replacing claim. |
| `first_seen`, `last_verified` | `last_verified` moves forward each time a refresh re-sees a source that still supports the claim. |

## README.md

- One short section per question from scope.
- Every factual sentence ends with its claim ids: `… readers never block writers [c-1f3a9b2e].`
- Every active claim is cited at least once.
- The README cites no claim that is not active.
- `## Sources` lists each source once: URL, title and observed date.
- `## Operator notes` holds what the operator told you in the walkthrough. Each note is labelled
  "operator, <date>". These notes are memories, not claims, so they carry no claim id.

## A skill from the ledger

```markdown
---
name: sqlite-wal-setup
description: |
  Configure SQLite write-ahead logging for a service with many readers and one writer:
  enable WAL, set the checkpoint policy, and know what WAL cannot do on a network filesystem.
metadata:
  learn-topic: sqlite-wal
---

# SQLite WAL setup
1. Run `PRAGMA journal_mode=WAL;` once per database file. The mode persists [c-5b0e77a1].
…

## Sources
c-5b0e77a1, c-1f3a9b2e (see .wicked/knowledge/sqlite-wal/claims.jsonl)
```

Then run `wicked-garden run scripts/learn/check.py --repo .`. If it exits 0, there are no findings.
If it exits 1, each finding names its file, its rule and the fix. Exit 2 means there is no topic.
