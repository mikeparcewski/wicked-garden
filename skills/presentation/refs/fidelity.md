# Fidelity — Layout Quality Tiers

Fidelity controls how much effort the plugin invests in layout correctness before delivering
output. Three tiers. Higher fidelity takes more render passes and time; lower fidelity
produces content faster and leaves layout work for the user.

---

## The Three Tiers

### `best` — Client-Ready
**Motto:** *Don't stop until it looks right.*

Multiple render passes. After each pass, verify layout against a checklist. Re-render any
slide that fails. Iterate until all slides pass or the pass limit is reached.

Use when: presenting to a client, executive, or external audience. When the deck needs to be
handed off as-is. When polish matters more than speed.

**What gets verified per slide:**
- No text overflow — all copy fits within its content zone without clipping
- No element overlap — text boxes, images, and shapes don't collide
- Consistent heading sizes across slides of the same template type
- Consistent margin/padding — no slide feels significantly tighter or looser than others
- Image placement matches template spec — not drifted, stretched, or misaligned
- Speaker notes are present on all slides (not just flagged ones)
- Stat values are visually dominant — larger than labels
- Bullet lists don't exceed 6 items (split to new slide if needed)
- Section dividers are visually distinct from content slides (background contrast)
- Title slide and closing slide have strong visual weight

**Render loop:**
```
Pass 1: Generate all slides from Deck Spec
Pass 2: Run layout verification checklist on each slide
        → Flag any slides that fail
Pass 3: Re-render flagged slides with corrective instructions
Pass 4: Re-verify. If still failing: apply conservative fallback layout, flag as REVIEW.
        Stop after pass 4 regardless — don't loop forever.
```

**Time expectation:** Slower. Communicate to user before starting on large decks:
> *"Best fidelity on an 18-slide deck typically takes 3–4 render passes. Starting now..."*
> Show progress: *"Pass 1 complete. 4 slides flagged for layout correction. Running pass 2..."*

**Output note in summary:**
```
Fidelity: best (3 passes, 2 slides corrected, 1 REVIEW flag remaining)
```

---

### `draft` — First Draft
**Motto:** *Clean enough to present with minor edits.*

Single render pass with layout-aware generation. Content zones are respected, templates are
applied correctly, and obvious problems (massive overflow, elements off-slide) are avoided.
Minor imperfections are expected and acceptable — uneven spacing, slightly tight text,
image not perfectly cropped. User can clean these up in PowerPoint or HTML.

Use when: working session, internal review, iteration stage, or whenever you'll touch the
file before the final presentation. Default for most flows.

**What's enforced in a single pass:**
- Content placed in correct zones for the chosen template
- Heading and body font sizes from profile applied
- Profile colors applied to backgrounds, text, and accents
- Images sourced and placed per template spec
- No content placed off-slide or outside margins
- Bullet lists capped at 7 items (soft cap — warns but doesn't split)

**What may need user attention:**
- Text that's slightly tight may not wrap perfectly
- Image aspect ratios may not be ideal
- Spacing between elements may be uneven across slides
- Some stat values may not achieve full visual dominance

**Output note in summary:**
```
Fidelity: draft (1 pass — minor layout cleanup may be needed)
```

---

### `rough` — Structural Pass
**Motto:** *Content in, structure right, layout TBD.*

One pass. Content placed, slide order correct, speaker notes written. Layout is intentionally
not optimized — elements exist in approximately the right positions but sizing, spacing, and
visual polish are left entirely to the user.

Use when: you need the text and structure immediately, you're comfortable editing slides
yourself, or this is an input to another workflow (e.g., a designer will take it from here).
Also ideal when prototyping content before committing to full layout work.

**What's included:**
- All slide content from the Deck Spec (titles, body, stats, quotes, etc.)
- Correct template type applied (determines general zone structure)
- Profile colors applied to backgrounds and primary text
- Speaker notes written
- REVIEW flags preserved

**What's explicitly skipped:**
- Image sourcing (image zones left as labeled placeholders: `[IMAGE: query]`)
- Fine-grained sizing and positioning
- Font size hierarchy tuning
- Spacing and margin consistency
- Any multi-pass correction

**Output note in summary:**
```
Fidelity: rough (1 pass — layout needs user attention, images not sourced)
```

---

## Fidelity × Format Interaction

| Fidelity | PPTX behavior | HTML (reveal.js) behavior |
|---|---|---|
| `best` | Multiple PptxGenJS generation passes with coordinate/size verification | Multiple HTML renders; CSS layout verified via computed style checks; text overflow detected via scrollHeight vs clientHeight |
| `draft` | Single PptxGenJS pass, layout-aware prompting | Single HTML render, template CSS applied cleanly |
| `rough` | Single pass, minimal coordinate precision | Single render, placeholder divs for images, minimal CSS tuning |

For HTML output, layout verification in `best` mode uses JavaScript-based checks injected
into the rendered page to detect overflow and misalignment before finalizing the file.

---

## Fidelity in the Deck Spec

Fidelity is stored on the version record and in the spec:

```json
{
  "fidelity": "best",
  "render_passes": 3,
  "slides_corrected": 2,
  "slides_review_remaining": 1
}
```

**Re-rendering at higher fidelity:**
To upgrade fidelity on an existing deck, request re-render at best fidelity.
Takes the existing Deck Spec (content unchanged) and runs it through the full best-fidelity
render loop. Produces a new versioned file — does not overwrite the draft version.
```
deck-name_v2-draft.pptx       ← original
deck-name_v3-best.pptx        ← upgraded fidelity (new version)
```

---

## Fidelity Defaults by Mode

| Mode | Default fidelity | Rationale |
|---|---|---|
| Brainstorm (interactive) | `draft` | Interactive flow — user expects to iterate |
| Create (content-driven) | `draft` | Content pass first; polish in a follow-up |
| Fast path | `draft` | Speed is the point; best defeats the purpose |
| Overview | `rough` | Skeleton only — polish is irrelevant |
| Re-render | Inherits from request or previous version | Explicit re-render implies intentional quality lift |

User can always specify fidelity upfront or per request.

---

## Profile Default

Set `output.default_fidelity` in the profile. Options: `best`, `draft`, `rough`.
If not set, wizard asks. Fast path silently uses `draft` regardless of profile default
(to preserve fast-path speed contract) unless best fidelity is explicitly requested.

---

## Fidelity Hints

**Large deck + best fidelity:**
> *"Best fidelity on [N] slides will take multiple passes — estimated [2–4x] longer than draft.
> Proceed, or use draft now and re-render at best when you're happy with the content?"*

**Rough output with images disabled (reminder):**
> *"Rough fidelity skips image sourcing — image zones are placeholders. Request a re-render at draft fidelity to add images when ready."*

**Draft with overflow risk (many bullets):**
> *"A few slides have more content than the template comfortably fits. In draft mode these
> may overflow slightly — request best fidelity to have them auto-corrected, or split them manually."*
