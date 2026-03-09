# Content Lint — Slide Content Quality Checks

Rule-based checks for content quality issues in a Deck Spec. Produces structured findings with
severity levels. Called by the audit flow (content and lint categories) and available as a
standalone check.

---

## Invocation

| Trigger | Behavior |
|---|---|
| Audit runs content/lint categories | Called by [audit.md](audit.md) with full Deck Spec |
| User says "lint my deck" / "check content" | Standalone run, all six categories |
| User says "check bullets" / "check titles" | Targeted run, named category only |

---

## Lint Categories

Six categories. Each produces FAIL, WARN, or INFO findings per slide.

---

### Category 1 — Bullet Overload

Excessive bullet count reduces readability and forces cognitive overload.

| Condition | Severity | Threshold |
|---|---|---|
| > 7 bullets on a slide | FAIL | Hard limit |
| > 6 bullets on a slide | WARN | Soft limit |
| > 12 words in a single bullet | FAIL | Per-bullet hard limit |

```
for each slide:
  bullets = content zone bullet items
  if len(bullets) > 7 → FAIL "X bullets — hard limit is 7"
  elif len(bullets) > 6 → WARN "X bullets — soft limit is 6"
  for each bullet:
    if word_count(bullet) > 12 → FAIL "Bullet '[text]' is X words — limit is 12"
```

Corrective (count): *"Split into two slides or trim to [limit] bullets."*
Corrective (word count): *"Shorten '[bullet text]' to ≤ 12 words. Consider breaking into
sub-bullets or moving detail to speaker notes."*

---

### Category 2 — Title Hygiene

Slide titles anchor navigation, presenter confidence, and audience comprehension.

| Condition | Severity |
|---|---|
| Slide has no title | FAIL |
| Title exceeds 10 words | WARN |
| Duplicate title appears 2+ times in the deck | WARN |

```
titles = []
for each slide:
  title = slide.title
  if not title or title.strip() == '' → FAIL "Missing title"
  elif word_count(title) > 10 → WARN "Title is X words — aim for ≤ 10"
  titles.append((slide_index, title.lower().strip()))

duplicates = [t for t in titles if titles.count(t) > 1]
for each duplicate → WARN "Title '[text]' appears on slides [N, M]"
```

Corrective (missing): *"Add a descriptive title — even a placeholder helps navigation."*
Corrective (too long): *"Trim to ≤ 10 words: '[suggested_shorter_title]'."*
Corrective (duplicate): *"Differentiate slide titles to aid navigation and speaker recall."*

---

### Category 3 — Stat Formatting

Statistics are high-value content. They must be immediately scannable and clearly attributed.

| Condition | Severity |
|---|---|
| Stat value contains non-numeric characters (excluding %, $, ×, K, M, B, +, −) | WARN |
| Stat value has no accompanying label | WARN |
| Stat value string exceeds 8 characters | WARN |

```
for each slide where template == 'stat-callout':
  for each stat zone (zone-stat1, zone-stat2, zone-stat3):
    value = stat_zone.content
    label = stat_label_zone.content (sibling)

    allowed_non_numeric = ['%', '$', '×', 'K', 'M', 'B', '+', '−', '.', ',']
    if any char in value not in [digits + allowed_non_numeric] → WARN

    if not label or label.strip() == '' → WARN "Stat '[value]' has no label"

    if len(value.strip()) > 8 → WARN "Stat '[value]' is X chars — keep ≤ 8 for scannability"
```

Corrective (non-numeric): *"Stat '[value]' contains unexpected characters. Use a clean
numeric format: e.g., '47%', '$2.3M', '12×'."*
Corrective (no label): *"Add a brief label beneath '[value]' to explain what it measures."*
Corrective (too long): *"Shorten '[value]' — e.g., '1,234,567' → '1.2M'."*

---

### Category 4 — Quote Attribution

Unattributed quotes erode credibility and remove the social proof value of the quote.

| Condition | Severity |
|---|---|
| Quote slide has no attribution at all | FAIL |
| Attribution is present but lacks name AND role/company | WARN |

```
for each slide where template == 'quote-pull':
  attribution = zone-attribution.content

  if not attribution or attribution.strip() == '' → FAIL "Missing attribution"
  elif not has_name(attribution) or not has_role_or_company(attribution):
    → WARN "Attribution incomplete — include name and role or company"
```

`has_name`: attribution contains ≥ 1 capitalized word (heuristic for proper name).
`has_role_or_company`: attribution contains a comma, a title keyword, or parenthetical.

Corrective (missing): *"Add attribution to this quote: '— [Name], [Role], [Company]'."*
Corrective (incomplete): *"Expand attribution from '[current]' to include full name and
role or company for credibility."*

---

### Category 5 — Passive Voice Density

High passive voice density makes content feel abstract and less direct. Informational only —
does not affect audit scoring, but surfaces as an editing opportunity.

| Condition | Severity |
|---|---|
| Passive voice > 40% of sentences in body text | INFO |

```
for each slide:
  sentences = tokenize body and bullet text into sentences
  passive_count = count sentences matching passive voice patterns
  density = passive_count / len(sentences) if sentences else 0
  if density > 0.40 → INFO "X% of body sentences use passive voice"
```

Passive voice heuristic: sentence contains a form of "to be" (is, are, was, were, been, being)
followed within 3 words by a past participle (ends in -ed or irregular).

Corrective: *"[N]% of sentences are passive. Review for active-voice alternatives to improve
directness and impact. (Speaker notes not checked.)"*

---

### Category 6 — CTA Completeness

Closing slides must direct the audience to a clear next action.

| Condition | Severity |
|---|---|
| `closing-cta` slide has no action items in `.zone-cta-actions` | WARN |
| Action items present but none begins with an imperative verb | INFO |

```
for each slide where template == 'closing-cta':
  actions = zone-cta-actions.content.lines

  if len(actions) == 0 → WARN "No action items on closing slide"
  else:
    verb_led = [a for a in actions if starts_with_imperative_verb(a)]
    if len(verb_led) == 0 → INFO "Action items don't begin with imperative verbs"
```

Imperative verb heuristic: first word of the action item matches a common CTA verb list:
Book, Schedule, Visit, Download, Register, Contact, Email, Call, Sign up, Start, Join, Try,
Request, Submit, Apply, Learn, Get, Explore, Review, Reach out.

Corrective (no actions): *"Add 1–3 clear next steps to the closing slide."*
Corrective (no verbs): *"Lead each action with an imperative verb: 'Schedule a demo',
'Download the guide', 'Email us at contact@...'."*

---

## Findings Aggregation

Each category produces a list of findings. The combined list is returned to the caller
([audit.md](audit.md) or direct invocation).

### Full Findings Schema

```json
{
  "slide_index": 4,
  "slide_title": "Key Metrics",
  "template": "stat-callout",
  "category": "content",
  "lint_category": "stat_formatting",
  "type": "stat_no_label",
  "element": "zone-stat2",
  "detail": "Stat '47%' has no label",
  "severity": "WARN",
  "corrective": "Add a brief label beneath '47%' to explain what it measures."
}
```

| Field | Description |
|---|---|
| `slide_index` | 0-based slide position |
| `slide_title` | Slide title text |
| `template` | Template name |
| `category` | `content` or `lint` (maps to audit category) |
| `lint_category` | `bullet_overload`, `title_hygiene`, `stat_formatting`, `quote_attribution`, `passive_voice`, `cta_completeness` |
| `type` | Specific check identifier |
| `element` | Zone id or CSS class of the affected element |
| `detail` | Human-readable description |
| `severity` | `FAIL`, `WARN`, `INFO` |
| `corrective` | Suggested fix text |

---

## Severity Summary Output

When run standalone, output a summary after the findings list:

```
Content Lint — [deck-name] v[N]
────────────────────────────────
Bullet overload:    0 FAIL, 1 WARN
Title hygiene:      1 FAIL, 0 WARN
Stat formatting:    0 FAIL, 2 WARN
Quote attribution:  0 FAIL, 1 WARN
Passive voice:      —       3 INFO
CTA completeness:   0 FAIL, 1 WARN

Total: 1 FAIL, 4 WARN, 3 INFO
```

---

## Integration with Other Refs

| Need | Read |
|---|---|
| Audit scoring context | [audit.md](audit.md) — Category: Content and Category: Lint |
| Stat zone DOM structure | [css-contract.md](css-contract.md) — stat-callout section |
| Template zone definitions | [templates.md](templates.md) |
