# Report mode: the fidelity check

The last step of a report run. You are the evaluator: you did not gather or synthesize this report, and you
re-check every claim at its source yourself. If you gathered or synthesized any of it, say so and give no
verdict line (wicked-crew already keeps those seats off this step; this is the second guard).

You change nothing: write no file in any repository and commit nothing. Scratch goes in your notes folder,
outside every repository.

## 1. Run the floor

Copy the packet (the json block in `synthesize`'s output) to `packet.json` in your notes folder, then run,
with the documents folder's absolute path from `gather`'s preflight:

```
wicked-garden run scripts/learn/report_check.py check --packet <notes folder>/packet.json --records <documents folder> [--repo <repository>]
```

Paste its JSON and its exit code. Leave out `--records` only when the job staged no documents. Every finding
fails the run, with one exception: a `quote-not-found-in-pdf-text` where you read the pdf page and the quote
is there (the text extraction lost it). Say so for that source id. With no launcher or no Python, walk
refs/report-claims.md's manual alternative and say you did.

The floor reads CommonMark links and images, reference definitions and GFM autolinks before
comparing destinations. Accepted citations use literal `<url>`, `[title](url)` or
`[title](<url>)`, or reference links with a `[ref]: <url>` definition without a title. A bare destination
containing parentheses must use angle brackets. Titles, whitespace or control characters (raw or
decoded), non-http(s) destinations, email addresses, `www.` addresses and bare URLs produce
`url-form`. A backslash or an `&...;` reference anywhere inside an accepted destination, including
its fragment, is refused: write the percent-encoded form that the reader opens.

Independent lexical sweeps refuse plain `http://`, `https://` and `ftp://` URLs anywhere in the text,
code spans and code blocks included. Outside code spans and code blocks they also refuse email
addresses (`name@domain.tld`, which includes a package pin such as `pkg@1.2.3`), encoded `@`
characters and raw HTML. Code renders as text, so `` `Vec<String>` ``, `` `<?xml ...?>` `` and
`` `npm i lodash@4.17.21` `` pass; in code only the link-bearing tags `a`, `img`, `iframe`, `link`,
`area` and `form` are refused (`a raw HTML link`). An indented line that continues a paragraph is
paragraph text, not code. Any character reference that decodes
to `@` (`&commat;`, `&#64;`, `&#x40;`, including leading zeros and either hex case) produces
`url-form` with reason `an encoded @`. The email and encoded-`@` sweeps exempt only parsed,
accepted HTTP(S) destination spans. Raw HTML means every `<!` or `<?` construct and every ASCII-named tag, even when the
floor cannot read its attributes. The sole exceptions are attribute-less `br`, `sup`, `sub`, `b`,
`i`, `em`, `strong`, `kbd`, `code`, `s`, `u`, `mark`, `small`, `details`, `summary`, `p`, `span` and
`div` tags, in exactly the forms `<x>`, `</x>`, `<x/>` and `<x />` (ASCII case-insensitive).
Scheme autolinks such as `<https://example.org/page>` are still parsed as links.

A fail-closed lexical backstop also checks the whole normalised text, including code, independently
of the parser's block boundaries. Every `](` must lead to an accepted inline link/image destination,
or produces `url-form` with reason `link syntax the floor did not read`. A `]:` is a candidate
reference definition when the last unescaped `[` within 1000 characters, with no unescaped `]`
after it, starts its line after only spaces,
tabs, quote markers or list markers followed by whitespace, or when a line ending separates that
`[` from the `]:`. It must lead to an accepted definition, or produces `a reference definition the
floor did not read`. Thus `see [C1]: the result` in prose is allowed, and a label with an escaped
bracket (`[a\[b]: /x`) is still a candidate. Both checks skip spaces/tabs,
at most one line ending, more spaces/tabs and an optional `<` before checking the destination start.
Every `<` followed by a URI scheme must also start an accepted angle destination (including inline
links and definitions), or produces `an autolink the floor did not read`. Each sweep is linear.

Code spans containing `www.unlogged.invalid` remain text, but even a code span containing
`[x](/evil)` is refused by the syntax backstop. Every accepted destination must match the source log exactly
apart from scheme/hostname case and the fragment; the fragment still undergoes the spelling and
character checks above.

## 2. Re-check every claim at its source

| Source kind | How you re-check it |
|---|---|
| web | First match the record to a fetch receipt `gather` pasted in its output: the same URL, and `observed_at` equal to that receipt's `fetched_at`. A web record with no matching receipt is a finding (a page the job may never have fetched). Then fetch the URL again through the same web source (in a crew run, the `fetch` tool of the job's `web` source; outside one, your own web tools) and read it. Does it say what the claim says? |
| file | Open the file at the page and find the quote. For `brief`, first check that the packet's `brief` is the text the brief really carries. Does the claim follow from the quote, with the same numbers, dates, scope and hedges? A file the floor listed as `unchecked` is read in the original. |
| code | Open the repository file at the line and find the quote. Does the claim follow from it? |
| tool | Call the same tool of the same source with the record's `args`, read-only. Does the result still support the claim? A tool record you cannot call again (no `args`, the source refuses) leaves its claim unverified. |

Each claim ends in one of three states:
- **holds**: the source says it, and the claim says no more than the source does;
- **does not hold**: the source does not say it, says something else, or the claim stretches it (a number,
  a date, "all" for "some", a cause where the source gives a correlation);
- **unverified**: you could not reach the source again (the fetch was refused or failed, the pdf cannot be
  read, the call cannot be repeated). Name what failed. An unverified claim is not a held claim.

## 3. Judge the rest

- Every factual sentence in the report cites a claim. An uncited factual sentence is a finding.
- No source is invented: every URL and file is in the log, every web record matches a fetch receipt, and
  the log matches what the job could read. Read the report as it renders: every link a reader could open
  (a reference link, an email or `www.` address, an HTML link included) is a logged web source, or it is a
  finding. A web source when the packet says the web was not available is a
  fabrication.
- When the web was not used, the report says why, in plain words.
- The lens's shape is there (refs/report-<lens>.md): for example, an estimate states every assumption,
  and its price is effort × rate. Recompute every derived number.
- A stopped packet states a true reason: check that the documents or sources it says are missing are
  really missing.

## 4. Your output

1. **The checked report.** The report with every claim that does not hold, and every unverified claim,
   removed. They are listed under `## Did not hold at the check`, each with the claim id and why. For a
   stopped packet, its reason.
2. **Findings**, most severe first, each citing the claim id and the source id.
3. **Counts:** claims checked N, held H, did not hold D, unverified U, and the floor's exit code.
4. The last line is `VERDICT: PASS` only when the floor is clean (apart from extraction losses you
   confirmed in the pdf), every claim holds, and nothing in step 3 failed. Otherwise `VERDICT: FAIL`. A FAIL
   holds for the person, who sees the findings and the checked report.
