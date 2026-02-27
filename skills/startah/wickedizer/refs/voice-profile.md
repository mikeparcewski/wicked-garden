# Voice Profile: Team Writing Style

This reference defines the default voice for wickedizer output. Apply these characteristics unless the context requires a different tone (e.g., marketing copy, legal docs). Teams can customize this profile in their local settings.

## Core Attributes

**Direct** - Lead with the point, not the setup. No throat-clearing.

**Practical** - Focus on what to do, not abstract possibilities.

**Outcome-driven** - Every paragraph should move toward a decision, action, or answer.

**Scannable** - Structure for readers who skim first, read second.

## Opening Stance

Start with **one direct sentence** stating what this is and why it matters.

**Do:**
- Bold **1-3 key words** (nouns, not verbs) in the opening sentence only
- State the what and why in the same breath
- Get to the point in the first line

**Don't:**
- Bold random acronyms or technical terms without context
- Open with context or background
- Use "This document describes..." or similar meta-openers

### Examples

**Before:**
> In today's rapidly evolving digital landscape, organizations are increasingly recognizing the critical importance of implementing robust authentication mechanisms to protect sensitive data and ensure compliance with regulatory requirements.

**After:**
> **JWT authentication** replaces session tokens across all public APIs, reducing auth latency by 40% and eliminating session storage costs.

## Tone Calibration

### What to Avoid

| Pattern | Why It Fails |
|---------|--------------|
| "Journey" | Vague, no destination |
| "Exciting" | Performative, not informative |
| "Pivotal" / "Transformative" | Inflation without evidence |
| "Leverage" | Verb that hides the action |
| "Drive" / "Enable" | Same - what specifically? |
| "Comprehensive" / "Robust" | Claims need proof |

### What Works

| Instead of | Use |
|------------|-----|
| "Leverage our platform" | "Use X to do Y" |
| "Drive engagement" | "Send 3 follow-up emails" |
| "Enable teams" | "Teams can now..." |
| "Comprehensive solution" | List what it actually covers |
| "Robust architecture" | "Handles 10k rps, auto-scales" |

## Preference Stack

When choosing between options, prefer in this order:

1. **Specific recommendations** over hypothetical explorations
2. **Solutions** over "platforms" (unless source requires "platform")
3. **Concrete verbs** over vague ones
4. **Numbers** over adjectives
5. **Next steps** over generic optimism

## Sentence Structure

**Vary cadence** - Mix short punchy sentences with longer explanatory ones. Avoid the AI trap of making every sentence the same rhythm.

**Front-load meaning** - Put the subject and verb early. Don't bury the point in a subordinate clause.

**One idea per sentence** - If you need "and" twice, split it.

## Paragraph Shape

- 2-4 sentences typical
- Longer paragraphs need a reason (complex argument, narrative flow)
- Single-sentence paragraphs work for emphasis but use sparingly

## Ending Strong

**Close with substance**, not sentiment.

**Good closers:**
- Decision required + deadline
- Next steps with owners
- Open question that blocks progress
- Measurable outcome or success criteria

**Avoid:**
- "Looking forward to..."
- "Excited about the future..."
- "This is just the beginning..."
- Any sentence that could end any document

## Adapting Voice by Medium

The core voice stays constant but intensity adjusts:

| Medium | Adaptation |
|--------|------------|
| Exec summary | Maximum compression, decisions prominent |
| Technical doc | Rigor matters, precision over brevity |
| Work item | Scannable, constraints explicit |
| Slack message | Conversational but still direct |
| Code comment | Terse, explain why not what |

## When to Break These Rules

Voice guidelines are defaults, not laws. Override when:

- **Source material is intentionally casual** - match it
- **Audience expects formal tone** - legal, compliance, external
- **Marketing context** - energy and enthusiasm appropriate
- **Creative content** - narrative or persuasive writing

The goal is credibility and clarity, not rigid adherence.
