# Consistency — Cross-Deck and Within-Deck Consistency Checks

Checks that presentation elements are visually and structurally consistent within a deck, or
across two decks being compared. Called by the audit flow (for the consistency category score)
and directly when users request a comparison.

---

## Invocation

| Trigger | Source |
|---|---|
| Audit runs consistency category | Called by [audit.md](audit.md) with a single Deck Spec |
| User says "compare [deck-a] and [deck-b]" | Called by [audit.md](audit.md) in comparison mode with two Deck Specs |
| User says "check consistency of [deck]" | Direct invocation, single-deck mode |

---

## Single-Deck Consistency Rules

### Rule 1 — Heading Size Consistency

**Check**: Slides using the same template MUST use the same heading font-size.

| Condition | Severity |
|---|---|
| Variance ≤ 2px across same-template slides | PASS |
| Variance > 2px across same-template slides | WARN |

```
For each template type with ≥ 2 slides:
  collect heading font-sizes (from Deck Spec typography or computed CSS)
  max_size − min_size = variance
  if variance > 2px → WARN finding per deviant slide
```

Corrective: *"Normalize [template] heading to [modal_size]px across all [N] slides."*

---

### Rule 2 — Template Distribution

**Check**: No single template (excluding `section-divider`) should account for more than 50%
of non-divider slides. Heavy repetition reduces visual variety and audience engagement.

| Condition | Severity |
|---|---|
| No template > 50% of non-dividers | PASS |
| One template 51–65% of non-dividers | WARN |
| One template > 65% of non-dividers | FAIL |

```
non_divider_slides = slides where template != 'section-divider'
for each template type:
  pct = count(template) / len(non_divider_slides)
  if pct > 0.65 → FAIL
  elif pct > 0.50 → WARN
```

Corrective: *"[N] of [total] non-divider slides use [template] ([pct]%). Consider varying
with [suggested_alternatives] for visual rhythm."*

---

### Rule 3 — Color Palette Adherence

**Check**: All color values used in the deck should match the active profile's palette within
a luminance tolerance of ±5.

| Condition | Severity |
|---|---|
| All colors within ±5 luminance of a palette color | PASS |
| 1–3 off-palette colors | WARN |
| > 3 off-palette colors | FAIL |

```
for each hex color value in the Deck Spec:
  find nearest palette color by luminance delta
  if min_delta > 5 → off-palette violation
```

Luminance delta is computed as: `|L(spec_color) − L(palette_color)|` using relative luminance
(WCAG formula). Off-palette violations are grouped by slide for reporting.

Corrective: *"Slide [N] uses [hex] — nearest palette match is [palette_hex] (ΔL = [delta]).
Replace with [palette_hex] or add to palette."*

---

### Rule 4 — Section Divider Cadence

**Check**: At least one `section-divider` slide must appear within every run of 6 consecutive
content slides.

| Condition | Severity |
|---|---|
| No run of content slides exceeds 6 without a divider | PASS |
| A run of 7–9 content slides without a divider | WARN |
| A run of ≥ 10 content slides without a divider | FAIL |

```
max_run = 0, current_run = 0
for each slide in deck order:
  if template == 'section-divider':
    max_run = max(max_run, current_run)
    current_run = 0
  else:
    current_run += 1
max_run = max(max_run, current_run)

if max_run >= 10 → FAIL
elif max_run >= 7 → WARN
```

Corrective: *"Slides [N]–[M] form a run of [run] content slides without a divider.
Insert a `section-divider` around slide [midpoint]."*

---

### Rule 5 — Speaker Notes Presence

**Check**: All non-divider slides must have speaker notes.

| Condition | Severity |
|---|---|
| All non-divider slides have non-empty notes | PASS |
| 1–2 slides missing notes | WARN |
| > 2 slides missing notes | FAIL |

Corrective: *"Slide [N] '[title]' has no speaker notes. Add talking points for the presenter."*

---

## Consistency Score (single-deck)

```
score = 100
for each FAIL finding: score -= 20
for each WARN finding: score -= 8
floor score at 0
```

Returns integer 0–100. Called by [audit.md](audit.md) for the consistency category weight.

---

## Cross-Deck Comparison Mode

When comparing two decks, run all single-deck rules on each deck independently, then add
the cross-deck checks below.

### Cross-Deck Check 1 — Brand Alignment

Compare color palettes between the two decks. Report off-palette divergence.

| Condition | Severity |
|---|---|
| Both decks share the same active profile | PASS |
| Both decks use compatible palettes (all colors within ±5 luminance) | PASS |
| 1–3 palette color divergences | WARN |
| > 3 divergences or different profiles with incompatible palettes | FAIL |

### Cross-Deck Check 2 — Typography Alignment

Compare heading font-sizes for the same template types across the two decks.

| Condition | Severity |
|---|---|
| Same-template heading sizes match within ±2px | PASS |
| Variance > 2px for any template type | WARN |

### Cross-Deck Check 3 — Template Set Coverage

Report which templates appear in Deck A but not B and vice versa. Informational only.

```
only_in_a = templates(deck_a) - templates(deck_b)
only_in_b = templates(deck_b) - templates(deck_a)
```

Severity: INFO. No score deduction.

---

## Comparison Report Format

```
Deck Comparison: [deck-a] vs. [deck-b]
────────────────────────────────────────────────────────
                          [deck-a]     [deck-b]
Consistency score:          82           74
Heading size variance:      0px          4px  ← WARN
Template distribution:      PASS         PASS
Color palette:              PASS         3 off-palette  ← WARN
Section divider cadence:    PASS         FAIL (run of 11)
Speaker notes:              PASS         2 missing  ← WARN

Cross-deck
  Brand alignment:    compatible (same profile)
  Typography:         2px heading variance on two-column  ← WARN
  Template coverage:  [deck-b] missing: quote-pull, team-grid

Top cross-deck findings:
  [FAIL] deck-b: 11-slide run without section divider (slides 4–14)
  [WARN] deck-b: 3 off-palette colors (slides 3, 7, 12)
  [WARN] cross-deck: two-column heading 28px in deck-a, 30px in deck-b
```

---

## Integration with Other Refs

| Need | Read |
|---|---|
| Audit scoring context | [audit.md](audit.md) — Category: Consistency |
| CSS zone definitions | [css-contract.md](css-contract.md) |
| Template zone schemas | [templates.md](templates.md) |
