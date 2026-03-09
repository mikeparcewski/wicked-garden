# Audit — Deck Quality Audit

Comprehensive quality scoring for an existing deck. Runs in three modes: full, targeted, or
comparison. Produces a score, band, and prioritized remediation list.

---

## Invocation

| User says | Mode | Behavior |
|---|---|---|
| "audit my deck" / "audit [deck-name]" | full | All five categories scored |
| "audit the content of [deck-name]" | targeted | User selects one or more categories |
| "compare [deck-a] and [deck-b]" | comparison | Delegates to [consistency.md](consistency.md) |
| "quick audit" | full | Same as full, briefer output |

---

## Scoring Model

Five weighted categories. Aggregate score determines the quality band.

| Category | Weight | What it measures |
|---|---|---|
| Structure | 25% | Template appropriateness, slide count, section cadence, logical flow |
| Content | 30% | Clarity, density, title hygiene, stat formatting, quote attribution |
| CSS | 20% | Zone overflow, element overlap, stat visual dominance |
| Consistency | 15% | Heading sizes, color palette, template distribution, speaker notes |
| Lint | 10% | Bullet count, word count, passive voice, CTA completeness |

**Aggregate score** = sum of (category_score × weight). Integer 0–100.

### Quality Bands

| Band | Score range | Meaning |
|---|---|---|
| PASS | ≥ 80 | Deck is presentation-ready with minor polish optional |
| REVIEW | 60–79 | Presentable but has issues worth addressing before external use |
| FAIL | < 60 | Significant problems — remediate before presenting |

---

## Full Audit Flow

```
1. Load Deck Spec from presentation:specs
2. For each category: run checks → collect findings → compute category score
3. Apply weights → compute aggregate score → assign band
4. Sort findings by severity (FAIL > WARN > INFO)
5. Output: score card + top 10 prioritized findings + remediation suggestions
```

### Score Card Output

```
Deck: [deck-name]  Version: v[N]  Slides: [N]
──────────────────────────────────────────────
Structure    [score]/100  weight 25%  → [weighted]
Content      [score]/100  weight 30%  → [weighted]
CSS          [score]/100  weight 20%  → [weighted]
Consistency  [score]/100  weight 15%  → [weighted]
Lint         [score]/100  weight 10%  → [weighted]
──────────────────────────────────────────────
TOTAL        [score]/100  Band: [PASS|REVIEW|FAIL]
```

---

## Targeted Audit Flow

```
1. Ask: "Which categories? (structure, content, CSS, consistency, lint)"
2. Run only selected categories
3. Score selected categories only (re-weight proportionally among selected)
4. Output findings for selected categories only
```

---

## Category: Structure (25%)

| Check | Pass condition | Severity if fail |
|---|---|---|
| Template match | Template matches content type per selection logic | WARN |
| Slide count | 8–30 slides for a full deck | INFO |
| Section divider cadence | At least one divider per 6 content slides | WARN |
| Opener + closer | First slide `title-hero`, last slide `closing-cta` | WARN |
| Logical flow | Section order follows a recognizable narrative arc | INFO |
| No orphan sections | Every section has ≥ 2 content slides | WARN |

**Scoring**: Start at 100. Deduct per finding: FAIL −20, WARN −10, INFO −3.

---

## Category: Content (30%)

Runs content lint checks (see [content-lint.md](content-lint.md)) and maps findings to scores.

| Finding type | Points deducted per instance |
|---|---|
| FAIL finding | −15 |
| WARN finding | −7 |
| INFO finding | −2 |

Cap deductions at −100 (floor at 0).

---

## Category: CSS (20%)

Runs visual QA checks (see [fidelity.md](fidelity.md) — Visual QA section) and maps findings.

| Finding type | Points deducted per instance |
|---|---|
| Overflow detected | −20 |
| Element overlap | −15 |
| Stat dominance failure (severity WARN from fidelity.md Check 3) | −10 |

Cap deductions at −100 (floor at 0).

---

## Category: Consistency (15%)

Delegates checks to [consistency.md](consistency.md). Receives a consistency score (0–100) directly.

---

## Category: Lint (10%)

Runs content-lint checks (see [content-lint.md](content-lint.md)) and computes a lint-specific score.

| Finding count | Score |
|---|---|
| 0 | 100 |
| 1–2 | 85 |
| 3–5 | 65 |
| 6–10 | 40 |
| > 10 | 15 |

---

## Findings Schema

Each finding uses this structure:

```json
{
  "slide_index": 3,
  "slide_title": "Q1 Results",
  "template": "stat-callout",
  "category": "content",
  "type": "bullet_overload",
  "element": ".zone-context",
  "detail": "9 bullets found — limit is 7 (FAIL at 8+)",
  "severity": "FAIL",
  "corrective": "Split into two slides or reduce to 7 bullets."
}
```

| Field | Type | Description |
|---|---|---|
| `slide_index` | int | 0-based slide position |
| `slide_title` | string | Slide title text |
| `template` | string | Template name |
| `category` | string | `structure`, `content`, `css`, `consistency`, `lint` |
| `type` | string | Specific check identifier |
| `element` | string | CSS selector or zone id of the affected element |
| `detail` | string | Human-readable finding description |
| `severity` | string | `FAIL`, `WARN`, `INFO` |
| `corrective` | string | Suggested fix |

---

## Remediation Output Format

After the score card, list the top 10 findings sorted by severity then score impact:

```
Top Findings (sorted by severity)
──────────────────────────────────
[FAIL] Slide 3 "Q1 Results" — 9 bullets in stat context zone
       → Split into two slides or reduce to 7 bullets.

[FAIL] Slide 7 "Process Overview" — title missing
       → Add a descriptive title to this slide.

[WARN] Slide 5 "Team Intro" — heading size variance 4px across same-template slides
       → Normalize h1 to a consistent px value across all two-column slides.

[INFO] Slides 2, 4, 6 — passive voice density > 40%
       → Review body copy for active-voice alternatives.
```

---

## Audit Storage

Audit results are transient — not persisted across sessions. Within a session, the most recent
audit result is available at `presentation:session.last_audit`. Structure:

```json
{
  "deck_name": "q1-results",
  "version": "v3",
  "timestamp": "2025-03-15T10:22:00Z",
  "scores": {
    "structure": 88,
    "content": 72,
    "css": 95,
    "consistency": 81,
    "lint": 90
  },
  "aggregate": 82,
  "band": "PASS",
  "findings": [ ... ]
}
```

---

## Re-audit After Fix

After a remediation pass, user can say "re-audit" to run the full audit again on the current
version. Produces a diff summary:

```
Re-audit vs. prior run
──────────────────────
Structure:   88 → 92  (+4)
Content:     72 → 85  (+13) ← 3 FAIL findings resolved
CSS:         95 → 95  (no change)
Consistency: 81 → 81  (no change)
Lint:        90 → 95  (+5)  ← passive voice density improved
──────────────────────
TOTAL:       82 → 88  (+6)  Band: PASS (was PASS)
```

---

## Integration with Other Refs

| Need | Read |
|---|---|
| Visual QA JavaScript checks | [fidelity.md](fidelity.md) — Visual QA section |
| Content findings detail | [content-lint.md](content-lint.md) |
| Consistency scoring | [consistency.md](consistency.md) |
| CSS zone definitions | [css-contract.md](css-contract.md) |
