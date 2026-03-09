# Templates — Slide Template Library

Named slide layout patterns. The plugin selects templates automatically based on content type,
then applies the active profile's visual style on top.

---

## Template Selection Logic

Map content → template automatically:

| Content type | Default template |
|---|---|
| Opening / title | `title-hero` |
| Section break | `section-divider` |
| Single large statistic or 2–3 numbers | `stat-callout` |
| Narrative text + supporting visual | `two-column` |
| Chronological events / roadmap | `timeline` |
| Option A vs. Option B evaluation | `comparison-matrix` |
| Attributed quote or customer voice | `quote-pull` |
| Meeting agenda / structured list | `agenda` |
| Process steps / numbered flow | `process-steps` |
| Team members / roster | `team-grid` |
| Chart or graph as primary content | `data-chart` |
| Closing / next steps / call to action | `closing-cta` |
| No clear type | `two-column` (default fallback) |

User can override at any point: *"Use stat-callout for the ROI section"*

---

## Built-in Templates

### `title-hero`
Full-bleed visual background (image or solid color). Large centered title. Optional subtitle.
Minimal text. High visual impact. Use for: deck opener, major reveal slides.
```
[ FULL-BLEED IMAGE OR COLOR BACKGROUND                    ]
[                                                         ]
[           TITLE — large, centered or left-aligned       ]
[           Subtitle — smaller, optional                  ]
[                                                         ]
[ optional: logo bottom-right ]
```

---

### `stat-callout`
One dominant number (hero layout) or two to three numbers (row layout). Supporting label beneath
each stat. Optional brief context sentence at bottom. Data-forward, minimal decoration.
```
[ STAT 1 ]   [ STAT 2 ]   [ STAT 3 ]
[ label  ]   [ label  ]   [ label  ]

Optional: one-line context or source note
```

---

### `two-column`
Left column: text (headline + 3–5 bullets or short paragraph). Right column: image, diagram,
icon cluster, or chart. Columns can flip (image left, text right). Most versatile layout.
```
[ Headline                    | IMAGE / VISUAL              ]
[                             |                             ]
[ • Point one                 |                             ]
[ • Point two                 |                             ]
[ • Point three               |                             ]
```

---

### `timeline`
Horizontal or vertical. Events or milestones with dates/labels. Optional brief descriptions.
Use for: roadmaps, history, project phases.
```
●————————————————●————————————————●————————————————●
Q1 2025         Q2 2025         Q3 2025         Q4 2025
Phase 1         Phase 2         Phase 3         Launch
[description]   [description]   [description]   [description]
```

---

### `comparison-matrix`
Side-by-side columns. Header row per option. Rows for comparison criteria. Optional
winner/recommendation callout at bottom.
```
| Criteria        | Option A      | Option B      |
|-----------------|---------------|---------------|
| Cost            | $$            | $             |
| Speed           | Fast          | Moderate      |
| Risk            | Low           | Medium        |

→ Recommendation: Option A for [reason]
```

---

### `quote-pull`
Large attribution quote. Author name + role/company beneath. Optional supporting visual (portrait,
logo, or abstract). Use for: customer voice, executive endorsement, key insight emphasis.
```
[                                                         ]
[  "  Quote text — large, prominent, centered or left  " ]
[                                                         ]
[     — Author Name, Role, Company                        ]
[                                 optional: photo/logo    ]
```

---

### `agenda`
Structured numbered or bulleted list. Optional icons per item. Optional time/owner columns.
Use for: meeting agendas, table of contents, structured overview.
```
Today's Agenda

  01  Topic One ........................ 10 min
  02  Topic Two ........................ 20 min
  03  Topic Three ...................... 15 min
  04  Q&A .............................. 15 min
```

---

### `process-steps`
Numbered or connected flow. 3–6 steps optimal. Each step: number + title + brief description.
Horizontal (left-to-right) or vertical. Optional icons per step.
```
  [1]          [2]          [3]          [4]
  Discover  →  Design   →  Build    →  Launch
  [detail]     [detail]    [detail]    [detail]
```

---

### `team-grid`
Photo cards in a grid. Each card: photo + name + role. 2×2 to 3×3 grid typical.
If no photos available: initials in colored circle + name + role.
```
[ Photo ]  [ Photo ]  [ Photo ]
[ Name  ]  [ Name  ]  [ Name  ]
[ Role  ]  [ Role  ]  [ Role  ]
```

---

### `data-chart`
Chart or graph as primary content. Minimal surrounding text. Title above, brief insight
or callout below the chart. Chart types: bar, line, area, donut, scatter.
```
Slide Title

[ CHART — full width, prominent ]

→ Key insight: one sentence callout
```

---

### `section-divider`
Visual break between major sections. Section number + title. Optional brief teaser.
Typically uses a distinct background color (dark or accent) to signal transition.
```
[ DARK / ACCENT BACKGROUND                               ]
[                                                        ]
[   02                                                   ]
[   Section Title — large                                ]
[   Optional: one-line section preview                   ]
```

---

### `closing-cta`
Action-oriented final slide. Clear next step or call to action. Contact info optional.
High visual impact — treat like the title-hero.
```
[ STRONG BACKGROUND                                      ]
[                                                        ]
[   What happens next?                                   ]
[                                                        ]
[   → Next step one                                      ]
[   → Next step two                                      ]
[                                                        ]
[   contact@example.com  |  @handle                      ]
```

---

## Custom Templates (from Learn)

During style extraction, frequently recurring layouts in source decks are captured as custom
templates. They are stored in the profile with a generated name (`custom-layout-01`, etc.) and
can be renamed by the user.

Custom templates record: approximate column structure, content zone positions, and background
treatment. They are applied during generation as positioning guides.

---

## Template Schema (for registry contributions)

Each zone includes a `css_class` field that maps to the rendered HTML element class (see
[css-contract.md](css-contract.md) for the full class inventory and required CSS rules).
The `stat-callout` schema below is the exhaustive exemplar — all 12 templates follow the
same zone schema pattern. Use css-contract.md's class inventory table for zone-to-class mappings.

```json
{
  "name": "stat-callout",
  "description": "One to three dominant statistics with supporting labels. Data-forward.",
  "zones": [
    { "id": "stat1", "css_class": "zone-stat1", "type": "text", "role": "primary-stat", "position": "left-third" },
    { "id": "stat1-label", "css_class": "zone-stat-label", "type": "text", "role": "stat-label", "position": "left-third-label" },
    { "id": "stat2", "css_class": "zone-stat2", "type": "text", "role": "primary-stat", "position": "center-third" },
    { "id": "stat2-label", "css_class": "zone-stat-label", "type": "text", "role": "stat-label", "position": "center-third-label" },
    { "id": "stat3", "css_class": "zone-stat3", "type": "text", "role": "primary-stat", "position": "right-third" },
    { "id": "stat3-label", "css_class": "zone-stat-label", "type": "text", "role": "stat-label", "position": "right-third-label" },
    { "id": "context", "css_class": "zone-context", "type": "text", "role": "caption", "position": "bottom-full" }
  ],
  "density": "low",
  "image_support": false,
  "best_for": ["metrics", "results", "ROI", "KPIs"],
  "avoid_for": ["narrative", "process", "team"]
}
```

The `css_class` field is required for all zones in registry contributions. The renderer uses
it to apply the correct CSS class to each zone element. For repeated zones (`.zone-event-label`,
`.zone-step`, `.zone-member-card`), the `css_class` value is the same across all instances.

### Zone Schema Fields

| Field | Required | Description |
|---|---|---|
| `id` | yes | Unique zone identifier within the template |
| `css_class` | yes | CSS class applied to the rendered zone element |
| `type` | yes | `text`, `image` |
| `role` | yes | Semantic role: `heading`, `subheading`, `body`, `primary-stat`, `stat-label`, `caption`, `quote`, `callout`, `background`, `logo`, `supporting-visual`, `chart`, `card`, `table-header`, `table-column`, `step`, `label`, `eyebrow`, `structural` |
| `position` | yes | Named position token resolved to coordinates per 1920×1080 canvas |
