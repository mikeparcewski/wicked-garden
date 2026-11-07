# Report mode: the packet

Report mode answers a question or reads documents for the person and changes nothing. Its record is one
JSON object, the **report packet**. `synthesize` puts it in its output as one json block. The fidelity check
reads it, re-checks it at the sources, and passes or fails it. Nothing is written to a repository.

Report mode does not use learn's ledger (refs/claims.md). Its claim ids are local to the report (C1..Cn),
and its sources may be documents, repository files and source calls as well as web pages.

## The packet

```json
{"schema": 1,
 "lens": "due-diligence",
 "question": "Is the vendor's SOW complete enough to sign?",
 "documents": ["sow.pdf", "msa.md"],
 "web": {"state": "not-picked", "reason": "this job did not pick the web"},
 "sources": [
   {"id": "S1", "file": "sow.pdf", "page": 4, "quote": "Acceptance is deemed after 10 business days."},
   {"id": "S2", "file": "msa.md", "quote": "Liability is capped at fees paid in the prior 12 months."},
   {"id": "S3", "source": "support-pg", "tool": "query",
    "args": {"sql": "select count(*) from tickets where vendor = 'acme' and opened >= '2026-07-01'"},
    "observed_at": "2026-11-06T21:41:03Z"}
 ],
 "claims": [
   {"id": "C1", "text": "The SOW deems acceptance after 10 business days.", "sources": ["S1"]},
   {"id": "C2", "text": "Liability is capped at the fees paid in the prior 12 months.", "sources": ["S2"]},
   {"id": "C3", "text": "Support logged 14 tickets against this vendor since 2026-07-01.", "sources": ["S3"]}
 ],
 "stopped": null,
 "report": "## What holds\nAcceptance is deemed after 10 business days [C1]. Liability is capped at a year of fees [C2].\n\n## What is a risk\n14 tickets since July [C3].\n\n## Sources\n- S1 sow.pdf, page 4\n- S2 msa.md\n- S3 support-pg, query"}
```

A web source looks like `{"id": "S4", "url": "https://example.org/terms", "title": "Example terms",
"observed_at": "2026-11-06T21:40:12Z"}`, and needs `web.state` `used`.

| Field | Rule |
|---|---|
| `schema` | `1`. |
| `lens` | The brief's `Lens:` line: `research`, `competitive`, `due-diligence`, `analyze`, `critique` or `estimate`. No line means `research`. |
| `question` | The question or the task, in one line, from the brief. |
| `brief` | Only when the brief itself carries text the report rests on (a pasted claim to critique, an estimate's scope): that text, verbatim. |
| `documents` | Every staged file you read, relative to the documents folder (`records/` in a crew run). `[]` when there are none. |
| `web` | `{"state": "used"}`, or `{"state": "not-picked"}` / `{"state": "unavailable"}` with a `reason`. The report says the reason too. |
| `sources` | The source log: one record per thing you read, ids `S1..Sn`, each exactly one of the four kinds below. |
| `claims` | `C1..Cn`: one atomic, checkable statement each, with `sources`, the ids it rests on (at least one). |
| `stopped` | `null`, or the reason the job could not report. A stopped packet has no claims and an empty `report`: the reason is the whole output. |
| `report` | The markdown the person reads. Every factual sentence ends with its claim ids, `[C1]` or `[C1, C3]`. Every claim is cited. It ends with `## Sources`. |

## The four source records

| Kind | Record | Rules |
|---|---|---|
| web | `{id, url, title, observed_at}` | A page you fetched. `observed_at` is the fetch time in UTC: in a crew run it is the web source's `fetched_at`, copied, never typed, and `gather` pastes that fetch result's receipt (its URL and `fetched_at`) verbatim in its output, so the fidelity check can match the record to it. A search result is a lead, not a source: fetch the page before you cite it. Never cite the `web` source as a tool. |
| file | `{id, file, page?, quote}` | A staged document. `quote` is the exact words the claim rests on, copied, at least 8 characters. `page` is the pdf page. A quote from a pdf's text derivative (`<name>.txt`) may name that derivative as `file`. `file: "brief"` quotes the packet's `brief`. |
| code | `{id, path, line?, quote}` | A file in the repository in scope, `path` relative to its root, with the exact words quoted. With `line`, the quote must be on that line and may be short; without it, at least 8 characters. |
| tool | `{id, source, tool, args, observed_at}` | A call to one of the job's picked sources (a database, a tracker). `args` is the read-only query or arguments, verbatim (`{}` for a call that takes none), so the call can be made again. `observed_at` is the call time. Put what the call returned in the claim, not in the record. |

Times are ISO-8601 with seconds and a zone (`2026-11-06T21:41:03Z`).

**URLs.** Write every URL, in the report and in claims, in one of two forms: `<url>`, or a link
`[title](url)`. A URL containing parentheses goes in angle brackets: `<url>` or `[title](<url>)`. A
reference definition is `[ref]: <url>`. Write each URL as the reader opens it: no backslash escapes and no
character references (`&amp;`, `&#58;`). Anything else is refused (`url-form`): a bare URL, a link with a
title, a relative or `//` link, another scheme, a `www.` address, raw HTML links. The floor reads URLs
exactly and never trims or decodes. A URL appears only when it is exactly the `url` of a web source in the log (a fragment may
differ; a trailing slash may not). A file source names only a file among `documents`, or `brief`.

## The floor

```
wicked-garden run scripts/learn/report_check.py check --packet <packet.json> --records <documents folder> [--repo <repository>]
```

Pass both folders as absolute paths: `gather`'s preflight prints the documents folder's absolute path
(`records`), and each later step uses that path. Leave out `--records` only when no documents were staged.
It exits 0 with no findings, 1 with findings, and 2 when the packet cannot be read. Its findings include an
unsourced claim, a claim citing a source the log does not hold, a URL the log does not hold or not
written as `<url>` or `[title](url)`, a file not among
the staged documents, a quote not in its file's text, a web source when the web was not available, a stop
while something is readable (a non-empty staged document, a source in the log, text in the brief), and a documents-required lens that reports with no documents. It lists the files
whose text it could not read (an image, a pdf with no text derivative, an empty file) under `unchecked`, with
the reason, for the fidelity check to read in the original.

One finding has a narrow exception: `quote-not-found-in-pdf-text` means the quote is not in a pdf's
extracted text, which may have lost it. Read the pdf page. If the quote is there, say so in your output as an
extraction loss for that source id; the fidelity check reads the page again. Every other finding is fixed.

Manual alternative (no launcher, or no Python): walk the same list by hand. For each claim, check that its
ids are in `sources`. For each URL in the report, check that it is in `sources`. For each quote, find it in
its file. Say in your output that you checked by hand.
