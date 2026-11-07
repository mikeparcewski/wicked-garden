# Report mode: the fidelity check

The last step of a report run. You are the evaluator: you did not gather or synthesize this report, and you
re-check every claim at its source yourself. If you gathered or synthesized any of it, say so and give no
verdict line (wicked-crew already keeps those seats off this step; this is the second guard).

You change nothing: write no file in any repository and commit nothing. Scratch goes in your notes folder,
outside every repository.

## 1. Run the floor

Copy the packet (the json block in `synthesize`'s output) to `packet.json` in your notes folder, then run:

```
wicked-garden run scripts/learn/report_check.py check --packet <notes folder>/packet.json --records <documents folder>
```

Paste its JSON and its exit code. Leave out `--records` when the job staged no documents. Every finding
stands as a failure, with one exception: a `quote-not-found` where you read the original (the pdf page)
and the quote is there, because the text extraction lost it. Say so for that finding. With no launcher or no
Python, walk refs/report-claims.md's manual alternative and say you did.

## 2. Re-check every claim at its source

| Source kind | How you re-check it |
|---|---|
| web | Fetch the URL again through the same web source (in a crew run, the `fetch` tool of the job's `web` source; outside one, your own web tools). Read the page. Does it say what the claim says? |
| file | Open the file at the page and find the quote (for `brief`, first check that the packet's `brief` is the text the brief really carries). Does the claim follow from the quote, with the same numbers, dates, scope and hedges? A file the floor listed as `unchecked` (an image, a pdf without text) is read in the original. |
| tool | Call the same tool with the same read-only query, if you can. Does the result still support the claim? |

Each claim ends in one of three states:
- **holds**: the source says it, and the claim says no more than the source does;
- **does not hold**: the source does not say it, says something else, or the claim stretches it (a number,
  a date, "all" for "some", a cause where the source gives a correlation);
- **unverified**: you could not reach the source again (the fetch was refused or failed, the pdf cannot be
  read). Name what failed. An unverified claim is not a held claim.

## 3. Judge the rest

- Every factual sentence in the report cites a claim. An uncited factual sentence is a finding.
- No source is invented: every URL and file is in the log, and the log matches what the job could read. A
  web source when the packet says the web was not available is a fabrication.
- When the web was not used, the report says why, in plain words.
- The lens's shape is there (refs/report-<lens>.md): for example, an estimate states every assumption,
  and its price is effort × rate. Recompute every derived number.
- A stopped report states a true reason: check that the documents or sources it says are missing are
  really missing.

## 4. Your output

1. **The checked report.** The report with every claim that does not hold, and every unverified claim,
   removed. They are listed under `## Did not hold at the check`, each with the claim id and why.
2. **Findings**, most severe first, each citing the claim id and the source id.
3. **Counts:** claims checked N, held H, did not hold D, unverified U, and the floor's exit code.
4. The last line is `VERDICT: PASS` only when the floor is clean (or every finding was shown to be an
   extraction loss), every claim holds, and nothing in step 3 failed. Otherwise `VERDICT: FAIL`. A FAIL
   holds for the person, who sees the findings and the checked report.
