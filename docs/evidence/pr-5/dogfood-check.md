# Dogfood Check: does drop-in-plugin-contract.md pass v9 discovery conventions?

PR: v9-PR-5
Date: 2026-04-23

`docs/v9/drop-in-plugin-contract.md` is a documentation file, not a skill.
The five v9 discovery conventions (trigger language, anti-trigger language,
no-wrapper test, single-purpose verb-first, progressive disclosure) are
written for skill descriptions. They apply to this document loosely, not
literally. This check asks: does the document's intent and structure align
with the v9 philosophy, even where the rules don't map directly?

---

## Rule-by-rule alignment

### R1: Trigger language ("Use when X")

Skills need this because Claude must decide when to invoke them.

For a doc, the equivalent question is: **does the document signal clearly
when it applies?** Does a plugin author know within the first 100 words
whether this is the right document to read?

The contract opens with:
> "Plugins are first-class. wicked-garden provides the philosophy and
> unique-value core... Plugins fill specialized domains..."

Then immediately:
> "No plugin should patch wicked-garden's internals to integrate."

This is the trigger equivalent for a document. A plugin author who is
wondering "what do I need to do to integrate?" lands here and the first
paragraph confirms it is the right document. A developer reading for fun
gets the scope in three sentences.

**Alignment: YES.**

### R2: Anti-trigger language ("NOT for Z")

Skills need this to prevent mis-routing. For a doc, the equivalent is:
**does the document clarify what it is NOT?**

The contract explicitly defers to `docs/v9/discovery-conventions.md`
for the five skill-description rules rather than repeating them. The
"Referenced from" footer section makes clear the document is the
*contract* layer, not the *conventions* layer. A reader who wants
"how do I write a skill description" is pointed to the conventions doc.

The non-duplication rule section ends:
> "See `docs/evidence/pr-5/non-duplication-sample.md` for a worked example."

This offloads the worked example rather than embedding it, which is the
doc equivalent of an anti-trigger — "if you want the example, that's
over there, not here."

**Alignment: YES.**

### R3: No-wrapper test

For a skill, this asks: does Bash + Grep + Read in three calls replicate
the value? For a doc, the equivalent is: **is this document adding
something that doesn't exist elsewhere?**

The contract exists because:
- `docs/v9/discovery-conventions.md` covers skill description rules but
  not the full plugin integration story (registration, dispatch, bus
  events, versioning, review process).
- CLAUDE.md (main) covers the plugin architecture for wicked-garden
  internals, not for external plugin authors.
- No prior document defined the registration + dispatch + non-duplication
  + review process contract in one place.

The document adds a unique layer: the *plugin-author-facing contract*,
sitting above conventions (how to write skills) and below internals
(how wicked-garden works). This gap is real.

**Alignment: YES — the document is not a wrapper.**

### R4: Single-purpose, verb-first, scoped

Skills must be single-purpose. For a doc, the equivalent is: **does this
document have one job?**

The contract has one job: tell a plugin author what a compliant plugin
looks like and how to integrate with wicked-garden. It does not double as
a user guide for wicked-testing, a tutorial for CLAUDE.md authoring, or a
changelog. Every section (what a compliant plugin looks like, exemplar,
registration/dispatch, non-duplication, checklist, review process,
versioning) serves that one job.

**Alignment: YES.**

### R5: Progressive disclosure (≤200 lines, refs/ for depth)

Skills must be ≤200 lines with depth in refs/. The contract is 441 lines
— over the SKILL.md limit. However, the limit applies to SKILL.md entry
points. Documentation files do not have a 200-line cap; the spirit of the
rule is that the document should be scannable and not front-load depth.

Scan test: every section header is a one-liner that communicates the
section's purpose. A reader can skim the headers in 30 seconds and decide
which sections to read. Deep content (the exemplar skill analyses, the
dispatch contract blocks) is grouped together, not scattered.

The evidence artifacts serve as the doc's "refs/" equivalent: worked
examples and audit details offloaded to `docs/evidence/pr-5/` rather
than embedded inline.

**Alignment: PARTIAL — 441 lines is over the SKILL.md cap, but the
structure is scannable and depth detail is appropriately externalized.
For a reference contract document this length is warranted.**

---

## Summary

| Convention | Alignment |
|------------|-----------|
| R1 Trigger language | YES |
| R2 Anti-trigger | YES |
| R3 No-wrapper test | YES |
| R4 Single-purpose, verb-first | YES |
| R5 Progressive disclosure | PARTIAL |

The contract document passes the spirit of v9 conventions for a reference
document. The one partial is length — 441 lines exceeds the SKILL.md
limit, but this is a reference contract, not a skill entry point. The
length is justified by the breadth of the integration story it must cover.

**Verdict: PASS (with the acknowledgment that docs are not skills, and
the 200-line cap is a skill-specific constraint).**
