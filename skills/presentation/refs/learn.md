# Learn — Style Extraction

Extracts a reusable style fingerprint from existing assets. Saves as a named profile in plugin
storage. Accepts PPTX files, PDF files, and images (screenshots, mood boards, brand assets).

---

## Invocation

To extract styles, ask Claude to learn from a path, single file, multiple files, or refresh the current profile. Optionally name the profile. Examples: "learn my brand from ./assets", "extract styles from brand.pdf and logo.png", "refresh my current style profile", "learn and save as my-brand."

---

## Input Types

### PPTX Files
Primary source. Extract from slide XML and theme definitions:
- **Color palette**: pull from theme colors (`dk1`, `dk2`, `lt1`, `lt2`, `accent1`–`accent6`)
  plus computed dominant colors from slide backgrounds and shapes
- **Typography**: font families from theme (`majorFont`, `minorFont`), sizes from title/body
  placeholders across all slide layouts, weight conventions
- **Layout patterns**: analyze all slide layouts in slide master; count usage frequency across
  slides; identify top 5 most-used compositions
- **Spacing/density**: average text-to-whitespace ratio, margin conventions, object padding
- **Logo/brand placement**: detect recurring small images in consistent positions (header/footer/corner)
- **Icon usage**: detect small SVG or EMF shapes; classify style if possible

### PDF Files
Secondary source. Useful for brand guides, style documents, lookbooks:
- Render each page to image
- Extract dominant colors per page (k-means, k=6)
- Detect layout geometry: column structure, margin widths, text block positions
- Infer typography from text rendering (approximate — flag as "inferred, verify")
- Note visual language: photo-heavy vs. diagram-heavy vs. text-heavy

### Images (PNG, JPG, screenshots)
Tertiary source. Best for mood boards and brand references:
- Extract dominant color palette (k-means, k=5)
- Detect image style: photographic / illustrative / diagrammatic / typographic
- Infer density preference from visual complexity
- Cannot extract font information — flag as missing

### Mixed Input
When multiple file types provided: merge extractions, weight PPTX data highest, flag conflicts.
Example conflict: PPTX theme says navy primary, PDF brand guide shows purple primary →
`[REVIEW: conflicting primary colors found — PPTX: #1C2B5E, PDF: #6B2D8B. Which is authoritative?]`

---

## What Gets Extracted

```json
{
  "profile_name": "my-brand",
  "source_files": ["q3-deck.pptx", "brand-guide.pdf"],
  "extracted_at": "2025-03-05T14:22:00Z",
  "colors": {
    "primary": "#CC0000",
    "secondary": "#1A1A1A",
    "accent": "#F5F5F5",
    "background_light": "#FFFFFF",
    "background_dark": "#1A1A1A",
    "text_on_light": "#222222",
    "text_on_dark": "#FFFFFF",
    "palette_raw": ["#CC0000", "#1A1A1A", "#F5F5F5", "#888888", "#FFFFFF"]
  },
  "typography": {
    "heading_font": "Helvetica Neue",
    "body_font": "Helvetica Neue",
    "heading_size_pt": 36,
    "subheading_size_pt": 24,
    "body_size_pt": 16,
    "caption_size_pt": 12,
    "heading_weight": "bold",
    "body_weight": "regular"
  },
  "layout": {
    "preferred_layouts": ["two-column", "title-hero", "stat-callout"],
    "density": "moderate",
    "margin_convention": "generous",
    "image_treatment": "full-bleed",
    "icon_style": "filled",
    "logo_position": "bottom-right"
  },
  "imagery": {
    "primary_style": "photographic",
    "placement": "right-panel or full-bleed",
    "treatment": "high-contrast, slightly desaturated"
  },
  "inferred_flags": [],
  "review_flags": []
}
```

---

## Storage

Save profile to plugin storage under `presentation:profiles:<name>`.

After extraction, prompt:
> "Profile saved as '[name]'. Want to set this as your default for this project?"

If a profile with this name already exists:
> "A profile named '[name]' already exists (extracted [date]). Overwrite, rename, or cancel?"

---

## Matching Against Registry

After extraction, check `presentation:registry-cache` for palette/template similarity:
- Compare extracted primary color against registry palettes (delta-E color distance)
- If close match found (delta-E < 10): suggest
  > "This looks close to '[registry-palette-name]' in your registry. Use that as a base and override
  > with what I learned? (keeps things consistent with your team)"

---

## Extraction Quality Indicators

Report after extraction:

```
✓ Style extracted from 3 files (1 PPTX, 1 PDF, 1 image)
  Colors:     high confidence (from PPTX theme + PDF)
  Typography: medium confidence (PPTX confirmed, PDF inferred)
  Layouts:    high confidence (14 unique slide layouts analyzed)
  Imagery:    low confidence (1 image source only)
  ⚠ 1 conflict found — see REVIEW flag in profile
```

Low confidence fields are marked in the profile JSON and surfaced during wizard profile selection.
