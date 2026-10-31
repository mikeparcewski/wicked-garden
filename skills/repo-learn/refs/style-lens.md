# Style lens: how the person or team works, not only how the code works

Use this lens when the run asks for **style** (studio's Learn → Style launches `capture-learnings`
with a problem that names a style read, e.g. "Learn the style of acme/web-store"), or when a
person asks "learn how I write code here". The three phases stay the same and stay bounded; the
lens changes what phase 2 reads for and what phase 3 captures.

## What to read for (phase 2)

Sample, never stream: every read below has a cap, and the cap goes in your output.

| Angle | Bounded read | What a finding looks like |
|---|---|---|
| Naming | the churn set's exported symbols (estate `SearchEntity`/`RetrieveEntity`), 30 at most | "Functions are verbs, types are nouns; no `I` prefix on interfaces" |
| Structure | where tests, fixtures and docs sit relative to the code: `git ls-files \| head -400` rolled up by directory | "Tests sit beside the code as `*.test.ts`" |
| Test shape | 3 to 5 test files from the churn set, read for real | "One `describe` per exported function; table-driven cases" |
| Change size | `git log --no-merges -n 200 --shortstat --format=%h` summed per commit (median and 90th percentile) | "Commits stay under 400 changed lines (90% of the last 200)" |
| Commit tone | `git log --no-merges -n 100 --format=%s` | "Imperative, area first: `cart: …`" |
| Review tone | only when `gh` is signed in: `gh pr list --state merged -L 20 --json number` then `gh pr view <n> --comments` for 3 to 5 of them | "Reviews ask for a test before approving a fix" |

Skip an angle the repo cannot answer (no `gh`, no tests) and say so in one line; never fill it
with a guess.

## What to capture (phase 3)

Why style is memory here: the person pointed Learn at this repository or writing as **their own example**
("this is how we work"), and nothing is kept until they accept it in review. That makes the pattern
*told*, the memory side of the memory-vs-knowledge rule. A fact about how the code itself behaves is still
*acquired*, so it stays knowledge with `source` and `source_rev`, exactly as in
[capture-proposals.md](capture-proposals.md). Without the person's hand-off (a repo learned for orientation
only) there is no style lens and no style memory.

- A **style memory** is how this person or team chooses to work. `kind_type: "memory"`; payload
  `{"content": "<one sentence, what they do>", "tier": "semantic", "capture": "memory", "reach": "operator"}`;
  facets `{"repo": "<name>", "project": "<name>"}`. Name the evidence inside the sentence: "… (212 merged
  PRs, last 6 months)". A memory payload carries no `source` key (that marks acquired knowledge, and the
  memory shim refuses it). `reach: "operator"` lets the person decide, when they
  accept it, whether it applies everywhere they work.
- A convention the repo **enforces** (a lint rule, a CI check, a CONTRIBUTING line that says "must")
  is a **policy**, as in [capture-proposals.md](capture-proposals.md), not a style memory.
- What the code **does** stays knowledge, exactly as without the lens.
- At most 8 style memories per repository: the ones a new contributor would get wrong first.

## Writing as a source (a blog, a docs site, a document)

When the material is the person's writing rather than a repository, there is no churn and no graph:

1. **Read** a bounded sample: at most 10 posts or pages, newest first, or the document as given.
   Fetch only public addresses; a page that needs a sign-in is skipped and named.
2. **Spot patterns**: sentence length, voice (active or passive), person (I, we, you), how a piece
   opens and ends, jargon, headings, lists against prose.
3. **Capture** each pattern as a style memory as above, naming the writing inside the sentence ("…, across
   14 posts on the team blog"), facets `{"project": "<name>"}`, no `source` key. The person handed over
   their own voice, so it is memory (told), never knowledge.
