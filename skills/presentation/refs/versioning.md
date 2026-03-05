# Versioning — Naming Conventions & History

Simple, non-destructive versioning using file naming conventions. Every generation run produces
a new versioned file. Plugin storage tracks metadata per version.

---

## Naming Convention

```
{deck-slug}_v{N}.pptx
{deck-slug}_v{N}-{label}.pptx
```

### Examples
```
sales-kickoff_v1.pptx
sales-kickoff_v2.pptx
sales-kickoff_v2.html
sales-kickoff_v2-client-review.pptx
sales-kickoff_v2-client-review.html
sales-kickoff_v3.pptx
quarterly-retro_v1-draft.pptx
quarterly-retro_v2-final.pptx
quarterly-retro_v2-final.html
```

When both formats are requested, both files share the same version number and label.
The Deck Spec (the content source) is always stored separately:
`presentation:specs:{slug}:{version}` — re-render any version to any format at any time.

### Rules
- Slug: derived from deck title, lowercased, spaces → hyphens, special chars stripped
- Version number: auto-increments from highest existing version for this slug
- Label: optional, appended with hyphen, alphanumeric + hyphens only
- Never overwrite an existing file — always increment

### Custom slug
Fast path accepts an optional name parameter for a custom slug. Otherwise derived from the topic or content title.

---

## Version Labels

### Interactive flows
After generation, prompt (optional):
> "Want to add a label to this version? (e.g., draft, client-review, final) — or press enter to skip"

### Fast path
Silently auto-increments. No label prompt. User can rename the file manually.

### Suggested labels
Plugin may suggest a label based on context:
- If research was used → suggest `research-pass`
- If overview flow → suggest `skeleton`
- If brainstorm flow → suggest `draft`
- If create flow with all content provided → suggest `content-pass`

---

## Version Metadata

Stored in plugin storage under `presentation:versions:{deck-slug}` as an array:

```json
[
  {
    "version": 1,
    "label": "draft",
    "filenames": ["sales-kickoff_v1-draft.pptx"],
    "formats_rendered": ["pptx"],
    "spec_key": "presentation:specs:sales-kickoff:v1",
    "fidelity": "draft",
    "render_passes": 1,
    "created_at": "2025-03-01T09:15:00Z",
    "mode": "brainstorm",
    "profile": "corporate-blue",
    "slide_count": 16,
    "source_files": ["strategy-doc.md", "project-scope.docx"],
    "research_used": false,
    "image_mode": "icons",
    "review_flags": 3,
    "templates_used": {
      "title-hero": 1,
      "section-divider": 3,
      "two-column": 6,
      "stat-callout": 2,
      "timeline": 1,
      "closing-cta": 1
    }
  },
  {
    "version": 2,
    "label": "client-review",
    "filenames": ["sales-kickoff_v2-client-review.pptx", "sales-kickoff_v2-client-review.html"],
    "formats_rendered": ["pptx", "html"],
    "spec_key": "presentation:specs:sales-kickoff:v2",
    "fidelity": "best",
    "render_passes": 3,
    "slides_corrected": 2,
    "created_at": "2025-03-03T14:30:00Z",
    "mode": "create",
    "profile": "corporate-blue",
    "slide_count": 18,
    "source_files": ["strategy-doc.md", "project-scope.docx", "team-feedback.md"],
    "research_used": true,
    "image_mode": "unsplash",
    "review_flags": 1,
    "templates_used": {
      "title-hero": 1,
      "section-divider": 3,
      "two-column": 7,
      "stat-callout": 3,
      "timeline": 1,
      "quote-pull": 1,
      "closing-cta": 1
    }
  }
]
```

---

## Operations

### List versions
Say "show version history for [deck]" or "list versions of sales-kickoff" to see all versions with metadata.

Output:
```
sales-kickoff — 2 versions

  v1  [draft]          2025-03-01  16 slides  brainstorm  corporate-blue  3 flags  pptx      fidelity:draft
  v2  [client-review]  2025-03-03  18 slides  create      corporate-blue  1 flag   pptx+html fidelity:best (3 passes)

Latest: sales-kickoff_v2-client-review.pptx / .html
Re-render: request "re-render sales-kickoff_v2 as <format>"
```

### Diff two versions
Say "diff v1 and v2 of sales-kickoff" to get a structural diff summary.

Output (structural summary, not visual diff):
```
sales-kickoff: v1 → v2

  Slide count:   16 → 18  (+2)
  Mode:          brainstorm → create
  Profile:       corporate-blue (same)
  Research:      off → on
  Images:        icons → unsplash
  Review flags:  3 → 1  (-2)

  Template changes:
    two-column:    6 → 7  (+1)
    stat-callout:  2 → 3  (+1)
    quote-pull:    0 → 1  (+1, new)

  New source files: client-feedback.md
```

### Build from prior version
At wizard startup, if versions exist for a topic:
> "Found 2 prior versions of 'sales-kickoff'. Start fresh or build from v2 (latest)?"

If building from prior: load that version's source files, profile, and structure as starting point.
Apply new inputs on top.

---

## Storage Cleanup

Say "clean up versions of sales-kickoff" to list all versions and choose which to keep. Removes metadata records for deleted files.
Does not delete actual PPTX files — user manages their own filesystem.
