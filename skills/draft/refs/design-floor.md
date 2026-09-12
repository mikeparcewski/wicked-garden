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

| Token | Declared | Composited on `#1a1a26` (card) | Ratio | Verdict |
|-------|----------|-------------------------------|-------|---------|
| `--ink-primary` | `rgba(255,255,255,0.92)` | `#ededee` | 14.6:1 | fine |
| `--ink-body` | `rgba(255,255,255,0.78)` | `#cdcdcf` | 10.4:1 | fine |
| `--ink-muted` | `rgba(255,255,255,0.48)` | `#88888e` | 4.6:1 | passes 4.5 — but at 6.8pt it read as ~93/255 grey; use 0.70+ for small meta |
| `--ink-faint` | `rgba(255,255,255,0.14)` | `#3a3a44` | **1.5:1** | the invisible footer / KPI label |
| `--accent` | `hsl(258,72%,62%)` | `#8258e4` | **3.7:1** | fine for rules and glyphs, not for text |

Lifting `--ink-faint` to `0.70`, `--ink-muted` to `0.72` and the accent to 78 % lightness makes
the same document pass every pair (`tests/draft/test_contrast_check.py` proves it).

## Safe defaults

- **Dark surface (`#09090f`–`#22223a`):** text tints of white at ≥ 0.72 (meta) and ≥ 0.85
  (body); accents for TEXT at ≥ 75 % lightness; never a tint under 0.6.
- **Light paper (`#ffffff`–`#f8fafc`):** body `#1e293b`-class inks (≥ 12:1); meta no lighter than
  `#5b6470` (≈ 6:1); `#94a3b8` (3.2:1) is a rule colour, not a caption colour.
- **Tinted cards over a gradient hero:** the text must pass against the darkest AND lightest
  stop the card can sit over — or give the card an opaque background.
- **Status colours** (emerald/amber/red) as text: check them — `hsl(148,58%,58%)` on `#1a1a26`
  is 7.8:1 (fine); `hsl(45,90%,68%)` is 11:1 (fine); a 45 %-lightness variant of either is not.

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
- Verify with the rendered count (`page_count.py --render`, or the product's export) — the
  structural estimate cannot see a wrapper that grew past the sheet.
