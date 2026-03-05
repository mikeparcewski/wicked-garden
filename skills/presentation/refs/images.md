# Images — Sourcing & Attribution

Two image modes: Unsplash (photography) and Icon/UI Illustration (generated from icon sets).
Mode is set in the profile, selectable per deck, and overridable per slide.

---

## Image Mode Selection

Set in profile under `imagery.default_mode`. Options:
- `unsplash` — real photography via Unsplash API
- `icons` — icon/UI illustration style, generated from registered iconsets
- `none` — no images; layouts adapt to text-only

Per-deck override: set during wizard Q8 (image mode question).
Per-slide override: user can say *"use an icon on this slide instead of a photo"* at any point.

---

## Unsplash Mode

### How it works
For each image-bearing slide, generate a search keyword from the slide's content topic.
Query the Unsplash API. Select the most visually appropriate result (composition, color match
to palette, subject relevance). Download and embed in the slide.

### Keyword generation
Derive from slide title + primary content. Keep keywords concrete and visual:
- "quarterly results" → `"growth graph upward"` or `"business momentum"`
- "team introduction" → `"professional team collaboration"`
- "migration risk" → `"bridge construction"` or `"pathway forward"`
Avoid abstract queries that return random stock images. Prefer: people, places, objects, metaphors.

### Attribution
Unsplash requires attribution for API usage. Add automatically based on profile setting:

| Attribution setting | Behavior |
|---|---|
| `notes` (default) | Photo credit added to slide's speaker notes: `Photo by [Name] on Unsplash` |
| `footer` | Small text added to slide footer: `Photo: [Name] / Unsplash` |
| `none` | No attribution added (only use if deck will not be distributed publicly) |

Set in profile under `imagery.unsplash_attribution`. Default: `notes`.

### Unsplash API configuration
Store API key in plugin storage under `presentation:unsplash-config`. If not configured:
> *"Unsplash mode requires an API key. Get a free key at unsplash.com/developers and configure your Unsplash API key in presentation skill settings."*

Fallback if API unavailable: switch to icons mode for that slide, note in post-generation summary.

### Image placement
Follow the active profile's `imagery.placement` setting:
- `full-bleed` — image fills entire slide background; text overlaid with contrast overlay
- `right-panel` — image occupies right 40–50% of slide; text on left
- `inset` — image as a contained element within a content zone, not full-bleed
- `none` — no images (even in unsplash mode, some templates skip images)

Template determines which placements are valid. `title-hero` always full-bleed. `two-column`
uses right-panel. `stat-callout` ignores image mode entirely.

---

## Icon / UI Illustration Mode

### How it works
Select icons from registered iconsets (see [registry.md](registry.md) → Iconsets Schema).
Map slide content to icon categories. Compose icon clusters or single hero icons as visual
elements. Combine with colored backgrounds, geometric shapes, and typography to create a
designed, illustration-style slide rather than a photo slide.

### Icon selection logic
Map slide topic → icon category → specific icon:
```
"security" → tech category → shield icon
"growth" → data category → trending-up icon
"team" → people category → users icon
"timeline" → actions category → calendar icon
"warning / risk" → actions category → alert-triangle icon
```

### Icon composition styles
| Style | Description | Best for |
|---|---|---|
| `hero-single` | One large icon, centered, colored background | section dividers, concept slides |
| `cluster-3` | Three icons in a row with labels | three-point lists, comparisons |
| `inline` | Small icons inline with bullet points | agenda, process slides |
| `background-ghost` | Large low-opacity icon as background texture | stat-callout, quote slides |

### Icon style (line vs. filled)
Set in profile under `layout.icon_style`. Options: `line`, `filled`, `flat`.
Must be consistent across the deck. Apply the same style to all icons from the same iconset.

### Color application
Icons inherit palette colors. Primary icon color = profile's `accent` or `primary`.
On dark backgrounds: use light icon color. On light backgrounds: use primary or secondary.

---

## No Images Mode

When `imagery.default_mode = "none"`:
- All templates adapt to text/data-only layouts
- `title-hero` uses solid color background instead of image
- `two-column` becomes full-width text or text + chart/diagram only
- Speaker notes do not include attribution lines
- Post-generation summary notes: `Images: none`

---

## Post-Generation Image Summary

Always include in the generation summary:
```
Images: Unsplash (12 photos, attribution in speaker notes)
  — 2 slides fell back to icons (Unsplash returned no good match)
  — 1 slide has no image (stat-callout template)
```

Or:
```
Images: Icon/UI illustration (lucide-line iconset)
  — 14 slides with icons, 4 slides no image (stat-callout, data-chart)
```
