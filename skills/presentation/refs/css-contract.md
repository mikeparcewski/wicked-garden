# CSS Contract — Slide and Zone Class Definitions

Canonical CSS naming conventions for all rendered HTML slides. These class names are the contract
between the Deck Spec, the template renderer, and the visual QA checks.

---

## Naming Conventions

| Element | Pattern | Example |
|---|---|---|
| Slide wrapper | `.slide-{template-name}` | `.slide-title-hero` |
| Zone element | `.zone-{zone-id}` | `.zone-title`, `.zone-stat1` |
| Stat label (sibling) | `.zone-stat-label` | Follows `.zone-stat*` immediately |

All template names use kebab-case. Zone IDs match the `id` field in the template zone schema
(see [templates.md](templates.md)).

---

## Zone Coordinate Source

Zone coordinates (top, left, width, height) are defined **per-template** in the zone schema
documented in [templates.md](templates.md). The renderer reads zone position and size from the
schema and applies them as absolute CSS values. Zone coordinates are expressed as percentages
of slide dimensions (1920×1080 reference canvas) and converted to `px` at render time.

**Coordinate resolution order:**
1. Active profile overrides (if the profile customizes a template's zone positions)
2. Template schema defaults from [templates.md](templates.md)
3. Conservative fallback positions (see Conservative Fallback below)

No zone coordinate is hardcoded in this file — always read from the template schema.

---

## Universal Zone Rules

All zone elements MUST include:

```css
.zone-* {
  box-sizing: border-box;
  overflow: hidden;
  position: absolute;
}
```

These three properties are required on every zone regardless of type. The renderer injects
them as a base layer before applying type-specific rules.

---

## Zone Type Rules

Applied in addition to universal rules based on zone `type` field in the template schema.

### Text Zones (`type: "text"`)

```css
font-size: [N]px;        /* explicit px — never em or rem */
line-height: [N];        /* numeric, unitless — e.g. 1.3 */
```

Font size comes from the active profile's typography settings for the zone's `role` field.

### Image Zones (`type: "image"`)

```css
object-fit: contain | cover;   /* contain for logos/diagrams; cover for full-bleed photos */
```

`contain` is the safe default. Override to `cover` only for full-bleed background zones.

### Stat Zones (`role: "primary-stat"`)

```css
font-size: [N]px;    /* minimum 36px */
font-weight: bold;
```

Stat labels (`.zone-stat-label`) paired with a stat zone:

```css
font-size: [N]px;    /* minimum 28px; must be < stat font-size */
```

The stat value element (`.zone-stat*`) MUST be immediately followed by a `.zone-stat-label`
sibling in the DOM. The visual QA dominance check relies on this sibling relationship.

---

## Full Class Inventory

### `.slide-title-hero`

| Zone class | Type | Role | object-fit |
|---|---|---|---|
| `.zone-background` | image | background | cover |
| `.zone-title` | text | heading | — |
| `.zone-subtitle` | text | subheading | — |
| `.zone-logo` | image | logo | contain |

### `.slide-stat-callout`

| Zone class | Type | Role | Min font-size |
|---|---|---|---|
| `.zone-stat1` | text | primary-stat | 36px |
| `.zone-stat-label` (after stat1) | text | stat-label | 28px |
| `.zone-stat2` | text | primary-stat | 36px |
| `.zone-stat-label` (after stat2) | text | stat-label | 28px |
| `.zone-stat3` | text | primary-stat | 36px |
| `.zone-stat-label` (after stat3) | text | stat-label | 28px |
| `.zone-context` | text | caption | — |

### `.slide-two-column`

| Zone class | Type | Role |
|---|---|---|
| `.zone-headline` | text | heading |
| `.zone-body` | text | body |
| `.zone-visual` | image | supporting-visual |

### `.slide-timeline`

| Zone class | Type | Role | Notes |
|---|---|---|---|
| `.zone-timeline-track` | text | structural | Horizontal or vertical track |
| `.zone-event-label` | text | label | Repeated — one per event |

### `.slide-comparison-matrix`

| Zone class | Type | Role |
|---|---|---|
| `.zone-criteria` | text | table-header |
| `.zone-option-a` | text | table-column |
| `.zone-option-b` | text | table-column |
| `.zone-recommendation` | text | callout |

### `.slide-quote-pull`

| Zone class | Type | Role |
|---|---|---|
| `.zone-quote-text` | text | quote |
| `.zone-attribution` | text | caption |
| `.zone-visual` | image | supporting-visual |

### `.slide-agenda`

| Zone class | Type | Role |
|---|---|---|
| `.zone-agenda-title` | text | heading |
| `.zone-agenda-items` | text | body |

### `.slide-process-steps`

| Zone class | Type | Role | Notes |
|---|---|---|---|
| `.zone-step` | text | step | Repeated — up to 6 instances |

### `.slide-team-grid`

| Zone class | Type | Role | Notes |
|---|---|---|---|
| `.zone-member-card` | image+text | card | Repeated — one per team member |

### `.slide-data-chart`

| Zone class | Type | Role |
|---|---|---|
| `.zone-chart-title` | text | heading |
| `.zone-chart-area` | image | chart |
| `.zone-chart-insight` | text | callout |

### `.slide-section-divider`

| Zone class | Type | Role |
|---|---|---|
| `.zone-section-number` | text | eyebrow |
| `.zone-section-title` | text | heading |
| `.zone-section-preview` | text | subheading |

### `.slide-closing-cta`

| Zone class | Type | Role |
|---|---|---|
| `.zone-cta-headline` | text | heading |
| `.zone-cta-actions` | text | body |
| `.zone-cta-contact` | text | caption |

---

## Conservative Fallback Layout

When visual QA detects unresolvable layout failures after pass 3, the renderer applies the
conservative fallback. This guarantees legibility at the cost of visual design.

```css
/* Conservative fallback — applied when best-fidelity passes 3–4 fail */
.slide-* {
  padding: 48px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.zone-title, .zone-headline, .zone-cta-headline, .zone-section-title {
  font-size: 28px;
  line-height: 1.2;
}

.zone-body, .zone-agenda-items, .zone-cta-actions {
  font-size: 16px;
  line-height: 1.4;
}

.zone-stat1, .zone-stat2, .zone-stat3 {
  font-size: 36px;
  font-weight: bold;
}

.zone-visual, .zone-background, .zone-chart-area {
  display: none;  /* images omitted in conservative fallback */
}
```

Slides rendered via conservative fallback are flagged as `status: REVIEW` in the findings
schema. The audit summary line reads: `conservative fallback applied`.

---

## CSS Contract Validation

During visual QA, the rendered DOM is checked against this contract:

| Check | Method |
|---|---|
| Slide class present | `document.querySelector('.slide-{template}')` exists |
| All expected zone classes present | Each zone in the template schema has a matching element |
| Universal rules applied | `getComputedStyle(zone).boxSizing === 'border-box'` |
| Text zones have explicit px font-size | `getComputedStyle(zone).fontSize` ends in `px` |
| Stat zones meet minimum font-size | parsed px value ≥ 36px |
| Stat-label zones meet minimum | parsed px value ≥ 28px |

Violations are reported as CSS-category findings in the audit findings schema.

---

## Integration with Other Refs

| Need | Read |
|---|---|
| Zone coordinate values | [templates.md](templates.md) — Template Schema section |
| Visual QA JavaScript implementation | [fidelity.md](fidelity.md) — Visual QA section |
| Audit scoring for CSS category | [audit.md](audit.md) — Category: CSS section |
