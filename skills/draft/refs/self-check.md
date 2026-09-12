# The self-check — flags, output, exit codes, manual alternative

`scripts/draft/self_check.py` runs the three floors and prints one verdict. The three checks are
also individually runnable (same flags, same JSON shape per check).

## Commands

```bash
# print brochure, budget from the brief, render with headless Chrome, trace claims to the snapshot
wicked-garden run scripts/draft/self_check.py out.html --pages 2 --exact --render --repo /path/to/snapshot

# the product already exported a PDF — authoritative page count
wicked-garden run scripts/draft/self_check.py out.html --pages 2 --exact --pdf out.pdf

# web page / memo — no page budget, screen media, no print size floor
wicked-garden run scripts/draft/self_check.py out.html --no-pages --mode screen --min-font-pt 0

# the individual checks
wicked-garden run scripts/draft/contrast_check.py out.html --mode print --min 4.5 --min-font-pt 7
wicked-garden run scripts/draft/page_count.py out.html --budget 2 --exact --render
wicked-garden run scripts/draft/claims_scan.py out.html --repo /path/to/snapshot
```

| Flag | Meaning |
|------|---------|
| `--pages N` / `--exact` | the brief's page budget; `--exact` = must equal N (default: must not exceed) |
| `--pdf <file>` | an exported PDF — the authoritative rendered count; a path that does not exist is an error (exit 2) unless `--render` is also given, in which case the render is written there |
| `--render` | print the HTML with Chrome/Chromium/Edge (PATH, usual install dirs, `$WICKED_CHROME`) |
| `--no-pages` | skip the page check (web pages, prose docs) |
| `--repo <dir>` (repeatable) | repository snapshot(s) claims must trace to: `data-source` paths must exist, URLs must appear |
| `--min-contrast` | default 4.5 (large text always 3.0) |
| `--min-font-pt` | print size floor, default 7; `0` disables |
| `--mode print\|screen\|both` | which `@media` rules apply (default `print`) |
| `--json` | machine-readable report |

## Verdict and exit codes

| Verdict | Exit | When |
|---------|------|------|
| `PASS` | 0 | every floor met; every pair evaluated; page count verified (or `--no-pages`) |
| `FAIL` | 1 | any `contrast`/`size` or claims finding, or pages over (or ≠ with `--exact`) the budget — a structural estimate that already exceeds the budget is a FAIL too |
| `UNVERIFIED` | 3 | nothing failed, but something could not be evaluated: no PDF and no renderer (page count = structural estimate), and/or `[unknown]` contrast pairs (unsupported colour function, image-only background, an unevaluable transform) |
| error | 2 | unreadable input / usage (including a `--pdf` path that does not exist) |

The two "done" states are `PASS` and `UNVERIFIED`-with-disclosure. `FAIL` is fixed in the
DOCUMENT and re-run; never by loosening the flags, never by `zoom`/`scale`. `UNVERIFIED` is never
rounded up to a pass: the check prints one `DISCLOSE in the deliverable's notes -> …` line per
unverified check — copy those lines into the document's notes and your reply. A disclosure always
names **which** check, **why** on this seat, and **what a reviewer does to verify**:

```
pages: count UNVERIFIED (no PDF and no renderer on this seat) — structural estimate 2;
       verify with `page_count.py --pdf <export>` on the product's export
contrast: 1 pair(s) UNVERIFIED — see the [unknown] findings; verify those pairs by hand or
       rewrite them in hex/rgb/hsl with an opaque background fallback
```

The individual checks use the same codes: `contrast_check.py` exits 3 when no pair fails but at
least one is `[unknown]`; `page_count.py` exits 1 before 3 (an over-budget estimate is a failure);
`claims_scan.py` has no unverified state.

## JSON shape (top level)

```json
{"check": "draft-self-check", "file": "out.html", "verdict": "FAIL", "ok": false,
 "failed": ["contrast", "pages"], "unverified": [],
 "checks": {
   "contrast": {"ok": false, "elements_checked": 117, "contrast_failures": 11, "size_failures": 34,
                "findings": [{"kind": "contrast", "path": "section.page.page-2 > … > div.cta-reqs",
                              "text": "Node.js ≥ 22 · npm ≥ 10 …", "fg": "#3a3a44", "bg": "#1a1a26",
                              "ratio": 1.53, "required": 4.5, "font_pt": 6.2, "mode": "print"}]},
   "claims":   {"ok": true, "by_kind": {}, "findings": [], "stats": {"numbers": 13, "cited_numbers": 13}},
   "pages":    {"pages": 4, "source": "pdf", "verified": true, "budget": 2, "within_budget": false}
 },
 "summary": ["contrast: …", "claims: …", "pages: 4 (pdf) vs budget = 2 — EXCEEDED"]}
```

Finding kinds — contrast: `contrast`, `size` (carries `scale` when a zoom/transform factor was
applied: the reported `font_pt` is the *effective* size), `unknown` (UNVERIFIED pair, with a
`detail` saying what and what to do); claims: `placeholder`, `uncited-number`, `uncited-url`,
`unsourced-url`, `mock-label-hidden`, `mock-unlabelled`, `dangling-source`. The contrast report
also carries `notes` — e.g. colour-declaring rules whose selectors (`:nth-child`, `:is`, `:has`…)
the checker does not evaluate and therefore did NOT judge; check those elements by hand. With
`--mode both` a pair failing in both media is one finding tagged `print+screen`.

## Manual alternative (launcher or Python unavailable)

Say which of these you did by hand.

1. **Contrast.** For every text colour token, composite it over the surface it sits on
   (`c = a·fg + (1−a)·bg` per channel), linearise (`s/12.92` if `s ≤ 0.04045` else
   `((s+0.055)/1.055)^2.4`), `L = 0.2126R + 0.7152G + 0.0722B`, ratio `(L1+0.05)/(L2+0.05)`.
   Body/meta ≥ 4.5, large ≥ 3. Any `rgba(255,255,255,a)` with `a < 0.6` on a dark surface fails
   without computing. Check font sizes: nothing under 7pt in print.
2. **Pages.** Print the HTML to PDF (browser: File → Print → Save as PDF, A4, default margins)
   and read the page count from the viewer. No printer available → write "page count
   unverified" in the notes with your wrapper/break count.
3. **Claims.** Search the visible text for `PLACEHOLDER`, `TODO`, `TBD`, `lorem`, `{{`,
   `[INSERT`; list every number and URL and point each at a `data-source` path that exists in
   the snapshot; confirm every mock has a visible "illustrative" label.
