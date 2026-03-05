# Registry — Shared Design Asset Registry

A git-backed shared repository of reusable design components. Not user preferences — shared craft.
The registry stores the building blocks that profiles and decks are assembled from.

---

## What Lives in the Registry

```
registry/
├── palettes/            # Named color palettes
│   ├── corporate-bold.json
│   ├── startup-fresh.json
│   └── healthcare-clean.json
├── templates/           # Slide layout definitions
│   ├── stat-callout.json
│   ├── timeline.json
│   └── ...
├── layouts/             # Spatial composition rules
│   ├── executive-dense.json
│   └── investor-airy.json
├── iconsets/            # Icon family references or bundled SVGs
│   ├── lucide-line.json
│   └── phosphor-filled.json
└── strategies/          # Named design strategy bundles
    ├── executive-dense.json
    ├── investor-airy.json
    └── workshop-warm.json
```

---

## Registry Operations

Say "sync registry" or "pull registry" to pull the latest from the remote git repo. Say "push palette [name]", "push template [name]", or "push strategy [name]" to contribute an asset. Say "list registry" to show all assets by category, or "list palettes" to show palettes only. Say "show registry asset [name]" to display a specific asset. Say "set registry remote [url]" to configure the git remote URL. Say "registry status" to show sync status.

---

## Registry Configuration

Store remote URL in plugin storage under `presentation:registry-config`:
```json
{
  "remote_url": "https://github.com/your-org/design-registry",
  "branch": "main",
  "last_pulled": "2025-03-05T10:00:00Z",
  "auto_pull": false
}
```

`auto_pull: false` by default — always prompt before pulling. Set `true` to sync silently on
each session start.

---

## Palette Schema

```json
{
  "name": "corporate-bold",
  "version": "2025-Q1",
  "description": "Bold corporate palette — primary purple system",
  "colors": {
    "primary": "#A100FF",
    "secondary": "#460073",
    "accent": "#FFFFFF",
    "background_light": "#F5F5F5",
    "background_dark": "#1A0038",
    "text_on_light": "#1A1A1A",
    "text_on_dark": "#FFFFFF",
    "highlight": "#7B00CC"
  },
  "palette_raw": ["#A100FF", "#460073", "#FFFFFF", "#F5F5F5", "#1A1A1A"]
}
```

---

## Strategy Schema

A strategy bundles layout philosophy, density, and imagery preferences into a named approach.
Strategies are what differentiate "same palette, different feel."

```json
{
  "name": "executive-dense",
  "description": "High-information density for executive audiences. Data-forward, minimal decoration.",
  "density": "high",
  "margins": "tight",
  "preferred_templates": ["stat-callout", "data-chart", "two-column", "section-divider"],
  "avoid_templates": ["team-grid", "quote-pull", "closing-cta"],
  "image_treatment": "inset-right",
  "icon_usage": "minimal",
  "slide_count_bias": "lean",
  "tone": "formal"
}
```

```json
{
  "name": "investor-airy",
  "description": "Story-forward, spacious layouts for investor or board audiences.",
  "density": "low",
  "margins": "generous",
  "preferred_templates": ["title-hero", "stat-callout", "quote-pull", "closing-cta"],
  "avoid_templates": ["data-chart", "comparison-matrix"],
  "image_treatment": "full-bleed",
  "icon_usage": "none",
  "slide_count_bias": "lean",
  "tone": "narrative"
}
```

---

## Contributing to the Registry

When a user creates a new palette, template, or strategy they want to share:

1. The registry push flow stages the asset
2. Plugin formats it into the correct schema
3. Plugin shows a preview of the asset JSON:
   > "Ready to push to the registry. This will be visible to your team. Confirm?"
4. On confirm: commits to git remote, pushes
5. Reports: `✓ Pushed 'my-brand' palette to registry`

Contributors should add a `description` field — prompted if missing.

---

## Registry in the Wizard

During wizard profile selection, after listing local profiles:
- Check if registry cache is fresh (pulled within current session or within 24h if auto_pull)
- If stale: *"Your design registry hasn't been synced this session — pull latest? (yes / skip)"*
- Registry assets appear in the profile selection list under "Imported / Registry"
- Assembled profiles built from registry components record their sources in `registry_components`
  field — so if a registry asset updates, the user can be notified

---

## Iconsets Schema

```json
{
  "name": "lucide-line",
  "description": "Lucide icon set — clean line style, MIT licensed",
  "style": "line",
  "license": "MIT",
  "source_url": "https://lucide.dev",
  "categories": ["arrows", "actions", "data", "people", "tech", "finance"],
  "format": "svg",
  "usage_note": "Best at 24-48px. Use at consistent size across slide."
}
```
