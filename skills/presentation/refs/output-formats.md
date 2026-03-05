# Output Formats

The presentation skill uses a **single intermediate representation** (the Deck Spec) and renders to any
supported format from it. Content is generated once; rendered anywhere.

---

## Architecture

```
[wizard / brainstorm / create / fast / overview]
                    ↓
            [Deck Spec JSON]          ← stored in presentation:specs:{slug}:{version}
             /             \
      [PptxGenJS]       [Reveal.js]
           ↓                  ↓
      .pptx file          .html file
  (editable in PPT)  (self-contained, browser)
```

The Deck Spec is the canonical artifact. Both renderers consume it. Re-rendering to a new format
never regenerates content — it re-interprets the same spec through a different renderer.

---

## Supported Formats

### `pptx` — PowerPoint (default)
Generated via PptxGenJS. Standards-compliant OOXML. Opens in PowerPoint, Keynote, LibreOffice.
Editable after delivery. Best for decks that need post-generation polish or client handoff.

### `html` — Reveal.js Presentation
Self-contained single `.html` file. No server, no build step, no dependencies — open in any
browser. Best for sharing as a link, embedding in pages, or presenting directly from a laptop
without PowerPoint installed.

### `both`
Generates both files from the same Deck Spec in a single run. Both versioned together.

---

## Format Selection

**Per run:**
Specify format upfront: "make this as html", "pptx format", or "both formats." For fast path,
add the format intent to your request: "fast deck on [topic] as html." Valid values: `pptx`,
`html`, `both`.

**Profile default:**
Set `output.default_format` in the profile. Options: `pptx`, `html`, `both`.
If not set, defaults to `pptx`.

**Wizard:**
If format not set via request and not in profile default, wizard asks after mode selection:
> "Output format: pptx / html / both?"

**Fast path:**
Uses profile default silently. Falls back to `pptx` if nothing set.

---

## Re-rendering Existing Specs

Any prior version's Deck Spec can be rendered to a new format without regenerating content.
To re-render an existing spec, request: "re-render deck-name_v2 to html format" or
"re-render deck-name_v2 in both formats."

This reads `presentation:specs:deck-name:v2`, runs it through the requested renderer(s),
and outputs new versioned file(s). The version record is updated to note the new render.
Content is never touched.

Use cases:
- Built a PPTX for a meeting → now want an HTML version to share as a link
- Prototype in HTML (fast iteration) → render final PPTX for client handoff
- Regenerate after profile update (new colors applied to existing spec)

---

## Deck Spec Schema

The Deck Spec is the shared input both renderers consume. It is renderer-agnostic.

```json
{
  "spec_version": "1.0",
  "slug": "sales-kickoff",
  "version": 2,
  "label": "client-review",
  "title": "Q2 Sales Kickoff Strategy",
  "created_at": "2025-03-05T14:00:00Z",
  "profile": "corporate-blue",
  "image_mode": "unsplash",
  "fidelity": "draft",
  "slides": [
    {
      "index": 1,
      "template": "title-hero",
      "title": "Q2 Sales Kickoff",
      "subtitle": "From Pipeline to Revenue — Our Plan for Next Quarter",
      "background": { "type": "image", "query": "technology transformation abstract" },
      "speaker_notes": "Opening — set the stage for the transformation journey.",
      "review_flags": []
    },
    {
      "index": 2,
      "template": "stat-callout",
      "title": "The Baseline",
      "stats": [
        { "value": "73%", "label": "Manual test coverage" },
        { "value": "4.2 days", "label": "Avg defect escape time" },
        { "value": "$2.1M", "label": "Annual rework cost" }
      ],
      "context": "Current state as of Q4 2024 audit.",
      "speaker_notes": "These numbers justify the urgency of the program.",
      "review_flags": ["[REVIEW: $2.1M figure — confirm with finance before presenting]"]
    },
    {
      "index": 3,
      "template": "two-column",
      "title": "Our Approach",
      "left": {
        "type": "bullets",
        "items": ["AI-native test generation", "Shift-left integration", "Continuous quality gates"]
      },
      "right": { "type": "image", "query": "engineering workflow diagram" },
      "speaker_notes": "Walk through the three pillars.",
      "review_flags": []
    }
  ]
}
```

### Slide fields (all templates share these)
| Field | Required | Description |
|---|---|---|
| `index` | Yes | Slide number (1-based) |
| `template` | Yes | Template name — see templates.md |
| `title` | Yes | Slide title |
| `speaker_notes` | No | Notes for presenter |
| `review_flags` | No | Array of REVIEW strings (empty = clean) |
| `background` | No | Override background for this slide |

Template-specific fields (stats, left/right columns, quote, etc.) are defined per template
in templates.md.

---

## PptxGenJS Renderer

**Library:** PptxGenJS (gitbrent/PptxGenJS)
**Output:** `.pptx` — OOXML, compatible with PowerPoint, Keynote, LibreOffice

### Profile → PptxGenJS mapping
| Profile field | PptxGenJS equivalent |
|---|---|
| `colors.primary` | Slide master accent color |
| `colors.background_light/dark` | Slide background fill |
| `typography.heading_font` | Title placeholder font |
| `typography.body_font` | Content placeholder font |
| `layout.logo_position` | Recurring image on slide master |

### Notes
- Slide master defined once from profile; applied to all slides via `addSlide({ masterName })`
- Speaker notes written to `slide.addNotes()`
- Images embedded as base64 when possible; linked when file size is a concern
- Charts use PptxGenJS native chart objects (`slide.addChart()`)

---

## Reveal.js Renderer

**Library:** reveal.js (hakimel/reveal.js)
**Output:** Self-contained `.html` file — no build step, no CDN, no server

Reveal.js is chosen over alternatives (e.g., Spectacle) because it produces clean, self-contained HTML from simple section-tag markup — well-suited to programmatic generation and LLM output.

### Self-contained output
All reveal.js CSS and JS is inlined. Images are base64-encoded and embedded. The output is
a single `.html` file with zero external dependencies. Open it offline, email it, host it
anywhere.

### Profile → Reveal.js mapping
Profile colors and typography are injected as CSS custom properties into the HTML `<style>` block:

```css
:root {
  --r-background-color: #F5F5F5;
  --r-main-color: #1A1A1A;
  --r-heading-color: #A100FF;
  --r-link-color: #460073;
  --r-main-font: 'Helvetica Neue', sans-serif;
  --r-heading-font: 'Helvetica Neue', sans-serif;
  --r-heading-font-weight: bold;
}
```

### Template → HTML section mapping
Each Deck Spec slide becomes a `<section>` element. Template type determines internal structure:

```html
<!-- title-hero -->
<section data-background-image="..." data-background-opacity="0.4">
  <h1>Slide Title</h1>
  <p class="subtitle">Subtitle text</p>
</section>

<!-- stat-callout -->
<section>
  <h2>The Baseline</h2>
  <div class="stat-row">
    <div class="stat"><span class="value">73%</span><span class="label">Manual test coverage</span></div>
    <div class="stat"><span class="value">4.2 days</span><span class="label">Avg defect escape time</span></div>
    <div class="stat"><span class="value">$2.1M</span><span class="label">Annual rework cost</span></div>
  </div>
  <p class="context">Current state as of Q4 2024 audit.</p>
</section>

<!-- two-column -->
<section>
  <h2>Our Approach</h2>
  <div class="two-col">
    <div class="col-left"><ul>...</ul></div>
    <div class="col-right"><img src="data:image/..."/></div>
  </div>
</section>
```

Standard reveal.js keyboard shortcuts apply: arrow keys and Space advance slides, S opens speaker notes in a separate window, O shows a slide overview grid, F enters fullscreen, B blacks the screen.

### PDF export from HTML
Append `?print-pdf` to the file URL in Chrome, then use browser print (Ctrl/Cmd+P).
Select "Save as PDF." Produces a per-slide paginated PDF with speaker notes optionally included.

### Transitions
Default: `slide` (horizontal). Override per deck in profile under `output.html_transition`.
Options: `none`, `fade`, `slide`, `convex`, `concave`, `zoom`.

---

## Format Capability Comparison

| Feature | PPTX | HTML (reveal.js) |
|---|---|---|
| Editable in PowerPoint | ✅ | ❌ |
| Editable post-generation | ✅ (full) | ✅ (HTML/CSS knowledge needed) |
| Animations / transitions | Basic | Rich (fade, zoom, convex, etc.) |
| Live code demo in slide | ❌ | ✅ |
| Presenter mode | Via PowerPoint | Built-in (press S) |
| Slide overview mode | Via PowerPoint | Built-in (press O) |
| PDF export | Via PowerPoint | Via Chrome print + ?print-pdf |
| Share as URL | ❌ | ✅ (host the .html file) |
| Offline use | ✅ | ✅ (self-contained) |
| Zero install to present | ❌ (needs PPT) | ✅ (any browser) |
| Charts | PptxGenJS native | HTML/CSS or inline SVG |
| Speaker notes | Slide notes pane | Press S — separate window |
| Client edits after | ✅ easy | ⚠ requires HTML knowledge |
| File size | Medium (.pptx) | Larger if many images (base64) |

---

## Version Naming with Format

Both format outputs share the same version number and label:
```
deck-name_v2-client-review.pptx
deck-name_v2-client-review.html
```

The version record tracks which formats have been rendered:
```json
{
  "version": 2,
  "label": "client-review",
  "formats_rendered": ["pptx", "html"],
  "spec_key": "presentation:specs:deck-name:v2"
}
```

---

## Post-Generation Summary (format section)

Always include format output in the generation summary:
```
✓ Deck created: deck-name_v2-client-review.pptx + .html (18 slides)
  Format:   both (pptx + reveal.js html)
  Fidelity: draft (1 pass)
  Spec:     saved to presentation:specs:deck-name:v2
  Re-render any time: request "re-render deck-name_v2 as <format>"
  Upgrade layout:     request "re-render deck-name_v2 at best fidelity"
```
