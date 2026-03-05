# Profiles — Style Profile Management

A style profile is an assembled set of design decisions: colors, typography, layout preferences,
image mode, template preferences, and density. Profiles are the bridge between the design registry
(shared, component-level assets) and a specific deck's visual identity.

---

## Profile Types

### Learned Profiles
Created by the learn flow. Extracted from existing PPTX, PDF, or image assets.
Stored in `presentation:profiles` plugin storage. Local to this installation unless exported.

### Assembled Profiles
Built manually or during a wizard run by combining registry components:
- Pick a registry palette
- Pick a registry layout strategy
- Pick template preferences
- Save as a named profile
These are the sharable, team-consistent profiles.

### Imported Profiles
Pulled from `.pptprofile` files shared by teammates or stored in the registry.
Imported via the profile import flow or registry pull.

### Built-in Themes
Always available. No extraction required. Use when no profile exists.

| Name | Character |
|---|---|
| `minimal-light` | White background, dark text, clean sans-serif, generous whitespace |
| `minimal-dark` | Dark background, white text, premium feel |
| `enterprise-blue` | Corporate navy, structured layouts, moderate density |
| `corporate-bold` | Purple (`#A100FF`) primary, dark (`#460073`) secondary, bold geometric |

---

## Profile Operations

Say "list my profiles" to show all available profiles with source and date. Say "show profile [name]" to display full profile JSON. Say "export profile [name]" to produce a `.pptprofile` file for sharing. Say "import profile [file]" to register an imported profile. Say "set default profile [name]" to set the session default. Say "delete profile [name]" to remove a profile. Say "assemble a profile" for the interactive registry-component assembly flow.

---

## Profile Selection During Wizard

When a wizard flow reaches the style selection step, present available profiles grouped:

```
Style profile:

  Learned (from your assets):
    • my-brand           [high confidence] — extracted 2025-03-01
    • team-clinical      [medium confidence] — extracted 2025-02-15

  Imported / Registry:
    • corporate-q1-2025  — from team registry
    • team-project       — from team registry

  Built-in:
    • minimal-light  •  minimal-dark  •  enterprise-blue  •  corporate-bold

  Or: describe a vibe →
```

**Vibe matching:**
If user describes a vibe (e.g., "clean and modern", "bold and colorful", "dark executive"),
map to closest built-in + override suggestions. Examples:

| Vibe phrase | Maps to | Suggested overrides |
|---|---|---|
| "clean", "minimal", "airy" | minimal-light | large margins, no icons |
| "dark", "premium", "executive" | minimal-dark | stat-callout templates |
| "bold", "colorful", "energetic" | corporate-bold | high-saturation accent |
| "corporate", "safe", "formal" | enterprise-blue | conservative layouts |
| "warm", "human", "story-driven" | minimal-light | photographic images, pull quotes |

---

## .pptprofile Format

Exported profile format. Self-contained, portable, human-readable JSON.

```json
{
  "format": "pptprofile-v1",
  "name": "my-brand",
  "description": "Engineering team deck style — Q1 2025",
  "exported_at": "2025-03-05T14:00:00Z",
  "exported_by": "presentation",
  "colors": {
    "primary": "#CC0000",
    "secondary": "#1A1A1A",
    "accent": "#F5F5F5",
    "background_light": "#FFFFFF",
    "background_dark": "#1A1A1A",
    "text_on_light": "#222222",
    "text_on_dark": "#FFFFFF"
  },
  "typography": {
    "heading_font": "Helvetica Neue",
    "body_font": "Helvetica Neue",
    "heading_size_pt": 36,
    "body_size_pt": 16,
    "heading_weight": "bold"
  },
  "layout": {
    "density": "moderate",
    "margin_convention": "generous",
    "image_treatment": "full-bleed",
    "icon_style": "filled",
    "logo_position": "bottom-right"
  },
  "imagery": {
    "default_mode": "unsplash",
    "unsplash_attribution": "notes",
    "icon_style": "filled"
  },
  "template_preferences": {
    "preferred": ["two-column", "stat-callout", "title-hero"],
    "avoid": ["team-grid", "quote-pull"]
  },
  "registry_components": {
    "palette_source": "my-brand",
    "strategy_source": "executive-dense"
  }
}
```

---

## Profile Assembly (Interactive)

The profile assembly flow walks through:

1. Name this profile
2. Color palette — pick from registry, enter hex values, or extract from an asset
3. Typography — pick from registry or specify fonts
4. Layout strategy — pick from registry strategies
5. Template preferences — which templates to favor/avoid
6. Image mode default — unsplash / icons / none
7. Logo/brand asset — upload path or skip
8. Save and optionally set as default
