# De-AI Pass: Removing AI-Generated Tells

This reference covers identifying and removing patterns that signal AI-generated content. The goal isn't to hide AI involvement - it's to remove artifacts that damage trust and clarity.

## Why This Matters

AI-generated content often fails not because it's wrong, but because it's recognizably synthetic. Readers develop "AI fatigue" and dismiss content that triggers pattern recognition.

**The fix isn't deception - it's quality.** Human writers produce these same patterns when writing lazily. We're removing bad writing habits, not fingerprints.

## The Five Categories of AI Tells

### 1. Chatbot Artifacts

Direct signals that text came from a conversation with an AI.

| Pattern | Example | Fix |
|---------|---------|-----|
| Sign-off phrases | "Hope this helps!" | Delete |
| Prompt acknowledgment | "Great question!" | Delete |
| Availability offers | "Let me know if you need more" | Delete |
| Validation filler | "That's a great approach" | Delete |
| Meta-commentary | "I'll break this down into sections" | Just do it |

**Rule:** If you wouldn't write it in a formal document, delete it.

### 2. Promotional Language

Excessive positivity and significance inflation.

| Pattern | Example | Fix |
|---------|---------|-----|
| Unearned superlatives | "groundbreaking", "revolutionary" | Remove or prove |
| Significance inflation | "pivotal moment", "game-changer" | State impact specifically |
| Future hype | "unprecedented opportunities" | Name the opportunities |
| Vague benefits | "driving value across the organization" | What value? For whom? |

**Rule:** If a claim can't be measured or verified, downgrade or delete it.

### 3. Hedge Stacking

Multiple qualifiers that destroy confidence.

**Before:**
> This approach could potentially possibly help to somewhat improve performance in certain scenarios.

**After:**
> This approach improves read performance for queries under 100ms.

| Hedge Stack | Problem | Better |
|-------------|---------|--------|
| "could potentially" | Double hedge | "can" or remove |
| "might be able to" | Triple hedge | "can" or state conditions |
| "in some cases, sometimes" | Redundant | Pick one, be specific |
| "it is believed that" | Passive + hedge | State source or remove |

**Rule:** One hedge per claim maximum. If you're that uncertain, cut the claim.

### 4. Structural Tells

Patterns in how content is organized.

| Pattern | Problem | Fix |
|---------|---------|-----|
| Rule of three | Everything in threes feels forced | Use 2 or 4 when that's the real count |
| Parallel construction | "Not just X, but Y. Not just Y, but Z" | Vary structure |
| Transitional spam | "Additionally... Furthermore... Moreover..." | Just continue |
| Cadence uniformity | Every sentence same length/shape | Vary rhythm |

**Rule:** Humans are messy. Perfect symmetry signals automation.

### 5. Vague Attribution

Citations to unnamed authorities.

| Pattern | Example | Fix |
|---------|---------|-----|
| Unnamed experts | "experts agree" | Name them or delete |
| Passive voice attribution | "it is widely accepted" | By whom? |
| Implied research | "studies show" | Cite or delete |
| Industry consensus | "industry leaders believe" | Name one |

**Rule:** Cite specifically or don't cite at all.

## The De-AI Process

### Pass 1: Delete Obvious Artifacts

Quick scan for chatbot phrases, sign-offs, meta-commentary. Delete on sight.

### Pass 2: Audit Claims

For each claim, ask:
- Can this be verified from the source input?
- Is it supported by evidence?
- Is it overstated?

Options: keep, downgrade to opinion, delete.

### Pass 3: Vary Structure

- Break up uniform sentence lengths
- Reduce transitions to only necessary ones
- Let section flow naturally

### Pass 4: Specificity Check

Replace each vague phrase with a specific alternative or delete:

| Vague | Ask | Specific |
|-------|-----|----------|
| "improve efficiency" | By how much? How measured? | "reduce processing time from 4s to 1.2s" |
| "enhance collaboration" | What action? What outcome? | "teams can now edit the same doc" |
| "streamline workflows" | Which workflows? What changes? | "approval requires 2 steps instead of 5" |

## When to Keep Hedges

Hedging isn't always wrong. Keep hedges when:

- **Genuine uncertainty exists** - "Performance may vary based on load"
- **Stating limitations** - "This approach works best for read-heavy workloads"
- **Legal/compliance requires it** - "Results not guaranteed"
- **Preliminary data** - "Initial tests suggest..."

The problem isn't hedging - it's hedging when you're not actually uncertain.

## Credibility Over Casualness

"Human" doesn't mean informal. It means:

- Claims match evidence
- Structure serves content
- Voice is consistent
- Reader trusts the text

A formal document can be human. A casual message can be AI-ish. The distinction is credibility, not tone.
