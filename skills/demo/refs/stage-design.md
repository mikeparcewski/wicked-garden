# Stage design

The visual system the recorder draws. Everything here is stage DOM (a page wrapping the app in an iframe), so it is
rendered with real fonts and CSS transitions, and none of it ever sits on top of the product UI except callouts and
the cursor, which point *at* it.

## Layout (1920x1080 canvas)

| Element | Position and size | Notes |
|---|---|---|
| Window | x 160, y 20, 1600x900, radius 14 px, soft shadow | White, 1 px border; app viewport is 1600x862 below the title bar |
| Title bar | 38 px high | Three muted dots, centred address pill: **brand name** + current path (path only, no query string, single line with ellipsis) |
| Caption band | x 160, from y ~942 to the bottom, width 1600 | Caption on the left, brand block on the right (300 px) |
| Speed badge | In the title bar, right-aligned, 28 px pill | Dark pill: fast-forward icon, `8×`, label, `m:ss real time`. `pointer-events: none` |
| Cursor | 26 px arrow, dark fill with white stroke, drop shadow | Hidden until first use; glides 0.7 s between targets |
| Background | Very light neutral radial gradient | Keeps the white window distinct without drawing attention |

Why a window and a band: captions over the UI hide the thing being explained, and a full-bleed recording of a
browser looks like a screen grab. A framed window on a quiet canvas reads as a produced video and leaves a
dedicated, always-legible place for words.

## Typography

- One family (a clean sans such as Inter, with system fallbacks). Loaded as a web font; see gotchas for offline.
- Kicker 13 px, weight 700, uppercase, 0.14 em tracking, accent colour, preceded by a short accent rule.
- Caption title 27 px, weight 650, one line (ellipsis if too long: rewrite it shorter).
- Caption body 17.5 px, line height 1.45, muted ink, max two lines; `<em>` renders as semibold ink for one key phrase.
- Chapter slide title 58 px; number 150 px in accent; blurb 23 px; tags 15 px pills.

## Captions

- **Kicker** names the beat ("Search", "Governance"); **title** says what the viewer should take away in one line;
  **body** gives the why or the mechanism in at most two lines.
- Change the caption **before** the navigation it describes (pass a short `readMs`, 600 to 1200 ms), so the new
  words land as the new picture arrives. A caption that lingers over the next screen reads as a mistake.
- Default reading time is about 2.2 s plus 38 ms per character, capped at 9 s. Hold longer on dense screens.
- Transition: the old caption fades out (0.28 s), then the new one slides up and fades in (0.45 s). Never overlap.
- Write for the audience, not the developer: no internal keys, no jargon the product UI doesn't use.

## Callouts

- Accent 3 px outline, 12 px radius, 7 px soft accent glow, padded 8 px around the element.
- A dark label (13.5 px, white) sits above the box, or below it when there is no room above.
- The box is **clipped to the visible app viewport**: tall sections get a box to the window edge, not off-canvas.
- Before pointing, the element is scrolled into view smoothly: centred if it fits, otherwise its top is placed just
  under the app's sticky header so the section title is visible.
- Point at the smallest element that makes the point. Remove the callout before moving on.
- First appearance fades in place (no slide from the corner); later moves animate position and size.

## Cursor and clicks

- The cursor moves to the target (centre, or 60 px in from the left edge of wide targets), waits, ripples (an accent
  ring scaling out over 0.6 s), then the real click happens. Typing is visible, character by character.
- Hide the cursor before closing cards and on static beats where it would distract.

## Chapter slides and joins

- Each non-intro segment opens on a full-stage slide: big accent number (`02`), "CHAPTER 2 OF 10", title, blurb,
  capability tags. It is shown while the segment's setup (reset, persona, start page) happens behind it.
- The segment's video is trimmed to start on the fully faded-in slide.
- Every chapter segment ends by fading to the plain stage background (an empty card). The next segment starts on its
  slide, so the join is a clean cut from background to slide: no frame-accurate stitching, no crossfades to render.
  The intro ends on its own title card, so intro → chapter 1 is a card-to-card cut. The last segment ends on the
  closing card instead.
- The caption band shows chapter progress: one short bar per chapter (done, current in accent, upcoming) and
  "Chapter N of M · Title".

## Title and closing cards

- Title card: logo lock-up (logo, divider, product name), a two-line headline with one accent phrase, one sentence,
  and chips such as "Recorded live", "Business date · …", "Synthetic data".
- Closing card: logo, "How <product> speeds up execution" (or similar), a two-column numbered list of accelerators,
  and chips with **measured** numbers from `timings.json` (ranges and medians). Never estimates.

## Time-lapse badge

- Any real wait longer than a few seconds runs inside `ctx.fast(label, factor, fn)`. The badge shows the factor,
  the label and a running real-time clock; post-processing speeds up exactly that span.
- 4× for assistant answers (10 to 40 s), 8× for jobs of a minute or more. The viewer always knows time was compressed.

## Branding

- `brand.name` appears in the title bar and caption band; `brand.logo` (SVG, inlined) in the band and on cards via
  `<div data-logo></div>`; `brand.accent` drives kicker, callouts, cursor ripple, chapter numbers and progress.
- Keep the accent to those elements. The product UI provides the rest of the colour.
- Don't imitate another organisation's branding unless it is your own product and you are entitled to use it.

## Legibility

- Record at device scale 1 so the 1600x862 app viewport maps 1:1 to video pixels; text stays crisp at 1080p.
- Keep caption and label contrast high (dark ink on light, white on dark); never put text over busy UI.
- Avoid flashing: fades are 0.3 to 0.7 s, holds at least 2 s on anything the viewer should read.
