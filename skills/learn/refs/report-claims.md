# Report mode: the packet

Report mode answers a question or reads documents for the person and changes nothing. Its record is one
JSON object, the **report packet**. `synthesize` puts it in its output as one json block. The fidelity check
reads it, re-checks it at the sources, and passes or fails it. Nothing is written to a repository.

Report mode does not use learn's ledger (refs/claims.md). Its claim ids are local to the report (C1..Cn),
and its sources may be documents and tools as well as web pages.

## The packet

```json
{"schema": 1,
 "lens": "due-diligence",
 "question": "Is the vendor's SOW complete enough to sign?",
 "documents": ["sow.pdf", "sow.txt", "msa.md"],
 "web": {"state": "not-picked", "reason": "this job did not pick the web"},
 "sources": [
   {"id": "S1", "file": "sow.pdf", "page": 4, "quote": "Acceptance is deemed after 10 business days."},
   {"id": "S2", "file": "msa.md", "quote": "Liability is capped at fees paid in the prior 12 months."},
   {"id": "S3", "source": "support-pg", "tool": "query", "observed_at": "2026-11-06T21:41:03Z"}
 ],
 "claims": [
   {"id": "C1", "text": "The SOW deems acceptance after 10 business days, with no test plan named.", "sources": ["S1"]},
   {"id": "C2", "text": "Liability is capped at the fees paid in the prior 12 months.", "sources": ["S2"]},
   {"id": "C3", "text": "Support logged 14 open tickets against this vendor last quarter.", "sources": ["S3"]}
 ],
 "stopped": null,
 "report": "## What holds\nAcceptance is deemed after 10 business days [C1]. Liability is capped at a year of fees [C2].\n\n## What is a risk\n14 open tickets last quarter [C3].\n\n## Sources\n- S1 sow.pdf, page 4\n- S2 msa.md\n- S3 support-pg, query"}
```

A web source looks like `{"id": "S4", "url": "https://example.org/terms", "title": "Example terms",
"observed_at": "2026-11-06T21:40:12Z"}`, and needs `web.state` `used`.

| Field | Rule |
|---|---|
| `schema` | `1`. |
| `lens` | The brief's `Lens:` line: `research`, `competitive`, `due-diligence`, `analyze`, `critique` or `estimate`. No line means `research`. |
| `question` | The question or the task, in one line, from the brief. |
| `brief` | Only when the brief itself carries the text under review (a pasted claim to critique): that text, verbatim. |
| `documents` | Every staged file you read, relative to the documents folder (`records/` in a crew run). `[]` when there are none. |
| `web` | `{"state": "used"}`, or `{"state": "not-picked"}` / `{"state": "unavailable"}` with a `reason`. The report says the reason too. |
| `sources` | The source log: one record per thing you read, ids `S1..Sn`, each exactly one of the three kinds below. |
| `claims` | `C1..Cn`: one atomic, checkable statement each, with `sources`, the ids it rests on (at least one). |
| `stopped` | `null`, or the reason the job could not report (then `claims` is empty). |
| `report` | The markdown the person reads. Every factual sentence ends with its claim ids, `[C1]` or `[C1, C3]`. Every claim is cited. It ends with `## Sources`. |

## The three source records

| Kind | Record | Rules |
|---|---|---|
| web | `{id, url, title, observed_at}` | A page you fetched. `observed_at` is the fetch time in UTC: in a crew run it is the web source's `fetched_at`, copied, never typed. A search result is a lead, not a source: fetch the page before you cite it. |
| file | `{id, file, page?, quote}` | A staged document. `quote` is the exact words the claim rests on, copied. `page` is the pdf page. A quote from a pdf's text derivative (`<name>.txt`) may name that derivative as `file`. |
| tool | `{id, source, tool, observed_at}` | A call to one of the job's picked sources (a database, a tracker). `observed_at` is the call time. Put what the call returned in the claim, not in the record. |

A URL appears in the report, or in a claim, only when it is the `url` of a web source in the log. A file
source names only a file among `documents`, or `brief` for text pasted into the brief (its quote must be in
`brief`).

## The floor

```
wicked-garden run scripts/learn/report_check.py check --packet <packet.json> --records <documents folder>
```

It exits 0 with no findings, 1 with findings, and 2 when the packet cannot be read. Its findings include
an unsourced claim, a claim citing a source the log does not hold, a URL the log does not hold, a file not
among the staged documents, a quote not in its file's text, a web source when the web was not available,
and a documents-required lens that reports with no documents. It lists the files whose text it could not
read (an image, a pdf with no text derivative) under `unchecked`, for the fidelity check to read.

Manual alternative (no launcher, or no Python): walk the same list by hand. For each claim, check that its
ids are in `sources`. For each URL in the report, check that it is in `sources`. For each quote, find it
in its file. Say in your output that you checked by hand.
