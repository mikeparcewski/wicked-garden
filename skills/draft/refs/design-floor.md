# Design floor — colour pairs and print typography

The readable floor of the `wicked-garden-draft` skill, with the numbers worked out. Everything
here is re-derived by `scripts/draft/contrast_check.py`; this page is for choosing tokens BEFORE
the check tells you they fail.

## How the check judges a pair

WCAG 2.x contrast: `(L_lighter + 0.05) / (L_darker + 0.05)` over relative luminance (sRGB
linearised). Floors: **4.5:1** for text, **3:1** for large text (≥ 24px, or ≥ 18.66px bold).
The checker cascades your stylesheet (specificity, source order, inline `style=`, `!important`,
`var()` with inheritance, `@media print` in print mode), composites translucent text and
backgrounds over what is really beneath them (root = white unless `html`/`body` paints), applies
`opacity`, judges every gradient stop, and reports the WORST pair per element. It skips
`display:none` / `visibility:hidden` / `hidden` content and glyph-only spans (`·`, `|`).

## The token pairs from the recon brochure (why it was unreadable)

All ratios below are computed with `scripts/draft/contrast_check.py`
(`contrast_ratio(composite(token, surface), surface)`), rounded to one decimal.

| Token | Declared | Composited on `#1a1a26` (card) | Ratio | Verdict |
|-------|----------|-------------------------------|-------|---------|
| `--ink-primary` | `rgba(255,255,255,0.92)` | `#ededee` | 14.7:1 | fine |
| `--ink-body` | `rgba(255,255,255,0.78)` | `#cdcdcf` | 10.8:1 | fine |
| `--ink-muted` | `rgba(255,255,255,0.48)` | `#88888e` | 4.9:1 | passes 4.5 — but at 6.8pt it read as ≤ 93/255 grey; use 0.70+ for small meta |
| `--ink-faint` | `rgba(255,255,255,0.14)` | `#3a3a44` | **1.5:1** | the invisible footer / KPI label |
| `--accent` | `hsl(258,72%,62%)` | `#8258e4` | **3.7:1** | fine for rules and glyphs, not for text |

Lifting `--ink-faint` to `0.70` (8.9:1), `--ink-muted` to `0.72` (9.4:1) and the accent to 78 %
lightness (7.5:1) makes the same document pass every pair (`tests/draft/test_contrast_check.py`
proves it).

## Safe defaults

- **Dark surface (`#09090f`–`#22223a`):** text tints of white at ≥ 0.72 (meta; 10.3:1 on the
  surface) and ≥ 0.85 (body; 14.2:1); accents for TEXT at ≥ 75 % lightness (6.6:1 on the card);
  a tint of 0.6 is 6.9:1 on the card — treat it as the floor for meta, never go under it.
- **Light paper (`#ffffff`–`#f8fafc`):** body `#1e293b`-class inks (14.6:1); meta no lighter than
  `#5b6470` (6.0:1); `#64748b` (4.8:1) is the last passing grey; `#94a3b8` (**2.6:1**) is a rule
  colour, not a caption colour.
- **Tinted cards over a gradient hero:** the text must pass against the darkest AND lightest
  stop the card can sit over — or give the card an opaque background.
- **Status colours** (emerald/amber/red) as text: check them — `hsl(148,58%,58%)` on `#1a1a26`
  is 9.0:1, `hsl(45,90%,68%)` is 11.8:1; darker variants lose ratio fast (the 45 %-lightness
  emerald is 6.6:1, the amber 7.8:1) — let the check tell you rather than guessing.
- **Colours the check cannot read:** `oklch()`, `oklab()`, `lab()`, `lch()`, `color-mix()`,
  `light-dark()` are not evaluated — the pair is reported `UNVERIFIED`, never passed or inherited.
  Write tokens in hex / `rgb()` / `hsl()`.
- **Image backgrounds:** a container painted only by `background: url(…)` has no colour the
  checker can judge — its text is `UNVERIFIED`. Give it an opaque `background-color` fallback
  (`background: #0d0d1e url(hero.jpg) center/cover`) so the pair is judged on the fallback.

## Print typography floor

- Body 9.5–11pt; captions, eyebrows, fact strips, footers **≥ 7pt** (the check's
  `--min-font-pt 7`). Nothing at 5.5–6.8pt survives a laser print or a 1240px PNG.
- Uppercase + wide tracking + monospace at small sizes compounds the loss: if a strip must be
  small, make it high-contrast (≥ 7:1) and ≥ 7pt.
- Thin weights (300) on dark surfaces need +1 step of tint; the check does not measure stroke
  width, so you have to.
- Screen-only deliverables (`web`): `--min-font-pt 0 --mode screen`; keep body ≥ 16px.

## Page-budget layout recipe (A4 portrait, `@page { margin: 18mm 20mm }`)

- Available block per sheet: `297mm − 36mm = 261mm` tall, `210mm − 40mm = 170mm` wide.
- Each `.page` wrapper: budget its content to ≤ 261mm; `break-after: page` on every wrapper but
  the last; **no** `overflow: hidden`, **no** fixed `height` that clips.
- **Never `zoom`, `transform: scale(…)` or `scale:` the page (or drop `font-size` under 7pt) to
  make the count fit** — that is the unreadable brochure again. Cut content: drop a card, shorten
  a paragraph, move a table to the notes. The size floor is judged on the effective size after any
  zoom/scale, so a shrunk page fails the check anyway.
- Verify with the rendered count (`page_count.py --render`, or the product's export) — the
  structural estimate cannot see a wrapper that grew past the sheet.
