---
codebook: inventory-report
version: 1
block: wicked-inventory
---
# Inventory report

When your step lists things a later step acts on (issues, PRs, files, endpoints, records), say
whether the list is complete. End your reply with one block per source, nothing after them:

```wicked-inventory
{"source": "gh issue list -R owner/repo --state all", "answered": "partial", "listed": 9, "expected": 10, "unread": ["issue #936: not in the API page"]}
```

- `source`: the command, API or path you listed from, exactly as you ran it.
- `answered`: `full` only when the source returned everything, `unread` is empty, and `listed`
  equals `expected` (or the source reports no total and you paged to the end). `partial` when
  some of it could not be read. `none` when the source failed.
- `listed`: how many you have.
- `expected`: the total the source reported, or `null` when it reports none.
- `unread`: what you could not read and why. Never leave out a failure.

A fallback (another tool, a web page, a cached copy) is a different source: name it in `source`
and say `partial` unless you checked it against the first one. crew reads the block and serves it
with the run, so a reviewer sees an incomplete list without reading your reply. A step that acts on
a list it was handed says so first when that list is not `full`.
