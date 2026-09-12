---
name: wicked-garden-draft
user-invocable: true
description: |
  The quality floor for DOCUMENT deliverables drafted from a repository — brochures,
  one-pagers, flyers, product pages, slide decks, memos — as design guidance AND one
  self-check the author runs before "done". Three floors: (1) READABLE — every
  text/background pair ≥ 4.5:1 (WCAG AA; 3:1 for large text) judged on the COMPOSITED
  colours, and print text ≥ 7pt; (2) SIZED TO THE BRIEF — the RENDERED page count
  honours the page budget the brief names (wrappers are not pages); (3) GROUNDED — every
  number, URL and product claim cites a repo path, mocks are visibly labelled, and no
  placeholder ever ships inside the deliverable.

  Use when: "draft a brochure / one-pager / flyer / product page / deck / memo about
  <repo>", "print-ready A4 / Letter", "make it two pages", "is this brochure readable /
  grounded", before declaring any wicked-interactive document draft, edit or revision
  done, or as the skill a governed drafting run (wicked-crew `interactive-draft`,
  `interactive-edit`, `interactive-chat`) follows.

  NOT for reviewing code documentation (that is the engineering documentarian) or for
  auditing a running app's accessibility (the product accessibility action / the qe
  a11y engineer).
phase_relevance: ["build", "review"]
archetype_relevance: ["*"]
---

# wicked-garden-draft — the document-deliverable quality floor

A drafting worker can write a beautiful brochure that nobody can read, that prints on
four pages when two were asked for, and that ships an amber `[PLACEHOLDER]` box next to
an invented "live instance" — and every prompt-level instruction it was given ("never
invent facts", "honour the page count") will have been *followed in spirit*. That is
the 2026-09 recon outcome this skill exists to prevent. Guidance tells the author what
good looks like; the **self-check re-derives it from the saved file**. A deliverable is
not done until the self-check says `PASS` (or says `UNVERIFIED` and the notes disclose
exactly what could not be verified).

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## The contract

| # | Floor | Rule | Re-derived by |
|---|-------|------|---------------|
| 1 | **Readable** | every text/background pair ≥ **4.5:1** (3:1 for large text: ≥ 24px, or ≥ 18.66px bold), judged on the colours as COMPOSITED (alpha tints, gradients, `opacity`); print text ≥ **7pt** | `scripts/draft/contrast_check.py` |
| 2 | **Sized to the brief** | the RENDERED page count meets the budget the brief names — "two pages" means two PDF pages, not two `.page` wrappers | `scripts/draft/page_count.py` |
| 3 | **Grounded** | every number, URL, quote and capability claim cites a repo path; mocks are visibly labelled; no `[PLACEHOLDER]` / TODO / lorem in the deliverable | `scripts/draft/claims_scan.py` |

One command runs all three (§ Self-check). Details and worked examples: `refs/design-floor.md`
(colour and print typography), `refs/claims.md` (the citation convention), `refs/self-check.md`
(flags, JSON shape, exit codes, the manual alternative).

## 1. Readable — the contrast floor

- **Judge the pair, not the token.** `--ink-faint: rgba(255,255,255,0.14)` looks like a
  palette entry; on `#1a1a26` it is **1.5:1** — invisible in print. Compute (or run the
  check on) the composited text colour over the background it actually sits on.
- **On dark surfaces, alpha tints under 0.6 of white never pass.** For meta text (fact
  strips, footers, eyebrows, captions) use ≥ 0.7 — aim for 7:1, not 4.5:1: small thin
  type never reaches full pixel coverage, so it renders dimmer than its computed ratio.
- **Accent colours are not body-text colours.** A 62 %-lightness violet on a `#1a1a26`
  card is 3.7:1; lift it to ~78 % lightness for text, or keep the accent for rules,
  badges and glyphs only.
- **Gradients:** the text must pass against the darkest AND the lightest stop it can
  sit over.
- **Print size floor: 7pt.** Eyebrows at 5.5pt and monospace fact strips at 6.8pt are
  what "unreadable" looked like. Body 9.5–11pt, captions/meta ≥ 7pt, and let the check
  tell you (`--min-font-pt`, default 7; `0` for screen-only deliverables).
- **Write colours the check can read.** Use hex / `rgb()` / `hsl()`; `oklch()`, `lab()`,
  `color-mix()` and friends are not evaluated — the pair comes back `UNVERIFIED`, not
  passed. A container whose background is only an image (`url(…)`) gets an opaque
  `background-color` fallback, or its text is `UNVERIFIED` too.

## 2. Sized to the brief — the page budget

- **Default = exactly what the brief asks** ("two pages" → budget 2, `--exact`). If the
  brief names no count: a brochure/leaflet defaults to 2, a one-pager to 1, a deck to
  its slide count; a web page or memo has no page budget (`--no-pages`).
- **Disclose any hard cap** the format imposes (an A4 export, a slide template) in the
  deliverable's notes — and when the material cannot fit the budget, **cut content;
  never spill.** A spill page is a blank page with a header on it.
- **Wrappers are not pages.** A `.page` block taller than the sheet prints on two.
  Budget each page's content to the sheet (A4 portrait: 297mm minus the `@page` margins),
  use `break-after: page` between pages, never `overflow: hidden` to hide the overflow.
- **Never shrink to fit.** `zoom`, `transform: scale(…)`, `scale:` on `html`/`body`/a
  page wrapper, or dropping `font-size` under the floor to make the count come out, is
  the F-RECON-007 defect in a new coat: a page budget is met by **cutting content**, never
  by scaling the page. The size floor is judged on the *effective* size after any
  zoom/scale, so the check fails such a document — and a transform it cannot evaluate
  makes the size `UNVERIFIED`, not passed.
- **Verify the RENDERED count**: the exported PDF (`--pdf`) or a headless-Chrome print
  (`--render`). When neither is possible the count is `UNVERIFIED` — say so in the notes
  with the structural estimate; never state a page count you did not render.

## 3. Grounded — claims discipline

- **Every factual claim cites a repo path** — versions, requirements (`Node ≥ 22`),
  percentages, latencies, feature lists, quotes, URLs. Put `data-source="README.md:87"`
  on the element or its block (invisible in print, survives instrumentation) and list
  the sources for the reader in a visible **Sources** strip (`refs/claims.md`).
- **A URL claim must say what the source says.** `ws.wickedagile.com` documented as a
  static product site is a "Product site", never a "live instance". Quote the source
  line before you characterise a link.
- **Mocks and illustrations are labelled where the reader can see it** — the container
  carries `data-illustrative` AND visible text ("Illustrative — not measured data"). A
  label that lives only in an HTML comment is the defect, not the label.
- **No placeholders in the deliverable.** `[PLACEHOLDER: …]`, TODO, TBD, lorem, "quote
  goes here": a gap belongs in your reply/notes ("no customer quote exists in the repo —
  section omitted"), never in the document. A number you cannot cite is removed, not
  softened.

## Self-check before "done" (mandatory)

Run it on the SAVED deliverable (the file on disk is what ships), fix, and re-run until
it passes:

```bash
wicked-garden run scripts/draft/self_check.py <out.html> --pages 2 --exact --render --repo <snapshot-dir>
# with the product's own export:   --pdf <exported.pdf>   instead of --render
# web page / memo (no page budget): --no-pages --min-font-pt 0 --mode screen
```

| Verdict | Exit | Meaning | What you do |
|---------|------|---------|-------------|
| `PASS` | 0 | every floor met and every pair/page evaluated | **done** — end your reply with the verdict line |
| `FAIL` | 1 | a pair below the floor, text under 7pt (after any zoom/scale), pages over budget, a placeholder, an uncited number/URL, a hidden mock label, a dangling source | **never done** — fix the document (not the check, not the flags), re-run |
| `UNVERIFIED` | 3 | no floor failed, but something could not be evaluated: the page count (no PDF and no renderer on this seat), or a colour pair (unsupported colour function, image-only background, an unevaluable transform) | **done only with disclosure** — copy the `DISCLOSE` line(s) the check prints into the deliverable's notes and your reply |

There are exactly two "done" states: `PASS`, or `UNVERIFIED` with the disclosure. `FAIL`
is never done. A disclosure names (a) which check is unverified, (b) why on this seat
(e.g. "no Chrome/Chromium — structural estimate 2 pages"), (c) what a reviewer must do to
verify it (e.g. "run `page_count.py --pdf <export>` on the product's PDF export", or
"check pair X by hand / rewrite it in hex with an opaque background"). Paste the verdict
line(s) into your reply — never paraphrase them or describe a run you did not make. If the
launcher or Python is missing, follow the manual alternative in `refs/self-check.md` (the
WCAG formula per token pair, a real print to count pages, and the placeholder/number grep)
and say which steps were manual.

## In a governed run (wicked-crew `interactive-draft`, `-edit`, `-chat`)

- **Outline phase:** state the page budget you read from the brief (or the default
  above), the deliverable's format contract, and the sources you will cite — as plain
  text, no HTML yet.
- **Draft phase:** write the file to the absolute path the task names, then run the
  self-check on THAT file with the budget and the repo snapshot(s) the task names
  (`--pdf` when the task gives you an export, else `--render`). Fix and re-run until the
  verdict is `PASS` — or `UNVERIFIED` when this seat has no renderer or a pair cannot be
  evaluated (the check prints `DISCLOSE …` lines): then stop re-running, put the
  disclosure into the deliverable's notes, and end the reply with the absolute path, the
  verdict line, the structural page estimate, and the verification point ("verify with
  `page_count.py --pdf` on the product's PDF export"). A `FAIL` is never a stopping
  point. The run's own deliverable floor only proves the file exists — this skill is the
  quality floor.
- **Edit / revise phases:** a revision can re-introduce a defect (a design pin that
  darkens a caption). Re-run the self-check after every landed change; a `FAIL` is
  yours to fix before the turn ends.
- Never add `data-wid` attributes yourself; `data-source` and `data-illustrative` are
  fine — the service instruments its own anchors around them.
